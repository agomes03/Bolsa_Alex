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
