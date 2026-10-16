"""Qué hacer con cada acción que ya tienes: esperar, diversificar, poner stop-loss, vigilar o vender.

Junta tres miradas:
- tu situación: cuánto pesa la acción frente a lo prudente para tu perfil y si tienes stop-loss;
- la de la app: tendencia, nota y riesgo de caída (el consejo de cada posición);
- la de los brókers: el consenso de los analistas que siguen la empresa (recomendación media y precio objetivo).

Se usa el consenso de analistas (Yahoo Finance) y no los foros: en los foros opina cualquiera, sin responsabilidad
y a veces para mover el precio a su favor. Los analistas también se equivocan, por eso es una mirada más, no la
decisión.
"""

from __future__ import annotations

import math

ACCIONES = {"vender": ("🔴", "Vender"), "diversificar": ("⚖️", "Diversificar"), "stop": ("🛡️", "Poner stop-loss"),
            "subir_stop": ("⬆️", "Subir el stop-loss"), "vigilar": ("🟠", "Vigilar"), "esperar": ("🟢", "Esperar")}
RECOMENDACIONES = {"strong_buy": "comprar (con convicción)", "buy": "comprar", "hold": "mantener",
                   "underperform": "reducir", "sell": "vender", "strong_sell": "vender (con convicción)"}
NEGATIVAS = {"underperform", "sell", "strong_sell"}


def _num(x: float) -> str:
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _pct(x: float) -> str:
    return f"{x * 100:+.0f} %".replace("-", "−")


def consenso(fund: dict | None, precio: float | None) -> dict | None:
    """Consenso de analistas: recomendación, nº de analistas, precio objetivo medio y potencial frente a hoy."""
    fund = fund or {}
    n, clave = fund.get("numberOfAnalystOpinions"), fund.get("recommendationKey")
    if not n or clave not in RECOMENDACIONES:
        return None
    objetivo = fund.get("targetMeanPrice")
    potencial = objetivo / precio - 1 if objetivo and precio else None
    texto = f"Consenso de {n} analistas: **{RECOMENDACIONES[clave]}**"
    if objetivo:
        texto += f", precio objetivo medio {_num(objetivo)}"
        if potencial is not None:
            texto += f" ({_pct(potencial)} sobre el precio de hoy)"
        if fund.get("targetLowPrice") and fund.get("targetHighPrice"):
            texto += f"; el más pesimista {_num(fund['targetLowPrice'])} y el más optimista {_num(fund['targetHighPrice'])}"
    return {"n": n, "clave": clave, "recomendacion": RECOMENDACIONES[clave], "objetivo": objetivo,
            "potencial": potencial, "texto": texto + "."}


def decidir(fila: dict, valor: float, total: float, limite: float, analistas: dict | None = None,
            precio_eur: float | None = None) -> dict:
    """`fila`: la revisión de la posición (nivel y consejo de la app, posición, stop sugerido, precio).
    `valor`/`total`: euros en esta acción y en toda la cuenta. `limite`: peso máximo prudente para tu perfil."""
    pos, nivel = fila["pos"], fila.get("nivel")
    peso = valor / total if total else 0.0
    sin_proteccion = not pos.get("stop") and not pos.get("sin_stop")
    stop_sug = fila.get("stop_sugerido")
    precio = fila.get("precio")
    motivos, tambien = [], []

    if nivel == "vender":
        clave, texto = "vender", fila.get("consejo", "")
    elif peso > limite and fila.get("clase", "Acciones") == "Acciones":
        exceso = valor - limite * total
        n = min(pos["acciones"], math.ceil(exceso / precio_eur)) if precio_eur else None
        clave = "diversificar"
        texto = (f"Pesa el {peso * 100:.0f} % de tu dinero y lo prudente para tu perfil es como mucho un "
                 f"{limite * 100:.0f} %. " + (f"Vende unas {n} acciones (≈ {_num(n * precio_eur)} €) y reparte ese "
                                              "dinero en un fondo indexado o en otras empresas de sectores distintos: "
                                              "así una mala noticia no te hunde." if n else
                                              "Vende una parte y repártela en un fondo indexado u otras empresas."))
        if sin_proteccion and stop_sug:
            tambien.append(f"🛡️ Y pon un stop-loss en {_num(stop_sug)} a lo que te quede.")
    elif sin_proteccion and fila.get("clase", "Acciones") == "Acciones":
        clave = "stop"
        texto = (f"No tiene stop-loss. Ponlo en {_num(stop_sug)} ({_pct(stop_sug / precio - 1)} desde el precio de hoy): "
                 "si cae con fuerza, vende sola y limita la pérdida." if stop_sug and precio else
                 "No tiene stop-loss: ponlo para limitar lo que puedes perder.")
        tambien.append("O, si la compraste para largo plazo sin stop a propósito, márcala en 🏦 Mi cartera como "
                       "«solo vigilar» y la app te avisará si cae.")
    elif nivel == "vigilar":
        clave, texto = "vigilar", fila.get("consejo", "")
    elif nivel == "subir_stop":
        clave, texto = "subir_stop", fila.get("consejo", "")
    else:
        clave = "esperar"
        texto = ("Todo en orden: mantén y espera. Tendencia, nota y peso están bien; no hace falta hacer nada "
                 "(cada operación cuesta comisiones e impuestos).")

    if analistas:
        motivos.append(analistas["texto"])
        pot = analistas.get("potencial")
        if analistas["clave"] in NEGATIVAS and clave == "esperar":
            clave = "vigilar"
            texto = ("La app no ve problemas, pero los analistas recomiendan reducir o vender: no compres más y "
                     "revisa si tu motivo para tenerla sigue en pie.")
        elif pot is not None and pot < -0.05 and clave in ("esperar", "subir_stop"):
            motivos.append(f"Ojo: ya cotiza por encima del objetivo medio de los analistas ({_pct(pot)}); según "
                           "ellos le queda poco recorrido. Buen momento para proteger la ganancia con el stop.")
        elif pot is not None and pot > 0.15 and analistas["clave"] in ("buy", "strong_buy") and clave in (
                "diversificar", "vigilar"):
            motivos.append(f"Los analistas le ven recorrido ({_pct(pot)}), pero eso no cambia el riesgo de tener "
                           "demasiado en una sola empresa.")
    if fila.get("consejo") and clave not in ("vender", "vigilar", "subir_stop"):
        motivos.insert(0, "Lo que ve la app: " + fila["consejo"])
    icono, titulo = ACCIONES[clave]
    return {"clave": clave, "icono": icono, "titulo": titulo, "texto": texto, "tambien": tambien,
            "motivos": motivos, "peso": peso}


__all__ = ["ACCIONES", "RECOMENDACIONES", "consenso", "decidir"]
