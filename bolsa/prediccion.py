"""Predicción estadística por "situaciones parecidas del pasado" (k vecinos más cercanos).

Idea, explicada fácil: describimos la situación de hoy de la acción con unos pocos números
(tendencia, RSI, impulso, volatilidad...). Buscamos en sus últimos años los días en los que
estaba en una situación muy parecida y miramos qué pasó después. Si en el 65% de esos días
la acción subió en el mes siguiente, la probabilidad estimada es 65%.

Lo más importante: el modelo se **examina a sí mismo**. Repite el proceso en cientos de
fechas pasadas usando solo la información que había en cada momento (validación
"walk-forward") y cuenta cuántas veces acertó. Así sabes cuánto fiarte de él para
cada acción. Si no acierta más que lanzar una moneda, te lo dice.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .indicadores import calcular_todo

HORIZONTES = {"1 semana": 5, "1 mes": 21, "3 meses": 63}


def caracteristicas(df: pd.DataFrame) -> pd.DataFrame:
    """Describe la situación de cada día con números comparables entre fechas."""
    d = calcular_todo(df)
    c = d["Close"]
    f = pd.DataFrame(index=d.index)
    f["dist200"] = c / d["SMA200"] - 1
    f["dist50"] = c / d["SMA50"] - 1
    f["rsi"] = d["RSI"] / 100
    f["mom5"] = c.pct_change(5)
    f["mom20"] = c.pct_change(20)
    f["mom60"] = c.pct_change(60)
    f["vol20"] = c.pct_change().rolling(20).std() * np.sqrt(252)
    f["macd"] = d["histograma"] / c
    f["desde_max"] = c / d["Max52"] - 1
    return f.replace([np.inf, -np.inf], np.nan)


def rentabilidad_futura(df: pd.DataFrame, sesiones: int) -> pd.Series:
    c = df["Close"]
    return c.shift(-sesiones) / c - 1


@dataclass
class Prediccion:
    horizonte: str
    sesiones: int
    precio: float
    prob_subida: float           # 0-1
    rent_p10: float              # rentabilidades en tanto por uno
    rent_mediana: float
    rent_p90: float
    casos: int                   # situaciones parecidas encontradas
    acierto: float | None        # % de aciertos en el examen histórico (0-1)
    acierto_referencia: float | None  # aciertos de la estrategia tonta "repetir siempre lo más frecuente"
    acierto_seguro: float | None # acierto cuando el modelo estaba muy seguro (prob >65% o <35%)
    n_seguro: int
    pruebas: int

    @property
    def precio_p10(self) -> float:
        return self.precio * (1 + self.rent_p10)

    @property
    def precio_mediana(self) -> float:
        return self.precio * (1 + self.rent_mediana)

    @property
    def precio_p90(self) -> float:
        return self.precio * (1 + self.rent_p90)

    @property
    def ventaja(self) -> float | None:
        """Puntos (0-1) que el modelo acierta por encima de la referencia."""
        if self.acierto is None or self.acierto_referencia is None:
            return None
        return self.acierto - self.acierto_referencia

    @property
    def fiabilidad(self) -> str:
        v = self.ventaja
        if v is None or self.pruebas < 40:
            return "Sin datos"
        if v >= 0.08:
            return "Alta"
        if v >= 0.03:
            return "Media"
        return "Baja"

    @property
    def direccion(self) -> str:
        if self.prob_subida >= 0.60:
            return "Probable subida"
        if self.prob_subida <= 0.40:
            return "Probable bajada"
        return "Incierto"


def _vecinos(Z: np.ndarray, r: np.ndarray, z: np.ndarray, k: int, base: float) -> tuple[float, np.ndarray]:
    """Probabilidad de subida y rentabilidades de los k casos más parecidos.
    La probabilidad se 'encoge' hacia la tasa base para no exagerar la confianza."""
    d = np.sqrt(((Z - z) ** 2).sum(axis=1))
    k = min(k, len(d))
    idx = np.argpartition(d, k - 1)[:k]
    w = 1 / (d[idx] + 0.5)
    p = float((w * (r[idx] > 0)).sum() / w.sum())
    m = 20  # fuerza del encogimiento
    p = (k * p + m * base) / (k + m)
    return p, r[idx]


def _k(n: int) -> int:
    return int(max(25, min(120, n // 12)))


def _preparar(X: pd.DataFrame, r: pd.Series):
    valido = X.notna().all(axis=1)
    return X[valido], r[valido]


def predecir(df: pd.DataFrame, sesiones: int, horizonte: str = "", n_pruebas: int = 150,
             min_entreno: int = 250) -> Prediccion | None:
    """Predice la rentabilidad a `sesiones` vista y examina el modelo con el pasado."""
    X, r = _preparar(caracteristicas(df), rentabilidad_futura(df, sesiones))
    if X.empty or pd.isna(X.iloc[-1]).any():
        return None
    Xv, rv = X.to_numpy(), r.to_numpy()
    conocidos = ~np.isnan(rv)
    if conocidos.sum() < min_entreno:
        return None

    def ajustar(hasta: int):
        """Entrena con las filas < hasta cuyo resultado ya se conocía en la fila `hasta`."""
        limite = hasta - sesiones
        mask = conocidos.copy()
        mask[max(limite, 0):] = False
        Xt, rt = Xv[mask], rv[mask]
        mu, sd = Xt.mean(axis=0), Xt.std(axis=0) + 1e-9
        return (Xt - mu) / sd, rt, mu, sd

    # --- Examen walk-forward: fechas pasadas, sin mirar el futuro.
    pos = np.arange(len(Xv))
    candidatas = pos[conocidos & (pos >= min_entreno + sesiones)]
    paso = max(1, len(candidatas) // n_pruebas)
    pruebas = candidatas[::-1][::paso][:n_pruebas]
    aciertos, seguros_ok, seguros, reales = 0, 0, 0, []
    for t in pruebas:
        Z, rt, mu, sd = ajustar(t)
        if len(rt) < min_entreno:
            continue
        base = float((rt > 0).mean())
        p, _ = _vecinos(Z, rt, (Xv[t] - mu) / sd, _k(len(rt)), base)
        subio = rv[t] > 0
        reales.append(subio)
        aciertos += (p > 0.5) == subio
        if p >= 0.65 or p <= 0.35:
            seguros += 1
            seguros_ok += (p > 0.5) == subio
    n = len(reales)
    acierto = aciertos / n if n else None
    frac = float(np.mean(reales)) if n else None
    referencia = max(frac, 1 - frac) if n else None

    # --- Predicción de hoy, con todo lo conocido.
    Z, rt, mu, sd = ajustar(len(Xv))
    base = float((rt > 0).mean())
    k = _k(len(rt))
    p, rs = _vecinos(Z, rt, (Xv[-1] - mu) / sd, k, base)
    return Prediccion(
        horizonte=horizonte or f"{sesiones} sesiones", sesiones=sesiones, precio=float(df["Close"].iloc[-1]),
        prob_subida=p, rent_p10=float(np.percentile(rs, 10)), rent_mediana=float(np.median(rs)),
        rent_p90=float(np.percentile(rs, 90)), casos=k, acierto=acierto, acierto_referencia=referencia,
        acierto_seguro=seguros_ok / seguros if seguros else None, n_seguro=seguros, pruebas=n,
    )


def predecir_todos(df: pd.DataFrame, n_pruebas: int = 150) -> dict[str, Prediccion]:
    salida = {}
    for nombre, s in HORIZONTES.items():
        p = predecir(df, s, nombre, n_pruebas=n_pruebas)
        if p:
            salida[nombre] = p
    return salida


def explicar(p: Prediccion) -> str:
    """Frase en lenguaje llano."""
    texto = (f"En las {p.casos} situaciones más parecidas a la actual de los últimos años, la acción "
             f"subió a {p.horizonte.lower()} vista en un {p.prob_subida * 100:.0f}% de los casos. "
             f"Lo más habitual fue un movimiento de {p.rent_mediana * 100:+.1f}%, y en 8 de cada 10 casos "
             f"quedó entre {p.rent_p10 * 100:+.1f}% y {p.rent_p90 * 100:+.1f}%.")
    if p.acierto is not None:
        texto += (f" Examinado en {p.pruebas} fechas pasadas, este modelo acertó la dirección el "
                  f"{p.acierto * 100:.0f}% de las veces (decir siempre lo mismo habría acertado el "
                  f"{p.acierto_referencia * 100:.0f}%).")
        if p.fiabilidad == "Baja":
            texto += " **Para esta acción el modelo no es mejor que el azar: no le hagas caso.**"
    return texto
