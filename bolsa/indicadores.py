"""Indicadores técnicos clásicos, calculados sobre un DataFrame con columnas
Open, High, Low, Close, Volume (formato de Yahoo Finance)."""

import numpy as np
import pandas as pd

from .memo import memorizar


def media_movil(serie: pd.Series, dias: int) -> pd.Series:
    return serie.rolling(dias, min_periods=dias).mean()


def rsi(serie: pd.Series, dias: int = 14) -> pd.Series:
    """RSI de Wilder: 0-100. Más de 70 = 'sobrecomprado', menos de 30 = 'sobrevendido'."""
    delta = serie.diff()
    subidas = delta.clip(lower=0)
    bajadas = -delta.clip(upper=0)
    media_sub = subidas.ewm(alpha=1 / dias, min_periods=dias, adjust=False).mean()
    media_baj = bajadas.ewm(alpha=1 / dias, min_periods=dias, adjust=False).mean()
    rs = media_sub / media_baj.replace(0, np.nan)
    resultado = 100 - 100 / (1 + rs)
    # Si no ha habido ninguna bajada, el RSI es 100; si el precio no se ha movido nada, 50 (neutral).
    resultado = resultado.where(media_baj != 0, 100.0).where((media_baj != 0) | (media_sub != 0), 50.0)
    return resultado.where(media_sub.notna())


def macd(serie: pd.Series, rapida: int = 12, lenta: int = 26, senal: int = 9) -> pd.DataFrame:
    ema_r = serie.ewm(span=rapida, adjust=False).mean()
    ema_l = serie.ewm(span=lenta, adjust=False).mean()
    linea = ema_r - ema_l
    linea_senal = linea.ewm(span=senal, adjust=False).mean()
    return pd.DataFrame({"macd": linea, "senal": linea_senal, "histograma": linea - linea_senal})


def atr(df: pd.DataFrame, dias: int = 14) -> pd.Series:
    """Average True Range: cuánto se mueve el precio en un día normal (en euros/dólares)."""
    cierre_prev = df["Close"].shift(1)
    rango = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - cierre_prev).abs(),
        (df["Low"] - cierre_prev).abs(),
    ], axis=1).max(axis=1)
    return rango.ewm(alpha=1 / dias, min_periods=dias, adjust=False).mean()


def volatilidad_anual(serie: pd.Series, dias: int = 60) -> float:
    rent = serie.pct_change().dropna().tail(dias)
    if len(rent) < 10:
        return float("nan")
    return float(rent.std() * np.sqrt(252) * 100)


def variacion(serie: pd.Series, sesiones: int) -> float:
    """Variación en % respecto a hace `sesiones` sesiones."""
    serie = serie.dropna()
    if len(serie) <= sesiones:
        return float("nan")
    return float((serie.iloc[-1] / serie.iloc[-1 - sesiones] - 1) * 100)


@memorizar(48)
def calcular_todo(df: pd.DataFrame) -> pd.DataFrame:
    """Devuelve una copia del histórico con todas las columnas de indicadores añadidas."""
    out = df.copy()
    c = out["Close"]
    out["SMA20"] = media_movil(c, 20)
    out["SMA50"] = media_movil(c, 50)
    out["SMA200"] = media_movil(c, 200)
    out["RSI"] = rsi(c)
    out = out.join(macd(c))
    out["ATR"] = atr(out)
    out["Max52"] = c.rolling(252, min_periods=20).max()
    out["Min52"] = c.rolling(252, min_periods=20).min()
    out["VolMedio20"] = out["Volume"].rolling(20, min_periods=5).mean()
    return out
