"""Dividendos de tu cartera: cuánto cobras al año, cuándo es el próximo y la rentabilidad con dividendos.

Datos reales de Yahoo Finance (historial de pagos y próxima fecha ex-dividendo cuando la empresa ya la ha
anunciado). Si no está anunciada, se estima con la fecha del pago equivalente del año anterior.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pandas as pd

RETENCION_ESPANA = 0.19


def _serie(div: pd.Series | None) -> pd.Series:
    if div is None or len(div) == 0:
        return pd.Series(dtype=float, index=pd.DatetimeIndex([]))
    idx = pd.to_datetime(div.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    return pd.Series(div.values, index=idx.normalize()).sort_index()


def resumen(ticker: str, dividendos: pd.Series | None, ex_dividendo: int | float | None, acciones: float,
            precio: float, fx: float = 1.0, hoy: date | None = None, fecha_compra: str | None = None) -> dict:
    """`dividendos`: pagos por acción (en la divisa del valor) con su fecha ex-dividendo.
    `ex_dividendo`: próxima fecha ex-dividendo anunciada (timestamp Unix) si la hay."""
    hoy = hoy or date.today()
    d = _serie(dividendos)
    hace_un_ano = pd.Timestamp(hoy) - pd.DateOffset(years=1)
    ultimo_ano = d[d.index > hace_un_ano]
    ttm = float(ultimo_ano.sum())
    pagos_ano = len(ultimo_ano)
    salida = {"ticker": ticker, "por_accion_ano": ttm, "rentabilidad": ttm / precio if precio else 0.0,
              "bruto_ano": acciones * ttm * fx, "neto_ano": acciones * ttm * fx * (1 - RETENCION_ESPANA),
              "pagos_ano": pagos_ano, "proximo": None, "proximo_confirmado": False, "proximo_importe": None,
              "cobrado_desde_compra": 0.0}
    if len(d) == 0:
        return salida
    ultimo_importe = float(d.iloc[-1])
    proximo = None
    if ex_dividendo:
        fecha_ex = datetime.fromtimestamp(float(ex_dividendo), tz=timezone.utc).date()
        if fecha_ex >= hoy:
            proximo, salida["proximo_confirmado"] = fecha_ex, True
    if proximo is None and pagos_ano:
        # Estimación: el pago equivalente del año pasado, un año después.
        for f in d.index:
            candidata = (f + pd.DateOffset(years=1)).date()
            if candidata >= hoy:
                proximo = candidata
                break
    if proximo:
        salida["proximo"] = proximo
        salida["proximo_importe"] = acciones * ultimo_importe * fx
    if fecha_compra:
        desde = pd.Timestamp(fecha_compra[:10])
        salida["cobrado_desde_compra"] = float(d[d.index >= desde].sum()) * acciones * fx
    return salida


def calendario(resumenes: list[dict], dias: int = 60, hoy: date | None = None) -> list[dict]:
    """Próximos dividendos de la cartera en los próximos `dias`, ordenados por fecha."""
    hoy = hoy or date.today()
    proximos = [r for r in resumenes if r.get("proximo") and (r["proximo"] - hoy).days <= dias]
    return sorted(proximos, key=lambda r: r["proximo"])


__all__ = ["resumen", "calendario", "RETENCION_ESPANA"]
