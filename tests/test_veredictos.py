import numpy as np
import pandas as pd

from bolsa import informe


def _serie(inicio, valores):
    idx = pd.bdate_range(inicio, periods=len(valores))
    return pd.DataFrame({"Close": valores}, index=idx)


def test_archiva_y_evalua_veredictos_un_mes_despues(tmp_path):
    ruta = tmp_path / "v.csv"
    fila_ok = {"ticker": "AAA.MC", "precio": 10.0, "indice": "^IBEX", "nota": 90, "puntuacion": 85, "color": "green",
               "momentum": 0.3, "mercado_alcista": True, "resultados_pronto": False, "riesgo_nivel": "bajo"}
    fila_mal = {"ticker": "BBB.MC", "precio": 10.0, "indice": "^IBEX", "nota": 10, "puntuacion": 20, "color": "red",
                "momentum": -0.3, "mercado_alcista": True, "resultados_pronto": False, "riesgo_nivel": "alto"}
    indices = {"^IBEX": _serie("2026-01-01", np.full(40, 100.0))}
    h = informe.archivar_veredictos(ruta, "2026-01-01", [fila_ok, fila_mal, {"ticker": "ETF", "etf": True}], indices)
    assert len(h) == 2 and set(h["color"]) >= {"green"}
    # Volver a archivar el mismo día no duplica
    assert len(informe.archivar_veredictos(ruta, "2026-01-01", [fila_ok, fila_mal], indices)) == 2
    acciones = {"AAA.MC": _serie("2026-01-01", np.linspace(10, 11, 40)),
                "BBB.MC": _serie("2026-01-01", np.linspace(10, 9, 40))}
    ev = informe.evaluar_veredictos(h, acciones, indices)
    assert ev["evaluados"] == 2 and ev["dias"] == 1
    g = {x["veredicto"]: x for x in ev["grupos"]}
    mejor, peor = ev["grupos"][0], ev["grupos"][-1]
    assert mejor["rent_media"] > 0 > peor["rent_media"] and mejor["exceso_medio"] > 0
    assert len(g) == 2


def test_sin_un_mes_quedan_pendientes(tmp_path):
    indices = {"^IBEX": _serie("2026-01-01", np.full(5, 100.0))}
    h = informe.archivar_veredictos(tmp_path / "v.csv", "2026-01-01",
                                    [{"ticker": "AAA.MC", "precio": 10.0, "indice": "^IBEX", "puntuacion": 60}],
                                    indices)
    ev = informe.evaluar_veredictos(h, {"AAA.MC": _serie("2026-01-01", np.full(5, 10.0))}, indices)
    assert ev["evaluados"] == 0 and ev["pendientes"] == 1 and ev["desde"] == "2026-01-01"
