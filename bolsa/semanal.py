"""Resumen semanal en palabras: cuánto ha cambiado tu dinero, qué lo ha movido y qué ha pasado en el mercado."""

from __future__ import annotations

import pandas as pd

SESIONES_SEMANA = 5


def _cambio(df: pd.DataFrame | None, sesiones: int = SESIONES_SEMANA) -> tuple[float, float] | None:
    """(precio hace `sesiones` sesiones, último precio)."""
    if df is None or df.empty:
        return None
    c = df["Close"].dropna()
    if len(c) <= sesiones:
        return None
    return float(c.iloc[-1 - sesiones]), float(c.iloc[-1])


def resumen(posiciones: list[dict], historicos: dict[str, pd.DataFrame], referencias: dict[str, pd.DataFrame] | None
            = None, noticias: list[dict] | None = None) -> dict:
    """`posiciones`: ticker, nombre, acciones y fx (euros por unidad de su divisa).
    `referencias`: {'IBEX 35': df, 'Fondo mundial': df}. `noticias`: [{'titulo', 'empresas'}]."""
    filas = []
    for p in posiciones:
        par = _cambio(historicos.get(p["ticker"]))
        if not par:
            continue
        antes, ahora = par
        fx = p.get("fx", 1.0)
        filas.append({"nombre": p["nombre"], "ticker": p["ticker"], "antes": p["acciones"] * antes * fx,
                      "ahora": p["acciones"] * ahora * fx, "pct": ahora / antes - 1 if antes else 0.0})
    if not filas:
        return {}
    antes, ahora = sum(f["antes"] for f in filas), sum(f["ahora"] for f in filas)
    for f in filas:
        f["cambio"] = f["ahora"] - f["antes"]
    filas.sort(key=lambda f: -abs(f["cambio"]))
    refs = {}
    for nombre, df in (referencias or {}).items():
        par = _cambio(df)
        if par:
            refs[nombre] = par[1] / par[0] - 1
    mias = {f["ticker"] for f in filas}
    titulares = [n for n in (noticias or []) if mias & set(n.get("empresas") or [])][:3]
    return {"antes": antes, "ahora": ahora, "cambio": ahora - antes, "pct": ahora / antes - 1 if antes else 0.0,
            "posiciones": filas, "referencias": refs, "noticias": titulares}


def _e(x: float) -> str:
    s = f"{abs(x):,.0f}".replace(",", ".")
    return ("+" if x >= 0 else "−") + s + " €"


def _p(x: float) -> str:
    return (f"{x * 100:+.1f} %").replace(".", ",").replace("-", "−")


def texto(r: dict) -> list[str]:
    """El resumen en frases cortas."""
    if not r:
        return []
    lineas = [f"Esta semana tu dinero ha cambiado {_e(r['cambio'])} ({_p(r['pct'])}) y ahora vale "
              f"{_e(r['ahora'])[1:]}."]
    if r["referencias"]:
        lineas.append("En el mismo tiempo: " + ", ".join(f"{n} {_p(v)}" for n, v in r["referencias"].items()) + ".")
    suben = [f for f in r["posiciones"] if f["cambio"] > 0]
    bajan = [f for f in r["posiciones"] if f["cambio"] < 0]
    if suben:
        f = max(suben, key=lambda x: x["cambio"])
        lineas.append(f"Lo que más ha sumado: {f['nombre']} ({_e(f['cambio'])}, {_p(f['pct'])}).")
    if bajan:
        f = min(bajan, key=lambda x: x["cambio"])
        lineas.append(f"Lo que más ha restado: {f['nombre']} ({_e(f['cambio'])}, {_p(f['pct'])}).")
    if abs(r["pct"]) >= 0.05:
        lineas.append("Ha sido una semana movida. Es normal en bolsa: revisa tus stop-loss, pero no tomes decisiones "
                      "en caliente.")
    for n in r["noticias"]:
        lineas.append(f"Noticia sobre lo que tienes: «{n['titulo']}».")
    return lineas


__all__ = ["resumen", "texto"]
