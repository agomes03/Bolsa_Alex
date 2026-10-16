"""Qué hay de verdad dentro de tus fondos y ETF («look-through», como el Fund X-Ray de Snowball): sumando lo que
tienes directamente y lo que llevan tus fondos, cuánto de tu dinero está en cada empresa y en cada sector."""

from __future__ import annotations

SECTORES = {"technology": "Tecnología", "financial_services": "Banca y finanzas", "healthcare": "Salud",
            "consumer_cyclical": "Consumo cíclico", "consumer_defensive": "Consumo básico",
            "communication_services": "Telecomunicaciones y medios", "industrials": "Industria",
            "energy": "Energía", "utilities": "Eléctricas y agua", "realestate": "Inmobiliario",
            "basic_materials": "Materiales"}

# Las mismas empresas con otro código en Yahoo según la bolsa (para detectar que ya las tienes).
_RAIZ = lambda s: s.split(".")[0].upper()  # noqa: E731


def exposicion(directas: dict[str, float], fondos: dict[str, float], composiciones: dict[str, dict],
               nombres: dict[str, str]) -> dict:
    """`directas`/`fondos`: euros en cada acción / en cada fondo. Devuelve:
    - empresas: [{nombre, directo, via_fondos, total, peso}] ordenadas por total (solo las 10 mayores de cada fondo
      son visibles: el resto del fondo queda como «resto, muy repartido»);
    - solapes: empresas que tienes directamente Y dentro de algún fondo;
    - sectores: {sector: euros} de la parte en fondos con datos;
    - cubierto: parte del dinero en fondos cuya composición se conoce."""
    total = sum(directas.values()) + sum(fondos.values())
    if total <= 0:
        return {"empresas": [], "solapes": [], "sectores": {}, "cubierto": 0.0}
    por = {}
    for t, v in directas.items():
        e = por.setdefault(_RAIZ(t), {"nombre": nombres.get(t, t), "directo": 0.0, "via_fondos": 0.0, "fondos": []})
        e["directo"] += v
    sectores: dict[str, float] = {}
    con_datos = 0.0
    for f, v in fondos.items():
        comp = composiciones.get(f) or {}
        if comp.get("top"):
            con_datos += v
        for h in comp.get("top", []):
            e = por.setdefault(_RAIZ(h["simbolo"]), {"nombre": h["nombre"], "directo": 0.0, "via_fondos": 0.0,
                                                    "fondos": []})
            e["via_fondos"] += v * h["peso"]
            e["fondos"].append(nombres.get(f, f))
        for s, w in (comp.get("sectores") or {}).items():
            sectores[SECTORES.get(s, s)] = sectores.get(SECTORES.get(s, s), 0.0) + v * w
    empresas = [{**e, "total": e["directo"] + e["via_fondos"], "peso": (e["directo"] + e["via_fondos"]) / total}
                for e in por.values()]
    empresas.sort(key=lambda e: -e["total"])
    solapes = [e for e in empresas if e["directo"] > 0 and e["via_fondos"] > 0]
    return {"empresas": empresas, "solapes": solapes, "sectores": dict(sorted(sectores.items(), key=lambda x: -x[1])),
            "cubierto": con_datos / sum(fondos.values()) if fondos else 0.0}


__all__ = ["SECTORES", "exposicion"]
