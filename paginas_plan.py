"""Página 🎯 Mi plan: para qué es el dinero, cuánto, cuándo y qué te interesa → qué hacer hoy con él.

Lee el mercado del mismo día (informe diario, tendencia de divisas, oro, cripto y fondos) y propone, según el
objetivo, ideas concretas con entrada, stop-loss y objetivo (operación), un reparto a largo plazo, rentas con
dividendos o un plan para proteger el dinero. Cada cuenta tiene su propio plan.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from bolsa import asesor, bankinter, plan
from bolsa.activos import LIMITES_ALTERNATIVOS
from paginas_hoy import (COLOR_SEMAFORO, TEXTO_SEMAFORO, bloque_que_puede_pasar, cartera_del_perfil,
                         precio_eur)
from ui_comun import (cargar_activos, cargar_informe, cargar_varios, cuenta_activa, datos_usuario, eur, fx,
                      guardar_datos, ir_a, num, palabras_de_la_pagina, pct, perfil)

PERDIDAS_MAX = [2, 3, 5, 8, 10]


def _cuestionario(cta: dict) -> dict | None:
    previo = cta.get("perfil_inversor", {})
    with st.form("cuestionario"):
        objetivo = st.radio("1️⃣ ¿Para qué es este dinero?", list(plan.OBJETIVOS), format_func=plan.OBJETIVOS.get,
                            index=list(plan.OBJETIVOS).index(previo.get("objetivo", "crecer")))
        c = st.columns(2)
        importe = c[0].number_input("2️⃣ ¿Cuánto dinero? (€)", 0.0, 10_000_000.0, float(previo.get("importe", 5_000.0)),
                                    500.0)
        mensual = c[1].number_input("¿Cuánto podrías añadir cada mes? (€)", 0.0, 100_000.0,
                                    float(previo.get("mensual", 0.0)), 25.0, help="0 si no vas a añadir más.")
        intereses = st.multiselect("3️⃣ ¿Qué te interesa? (puedes elegir varios)", plan.INTERESES,
                                   default=[i for i in previo.get("intereses", []) if i in plan.INTERESES],
                                   placeholder="Si no eliges nada, uso lo habitual para tu objetivo")
        c = st.columns(2)
        plazo = c[0].select_slider("4️⃣ Si es una operación, ¿cuánto tiempo la mantendrías?", list(plan.PLAZOS),
                                   value=previo.get("plazo", "1-3 meses"))
        perdida = c[1].select_slider("Si es una operación, ¿cuánto aceptas perder como máximo? (% del dinero)",
                                     PERDIDAS_MAX, value=previo.get("perdida_max", 5),
                                     help="Si todo sale mal y saltan todos los stop-loss, perderías como mucho esto.")
        horizonte = st.slider("5️⃣ ¿Dentro de cuántos años podrías necesitar este dinero para otra cosa?", 0, 40,
                              int(previo.get("horizonte", 10)))
        reaccion = st.radio("6️⃣ Si lo que compras bajara un 20 % en pocas semanas, ¿qué harías?",
                            list(asesor.REACCIONES),
                            index=list(asesor.REACCIONES).index(previo.get("reaccion", list(asesor.REACCIONES)[1])))
        experiencia = st.radio("7️⃣ Tu experiencia invirtiendo", list(asesor.EXPERIENCIA),
                               index=list(asesor.EXPERIENCIA).index(previo.get("experiencia",
                                                                               list(asesor.EXPERIENCIA)[1])))
        c = st.columns(2)
        colchon = c[0].checkbox("Tengo ahorrados 3-6 meses de gastos aparte de esto", previo.get("colchon", True))
        deudas = c[1].checkbox("Tengo deudas caras (tarjetas, préstamos de más del 7 %)", previo.get("deudas", False))
        if st.form_submit_button("Ver mi plan para hoy", type="primary", width="stretch"):
            cta.pop("perfil_elegido", None)        # el test nuevo manda sobre lo elegido a mano
            st.session_state.pop("perfil_diag", None)
            cta["perfil_inversor"] = {"objetivo": objetivo, "importe": importe, "mensual": mensual,
                                      "intereses": intereses or plan.INTERESES_POR_DEFECTO[objetivo],
                                      "plazo": plazo, "perdida_max": perdida, "horizonte": max(horizonte, 0),
                                      "reaccion": reaccion, "experiencia": experiencia, "colchon": colchon,
                                      "deudas": deudas}
            guardar_datos()
    return cta.get("perfil_inversor")


def _historicos(intereses: list[str]) -> dict[str, pd.DataFrame]:
    tickers = set()
    for clave in ("Oro", "Criptomonedas", "Fondos indexados y ETF"):
        if clave in intereses:
            tickers |= {t for t, _, _ in plan.ALTERNATIVOS[clave]}
    if "Divisas" in intereses:
        tickers |= set(plan.DIVISAS)
    return cargar_varios(tuple(sorted(tickers)), "2y") if tickers else {}


def _mercado_hoy(inf: dict, intereses: list[str], historicos: dict) -> None:
    """Lo que pasa hoy en lo que te interesa, en pocas líneas."""
    with st.container(border=True):
        st.markdown("#### 📡 El mercado hoy")
        mer = inf.get("mercado") or {}
        if mer.get("semaforo"):
            st.markdown(f"**{COLOR_SEMAFORO[mer['semaforo']][1]}.** {TEXTO_SEMAFORO[mer['semaforo']]}")
        lecturas = {a["ticker"]: a for a in (cargar_activos() or [])}
        claves = {"Oro": ["GC=F"], "Criptomonedas": ["BTC-EUR"], "Fondos indexados y ETF": ["IWDA.AS", "^GSPC"]}
        for interes, tickers in claves.items():
            if interes in intereses:
                for t in tickers:
                    if t in lecturas:
                        st.markdown(f"- {lecturas[t]['lectura']}")
        if "Divisas" in intereses:
            for par, (nombre, codigo) in plan.DIVISAS.items():
                t = plan.tendencia(historicos.get(par))
                if t:
                    estado = ("el euro se fortalece" if t["alcista"] else "el euro se debilita" if t["bajista"]
                              else "sin tendencia clara")
                    st.markdown(f"- EUR/{codigo}: {num(t['precio'], 4)}. Tendencia de fondo: {estado} frente "
                                f"{plan.frente_a(codigo)} (último mes {pct((t['var_1m'] or 0) * 100)}).")


def _tarjeta_operacion(p: dict, i: int) -> list[str]:
    """Una idea de la operación; devuelve las órdenes para copiar."""
    pf = perfil()
    ordenes = []
    m = p.get("moneda", "€")
    with st.container(border=True):
        st.markdown(f"**{p['tipo']} · {p['nombre']}**" + (f" · nota {p['nota']}/100" if p.get("nota") else ""))
        st.caption(p["por_que"])
        c = st.columns(2 if pf.movil else 4)
        decimales = 4 if p.get("divisa") else 2
        c[0].metric("Entrada", num(p["entrada"], decimales) + ("" if p.get("divisa") else f" {m}"))
        c[1].metric("Stop-loss", num(p["stop"], decimales), pct(-(p["riesgo_pct"] or 0) * 100), delta_arrow="off")
        c[2 % len(c)].metric("Objetivo", num(p["objetivo"], decimales), pct((p["beneficio_pct"] or 0) * 100),
                             delta_arrow="off")
        c[3 % len(c)].metric("Dinero", eur(p["euros"]))
        texto = (f"Si salta el stop pierdes unos **{eur(p['perdida_si_stop'])}**; si llega al objetivo ganas unos "
                 f"**{eur(p['ganancia_si_objetivo'])}** (antes de comisiones e impuestos).")
        if p["tipo"].startswith("Acción") or p["tipo"] == "Fondo/ETF" or p["tipo"] == "Oro":
            pe = p.get("precio_eur") or (p["precio"] * (fx(p["ticker"]) or 1.0))
            n = int(p["euros"] // pe) if pe else 0
            texto = f"**{n} títulos** de unos {eur(pe)}. " + texto
            if n:
                ordenes.append(bankinter.ticket_compra(p["ticker"], n, p["entrada"], tarifa=pf.tarifa,
                                                       importe_eur=n * pe))
                ordenes.append(bankinter.ticket_stop_relacionadas(p["ticker"], n, p["stop"], p["objetivo"]))
        st.markdown(texto)
        st.caption("💡 Cómo: " + p["como"])
        if p["tipo"].startswith("Acción") and st.button("🔍 Ver análisis completo", key=f"plan_ver_{i}"):
            ir_a("analizar", analizar_ticker=p["ticker"])
    return ordenes


def _plan_operacion(p: dict, perfil_inv, inf: dict, historicos: dict) -> None:
    st.subheader(f"⚡ Tu operación ({p['plazo']})")
    if REACCION_VENDE == p["reaccion"] or p["experiencia"] == list(asesor.EXPERIENCIA)[0]:
        st.warning("Has dicho que venderías ante una caída o que no tienes experiencia: las operaciones a corto plazo "
                   "son lo más difícil de la bolsa. Pruébalo antes en la 🎮 Cartera virtual o pon menos dinero.")
    if (inf.get("mercado") or {}).get("semaforo") == "rojo":
        st.warning("Hoy el mercado está débil: las operaciones a favor de tendencia salen peor. Si entras, usa menos "
                   "dinero o espera a que el semáforo mejore.")
    ranking = inf.get("ranking", [])
    ideas, sin_idea = plan.ideas_del_dia(p["intereses"], ranking, historicos,
                                         con_resultados=plan.PLAZOS[p["plazo"]] > 63)
    r = plan.plan_operacion(p["importe"], p["perdida_max"] / 100, ideas)
    if not r["posiciones"]:
        st.info("Hoy no hay ninguna idea que cumpla las condiciones en lo que te interesa. No pasa nada: no operar "
                "también es una decisión. Prueba a añadir más intereses o vuelve otro día.")
    else:
        c = st.columns(2 if perfil().movil else 4)
        c[0].metric("Invertido", eur(p["importe"] - r["liquidez"]))
        c[1].metric("Se queda en liquidez", eur(r["liquidez"]))
        c[2 % len(c)].metric("Pérdida máxima (todos los stops)", eur(r["riesgo_total"]))
        c[3 % len(c)].metric("Si todo llega al objetivo", eur(r["ganancia_objetivo"]))
        ordenes = []
        for i, pos in enumerate(r["posiciones"]):
            ordenes += _tarjeta_operacion(pos, i)
        if ordenes:
            with st.expander("📋 Órdenes para copiar en tu bróker (compra + stop-loss y objetivo a la vez)"):
                for o in ordenes:
                    st.code(o, language=None)
        for a in r["avisos"]:
            st.caption("ℹ️ " + a)
        st.info(f"⏱️ Revísala cada semana en 🧭 Hoy. Si al cabo de {p['plazo']} no ha llegado ni al stop ni al "
                "objetivo, decide con calma: la idea no ha funcionado como esperabas. Apúntala en 📒 Seguimiento → "
                "Diario para aprender de ella.")
    for s in sin_idea:
        st.caption("ℹ️ " + s)
    st.caption("Con datos reales, la app ha comprobado que adivinar si algo sube o baja en semanas funciona poco "
               "mejor que el azar. Lo que sí ayuda: ir a favor de la tendencia, evitar lo que tiene mucho riesgo de "
               "caída, arriesgar poco en cada idea y respetar el stop-loss. Mira ✅ ¿Acierta la app?")


REACCION_VENDE = list(asesor.REACCIONES)[0]


def _plan_rentas(p: dict, perfil_inv, inf: dict) -> None:
    st.subheader("💶 Tu plan de rentas")
    ideas = plan.ideas_dividendo(inf.get("ranking", []))
    lecturas = {a["ticker"]: a for a in (cargar_activos() or [])}
    interes = max((lecturas.get("XEON.DE", {}).get("var_1a") or 2.0) / 100, 0.0)
    r = plan.plan_rentas(p["importe"], perfil_inv.nombre, ideas, interes)
    c = st.columns(2 if perfil().movil else 3)
    c[0].metric("Cobrarías al año (bruto)", eur(r["renta_anual"]), pct(r["rentabilidad"] * 100, 1),
                delta_arrow="off")
    c[1].metric("Neto tras el 19 % de retención", eur(r["renta_anual"] * 0.81))
    c[2 % len(c)].metric("Al mes (neto)", eur(r["renta_anual"] * 0.81 / 12))
    if r["acciones"]:
        st.markdown(f"**Acciones con buen dividendo** ({eur(sum(a['euros'] for a in r['acciones']))}):")
        st.dataframe(pd.DataFrame([{"Empresa": a["nombre"], "Sector": a.get("sector"), "Dividendo": pct(
            a["dividendo"] * 100, 1, False), "Euros": eur(a["euros"]), "Cobrarías/año": eur(a["euros"] * a["dividendo"]),
            "Riesgo de caída": a.get("riesgo_nivel", "—")} for a in r["acciones"]]), hide_index=True, width="stretch")
        for a in r["acciones"]:
            st.caption(f"• {a['nombre']}: {a['por_que']}")
    st.markdown(f"**Renta fija y letras** ({eur(r['renta_fija'])}): Letras del Tesoro, un fondo monetario o deuda a "
                f"corto plazo, que hoy pagan alrededor de un {pct(interes * 100, 1, False)} al año casi sin riesgo.")
    st.caption("Un dividendo no está garantizado: la empresa puede bajarlo. Repartir entre varias empresas de sectores "
               "distintos lo hace mucho más estable.")
    pesos = {a["ticker"]: a["euros"] for a in r["acciones"]}
    if r["renta_fija"]:
        pesos["IBGS.AS"] = r["renta_fija"]
    st.subheader("🔮 ¿Qué podría pasar?")
    total = sum(pesos.values())
    bloque_que_puede_pasar({t: v / total for t, v in pesos.items()}, p["importe"], 0.0, p["horizonte"])


def _plan_proteger(p: dict) -> None:
    st.subheader("🛡️ Tu plan para proteger el dinero")
    partes = plan.plan_proteger(p["importe"], oro=True)
    lecturas = {a["ticker"]: a for a in (cargar_activos() or [])}
    que = {"Monetario / Letras del Tesoro": asesor.PRODUCTOS["Monetario / Letras del Tesoro"]["que"],
           "Renta fija a corto plazo": asesor.PRODUCTOS["Renta fija a corto plazo"]["que"],
           "Oro": "Un poco de oro (ETC de oro físico, código 4GLD) protege en crisis y frente a la inflación."}
    for x in partes:
        with st.container(border=True):
            c = st.columns([3, 1])
            c[0].markdown(f"**{x['parte']}** · {x['pct']} %")
            c[1].markdown(f"**{eur(x['euros'])}**")
            st.caption(que[x["parte"]])
    interes = lecturas.get("XEON.DE", {}).get("var_1a")
    if interes is not None:
        st.caption(f"El monetario en euros ha dado un {pct(interes, 1)} en el último año: es lo que pagan hoy los "
                   "tipos de interés.")
    st.subheader("🔮 ¿Qué podría pasar?")
    bloque_que_puede_pasar({x["ticker"]: x["pct"] / 100 for x in partes}, p["importe"], p["mensual"], p["horizonte"])


def _plan_crecer(p: dict, perfil_inv, inf: dict, historicos: dict) -> None:
    pf = perfil()
    ranking = {r["ticker"]: r for r in inf.get("ranking", [])}
    minimo = asesor.MINIMO_POR_ACCION_CERO if pf.tarifa.broker_cero else asesor.MINIMO_POR_ACCION
    propia = cartera_del_perfil(inf) if inf else None
    if "Acciones españolas" not in p["intereses"]:
        candidatas = []
    elif propia:
        candidatas = [ranking[x["ticker"]] for x in propia[1]["composicion"] if x["ticker"] in ranking]
    else:
        candidatas = [ranking[t] for t in inf.get("ideas_es", []) if t in ranking]
    candidatas = [r for r in candidatas if precio_eur(r)]
    plan_base = asesor.plan_inversion(p["importe"], p["mensual"], perfil_inv, candidatas, minimo)
    if "Acciones españolas" not in p["intereses"] and plan_base["reparto"].get("Acciones individuales"):
        plan_base["avisos"].append("Como no te interesan las acciones sueltas, esa parte va al fondo indexado.")
    fase = inf.get("mercado", {}).get("fases", {}).get("^IBEX", {}).get("fase")
    st.info("⏱️ " + asesor.ritmo_de_entrada(fase))

    # Satélites: un poco de oro o cripto si te interesan, quitándolo del fondo indexado.
    sat = plan.satelites(perfil_inv.nombre, p["intereses"], LIMITES_ALTERNATIVOS) if perfil_inv.invertir_en_bolsa else {}
    lineas = [dict(x) for x in plan_base["lineas"]]
    fondo = next((x for x in lineas if x["parte"] == "Fondo indexado mundial"), None)
    for nombre, w in sat.items():
        if fondo and fondo["pct"] > w * 100:
            fondo["pct"] -= w * 100
            fondo["euros"] -= p["importe"] * w
            ticker, _, como = plan.ALTERNATIVOS[nombre][0]
            t = plan.tendencia(historicos.get(ticker))
            hoy = ("Hoy está en tendencia alcista: puedes entrar ya." if t and t["alcista"] else
                   "Hoy no está en tendencia alcista: entra poco a poco, en 3-4 meses." if t else "")
            lineas.append({"parte": nombre, "pct": round(w * 100), "euros": p["importe"] * w, "ticker": ticker,
                           "que": f"{como} Máximo prudente para un perfil {perfil_inv.nombre.lower()}. {hoy}"})

    st.subheader("Reparto propuesto")
    for x in lineas:
        with st.container(border=True):
            c = st.columns([3, 1])
            c[0].markdown(f"**{x['parte']}** · {x['pct']:.0f} %")
            c[1].markdown(f"**{eur(x['euros'])}**")
            st.caption(x["que"])
    for a in plan_base["avisos"]:
        st.caption("ℹ️ " + a)
    if plan_base["acciones"]:
        nombre_cartera = propia[1]["nombre"] if propia else "Ideas del día"
        st.markdown(f"**Acciones individuales — {nombre_cartera}** (españolas, sectores distintos, revisión mensual):")
        filas, ordenes = [], []
        for a in plan_base["acciones"]:
            pe = precio_eur(a)
            n = int(a["euros"] // pe) if pe else 0
            filas.append({"Empresa": a["nombre"], "Sector": a["sector"], "Títulos": n,
                          "Precio": round(a["precio"], 2), "Importe": eur(n * pe) if pe else "—",
                          "Stop-loss": round(a["stop"], 2) if a.get("stop") else None})
            if n:
                ordenes.append(bankinter.ticket_compra(a["ticker"], n, a["precio"], tarifa=pf.tarifa,
                                                       importe_eur=n * pe))
                if a.get("stop"):
                    ordenes.append(bankinter.ticket_stop(a["ticker"], n, a["stop"]))
        st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch")
        with st.expander("📋 Órdenes para copiar en tu bróker"):
            for o in ordenes:
                st.code(o, language=None)
    if "Acciones de Europa y EEUU" in p["intereses"]:
        fuera = plan.ideas_acciones(inf.get("ranking", []), nacionales=False, n=3)
        if fuera:
            with st.expander("🌍 Empresas de fuera con buena nota hoy"):
                st.caption("En Bankinter cada compra fuera de España cuesta unos 20 € más el cambio de divisa y la "
                           "custodia: solo compensan con importes grandes (unos 5.000 € por empresa).")
                for x in fuera:
                    st.markdown(f"- **{x['nombre']}** ({x['sector']}): {x['por_que']}")
    if "Divisas" in p["intereses"]:
        st.caption("💱 Divisas a largo plazo: el fondo indexado mundial ya invierte en dólares, libras, yenes... "
                   "(unos dos tercios fuera del euro), así que no hace falta cambiar de moneda aparte.")
    if p["mensual"]:
        st.markdown(f"**Cada mes:** {eur(plan_base['mensual_fondo'])} al fondo indexado"
                    + (f" y {eur(plan_base['mensual_seguro'])} a la parte segura"
                       if plan_base["mensual_seguro"] > 0 else "") + ".")
        st.caption("Puedes programarlo en 📒 Seguimiento → Aportación mensual, y en tu banco como aportación periódica.")
    st.subheader("🔮 ¿Qué podría pasar con este plan?")
    pesos = asesor.pesos_para_escenarios(plan_base)
    for x in lineas:
        if x["parte"] in sat and x.get("ticker"):
            pesos[x["ticker"]] = x["pct"] / 100
    if fondo and "IWDA.AS" in pesos:
        pesos["IWDA.AS"] = fondo["pct"] / 100
    bloque_que_puede_pasar(pesos, p["importe"], p["mensual"], p["horizonte"])


def pagina_plan():
    d = datos_usuario()
    cta = cuenta_activa()
    varias = len(d.get("cuentas", {})) > 1
    st.title("🎯 Mi plan" + (f" · 👤 {d['cuenta_activa']}" if varias else ""))
    st.caption("Dime para qué es el dinero y la app te propone qué hacer hoy con él, leyendo el mercado del día: "
               "empresas concretas, divisas, oro, cripto o fondos, según tu objetivo y lo que te interese.")
    p = _cuestionario(cta)
    if not p:
        return
    p = {**p, "objetivo": p.get("objetivo", "crecer"), "intereses": p.get("intereses") or
         plan.INTERESES_POR_DEFECTO[p.get("objetivo", "crecer")], "plazo": p.get("plazo", "1-3 meses"),
         "perdida_max": p.get("perdida_max", 5), "mensual": p.get("mensual", 0.0)}
    perfil_inv = asesor.perfil_inversor(p["horizonte"], p["reaccion"], p["experiencia"], p["colchon"],
                                        p.get("deudas", False))
    st.header(f"{plan.OBJETIVOS[p['objetivo']]}")
    st.caption(f"Perfil {perfil_inv.nombre.lower()} · " + " · ".join(perfil_inv.motivos))
    for a in perfil_inv.alertas:
        if p["objetivo"] == "operacion" and a.startswith("Con menos de 2 años"):
            a = ("Para una operación, usa solo dinero que puedas permitirte perder: si lo necesitas pronto, mejor "
                 "Letras del Tesoro o un monetario.")
        st.warning(a)
    inf = cargar_informe() or {}
    historicos = _historicos(p["intereses"]) if p["objetivo"] in ("operacion", "crecer") else {}
    _mercado_hoy(inf, p["intereses"], historicos)
    if p["objetivo"] == "operacion":
        _plan_operacion(p, perfil_inv, inf, historicos)
    elif p["objetivo"] == "rentas":
        _plan_rentas(p, perfil_inv, inf)
    elif p["objetivo"] == "proteger" or not perfil_inv.invertir_en_bolsa:
        if p["objetivo"] != "proteger":
            st.info("Como vas a necesitar el dinero pronto, lo prudente es protegerlo en vez de invertirlo en bolsa.")
        _plan_proteger(p)
    else:
        _plan_crecer(p, perfil_inv, inf, historicos)
    palabras_de_la_pagina(["Stop-loss", "Objetivo de precio", "Fondo indexado", "Dividendo", "Diversificación",
                           "Letras del Tesoro", "Tendencia", "Cambio de divisa"])
