from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from bolsa import costes, noticias, senales
from bolsa.indicadores import calcular_todo, rsi


def serie(tendencia: float, n: int = 400, semilla: int = 1, ruido: float = 0.01) -> pd.DataFrame:
    rng = np.random.default_rng(semilla)
    rent = tendencia + rng.normal(0, ruido, n)
    close = 100 * np.cumprod(1 + rent)
    idx = pd.bdate_range("2024-01-01", periods=n)
    return pd.DataFrame({"Open": close * 0.998, "High": close * 1.01, "Low": close * 0.99,
                         "Close": close, "Volume": 1_000_000}, index=idx)


def test_rsi_limites():
    sube = pd.Series(np.arange(1, 60, dtype=float))
    assert rsi(sube).iloc[-1] == pytest.approx(100)
    baja = pd.Series(np.arange(60, 1, -1, dtype=float))
    assert rsi(baja).iloc[-1] < 1


def test_indicadores_columnas():
    d = calcular_todo(serie(0.001))
    for col in ("SMA50", "SMA200", "RSI", "macd", "ATR", "Max52"):
        assert col in d and d[col].notna().iloc[-1]


def test_alcista_puntua_mas_que_bajista():
    alc = senales.evaluar("X", serie(0.0015), mercado_alcista=True)
    baj = senales.evaluar("X", serie(-0.0015), mercado_alcista=False)
    assert alc.puntuacion > baj.puntuacion
    assert baj.veredicto in ("Evitar por ahora", "Esperar")
    assert any("alcista" in m.titulo for m in alc.motivos)
    assert 0 <= baj.puntuacion <= 100


def test_plan_coherente():
    ev = senales.evaluar("X", serie(0.001))
    p = ev.plan
    assert p.stop < p.entrada < p.objetivo
    assert p.beneficio_pct == pytest.approx(2 * p.riesgo_pct, rel=1e-6)
    assert p.riesgo_pct <= 20.0001


def test_historial_corto_no_falla():
    ev = senales.evaluar("X", serie(0.001, n=60))
    assert ev.avisos and 0 <= ev.puntuacion <= 100


def test_backtest():
    bt = senales.backtest_media200(serie(0.0005, n=800))
    assert {"rent_estrategia", "rent_mantener", "operaciones"} <= bt.keys()
    assert bt["caida_mantener"] <= 0


def test_estado_indice():
    assert senales.estado_indice(serie(0.002))["alcista"] is True
    assert senales.estado_indice(serie(-0.002))["alcista"] is False


def _n(titulo, horas=1):
    return noticias.analizar(noticias.Noticia(titulo, "http://x", "test",
                                              datetime.now(timezone.utc) - timedelta(hours=horas)))


def test_noticia_macro_negativa():
    n = _n("El Ibex se desploma tras la subida de tipos del BCE y los temores de recesión")
    assert n.sentimiento == -1
    assert n.impacto >= 7
    assert n.explicaciones


def test_noticia_empresa_positiva():
    n = _n("Inditex dispara su beneficio y supera previsiones; sube en bolsa")
    assert "ITX.MC" in n.empresas
    assert n.sentimiento == 1


def test_deteccion_empresas():
    assert noticias.detectar_empresas("Acciona Energía cae un 3%") == ["ANE.MC"]
    assert set(noticias.detectar_empresas("BBVA y Sabadell")) == {"BBVA.MC", "SAB.MC"}
    assert noticias.detectar_empresas("Metales preciosos") == []  # 'meta' no debe coincidir


def test_noticia_antigua_pesa_menos():
    assert _n("La Fed baja los tipos", horas=1).impacto > _n("La Fed baja los tipos", horas=100).impacto


def test_costes():
    t = costes.Tarifa(pct=0.2, minimo=6, canon_fijo=1)
    assert t.coste(1000) == pytest.approx(7)
    assert t.coste(10000) == pytest.approx(21)
    c = costes.coste_compra(1000, "SAN.MC", t)
    assert c["itf"] == pytest.approx(2)
    assert costes.coste_compra(1000, "AAPL", t)["itf"] == 0


def test_tamano_por_riesgo():
    # Riesgo 1% de 10.000 = 100 €; pierde 2 € por acción -> 50 acciones (500 € < capital).
    assert costes.tamano_por_riesgo(10_000, 1, 10, 8) == 50
    # Limitado por capital.
    assert costes.tamano_por_riesgo(1_000, 5, 100, 99) == 10
    assert costes.tamano_por_riesgo(1_000, 1, 10, 11) == 0


def test_impuestos():
    assert costes.impuesto_ganancia(-50) == 0
    assert costes.impuesto_ganancia(6000) == pytest.approx(1140)
    assert costes.impuesto_ganancia(10000) == pytest.approx(1140 + 4000 * 0.21)


def test_aportaciones():
    filas = costes.simular_aportaciones(100, 2, 0)
    assert filas[-1]["Valor"] == pytest.approx(2400)
    assert costes.simular_aportaciones(100, 10, 7)[-1]["Ganancia"] > 0


# ----------------------------------------------------------------- predicción
from bolsa import prediccion  # noqa: E402


def test_prediccion_estructura():
    p = prediccion.predecir(serie(0.0005, n=900), 21, "1 mes", n_pruebas=60)
    assert p is not None
    assert 0 <= p.prob_subida <= 1
    assert p.rent_p10 <= p.rent_mediana <= p.rent_p90
    assert p.pruebas > 30 and p.acierto is not None
    assert p.fiabilidad in ("Alta", "Media", "Baja", "Sin datos")
    assert "situaciones" in prediccion.explicar(p)


def test_prediccion_azar_no_es_fiable():
    # Paseo aleatorio puro: el modelo NO debe presumir de fiabilidad alta.
    fiabilidades = [prediccion.predecir(serie(0.0, n=1200, semilla=s), 21, n_pruebas=80).fiabilidad
                    for s in range(4)]
    assert fiabilidades.count("Alta") <= 1


def test_prediccion_detecta_patron():
    # Serie con ciclos regulares: lo pasado sí informa del futuro, el modelo debe batir al azar.
    n = 1500
    t = np.arange(n)
    rng = np.random.default_rng(3)
    close = 100 * np.exp(0.15 * np.sin(2 * np.pi * t / 120) + np.cumsum(rng.normal(0, 0.004, n)))
    df = pd.DataFrame({"Open": close, "High": close * 1.005, "Low": close * 0.995, "Close": close,
                       "Volume": 1}, index=pd.bdate_range("2019-01-01", periods=n))
    p = prediccion.predecir(df, 21, n_pruebas=100)
    assert p.acierto > p.acierto_referencia + 0.1


def test_prediccion_sin_historial():
    assert prediccion.predecir(serie(0.001, n=150), 21) is None


def test_evaluar_con_prediccion_y_fundamentales():
    df = serie(0.001, n=900)
    p = prediccion.predecir(df, 21, "1 mes", n_pruebas=50)
    fund = {"targetMeanPrice": float(df["Close"].iloc[-1]) * 1.3, "numberOfAnalystOpinions": 10,
            "recommendationKey": "buy", "forwardPE": 9.0}
    ev = senales.evaluar("X", df, fundamentales=fund, prediccion=p)
    titulos = " ".join(m.titulo for m in ev.motivos)
    assert "analistas" in titulos and "PER" in titulos and "Modelo estadístico" in titulos


# ----------------------------------------------------------------- noticias (más fuentes)
def test_noticia_en_ingles():
    n = _n("Stocks tumble as Fed signals rate hike; Nvidia shares slide")
    assert n.sentimiento == -1
    assert "NVDA" in n.empresas
    assert n.impacto >= 6


def test_combinar_repetidas():
    ahora = datetime.now(timezone.utc)
    brutas = [noticias.Noticia("El BCE baja los tipos de interés - Expansión", "a", "A", ahora),
              noticias.Noticia("El BCE baja los tipos de interés - El País", "b", "B", ahora),
              noticias.Noticia("El BCE baja los tipos de interés", "c", "C", ahora - timedelta(hours=1)),
              noticias.Noticia("Noticia vieja", "d", "D", ahora - timedelta(days=10))]
    lista = noticias.combinar(brutas)
    assert len(lista) == 1
    assert lista[0].repeticiones == 3
    assert lista[0].fecha == ahora - timedelta(hours=1)
