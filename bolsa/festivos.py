"""Festivos de las bolsas (días sin mercado aunque sean laborables).

Calendarios de la Bolsa española, Xetra, Euronext, Londres, SIX (Suiza) y Nueva York, con los festivos que
dependen de la Semana Santa calculados para cualquier año. Las bolsas asiáticas y nórdicas no se incluyen (sus
calendarios cambian mucho de un año a otro): esos días la app puede decir «abierto» aunque no lo esté.
"""

from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache


def pascua(anio: int) -> date:
    """Domingo de Pascua (algoritmo gregoriano anónimo)."""
    a, b, c = anio % 19, anio // 100, anio % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    mes = (h + l_ - 7 * m + 114) // 31
    dia = ((h + l_ - 7 * m + 114) % 31) + 1
    return date(anio, mes, dia)


def _n_dia_semana(anio: int, mes: int, dia_semana: int, n: int) -> date:
    """n-ésimo día de la semana del mes (n=-1: el último). dia_semana: 0 = lunes."""
    if n > 0:
        d = date(anio, mes, 1)
        d += timedelta(days=(dia_semana - d.weekday()) % 7)
        return d + timedelta(weeks=n - 1)
    d = date(anio + (mes == 12), mes % 12 + 1, 1) - timedelta(days=1)
    return d - timedelta(days=(d.weekday() - dia_semana) % 7)


def _observado_eeuu(d: date) -> date:
    return d - timedelta(days=1) if d.weekday() == 5 else d + timedelta(days=1) if d.weekday() == 6 else d


def _observado_uk(d: date) -> date:
    return d + timedelta(days=(7 - d.weekday())) if d.weekday() >= 5 else d


@lru_cache(maxsize=64)
def calendario(mercado: str, anio: int) -> dict[date, str]:
    p = pascua(anio)
    viernes_santo, lunes_pascua = p - timedelta(days=2), p + timedelta(days=1)
    comunes = {date(anio, 1, 1): "Año Nuevo", viernes_santo: "Viernes Santo", lunes_pascua: "Lunes de Pascua",
               date(anio, 5, 1): "Día del Trabajo", date(anio, 12, 25): "Navidad", date(anio, 12, 26): "San Esteban"}
    if mercado in ("ES", "DE"):
        return {**comunes, date(anio, 12, 24): "Nochebuena", date(anio, 12, 31): "Nochevieja"}
    if mercado == "EURONEXT":
        return comunes
    if mercado == "CH":
        return {**comunes, date(anio, 1, 2): "San Bertoldo", p + timedelta(days=39): "Ascensión",
                p + timedelta(days=50): "Lunes de Pentecostés", date(anio, 8, 1): "Fiesta nacional suiza",
                date(anio, 12, 24): "Nochebuena", date(anio, 12, 31): "Nochevieja"}
    if mercado == "UK":
        navidad = _observado_uk(date(anio, 12, 25))
        san_esteban = navidad + timedelta(days=1) if navidad.weekday() < 4 else _observado_uk(navidad + timedelta(days=1))
        return {_observado_uk(date(anio, 1, 1)): "Año Nuevo", viernes_santo: "Viernes Santo",
                lunes_pascua: "Lunes de Pascua", _n_dia_semana(anio, 5, 0, 1): "Festivo de mayo",
                _n_dia_semana(anio, 5, 0, -1): "Festivo de primavera", _n_dia_semana(anio, 8, 0, -1): "Festivo de verano",
                navidad: "Navidad", san_esteban: "San Esteban"}
    if mercado == "US":
        salida = {_n_dia_semana(anio, 1, 0, 3): "Martin Luther King", _n_dia_semana(anio, 2, 0, 3): "Día del Presidente",
                  viernes_santo: "Viernes Santo", _n_dia_semana(anio, 5, 0, -1): "Memorial Day",
                  _observado_eeuu(date(anio, 6, 19)): "Juneteenth", _observado_eeuu(date(anio, 7, 4)): "Independencia",
                  _n_dia_semana(anio, 9, 0, 1): "Día del Trabajo", _n_dia_semana(anio, 11, 3, 4): "Acción de Gracias",
                  _observado_eeuu(date(anio, 12, 25)): "Navidad"}
        if date(anio, 1, 1).weekday() != 5:        # si cae en sábado no se traslada al viernes anterior
            salida[_observado_eeuu(date(anio, 1, 1))] = "Año Nuevo"
        return salida
    return {}


def mercado_de(ticker: str) -> str | None:
    if ticker.endswith(".MC"):
        return "ES"
    if ticker.endswith((".DE", ".F", ".HE", ".CO", ".ST", ".OL")) or ticker.startswith("0P"):
        return "DE"
    if ticker.endswith((".PA", ".AS", ".BR", ".LS", ".MI")):
        return "EURONEXT"
    if ticker.endswith(".SW"):
        return "CH"
    if ticker.endswith(".L"):
        return "UK"
    if "." not in ticker and not ticker.startswith("^") and "=" not in ticker and "-" not in ticker:
        return "US"
    if ticker in ("^GSPC", "^NDX", "^IXIC", "^DJI", "^RUT", "^VIX", "^TNX", "^TYX", "^FVX", "^IRX"):
        return "US"
    if ticker == "^FTSE":
        return "UK"
    if ticker in ("^GDAXI", "^STOXX50E"):
        return "DE"
    if ticker in ("^FCHI", "^AEX"):
        return "EURONEXT"
    if ticker == "^SSMI":
        return "CH"
    if ticker in ("^IBEX",):
        return "ES"
    return None


def festivo(ticker: str, dia: date) -> str | None:
    """Nombre del festivo si ese día no hay mercado para ese valor; None si es día de mercado (o no se sabe)."""
    m = mercado_de(ticker)
    return calendario(m, dia.year).get(dia) if m else None


__all__ = ["pascua", "calendario", "festivo", "mercado_de"]
