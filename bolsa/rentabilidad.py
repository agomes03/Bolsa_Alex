"""Rentabilidad de tu cartera por periodos (hoy, semana, mes, año...) y su evolución, como en Ghostfolio,
Portfolio Performance o el bróker.

Se calcula con las posiciones que tienes HOY (títulos x precio de cada día, en euros): responde a «¿cómo le ha ido
a lo que tengo?», sin que las aportaciones o retiradas de dinero inflen o hundan la cifra. Los extractos del banco
no traen la fecha de cada compra, así que no se puede rehacer al céntimo lo que ganaste tú en cada periodo.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

PERIODOS = [("Hoy", "1d"), ("1 semana", "7d"), ("1 mes", "1m"), ("En el año", "ytd"), ("1 año", "1y"),
            ("3 años", "3y"), ("5 años", "5y")]


def valor_diario(acciones: dict[str, float], cierres_eur: dict[str, pd.Series]) -> pd.Series:
    """Valor en euros de las posiciones de hoy cada día (solo los días en que todas tienen precio)."""
    series = {t: cierres_eur[t].dropna() * n for t, n in acciones.items()
              if t in cierres_eur and cierres_eur[t] is not None and len(cierres_eur[t].dropna())}
    if not series:
        return pd.Series(dtype=float)
    tabla = pd.DataFrame(series).sort_index().ffill()
    tabla = tabla.dropna()                    # desde que todas cotizan
    return tabla.sum(axis=1)


def _inicio(clave: str, fin: pd.Timestamp) -> pd.Timestamp:
    if clave == "ytd":
        return pd.Timestamp(date(fin.year, 1, 1)) - pd.Timedelta(days=1)
    n, unidad = int(clave[:-1]), clave[-1]
    return fin - (pd.Timedelta(days=n) if unidad == "d" else pd.DateOffset(months=n) if unidad == "m"
                  else pd.DateOffset(years=n))


def por_periodos(serie: pd.Series, variacion_hoy: float | None = None) -> list[dict]:
    """[{periodo, pct}] con pct en %. «Hoy» usa la variación de la sesión si se pasa (precio de ahora)."""
    serie = serie.dropna()
    salida = []
    if len(serie) < 2:
        return salida
    fin = serie.index[-1]
    for nombre, clave in PERIODOS:
        if clave == "1d":
            pct = variacion_hoy if variacion_hoy is not None else (serie.iloc[-1] / serie.iloc[-2] - 1) * 100
        else:
            inicio = _inicio(clave, fin)
            if serie.index[0] > inicio + pd.Timedelta(days=5):
                continue                      # no hay historia suficiente para ese periodo
            base = serie[serie.index <= inicio]
            if base.empty:
                continue
            pct = (serie.iloc[-1] / base.iloc[-1] - 1) * 100
        salida.append({"periodo": nombre, "pct": float(pct)})
    return salida


def base_100(serie: pd.Series, desde: pd.Timestamp) -> pd.Series:
    s = serie[serie.index >= desde].dropna()
    return s / s.iloc[0] * 100 if len(s) else s


__all__ = ["PERIODOS", "valor_diario", "por_periodos", "base_100"]
