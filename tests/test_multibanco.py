import io
from datetime import date

import numpy as np
import pandas as pd
import pytest

from bolsa import activos, asesor_diario, bankinter, costes, importador

from test_diagnostico import CSV_BANKINTER


def resolver_falso(q):
    tabla = {"IE00B03HD191": {"symbol": "0P0000YXJO.F", "name": "Vanguard Global Stock Index", "type": "MUTUALFUND"},
             "US0378331005": {"symbol": "AAPL", "name": "Apple Inc.", "type": "EQUITY"}}
    return tabla.get(q)


def test_importa_bankinter_con_el_importador_universal():
    df = importador.leer_archivo(io.BytesIO(CSV_BANKINTER.encode()), "Posición global.csv")
    assert df[["ticker", "acciones", "precio_medio"]].to_dict("records") == [
        {"ticker": "SAN.MC", "acciones": 1200, "precio_medio": 10.46},
        {"ticker": "ITX.MC", "acciones": 100, "precio_medio": 45.0}]


def test_formato_tipo_caixabank_con_isin_y_fondo_con_decimales():
    texto = ("Nombre del valor;ISIN;Nº títulos;Precio medio de compra;Valoración\n"
             "IBERDROLA;ES0144580Y14;200;12,50;3.100,00\n"
             "VANGUARD GLOBAL STOCK INDEX FUND EUR ACC;IE00B03HD191;35,1234;45,10;1.900,00\n")
    df = importador.leer_texto(texto, resolver_falso)
    assert df["ticker"].tolist() == ["IBE.MC", "0P0000YXJO.F"]
    assert df["acciones"].tolist() == [200, pytest.approx(35.1234)]
    assert df["clase"].tolist() == ["Acciones", "Fondos y ETF"]


def test_tabla_pegada_en_ingles_con_bitcoin_y_coste_total():
    texto = "Name\tISIN\tShares\tTotal cost\nBitcoin\t\t0,05\t2.500,00\nApple\tUS0378331005\t3\t541,50\n"
    df = importador.leer_texto(texto, resolver_falso)
    assert df["ticker"].tolist() == ["BTC-EUR", "AAPL"]
    assert df["precio_medio"].tolist() == [pytest.approx(50_000), pytest.approx(180.5)]
    assert df["clase"].tolist() == ["Criptomonedas", "Acciones"]


def test_cabecera_tras_filas_de_resumen_y_isin_en_columna_de_codigo():
    texto = ("Cartera de valores;;;\nTitular;XXXX;;\nProducto;Código;Participaciones;Coste medio\n"
             "Fondo Mundial;IE00B03HD191;10;40\n")
    df = importador.leer_texto(texto, resolver_falso)
    assert df.iloc[0]["ticker"] == "0P0000YXJO.F" and df.iloc[0]["isin"] == "IE00B03HD191"


def test_sin_identificar_queda_vacio_para_corregir():
    df = importador.leer_texto("Valor;Títulos;Precio medio\nEMPRESA RARA SA;10;5\n")
    assert df.iloc[0]["ticker"] == "" and df.iloc[0]["clase"] == "—"


def test_clases_de_activo():
    assert activos.clase_de("SAN.MC") == "Acciones"
    assert activos.clase_de("IWDA.AS") == "Fondos y ETF"
    assert activos.clase_de("XEON.DE") == "Monetario y liquidez"
    assert activos.clase_de("BTC-EUR") == "Criptomonedas"
    assert activos.clase_de("4GLD.DE") == "Oro y materias primas"
    assert activos.clase_de("GS", "EQUITY", "Goldman Sachs") == "Acciones"
    assert costes.divisa("BTC-EUR") == "EUR"
    assert costes.tasa_tobin_pct("IWDA.AS") == 0 and costes.tasa_tobin_pct("BTC-EUR") == 0
    assert costes.tasa_tobin_pct("SAN.MC") == 0.2


def test_lectura_de_un_activo():
    c = pd.Series(np.linspace(100, 150, 300), index=pd.bdate_range("2025-01-01", periods=300))
    e = activos.estado(pd.DataFrame({"Close": c}))
    assert e["alcista"] and e["desde_maximo"] == pytest.approx(0) and e["var_1a"] > 0
    assert "tendencia alcista" in activos.lectura("Oro", e)


def test_tarifa_personal_y_trade_republic():
    tr = costes.TARIFAS_PRECARGADAS["Trade Republic"]
    assert tr.coste(1_000, "SAN.MC") == pytest.approx(1.0) and tr.coste(1_000, "AAPL") == pytest.approx(1.0)
    otro = costes.TarifaPersonal(nacional_fija=5, internacional_fija=10, divisa_pct=0.5, custodia_anual_valor=12,
                                 canon_nacional=1)
    assert otro.coste(2_000, "SAN.MC") == pytest.approx(6.0)
    assert otro.coste(2_000, "AAPL") == pytest.approx(20.0)
    assert otro.custodia_anual(5_000, "AAPL") == 12 and otro.custodia_anual(5_000, "SAN.MC") == 0
    assert costes.acciones_asequibles(1_000, 10, "SAN.MC", otro) < 100


def test_textos_de_ordenes_segun_el_broker():
    try:
        bankinter.BROKER = "Trade Republic"
        t = bankinter.ticket_stop("SAN.MC", 10, 9.0)
        assert "Buscar en Trade Republic" in t and "Bankinter" not in t
        assert "OCO" in bankinter.ticket_stop_relacionadas("SAN.MC", 10, 9.0, 12.0)
    finally:
        bankinter.BROKER = "Bankinter"
    assert "Bankinter" in bankinter.ticket_stop("SAN.MC", 10, 9.0)


def test_asesor_del_dia_prioriza_y_dice_cuando_no_hay_nada():
    informe = {"proteccion": {"^IBEX": {"estado": "fuera"}}, "mercado": {"semaforo": "rojo"}}
    posiciones = [{"ticker": "SAN.MC", "nombre": "Santander", "nivel": "poner_stop", "consejo": "Pon stop"}]
    dg = {"clases": {"Criptomonedas": 0.1}, "hallazgos": [{"gravedad": "alta", "titulo": "Indra pesa", "texto": "x"}]}
    btc = [{"nombre": "Bitcoin (€)", "clase": "Criptomonedas", "var_1d": -9.5}]
    plan = asesor_diario.plan_del_dia(dg, posiciones, informe, btc, hoy=date(2026, 10, 15))
    assert plan[0]["titulo"].startswith("Protección activada")
    titulos = [a["titulo"] for a in plan]
    assert "Santander" in titulos and "Indra pesa" in titulos and any("Bitcoin" in t for t in titulos)
    assert [a["prioridad"] for a in plan] == sorted(a["prioridad"] for a in plan)
    vacio = asesor_diario.plan_del_dia({"clases": {}, "hallazgos": []}, [], {}, [], hoy=date(2026, 10, 15))
    assert vacio[0]["titulo"] == "Nada urgente hoy"


def test_isin_de_etf_conocido_va_a_la_cotizacion_en_euros():
    df = importador.leer_texto("Producto;ISIN;Participaciones;Coste medio\niShares Core MSCI World;IE00B4L5Y983;10;90\n",
                               lambda q: {"symbol": "IWDA.L", "name": "x", "type": "ETF"})
    assert df.iloc[0]["ticker"] == "IWDA.AS"
    assert "tipos de interés" in activos.lectura("Monetario", {"var_1a": 2.0}, "Monetario y liquidez")


def test_consejos_repetidos_se_agrupan_en_una_linea():
    posiciones = [{"ticker": t, "nombre": n, "nivel": "poner_stop", "consejo": "x", "stop_sugerido": s}
                  for t, n, s in [("SAN.MC", "Banco Santander", 11.07), ("ITX.MC", "Inditex", 53.3),
                                  ("IDR.MC", "Indra", 59.6)]]
    dg = {"clases": {}, "hallazgos": [
        {"gravedad": "alta", "titulo": "Indra pesa el 53 % de tu dinero", "texto": "x"},
        {"gravedad": "media", "titulo": "Inditex pesa el 31 % de tu dinero", "texto": "x"}]}
    plan = asesor_diario.plan_del_dia(dg, posiciones, {}, [], hoy=date(2026, 10, 15))
    titulos = [a["titulo"] for a in plan]
    assert "Sin stop-loss: Banco Santander, Inditex e Indra" in titulos
    assert "Indra (53 %) e Inditex (31 %) pesan demasiado" in titulos
    assert len(plan) == 2
    assert "Indra a 59,60" in plan[[a["titulo"] for a in plan].index("Sin stop-loss: Banco Santander, Inditex e Indra")]["texto"]
