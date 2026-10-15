"""Descarga de cotizaciones desde Yahoo Finance (gratis, con ~15 min de retraso en Bolsa de Madrid)."""

from __future__ import annotations

import pandas as pd


def _sin_zona(df: pd.DataFrame) -> pd.DataFrame:
    idx = pd.to_datetime(df.index)
    df.index = idx.tz_localize(None) if idx.tz is not None else idx
    return df


def historico(ticker: str, periodo: str = "2y") -> pd.DataFrame:
    """Histórico diario. Devuelve un DataFrame vacío si no hay datos."""
    import yfinance as yf

    try:
        df = yf.Ticker(ticker).history(period=periodo, interval="1d", auto_adjust=True)
    except Exception:  # noqa: BLE001 - errores de red: la app mostrará un aviso
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
    return _sin_zona(df)


def varios(tickers: list[str], periodo: str = "2y") -> dict[str, pd.DataFrame]:
    """Descarga varios tickers de una vez (mucho más rápido que uno a uno)."""
    import yfinance as yf

    try:
        bruto = yf.download(tickers, period=periodo, interval="1d", auto_adjust=True,
                            group_by="ticker", progress=False, threads=True)
    except Exception:  # noqa: BLE001
        return {}
    salida = {}
    for t in tickers:
        try:
            df = bruto[t] if isinstance(bruto.columns, pd.MultiIndex) else bruto
        except KeyError:
            continue
        df = df[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
        if not df.empty:
            salida[t] = _sin_zona(df.copy())
    return salida
