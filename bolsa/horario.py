"""Horario de cada bolsa para saber si el mercado está abierto (como en el bróker).

No incluye los festivos de cada bolsa: esos días la app dirá «abierto» pero no habrá cotizaciones nuevas.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

MADRID = ZoneInfo("Europe/Madrid")

# (zona horaria de la bolsa, apertura, cierre) en hora local de esa bolsa.
SESIONES = {
    "EEUU": (ZoneInfo("America/New_York"), time(9, 30), time(16, 0)),
    ".L": (ZoneInfo("Europe/London"), time(8, 0), time(16, 30)),
    "EUROPA": (MADRID, time(9, 0), time(17, 30)),
    ".T": (ZoneInfo("Asia/Tokyo"), time(9, 0), time(15, 30)),
    ".HK": (ZoneInfo("Asia/Hong_Kong"), time(9, 30), time(16, 0)),
    ".KS": (ZoneInfo("Asia/Seoul"), time(9, 0), time(15, 30)),
    ".TW": (ZoneInfo("Asia/Taipei"), time(9, 0), time(13, 30)),
    ".NS": (ZoneInfo("Asia/Kolkata"), time(9, 15), time(15, 30)),
    ".SS": (ZoneInfo("Asia/Shanghai"), time(9, 30), time(15, 0)),
}
SUFIJOS_EUROPA = (".MC", ".DE", ".PA", ".AS", ".MI", ".BR", ".HE", ".LS", ".SW", ".CO", ".ST", ".OL")
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def sesion(ticker: str):
    for sufijo in (".L", ".T", ".HK", ".KS", ".TW", ".NS", ".SS"):
        if ticker.endswith(sufijo):
            return SESIONES[sufijo]
    if ticker.endswith(SUFIJOS_EUROPA) or ticker.startswith("^"):
        return SESIONES["EUROPA"]
    return SESIONES["EEUU"]


def estado_mercado(ticker: str, ahora: datetime | None = None) -> dict:
    """{'abierto': bool, 'texto': '...', 'apertura': datetime en hora de Madrid de la próxima apertura}."""
    ahora = ahora or datetime.now(timezone.utc)
    if ahora.tzinfo is None:
        ahora = ahora.replace(tzinfo=timezone.utc)
    from .activos import es_cripto

    if es_cripto(ticker):
        return {"abierto": True, "texto": "Las criptomonedas cotizan las 24 horas, todos los días",
                "apertura": ahora.astimezone(MADRID)}
    if ticker.endswith(("=X", "=F")) or ticker == "DX-Y.NYB":
        madrid = ahora.astimezone(MADRID)
        # De domingo 23:00 a viernes 23:00 (hora peninsular), aproximadamente.
        abierto = (madrid.weekday() < 4 or (madrid.weekday() == 4 and madrid.hour < 23)
                   or (madrid.weekday() == 6 and madrid.hour >= 23))
        que = "Las divisas" if ticker.endswith("=X") else "Los futuros de materias primas"
        return {"abierto": abierto, "texto": f"{que} cotizan casi 24 horas de lunes a viernes"
                + ("" if abierto else ": ahora está cerrado (abre el domingo a las 23:00)"), "apertura": madrid}
    if ticker.startswith("0P"):
        return {"abierto": ahora.astimezone(MADRID).weekday() < 5,
                "texto": "Los fondos se compran y venden al valor liquidativo, que se calcula una vez al día",
                "apertura": ahora.astimezone(MADRID)}
    zona, abre, cierra = sesion(ticker)
    local = ahora.astimezone(zona)
    hoy_abre = local.replace(hour=abre.hour, minute=abre.minute, second=0, microsecond=0)
    hoy_cierra = local.replace(hour=cierra.hour, minute=cierra.minute, second=0, microsecond=0)
    if local.weekday() < 5 and hoy_abre <= local < hoy_cierra:
        cierre_madrid = hoy_cierra.astimezone(MADRID)
        return {"abierto": True, "texto": f"Mercado abierto (cierra a las {cierre_madrid:%H:%M}, hora peninsular)",
                "apertura": hoy_abre.astimezone(MADRID)}
    siguiente = hoy_abre if local < hoy_abre else hoy_abre + timedelta(days=1)
    while siguiente.weekday() >= 5:
        siguiente += timedelta(days=1)
    s = siguiente.astimezone(MADRID)
    cuando = "hoy" if s.date() == ahora.astimezone(MADRID).date() else \
        "mañana" if s.date() == ahora.astimezone(MADRID).date() + timedelta(days=1) else f"el {DIAS[s.weekday()]}"
    return {"abierto": False, "texto": f"Mercado cerrado: abre {cuando} a las {s:%H:%M} (hora peninsular)",
            "apertura": s}


def ahora_madrid() -> datetime:
    """Fecha y hora actual en Madrid, sin zona (como el índice de las cotizaciones)."""
    return datetime.now(MADRID).replace(tzinfo=None, second=0, microsecond=0)


__all__ = ["estado_mercado", "sesion", "ahora_madrid", "MADRID"]
