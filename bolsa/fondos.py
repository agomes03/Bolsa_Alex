"""Qué hay de verdad dentro de tus fondos y ETF («look-through», como el Fund X-Ray de Snowball): sumando lo que
tienes directamente y lo que llevan tus fondos, cuánto de tu dinero está en cada empresa y en cada sector."""

from __future__ import annotations

SECTORES = {"technology": "Tecnología", "financial_services": "Banca y finanzas", "healthcare": "Salud",
            "consumer_cyclical": "Consumo cíclico", "consumer_defensive": "Consumo básico",
            "communication_services": "Telecomunicaciones y medios", "industrials": "Industria",
            "energy": "Energía", "utilities": "Eléctricas y agua", "realestate": "Inmobiliario",
            "basic_materials": "Materiales"}

def _clave_holding(simbolo: str, nombre: str, directas: dict[str, str]) -> str:
    """La clave con la que se junta una posición de un fondo con tus acciones: el mismo código; o, si el fondo la da
    sin bolsa (p. ej. «SAN»), la acción tuya con esa raíz y un nombre parecido (para no confundir Sanofi «SAN.PA»
    con Santander «SAN.MC»)."""
    s = simbolo.upper()
    if s in directas:
        return s
    if "." not in s:
        primera = (nombre or "").split()[0].lower() if nombre else ""
        for t, n in directas.items():
            if t.split(".")[0] == s and primera and primera in (n or "").lower():
                return t
    return s


def exposicion(directas: dict[str, float], fondos: dict[str, float], composiciones: dict[str, dict],
               nombres: dict[str, str], total: float | None = None) -> dict:
    """`directas`/`fondos`: euros en cada acción / en cada fondo; `total`: todo tu dinero invertido (si no, acciones
    más fondos). Devuelve:
    - empresas: [{nombre, directo, via_fondos, total, peso}] ordenadas por total (solo las 10 mayores de cada fondo
      son visibles: el resto del fondo queda como «resto, muy repartido»);
    - solapes: empresas que tienes directamente Y dentro de algún fondo;
    - sectores: {sector: euros} de la parte en fondos con datos;
    - cubierto: parte del dinero en fondos cuya composición se conoce."""
    total = total if total else sum(directas.values()) + sum(fondos.values())
    if total <= 0:
        return {"empresas": [], "solapes": [], "sectores": {}, "cubierto": 0.0}
    mias = {t.upper(): nombres.get(t, t) for t in directas}
    por = {}
    for t, v in directas.items():
        e = por.setdefault(t.upper(), {"nombre": nombres.get(t, t), "directo": 0.0, "via_fondos": 0.0, "fondos": []})
        e["directo"] += v
    sectores: dict[str, float] = {}
    con_datos = 0.0
    for f, v in fondos.items():
        comp = composiciones.get(f) or {}
        if comp.get("top"):
            con_datos += v
        for h in comp.get("top", []):
            e = por.setdefault(_clave_holding(h["simbolo"], h["nombre"], mias),
                               {"nombre": h["nombre"], "directo": 0.0, "via_fondos": 0.0, "fondos": []})
            e["via_fondos"] += v * h["peso"]
            e["fondos"].append(nombres.get(f, f))
        for s, w in (comp.get("sectores") or {}).items():
            sectores[SECTORES.get(s, s)] = sectores.get(SECTORES.get(s, s), 0.0) + v * w
    empresas = [{**e, "total": e["directo"] + e["via_fondos"], "peso": (e["directo"] + e["via_fondos"]) / total}
                for e in por.values()]
    empresas.sort(key=lambda e: -e["total"])
    solapes = [e for e in empresas if e["directo"] > 0 and e["via_fondos"] > 0]
    en_fondos = sum(fondos.values())
    return {"empresas": empresas, "solapes": solapes, "sectores": dict(sorted(sectores.items(), key=lambda x: -x[1])),
            "cubierto": con_datos / en_fondos if en_fondos > 0 else 0.0}


__all__ = ["SECTORES", "exposicion"]
