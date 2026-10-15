"""Tipos de activo (acciones, fondos, renta fija, oro, criptomonedas...) y lectura del mercado de todos ellos."""

from __future__ import annotations

import numpy as np
import pandas as pd

CLASES = ["Acciones", "Fondos y ETF", "Renta fija", "Monetario y liquidez", "Oro y materias primas",
          "Criptomonedas"]

CRIPTO = {"BTC": "Bitcoin", "ETH": "Ethereum", "SOL": "Solana", "XRP": "XRP", "ADA": "Cardano", "BNB": "BNB",
          "DOGE": "Dogecoin", "DOT": "Polkadot", "LTC": "Litecoin", "USDT": "Tether", "USDC": "USD Coin"}

# Mercado de todo tipo de activos para leer el día a día. `invertible`: el ticker con el que se puede tener en
# euros (para la cartera); `None` si es solo un termómetro.
ACTIVOS = {
    "^GSPC": {"nombre": "Bolsa de EEUU (S&P 500)", "clase": "Acciones", "invertible": "SXR8.DE"},
    "^STOXX50E": {"nombre": "Bolsa europea (Euro Stoxx 50)", "clase": "Acciones", "invertible": "EXSA.DE"},
    "^IBEX": {"nombre": "Bolsa española (IBEX 35)", "clase": "Acciones", "invertible": "BBVAI.MC"},
    "IWDA.AS": {"nombre": "Fondo indexado mundial (MSCI World, €)", "clase": "Fondos y ETF", "invertible": "IWDA.AS"},
    "IBGS.AS": {"nombre": "Deuda pública euro 1-3 años", "clase": "Renta fija", "invertible": "IBGS.AS"},
    "XEON.DE": {"nombre": "Monetario en euros", "clase": "Monetario y liquidez", "invertible": "XEON.DE"},
    "GC=F": {"nombre": "Oro (onza, $)", "clase": "Oro y materias primas", "invertible": "4GLD.DE"},
    "SI=F": {"nombre": "Plata (onza, $)", "clase": "Oro y materias primas", "invertible": None},
    "BZ=F": {"nombre": "Petróleo Brent ($)", "clase": "Oro y materias primas", "invertible": None},
    "BTC-EUR": {"nombre": "Bitcoin (€)", "clase": "Criptomonedas", "invertible": "BTC-EUR"},
    "ETH-EUR": {"nombre": "Ethereum (€)", "clase": "Criptomonedas", "invertible": "ETH-EUR"},
}

ORO = {"4GLD.DE": "Xetra-Gold (oro físico, €)", "GC=F": "Oro", "GLD": "SPDR Gold Shares", "IGLN.L": "iShares Physical Gold",
       "SGLD.L": "Invesco Physical Gold"}

# Peso máximo orientativo de activos muy volátiles o sin rentas según el perfil (prudencia, no una regla oficial).
LIMITES_ALTERNATIVOS = {
    "Conservador": {"Criptomonedas": 0.0, "Oro y materias primas": 0.05},
    "Moderado": {"Criptomonedas": 0.02, "Oro y materias primas": 0.10},
    "Dinámico": {"Criptomonedas": 0.05, "Oro y materias primas": 0.10},
}

# Cómo encajan las clases con el reparto de 🎯 Mi plan (asesor.REPARTOS).
CLASE_A_REPARTO = {"Acciones": "Acciones individuales", "Fondos y ETF": "Fondo indexado mundial",
                   "Renta fija": "Renta fija a corto plazo", "Monetario y liquidez": "Monetario / Letras del Tesoro"}


def es_cripto(ticker: str) -> bool:
    base = ticker.split("-")[0].upper()
    return "-" in ticker and base in CRIPTO


def clase_de(ticker: str, tipo: str | None = None, nombre: str = "") -> str:
    """Clase de un activo a partir de su ticker y, si se conoce, del tipo de Yahoo ('EQUITY', 'ETF',
    'MUTUALFUND', 'CRYPTOCURRENCY'...) y su nombre."""
    from .tickers import ETFS

    tipo = (tipo or "").upper()
    n = "" if tipo == "EQUITY" else f" {(nombre or '').lower()} "   # el nombre solo cuenta si no es una acción
    if es_cripto(ticker) or tipo == "CRYPTOCURRENCY":
        return "Criptomonedas"
    if ticker in ORO or ticker in ("SI=F", "BZ=F", "CL=F") or any(p in n for p in (" gold", " oro ", "silver",
                                                                                   " plata ")):
        return "Oro y materias primas"
    if ticker in ETFS:
        sector = ETFS[ticker][1]
        return "Renta fija" if sector == "Renta fija" else "Monetario y liquidez" if sector == "Monetario" \
            else "Fondos y ETF"
    if tipo in ("ETF", "MUTUALFUND") or ticker.startswith("0P") or any(
            p in n for p in (" etf", "ucits", " index", "fondo", " fund", " fi ", "indexado", "msci", "s&p 500",
                                     "ishares", "vanguard", "amundi", "xtrackers", " sicav")):
        if any(p in n for p in ("money market", "monetario", "overnight", "liquidez")):
            return "Monetario y liquidez"
        if any(p in n for p in ("bond", "renta fija", "govt", "government", "aggregate", "treasury", "deuda")):
            return "Renta fija"
        return "Fondos y ETF"
    return "Acciones"


def estado(df: pd.DataFrame) -> dict | None:
    """Lectura de un activo: variaciones, tendencia (media de 200 sesiones), distancia al máximo y volatilidad."""
    if df is None or df.empty or len(df) < 30:
        return None
    c = df["Close"].dropna()
    ultimo = float(c.iloc[-1])

    def var(n):
        return float(ultimo / c.iloc[-n - 1] * 100 - 100) if len(c) > n else None

    sma200 = float(c.iloc[-200:].mean()) if len(c) >= 200 else None
    maximo = float(c.iloc[-252:].max())
    rets = c.pct_change().dropna().iloc[-252:]
    return {"precio": ultimo, "var_1d": var(1), "var_1m": var(21), "var_1a": var(252),
            "alcista": ultimo > sma200 if sma200 else None, "desde_maximo": ultimo / maximo * 100 - 100,
            "volatilidad": float(rets.std() * np.sqrt(252) * 100) if len(rets) > 20 else None}


def lectura(nombre: str, e: dict, clase: str | None = None) -> str:
    """Una frase en lenguaje sencillo sobre cómo está ese activo."""
    if clase in ("Monetario y liquidez", "Renta fija") and e.get("var_1a") is not None:
        que = "lo que pagan hoy los tipos de interés, casi sin riesgo" if clase == "Monetario y liquidez" else \
            "con movimientos pequeños; amortigua las caídas de la bolsa"
        return f"{nombre}: {e['var_1a']:+.1f} % en el último año, {que}.".replace(".", ",", 1)
    if e["alcista"] is None:
        tendencia = "sin historia suficiente para saber su tendencia"
    else:
        tendencia = "en tendencia alcista" if e["alcista"] else "en tendencia bajista"
    caida = e["desde_maximo"]
    lejos = "en máximos del último año" if caida > -3 else f"un {abs(caida):.0f} % por debajo de su máximo del año"
    texto = f"{nombre}: {tendencia}, {lejos}".replace(".", ",")
    if e.get("volatilidad") and e["volatilidad"] > 45:
        texto += " · muy volátil"
    return texto + "."


def resumen(historicos: dict[str, pd.DataFrame]) -> list[dict]:
    salida = []
    for t, info in ACTIVOS.items():
        e = estado(historicos.get(t))
        if e:
            salida.append({"ticker": t, **info, **e, "lectura": lectura(info["nombre"], e, info["clase"])})
    return salida


__all__ = ["ACTIVOS", "CLASES", "CRIPTO", "LIMITES_ALTERNATIVOS", "CLASE_A_REPARTO", "clase_de", "es_cripto",
           "estado", "lectura", "resumen"]
