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

ACCIONES = {"vender": ("🔴", "Vender"), "diversificar": ("⚖️", "Vender una parte para diversificar"),
            "vender_parte": ("✂️", "Vender una parte (recoger beneficios)"), "stop": ("🛡️", "Poner stop-loss"),
            "subir_stop": ("⬆️", "Subir el stop-loss"), "vigilar": ("🟠", "Vigilar"),
            "comprar": ("➕", "Comprar más"), "esperar": ("🟢", "Esperar")}
RECOMENDACIONES = {"strong_buy": "comprar (con convicción)", "buy": "comprar", "hold": "mantener",
                   "underperform": "reducir", "sell": "vender", "strong_sell": "vender (con convicción)"}
NEGATIVAS = {"underperform", "sell", "strong_sell"}


def _num(x: float) -> str:
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _pct(x: float) -> str:
    return f"{x * 100:+.0f} %".replace("-", "−")


def _clave_por_media(media: float) -> str:
    """Recomendación media de 1 (comprar con convicción) a 5 (vender con convicción), como la publica Yahoo."""
    return ("strong_buy" if media <= 1.5 else "buy" if media <= 2.5 else "hold" if media <= 3.5 else
            "underperform" if media <= 4.5 else "sell")


def consenso(fund: dict | None, precio: float | None, extra: dict | None = None) -> dict | None:
    """Consenso de los analistas que siguen la empresa, con su fiabilidad.

    Junta tres señales independientes del mismo grupo de analistas (bancos y brókers):
    - qué recomiendan (cuántos dicen comprar, mantener o vender) y cómo ha cambiado en 3 meses;
    - a qué precio creen que llegará (mediana: no la distorsiona un analista extremo) y lo de acuerdo que están;
    - si están subiendo o bajando sus previsiones de beneficio (lo que más mueve los precios a medio plazo).
    `extra`: lo de datos.analistas(); si falta, se usa el resumen de los datos de la empresa."""
    fund, extra = fund or {}, extra or {}
    rec = extra.get("recuento")
    n = sum(rec.values()) if rec else fund.get("numberOfAnalystOpinions") or 0
    if rec and n:
        media = (rec["strongBuy"] + 2 * rec["buy"] + 3 * rec["hold"] + 4 * rec["sell"] + 5 * rec["strongSell"]) / n
        clave = _clave_por_media(media)
    else:
        clave = fund.get("recommendationKey")
    if not n or clave not in RECOMENDACIONES:
        return None
    lineas = []
    acuerdo = None
    tendencia = "sin datos"
    if rec:
        compran, mantienen = rec["strongBuy"] + rec["buy"], rec["hold"]
        venden = rec["sell"] + rec["strongSell"]
        acuerdo = max(compran, mantienen, venden) / n
        lineas.append(f"{n} analistas: {compran} comprar · {mantienen} mantener · {venden} vender "
                      f"({compran / n * 100:.0f} % recomienda comprar) → **{RECOMENDACIONES[clave]}**.")
        antes = extra.get("recuento_antes")
        if antes and sum(antes.values()):
            cambio = compran / n - (antes["strongBuy"] + antes["buy"]) / sum(antes.values())
            tendencia = "mejora" if cambio >= 0.10 else "empeora" if cambio <= -0.10 else "estable"
    else:
        lineas.append(f"Consenso de {n} analistas: **{RECOMENDACIONES[clave]}**.")
    obj = extra.get("objetivos") or {}
    objetivo = obj.get("median") or obj.get("mean") or fund.get("targetMeanPrice")
    bajo, alto = obj.get("low") or fund.get("targetLowPrice"), obj.get("high") or fund.get("targetHighPrice")
    potencial = objetivo / precio - 1 if objetivo and precio else None
    potencial_alto = alto / precio - 1 if alto and precio else None
    dispersion = (alto - bajo) / objetivo if alto and bajo and objetivo else None
    if objetivo:
        texto = f"Precio objetivo ({'mediana' if obj.get('median') else 'media'}): {_num(objetivo)}"
        if potencial is not None:
            texto += f" ({_pct(potencial)} sobre el precio de hoy)"
        if bajo and alto:
            texto += f"; el más pesimista {_num(bajo)} y el más optimista {_num(alto)}"
        lineas.append(texto + ".")
    revision = extra.get("revision_beneficios")
    partes = []
    if tendencia != "sin datos":
        partes.append({"mejora": "más analistas recomiendan comprar que hace 3 meses",
                       "empeora": "menos analistas recomiendan comprar que hace 3 meses",
                       "estable": "su opinión apenas ha cambiado en 3 meses"}[tendencia])
    if revision is not None:
        partes.append(f"han {'subido' if revision >= 0 else 'bajado'} sus previsiones de beneficio un "
                      f"{abs(revision) * 100:.1f} % en 90 días".replace(".", ","))
    if partes:
        lineas.append(("Evolución: " + "; ".join(partes) + ".").capitalize())
    for c in (extra.get("cambios") or [])[:3]:
        lineas.append(f"{c['fecha']}: {c['firma']} → {c['a']}" + (f" (objetivo {_num(c['objetivo'])})"
                                                                    if c.get("objetivo") else ""))
    # Fiabilidad: muchos analistas, de acuerdo entre ellos y con objetivos parecidos.
    puntos = (2 if n >= 15 else 1 if n >= 8 else 0) + (2 if (acuerdo or 0) >= 0.7 else 1 if (acuerdo or 0) >= 0.55
                                                       else 0) + (2 if dispersion is not None and dispersion <= 0.35
                                                                  else 1 if dispersion is not None and dispersion <= 0.6
                                                                  else 0)
    fiabilidad = "alta" if puntos >= 5 else "media" if puntos >= 3 else "baja"
    motivo = {"alta": "muchos analistas, de acuerdo entre ellos y con objetivos parecidos",
              "media": "bastantes analistas, pero no todos coinciden", "baja": "pocos analistas o muy en desacuerdo: "
              "tómalo con cautela"}[fiabilidad]
    lineas.append(f"Fiabilidad del consenso: **{fiabilidad}** ({motivo}).")
    return {"n": n, "clave": clave, "recomendacion": RECOMENDACIONES[clave], "objetivo": objetivo,
            "potencial": potencial, "potencial_alto": potencial_alto, "fiabilidad": fiabilidad,
            "tendencia": tendencia, "revision": revision, "lineas": lineas, "texto": " ".join(lineas)}


def decidir(fila: dict, valor: float, total: float, limite: float, analistas: dict | None = None,
            precio_eur: float | None = None) -> dict:
    """Qué hacer hoy con una acción que ya tienes.
    `fila`: la revisión de la posición (nivel y consejo de la app, posición, stop sugerido, precio).
    `valor`/`total`: euros en esta acción y en toda la cuenta. `limite`: peso máximo prudente para tu perfil.
    `analistas`: lo de consenso()."""
    pos, nivel = fila["pos"], fila.get("nivel")
    es_accion = fila.get("clase", "Acciones") == "Acciones"
    peso = valor / total if total else 0.0
    sin_proteccion = not pos.get("stop") and not pos.get("sin_stop")
    stop_sug, precio = fila.get("stop_sugerido"), fila.get("precio")
    a = analistas or {}
    negativos = a.get("clave") in NEGATIVAS
    motivos, tambien = [], []

    def n_acciones(euros: float) -> int:
        return max(int(euros // precio_eur), 0) if precio_eur else 0

    if nivel == "vender":
        clave, texto = "vender", fila.get("consejo", "")
    elif peso > limite and es_accion:
        n = min(pos["acciones"], math.ceil((valor - limite * total) / precio_eur)) if precio_eur else None
        clave = "diversificar"
        texto = (f"Pesa el {peso * 100:.0f} % de tu dinero y lo prudente para tu perfil es como mucho un "
                 f"{limite * 100:.0f} %. " + (f"Vende unas {n} acciones (≈ {_num(n * precio_eur)} €) y reparte ese "
                                              "dinero en un fondo indexado o en otras empresas de sectores distintos: "
                                              "así una mala noticia no te hunde." if n else
                                              "Vende una parte y repártela en un fondo indexado u otras empresas."))
        if sin_proteccion and stop_sug:
            tambien.append(f"🛡️ Y pon un stop-loss en {_num(stop_sug)} a lo que te quede.")
    elif nivel == "vigilar" and negativos:
        clave = "vender"
        texto = ("La tendencia se ha estropeado y además los analistas recomiendan reducir o vender: te recomiendo "
                 "vender o, al menos, una buena parte.")
    elif (es_accion and a.get("potencial_alto") is not None and a["potencial_alto"] < 0 and precio
          and pos.get("precio_medio") and precio >= pos["precio_medio"]):
        n = n_acciones(valor / 2)
        clave = "vender_parte"
        texto = (f"Ya cotiza por encima del objetivo MÁS optimista de los analistas ({_pct(a['potencial_alto'])}). "
                 f"Te recomiendo vender una parte (por ejemplo, la mitad: unas {n} acciones) y asegurar la ganancia; "
                 "al resto, súbele el stop-loss.")
    elif sin_proteccion and es_accion:
        clave = "stop"
        texto = (f"Te recomiendo poner un stop-loss en {_num(stop_sug)} ({_pct(stop_sug / precio - 1)} desde el precio "
                 "de hoy): si cae con fuerza, vende sola y limita la pérdida." if stop_sug and precio else
                 "Te recomiendo poner un stop-loss para limitar lo que puedes perder.")
        tambien.append("O, si la compraste para largo plazo sin stop a propósito, márcala en 🏦 Mi cartera como "
                       "«solo vigilar» y la app te avisará si cae.")
    elif nivel == "vigilar":
        clave, texto = "vigilar", fila.get("consejo", "")
    elif nivel == "subir_stop":
        clave, texto = "subir_stop", fila.get("consejo", "")
    elif (es_accion and nivel == "mantener" and peso < limite * 0.8 and a.get("clave") in ("buy", "strong_buy")
          and (a.get("potencial") or 0) >= 0.10 and a.get("fiabilidad") != "baja" and a.get("tendencia") != "empeora"
          and (a.get("revision") is None or a["revision"] > -0.02)
          and n_acciones(limite * total - valor) >= 1):
        n = n_acciones(limite * total - valor)
        clave = "comprar"
        texto = (f"Todo acompaña: la tendencia es buena, los analistas recomiendan comprar con un objetivo "
                 f"{_pct(a['potencial'])} por encima del precio de hoy y aún pesa poco en tu cartera. Si quieres "
                 f"aumentarla, te recomiendo comprar como mucho unas {n} acciones (≈ {_num(n * precio_eur)} €), para "
                 f"no pasar del {limite * 100:.0f} % que es prudente para tu perfil. Mejor en 2-3 veces que de golpe.")
    else:
        clave = "esperar"
        texto = ("Te recomiendo esperar: mantén las que tienes y no compres más por ahora. "
                 + ("Está cerca del máximo prudente para tu perfil." if es_accion and peso >= limite * 0.8 else
                    "Tendencia, peso y opinión de los analistas no piden hacer nada (cada operación cuesta comisiones "
                    "e impuestos)."))

    if a:
        pot = a.get("potencial")
        if negativos and clave in ("esperar", "comprar"):
            clave = "vigilar"
            texto = ("La app no ve problemas, pero los analistas recomiendan reducir o vender: no compres más y "
                     "revisa si tu motivo para tenerla sigue en pie.")
        elif pot is not None and pot < -0.05 and clave in ("esperar", "subir_stop"):
            motivos.append(f"Ojo: ya cotiza por encima del objetivo medio de los analistas ({_pct(pot)}); según "
                           "ellos le queda poco recorrido. Buen momento para proteger la ganancia con el stop.")
        elif pot is not None and pot > 0.15 and a.get("clave") in ("buy", "strong_buy") and clave in (
                "diversificar", "vigilar"):
            motivos.append(f"Los analistas le ven recorrido ({_pct(pot)}), pero eso no cambia el riesgo de tener "
                           "demasiado en una sola empresa.")
    if fila.get("consejo") and clave not in ("vender", "vigilar", "subir_stop"):
        motivos.insert(0, "Lo que ve la app: " + fila["consejo"])
    icono, titulo = ACCIONES[clave]
    situacion = None
    if precio and pos.get("precio_medio"):
        ganancia = precio / pos["precio_medio"] - 1
        situacion = (f"Tienes {_num(pos['acciones']).rstrip('0').rstrip(',')} acciones compradas a "
                     f"{_num(pos['precio_medio'])} · hoy {_num(precio)} ({_pct(ganancia)})")
    return {"clave": clave, "icono": icono, "titulo": titulo, "texto": texto, "tambien": tambien,
            "motivos": motivos, "analistas": (a.get("lineas") or []), "peso": peso, "situacion": situacion}


__all__ = ["ACCIONES", "RECOMENDACIONES", "consenso", "decidir"]
