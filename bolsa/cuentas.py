"""Varias cuentas (por ejemplo, dos cuentas de valores en Bankinter, o una en Bankinter y otra en Trade Republic).

Cada cuenta guarda sus posiciones con su propio precio medio, sus stops y sus operaciones. La app mantiene además
una cartera «Todas» (`cartera_real`) que suma todas las cuentas: es la que usan el diagnóstico, los dividendos, la
Renta, los avisos y Telegram, porque el riesgo y los impuestos dependen de todo tu dinero junto.

En «Todas», una misma empresa comprada en dos cuentas aparece una sola vez: con la suma de títulos y el precio
medio ponderado. El detalle por cuenta se ve con `desglose`.
"""

from __future__ import annotations

import copy

PRINCIPAL = "Cuenta principal"
TODAS = "Todas"


def _vacia() -> dict:
    from .cartera import nueva

    return nueva(None)


def asegurar(d: dict) -> dict[str, dict]:
    """Pasa los datos antiguos (una sola cartera) al formato de cuentas. Devuelve las cuentas."""
    if "cuentas" not in d:
        d["cuentas"] = {PRINCIPAL: copy.deepcopy(d["cartera_real"]) if d.get("cartera_real") else _vacia()}
        consolidar(d)
    elif "cartera_real" not in d:
        consolidar(d)
    return d["cuentas"]


def consolidar(d: dict) -> dict:
    """Rehace la cartera «Todas» a partir de las cuentas."""
    cuentas = d.get("cuentas") or {}
    total = _vacia()
    fechas = [c.get("creada") for c in cuentas.values() if c.get("creada")]
    if fechas:
        total["creada"] = min(fechas)
    por_ticker: dict[str, list[tuple[str, dict]]] = {}
    for nombre, c in cuentas.items():
        for t, p in c.get("posiciones", {}).items():
            por_ticker.setdefault(t, []).append((nombre, p))
        total["historial"] += [{**h, "cuenta": nombre} for h in c.get("historial", [])]
    total["historial"].sort(key=lambda h: h.get("fecha", ""))
    for t, lista in por_ticker.items():
        posiciones = [p for _, p in lista]
        acciones = sum(p["acciones"] for p in posiciones)
        if acciones <= 0:
            continue
        coste_local = sum(p["acciones"] * p["precio_medio"] for p in posiciones)
        coste_eur = sum(p["acciones"] * p["precio_medio"] * p.get("fx_medio", 1.0) for p in posiciones)
        stops = [p.get("stop") for p in posiciones]
        alarmas = [p["alarma"] for p in posiciones if p.get("alarma")]
        primera = posiciones[0]
        total["posiciones"][t] = {
            **{k: v for k, v in primera.items() if k in ("nombre", "clase", "nota", "objetivo")},
            "acciones": acciones,
            "precio_medio": coste_local / acciones,
            "fx_medio": coste_eur / coste_local if coste_local else 1.0,
            "gastos": sum(p.get("gastos", 0.0) for p in posiciones),
            "fecha": min(p.get("fecha", "9999") for p in posiciones),
            "desde": min(p.get("desde", p.get("fecha", "9999")) for p in posiciones),
            # Con stop solo si TODAS las cuentas lo tienen; el más alto es el primero que saltaría.
            "stop": max(stops) if all(stops) else None,
            "sin_stop": any(p.get("sin_stop") for p in posiciones),
            "alarma": max(alarmas) if alarmas else None,
            "cuentas": [n for n, _ in lista],
        }
    d["cartera_real"] = total
    return total


def desglose(d: dict, ticker: str) -> list[dict]:
    """Lo que tienes de un valor en cada cuenta."""
    return [{"cuenta": n, "acciones": c["posiciones"][ticker]["acciones"],
             "precio_medio": c["posiciones"][ticker]["precio_medio"], "stop": c["posiciones"][ticker].get("stop")}
            for n, c in (d.get("cuentas") or {}).items() if ticker in c.get("posiciones", {})]


def nueva_cuenta(d: dict, nombre: str) -> str | None:
    nombre = nombre.strip()
    cuentas = asegurar(d)
    if not nombre:
        return "Ponle un nombre a la cuenta (por ejemplo, «Bankinter 2» o «Cuenta de mi pareja»)."
    if nombre in cuentas or nombre == TODAS:
        return f"Ya hay una cuenta llamada «{nombre}»."
    cuentas[nombre] = _vacia()
    return None


def renombrar(d: dict, viejo: str, nuevo: str) -> str | None:
    nuevo = nuevo.strip()
    cuentas = asegurar(d)
    if viejo not in cuentas:
        return "Esa cuenta no existe."
    if not nuevo or nuevo == TODAS or (nuevo in cuentas and nuevo != viejo):
        return "Elige otro nombre."
    d["cuentas"] = {(nuevo if n == viejo else n): c for n, c in cuentas.items()}
    consolidar(d)
    return None


def borrar(d: dict, nombre: str) -> str | None:
    cuentas = asegurar(d)
    if nombre not in cuentas:
        return "Esa cuenta no existe."
    if len(cuentas) == 1:
        return "Necesitas al menos una cuenta."
    del cuentas[nombre]
    consolidar(d)
    return None


__all__ = ["PRINCIPAL", "TODAS", "asegurar", "consolidar", "desglose", "nueva_cuenta", "renombrar", "borrar"]
