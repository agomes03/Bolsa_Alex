import json
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from bolsa import asesor, avisos, informe, modelo_ml, noticias, patrones
from test_bolsa import serie


def hist(semilla: int, n: int = 1800, patron: bool = True) -> pd.DataFrame:
    rng = np.random.default_rng(semilla)
    r = rng.normal(0.0003, 0.015, n)
    if patron:
        r = r + 0.0015 * np.sign(np.sin(np.arange(n) / 90 + semilla))
    c = 100 * np.cumprod(1 + r)
    o = np.r_[c[0], c[:-1]]
    return pd.DataFrame({"Open": o, "High": np.maximum(o, c) * 1.004, "Low": np.minimum(o, c) * 0.996,
                         "Close": c, "Volume": rng.integers(1e5, 1e6, n)},
                        index=pd.bdate_range("2018-01-01", periods=n))


# ----------------------------------------------------------------- modelo conjunto
@pytest.fixture(scope="module")
def panel_con_patron():
    return modelo_ml.construir_panel({f"T{i}.MC": hist(i) for i in range(25)}, {"^IBEX": hist(99, patron=False)})


def test_panel_sin_futuro_en_caracteristicas(panel_con_patron):
    assert set(modelo_ml.COLUMNAS) <= set(panel_con_patron.columns)
    # Las características de un día no deben cambiar si se alteran precios posteriores.
    h = hist(3)
    f1 = modelo_ml.caracteristicas_accion(h)
    h2 = h.copy()
    h2.iloc[1500:, :4] *= 0.5
    f2 = modelo_ml.caracteristicas_accion(h2)
    pd.testing.assert_frame_equal(f1.iloc[:1500], f2.iloc[:1500])


def test_walk_forward_detecta_patron(panel_con_patron):
    wf = modelo_ml.walk_forward(panel_con_patron)
    m = wf["metricas"]
    assert m["auc"] > 0.55
    assert m["mejores_mes"] > m["peores_mes"]
    cal = wf["calibracion"]
    assert cal["sube"].iloc[-1] > cal["sube"].iloc[0]  # más probabilidad -> más subidas reales
    # Las predicciones solo existen para años posteriores a los de entrenamiento mínimo.
    primer_ano = wf["oos"].index.get_level_values("fecha").min().year
    assert primer_ano >= 2018 + 3


def test_walk_forward_no_inventa_en_azar():
    panel = modelo_ml.construir_panel({f"T{i}.MC": hist(i, patron=False) for i in range(20)})
    wf = modelo_ml.walk_forward(panel)
    assert wf["metricas"]["auc"] < 0.54


def test_calibrar_y_prediccion_hoy(panel_con_patron):
    wf = modelo_ml.walk_forward(panel_con_patron)
    final = modelo_ml.entrenar_final(panel_con_patron)
    hoy = modelo_ml.predecir_hoy(final, panel_con_patron)
    assert len(hoy) == 25 and hoy.between(0, 1).all()
    c = modelo_ml.calibrar(float(hoy.iloc[0]), wf["calibracion"])
    assert 0 <= c["prob"] <= 1 and c["p10"] <= c["rent_media"] <= c["p90"]
    assert modelo_ml.calibrar(float("nan"), wf["calibracion"]) == {}


# ----------------------------------------------------------------- patrones y escenarios
def test_fases_y_estadisticas():
    c = hist(5, n=3000)["Close"]
    f = patrones.fase_mercado(c)
    assert set(f.dropna().unique()) <= set(patrones.FASES)
    e = patrones.estadisticas_fase(c)
    assert e["fase"] in patrones.FASES
    h = e["horizontes"]["1 mes"]
    assert h["casos"] > 10 and 0 <= h["prob_sube"] <= 1 and h["p10"] <= h["mediana"] <= h["p90"]


def test_peores_caidas():
    c = pd.Series([100, 110, 120, 60, 80, 125, 130, 100, 131.0], index=pd.bdate_range("2020-01-01", periods=9))
    caidas = patrones.peores_caidas(c, minimo=-0.1)
    assert caidas[0]["caida"] == pytest.approx(-0.5)
    assert caidas[0]["recuperado"] is not None
    assert caidas[1]["caida"] == pytest.approx(100 / 130 - 1)


def test_escenarios_y_estres():
    hs = {"A": hist(1, n=1500), "B": hist(2, n=1500)}
    r = patrones.rentabilidades_cartera(hs, {"A": 50, "B": 50})
    assert len(r) > 1000
    e = patrones.escenarios(r, n=500)
    assert e["p5"] < e["p50"] < e["p95"] and 0 <= e["prob_perdida"] <= 1
    estres = patrones.prueba_estres(hs, {"A": 50, "B": 50}, {"Prueba": ("2019-03-01", "2019-06-03")})
    a, b = (hs[t]["Close"] for t in "AB")
    esperado = 0.5 * (a[:"2019-06-03"].iloc[-1] / a[:"2019-03-01"].iloc[-1] - 1) + \
        0.5 * (b[:"2019-06-03"].iloc[-1] / b[:"2019-03-01"].iloc[-1] - 1)
    assert estres[0]["cambio"] == pytest.approx(esperado)


# ----------------------------------------------------------------- asesor
def test_perfiles():
    p = asesor.perfil_inversor(15, "Aprovecharía para comprar más", "He invertido antes", True)
    assert p.nombre == "Dinámico" and p.invertir_en_bolsa and not p.alertas
    p = asesor.perfil_inversor(1, "Vendería todo para no perder más", "Ninguna", False)
    assert p.nombre == "Conservador" and not p.invertir_en_bolsa and len(p.alertas) == 2
    p = asesor.perfil_inversor(20, "Vendería todo para no perder más", "He invertido antes", True)
    assert p.nombre != "Dinámico"


def test_ideas_diversificadas():
    ranking = [{"ticker": f"T{i}", "sector": "Banca" if i < 3 else f"S{i}", "puntuacion": 90 - i,
                "prob_modelo": 0.55, "etf": False} for i in range(8)]
    ranking.append({"ticker": "ETF", "sector": "ETF", "puntuacion": 99, "etf": True})
    ranking.append({"ticker": "R", "sector": "X", "puntuacion": 95, "resultados_pronto": True})
    ideas = asesor.ideas_diversificadas(ranking, max_ideas=4)
    assert [i["ticker"] for i in ideas] == ["T0", "T3", "T4", "T5"]


def test_plan_inversion_euros():
    perfil = asesor.perfil_inversor(10, "Me preocuparía, pero esperaría", "Básica (sé lo que es una acción y un fondo)", True)
    ideas = [{"ticker": "SAN.MC", "nombre": "Santander", "sector": "Banca"}]
    plan = asesor.plan_inversion(10_000, 200, perfil, ideas)
    assert sum(l["euros"] for l in plan["lineas"]) == pytest.approx(10_000)
    assert sum(a["euros"] for a in plan["acciones"]) == pytest.approx(10_000 * plan["reparto"]["Acciones individuales"] / 100)
    pequeño = asesor.plan_inversion(1_000, 50, perfil, ideas)
    assert pequeño["reparto"]["Acciones individuales"] == 0 and pequeño["avisos"]
    assert sum(asesor.pesos_para_escenarios(plan).values()) == pytest.approx(100)


# ----------------------------------------------------------------- informe y avisos
def test_limpiar_json():
    datos = {"a": np.float64(1.234567891), "b": float("nan"), "c": [np.int64(3), pd.Timestamp("2026-01-02")],
             "d": np.bool_(True)}
    salida = informe.limpiar(datos)
    json.dumps(salida)
    assert salida == {"a": 1.23457, "b": None, "c": [3, "2026-01-02"], "d": True}


def test_historial_de_ideas(tmp_path):
    acciones = {"A.MC": serie(0.002, n=300)}
    indices = {"^IBEX": serie(0.0005, n=300, semilla=9)}
    fecha = acciones["A.MC"].index[200]
    ruta = tmp_path / "ideas.csv"
    pd.DataFrame([{"fecha": fecha.date().isoformat(), "ticker": "A.MC",
                   "precio": acciones["A.MC"]["Close"].iloc[200], "puntuacion": 80, "prob_modelo": 0.6,
                   "indice": "^IBEX", "precio_indice": indices["^IBEX"]["Close"].iloc[200]}]).to_csv(ruta, index=False)
    total = informe.archivar_ideas(ruta, "2099-01-01", [], indices)
    assert len(total) == 1
    ev = informe.evaluar_ideas(total, acciones, indices)
    esperado = acciones["A.MC"]["Close"].iloc[221] / acciones["A.MC"]["Close"].iloc[200] - 1
    assert ev["evaluadas"] == 1 and ev["rent_media"] == pytest.approx(esperado)


def test_archivo_noticias(tmp_path):
    ahora = datetime.now(timezone.utc)
    lista = noticias.combinar([noticias.Noticia("Santander sube con fuerza tras resultados", "x", "F", ahora),
                               noticias.Noticia("El Ibex cae por los aranceles", "y", "F", ahora - timedelta(hours=1))])
    t = informe.archivar_noticias(tmp_path / "n.csv", "2026-10-15", lista)
    assert "MERCADO" in set(t["ambito"]) and "SAN.MC" in set(t["ambito"])
    t = informe.archivar_noticias(tmp_path / "n.csv", "2026-10-15", lista)  # mismo día: no duplica
    assert (t["ambito"] == "MERCADO").sum() == 1


def test_avisos_cartera_y_mensaje():
    ranking = [{"ticker": "SAN.MC", "nombre": "Santander", "precio": 9.0, "puntuacion": 30, "stop": 8.5,
                "prob_modelo": 0.55}]
    cartera = {"posiciones": {"SAN.MC": {"acciones": 10, "precio_medio": 8.0, "stop": 7.5}}}
    a = avisos.avisos_cartera(cartera, ranking, umbral_venta=40)
    assert len(a) == 1 and "Santander" in a[0]
    texto = avisos.mensaje_diario({"fecha": "2026-10-15", "resumen": ["Hola"], "ideas": ["SAN.MC"],
                                   "ranking": ranking}, a)
    assert "Santander" in texto and "Tu cartera" in texto


@pytest.mark.parametrize("objetivo", list(modelo_ml.OBJETIVOS))
def test_ningun_objetivo_ve_el_futuro(objetivo):
    """Con datos aleatorios, ningún tipo de predicción puede acertar más que el azar (si lo hace, hay fuga)."""
    # Las caídas fuertes son raras: hacen falta más acciones para que el azar no parezca señal.
    n = 30 if objetivo.startswith("caida") else 12
    panel = modelo_ml.construir_panel({f"T{i}.MC": hist(i, patron=False) for i in range(n)})
    wf = modelo_ml.walk_forward(panel, objetivo=objetivo)
    assert wf["metricas"]["auc"] < 0.56, wf["metricas"]["auc"]
