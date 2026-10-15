import numpy as np
import pandas as pd
import pytest

from bolsa import comparativa


def _hist(ret_diario, n=800, ruido=0.0, semilla=0):
    rng = np.random.default_rng(semilla)
    r = ret_diario + rng.normal(0, ruido, n)
    c = 100 * np.cumprod(1 + r)
    return pd.DataFrame({"Close": c}, index=pd.bdate_range("2023-01-02", periods=n))


def test_compara_con_el_fondo_y_el_ibex():
    hist = {"AAA.MC": _hist(0.001, ruido=0.03, semilla=1), "IWDA.AS": _hist(0.0004, ruido=0.008, semilla=2),
            "^IBEX": _hist(0.0003, ruido=0.01, semilla=3)}
    res = comparativa.comparar(hist, {"AAA.MC": 1.0}, 1)
    assert set(res) == {"Tu cartera (con tu reparto de hoy)", *comparativa.REFERENCIAS.values()}
    tuya = res["Tu cartera (con tu reparto de hoy)"]
    fondo = res[comparativa.REFERENCIAS["IWDA.AS"]]
    assert tuya["volatilidad"] > fondo["volatilidad"] and tuya["peor_caida"] <= 0
    assert 250 <= len(tuya["curva"]) <= 262          # un año natural de sesiones
    assert comparativa.conclusion(res)


def test_metricas_basicas():
    r = pd.Series([0.01] * 252, index=pd.bdate_range("2024-01-01", periods=252))
    m = comparativa.metricas(r)
    assert m["total"] == pytest.approx(1.01 ** 252 - 1) and m["peor_caida"] == 0
    assert comparativa.metricas(r.iloc[:10]) == {}
