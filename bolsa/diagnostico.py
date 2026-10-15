"""Diagnóstico de una cartera real, como lo haría un asesor: concentración, sectores, países, encaje con tu
perfil y una propuesta concreta de reequilibrio con sus costes e impuestos.

Las reglas son las de la gestión prudente que comparten casi todos los manuales y supervisores:
- Ninguna empresa debería pesar más del 20 % de lo que tienes invertido (una mala noticia no te hunde).
- Ningún sector más del 40 % (bancos, eléctricas... suelen caer juntos).
- Con menos de ~5 empresas "efectivas" el riesgo de una sola empresa domina tu resultado.
- Lo que no sean acciones sueltas, en fondos indexados (miles de empresas de todo el mundo).

No es asesoramiento financiero regulado: es un análisis educativo con tus datos.
"""

from __future__ import annotations

import math

from . import asesor, costes
from .activos import CLASE_A_REPARTO, LIMITES_ALTERNATIVOS, clase_de
from .tickers import nombre_de, sector_de

MAX_EMPRESA = 0.20
MAX_SECTOR = 0.40
MIN_EMPRESAS_EFECTIVAS = 5

PAIS_POR_SUFIJO = {".MC": "España", ".DE": "Alemania", ".PA": "Francia", ".AS": "Países Bajos", ".MI": "Italia",
                   ".BR": "Bélgica", ".HE": "Finlandia", ".L": "Reino Unido", ".SW": "Suiza", ".LS": "Portugal"}

GRAVEDAD_ORDEN = {"alta": 0, "media": 1, "baja": 2, "ok": 3}


def pais_de(ticker: str) -> str:
    for sufijo, pais in PAIS_POR_SUFIJO.items():
        if ticker.endswith(sufijo):
            return pais
    return "EEUU"


def _valor(p: dict) -> float:
    return p["acciones"] * p["precio"] * p.get("fx", 1.0)


def _coste(p: dict) -> float:
    return p["acciones"] * p["precio_medio"] * p.get("fx_medio", p.get("fx", 1.0))


def _nombre(p: dict) -> str:
    n = nombre_de(p["ticker"])
    return p.get("nombre") or n if n == p["ticker"] else n


def destino_por_perfil(perfil: str | None) -> dict[str, float]:
    """Cómo repartir el dinero que sale de acciones sueltas, según el reparto del perfil (sin acciones sueltas)."""
    reparto = asesor.REPARTOS.get(perfil or "", {"Fondo indexado mundial": 100})
    resto = {k: v for k, v in reparto.items() if k != "Acciones individuales" and v > 0}
    total = sum(resto.values())
    return {k: v / total for k, v in resto.items()}


def diagnosticar(posiciones: list[dict], otros_ahorros: float = 0.0, perfil: str | None = None,
                 tarifa: costes.Tarifa | None = None, filas_informe: dict[str, dict] | None = None,
                 max_empresa: float = MAX_EMPRESA, max_sector: float = MAX_SECTOR) -> dict:
    """`posiciones`: dicts con ticker, acciones, precio_medio y precio (en la divisa del valor), fx y fx_medio
    (euros por unidad de esa divisa) y, opcionalmente, stop. `otros_ahorros`: dinero fuera de estas acciones
    (cuentas, depósitos, fondos) en euros. `filas_informe`: filas del informe diario por ticker."""
    tarifa = tarifa or costes.Tarifa()
    filas_informe = filas_informe or {}
    pos = [dict(p, clase=p.get("clase") or clase_de(p["ticker"])) for p in posiciones
           if p.get("precio") and p.get("acciones", 0) > 0]
    total_invertido = sum(_valor(p) for p in pos)
    if total_invertido <= 0:
        return {"total_acciones": 0.0, "hallazgos": [], "propuesta": [], "semaforo": "sin_datos"}
    patrimonio = total_invertido + max(otros_ahorros, 0.0)

    empresas = sorted(({"ticker": p["ticker"], "nombre": _nombre(p), "valor": _valor(p), "clase": p["clase"],
                        "peso": _valor(p) / patrimonio,
                        "ganancia": _valor(p) - _coste(p), "ganancia_pct": _valor(p) / _coste(p) - 1 if _coste(p) else 0,
                        "sector": sector_de(p["ticker"]) if p["clase"] == "Acciones" else p["clase"],
                        "pais": pais_de(p["ticker"]) if p["clase"] == "Acciones" else "Global"} for p in pos),
                      key=lambda e: -e["valor"])
    acciones = [e for e in empresas if e["clase"] == "Acciones"]
    total_acciones = sum(e["valor"] for e in acciones)
    clases = {}
    for e in empresas:
        clases[e["clase"]] = clases.get(e["clase"], 0.0) + e["peso"]
    if otros_ahorros > 0:
        clases["Monetario y liquidez"] = clases.get("Monetario y liquidez", 0.0) + otros_ahorros / patrimonio
    sectores, paises = {}, {}
    for e in acciones:
        sectores[e["sector"]] = sectores.get(e["sector"], 0.0) + e["peso"]
        paises[e["pais"]] = paises.get(e["pais"], 0.0) + e["peso"]
    n_efectivo = 1 / sum((e["valor"] / total_acciones) ** 2 for e in acciones) if acciones else 0.0
    peso_acciones = total_acciones / patrimonio

    hallazgos = []

    def h(gravedad, titulo, texto):
        hallazgos.append({"gravedad": gravedad, "titulo": titulo, "texto": texto})

    # 1. Concentración por empresa (los fondos y ETF ya están diversificados por dentro)
    grandes = [e for e in acciones if e["peso"] > max_empresa]
    for e in grandes:
        h("alta" if e["peso"] > 0.35 else "media", f"{e['nombre']} pesa el {e['peso'] * 100:.0f} % de tu dinero",
          f"Lo prudente es que ninguna empresa pase del {max_empresa * 100:.0f} %. Si {e['nombre']} cayera un 40 % "
          f"(les ha pasado a grandes empresas en una sola mala noticia), perderías unos "
          f"{_eur(e['valor'] * 0.4)}, el {e['peso'] * 40:.0f} % de todo lo que tienes aquí.")
    if acciones and not grandes:
        h("ok", "Ninguna empresa pesa demasiado", f"Todas están por debajo del {max_empresa * 100:.0f} %.")

    # 2. Sectores
    grandes_t = {e["ticker"] for e in grandes}
    for s, w in sorted(sectores.items(), key=lambda x: -x[1]):
        del_sector = [e["ticker"] for e in acciones if e["sector"] == s]
        if len(del_sector) == 1 and del_sector[0] in grandes_t:
            continue  # ya avisado: es una sola empresa
        if w > max_sector and s != "—":
            h("alta" if w > 0.6 else "media", f"El sector {s} es el {w * 100:.0f} % de tu dinero",
              "Las empresas de un mismo sector suelen caer a la vez (por ejemplo, los bancos cuando bajan los tipos "
              f"de interés). Lo prudente es no pasar del {max_sector * 100:.0f} % en un sector.")

    # 3. Número de empresas (solo importa si las acciones sueltas son una parte grande de tu dinero)
    if acciones and n_efectivo < MIN_EMPRESAS_EFECTIVAS and peso_acciones > 0.3:
        ne = f"{n_efectivo:.1f}".replace(".", ",")
        h("media", f"Tus acciones equivalen a {ne} empresas",
          "Contando cuánto pesa cada una, tu riesgo es el de tener solo "
          f"{ne} empresas a partes iguales. Con menos de {MIN_EMPRESAS_EFECTIVAS}, lo que le pase a una sola "
          "empresa decide tu resultado. Un fondo indexado mundial reparte tu dinero entre más de 1.000 empresas.")

    # 4. Países
    if paises:
        pais_max, w_pais = max(paises.items(), key=lambda x: x[1])
        if w_pais > 0.7 and peso_acciones > 0.3:
            h("media", f"El {w_pais * 100:.0f} % de tu dinero depende de la bolsa de {pais_max}",
              f"Si a la economía de {pais_max} le va mal unos años, todo tu dinero lo nota. La bolsa de un solo país "
              "es una parte pequeña de la bolsa mundial; un fondo indexado mundial te reparte entre decenas de países.")

    # 5. Reparto por tipo de activo frente al perfil
    perfil_ref = perfil if perfil in asesor.REPARTOS else None
    if perfil_ref:
        reparto = asesor.REPARTOS[perfil_ref]
        desvios = []
        for clase, parte in CLASE_A_REPARTO.items():
            actual, objetivo = clases.get(clase, 0.0), reparto[parte] / 100
            if abs(actual - objetivo) > 0.10:
                desvios.append((clase, actual, objetivo))
        if desvios:
            peor = max(abs(a - o) for _, a, o in desvios)
            h("alta" if peor > 0.40 else "media", f"Tu reparto se aleja del de un perfil {perfil_ref.lower()}",
              "; ".join(f"{c}: tienes {a * 100:.0f} % (guía {o * 100:.0f} %)" for c, a, o in desvios)
              + ". Puedes acercarte poco a poco con tus aportaciones nuevas, sin vender de golpe.")
        else:
            h("ok", f"Tu reparto encaja con un perfil {perfil_ref.lower()}",
              "Acciones, fondos, renta fija y liquidez están cerca de la guía de 🎯 Mi plan.")
    limites = LIMITES_ALTERNATIVOS[perfil_ref or "Moderado"]
    for clase, limite in limites.items():
        w = clases.get(clase, 0.0)
        if w > limite + 0.01:
            que = ("Las criptomonedas han caído más de un 70 % varias veces y no generan rentas: si lo pierdes todo, "
                   "no debería cambiarte la vida." if clase == "Criptomonedas" else
                   "El oro protege en algunas crisis, pero no da intereses ni dividendos y puede pasar años sin subir.")
            h("alta" if w > limite * 2 + 0.05 else "media", f"{clase}: {w * 100:.0f} % de tu dinero",
              f"Para un perfil {(perfil_ref or 'moderado').lower()}, lo prudente es no pasar del {limite * 100:.0f} %. "
              + que)

    # 6. Stop-loss
    sin_stop = [_nombre(p) for p in pos if not p.get("stop") and p["clase"] == "Acciones"]
    if sin_stop:
        h("media", f"Sin stop-loss registrado: {', '.join(sin_stop)}",
          "Un stop-loss vende automáticamente si el precio cae hasta el nivel que eliges y evita que una caída "
          "fuerte se convierta en una pérdida enorme. Más abajo tienes la orden lista para cada posición. Si ya lo "
          "tienes puesto en tu bróker, apúntalo en la posición para que la app lo vigile.")

    # 7. Lo que dice el informe del día de cada empresa
    for p in pos:
        f = filas_informe.get(p["ticker"])
        if not f:
            continue
        etiqueta, color, _ = asesor.veredicto(f)
        nombre = _nombre(p)
        if f.get("riesgo_nivel") == "alto":
            h("media", f"{nombre}: riesgo de caída alto",
              "El modelo de riesgo la sitúa entre las que más a menudo han caído más de un 10 % en un mes. Asegúrate "
              "de tener el stop-loss puesto y no aumentes la posición.")
        elif color in ("red", "orange"):
            h("media", f"{nombre}: veredicto de hoy «{etiqueta}»",
              "No es una orden de vender, pero no es momento de comprar más. Revisa su stop-loss.")
        if f.get("resultados_pronto"):
            h("baja", f"{nombre} presenta resultados en los próximos días",
              "El precio puede moverse con fuerza ese día (en los dos sentidos).")
    favorables = [p for p in pos
                  if p["ticker"] in filas_informe and asesor.veredicto(filas_informe[p["ticker"]])[1] == "green"]
    acc = [p for p in pos if p["clase"] == "Acciones"]
    if acc and len(favorables) == len(acc):
        h("ok", "Todas tus empresas tienen hoy un veredicto favorable",
          "Tendencia y nota acompañan. Eso no quita el riesgo de tener mucho dinero en pocas empresas.")

    # 8. En pérdidas
    perdedoras = [e for e in empresas if e["ganancia"] < 0]
    if perdedoras:
        h("baja", "Posiciones en pérdidas: no es motivo para vender ni para aguantar",
          "Lo que importa es si la comprarías hoy. Si vendes alguna para diversificar, la pérdida reduce los "
          "impuestos de tus ganancias del año (regla de los 2 meses: no la recompres antes de 2 meses o Hacienda "
          "no te deja usar esa pérdida todavía).")

    propuesta = proponer_reequilibrio(pos, patrimonio, tarifa, perfil, max_empresa)
    hallazgos.sort(key=lambda x: GRAVEDAD_ORDEN[x["gravedad"]])
    gravedades = {x["gravedad"] for x in hallazgos}
    semaforo = "rojo" if "alta" in gravedades else "ambar" if "media" in gravedades else "verde"
    return {"total_acciones": total_acciones, "patrimonio": patrimonio, "peso_acciones": peso_acciones,
            "empresas": empresas, "sectores": sectores, "paises": paises, "n_efectivo": n_efectivo, "clases": clases,
            "hallazgos": hallazgos, "semaforo": semaforo, **propuesta}


def proponer_reequilibrio(pos: list[dict], patrimonio: float, tarifa: costes.Tarifa, perfil: str | None,
                          max_empresa: float = MAX_EMPRESA) -> dict:
    """Ventas para que ninguna empresa supere `max_empresa`, con su coste e impuestos aproximados, y a dónde
    llevar ese dinero. Las pérdidas de una venta compensan las ganancias de otra (como en el IRPF)."""
    ventas = []
    for p in pos:
        if p.get("clase", "Acciones") != "Acciones":
            continue
        precio_eur = p["precio"] * p.get("fx", 1.0)
        exceso = _valor(p) - max_empresa * patrimonio
        if exceso <= 0:
            continue
        n = min(p["acciones"], math.ceil(exceso / precio_eur))
        importe = n * precio_eur
        coste_venta = tarifa.coste(importe, p["ticker"])
        coste_compra = n * p["precio_medio"] * p.get("fx_medio", p.get("fx", 1.0))
        ventas.append({"ticker": p["ticker"], "nombre": _nombre(p), "acciones": n,
                       "precio": p["precio"], "importe": importe, "coste": coste_venta,
                       "ganancia": importe - coste_venta - coste_compra,
                       "queda_peso": (_valor(p) - importe) / patrimonio})
    neto = sum(v["ganancia"] for v in ventas)
    liberado = sum(v["importe"] - v["coste"] for v in ventas)
    destino = {k: liberado * w for k, w in destino_por_perfil(perfil).items()} if liberado > 0 else {}
    # Pesos en euros antes y después (para comparar riesgos con la historia real). Los destinos usan como
    # referencia los productos de `asesor.PRODUCTOS`.
    antes = {p["ticker"]: _valor(p) for p in pos}
    despues = dict(antes)
    for v in ventas:
        despues[v["ticker"]] -= v["importe"]
    for k, importe in destino.items():
        ref = asesor.PRODUCTOS[k]["ticker"]
        despues[ref] = despues.get(ref, 0.0) + importe
    return {"propuesta": ventas, "ganancia_realizada": neto, "impuesto": costes.impuesto_ganancia(neto),
            "costes_venta": sum(v["coste"] for v in ventas), "liberado": liberado, "destino": destino,
            "pesos_antes": antes, "pesos_despues": {t: v for t, v in despues.items() if v > 0}}


def _eur(x: float) -> str:
    return f"{x:,.0f} €".replace(",", ".")


__all__ = ["diagnosticar", "proponer_reequilibrio", "destino_por_perfil", "pais_de", "MAX_EMPRESA", "MAX_SECTOR"]
