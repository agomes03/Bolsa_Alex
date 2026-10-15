"""Tu cartera frente a alternativas sencillas (fondo indexado mundial, IBEX) con la historia real.

Se calcula «si hubieras tenido tu reparto de hoy durante el periodo»: rentabilidad, volatilidad y peor caída.
Así ves con números si concentrar el dinero en pocas empresas ha compensado el riesgo extra.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .patrones import rentabilidades_cartera

REFERENCIAS = {"IWDA.AS": "Fondo indexado mundial (MSCI World, dividendos incluidos)",
               "^IBEX": "IBEX 35 (solo precio, sin dividendos)"}


def metricas(rets: pd.Series) -> dict:
    rets = rets.dropna()
    if len(rets) < 20:
        return {}
    curva = (1 + rets).cumprod()
    anos = len(rets) / 252
    total = float(curva.iloc[-1] - 1)
    return {"total": total, "anual": float(curva.iloc[-1] ** (1 / anos) - 1) if anos >= 1 else None,
            "volatilidad": float(rets.std() * np.sqrt(252)),
            "peor_caida": float((curva / curva.cummax() - 1).min()),
            "peor_mes": float(rets.rolling(21).sum().min()) if len(rets) > 21 else None,
            "curva": curva}


def comparar(historicos: dict[str, pd.DataFrame], pesos: dict[str, float], anos: int) -> dict:
    """`historicos` (en euros, ajustados por dividendos) de tus posiciones y de las referencias."""
    corte = None
    serie_cartera = rentabilidades_cartera(historicos, pesos)
    if serie_cartera.empty:
        return {}
    corte = serie_cartera.index[-1] - pd.DateOffset(years=anos)
    salida = {"Tu cartera (con tu reparto de hoy)": metricas(serie_cartera[serie_cartera.index > corte])}
    for t, nombre in REFERENCIAS.items():
        df = historicos.get(t)
        if df is not None and not df.empty:
            r = df["Close"].pct_change().dropna()
            salida[nombre] = metricas(r[r.index > corte])
    return {k: v for k, v in salida.items() if v}


def conclusion(res: dict) -> str:
    """Una frase: ¿ha compensado tu reparto frente al fondo mundial?"""
    tuya = res.get("Tu cartera (con tu reparto de hoy)")
    fondo = res.get(REFERENCIAS["IWDA.AS"])
    if not tuya or not fondo:
        return ""
    gana = tuya["total"] > fondo["total"]
    mas_riesgo = tuya["volatilidad"] > fondo["volatilidad"] * 1.1
    if gana and mas_riesgo:
        return ("Tu reparto ha ganado más que el fondo mundial, pero con más sustos (más volatilidad y caídas más "
                "fuertes). Ha salido bien en este periodo; con tan pocas empresas también puede salir mal.")
    if gana:
        return "Tu reparto ha ganado más que el fondo mundial con un riesgo parecido en este periodo."
    if mas_riesgo:
        return ("El fondo mundial ha ganado más que tu reparto y con menos sustos: en este periodo, concentrarte no "
                "ha compensado.")
    return "El fondo mundial ha ganado más que tu reparto con un riesgo parecido."


__all__ = ["comparar", "metricas", "conclusion", "REFERENCIAS"]
