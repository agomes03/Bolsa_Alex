import pandas as pd

from bolsa import semanal


def _df(valores):
    return pd.DataFrame({"Close": valores}, index=pd.bdate_range("2026-10-01", periods=len(valores)))


def test_resumen_de_la_semana_en_palabras():
    hist = {"IDR.MC": _df([60, 60, 60, 60, 60, 60, 66]), "ITX.MC": _df([50, 50, 50, 50, 50, 50, 45])}
    pos = [{"ticker": "IDR.MC", "nombre": "Indra", "acciones": 100}, {"ticker": "ITX.MC", "nombre": "Inditex",
                                                                         "acciones": 100}]
    r = semanal.resumen(pos, hist, {"IBEX 35": _df([100] * 6 + [101])},
                        [{"titulo": "Indra gana un contrato", "empresas": ["IDR.MC"]}, {"titulo": "Otra", "empresas": []}])
    assert r["cambio"] == 100 and abs(r["referencias"]["IBEX 35"] - 0.01) < 1e-9
    t = semanal.texto(r)
    assert t[0].startswith("Esta semana tu dinero ha cambiado +100 €")
    assert any("más ha sumado: Indra (+600 €, +10,0 %)" in x for x in t)
    assert any("más ha restado: Inditex (−500 €, −10,0 %)" in x for x in t)
    assert any("Indra gana un contrato" in x for x in t) and not any("Otra" in x for x in t)


def test_sin_historia_suficiente():
    assert semanal.resumen([{"ticker": "X", "nombre": "X", "acciones": 1}], {"X": _df([1, 2])}) == {}
    assert semanal.texto({}) == []
