"""Funciones inspiradas en otras apps: rentabilidad por periodos, calendario, look-through de fondos, ficha de 5 ejes
y libertad financiera."""

from datetime import date, datetime, timezone

import pandas as pd

from bolsa import eventos, ficha, fondos, libertad, rentabilidad


def test_rentabilidad_por_periodos_con_las_posiciones_de_hoy():
    dias = pd.bdate_range("2024-01-01", "2026-10-16")
    precio = pd.Series(range(len(dias)), index=dias, dtype=float) / 100 + 10
    serie = rentabilidad.valor_diario({"A": 10, "B": 5}, {"A": precio, "B": precio * 2})
    assert serie.iloc[-1] == 10 * precio.iloc[-1] + 5 * precio.iloc[-1] * 2
    periodos = {p["periodo"]: p["pct"] for p in rentabilidad.por_periodos(serie, variacion_hoy=0.5)}
    assert periodos["Hoy"] == 0.5 and periodos["1 año"] > periodos["1 mes"] > 0
    assert "5 años" not in periodos                         # no hay tanta historia


def test_calendario_de_resultados_y_dividendos():
    hoy = date(2026, 10, 16)
    ts = datetime(2026, 10, 28, tzinfo=timezone.utc).timestamp()
    funds = {"SAN.MC": {"earningsTimestamp": ts, "exDividendDate": datetime(2026, 10, 29, tzinfo=timezone.utc)
                        .timestamp()},
             "ITX.MC": {"exDividendDate": datetime(2026, 9, 1, tzinfo=timezone.utc).timestamp()}}   # ya pasó
    lista = eventos.proximos({"SAN.MC": "Santander", "ITX.MC": "Inditex"}, funds, hoy)
    assert [(e["nombre"], e["tipo"], e["dias"]) for e in lista] == [("Santander", "resultados", 12),
                                                                    ("Santander", "ex_dividendo", 13)]
    manana = eventos.proximos({"SAN.MC": "Santander"}, funds, date(2026, 10, 27))
    assert "mañana" in eventos.texto_telegram(manana)


def test_look_through_suma_lo_directo_y_lo_que_llevan_los_fondos():
    comp = {"IWDA.AS": {"top": [{"simbolo": "SAN.MC", "nombre": "Santander", "peso": 0.01},
                                {"simbolo": "AAPL", "nombre": "Apple", "peso": 0.05}],
                        "sectores": {"technology": 0.3}}}
    r = fondos.exposicion({"SAN.MC": 1000}, {"IWDA.AS": 9000}, comp, {"SAN.MC": "Santander", "IWDA.AS": "MSCI World"})
    san = next(e for e in r["empresas"] if e["nombre"] == "Santander")
    assert san["directo"] == 1000 and abs(san["via_fondos"] - 90) < 1e-9 and r["solapes"][0]["nombre"] == "Santander"
    assert r["sectores"] == {"Tecnología": 2700.0} and r["cubierto"] == 1.0


def test_ficha_de_cinco_ejes():
    f = ficha.ficha({"trailingPE": 12, "forwardPE": 10, "priceToBook": 1.0, "targetMeanPrice": 15,
                     "dividendYield": 5, "payoutRatio": 0.5, "fiveYearAvgDividendYield": 4.5}, precio=11)
    assert f["Valoración"]["puntos"] == 6.0 and f["Dividendo"]["puntos"] >= 5
    assert f["Salud"]["puntos"] is None                     # sin datos suficientes: no se inventa
    assert "fuerte en valoración y dividendo" in ficha.resumen(f).lower()


def test_libertad_financiera():
    r = libertad.calcular(2000, 100_000, 1000, 0.04, 0.04)
    assert r["objetivo"] == 600_000 and r["renta_hoy"] == 100_000 * 0.04 / 12
    esc = r["escenarios"]
    assert esc["Optimista"]["anos"] < r["anos"] < esc["Pesimista"]["anos"]
    assert libertad.calcular(1000, 400_000, 0, 0.04)["anos"] == 0


def test_letras_del_tesoro():
    from bolsa import letras

    assert round(letras.precio(2.0, 364), 2) == 980.18           # 1.000 / (1 + 0,02·364/360)
    r = letras.calcular(10_000, 2.0, 364)
    assert r["letras"] == 10 and round(r["intereses"], 2) == 198.21
    assert round(r["impuesto"], 2) == round(r["intereses"] * 0.19, 2)
    assert letras.calcular(500, 2.0, 91)["letras"] == 0


def test_catalogo_grande_sin_grupos_vacios_y_mercados_completo():
    from bolsa import tickers
    from paginas_mercados import GRUPOS_ACCIONES, PESTANAS

    assert all(tickers.CATALOGO.values())
    assert set(GRUPOS_ACCIONES) | (set(PESTANAS) - {"Acciones"}) == set(tickers.CATALOGO)
    assert len(tickers.TODOS_LOS_VALORES) > 450
    assert tickers.nombre_de("TLGO.MC") == "Talgo"


def test_nombre_de_lo_encontrado_con_el_buscador():
    from bolsa import tickers

    assert tickers.nombre_de("QQQ1.XX") == "QQQ1.XX"
    tickers.NOMBRES_BUSCADOS["QQQ1.XX"] = "Algo Raro"
    try:
        assert tickers.nombre_de("QQQ1.XX") == "Algo Raro"
    finally:
        tickers.NOMBRES_BUSCADOS.pop("QQQ1.XX")


def test_cotizaciones_en_bloque_en_trozos_de_150(monkeypatch):
    from yfinance.data import YfData

    from bolsa import datos

    pedidas = []

    def falso(self, url, params=None, timeout=None):
        simbolos = params["symbols"].split(",")
        pedidas.append(len(simbolos))
        return {"quoteResponse": {"result": [
            {"symbol": s, "regularMarketPrice": 110.0, "regularMarketPreviousClose": 100.0,
             "regularMarketChangePercent": 10.0, "regularMarketTime": 1_792_165_352,
             "exchangeTimezoneName": "Europe/Madrid", "fiftyTwoWeekChangePercent": 25.0,
             "twoHundredDayAverage": 90.0, "fiftyTwoWeekHigh": 120.0} for s in simbolos if s != "MAL"]}}

    monkeypatch.setattr(YfData, "get_raw_json", falso)
    tickers = [f"T{i}" for i in range(320)] + ["MAL"]
    r = datos.cotizaciones_bloque(tickers)
    assert sorted(pedidas) == [21, 150, 150] and len(r) == 320 and "MAL" not in r
    q = r["T0"]
    assert q["precio"] == 110 and q["anterior"] == 100 and q["alcista"] and round(q["desde_maximo"], 2) == -8.33
    assert q["var_1a"] == 25 and str(q["fecha"]) == "2026-10-16"
    # precios_recientes usa lo rápido y no descarga nada más si está todo
    assert datos.precios_recientes(["T1", "T2"])["T2"]["variacion_pct"] == 10


def test_catalogo_mundial_por_niveles():
    from bolsa import tickers

    assert len(tickers.TODOS_LOS_VALORES) > 2000
    assert {"Acciones de España", "Acciones de Europa", "Acciones de EEUU",
            "Acciones del resto del mundo"} <= set(tickers.CATEGORIAS)
    assert all(g in tickers.CATALOGO for gs in tickers.CATEGORIAS.values() for g in gs)
    assert tickers.grupo_de("RHM.DE") == "Alemania" and tickers.categoria_de("Alemania") == "Acciones de Europa"
    assert tickers.nombre_de("ITX.MC") == "Inditex"              # el nombre escrito a mano manda
    assert "NVD.DE" not in tickers.CATALOGO["Alemania"]          # Nvidia en Fráncfort no es una empresa alemana
    assert max(len(d) for d in tickers.CATALOGO.values()) <= 200  # listas cortas para el móvil


def test_fondo_desde_importes_del_banco():
    from bolsa import cartera

    n, p = cartera.desde_importes(66_598.66, -2_315.09, 2_443.91)
    assert round(n, 4) == 27.2509 and round(p, 2) == 2528.86
    assert cartera.desde_importes(0, 0, 10) == (0.0, 0.0)


def test_buscar_con_el_nombre_del_banco(monkeypatch):
    import yfinance

    from bolsa import datos

    def falso(q, max_results=15, news_count=0):
        # Como Yahoo: con el nombre completo no da nada; con «bankinter bolsa», las dos clases
        quotes = [] if "espana" in q.lower() or "españa" in q.lower() else [
            {"symbol": "0P0001DEY6.F", "longname": "Bankinter Bolsa España C FI", "quoteType": "MUTUALFUND"},
            {"symbol": "0P00000PGI.F", "longname": "Bankinter Bolsa España R FI", "quoteType": "MUTUALFUND"}]
        return type("R", (), {"quotes": quotes})()

    monkeypatch.setattr(yfinance, "Search", falso)
    assert datos.buscar_simbolos("BANKINTER BOLSA ESPAÑA FI - R")[0]["symbol"] == "0P00000PGI.F"
    assert datos.buscar_simbolo("Bankinter Bolsa España FI - C")["symbol"] == "0P0001DEY6.F"
