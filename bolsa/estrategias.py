"""Estrategias respaldadas por la evidencia (laboratorio con datos reales + estudios académicos).

1. Carteras modelo de rotación mensual:
   - Dinámica: las 10 acciones con más "momentum 12-1" (lo que más subió en el último año, sin contar el
     último mes). El momentum es uno de los patrones más estudiados de la bolsa (Jegadeesh y Titman, 1993).
   - Equilibrada: las 20 con más momentum, solo si su mercado está en tendencia alcista.
   - Tranquila: las 20 menos volátiles, solo si su mercado está en tendencia alcista
     ("anomalía de baja volatilidad": rentabilidad parecida a la media con muchos menos sustos).
2. Regla de protección para índices/ETF: estar invertido mientras el índice esté por encima de su media de
   200 sesiones y salir solo si cae más de un 2% por debajo (la banda evita entrar y salir a cada rato).
   En la historia del IBEX (desde 1994) ganó algo más que 'comprar y mantener' (6,7% frente a 5,3% al año)
   con una peor caída de -37% en lugar de -63%; en el S&P 500 (desde 1928), -53% en lugar de -86%.

Advertencia importante: el universo son las grandes empresas de HOY (las que fracasaron no están), y eso
favorece al momentum en las simulaciones. Úsalo como una parte pequeña y diversificada de tu dinero.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import experimentos
from .costes import Tarifa
from .tickers import ETFS


@dataclass(frozen=True)
class CarteraModelo:
    clave: str
    nombre: str
    senal: str           # "momentum" o "baja_vol"
    n: int
    filtro_mercado: bool
    perfil: str
    descripcion: str


CARTERAS = {
    "dinamica": CarteraModelo("dinamica", "Cartera dinámica (momentum 10)", "momentum", 10, False, "Dinámico",
                              "Cada mes, las 10 acciones que más han subido en el último año (sin contar el último "
                              "mes). Es la que más ha ganado en las pruebas, pero también la que más ha caído: "
                              "llegó a perder más de un tercio en algún momento."),
    "equilibrada": CarteraModelo("equilibrada", "Cartera equilibrada (momentum 20 + filtro)", "momentum", 20, True,
                                 "Moderado", "Cada mes, las 20 acciones con más momentum, pero solo de mercados en "
                                 "tendencia alcista; si el mercado se tuerce, esa parte queda en liquidez."),
    "tranquila": CarteraModelo("tranquila", "Cartera tranquila (baja volatilidad 20 + filtro)", "baja_vol", 20, True,
                               "Conservador", "Cada mes, las 20 acciones más estables (las que menos se mueven), solo "
                               "de mercados en tendencia alcista. Gana parecido a la media con muchos menos sustos."),
}
CARTERA_POR_PERFIL = {c.perfil: c for c in CARTERAS.values()}


def cierres_acciones(acciones: dict[str, pd.DataFrame]) -> pd.DataFrame:
    return pd.DataFrame({t: df["Close"] for t, df in acciones.items() if t not in ETFS}).sort_index().ffill(limit=5)


def senal(cierres: pd.DataFrame, tipo: str) -> pd.DataFrame:
    s = experimentos.senales_basicas(cierres)
    return s["Momentum 12-1"] if tipo == "momentum" else s["Baja volatilidad"]


def composicion_hoy(cierres: pd.DataFrame, permitido: pd.DataFrame, c: CarteraModelo) -> list[dict]:
    sig = senal(cierres, c.senal).iloc[-1]
    ok = sig.notna() & cierres.iloc[-1].notna()
    if c.filtro_mercado:
        ok &= permitido.iloc[-1].reindex(sig.index).fillna(False).astype(bool)
    elegidas = sig[ok].sort_values(ascending=False).head(c.n)
    return [{"ticker": t, "senal": float(v), "precio": float(cierres[t].iloc[-1])} for t, v in elegidas.items()]


def evaluar_cartera(cierres: pd.DataFrame, permitido: pd.DataFrame, c: CarteraModelo, tarifa: Tarifa,
                    desde: str = "2017-06-01") -> dict:
    capital = 10_000.0 if c.n <= 10 else 20_000.0
    sig = senal(cierres, c.senal)
    curva, met = experimentos.simular_rotacion(cierres, sig, c.n, tarifa, capital,
                                               permitido if c.filtro_mercado else None, inicio=pd.Timestamp(desde))
    # Referencia: todas las acciones a partes iguales con un capital grande, para que las comisiones mínimas
    # no la penalicen (se parece al coste de un fondo indexado). Después se escala a la misma cifra.
    todas, met_todas = experimentos.simular_rotacion(cierres, pd.DataFrame(1.0, index=cierres.index,
                                                                           columns=cierres.columns),
                                                     len(cierres.columns), tarifa, 1_000_000.0,
                                                     inicio=pd.Timestamp(desde))
    todas = todas * capital / 1_000_000.0
    escala = 10_000.0 / capital

    def semanal(s: pd.Series) -> dict:
        s = (s * escala).resample("W").last().dropna()
        return {"fechas": [d.date().isoformat() for d in s.index], "valores": s.round(0).tolist()}

    anual = (curva.resample("YE").last() / curva.resample("YE").last().shift(1).fillna(capital) - 1) * 100
    anual_todas = (todas.resample("YE").last() / todas.resample("YE").last().shift(1).fillna(capital) - 1) * 100
    met_todas["gastos"] = met_todas["gastos"] * capital / 1_000_000.0
    return {"metricas": met, "referencia": met_todas, "curva": semanal(curva), "curva_referencia": semanal(todas),
            "por_ano": [{"ano": int(d.year), "cartera": float(a), "todas": float(b)}
                        for d, a, b in zip(anual.index, anual.values, anual_todas.values)],
            "capital_simulado": capital}


def proteccion_indices(largos: dict[str, pd.DataFrame], banda: float = 0.02) -> dict:
    """Estado actual de la regla de protección (media 200 ± 2%) y su historia."""
    salida = {}
    for t, df in largos.items():
        if df is None or df.empty:
            continue
        c = df["Close"].dropna()
        sma = c.rolling(200, min_periods=200).mean()
        estado, cambios = None, []
        for fecha, precio, media in zip(c.index, c.values, sma.values):
            if np.isnan(media):
                continue
            nuevo = estado
            if precio > media * (1 + banda):
                nuevo = "dentro"
            elif precio < media * (1 - banda):
                nuevo = "fuera"
            if nuevo != estado:
                cambios.append((fecha, nuevo))
                estado = nuevo
        hist = experimentos.filtro_tendencia_indice(c, 200, banda)
        salida[t] = {"estado": estado, "desde": str(cambios[-1][0].date()) if cambios else None,
                     "precio": float(c.iloc[-1]), "media200": float(sma.iloc[-1]),
                     "distancia": float(c.iloc[-1] / sma.iloc[-1] - 1),
                     "salir_si_baja_de": float(sma.iloc[-1] * (1 - banda)),
                     "entrar_si_sube_de": float(sma.iloc[-1] * (1 + banda)),
                     "ultimos_cambios": [{"fecha": str(f.date()), "estado": e} for f, e in cambios[-6:]],
                     "historia": hist}
    return salida


def permitido(cierres: pd.DataFrame, indices: dict[str, pd.DataFrame]) -> pd.DataFrame:
    return experimentos.permitido_por_indice(cierres, indices)


def percentil(serie: pd.Series) -> pd.Series:
    return serie.rank(pct=True)


def momentum_hoy(cierres: pd.DataFrame) -> pd.Series:
    return senal(cierres, "momentum").iloc[-1]


def volatilidad_hoy(cierres: pd.DataFrame) -> pd.Series:
    return -senal(cierres, "baja_vol").iloc[-1]


__all__ = ["CARTERAS", "CARTERA_POR_PERFIL", "CarteraModelo", "cierres_acciones", "composicion_hoy",
           "evaluar_cartera", "proteccion_indices", "permitido", "percentil", "momentum_hoy", "volatilidad_hoy"]
