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


def _a_madrid(df: pd.DataFrame) -> pd.DataFrame:
    """Índice intradía en hora de Madrid sin zona (así se comparan bolsas de distintos países)."""
    idx = pd.to_datetime(df.index)
    idx = idx.tz_convert("Europe/Madrid") if idx.tz is not None else idx.tz_localize("UTC").tz_convert("Europe/Madrid")
    df.index = idx.tz_localize(None)
    return df


def intradia(ticker: str, periodo: str = "5d", intervalo: str = "5m") -> pd.DataFrame:
    """Velas intradía SIN ajustar (los precios que ves en el bróker), en hora de Madrid."""
    import yfinance as yf

    try:
        df = yf.Ticker(ticker).history(period=periodo, interval=intervalo, auto_adjust=False, prepost=False)
    except Exception:  # noqa: BLE001
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()
    return _a_madrid(df[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"]))


def diario_sin_ajustar(ticker: str, periodo: str = "1y") -> pd.DataFrame:
    """Histórico diario con los precios tal cual cotizaron (sin descontar dividendos)."""
    import yfinance as yf

    try:
        df = yf.Ticker(ticker).history(period=periodo, interval="1d", auto_adjust=False)
    except Exception:  # noqa: BLE001
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()
    return _sin_zona(df[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"]))


def barras_ejecucion(diario: pd.DataFrame, intradia_df: pd.DataFrame) -> pd.DataFrame:
    """Velas para decidir si una orden se ha ejecutado: las diarias de los días sin datos intradía y, después,
    las intradía (más precisas: saben a qué hora se tocó cada precio)."""
    if intradia_df is None or intradia_df.empty:
        return diario
    if diario is None or diario.empty:
        return intradia_df
    inicio = intradia_df.index[0].normalize()
    return pd.concat([diario[diario.index < inicio], intradia_df]).sort_index()


def cotizacion(diario: pd.DataFrame, intradia_df: pd.DataFrame) -> dict | None:
    """Ficha de cotización como la del bróker: último, variación, apertura, máximo, mínimo, volumen..."""
    if (diario is None or diario.empty) and (intradia_df is None or intradia_df.empty):
        return None
    if intradia_df is not None and not intradia_df.empty:
        dia = intradia_df.index[-1].normalize()
        hoy = intradia_df[intradia_df.index >= dia]
        ultimo, hora = float(hoy["Close"].iloc[-1]), intradia_df.index[-1]
        apertura, maximo, minimo = float(hoy["Open"].iloc[0]), float(hoy["High"].max()), float(hoy["Low"].min())
        volumen = float(hoy["Volume"].sum())
        previos = diario[diario.index < dia] if diario is not None and not diario.empty else pd.DataFrame()
        anterior = float(previos["Close"].iloc[-1]) if len(previos) else None
    else:
        f = diario.iloc[-1]
        ultimo, hora = float(f["Close"]), diario.index[-1]
        apertura, maximo, minimo, volumen = float(f["Open"]), float(f["High"]), float(f["Low"]), float(f["Volume"])
        anterior = float(diario["Close"].iloc[-2]) if len(diario) > 1 else None
        hoy = None
    ultimo_ano = diario[diario.index >= diario.index[-1] - pd.Timedelta(days=365)] if diario is not None and \
        not diario.empty else pd.DataFrame()
    return {"precio": ultimo, "hora": hora, "anterior": anterior,
            "variacion": ultimo - anterior if anterior else None,
            "variacion_pct": (ultimo / anterior - 1) * 100 if anterior else None,
            "apertura": apertura, "maximo": maximo, "minimo": minimo, "volumen": volumen,
            "max_52s": float(max(ultimo_ano["High"].max(), maximo)) if len(ultimo_ano) else None,
            "min_52s": float(min(ultimo_ano["Low"].min(), minimo)) if len(ultimo_ano) else None,
            "sesion": hoy}


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
