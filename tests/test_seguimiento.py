"""Avisos de precio, aportación mensual, diario de inversiones, ayuda para la Renta y pendientes."""

from datetime import date, datetime

import pandas as pd
import pytest

from bolsa import agenda, alertas, aportaciones, cartera, costes, diario, renta


def velas(precios, inicio="2026-10-01", freq="B"):
    idx = pd.date_range(inicio, periods=len(precios), freq=freq)
    c = pd.Series(precios, index=idx, dtype=float)
    return pd.DataFrame({"Open": c, "High": c * 1.01, "Low": c * 0.99, "Close": c, "Volume": 1.0})


# --------------------------------------------------------------------------- avisos de precio
def test_no_deja_crear_un_aviso_que_ya_se_cumple():
    lista = []
    assert "ya está por debajo" in alertas.nueva(lista, "IDR.MC", "Indra", "baja", 200, 190)
    assert "ya está por encima" in alertas.nueva(lista, "IDR.MC", "Indra", "sube", 200, 210)
    assert alertas.nueva(lista, "IDR.MC", "Indra", "baja", 200, 230, hoy=date(2026, 10, 1)) is None
    assert lista[0]["id"] == 1 and lista[0]["disparada"] is None


def test_aviso_salta_cuando_se_toca_el_nivel_despues_de_crearlo():
    lista = []
    alertas.nueva(lista, "IDR.MC", "Indra", "baja", 200, 230, hoy=date(2026, 10, 1))
    # El mismo día de creación tocó 198 por la mañana, pero cerró en 230: no cuenta.
    hist = {"IDR.MC": velas([230, 220, 205, 199, 210])}
    hist["IDR.MC"].iloc[0, hist["IDR.MC"].columns.get_loc("Low")] = 198
    nuevos = alertas.revisar(lista, hist)
    assert [a["disparada"] for a in nuevos] == ["2026-10-06"]     # 199 * 0,99 < 200 el cuarto día hábil
    assert alertas.revisar(lista, hist) == []                     # no salta dos veces


def test_aviso_de_subida():
    lista = []
    alertas.nueva(lista, "SAN.MC", "Santander", "sube", 14, 12.5, hoy=date(2026, 10, 1))
    assert alertas.revisar(lista, {"SAN.MC": velas([12.5, 13, 13.5, 13.6])}) == []
    assert len(alertas.revisar(lista, {"SAN.MC": velas([12.5, 13, 13.5, 14.2])})) == 1


def test_cruce_en_la_ultima_hora_solo_si_antes_estaba_al_otro_lado():
    lista = []
    alertas.nueva(lista, "IDR.MC", "Indra", "baja", 200, 230, hoy=date(2026, 10, 15))
    idx = pd.date_range("2026-10-15 09:00", periods=24, freq="5min")
    precios = [210] * 12 + [199] * 12
    df = pd.DataFrame({"Open": precios, "High": precios, "Low": precios, "Close": precios}, index=idx, dtype=float)
    cruces = alertas.cruces_en_ventana(lista, {"IDR.MC": df}, datetime(2026, 10, 15, 10), datetime(2026, 10, 15, 11))
    assert len(cruces) == 1 and cruces[0]["precio_ahora"] == 199
    # La hora siguiente sigue por debajo: no es un cruce nuevo, no vuelve a avisar.
    df2 = pd.concat([df, df.iloc[-12:].set_axis(df.index[-12:] + pd.Timedelta(hours=1))])
    assert alertas.cruces_en_ventana(lista, {"IDR.MC": df2}, datetime(2026, 10, 15, 11),
                                     datetime(2026, 10, 15, 12)) == []
    assert "ha bajado de 200,00" in alertas.texto(cruces[0], 199)


# --------------------------------------------------------------------------- aportación mensual
def test_fecha_del_mes_se_mueve_al_lunes_y_al_ultimo_dia():
    assert aportaciones.fecha_del_mes(31, 2026, 2) == date(2026, 3, 2)     # 28/02/2026 es sábado
    assert aportaciones.fecha_del_mes(5, 2026, 10) == date(2026, 10, 5)


def test_pendiente_y_proxima():
    cfg = {"importe": 300, "dia": 5, "hechas": []}
    assert not aportaciones.pendiente(cfg, date(2026, 10, 4))
    assert aportaciones.pendiente(cfg, date(2026, 10, 15))
    assert aportaciones.proxima(cfg, date(2026, 10, 15)) == date(2026, 10, 15)
    cfg["hechas"].append({"fecha": "2026-10-15", "importe": 300})
    assert not aportaciones.pendiente(cfg, date(2026, 10, 20))
    assert aportaciones.proxima(cfg, date(2026, 10, 20)) == date(2026, 11, 5)
    assert aportaciones.racha(cfg, date(2026, 10, 20)) == 1


def test_el_dinero_nuevo_va_a_lo_que_falta():
    # Mucho en acciones sueltas (como una cartera concentrada) y nada en el fondo: todo al fondo y al monetario.
    actuales = {"Acciones individuales": 180_000}
    objetivo = {"Monetario / Letras del Tesoro": 10, "Renta fija a corto plazo": 15, "Fondo indexado mundial": 60,
                "Acciones individuales": 15}
    r = aportaciones.repartir(500, actuales, objetivo)
    assert "Acciones individuales" not in r
    assert sum(r.values()) == pytest.approx(500)
    assert max(r, key=r.get) == "Fondo indexado mundial"


def test_reparto_sin_trozos_pequenos():
    objetivo = {"Monetario / Letras del Tesoro": 5, "Fondo indexado mundial": 70, "Acciones individuales": 25}
    r = aportaciones.repartir(100, {}, objetivo)
    assert all(v >= aportaciones.MINIMO_POR_DESTINO for v in r.values())
    assert sum(r.values()) == pytest.approx(100)


def test_valores_por_destino():
    pos = [{"clase": "Acciones", "valor": 1000}, {"clase": "Fondos y ETF", "valor": 500},
           {"clase": "Criptomonedas", "valor": 300}]
    assert aportaciones.valores_por_destino(pos, 200) == {"Acciones individuales": 1000,
                                                          "Fondo indexado mundial": 500,
                                                          "Monetario / Letras del Tesoro": 200}


# --------------------------------------------------------------------------- diario
def test_diario_pide_motivo_y_avisa_cuando_toca_revisar():
    lista = []
    assert "por qué" in diario.nueva(lista, "IDR.MC", "Indra", "Compra", 200, "  ")
    assert diario.nueva(lista, "IDR.MC", "Indra", "Compra", 200, "Contratos de defensa", 3,
                        hoy=date(2026, 7, 15)) is None
    assert lista[0]["revisar"] == "2026-10-15"
    assert diario.pendientes(lista, date(2026, 10, 14)) == []
    assert len(diario.pendientes(lista, date(2026, 10, 15))) == 1
    e = diario.evaluar(lista[0], 230)
    assert e["cambio"] == pytest.approx(0.15) and "a tu favor" in e["frase"]
    diario.marcar_revisada(lista, 1, "Bien, pero pesa demasiado", hoy=date(2026, 10, 15))
    assert diario.pendientes(lista, date(2026, 10, 20)) == []


def test_diario_venta_que_luego_sube():
    e = {"nombre": "Indra", "accion": "Venta", "precio": 200.0}
    assert "reducir riesgo" in diario.evaluar(e, 220)["frase"]
    assert "ahorrado" in diario.evaluar(e, 180)["frase"]


# --------------------------------------------------------------------------- Renta
def _cartera_con_historia():
    c = cartera.nueva(None)
    t = costes.Tarifa()
    cartera.comprar(c, "SAN.MC", 1000, 10.0, t, "2025-03-01")
    cartera.comprar(c, "IDR.MC", 100, 100.0, t, "2025-03-01")
    cartera.vender(c, "SAN.MC", 1000, 12.0, t, "2026-05-10")                 # ganancia
    cartera.vender(c, "IDR.MC", 100, 80.0, t, "2026-06-10")                  # pérdida...
    cartera.comprar(c, "IDR.MC", 100, 82.0, t, "2026-07-01")                 # ...y recompra antes de 2 meses
    return c


def test_ventas_del_ano_y_regla_de_los_dos_meses():
    v = renta.ventas_del_ano(_cartera_con_historia()["historial"], 2026)
    assert [x["ticker"] for x in v] == ["SAN.MC", "IDR.MC"]
    assert v[0]["resultado"] > 1900 and not v[0]["aplazada"]
    assert v[1]["resultado"] < 0 and v[1]["aplazada"]
    assert v[0]["importe_venta"] - v[0]["importe_compra"] == pytest.approx(v[0]["resultado"])
    r = renta.resumen(v, [])
    assert r["perdidas"] == 0 and len(r["aplazadas"]) == 1      # la pérdida aplazada no resta este año


def test_dividendos_segun_titulos_en_la_fecha_ex():
    h = _cartera_con_historia()["historial"]
    divs = {"SAN.MC": pd.Series([0.10, 0.12], index=pd.to_datetime(["2026-04-30", "2026-10-31"]))}
    d = renta.dividendos_del_ano(h, divs, {}, 2026)
    assert len(d) == 1 and d[0]["acciones"] == 1000 and d[0]["bruto"] == pytest.approx(100)  # en octubre ya no tenía
    assert d[0]["retencion"] == pytest.approx(19)


def test_compensaciones_del_irpf():
    ventas = [{"resultado": -1000.0, "aplazada": False}]
    divs = [{"bruto": 2000.0, "retencion": 380.0, "extranjero": False}]
    r = renta.resumen(ventas, divs)
    assert r["compensacion_cruzada"] == pytest.approx(500)          # 25 % de los dividendos
    assert r["base_ahorro"] == pytest.approx(1500)
    assert r["perdidas_para_futuro"] == pytest.approx(500)
    assert r["cuota"] == pytest.approx(285)
    # Pérdidas de años anteriores: primero contra ganancias de ventas.
    r2 = renta.resumen([{"resultado": 3000.0, "aplazada": False}], [], perdidas_anteriores=1000)
    assert r2["base_ahorro"] == pytest.approx(2000) and r2["perdidas_anteriores_usadas"] == pytest.approx(1000)


def test_csv_para_excel_en_espanol():
    v = renta.ventas_del_ano(_cartera_con_historia()["historial"], 2026)
    texto = renta.tabla_csv(v, [])
    assert texto.splitlines()[0].startswith("Tipo;Fecha;Valor")
    assert "regla de los 2 meses" in texto


# --------------------------------------------------------------------------- pendientes
def test_pendientes_juntan_todo_en_orden():
    d = {"alertas": [{"id": 1, "ticker": "IDR.MC", "nombre": "Indra", "tipo": "baja", "precio": 200.0, "nota": "",
                      "creada": "2026-10-01", "disparada": "2026-10-14", "precio_disparo": 198.0}],
         "aportacion": {"importe": 300, "dia": 5, "hechas": []},
         "diario": [{"id": 1, "nombre": "Indra", "revisar": "2026-10-01", "revisada": None}]}
    p = agenda.pendientes(d, date(2026, 10, 15))
    assert [x["icono"] for x in p] == ["🔔", "💶", "📓"]
    assert "Toca tu aportación" in agenda.texto_telegram(d, date(2026, 10, 15))
    d["alertas"][0]["vista"] = True
    assert [x["icono"] for x in agenda.pendientes(d, date(2026, 10, 15))] == ["💶", "📓"]
    assert any(x["icono"] == "🧾" for x in agenda.pendientes({}, date(2027, 5, 1)))
    assert agenda.pendientes({}, date(2026, 10, 15)) == []


def test_ventana_de_la_ultima_hora_en_hora_de_madrid():
    import sys
    from pathlib import Path
    from zoneinfo import ZoneInfo

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import alertas as script

    desde, hasta = script.ventana(datetime(2026, 10, 15, 9, 7, tzinfo=ZoneInfo("UTC")))   # 11:07 en Madrid
    assert (desde, hasta) == (datetime(2026, 10, 15, 10), datetime(2026, 10, 15, 11))
    desde, _ = script.ventana(datetime(2026, 12, 15, 9, 7, tzinfo=ZoneInfo("UTC")))        # invierno: 10:07
    assert desde == datetime(2026, 12, 15, 9)
