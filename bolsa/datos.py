"""Descarga de cotizaciones desde Yahoo Finance (gratis, con ~15 min de retraso en Bolsa de Madrid)."""

from __future__ import annotations

import os
import re
import time
from pathlib import Path

import pandas as pd

# Respaldo: cada descarga correcta se guarda en disco; si Yahoo falla (sin conexión, límite de peticiones,
# cambios en su web), se usan los últimos datos buenos y la app avisa de que son antiguos.
CARPETA_RESPALDO = Path(os.environ.get("BOLSA_RESPALDO", Path(__file__).resolve().parent.parent / ".respaldo_datos"))
RESPALDOS_USADOS: dict[str, float] = {}     # ticker -> fecha (epoch) de los datos de respaldo usados
_CUANDO_RESPALDO: dict[str, float] = {}     # ticker -> cuándo se tuvo que usar el respaldo

def _descargar_yf(yf, *a, **k):
    # yfinance 1.7 guarda cada descarga por separado (antes usaba un diccionario global y dos a la vez se
    # mezclaban): se pueden hacer varias a la vez sin bloquearse.
    return yf.download(*a, **k)


def _ruta_respaldo(ticker: str, tipo: str) -> Path:
    return CARPETA_RESPALDO / (re.sub(r"[^A-Za-z0-9._-]", "_", f"{tipo}_{ticker}") + ".pkl")


def _guardar_respaldo(ticker: str, tipo: str, df: pd.DataFrame) -> None:
    try:
        CARPETA_RESPALDO.mkdir(parents=True, exist_ok=True)
        ruta = _ruta_respaldo(ticker, tipo)
        temporal = ruta.with_suffix(f".{os.getpid()}.tmp")
        df.to_pickle(temporal)
        os.replace(temporal, ruta)           # escritura atómica
    except Exception:  # noqa: BLE001 - el respaldo nunca debe romper una descarga correcta
        pass


def _leer_respaldo(ticker: str, tipo: str) -> pd.DataFrame:
    ruta = _ruta_respaldo(ticker, tipo)
    try:
        df = pd.read_pickle(ruta)
    except Exception:  # noqa: BLE001
        return pd.DataFrame()
    RESPALDOS_USADOS[ticker] = ruta.stat().st_mtime
    _CUANDO_RESPALDO[ticker] = time.time()
    return df


def respaldo_mas_antiguo() -> float | None:
    """Fecha (epoch) del respaldo más antiguo usado en la última media hora, o None si todo es fresco. (Un valor
    que Yahoo ha dejado de dar no deja el aviso puesto para siempre.)"""
    reciente = time.time() - 1800
    fechas = [f for t, f in list(RESPALDOS_USADOS.items()) if _CUANDO_RESPALDO.get(t, 0) >= reciente]
    return min(fechas) if fechas else None


def _sin_zona(df: pd.DataFrame) -> pd.DataFrame:
    idx = pd.to_datetime(df.index)
    df.index = idx.tz_localize(None) if idx.tz is not None else idx
    return df


def historico(ticker: str, periodo: str = "2y") -> pd.DataFrame:
    """Histórico diario. Devuelve un DataFrame vacío si no hay datos."""
    import yfinance as yf

    try:
        df = yf.Ticker(ticker).history(period=periodo, interval="1d", auto_adjust=True)
    except Exception:  # noqa: BLE001 - errores de red: se usan los últimos datos buenos
        df = None
    if df is None or df.empty:
        return _leer_respaldo(ticker, f"diario{periodo}")
    df = _sin_zona(df[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"]))
    RESPALDOS_USADOS.pop(ticker, None)
    _guardar_respaldo(ticker, f"diario{periodo}", df)
    return df


def varios(tickers: list[str], periodo: str = "2y") -> dict[str, pd.DataFrame]:
    """Descarga varios tickers de una vez (mucho más rápido que uno a uno)."""
    import yfinance as yf

    try:
        bruto = _descargar_yf(yf, tickers, period=periodo, interval="1d", auto_adjust=True,
                            group_by="ticker", progress=False, threads=True)
    except Exception:  # noqa: BLE001
        bruto = pd.DataFrame()
    salida = {}
    for t in tickers:
        df = pd.DataFrame()
        if bruto is not None and not bruto.empty:
            try:
                df = bruto[t] if isinstance(bruto.columns, pd.MultiIndex) else bruto
                df = df[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
            except KeyError:
                df = pd.DataFrame()
        if not df.empty:
            salida[t] = _sin_zona(df.copy())
            RESPALDOS_USADOS.pop(t, None)
            _guardar_respaldo(t, f"diario{periodo}", salida[t])
        else:
            respaldo = _leer_respaldo(t, f"diario{periodo}")
            if not respaldo.empty:
                salida[t] = respaldo
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
        df = None
    if df is None or df.empty:
        return _leer_respaldo(ticker, f"real{periodo}")
    df = _sin_zona(df[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"]))
    RESPALDOS_USADOS.pop(ticker, None)
    _guardar_respaldo(ticker, f"real{periodo}", df)
    return df


def barras_ejecucion(diario: pd.DataFrame, intradia_df: pd.DataFrame) -> pd.DataFrame:
    """Velas para decidir si una orden se ha ejecutado: las diarias de los días sin datos intradía y, después,
    las intradía (más precisas: saben a qué hora se tocó cada precio)."""
    if intradia_df is None or intradia_df.empty:
        return diario
    if diario is None or diario.empty:
        return intradia_df
    inicio = intradia_df.index[0].normalize()
    return pd.concat([diario[diario.index < inicio], intradia_df]).sort_index()


def ultimo_precio(df: pd.DataFrame | None) -> dict | None:
    """Último precio, cierre anterior, variación del día y fecha de la última vela diaria.
    Mientras la bolsa está abierta, la vela de hoy se va actualizando (con el retraso de Yahoo, ~15 min)."""
    if df is None or df.empty:
        return None
    c = df["Close"].dropna()
    if c.empty:
        return None
    precio = float(c.iloc[-1])
    anterior = float(c.iloc[-2]) if len(c) > 1 else None
    return {"precio": precio, "anterior": anterior, "fecha": pd.Timestamp(c.index[-1]).date(),
            "variacion_pct": (precio / anterior - 1) * 100 if anterior else None}


def combinar_precio(diario: pd.Series | None, intradia: pd.Series | None) -> dict | None:
    """Precio más reciente de un valor uniendo velas diarias (cierre oficial, con subasta) e intradía de 15 minutos
    (en hora de Madrid). Yahoo a veces tarda horas en publicar la vela diaria; la intradía llega antes.
    Devuelve precio, anterior (cierre de la sesión previa), fecha de la sesión y variación del día."""
    por_dia = {}
    if diario is not None:
        for f, v in diario.dropna().items():
            por_dia[pd.Timestamp(f).date()] = ("diario", float(v))
    if intradia is not None and len(intradia.dropna()):
        s = intradia.dropna()
        idx = s.index.tz_convert("Europe/Madrid") if s.index.tz is not None else s.index
        for dia, v in pd.Series(s.values, index=idx).groupby(idx.date).last().items():
            # La vela diaria manda si existe: durante la sesión lleva el último precio y, al cierre, la subasta.
            por_dia.setdefault(dia, ("intradia", float(v)))
    if not por_dia:
        return None
    dias = sorted(por_dia)
    precio = por_dia[dias[-1]][1]
    anterior = por_dia[dias[-2]][1] if len(dias) > 1 else None
    return {"precio": precio, "anterior": anterior, "fecha": dias[-1],
            "variacion_pct": (precio / anterior - 1) * 100 if anterior else None}


def precios_recientes(tickers: list[str]) -> dict[str, dict]:
    """Último precio de muchos valores a la vez (dos descargas en bloque: diaria e intradía de 15 minutos)."""
    import yfinance as yf

    salida = {}
    if not tickers:
        return salida

    def columnas(bruto):
        if bruto is None or bruto.empty or "Close" not in bruto:
            return {}
        c = bruto["Close"]
        if isinstance(c, pd.Series):
            return {tickers[0]: c}
        return {t: c[t] for t in c.columns if t in tickers}

    try:
        diario = columnas(_descargar_yf(yf, tickers, period="5d", interval="1d", auto_adjust=False, progress=False,
                                      threads=True))
    except Exception:  # noqa: BLE001
        diario = {}
    try:
        intradia = columnas(_descargar_yf(yf, tickers, period="5d", interval="15m", auto_adjust=False, progress=False,
                                        threads=True))
    except Exception:  # noqa: BLE001
        intradia = {}
    for t in tickers:
        q = combinar_precio(diario.get(t), intradia.get(t))
        if q:
            salida[t] = q
    return salida


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
        if diario is not None and not diario.empty and diario.index[-1].normalize() == dia:
            # La vela diaria de hoy incluye la subasta de cierre: es el precio oficial.
            f = diario.iloc[-1]
            ultimo, maximo, minimo = float(f["Close"]), float(f["High"]), float(f["Low"])
            volumen = float(f["Volume"]) or volumen
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


# Bolsas preferidas al elegir entre varios resultados (para un inversor en euros).
_PREFERENCIA_BOLSA = {"MCE": 0, "GER": 1, "AMS": 1, "PAR": 1, "MIL": 1, "FRA": 2, "NMS": 3, "NYQ": 3, "NGM": 3,
                      "LSE": 4}


def buscar_simbolo(consulta: str) -> dict | None:
    """Busca en Yahoo un ISIN o un nombre y devuelve {'symbol', 'name', 'type'} (None si no lo encuentra).
    Si hay varias bolsas, prefiere la española para ISIN ES, las europeas en euros para fondos y ETF, y la
    de EEUU para ISIN US."""
    import yfinance as yf

    try:
        resultados = yf.Search(consulta, max_results=10, news_count=0).quotes
    except Exception:  # noqa: BLE001
        return None
    resultados = [r for r in resultados or [] if r.get("symbol")]
    if not resultados:
        return None
    pais = consulta[:2].upper() if len(consulta) == 12 else ""

    def orden(r):
        bolsa = r.get("exchange", "")
        if pais == "ES":
            return 0 if bolsa == "MCE" else 5
        if pais == "US":
            return 0 if bolsa in ("NMS", "NYQ", "NGM", "NCM", "ASE") else 5
        return _PREFERENCIA_BOLSA.get(bolsa, 6)

    r = sorted(resultados, key=orden)[0]
    return {"symbol": r["symbol"], "name": r.get("longname") or r.get("shortname") or "",
            "type": r.get("quoteType")}


# Lo que tiene sentido buscar (fuera quedan opciones, futuros sueltos de empresas, etc.).
TIPOS_BUSCABLES = {"EQUITY": "Acción", "ETF": "ETF", "MUTUALFUND": "Fondo", "CRYPTOCURRENCY": "Cripto",
                   "INDEX": "Índice", "CURRENCY": "Divisa"}


def buscar_simbolos(consulta: str, maximo: int = 8) -> list[dict]:
    """Resultados de Yahoo para un nombre, ticker o ISIN: [{'symbol', 'name', 'type', 'exchange'}], primero las
    bolsas europeas en euros y EEUU (más fáciles de comprar desde España)."""
    import yfinance as yf

    consulta = consulta.strip()
    if len(consulta) < 2:
        return []
    try:
        resultados = yf.Search(consulta, max_results=15, news_count=0).quotes or []
    except Exception:  # noqa: BLE001
        return []
    salida = [{"symbol": r["symbol"], "name": r.get("longname") or r.get("shortname") or r["symbol"],
               "type": r.get("quoteType"), "exchange": r.get("exchDisp") or r.get("exchange") or ""}
              for r in resultados if r.get("symbol") and r.get("quoteType") in TIPOS_BUSCABLES]
    exacto = consulta.upper()
    salida.sort(key=lambda r: (r["symbol"] != exacto, _PREFERENCIA_BOLSA.get(
        next((x.get("exchange") for x in resultados if x.get("symbol") == r["symbol"]), ""), 6)))
    return salida[:maximo]


CAMPOS_FUNDAMENTALES = [
    "longName", "currency", "marketCap", "trailingPE", "forwardPE", "priceToBook",
    "trailingAnnualDividendYield", "payoutRatio", "returnOnEquity", "profitMargins",
    "revenueGrowth", "earningsGrowth", "debtToEquity", "beta", "targetMeanPrice", "targetLowPrice",
    "targetHighPrice", "numberOfAnalystOpinions", "recommendationKey", "recommendationMean",
    "earningsTimestamp", "earningsTimestampStart", "exDividendDate", "dividendDate", "dividendYield",
    "fiveYearAvgDividendYield", "currentRatio", "quoteType",
]


def dividendos_varios(tickers: list[str], periodo: str = "5y") -> dict[str, pd.Series]:
    """Dividendos de varios valores en UNA descarga (mucho más rápido que uno a uno)."""
    import yfinance as yf

    if not tickers:
        return {}
    try:
        bruto = _descargar_yf(yf, tickers, period=periodo, interval="1d", actions=True, group_by="ticker",
                            progress=False, threads=True, auto_adjust=True)
    except Exception:  # noqa: BLE001
        return {}
    salida = {}
    for t in tickers:
        try:
            d = (bruto[t] if isinstance(bruto.columns, pd.MultiIndex) else bruto)["Dividends"]
        except KeyError:
            continue
        salida[t] = d[d > 0].dropna()
    return salida


def dividendos(ticker: str) -> pd.Series:
    """Historial de dividendos por acción (fecha ex-dividendo → importe, en la divisa del valor)."""
    import yfinance as yf

    try:
        d = yf.Ticker(ticker).dividends
    except Exception:  # noqa: BLE001
        return pd.Series(dtype=float)
    return d if d is not None else pd.Series(dtype=float)


def fundamentales(ticker: str) -> dict:
    """Datos de la empresa (PER, dividendo, opinión de analistas, próxima fecha de resultados...)."""
    import yfinance as yf

    try:
        info = yf.Ticker(ticker).info or {}
    except Exception:  # noqa: BLE001
        return {}
    return {k: info.get(k) for k in CAMPOS_FUNDAMENTALES if info.get(k) is not None}


def composicion_fondo(ticker: str) -> dict:
    """Qué hay dentro de un ETF o fondo (Yahoo Finance): sus 10 mayores posiciones con su peso y el reparto por
    sectores. Vacío si Yahoo no lo da (acciones, algunos fondos)."""
    import yfinance as yf

    salida: dict = {}
    try:
        fd = yf.Ticker(ticker).funds_data
        top = fd.top_holdings
        if top is not None and not top.empty:
            salida["top"] = [{"simbolo": str(s), "nombre": str(f.get("Name") or s),
                              "peso": float(f.get("Holding Percent") or 0)} for s, f in top.iterrows()]
        sectores = fd.sector_weightings
        if sectores:
            salida["sectores"] = {k: float(v) for k, v in sectores.items() if v}
    except Exception:  # noqa: BLE001 - no es un fondo o Yahoo no lo da
        pass
    return salida


def analistas(ticker: str) -> dict:
    """Todo lo que publican los analistas sobre una empresa (Yahoo Finance, que agrega a los bancos y brókers que
    la siguen): recuento de recomendaciones hoy y hace 3 meses, precios objetivo (media, mediana, mínimo y
    máximo), revisiones de las previsiones de beneficio y cambios de recomendación recientes de cada firma.
    Cada parte es opcional: si Yahoo no la da, no aparece."""
    import yfinance as yf

    tk = yf.Ticker(ticker)
    salida: dict = {}
    try:
        r = tk.recommendations
        if r is not None and not r.empty:
            filas = {str(f["period"]): {k: int(f.get(k, 0) or 0) for k in
                                        ("strongBuy", "buy", "hold", "sell", "strongSell")} for _, f in r.iterrows()}
            salida["recuento"] = filas.get("0m")
            salida["recuento_antes"] = filas.get("-3m") or filas.get("-2m") or filas.get("-1m")
    except Exception:  # noqa: BLE001
        pass
    try:
        o = tk.analyst_price_targets
        if o and o.get("mean"):
            salida["objetivos"] = {k: float(o[k]) for k in ("mean", "median", "low", "high") if o.get(k)}
    except Exception:  # noqa: BLE001
        pass
    try:
        e = tk.eps_trend
        if e is not None and not e.empty:
            fila = e.loc["+1y"] if "+1y" in e.index else e.loc["0y"] if "0y" in e.index else None
            if fila is not None and fila.get("current") and fila.get("90daysAgo"):
                salida["revision_beneficios"] = float(fila["current"]) / float(fila["90daysAgo"]) - 1
    except Exception:  # noqa: BLE001
        pass
    try:
        u = tk.upgrades_downgrades
        if u is not None and not u.empty:
            idx = pd.to_datetime(u.index)
            if idx.tz is not None:
                idx = idx.tz_localize(None)
            recientes = u[idx >= pd.Timestamp.now() - pd.Timedelta(days=180)]
            salida["cambios"] = [{"fecha": pd.Timestamp(f).date().isoformat(), "firma": c.get("Firm"),
                                  "a": c.get("ToGrade"), "de": c.get("FromGrade"), "accion": c.get("Action"),
                                  "objetivo": c.get("currentPriceTarget")}
                                 for f, c in recientes.head(6).iterrows()]
    except Exception:  # noqa: BLE001
        pass
    return salida


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
