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


CAMPOS_FUNDAMENTALES = [
    "longName", "currency", "marketCap", "trailingPE", "forwardPE", "priceToBook",
    "trailingAnnualDividendYield", "payoutRatio", "returnOnEquity", "profitMargins",
    "revenueGrowth", "earningsGrowth", "debtToEquity", "beta", "targetMeanPrice", "targetLowPrice",
    "targetHighPrice", "numberOfAnalystOpinions", "recommendationKey", "recommendationMean",
    "earningsTimestamp", "earningsTimestampStart",
]


def fundamentales(ticker: str) -> dict:
    """Datos de la empresa (PER, dividendo, opinión de analistas, próxima fecha de resultados...)."""
    import yfinance as yf

    try:
        info = yf.Ticker(ticker).info or {}
    except Exception:  # noqa: BLE001
        return {}
    return {k: info.get(k) for k in CAMPOS_FUNDAMENTALES if info.get(k) is not None}


def noticias_yahoo(ticker: str) -> list[dict]:
    """Titulares de Yahoo Finance para un ticker: [{titulo, enlace, fuente, fecha(datetime)}]."""
    from datetime import datetime, timezone

    import yfinance as yf

    try:
        brutas = yf.Ticker(ticker).news or []
    except Exception:  # noqa: BLE001
        return []
    salida = []
    for item in brutas:
        c = item.get("content", item)  # yfinance cambió el formato en 2025
        titulo = c.get("title")
        enlace = (c.get("canonicalUrl") or {}).get("url") or c.get("link", "")
        fuente = (c.get("provider") or {}).get("displayName") or c.get("publisher", "Yahoo Finance")
        fecha = None
        if c.get("pubDate"):
            try:
                fecha = datetime.fromisoformat(c["pubDate"].replace("Z", "+00:00"))
            except ValueError:
                pass
        elif c.get("providerPublishTime"):
            fecha = datetime.fromtimestamp(c["providerPublishTime"], tz=timezone.utc)
        if titulo:
            salida.append({"titulo": titulo, "enlace": enlace, "fuente": f"Yahoo · {fuente}", "fecha": fecha,
                           "resumen": c.get("summary", "") or ""})
    return salida
