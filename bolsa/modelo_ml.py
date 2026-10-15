"""Modelo conjunto: aprende patrones de TODAS las empresas e índices a la vez.

Explicado fácil: en vez de mirar una sola acción, el modelo estudia ~10 años de unas 120 empresas
de España, Europa y EEUU (cientos de miles de "situaciones") y aprende qué combinaciones de
tendencia, impulso, volatilidad, fuerza frente a su índice y ambiente del mercado han precedido
más a menudo a subidas o bajadas en el mes siguiente.

Para no engañarnos:
- **Walk-forward anual**: para predecir 2023 solo se entrena con datos hasta finales de 2022
  (dejando un mes de margen para que no se cuele información). Así año a año.
- **Calibración**: se mide qué pasó de verdad cuando el modelo daba cada probabilidad. Si cuando
  decía "65%" la acción subió el 58% de las veces, la app te muestra 58%.
- Se compara siempre con la referencia de "decir siempre lo más frecuente".

Usa un algoritmo de "árboles de decisión potenciados" (HistGradientBoosting de scikit-learn),
configurado de forma conservadora (árboles pequeños, muchas observaciones por hoja) para
reducir el riesgo de aprender casualidades.
"""

from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd

from .indicadores import calcular_todo
from .tickers import indice_de_referencia

HORIZONTE = 21  # sesiones (≈ 1 mes)

NOMBRES = {
    "r5": "Rentabilidad 1 semana", "r21": "Rentabilidad 1 mes", "r63": "Rentabilidad 3 meses",
    "r126": "Rentabilidad 6 meses", "r252": "Rentabilidad 1 año", "dist50": "Distancia a la media de 50",
    "dist200": "Distancia a la media de 200", "cruce": "Media 50 frente a media 200", "rsi": "RSI",
    "macd": "Impulso (MACD)", "atr": "Movimiento diario típico", "vol21": "Volatilidad del último mes",
    "vol_ratio": "Volatilidad reciente frente a la del año", "desde_max": "Distancia al máximo del año",
    "desde_min": "Distancia al mínimo del año", "volumen": "Volumen negociado reciente",
    "mkt_dist200": "Tendencia del índice", "mkt_r21": "Índice: último mes", "rel63": "Fuerza frente a su índice",
    "vix": "Miedo en el mercado (VIX)", "rank_r63": "Puesto por rentabilidad 3 meses",
    "rank_r5": "Puesto por rentabilidad 1 semana", "rank_vol": "Puesto por volatilidad",
}
COLUMNAS = list(NOMBRES)
COLUMNAS_FUTURAS = {"fwd", "fwd63", "fut_dd21", "fut_dd63", "fut_rel21", "fut_rel63"}
assert not COLUMNAS_FUTURAS & set(COLUMNAS), "Una característica no puede ser un dato del futuro"


# --------------------------------------------------------------------------- características
def caracteristicas_accion(df: pd.DataFrame, indice: pd.DataFrame | None = None,
                           vix: pd.DataFrame | None = None) -> pd.DataFrame:
    """Situación de cada día de una acción, con números comparables entre empresas."""
    d = calcular_todo(df)
    c = d["Close"]
    ret = c.pct_change()
    f = pd.DataFrame(index=d.index)
    for n in (5, 21, 63, 126, 252):
        f[f"r{n}"] = c.pct_change(n)
    f["dist50"] = c / d["SMA50"] - 1
    f["dist200"] = c / d["SMA200"] - 1
    f["cruce"] = d["SMA50"] / d["SMA200"] - 1
    f["rsi"] = d["RSI"] / 100
    f["macd"] = d["histograma"] / c
    f["atr"] = d["ATR"] / c
    f["vol21"] = ret.rolling(21).std() * np.sqrt(252)
    f["vol_ratio"] = f["vol21"] / (ret.rolling(252, min_periods=120).std() * np.sqrt(252))
    f["desde_max"] = c / d["Max52"] - 1
    f["desde_min"] = c / d["Min52"] - 1
    v = d["Volume"].astype(float)
    f["volumen"] = np.log((v.rolling(5).mean() + 1) / (v.rolling(60).mean() + 1))
    if indice is not None and not indice.empty:
        m = indice["Close"].reindex(d.index, method="ffill")
        f["mkt_dist200"] = m / m.rolling(200).mean() - 1
        f["mkt_r21"] = m.pct_change(21)
        f["rel63"] = f["r63"] - m.pct_change(63)
    else:  # sin índice: valores neutros (una columna vacía no se puede usar para entrenar)
        f["mkt_dist200"] = f["mkt_r21"] = f["rel63"] = 0.0
    if vix is not None and not vix.empty:
        vx = vix["Close"].reindex(d.index, method="ffill")
        f["vix"] = vx / vx.rolling(252, min_periods=60).median()
    else:
        f["vix"] = 1.0
    return f.replace([np.inf, -np.inf], np.nan)


def construir_panel(historicos: dict[str, pd.DataFrame], indices: dict[str, pd.DataFrame] | None = None,
                    vix: pd.DataFrame | None = None, horizonte: int = HORIZONTE,
                    progreso: Callable[[float, str], None] | None = None) -> pd.DataFrame:
    """Tabla con una fila por (fecha, acción): características + resultado futuro."""
    indices = indices or {}
    partes = []
    for i, (t, df) in enumerate(historicos.items()):
        if len(df) < 300:
            continue
        if progreso:
            progreso(i / max(len(historicos), 1), t)
        f = caracteristicas_accion(df, indices.get(indice_de_referencia(t)), vix)
        c = df["Close"]
        f["fwd"] = c.shift(-horizonte) / c - 1
        f["fwd63"] = c.shift(-63) / c - 1
        # Peor momento de los próximos 21/63 días (para el modelo de riesgo de caída).
        f["fut_dd21"] = c.shift(-1)[::-1].rolling(21, min_periods=21).min()[::-1] / c - 1
        f["fut_dd63"] = c.shift(-1)[::-1].rolling(63, min_periods=63).min()[::-1] / c - 1
        f["ticker"] = t
        partes.append(f[f["r252"].notna()])
    if not partes:
        return pd.DataFrame()
    panel = pd.concat(partes)
    panel.index.name = "fecha"
    panel = panel.reset_index().set_index(["fecha", "ticker"]).sort_index()
    # Puestos relativos entre todas las empresas ese mismo día (patrón de "momentum" y "reversión").
    g = panel.groupby(level="fecha")
    panel["rank_r63"] = g["r63"].rank(pct=True)
    panel["rank_r5"] = g["r5"].rank(pct=True)
    panel["rank_vol"] = g["vol21"].rank(pct=True)
    # Rentabilidad futura frente a la mediana de todas las empresas ese día (¿lo hizo mejor que las demás?)
    # (prefijo "fut_" = dato del FUTURO: solo se usa como respuesta, nunca como característica)
    panel["fut_rel21"] = panel["fwd"] - g["fwd"].transform("median")
    panel["fut_rel63"] = panel["fwd63"] - g["fwd63"].transform("median")
    panel[COLUMNAS] = panel[COLUMNAS].astype("float32")
    return panel


# Qué se intenta predecir. y: etiqueta (True/False), ret: rentabilidad asociada, h: sesiones.
OBJETIVOS = {
    "sube_1m": {"col": "fwd", "y": lambda p: p["fwd"] > 0, "ret": "fwd", "h": 21,
                "texto": "¿Subirá en el próximo mes?"},
    "sube_3m": {"col": "fwd63", "y": lambda p: p["fwd63"] > 0, "ret": "fwd63", "h": 63,
                "texto": "¿Subirá en los próximos 3 meses?"},
    "supera_1m": {"col": "fut_rel21", "y": lambda p: p["fut_rel21"] > 0, "ret": "fwd", "h": 21,
                  "texto": "¿Lo hará mejor que la mayoría de empresas el próximo mes?"},
    "supera_3m": {"col": "fut_rel63", "y": lambda p: p["fut_rel63"] > 0, "ret": "fwd63", "h": 63,
                  "texto": "¿Lo hará mejor que la mayoría en los próximos 3 meses?"},
    "caida_1m": {"col": "fut_dd21", "y": lambda p: p["fut_dd21"] < -0.10, "ret": "fwd", "h": 21,
                 "texto": "¿Sufrirá una caída de más del 10% en algún momento del próximo mes?"},
    "caida_3m": {"col": "fut_dd63", "y": lambda p: p["fut_dd63"] < -0.15, "ret": "fwd63", "h": 63,
                 "texto": "¿Sufrirá una caída de más del 15% en algún momento de los próximos 3 meses?"},
}


# --------------------------------------------------------------------------- modelo
def nuevo_modelo():
    from sklearn.ensemble import HistGradientBoostingClassifier

    return HistGradientBoostingClassifier(learning_rate=0.05, max_iter=250, max_leaf_nodes=15,
                                          min_samples_leaf=300, l2_regularization=1.0,
                                          early_stopping=False, random_state=0)


def _muestra_entreno(panel: pd.DataFrame, hasta: pd.Timestamp, paso: int, col: str = "fwd") -> pd.DataFrame:
    """Filas con resultado ya conocido antes de `hasta`, una de cada `paso` sesiones
    (las sesiones contiguas son casi iguales y no aportan información nueva)."""
    fechas = panel.index.get_level_values("fecha")
    t = panel[(fechas < hasta) & panel[col].notna()]
    unicas = pd.Index(t.index.get_level_values("fecha").unique()).sort_values()
    elegidas = unicas[::paso]
    return t[t.index.get_level_values("fecha").isin(elegidas)]


def calibracion(p: np.ndarray, fwd: np.ndarray, bins: int = 10, y: np.ndarray | None = None) -> pd.DataFrame:
    """Qué pasó de verdad en cada tramo de probabilidad que dio el modelo. Con `y`, la columna 'sube'
    es la frecuencia real del suceso predicho (p. ej. una caída fuerte)."""
    df = pd.DataFrame({"p": p, "fwd": fwd, "y": (fwd > 0) if y is None else y}).dropna()
    if len(df) < bins * 20:
        bins = max(2, len(df) // 20)
    df["tramo"] = pd.qcut(df["p"], bins, duplicates="drop")
    t = df.groupby("tramo", observed=True).agg(
        p_media=("p", "mean"), p_min=("p", "min"), p_max=("p", "max"),
        sube=("y", "mean"), rent_media=("fwd", "mean"),
        p10=("fwd", lambda x: float(np.percentile(x, 10))), p90=("fwd", lambda x: float(np.percentile(x, 90))),
        casos=("fwd", "size"))
    return t.reset_index(drop=True)


def calibrar(p: float, tabla: pd.DataFrame | list[dict]) -> dict:
    """Traduce la probabilidad bruta del modelo a lo que ocurrió de verdad en ese tramo."""
    t = pd.DataFrame(tabla)
    if t.empty or p is None or np.isnan(p):
        return {}
    fila = t.iloc[int(np.clip(np.searchsorted(t["p_max"].to_numpy(), p), 0, len(t) - 1))]
    return {"prob": float(fila["sube"]), "rent_media": float(fila["rent_media"]),
            "p10": float(fila["p10"]), "p90": float(fila["p90"]), "casos": int(fila["casos"]),
            "tramo": int(fila.name) + 1, "tramos": len(t)}


def walk_forward(panel: pd.DataFrame, anos_minimos: int = 3, paso: int = 5, objetivo: str = "sube_1m",
                 progreso: Callable[[float, str], None] | None = None) -> dict:
    """Entrena con los años anteriores y predice el siguiente, año a año. Devuelve las
    predicciones 'fuera de muestra' (nunca vistas en el entrenamiento) y sus métricas."""
    from sklearn.metrics import roc_auc_score

    obj = OBJETIVOS[objetivo]
    h = obj["h"]
    etiqueta = obj["y"](panel).where(panel[obj["col"]].notna())
    fechas = panel.index.get_level_values("fecha")
    anos = sorted(set(fechas.year))
    anos_test = [a for a in anos if a >= anos[0] + anos_minimos]
    oos = []
    for i, ano in enumerate(anos_test):
        if progreso:
            progreso(i / len(anos_test), f"Entrenando para predecir {ano}")
        inicio = pd.Timestamp(year=ano, month=1, day=1)
        margen = inicio - pd.tseries.offsets.BDay(h + 2)  # que no se cuele el futuro
        entreno = _muestra_entreno(panel, margen, paso, obj["col"])
        prueba = panel[fechas.year == ano]
        y_entreno = etiqueta.loc[entreno.index].astype(bool)
        if len(entreno) < 2000 or prueba.empty or y_entreno.nunique() < 2:
            continue
        modelo = nuevo_modelo().fit(entreno[COLUMNAS], y_entreno)
        oos.append(pd.Series(modelo.predict_proba(prueba[COLUMNAS])[:, 1], index=prueba.index))
    if not oos:
        raise ValueError("No hay suficientes años de datos para validar el modelo.")
    pred = pd.concat(oos).rename("p")
    res = pd.DataFrame({"ret": panel[obj["ret"]], "y": etiqueta}).join(pred, how="inner")
    conocido = res.dropna()
    y = conocido["y"].astype(bool)
    base = float(y.mean())
    metricas = {
        "objetivo": objetivo, "pregunta": obj["texto"],
        "casos": int(len(conocido)), "acciones": int(conocido.index.get_level_values("ticker").nunique()),
        "desde": str(conocido.index.get_level_values("fecha").min().date()),
        "hasta": str(conocido.index.get_level_values("fecha").max().date()),
        "acierto": float(((conocido["p"] > 0.5) == y).mean()),
        "referencia": max(base, 1 - base), "tasa_subidas": base,
        "auc": float(roc_auc_score(y, conocido["p"])) if y.nunique() == 2 else float("nan"),
        "brier": float(((conocido["p"] - y) ** 2).mean()),
    }
    # Ventaja práctica: en fechas separadas por el horizonte, ¿el 20% con mejor nota rindió más que el 20% peor?
    fechas_c = conocido.index.get_level_values("fecha")
    separadas = pd.Index(fechas_c.unique()).sort_values()[::h]
    m = conocido[fechas_c.isin(separadas)]
    q = m.groupby(level="fecha")["p"].rank(pct=True)
    mejores = m[q >= 0.8].groupby(level="fecha")["ret"].mean()
    peores = m[q <= 0.2].groupby(level="fecha")["ret"].mean()
    todos = m.groupby(level="fecha")["ret"].mean()
    metricas.update(mejores_mes=float(mejores.mean()), peores_mes=float(peores.mean()),
                    todos_mes=float(todos.mean()),
                    meses_mejores_ganan=float((mejores > todos).mean()), meses=int(len(mejores)))
    por_ano = conocido.assign(ano=conocido.index.get_level_values("fecha").year).groupby("ano").apply(
        lambda g: pd.Series({"acierto": float(((g["p"] > 0.5) == g["y"].astype(bool)).mean()),
                             "tasa_subidas": float(g["y"].astype(bool).mean()),
                             "auc": float(roc_auc_score(g["y"].astype(bool), g["p"]))
                             if g["y"].astype(bool).nunique() == 2 else float("nan"),
                             "casos": len(g)}), include_groups=False)
    return {"oos": res["p"], "metricas": metricas,
            "calibracion": calibracion(conocido["p"].to_numpy(), conocido["ret"].to_numpy(),
                                       y=conocido["y"].astype(bool).to_numpy()),
            "por_ano": por_ano}


def entrenar_final(panel: pd.DataFrame, paso: int = 5, objetivo: str = "sube_1m"):
    """Modelo con TODOS los datos conocidos, para las predicciones de hoy."""
    obj = OBJETIVOS[objetivo]
    ultimo = panel.index.get_level_values("fecha").max() + pd.Timedelta(days=1)
    entreno = _muestra_entreno(panel, ultimo, paso, obj["col"])
    return nuevo_modelo().fit(entreno[COLUMNAS], obj["y"](entreno))


def predecir_hoy(modelo, panel: pd.DataFrame, max_dias: int = 7) -> pd.Series:
    """Probabilidad bruta de subida a 1 mes para la última fecha de cada acción."""
    ult = panel.groupby(level="ticker").tail(1)
    fechas = ult.index.get_level_values("fecha")
    ult = ult[fechas >= fechas.max() - pd.Timedelta(days=max_dias)]
    p = modelo.predict_proba(ult[COLUMNAS])[:, 1]
    return pd.Series(p, index=ult.index.get_level_values("ticker"))


def importancia(modelo, panel: pd.DataFrame, n: int = 6000, semilla: int = 0, objetivo: str = "sube_1m") -> pd.Series:
    """Qué datos pesan más en las predicciones (permutando cada columna y viendo cuánto empeora)."""
    from sklearn.inspection import permutation_importance

    obj = OBJETIVOS[objetivo]
    m = panel.dropna(subset=[obj["col"]])
    m = m.sample(min(n, len(m)), random_state=semilla)
    r = permutation_importance(modelo, m[COLUMNAS], obj["y"](m), n_repeats=3, random_state=semilla,
                               scoring="roc_auc")
    return pd.Series(r.importances_mean, index=[NOMBRES[c] for c in COLUMNAS]).sort_values(ascending=False)


def probabilidades_por_accion(oos: pd.Series) -> dict[str, pd.Series]:
    """Convierte las predicciones fuera de muestra en una serie por acción (para el simulador)."""
    return {t: s.droplevel("ticker") for t, s in oos.groupby(level="ticker")}
