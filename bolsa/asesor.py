"""Asesor: dónde invertir según tu perfil, con un plan concreto en euros.

Sigue los principios en los que coinciden casi todos los expertos para el inversor particular:
1. Primero un colchón de emergencia fuera de la bolsa.
2. Lo que necesites en menos de 2-3 años, fuera de la bolsa.
3. El núcleo, en fondos indexados/ETF globales y baratos (diversificación máxima).
4. Una parte pequeña en acciones individuales, bien diversificadas y con stop-loss.
5. Si el mercado está débil, entrar poco a poco en lugar de todo de golpe.

No es asesoramiento financiero personalizado regulado: es una guía educativa.
"""

from __future__ import annotations

from dataclasses import dataclass, field

REACCIONES = {
    "Vendería todo para no perder más": 0,
    "Me preocuparía, pero esperaría": 2,
    "Aprovecharía para comprar más": 3,
}
EXPERIENCIA = {"Ninguna": 0, "Básica (sé lo que es una acción y un fondo)": 1, "He invertido antes": 2}

REPARTOS = {
    "Conservador": {"Monetario / Letras del Tesoro": 35, "Bonos a corto plazo": 25, "ETF mundial": 35,
                    "Acciones individuales": 5},
    "Moderado": {"Monetario / Letras del Tesoro": 10, "Bonos a corto plazo": 15, "ETF mundial": 60,
                 "Acciones individuales": 15},
    "Dinámico": {"Monetario / Letras del Tesoro": 5, "Bonos a corto plazo": 0, "ETF mundial": 70,
                 "Acciones individuales": 25},
}

PRODUCTOS = {
    "Monetario / Letras del Tesoro": {
        "ticker": "XEON.DE",
        "que": "Letras del Tesoro (se compran en tesoro.es o en Bankinter), una cuenta remunerada o un "
               "fondo/ETF monetario. Prácticamente sin riesgo; rentan aproximadamente lo que marcan los tipos del BCE.",
    },
    "Bonos a corto plazo": {
        "ticker": "IBGS.AS",
        "que": "Un ETF o fondo de deuda pública europea a 1-3 años. Se mueve poco y amortigua las caídas de la bolsa.",
    },
    "ETF mundial": {
        "ticker": "IWDA.AS",
        "que": "Un ETF que replica la bolsa mundial (MSCI World o FTSE All-World): miles de empresas de todo el "
               "mundo en una sola compra, con comisiones mínimas. Es el núcleo de la inversión a largo plazo.",
    },
    "Acciones individuales": {
        "ticker": None,
        "que": "Empresas concretas elegidas con las 'Ideas del día' de la app: puntuación alta, sectores distintos, "
               "siempre con stop-loss. Es la parte para aprender y buscar algo extra.",
    },
}

MINIMO_POR_ACCION = 600.0  # por debajo, las comisiones mínimas se comen demasiado


@dataclass
class Perfil:
    nombre: str
    puntos: int
    motivos: list[str] = field(default_factory=list)
    alertas: list[str] = field(default_factory=list)
    invertir_en_bolsa: bool = True


def perfil_inversor(horizonte_anos: int, reaccion: str, experiencia: str, colchon: bool,
                    deudas_caras: bool = False) -> Perfil:
    puntos = 0
    motivos, alertas = [], []
    if horizonte_anos < 2:
        puntos += 0
        motivos.append("Necesitarás el dinero en menos de 2 años.")
    elif horizonte_anos < 5:
        puntos += 1
        motivos.append(f"Horizonte medio ({horizonte_anos} años).")
    elif horizonte_anos < 10:
        puntos += 2
        motivos.append(f"Horizonte largo ({horizonte_anos} años): puedes esperar a que pasen las caídas.")
    else:
        puntos += 3
        motivos.append(f"Horizonte muy largo ({horizonte_anos} años): el tiempo juega a tu favor.")
    puntos += REACCIONES.get(reaccion, 1)
    motivos.append(f"Ante una caída del 20%: «{reaccion.lower()}».")
    puntos += EXPERIENCIA.get(experiencia, 0)
    nombre = "Conservador" if puntos <= 3 else "Moderado" if puntos <= 6 else "Dinámico"
    if REACCIONES.get(reaccion, 1) == 0 and nombre == "Dinámico":
        nombre = "Moderado"
        motivos.append("Como venderías en una caída, se limita a perfil Moderado.")
    invertir = True
    if not colchon:
        alertas.append("Antes de invertir, reúne un **colchón de emergencia** de 3 a 6 meses de gastos en una "
                       "cuenta remunerada o Letras del Tesoro. Así nunca tendrás que vender en mal momento.")
    if deudas_caras:
        alertas.append("Si tienes deudas caras (tarjetas, préstamos al consumo por encima del 7-8%), "
                       "devolverlas es la 'inversión' más rentable y sin riesgo.")
    if horizonte_anos < 2:
        invertir = False
        alertas.append("Con menos de 2 años, la bolsa es demasiado arriesgada: puede estar en plena caída justo "
                       "cuando necesites el dinero. Usa Letras del Tesoro, depósitos o un fondo monetario.")
    return Perfil(nombre, puntos, motivos, alertas, invertir)


def ritmo_de_entrada(fase: str | None) -> str:
    if fase in ("Bajista", "Intentando recuperarse"):
        return ("El mercado está débil: invierte la parte de bolsa **poco a poco, en 6 aportaciones mensuales**. "
                "Si sigue cayendo, comprarás más barato; si sube, ya habrás empezado.")
    if fase in ("Alcista con nervios", "Corrección en tendencia alcista"):
        return "Hay algo de nerviosismo: reparte la parte de bolsa en **3 aportaciones mensuales**."
    return ("Mercado tranquilo: puedes invertir la parte de ETF de una vez o en 2-3 meses. "
            "Históricamente invertir pronto suele ganar a esperar, pero entrar escalonado da tranquilidad.")


def ideas_diversificadas(ranking: list[dict], max_ideas: int = 5, min_puntuacion: int = 65,
                         max_por_sector: int = 1) -> list[dict]:
    """Elige las mejores acciones sin repetir sector y descartando las que presentan resultados ya."""
    elegidas, por_sector = [], {}
    candidatas = [r for r in ranking if not r.get("etf") and r.get("puntuacion", 0) >= min_puntuacion
                  and not r.get("resultados_pronto")]
    candidatas.sort(key=lambda r: (r.get("puntuacion", 0) + 20 * (r.get("prob_modelo", 0.5) - 0.5)), reverse=True)
    for r in candidatas:
        s = r.get("sector", "—")
        if por_sector.get(s, 0) >= max_por_sector:
            continue
        elegidas.append(r)
        por_sector[s] = por_sector.get(s, 0) + 1
        if len(elegidas) >= max_ideas:
            break
    return elegidas


def plan_inversion(importe: float, mensual: float, perfil: Perfil, ideas: list[dict]) -> dict:
    """Reparto concreto en euros del importe inicial y de la aportación mensual."""
    reparto = dict(REPARTOS[perfil.nombre]) if perfil.invertir_en_bolsa else \
        {"Monetario / Letras del Tesoro": 100, "Bonos a corto plazo": 0, "ETF mundial": 0, "Acciones individuales": 0}
    euros_acciones = importe * reparto["Acciones individuales"] / 100
    n_ideas = min(len(ideas), int(euros_acciones // MINIMO_POR_ACCION))
    avisos = []
    if reparto["Acciones individuales"] and n_ideas == 0:
        # No compensa comprar acciones sueltas con tan poco: esa parte va al ETF.
        reparto["ETF mundial"] += reparto["Acciones individuales"]
        reparto["Acciones individuales"] = 0
        avisos.append(f"Con menos de {MINIMO_POR_ACCION:.0f} € por empresa las comisiones mínimas pesan demasiado: "
                      "de momento esa parte va al ETF mundial.")
    lineas = []
    for parte, pct in reparto.items():
        if pct <= 0:
            continue
        lineas.append({"parte": parte, "pct": pct, "euros": importe * pct / 100,
                       "ticker": PRODUCTOS[parte]["ticker"], "que": PRODUCTOS[parte]["que"]})
    acciones = []
    if reparto["Acciones individuales"] and n_ideas:
        cada = importe * reparto["Acciones individuales"] / 100 / n_ideas
        for r in ideas[:n_ideas]:
            acciones.append({**r, "euros": cada})
    # Aportación mensual: casi todo al ETF (una sola comisión), el resto al monetario.
    mensual_etf = mensual * (reparto["ETF mundial"] + reparto["Acciones individuales"]) / 100
    return {"lineas": lineas, "acciones": acciones, "mensual_etf": mensual_etf,
            "mensual_seguro": mensual - mensual_etf, "avisos": avisos, "reparto": reparto}


def pesos_para_escenarios(plan: dict) -> dict[str, float]:
    """Pesos por ticker (para simular escenarios con la historia real)."""
    pesos: dict[str, float] = {}
    for l in plan["lineas"]:
        if l["parte"] == "Acciones individuales":
            continue
        if l["ticker"]:
            pesos[l["ticker"]] = pesos.get(l["ticker"], 0) + l["pct"]
    for a in plan["acciones"]:
        pesos[a["ticker"]] = pesos.get(a["ticker"], 0) + plan["reparto"]["Acciones individuales"] / len(plan["acciones"])
    return pesos
