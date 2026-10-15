"""Aportación mensual: cuánto metes cada mes, qué día, y a dónde llevarlo para acercarte a tu reparto ideal.

Repartir el dinero nuevo hacia lo que va por debajo de su objetivo es la forma más barata de reequilibrar: no
vendes nada, así que no pagas impuestos ni comisiones de venta.
"""

from __future__ import annotations

import calendar
from datetime import date

from .activos import CLASE_A_REPARTO

MINIMO_POR_DESTINO = 50.0     # menos que esto en un destino no merece una orden aparte


def fecha_del_mes(dia: int, anio: int, mes: int) -> date:
    """El día elegido de ese mes (o el último si el mes es más corto), movido al lunes si cae en fin de semana."""
    d = date(anio, mes, min(dia, calendar.monthrange(anio, mes)[1]))
    while d.weekday() >= 5:
        d = date.fromordinal(d.toordinal() + 1)
    return d


def hecha_este_mes(cfg: dict, hoy: date | None = None) -> bool:
    hoy = hoy or date.today()
    return any(h["fecha"][:7] == hoy.isoformat()[:7] for h in cfg.get("hechas", []))


def pendiente(cfg: dict, hoy: date | None = None) -> bool:
    """¿Toca hacer la aportación (ya ha llegado el día de este mes y aún no está apuntada)?"""
    hoy = hoy or date.today()
    if not cfg or not cfg.get("importe"):
        return False
    return hoy >= fecha_del_mes(int(cfg.get("dia", 1)), hoy.year, hoy.month) and not hecha_este_mes(cfg, hoy)


def proxima(cfg: dict, hoy: date | None = None) -> date | None:
    hoy = hoy or date.today()
    if not cfg or not cfg.get("importe"):
        return None
    dia = int(cfg.get("dia", 1))
    este = fecha_del_mes(dia, hoy.year, hoy.month)
    if hoy <= este and not hecha_este_mes(cfg, hoy):
        return este
    if pendiente(cfg, hoy):
        return hoy
    anio, mes = (hoy.year + 1, 1) if hoy.month == 12 else (hoy.year, hoy.month + 1)
    return fecha_del_mes(dia, anio, mes)


def valores_por_destino(posiciones: list[dict], otros_ahorros: float = 0.0) -> dict[str, float]:
    """Euros que ya tienes en cada destino del reparto (acciones sueltas, fondo indexado, renta fija, monetario).
    `posiciones`: dicts con clase y valor (en euros). Oro, criptomonedas y demás no cuentan para el reparto."""
    salida: dict[str, float] = {}
    for p in posiciones:
        destino = CLASE_A_REPARTO.get(p["clase"])
        if destino:
            salida[destino] = salida.get(destino, 0.0) + p["valor"]
    if otros_ahorros > 0:
        clave = CLASE_A_REPARTO["Monetario y liquidez"]
        salida[clave] = salida.get(clave, 0.0) + otros_ahorros
    return salida


def repartir(importe: float, actuales: dict[str, float], objetivo_pct: dict[str, float],
             minimo: float = MINIMO_POR_DESTINO) -> dict[str, float]:
    """Reparte `importe` entre los destinos que van por debajo de su objetivo (en %), de más a menos lejos.
    Si todos están en su sitio, lo reparte según el objetivo. Nada por debajo de `minimo` euros."""
    objetivo = {k: v / 100 for k, v in objetivo_pct.items() if v > 0}
    if importe <= 0 or not objetivo:
        return {}
    total_despues = sum(actuales.get(k, 0.0) for k in objetivo) + importe
    falta = {k: max(w * total_despues - actuales.get(k, 0.0), 0.0) for k, w in objetivo.items()}
    suma_falta = sum(falta.values())
    if suma_falta <= 0:
        reparto = {k: importe * w for k, w in objetivo.items()}
    elif suma_falta >= importe:
        reparto = {k: importe * f / suma_falta for k, f in falta.items()}
    else:   # cubre todo lo que falta y el resto según el objetivo
        sobra = importe - suma_falta
        reparto = {k: falta[k] + sobra * w for k, w in objetivo.items()}
    # Juntar los trozos pequeños en el destino mayor (menos órdenes, menos líos).
    reparto = {k: v for k, v in reparto.items() if v > 0.005}
    pequenos = {k: v for k, v in reparto.items() if v < minimo}
    if pequenos and len(pequenos) < len(reparto):
        for k in pequenos:
            reparto.pop(k)
        mayor = max(reparto, key=reparto.get)
        reparto[mayor] += sum(pequenos.values())
    elif pequenos:      # todo es pequeño: todo al destino con más peso objetivo
        mayor = max(objetivo, key=objetivo.get)
        reparto = {mayor: importe}
    return {k: round(v, 2) for k, v in sorted(reparto.items(), key=lambda x: -x[1])}


def racha(cfg: dict, hoy: date | None = None) -> int:
    """Meses seguidos con aportación (contando hacia atrás desde este mes o el anterior)."""
    hoy = hoy or date.today()
    meses = {h["fecha"][:7] for h in cfg.get("hechas", [])}
    anio, mes = hoy.year, hoy.month
    if f"{anio:04d}-{mes:02d}" not in meses:
        anio, mes = (anio - 1, 12) if mes == 1 else (anio, mes - 1)
    n = 0
    while f"{anio:04d}-{mes:02d}" in meses:
        n += 1
        anio, mes = (anio - 1, 12) if mes == 1 else (anio, mes - 1)
    return n


__all__ = ["fecha_del_mes", "hecha_este_mes", "pendiente", "proxima", "valores_por_destino", "repartir", "racha",
           "MINIMO_POR_DESTINO"]
