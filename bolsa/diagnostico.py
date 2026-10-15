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
    pos = [p for p in posiciones if p.get("precio") and p.get("acciones", 0) > 0]
    total_acciones = sum(_valor(p) for p in pos)
    if total_acciones <= 0:
        return {"total_acciones": 0.0, "hallazgos": [], "propuesta": [], "semaforo": "sin_datos"}
    patrimonio = total_acciones + max(otros_ahorros, 0.0)

    empresas = sorted(({"ticker": p["ticker"], "nombre": nombre_de(p["ticker"]), "valor": _valor(p),
                        "peso": _valor(p) / patrimonio, "peso_acciones": _valor(p) / total_acciones,
                        "ganancia": _valor(p) - _coste(p), "ganancia_pct": _valor(p) / _coste(p) - 1 if _coste(p) else 0,
                        "sector": sector_de(p["ticker"]), "pais": pais_de(p["ticker"])} for p in pos),
                      key=lambda e: -e["valor"])
    sectores, paises = {}, {}
    for e in empresas:
        sectores[e["sector"]] = sectores.get(e["sector"], 0.0) + e["peso"]
        paises[e["pais"]] = paises.get(e["pais"], 0.0) + e["peso"]
    n_efectivo = 1 / sum(e["peso_acciones"] ** 2 for e in empresas)
    peso_acciones = total_acciones / patrimonio

    hallazgos = []

    def h(gravedad, titulo, texto):
        hallazgos.append({"gravedad": gravedad, "titulo": titulo, "texto": texto})

    # 1. Concentración por empresa
    grandes = [e for e in empresas if e["peso"] > max_empresa]
    for e in grandes:
        h("alta" if e["peso"] > 0.35 else "media", f"{e['nombre']} pesa el {e['peso'] * 100:.0f} % de tu dinero",
          f"Lo prudente es que ninguna empresa pase del {max_empresa * 100:.0f} %. Si {e['nombre']} cayera un 40 % "
          f"(les ha pasado a grandes empresas en una sola mala noticia), perderías unos "
          f"{_eur(e['valor'] * 0.4)}, el {e['peso'] * 40:.0f} % de todo lo que tienes aquí.")
    if not grandes:
        h("ok", "Ninguna empresa pesa demasiado", f"Todas están por debajo del {max_empresa * 100:.0f} %.")

    # 2. Sectores
    grandes_t = {e["ticker"] for e in grandes}
    for s, w in sorted(sectores.items(), key=lambda x: -x[1]):
        del_sector = [e["ticker"] for e in empresas if e["sector"] == s]
        if len(del_sector) == 1 and del_sector[0] in grandes_t:
            continue  # ya avisado: es una sola empresa
        if w > max_sector and s != "—":
            h("alta" if w > 0.6 else "media", f"El sector {s} es el {w * 100:.0f} % de tu dinero",
              "Las empresas de un mismo sector suelen caer a la vez (por ejemplo, los bancos cuando bajan los tipos "
              f"de interés). Lo prudente es no pasar del {max_sector * 100:.0f} % en un sector.")

    # 3. Número de empresas
    if n_efectivo < MIN_EMPRESAS_EFECTIVAS:
        ne = f"{n_efectivo:.1f}".replace(".", ",")
        h("media", f"Tu cartera equivale a {ne} empresas",
          "Contando cuánto pesa cada una, tu riesgo es el de tener solo "
          f"{ne} empresas a partes iguales. Con menos de {MIN_EMPRESAS_EFECTIVAS}, lo que le pase a una sola "
          "empresa decide tu resultado. Un fondo indexado mundial reparte tu dinero entre más de 1.000 empresas.")

    # 4. Países
    pais_max, w_pais = max(paises.items(), key=lambda x: x[1])
    if w_pais > 0.7 and peso_acciones > 0.3:
        h("media", f"El {w_pais * 100:.0f} % de tu dinero depende de la bolsa de {pais_max}",
          f"Si a la economía de {pais_max} le va mal unos años, todo tu dinero lo nota. La bolsa de un solo país es una "
          "parte pequeña de la bolsa mundial; un fondo indexado mundial te reparte entre decenas de países.")

    # 5. Encaje con el perfil
    objetivo = asesor.REPARTOS.get(perfil or "", {}).get("Acciones individuales")
    if objetivo is not None:
        objetivo /= 100
        if peso_acciones > objetivo + 0.10:
            h("alta" if peso_acciones > objetivo + 0.40 else "media",
              f"Tienes el {peso_acciones * 100:.0f} % en acciones sueltas; para un perfil {perfil.lower()} la guía es "
              f"un {objetivo * 100:.0f} %",
              f"Llevarlo a ese reparto supondría pasar unos {_eur((peso_acciones - objetivo) * patrimonio)} a fondos "
              "(indexado, monetario y renta fija según 🎯 Mi plan). No hace falta hacerlo de golpe.")
        else:
            h("ok", f"El peso de las acciones sueltas encaja con tu perfil {perfil.lower()}",
              f"Tienes un {peso_acciones * 100:.0f} % y la guía es alrededor del {objetivo * 100:.0f} %.")

    # 6. Stop-loss
    sin_stop = [nombre_de(p["ticker"]) for p in pos if not p.get("stop")]
    if sin_stop:
        h("media", f"Sin stop-loss registrado: {', '.join(sin_stop)}",
          "Un stop-loss vende automáticamente si el precio cae hasta el nivel que eliges y evita que una caída "
          "fuerte se convierta en una pérdida enorme. Más abajo tienes la orden lista para cada posición. Si ya lo "
          "tienes puesto en Bankinter, apúntalo en la posición para que la app lo vigile.")

    # 7. Lo que dice el informe del día de cada empresa
    for p in pos:
        f = filas_informe.get(p["ticker"])
        if not f:
            continue
        etiqueta, color, _ = asesor.veredicto(f)
        nombre = nombre_de(p["ticker"])
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
    favorables = [nombre_de(p["ticker"]) for p in pos
                  if p["ticker"] in filas_informe and asesor.veredicto(filas_informe[p["ticker"]])[1] == "green"]
    if favorables and len(favorables) == len(pos):
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
            "empresas": empresas, "sectores": sectores, "paises": paises, "n_efectivo": n_efectivo,
            "hallazgos": hallazgos, "semaforo": semaforo, **propuesta}


def proponer_reequilibrio(pos: list[dict], patrimonio: float, tarifa: costes.Tarifa, perfil: str | None,
                          max_empresa: float = MAX_EMPRESA) -> dict:
    """Ventas para que ninguna empresa supere `max_empresa`, con su coste e impuestos aproximados, y a dónde
    llevar ese dinero. Las pérdidas de una venta compensan las ganancias de otra (como en el IRPF)."""
    ventas = []
    for p in pos:
        precio_eur = p["precio"] * p.get("fx", 1.0)
        exceso = _valor(p) - max_empresa * patrimonio
        if exceso <= 0:
            continue
        n = min(p["acciones"], math.ceil(exceso / precio_eur))
        importe = n * precio_eur
        coste_venta = tarifa.coste(importe, p["ticker"])
        coste_compra = n * p["precio_medio"] * p.get("fx_medio", p.get("fx", 1.0))
        ventas.append({"ticker": p["ticker"], "nombre": nombre_de(p["ticker"]), "acciones": n,
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
