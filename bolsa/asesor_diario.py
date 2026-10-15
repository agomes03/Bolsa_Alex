"""«Tu asesor hoy»: qué hacer hoy con tu dinero, en orden de importancia.

Junta lo que sabe la app (diagnóstico de tu cartera, consejo de cada posición, semáforo y regla de protección de
los índices, lectura de oro, bitcoin y demás activos) y lo convierte en una lista corta de acciones concretas.
Si no hay nada importante, lo dice: no hacer nada también es una decisión profesional.
"""

from __future__ import annotations

import re
from datetime import date

NOMBRE_INDICE = {"^IBEX": "IBEX 35", "^GSPC": "S&P 500", "^STOXX50E": "Euro Stoxx 50"}


def _accion(prioridad: int, icono: str, titulo: str, texto: str, pagina: str | None = None) -> dict:
    return {"prioridad": prioridad, "icono": icono, "titulo": titulo, "texto": texto, "pagina": pagina}


def _lista(nombres: list[str]) -> str:
    """«A, B y C» (con «e» delante de palabras que empiezan por «i»: «Inditex e Indra»)."""
    if len(nombres) <= 1:
        return "".join(nombres)
    ultimo = nombres[-1]
    y = "e" if ultimo[:1].lower() in ("i", "í") or ultimo[:2].lower() in ("hi", "hí") else "y"
    return ", ".join(nombres[:-1]) + f" {y} {ultimo}"


def _num(x: float) -> str:
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _agrupar(nivel: str, grupo: list[dict]) -> tuple[str, str]:
    nombres = [p.get("nombre") or p["ticker"] for p in grupo]
    if nivel == "poner_stop" and all(p.get("stop_sugerido") for p in grupo):
        niveles = " · ".join(f"{n} a {_num(p['stop_sugerido'])}" for n, p in zip(nombres, grupo))
        return (f"Sin stop-loss: {_lista(nombres)}",
                f"Crea en tu bróker una orden Stop de venta para cada una ({niveles}). Así limitas lo que puedes "
                "perder si caen con fuerza.")
    titulos = {"vender": "Vender o reducir", "vigilar": "Vigilar de cerca", "poner_stop": "Sin stop-loss",
               "subir_stop": "Subir el stop-loss"}
    return (f"{titulos[nivel]}: {_lista(nombres)}",
            " ".join(f"**{n}:** {p.get('consejo', '')}" for n, p in zip(nombres, grupo)))


def plan_del_dia(diagnostico: dict | None, posiciones: list[dict], informe: dict | None,
                 activos: list[dict] | None = None, hoy: date | None = None, maximo: int = 6,
                 dividendos: list[dict] | None = None) -> list[dict]:
    """`posiciones`: filas con ticker, nombre, clase, nivel y consejo (de la revisión diaria de la cartera).
    `activos`: resumen de activos.resumen()."""
    hoy = hoy or date.today()
    informe = informe or {}
    acciones: list[dict] = []
    clases = (diagnostico or {}).get("clases", {})

    # 1. El mercado: regla de protección y semáforo
    fuera = [NOMBRE_INDICE.get(t, t) for t, p in (informe.get("proteccion") or {}).items() if p.get("estado") == "fuera"]
    if fuera:
        acciones.append(_accion(
            1, "🛡️", f"Protección activada en {', '.join(fuera)}",
            "Ha caído por debajo de su media de 200 sesiones. No abras posiciones nuevas en acciones sueltas y "
            "revisa que tus stop-loss estén puestos. Las aportaciones mensuales al fondo indexado siguen igual.",
            "hoy"))
    semaforo = (informe.get("mercado") or {}).get("semaforo")
    if semaforo == "rojo" and not fuera:
        acciones.append(_accion(2, "🔴", "Mercado en fase débil",
                                "Si vas a comprar, hazlo poco a poco (en 3-4 veces) en lugar de todo de golpe.", "hoy"))

    # 2. Cada posición (varias con el mismo consejo, en una sola línea)
    urgentes = {"vender": 1, "vigilar": 1, "poner_stop": 2, "subir_stop": 2}
    iconos = {"vender": "🔴", "vigilar": "🟠", "poner_stop": "🟡", "subir_stop": "⬆️"}
    for nivel in urgentes:
        grupo = [p for p in posiciones if p.get("nivel") == nivel]
        if len(grupo) == 1:
            p = grupo[0]
            acciones.append(_accion(urgentes[nivel], iconos[nivel], p.get("nombre") or p["ticker"],
                                    p.get("consejo", ""), "bankinter"))
        elif grupo:
            acciones.append(_accion(urgentes[nivel], iconos[nivel], *_agrupar(nivel, grupo), "bankinter"))

    # 3. Diagnóstico de la cartera (lo grave primero; las empresas que pesan demasiado, en una sola línea)
    hallazgos = (diagnostico or {}).get("hallazgos", [])
    patron = re.compile(r"^(.+) pesa el (\d+ %)")
    pesos = [m for m in (patron.match(x["titulo"]) for x in hallazgos if x["gravedad"] in ("alta", "media")) if m]
    if len(pesos) >= 2:
        acciones.append(_accion(
            2, "⚖️", f"{_lista([f'{m.group(1)} ({m.group(2)})' for m in pesos])} pesan demasiado",
            "Lo prudente es que ninguna empresa pase del 20 % de tu dinero: una sola mala noticia te haría mucho daño. "
            "En 🏦 Mi cartera tienes la propuesta para repartir el riesgo pagando lo mínimo en impuestos.",
            "bankinter"))
        hallazgos = [x for x in hallazgos if not patron.match(x["titulo"])]
    for x in [x for x in hallazgos if x["gravedad"] == "alta"][:2]:
        acciones.append(_accion(2, "⚖️", x["titulo"], x["texto"], "bankinter"))
    for x in [x for x in hallazgos if x["gravedad"] == "media" and not x["titulo"].startswith("Sin stop")][:1]:
        acciones.append(_accion(3, "⚖️", x["titulo"], x["texto"], "bankinter"))

    # 4. Movimientos fuertes hoy en lo que tienes (para no decidir en caliente)
    umbral = {"Criptomonedas": 7.0, "Oro y materias primas": 3.0}
    for a in activos or []:
        clase = a.get("clase")
        if clase in umbral and clases.get(clase, 0) > 0 and a.get("var_1d") is not None \
                and abs(a["var_1d"]) >= umbral[clase]:
            sentido = "sube" if a["var_1d"] > 0 else "cae"
            acciones.append(_accion(
                2, "🌪️", f"{a['nombre']} {sentido} un {abs(a['var_1d']):.1f} % hoy".replace(".", ","),
                "Tienes una parte de tu dinero en este activo. Los movimientos bruscos son normales en él: no compres "
                "ni vendas en caliente; si su peso se ha disparado, reequilíbralo con calma en la revisión mensual.",
                "mercados"))

    # 5. Calendario
    if hoy.day <= 3:
        acciones.append(_accion(3, "📦", "Principio de mes: revisa tu cartera modelo",
                                "Las carteras modelo se renuevan una vez al mes. Mira qué acciones entran y salen.",
                                "carteras"))
    for p in posiciones:
        if p.get("resultados_pronto"):
            acciones.append(_accion(3, "📅", f"{p.get('nombre') or p['ticker']} presenta resultados pronto",
                                    "Ese día el precio puede moverse con fuerza. Comprueba tu stop-loss.", "bankinter"))

    for r in dividendos or []:
        if r.get("proximo") and 0 <= (r["proximo"] - hoy).days <= 10:
            importe = f" (≈ {r['proximo_importe']:,.0f} € brutos)".replace(",", ".") if r.get("proximo_importe") else ""
            dia_antes = r["proximo"].toordinal() - 1
            acciones.append(_accion(
                3, "💶", f"{r.get('nombre', r['ticker'])}: dividendo el {r['proximo']:%d/%m}{importe}",
                "Para cobrarlo, ten las acciones al cierre del " + date.fromordinal(dia_antes).strftime("%d/%m")
                + ". Ese día la acción bajará más o menos lo que paga: no es un motivo para comprar ni vender.",
                "bankinter"))
    acciones.sort(key=lambda a: a["prioridad"])
    if not acciones:
        acciones.append(_accion(3, "✅", "Nada urgente hoy",
                                "Tu cartera no necesita cambios. No hacer nada también es una decisión: las operaciones "
                                "innecesarias cuestan comisiones e impuestos.", None))
    return acciones[:maximo]


__all__ = ["plan_del_dia"]
