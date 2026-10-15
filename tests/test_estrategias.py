import numpy as np
import pandas as pd
import pytest

from bolsa import estrategias, experimentos
from bolsa.costes import Tarifa
from test_modelos import hist


def cierres_sinteticos(n=12, dias=900):
    idx = pd.bdate_range("2020-01-01", periods=dias)
    datos = {}
    for i in range(n):
        tendencia = 0.0004 * (i - n / 2)  # unas suben y otras bajan
        rng = np.random.default_rng(i)
        datos[f"T{i}.MC"] = 100 * np.cumprod(1 + tendencia + rng.normal(0, 0.01 + 0.002 * i, dias))
    return pd.DataFrame(datos, index=idx)


def test_composicion_momentum_elige_las_que_mas_suben():
    c = cierres_sinteticos()
    perm = pd.DataFrame(True, index=c.index, columns=c.columns)
    comp = estrategias.composicion_hoy(c, perm, estrategias.CARTERAS["dinamica"])
    assert len(comp) == 10
    mom = estrategias.momentum_hoy(c)
    assert [x["ticker"] for x in comp] == list(mom.sort_values(ascending=False).index[:10])


def test_filtro_de_mercado_deja_en_liquidez():
    c = cierres_sinteticos()
    perm = pd.DataFrame(False, index=c.index, columns=c.columns)
    assert estrategias.composicion_hoy(c, perm, estrategias.CARTERAS["equilibrada"]) == []
    curva, met = experimentos.simular_rotacion(c, estrategias.senal(c, "momentum"), 5, Tarifa(), 10_000, perm)
    assert met["operaciones"] == 0 and curva.iloc[-1] == pytest.approx(10_000)


def test_rotacion_contabilidad():
    c = cierres_sinteticos()
    curva, met = experimentos.simular_rotacion(c, estrategias.senal(c, "momentum"), 4, Tarifa(), 10_000)
    valor = met["efectivo_final"] + sum(n * c[t].iloc[-1] for t, n in met["cartera_final"].items())
    assert curva.iloc[-1] == pytest.approx(valor)
    assert met["gastos"] > 0 and len(met["cartera_final"]) <= 4


def test_rotacion_no_mira_el_futuro():
    c = cierres_sinteticos()
    c2 = c.copy()
    c2.iloc[600:] *= 3
    s1, s2 = estrategias.senal(c, "momentum"), estrategias.senal(c2, "momentum")
    a, _ = experimentos.simular_rotacion(c, s1, 4, Tarifa(), 10_000)
    b, _ = experimentos.simular_rotacion(c2, s2, 4, Tarifa(), 10_000)
    pd.testing.assert_series_equal(a.iloc[:598], b.iloc[:598])


def test_proteccion_indices():
    precios = pd.Series(np.r_[np.linspace(100, 200, 400), np.linspace(200, 120, 150)],
                        index=pd.bdate_range("2015-01-01", periods=550))
    p = estrategias.proteccion_indices({"^IBEX": pd.DataFrame({"Close": precios})})["^IBEX"]
    assert p["estado"] == "fuera"
    assert p["salir_si_baja_de"] < p["media200"] < p["entrar_si_sube_de"]
    assert [x["estado"] for x in p["ultimos_cambios"]] == ["dentro", "fuera"]


def test_filtro_tendencia_indice_reduce_caidas():
    c = hist(7, n=3000)["Close"]
    r = experimentos.filtro_tendencia_indice(c, 200, 0.02)
    assert 0 < r["tiempo_invertido"] < 1
    assert r["filtro"]["max_caida_pct"] >= r["mantener"]["max_caida_pct"] - 5


def test_limite_por_sector():
    sig = np.array([9.0, 8.0, 7.0, 6.0, 5.0, -np.inf])
    sectores = ["Banca", "Banca", "Banca", "Energía", "Salud", "Salud"]
    assert experimentos.elegir_top(sig, 4, sectores, 2) == [0, 1, 3, 4]
    assert experimentos.elegir_top(sig, 4) == [0, 1, 2, 3]
    assert experimentos.elegir_top(sig, 10) == [0, 1, 2, 3, 4]  # nunca elige señales -inf


def test_composicion_respeta_sector():
    c = cierres_sinteticos()
    c.columns = ["SAN.MC", "BBVA.MC", "CABK.MC", "SAB.MC", "BKT.MC", "UNI.MC", "IBE.MC", "REP.MC", "ITX.MC",
                 "TEF.MC", "GRF.MC", "ACS.MC"]
    perm = pd.DataFrame(True, index=c.index, columns=c.columns)
    comp = estrategias.composicion_hoy(c, perm, estrategias.CARTERAS["es_dinamica"])
    from collections import Counter
    from bolsa.tickers import sector_de
    assert max(Counter(sector_de(x["ticker"]) for x in comp).values()) <= 2
