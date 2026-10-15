"""Asesor: dónde invertir según tu perfil, con un plan concreto en euros.

Sigue los principios en los que coinciden casi todos los expertos para el inversor particular:
1. Primero un colchón de emergencia fuera de la bolsa.
2. Lo que necesites en menos de 2-3 años, fuera de la bolsa.
3. El núcleo, en fondos indexados globales y baratos (diversificación máxima). En España, mejor fondos
   que ETF para aportar cada mes: no pagan comisión por aportación y se pueden traspasar sin impuestos.
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
    "Conservador": {"Monetario / Letras del Tesoro": 35, "Renta fija a corto plazo": 25, "Fondo indexado mundial": 35,
                    "Acciones individuales": 5},
    "Moderado": {"Monetario / Letras del Tesoro": 10, "Renta fija a corto plazo": 15, "Fondo indexado mundial": 60,
                 "Acciones individuales": 15},
    "Dinámico": {"Monetario / Letras del Tesoro": 5, "Renta fija a corto plazo": 0, "Fondo indexado mundial": 70,
                 "Acciones individuales": 25},
}

# `ticker` solo se usa como referencia para simular escenarios con su historia real (no es una recomendación
# de producto concreto).
PRODUCTOS = {
    "Monetario / Letras del Tesoro": {
        "ticker": "XEON.DE",
        "que": "Letras del Tesoro (en tesoro.es o en Bankinter), un fondo monetario o una cuenta remunerada. "
               "Prácticamente sin riesgo; rentan más o menos lo que marcan los tipos del BCE.",
    },
    "Renta fija a corto plazo": {
        "ticker": "IBGS.AS",
        "que": "Un fondo de deuda pública europea a corto plazo (1-3 años). Se mueve poco y amortigua las caídas "
               "de la bolsa.",
    },
    "Fondo indexado mundial": {
        "ticker": "IWDA.AS",
        "que": "Un fondo indexado al MSCI World o al FTSE All-World (miles de empresas de todo el mundo) con "
               "comisión anual baja (menos del 0,3 %). Búscalo en el buscador de fondos de Bankinter. Para aportar "
               "cada mes es mejor un fondo que un ETF: en Bankinter cada compra de un ETF extranjero cuesta 20 €, "
               "y entre fondos puedes hacer traspasos sin pagar impuestos.",
    },
    "Acciones individuales": {
        "ticker": None,
        "que": "Empresas concretas de la cartera modelo que encaja con tu perfil. Por defecto, españolas: en "
               "Bankinter cuestan de 0 a 8 € por operación, frente a 20 € más un 1 % de cambio de divisa y "
               "custodia (mínimo 24 € al año por valor) en las extranjeras.",
    },
}

MINIMO_POR_ACCION = 1_000.0       # España: comprar + vender cuesta ~1,2 % con 1.000 € (tarifa estándar)
MINIMO_POR_ACCION_CERO = 500.0    # con Bróker Cero solo se pagan los cánones de bolsa
MINIMO_INTERNACIONAL = 5_000.0    # extranjeras: 20 € por operación + custodia mínima de 24 €/año


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
                         max_por_sector: int = 1, solo_nacional: bool = False) -> list[dict]:
    """Elige las mejores acciones sin repetir sector y descartando las que presentan resultados ya."""
    elegidas, por_sector = [], {}

    def nota(r: dict) -> float:
        return r["nota"] if r.get("nota") is not None else r.get("puntuacion", 0)

    candidatas = [r for r in ranking if not r.get("etf") and nota(r) >= min_puntuacion
                  and not r.get("resultados_pronto") and r.get("riesgo_nivel") != "alto"
                  and (not solo_nacional or str(r.get("ticker", "")).endswith(".MC"))]
    candidatas.sort(key=nota, reverse=True)
    for r in candidatas:
        s = r.get("sector", "—")
        if por_sector.get(s, 0) >= max_por_sector:
            continue
        elegidas.append(r)
        por_sector[s] = por_sector.get(s, 0) + 1
        if len(elegidas) >= max_ideas:
            break
    return elegidas


def veredicto(f: dict) -> tuple[str, str, str]:
    """Veredicto ÚNICO de la app para una acción: (etiqueta, color, explicación en lenguaje llano)."""
    tecnica = f.get("puntuacion", 50)
    nota = f.get("nota")
    if f.get("mercado_alcista") is False:
        return ("Esperar", "orange", "Su mercado está en tendencia bajista: en esas fases incluso las buenas empresas "
                "suelen caer. Mejor esperar a que se recupere.")
    if tecnica < 40:
        return ("Evitar por ahora", "red", "Su propia tendencia es bajista: comprar ahora es intentar coger un "
                "cuchillo que cae.")
    if f.get("riesgo_nivel") == "alto":
        return ("Arriesgada ahora", "orange", "El modelo ve un riesgo alto de que caiga más de un 10 % el próximo mes. "
                "Si la compras, que sea con poco dinero y con stop-loss.")
    if nota is not None:
        if nota >= 75 and tecnica >= 55:
            texto = ("Está entre las mejores de hoy y su tendencia acompaña. Si encaja en tu plan, puedes comprarla "
                     "con una orden limitada y protegerla con un stop-loss.")
            if f.get("resultados_pronto"):
                texto += " Presenta resultados en pocos días: muchos prefieren esperar a verlos."
            return ("Candidata a comprar", "green", texto)
        if nota >= 40:
            return ("Neutral", "gray", "Ni de las mejores ni de las peores ahora mismo. Si ya la tienes, mantenla con "
                    "su stop-loss; si no, hay opciones mejores.")
        return ("Floja", "orange", "Está en la parte baja del ranking: ahora mismo hay opciones mejores.")
    if tecnica >= 70:
        return ("Tendencia favorable", "green", "Su tendencia y su impulso son buenos. No está en el informe diario, "
                "así que no se ha comparado con las demás empresas.")
    if tecnica >= 55:
        return ("Neutral", "gray", "Señales mezcladas, ligeramente positivas.")
    return ("Esperar", "orange", "Señales mezcladas: no hay prisa por comprar.")


def plan_inversion(importe: float, mensual: float, perfil: Perfil, ideas: list[dict],
                   minimo_por_accion: float = MINIMO_POR_ACCION) -> dict:
    """Reparto concreto en euros del importe inicial y de la aportación mensual."""
    reparto = dict(REPARTOS[perfil.nombre]) if perfil.invertir_en_bolsa else \
        {"Monetario / Letras del Tesoro": 100, "Renta fija a corto plazo": 0, "Fondo indexado mundial": 0,
         "Acciones individuales": 0}
    euros_acciones = importe * reparto["Acciones individuales"] / 100
    n_ideas = min(len(ideas), int(euros_acciones // minimo_por_accion))
    avisos = []
    if reparto["Acciones individuales"] and n_ideas == 0:
        # No compensa comprar acciones sueltas con tan poco: esa parte va al fondo indexado.
        reparto["Fondo indexado mundial"] += reparto["Acciones individuales"]
        reparto["Acciones individuales"] = 0
        avisos.append(f"Para que las comisiones no se coman la ganancia, conviene invertir al menos "
                      f"{minimo_por_accion:,.0f} € por empresa".replace(",", ".")
                      + ". De momento, esa parte va al fondo indexado.")
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
    # Aportación mensual: al fondo indexado (sin comisión por aportación) y el resto a la parte segura.
    mensual_fondo = mensual * (reparto["Fondo indexado mundial"] + reparto["Acciones individuales"]) / 100
    return {"lineas": lineas, "acciones": acciones, "mensual_fondo": mensual_fondo,
            "mensual_seguro": mensual - mensual_fondo, "avisos": avisos, "reparto": reparto}


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
