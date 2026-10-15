"""Finnhub (opcional y gratis para uso personal): noticias al momento y precios de EEUU en tiempo real.

Se activa poniendo la clave en Streamlit → Settings → Secrets:

    [finnhub]
    api_key = "..."

Sin clave, la app funciona igual que siempre (Yahoo Finance y RSS). El plan gratuito da precios en tiempo real
de la bolsa de EEUU y noticias de mercado y de empresas norteamericanas; las acciones españolas siguen con el
retraso de ~15 minutos de Yahoo.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

URL = "https://finnhub.io/api/v1"
MADRID = ZoneInfo("Europe/Madrid")


class ClaveNoValida(Exception):
    pass


def _get(ruta: str, clave: str, **params):
    import requests

    r = requests.get(f"{URL}{ruta}", params={**params, "token": clave}, timeout=10)
    if r.status_code in (401, 403):
        raise ClaveNoValida(r.text[:200])
    if r.status_code != 200:
        return None
    return r.json()


def es_eeuu(ticker: str) -> bool:
    """Acciones y ETF de EEUU: en Yahoo no llevan sufijo de bolsa (AAPL, MSFT, SPY)."""
    return bool(ticker) and "." not in ticker and not ticker.startswith("^") and "=" not in ticker \
        and "-" not in ticker


def cotizacion(ticker: str, clave: str) -> dict | None:
    """Precio en tiempo real (solo EEUU en el plan gratuito), con las mismas claves que datos.cotizacion."""
    if not es_eeuu(ticker):
        return None
    j = _get("/quote", clave, symbol=ticker)
    if not j or not j.get("c"):
        return None
    hora = datetime.fromtimestamp(j["t"], tz=timezone.utc).astimezone(MADRID).replace(tzinfo=None) \
        if j.get("t") else None
    return {"precio": float(j["c"]), "variacion": j.get("d"), "variacion_pct": j.get("dp"),
            "maximo": j.get("h") or None, "minimo": j.get("l") or None, "apertura": j.get("o") or None,
            "anterior": j.get("pc") or None, "hora": hora, "tiempo_real": True}


def _a_noticias(items, fuente: str = "Finnhub") -> list[dict]:
    salida = []
    for n in items or []:
        if not n.get("headline") or not n.get("datetime"):
            continue
        salida.append({"titulo": n["headline"].strip(), "enlace": n.get("url", ""),
                       "fuente": f"{fuente} · {n['source']}" if n.get("source") else fuente,
                       "fecha": datetime.fromtimestamp(n["datetime"], tz=timezone.utc),
                       "resumen": (n.get("summary") or "")[:400]})
    return salida


def noticias_mercado(clave: str, categoria: str = "general") -> list[dict]:
    """Últimas noticias de mercado (en inglés), al momento."""
    return _a_noticias(_get("/news", clave, category=categoria))


def noticias_empresa(ticker: str, clave: str, dias: int = 7, hoy: date | None = None) -> list[dict]:
    """Noticias de una empresa de EEUU de los últimos días (el plan gratuito solo cubre Norteamérica)."""
    if not es_eeuu(ticker):
        return []
    hoy = hoy or date.today()
    return _a_noticias(_get("/company-news", clave, symbol=ticker, **{"from": (hoy - timedelta(days=dias)).isoformat(),
                                                                      "to": hoy.isoformat()}))


def comprobar(clave: str) -> tuple[bool, str]:
    """¿Funciona la clave? (ok, mensaje para la barra lateral)."""
    try:
        q = cotizacion("AAPL", clave)
    except ClaveNoValida:
        return False, "La clave de Finnhub no es válida: revísala en Settings → Secrets."
    except Exception as e:  # noqa: BLE001 - sin conexión, se intenta más tarde
        return False, f"No se ha podido conectar con Finnhub ({type(e).__name__})."
    if not q:
        return False, "Finnhub no ha devuelto datos ahora mismo."
    return True, "Finnhub conectado: noticias al momento y precios de EEUU en tiempo real."


__all__ = ["es_eeuu", "cotizacion", "noticias_mercado", "noticias_empresa", "comprobar", "ClaveNoValida"]
