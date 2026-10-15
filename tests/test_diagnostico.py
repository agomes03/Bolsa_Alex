import io

import pytest

from bolsa import bankinter, costes, diagnostico

# Mismo formato que la exportación «Posición global» de Bankinter (separador ';', primera fila de resumen,
# números en formato español y apóstrofo delante de los negativos). Datos inventados.
CSV_BANKINTER = """Mi posición;;;;;;;;;;;;"20.000,00";EUR;;;;;
Valor;Ticker;Mercado;Posición;Último;Fecha / Hora;Importe variación diaria;% variación diaria;Importe rentabilidad diaria;% rentabilidad diaria;Importe rentabilidad total;% rentabilidad total;Valoración;Divisa;Alias/Cuenta;Títulos depositados;Títulos disponibles;Títulos prestados;Precio medio
BANCO SANTANDER;SAN;CONTINUO;1.200;"10,000";13:31 d;"'-0,094";"'-0,770";"'-112,80";"'-0,77";"'-552,00";"'-4,40";"12.000,00";EUR;*0000;1.200;1.200;0;"10,460"
INDITEX;ITX;CONTINUO;100;"50,00";13:31 d;"0,96";"1,770";"96,00";"1,77";"500,00";"11,11";"5.000,00";EUR;*0000;100;100;0;"45,00"
"""


def test_importa_formato_real_de_bankinter():
    df = bankinter.leer_archivo(io.BytesIO(CSV_BANKINTER.encode("utf-8")), "Posición global.csv")
    assert df.to_dict("records") == [
        {"ticker": "SAN.MC", "nombre": "BANCO SANTANDER", "acciones": 1200, "precio_medio": 10.46},
        {"ticker": "ITX.MC", "nombre": "INDITEX", "acciones": 100, "precio_medio": 45.0},
    ]


def test_numero_con_apostrofo_negativo():
    assert bankinter.numero("'-1.059,25") == -1059.25


def _pos(ticker, acciones, medio, precio, stop=None):
    return {"ticker": ticker, "acciones": acciones, "precio_medio": medio, "precio": precio, "stop": stop}


def test_diagnostico_cartera_concentrada():
    pos = [_pos("SAN.MC", 2500, 12.46, 12.0), _pos("ITX.MC", 1000, 56.74, 55.0), _pos("IDR.MC", 1500, 60.8, 62.0)]
    d = diagnostico.diagnosticar(pos, tarifa=costes.Tarifa())
    assert d["semaforo"] == "rojo"
    assert d["paises"] == {"España": pytest.approx(1.0)}
    assert 2 < d["n_efectivo"] < 3
    titulos = " ".join(h["titulo"] for h in d["hallazgos"])
    assert "Indra" in titulos and "Sin stop-loss" in titulos
    # Ninguna empresa por encima del 20 % tras la propuesta, y no se vende la que ya está por debajo.
    assert {v["ticker"] for v in d["propuesta"]} == {"ITX.MC", "IDR.MC"}
    assert all(v["queda_peso"] <= 0.2 for v in d["propuesta"])
    # La pérdida de Inditex compensa parte de la ganancia de Indra.
    gan = {v["ticker"]: v["ganancia"] for v in d["propuesta"]}
    assert gan["ITX.MC"] < 0 < gan["IDR.MC"]
    assert d["ganancia_realizada"] == pytest.approx(sum(gan.values()))
    assert d["impuesto"] == pytest.approx(costes.impuesto_ganancia(d["ganancia_realizada"]))
    # El dinero liberado va a un fondo indexado si no hay perfil.
    assert set(d["destino"]) == {"Fondo indexado mundial"}
    assert d["liberado"] == pytest.approx(sum(v["importe"] - v["coste"] for v in d["propuesta"]))
    assert sum(d["pesos_despues"].values()) == pytest.approx(sum(d["pesos_antes"].values()) - d["costes_venta"])


def test_diagnostico_perfil_reparte_destino_y_avisa():
    pos = [_pos("SAN.MC", 100, 10, 10, stop=9)]
    d = diagnostico.diagnosticar(pos, otros_ahorros=0, perfil="Moderado", tarifa=costes.Tarifa())
    assert any("perfil moderado" in h["titulo"] for h in d["hallazgos"])
    assert set(d["destino"]) == {"Monetario / Letras del Tesoro", "Renta fija a corto plazo", "Fondo indexado mundial"}
    assert sum(d["destino"].values()) == pytest.approx(d["liberado"])


def test_diagnostico_cartera_diversificada_sin_ventas():
    tickers = ["SAN.MC", "ITX.MC", "IBE.MC", "REP.MC", "TEF.MC", "AENA.MC", "FER.MC", "ACS.MC"]
    pos = [_pos(t, 10, 100, 100, stop=90) for t in tickers] + [_pos("IWDA.AS", 280, 100, 100)]
    d = diagnostico.diagnosticar(pos, otros_ahorros=4_000, perfil="Dinámico", tarifa=costes.Tarifa())
    assert d["propuesta"] == [] and d["impuesto"] == 0
    # El fondo indexado pesa el 70 %, pero no es una «empresa»: no hay avisos graves.
    assert not any(h["gravedad"] in ("alta", "media") for h in d["hallazgos"]), d["hallazgos"]
    assert any("encaja" in h["titulo"] for h in d["hallazgos"])


def test_diagnostico_multiactivo_cripto_y_oro():
    pos = [_pos("IWDA.AS", 100, 100, 100), _pos("BTC-EUR", 0.05, 50_000, 60_000), _pos("4GLD.DE", 30, 100, 100)]
    d = diagnostico.diagnosticar(pos, perfil="Moderado", tarifa=costes.Tarifa())
    assert d["clases"]["Criptomonedas"] == pytest.approx(3000 / 16000)
    titulos = " ".join(h["titulo"] for h in d["hallazgos"])
    assert "Criptomonedas" in titulos and "Oro y materias primas" in titulos
    assert "stop-loss" not in titulos            # a un fondo o al bitcoin no se le pide stop-loss
    assert d["propuesta"] == []


def test_diagnostico_sin_posiciones():
    assert diagnostico.diagnosticar([])["semaforo"] == "sin_datos"


def test_las_vigiladas_sin_stop_no_cuentan_como_sin_stop():
    from bolsa import diagnostico as dg_mod

    pos = [{"ticker": "SAN.MC", "acciones": 100, "precio_medio": 10, "precio": 11, "fx": 1.0, "sin_stop": True},
           {"ticker": "ITX.MC", "acciones": 10, "precio_medio": 50, "precio": 55, "fx": 1.0}]
    titulos = [h["titulo"] for h in dg_mod.diagnosticar(pos)["hallazgos"]]
    sin = [t for t in titulos if t.startswith("Sin stop-loss")]
    assert sin and "Santander" not in sin[0] and "Inditex" in sin[0]
