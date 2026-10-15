"""Páginas basadas en el informe diario: Hoy, Mi plan, Radar global y bloques de "qué puede pasar"."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from bolsa import asesor, bankinter, patrones
from bolsa.costes import simular_aportaciones
from bolsa.tickers import MERCADOS, TODAS_LAS_ACCIONES, nombre_de
from paginas_extra import avisos_resumen
from ui_comun import (cargar_informe, cargar_varios, datos_usuario, dias_informe, eur, guardar_datos, ir_a,
                      moneda_de, pct, perfil)

COLOR_SEMAFORO = {"verde": ("success", "🟢 VERDE · Mercado favorable"),
                  "ambar": ("warning", "🟡 ÁMBAR · Mercado mixto"),
                  "rojo": ("error", "🔴 ROJO · Mercado débil o nervioso")}
TEXTO_SEMAFORO = {
    "verde": "La mayoría de bolsas suben con calma. Buen entorno para invertir de forma escalonada.",
    "ambar": "Unas bolsas van bien y otras no. Sé selectivo, entra poco a poco y usa siempre stop-loss.",
    "rojo": "La mayoría de índices están en tendencia bajista o hay mucho miedo. Lo prudente: no tener prisa, "
            "y si inviertes a largo plazo, seguir solo con aportaciones pequeñas y periódicas.",
}


def sin_informe():
    st.info("📭 Todavía no hay **informe diario**. Se genera solo cada día laborable al cierre de Wall Street "
            "(GitHub Actions → 'Actualización diaria'). Mientras tanto, puedes usar 🔍 Analizar, 📰 Noticias y "
            "🌍 Mercados, que descargan los datos en directo.")


def aviso_antiguedad(inf: dict):
    dias = dias_informe(inf)
    st.caption(f"📅 Datos al cierre del **{inf['datos_hasta']}** · {inf['cobertura']['acciones']} valores, "
               f"{inf['cobertura']['noticias']} noticias · se actualiza solo cada día laborable")
    if dias > 4:
        st.warning(f"El informe tiene {dias} días. Revisa que la actualización diaria de GitHub esté funcionando.")


def texto_fase(nombre: str, f: dict) -> str:
    h = f.get("horizontes", {}).get("1 mes", {})
    if not h.get("prob_sube"):
        return f"**{nombre}**: fase «{f.get('fase', '—')}»."
    return (f"**{nombre}** está en fase **«{f['fase']}»** desde el {f['desde']}. En las {h['casos']} ocasiones "
            f"parecidas desde {f['historia_desde'][:4]}, un mes después **subió el {h['prob_sube'] * 100:.0f}%** de las "
            f"veces; lo normal fue entre {pct(h['p10'] * 100, 1)} y {pct(h['p90'] * 100, 1)}, y la peor vez "
            f"{pct(h['peor'] * 100, 1)}.")


ICONO_RIESGO = {"bajo": "🟢 bajo", "normal": "🟡 normal", "alto": "🔴 alto", None: "—"}


def tarjeta_idea(r: dict, clave: str):
    pf = perfil()
    m = moneda_de(r["ticker"])
    with st.container(border=True):
        st.markdown(f"**{r['nombre']}**  \n{r['sector']} · {r['mercado']}")
        if r.get("nota") is not None:
            st.metric("Nota global", f"{r['nota']}/100", f"puesto {r['puesto']} de {r['de']}", delta_color="off")
        else:
            st.metric("Puntuación", f"{r['puntuacion']}/100")
        detalles = []
        if r.get("momentum") is not None:
            detalles.append(f"último año {pct(r['momentum'] * 100, 0)}")
        if r.get("riesgo_nivel"):
            detalles.append(f"riesgo de caída {ICONO_RIESGO[r['riesgo_nivel']]}")
        if detalles:
            st.caption(" · ".join(detalles))
        if r.get("stop"):
            st.caption(f"Precio {eur(r['precio'], m)} · stop-loss {eur(r['stop'], m)}")
        positivos = [mo["t"] for mo in r.get("motivos", []) if mo["p"] > 0][:2]
        if positivos and not pf.movil:
            st.caption("Por qué: " + "; ".join(positivos))
        if st.button("Ver análisis completo", key=f"idea_{clave}_{r['ticker']}", width="stretch"):
            ir_a("analizar", analizar_ticker=r["ticker"])


def texto_proteccion(t: str, p: dict) -> str:
    if p.get("estado") == "dentro":
        return (f"🟢 **{nombre_de(t)}**: seguir invertido (desde el {p['desde']}). Se saldría si baja de "
                f"{p['salir_si_baja_de']:,.0f} ({pct((p['salir_si_baja_de'] / p['precio'] - 1) * 100, 1)}).").replace(",", ".")
    if p.get("estado") == "fuera":
        return (f"🔴 **{nombre_de(t)}**: la regla dice estar fuera (desde el {p['desde']}). Se volvería a entrar si "
                f"supera {p['entrar_si_sube_de']:,.0f} ({pct((p['entrar_si_sube_de'] / p['precio'] - 1) * 100, 1)}).").replace(",", ".")
    return f"⚪ **{nombre_de(t)}**: sin datos suficientes."


# --------------------------------------------------------------------------- 🧭 Hoy
def pagina_hoy():
    pf = perfil()
    st.title("🧭 Hoy")
    inf = cargar_informe()
    avisos_resumen()
    if not inf:
        sin_informe()
        return
    aviso_antiguedad(inf)
    mer = inf["mercado"]
    tipo, titulo = COLOR_SEMAFORO[mer["semaforo"]]
    getattr(st, tipo)(f"**{titulo}.** {TEXTO_SEMAFORO[mer['semaforo']]}")

    st.subheader("En pocas palabras")
    for f in inf["resumen"]:
        st.markdown(f"- {f}")

    st.subheader("💡 Ideas del día")
    por_ticker = {r["ticker"]: r for r in inf["ranking"]}
    ideas = [por_ticker[t] for t in inf.get("ideas", []) if t in por_ticker]
    if ideas:
        st.caption("Las acciones con mejor puntuación, **de sectores distintos**, cuyo mercado acompaña y que no "
                   "presentan resultados en los próximos días. Antes de comprar, mira el análisis completo.")
        cols = st.columns(1 if pf.movil else min(len(ideas), 3))
        for i, r in enumerate(ideas):
            with cols[i % len(cols)]:
                tarjeta_idea(r, "hoy")
    else:
        st.info("Hoy ninguna acción cumple todas las condiciones. No pasa nada: la opción más segura sigue siendo "
                "la aportación mensual a un ETF mundial (mira 🧭 Mi plan).")

    prot = inf.get("proteccion", {})
    if prot:
        st.subheader("🛡️ Regla de protección de los índices")
        for t, p in prot.items():
            st.markdown("- " + texto_proteccion(t, p))
        st.caption("Regla sencilla con 100 años de historia: seguir invertido mientras el índice esté por encima de su "
                   "media de 200 sesiones y salir solo si cae más de un 2% por debajo. Redujo a casi la mitad las peores "
                   "caídas con una rentabilidad parecida. Más detalle en 📦 Carteras modelo.")
    carteras = inf.get("carteras", {})
    if carteras:
        st.subheader("📦 Carteras modelo de este mes")
        for c in carteras.values():
            nombres = [por_ticker.get(x["ticker"], {}).get("nombre", x["ticker"]) for x in c["composicion"]]
            st.markdown(f"- **{c['nombre']}** (perfil {c['perfil'].lower()}): "
                        + (", ".join(nombres[:6]) + ("…" if len(nombres) > 6 else "") if nombres else
                           "este mes en liquidez (mercados en tendencia bajista)"))
        if st.button("Ver carteras modelo y cómo replicarlas", width="stretch"):
            ir_a("carteras")

    st.subheader("🔮 Qué puede pasar")
    for t, nombre in (("^IBEX", "El IBEX 35"), ("^GSPC", "El S&P 500"), ("^STOXX50E", "El Euro Stoxx 50")):
        f = mer.get("fases", {}).get(t)
        if f:
            st.markdown("- " + texto_fase(nombre, f))
    st.caption("Son estadísticas de lo que pasó en el pasado en situaciones parecidas, no una garantía.")

    st.subheader("📰 Lo más importante")
    for n in inf["noticias"]["top"][:3]:
        icono = {1: "🟢", -1: "🔴", 0: "⚪"}[n["sentimiento"]]
        st.markdown(f"{icono} [{n['titulo']}]({n['enlace']})")
        if n["explicaciones"]:
            st.caption("💡 " + n["explicaciones"][0])

    mr = inf.get("modelo_riesgo", {}).get("metricas")
    if mr:
        st.caption(f"🤖 Los modelos se reentrenan cada noche con {mr['casos']:,} situaciones de {mr['acciones']} valores. ".replace(",", ".")
                   + "Con datos reales, predecir si una acción subirá es casi imposible, pero el **riesgo de caída fuerte** "
                   f"sí se puede estimar (AUC {mr['auc']:.2f}): por eso las ideas evitan las de riesgo alto.")


# --------------------------------------------------------------------------- 🧭 Mi plan
def pagina_plan():
    st.title("🎯 Mi plan: dónde invertir")
    st.caption("Responde 6 preguntas y la app te propone un reparto concreto en euros, con productos que puedes "
               "comprar en Bankinter, y te enseña qué podría pasar con él.")
    d = datos_usuario()
    previo = d.get("perfil_inversor", {})
    with st.form("cuestionario"):
        c = st.columns(2)
        importe = c[0].number_input("¿Cuánto quieres invertir ahora? (€)", 0.0, 10_000_000.0,
                                    float(previo.get("importe", 5_000.0)), 500.0)
        mensual = c[1].number_input("¿Cuánto podrías aportar cada mes? (€)", 0.0, 100_000.0,
                                    float(previo.get("mensual", 150.0)), 25.0)
        horizonte = st.slider("¿Dentro de cuántos años podrías necesitar este dinero?", 1, 40,
                              int(previo.get("horizonte", 10)))
        reaccion = st.radio("Si tu inversión bajara un 20% en pocas semanas, ¿qué harías?", list(asesor.REACCIONES),
                            index=list(asesor.REACCIONES).index(previo.get("reaccion", list(asesor.REACCIONES)[1])))
        experiencia = st.radio("Tu experiencia invirtiendo", list(asesor.EXPERIENCIA),
                               index=list(asesor.EXPERIENCIA).index(previo.get("experiencia", list(asesor.EXPERIENCIA)[1])))
        c = st.columns(2)
        colchon = c[0].checkbox("Tengo ahorrados 3-6 meses de gastos aparte de esto", previo.get("colchon", True))
        deudas = c[1].checkbox("Tengo deudas caras (tarjetas, préstamos >7%)", previo.get("deudas", False))
        if st.form_submit_button("Ver mi plan", type="primary", width="stretch"):
            d["perfil_inversor"] = {"importe": importe, "mensual": mensual, "horizonte": horizonte,
                                    "reaccion": reaccion, "experiencia": experiencia, "colchon": colchon,
                                    "deudas": deudas}
            guardar_datos()
    p = d.get("perfil_inversor")
    if not p:
        return
    perfil_inv = asesor.perfil_inversor(p["horizonte"], p["reaccion"], p["experiencia"], p["colchon"], p["deudas"])
    st.header(f"Tu perfil: {perfil_inv.nombre}")
    for mo in perfil_inv.motivos:
        st.caption("· " + mo)
    for a in perfil_inv.alertas:
        st.warning(a)

    inf = cargar_informe()
    ranking = {r["ticker"]: r for r in (inf["ranking"] if inf else [])}
    cartera_perfil = next((c for c in (inf or {}).get("carteras", {}).values()
                           if c["perfil"] == perfil_inv.nombre), None)
    if cartera_perfil:
        candidatas = [ranking[x["ticker"]] for x in cartera_perfil["composicion"] if x["ticker"] in ranking]
        ideas = asesor.ideas_diversificadas(candidatas, max_ideas=10, min_puntuacion=0, max_por_sector=2)
    else:
        ideas = [ranking[t] for t in (inf or {}).get("ideas", []) if t in ranking]
    plan = asesor.plan_inversion(p["importe"], p["mensual"], perfil_inv, ideas)
    fase = (inf or {}).get("mercado", {}).get("fases", {}).get("^IBEX", {}).get("fase")
    st.info("⏱️ " + asesor.ritmo_de_entrada(fase))

    st.subheader("Reparto propuesto")
    for l in plan["lineas"]:
        with st.container(border=True):
            c = st.columns([3, 1])
            c[0].markdown(f"**{l['parte']}** · {l['pct']}%")
            c[1].markdown(f"**{eur(l['euros'])}**")
            st.caption(l["que"] + (f" Ejemplo en Bankinter: **{nombre_de(l['ticker'])}** ({l['ticker']})."
                                   if l["ticker"] else ""))
    for a in plan["avisos"]:
        st.caption("ℹ️ " + a)
    if plan["acciones"]:
        if cartera_perfil:
            m = cartera_perfil["metricas"]
            st.markdown(f"**Acciones individuales: las primeras de la {cartera_perfil['nombre']}**, la que encaja con "
                        f"tu perfil. En la simulación desde 2017 ganó {pct(m['cagr_pct'], 1)} al año con una peor caída "
                        f"de {pct(m['max_caida_pct'], 0)}. Revísala una vez al mes (📦 Carteras modelo).")
        else:
            st.markdown("**Acciones individuales sugeridas hoy** (sectores distintos, con stop-loss):")
        filas = []
        for a in plan["acciones"]:
            n = int(a["euros"] // a["precio"]) if a.get("precio") else 0
            filas.append({"Empresa": a["nombre"], "Sector": a["sector"], "Importe": eur(a["euros"]),
                          "Acciones": n, "Precio": round(a["precio"], 2), "Stop-loss": round(a["stop"], 2)
                          if a.get("stop") else None, "Puntuación": a["puntuacion"]})
        st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch")
        with st.expander("📋 Órdenes para copiar en Bankinter"):
            for a in plan["acciones"]:
                n = int(a["euros"] // a["precio"]) if a.get("precio") else 0
                if n:
                    st.code(bankinter.ticket(a["ticker"], "Compra", n, round(a["precio"], 2), a.get("stop"),
                                             a.get("objetivo")), language=None)
    if p["mensual"]:
        st.markdown(f"**Cada mes:** {eur(plan['mensual_etf'])} al ETF mundial"
                    + (f" y {eur(plan['mensual_seguro'])} a la parte segura" if plan["mensual_seguro"] > 0 else "")
                    + ". Muchos brokers permiten programarlo como plan periódico.")

    st.subheader("🔮 ¿Qué podría pasar con este plan?")
    pesos = asesor.pesos_para_escenarios(plan)
    bloque_que_puede_pasar(pesos, p["importe"], p["mensual"], p["horizonte"])


def bloque_que_puede_pasar(pesos: dict[str, float], importe: float, mensual: float = 0.0, anos: int = 10):
    """Escenarios a 1 año (con la historia real de esos productos) y pruebas de estrés en crisis reales."""
    pf = perfil()
    if not pesos or importe <= 0:
        st.caption("Introduce un importe para ver escenarios.")
        return
    with st.spinner("Calculando escenarios con 10 años de historia real..."):
        hist = cargar_varios(tuple(sorted(pesos)), "10y")
        rets = patrones.rentabilidades_cartera(hist, pesos)
        esc = patrones.escenarios(rets)
        estres = patrones.prueba_estres(hist, pesos)
    if not esc:
        st.caption("No hay historia suficiente para calcular escenarios.")
        return
    c = st.columns(1 if pf.movil else 3)
    c[0].metric("Año malo (1 de cada 20)", eur(importe * (1 + esc["p5"])), pct(esc["p5"] * 100, 1))
    c[1 % len(c)].metric("Año normal", eur(importe * (1 + esc["p50"])), pct(esc["p50"] * 100, 1))
    c[2 % len(c)].metric("Año bueno (1 de cada 20)", eur(importe * (1 + esc["p95"])), pct(esc["p95"] * 100, 1))
    st.caption(f"Probabilidad de acabar un año en pérdidas: **{esc['prob_perdida'] * 100:.0f}%**. "
               f"Durante el año, lo normal es ver en algún momento una caída de {pct(esc['caida_tipica'] * 100, 0)}, "
               f"y en un año malo de {pct(esc['caida_mala'] * 100, 0)}. "
               f"(Calculado remuestreando {esc['anos_historia']} años de historia real de estos productos.)")
    if estres:
        st.markdown("**Si se repitiera una crisis real:**")
        st.dataframe(pd.DataFrame([{"Crisis": e["crisis"], "Cambio": pct(e["cambio"] * 100, 1),
                                    "Tus euros": eur(importe * e["cambio"])} for e in estres]),
                     hide_index=True, width="stretch")
        st.caption("Todas estas crisis se recuperaron con el tiempo, pero solo quien no vendió con pánico lo vivió.")
    if mensual or anos:
        rent = max(min(esc["p50"] * 100, 9.0), 0.0)
        filas = simular_aportaciones(mensual, anos, rent, importe)
        f = filas[-1]
        st.caption(f"Proyección a {anos} años con un rendimiento anual de {rent:.1f}% (el escenario normal): "
                   f"aportarías {eur(f['Aportado'])} y tendrías unos **{eur(f['Valor'])}**. No está garantizado.")


# --------------------------------------------------------------------------- 📡 Radar global
def pagina_radar_global() -> bool:
    """Radar con todas las empresas del informe. Devuelve False si no hay informe."""
    pf = perfil()
    inf = cargar_informe()
    if not inf:
        return False
    st.title("📡 Radar: todas las empresas")
    aviso_antiguedad(inf)
    df = pd.DataFrame(inf["ranking"])
    ideas = set(inf.get("ideas", []))
    c = st.columns(1 if pf.movil else 3)
    mercados = c[0].multiselect("Mercados", list(MERCADOS), default=[m for m in MERCADOS if m != "ETF"])
    sectores = sorted(df["sector"].dropna().unique())
    sector = c[1 % len(c)].selectbox("Sector", ["Todos"] + sectores)
    solo = c[2 % len(c)].toggle("Solo candidatas (nota ≥75, riesgo no alto)", value=False)
    buscar = st.text_input("Buscar empresa", "").strip().lower()
    f = df[df["mercado"].isin(mercados)]
    if sector != "Todos":
        f = f[f["sector"] == sector]
    if solo:
        f = f[(f["nota"].fillna(0) >= 75) & (f["puntuacion"] >= 55) & (f["riesgo_nivel"] != "alto")]
    if buscar:
        f = f[f["nombre"].str.lower().str.contains(buscar) | f["ticker"].str.lower().str.contains(buscar)]
    tabla = pd.DataFrame({
        "": ["⭐" if t in ideas else "" for t in f["ticker"]],
        "Empresa": f["nombre"], "Mercado": f["mercado"], "Nota": f.get("nota"),
        "Riesgo caída": f["riesgo_nivel"].map(ICONO_RIESGO) if "riesgo_nivel" in f else None,
        "Último año %": (f["momentum"] * 100).round(0) if "momentum" in f else None,
        "Técnica": f["puntuacion"], "Veredicto": f["veredicto"],
        "Hoy %": f["var_1d"].round(2),
        "Analistas %": (f["potencial_analistas"] * 100).round(1), "PER": f["per"].round(1),
        "Dividendo %": (f["dividendo"] * 100).round(1), "Ticker": f["ticker"],
    })
    if pf.movil:
        tabla = tabla[["", "Empresa", "Nota", "Riesgo caída", "Hoy %", "Ticker"]]
    st.caption(f"{len(tabla)} valores, ordenados por **nota global**: el puesto de cada acción combinando su "
               "momentum del último año (50%), su puntuación técnica (30%) y su menor riesgo de caída (20%), que es "
               "lo que ha funcionado con datos reales. ⭐ = idea del día. **Toca una fila** para ver su análisis.")
    sel = st.dataframe(tabla, hide_index=True, width="stretch", height=min(38 * len(tabla) + 40, 900),
                       on_select="rerun", selection_mode="single-row",
                       column_config={"Nota": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d"),
                                      "Ticker": None if not pf.movil else st.column_config.TextColumn(width="small")})
    filas = sel.selection.rows if sel and sel.selection else []
    if filas:
        ir_a("analizar", analizar_ticker=tabla.iloc[filas[0]]["Ticker"])
    return True


# --------------------------------------------------------------------------- bloques para Analizar
def bloque_modelo_conjunto(ticker: str, fila: dict | None):
    inf = cargar_informe()
    if not inf or not fila:
        return
    st.markdown("**🤖 Lo que dicen los modelos entrenados con todas las empresas**")
    c = st.columns(2)
    if fila.get("nota") is not None:
        c[0].metric("Nota global", f"{fila['nota']}/100", f"puesto {fila['puesto']} de {fila['de']}", delta_color="off",
                    help="Combina momentum del último año, puntuación técnica y riesgo de caída.")
    mr = inf.get("modelo_riesgo", {})
    if fila.get("riesgo_caida") is not None and mr:
        base = mr["metricas"]["tasa_subidas"]
        c[1].metric("Riesgo de caída >10% en 1 mes", f"{fila['riesgo_caida'] * 100:.0f}%",
                    f"lo normal: {base * 100:.0f}%", delta_color="off")
        st.caption(f"Nivel de riesgo: **{ICONO_RIESGO.get(fila.get('riesgo_nivel'))}**. Este modelo sí distingue el "
                   f"riesgo en años que no había visto (AUC {mr['metricas']['auc']:.2f}; 0,5 sería azar). "
                   f"Fiabilidad: {mr['fiabilidad'].lower()}.")
    m = inf["modelo"]
    if fila.get("prob_modelo") is not None:
        st.caption(f"Predecir si subirá es mucho más difícil: el modelo de dirección da un "
                   f"{fila['prob_modelo'] * 100:.0f}% de probabilidad de subir en 1 mes, pero su fiabilidad es "
                   f"**{m['fiabilidad'].lower()}** (AUC {m['metricas']['auc']:.2f}). Tómalo solo como referencia.")


def bloque_que_puede_pasar_accion(ticker: str, df: pd.DataFrame, importe: float):
    """Escenarios a 1 año y crisis reales para una sola acción."""
    pf = perfil()
    rets = df["Close"].pct_change().dropna()
    esc = patrones.escenarios(rets)
    estres = patrones.prueba_estres({ticker: df}, {ticker: 1.0})
    if not esc:
        return
    st.caption(f"Con {eur(importe)} invertidos durante 1 año, según {esc['anos_historia']} años de su historia:")
    c = st.columns(1 if pf.movil else 3)
    c[0].metric("Año malo (1 de cada 20)", pct(esc["p5"] * 100, 0), eur(importe * esc["p5"]), delta_color="off")
    c[1 % len(c)].metric("Año normal", pct(esc["p50"] * 100, 0), eur(importe * esc["p50"]), delta_color="off")
    c[2 % len(c)].metric("Año bueno (1 de cada 20)", pct(esc["p95"] * 100, 0), eur(importe * esc["p95"]),
                         delta_color="off")
    if estres:
        st.caption("En crisis reales: " + " · ".join(f"{e['crisis']}: {pct(e['cambio'] * 100, 0)}" for e in estres))


def bloque_fases(inf: dict | None):
    if not inf:
        return
    mer = inf["mercado"]
    st.subheader("🧭 Fase de cada mercado y qué pasó después en el pasado")
    for t in ("^IBEX", "^STOXX50E", "^GSPC"):
        f = mer.get("fases", {}).get(t)
        if not f:
            continue
        with st.container(border=True):
            st.markdown(texto_fase(nombre_de(t), f))
            st.caption(f["explicacion"])
            filas = []
            for h, s in f["horizontes"].items():
                if s.get("prob_sube") is None:
                    continue
                g = f["todas"][h]
                filas.append({"Plazo": h, "Subió (esta fase)": f"{s['prob_sube'] * 100:.0f}%",
                              "Subió (siempre)": f"{g['prob_sube'] * 100:.0f}%",
                              "Lo normal": f"{pct(s['p10'] * 100, 0)} a {pct(s['p90'] * 100, 0)}",
                              "Peor caso": pct(s["peor"] * 100, 0), "Casos": s["casos"]})
            if filas:
                st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch")
    with st.expander("📉 Las peores caídas de la historia y cuánto tardaron en recuperarse"):
        for t in ("^IBEX", "^GSPC"):
            caidas = mer.get("peores_caidas", {}).get(t, [])
            if caidas:
                st.markdown(f"**{nombre_de(t)}**")
                st.dataframe(pd.DataFrame([{
                    "Empezó": c["inicio"], "Fondo": c["fondo"], "Caída": pct(c["caida"] * 100, 0),
                    "Recuperado": c["recuperado"] or "aún no",
                    "Años en recuperar": f"{c['dias_recuperar'] / 365:.1f}" if c["dias_recuperar"] else "—"}
                    for c in caidas]), hide_index=True, width="stretch")
        st.caption("Lección: las caídas fuertes ocurren cada pocos años. Quien invierte a largo plazo y no vende "
                   "con pánico ha acabado recuperándose; quien necesitaba el dinero en mal momento, no.")


# --------------------------------------------------------------------------- resultados del entrenamiento diario
def bloque_entrenamiento_diario():
    inf = cargar_informe()
    if not inf:
        sin_informe()
        return
    pf = perfil()
    e = inf["estrategia"]
    m = inf["modelo"]
    st.markdown(f"Cada noche el modelo conjunto se reentrena con **{m['metricas']['casos']:,}".replace(",", ".")
                + f" situaciones de {m['metricas']['acciones']} valores**, y cada semana la estrategia prueba "
                f"**{e.get('iteraciones', '—')} combinaciones de reglas** con {e.get('acciones', '—')} acciones "
                f"(último entrenamiento: {e.get('fecha', '—')}).")
    if inf.get("modelo_riesgo"):
        bloque_un_modelo(inf["modelo_riesgo"], "🛡️ Modelo de riesgo de caída fuerte (el que sí funciona)", riesgo=True)
    bloque_un_modelo(m, "🎲 Modelo de dirección: ¿subirá en 1 mes? (se publica por transparencia)")

    if e.get("fuera_de_muestra"):
        st.subheader("🏋️ Estrategia completa: años no vistos")
        from paginas_extra import tarjetas_metricas, veredicto_simulacion
        cols = st.columns(1 if pf.movil else 3)
        tarjetas_metricas(e["fuera_de_muestra"], "Estrategia entrenada", 10_000, cols[0])
        tarjetas_metricas(e["por_defecto"], "Reglas por defecto", 10_000, cols[1 % len(cols)])
        tarjetas_metricas(e["comprar_y_mantener"], "Comprar y mantener", 10_000, cols[2 % len(cols)])
        curvas = pd.DataFrame({k: pd.Series(v["valores"], index=pd.to_datetime(v["fechas"]))
                               for k, v in e.get("curvas", {}).items()})
        if not curvas.empty:
            st.line_chart(curvas, height=300 if pf.movil else 380)
        veredicto_simulacion(e["fuera_de_muestra"], e["comprar_y_mantener"])
        from bolsa.simulador import Parametros
        with st.expander("Reglas vigentes"):
            for linea in Parametros.desde_dict(e["parametros"]).describir():
                st.markdown(f"- {linea}")


def bloque_un_modelo(mod: dict, titulo: str, riesgo: bool = False):
    pf = perfil()
    mm = mod["metricas"]
    st.subheader(titulo)
    c = st.columns(1 if pf.movil else 3)
    c[0].metric("AUC (0,5 = azar)", f"{mm['auc']:.3f}", nivel_auc(mm["auc"]), delta_color="off")
    if riesgo:
        cal = pd.DataFrame(mod["calibracion"])
        c[1 % len(c)].metric("Caídas con riesgo 'muy bajo'", f"{cal['sube'].iloc[0] * 100:.0f}%")
        c[2 % len(c)].metric("Caídas con riesgo 'muy alto'", f"{cal['sube'].iloc[-1] * 100:.0f}%",
                             f"media {mm['tasa_subidas'] * 100:.0f}%", delta_color="off")
        st.caption("Frecuencia real con la que la acción llegó a caer más de un 10% en el mes siguiente, según el "
                   "riesgo que había estimado el modelo, en años que no había visto.")
    else:
        c[1 % len(c)].metric("Acierto de dirección a 1 mes", f"{mm['acierto'] * 100:.1f}%",
                             f"azar {mm['referencia'] * 100:.1f}%", delta_color="off")
        c[2 % len(c)].metric("20% mejor valoradas (al mes)", pct(mm["mejores_mes"] * 100, 2),
                             f"todas {pct(mm['todos_mes'] * 100, 2)}", delta_color="off")
    st.caption(f"{mm['casos']:,} casos de {mm['acciones']} valores ({mm['desde']} → {mm['hasta']}). ".replace(",", ".")
               + f"Fiabilidad: **{mod['fiabilidad']}**.")
    cal = pd.DataFrame(mod["calibracion"])
    if not cal.empty:
        with st.expander("📏 Calibración: lo que dijo el modelo y lo que pasó de verdad"):
            st.dataframe(pd.DataFrame({
                "El modelo decía": [f"{a * 100:.0f}-{b * 100:.0f}%" for a, b in zip(cal["p_min"], cal["p_max"])],
                "Ocurrió de verdad": (cal["sube"] * 100).round(0).astype(int).astype(str) + "%",
                "Rentabilidad media": [pct(x * 100, 1) for x in cal["rent_media"]],
                "Casos": cal["casos"]}), hide_index=True, width="stretch")
            st.caption("Si 'Ocurrió de verdad' cambia claramente de arriba abajo, el modelo distingue algo real. "
                       "La app siempre te enseña lo que ocurrió de verdad, no la cifra bruta del modelo.")
    if mod.get("importancia"):
        with st.expander("🔎 Qué patrones pesan más"):
            st.bar_chart(pd.DataFrame(mod["importancia"]).set_index("dato")["peso"], horizontal=True)
    if mod.get("por_ano"):
        with st.expander("📆 Año a año"):
            pa = pd.DataFrame(mod["por_ano"])
            st.dataframe(pd.DataFrame({"Año": pa["ano"], "AUC": pa["auc"].round(3),
                                       "Acierto": (pa["acierto"] * 100).round(1),
                                       "Frecuencia real %": (pa["tasa_subidas"] * 100).round(1), "Casos": pa["casos"]}),
                         hide_index=True, width="stretch")


# --------------------------------------------------------------------------- 📦 Carteras modelo
def pagina_carteras():
    pf = perfil()
    st.title("📦 Carteras modelo")
    inf = cargar_informe()
    if not inf or not inf.get("carteras"):
        sin_informe()
        return
    aviso_antiguedad(inf)
    st.markdown("Tres formas sencillas de invertir en acciones que **han funcionado con datos reales** y que puedes "
                "replicar en Bankinter. Se revisan **una vez al mes** (el primer día hábil): es lo contrario a estar "
                "comprando y vendiendo cada día.")
    st.warning("⚠️ Las simulaciones usan las grandes empresas de **hoy**; las que fracasaron por el camino no están, "
               "y eso hace los resultados algo optimistas (sobre todo para el momentum). Rentabilidades pasadas no "
               "garantizan las futuras. Úsalas solo para la parte de acciones de tu plan (🎯 Mi plan).")
    por_ticker = {r["ticker"]: r for r in inf["ranking"]}
    claves = list(inf["carteras"])
    perfil_guardado = datos_usuario().get("perfil_inversor")
    sugerida = 0
    if perfil_guardado:
        nombre = asesor.perfil_inversor(perfil_guardado["horizonte"], perfil_guardado["reaccion"],
                                        perfil_guardado["experiencia"], perfil_guardado["colchon"]).nombre
        sugerida = next((i for i, k in enumerate(claves) if inf["carteras"][k]["perfil"] == nombre), 0)
    tabs = st.tabs([inf["carteras"][k]["nombre"].split(" (")[0] for k in claves])
    for tab, k in zip(tabs, claves):
        c = inf["carteras"][k]
        with tab:
            if claves.index(k) == sugerida and perfil_guardado:
                st.success("👉 Es la que encaja con tu perfil.")
            st.markdown(f"**{c['nombre']}** · perfil {c['perfil'].lower()}")
            st.caption(c["descripcion"])
            m, ref = c["metricas"], c["referencia"]
            cols = st.columns(1 if pf.movil else 3)
            cols[0].metric("Rentabilidad anual simulada", pct(m["cagr_pct"], 1), f"todas: {pct(ref['cagr_pct'], 1)}",
                           delta_color="off")
            cols[1 % len(cols)].metric("Peor caída", pct(m["max_caida_pct"], 0), f"todas: {pct(ref['max_caida_pct'], 0)}",
                                       delta_color="off")
            cols[2 % len(cols)].metric("Comisiones pagadas", eur(m["gastos"] * 10_000 / c["capital_simulado"]),
                                       f"{m['operaciones']} operaciones", delta_color="off")
            curvas = pd.DataFrame({"Esta cartera": pd.Series(c["curva"]["valores"], index=pd.to_datetime(c["curva"]["fechas"])),
                                   "Todas a partes iguales": pd.Series(c["curva_referencia"]["valores"],
                                                                       index=pd.to_datetime(c["curva_referencia"]["fechas"]))})
            st.line_chart(curvas, height=260 if pf.movil else 340)
            st.caption(f"10.000 € invertidos el {m['desde']} siguiendo la regla (comisiones e impuesto de "
                       "transacciones incluidos; sin IRPF).")
            with st.expander("📆 Año a año"):
                st.dataframe(pd.DataFrame([{"Año": a["ano"], "Esta cartera": pct(a["cartera"], 1),
                                            "Todas a partes iguales": pct(a["todas"], 1)} for a in c["por_ano"]]),
                             hide_index=True, width="stretch")
            st.markdown("**Composición de este mes**")
            if not c["composicion"]:
                st.info("Este mes la cartera está en **liquidez**: los mercados de sus acciones están en tendencia "
                        "bajista. La regla vuelve a comprar cuando se recuperen.")
                continue
            importe = st.number_input("¿Cuánto quieres dedicar a esta cartera? (€)", 1_000.0, 1_000_000.0,
                                      float(max(1_000.0, c["n"] * 600.0)), 500.0, key=f"imp_{k}")
            por_valor = importe / c["n"]
            filas = []
            for x in c["composicion"]:
                r = por_ticker.get(x["ticker"], {})
                n = int(por_valor // x["precio"]) if x["precio"] else 0
                filas.append({"Empresa": r.get("nombre", x["ticker"]), "Sector": r.get("sector", "—"),
                              "Mercado": r.get("mercado", "—"), "Precio": round(x["precio"], 2), "Acciones": n,
                              "Importe": eur(n * x["precio"], moneda_de(x["ticker"])),
                              "Riesgo caída": ICONO_RIESGO.get(r.get("riesgo_nivel")), "Ticker": x["ticker"]})
            st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch")
            if por_valor < 600:
                st.warning(f"Con {eur(por_valor)} por empresa, las comisiones mínimas se comerían buena parte de la "
                           "ganancia. Mejor dedicar más dinero, elegir menos empresas o usar un ETF.")
            st.caption("Cómo seguirla: el primer día hábil de cada mes, vende las que ya no estén en la lista, compra "
                       "las nuevas y reparte a partes iguales. La app te avisa en 🧭 Hoy y por Telegram.")
            with st.expander("📋 Órdenes para copiar en Bankinter"):
                for x, fila in zip(c["composicion"], filas):
                    if fila["Acciones"]:
                        st.code(bankinter.ticket(x["ticker"], "Compra", fila["Acciones"], round(x["precio"], 2),
                                                 dias_validez=3), language=None)

    st.header("🛡️ Regla de protección para tus fondos indexados / ETF")
    st.markdown("Para la parte de tu dinero en fondos indexados: **seguir invertido mientras el índice esté por encima "
                "de su media de 200 sesiones, y pasar a liquidez solo si cae más de un 2% por debajo**. Volver a "
                "entrar cuando supere la media en un 2%.")
    filas = []
    for t, p in inf.get("proteccion", {}).items():
        st.markdown("- " + texto_proteccion(t, p))
        h = p.get("historia", {})
        if h:
            filas.append({"Índice": nombre_de(t), "Desde": h["mantener"]["desde"][:4],
                          "Mantener %/año": round(h["mantener"]["cagr_pct"], 1),
                          "Mantener peor caída": pct(h["mantener"]["max_caida_pct"], 0),
                          "Con la regla %/año": round(h["filtro"]["cagr_pct"], 1),
                          "Con la regla peor caída": pct(h["filtro"]["max_caida_pct"], 0),
                          "Cambios al año": round(h["cambios_por_ano"], 1)})
    if filas:
        st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch")
        st.caption("Índices sin dividendos; con la regla, el tiempo fuera se remunera al 2% anual. La regla no evita "
                   "las caídas rápidas (como marzo de 2020), pero sí las largas (2000-2003, 2008).")
    st.info("💡 **Truco fiscal en España**: entre **fondos de inversión** indexados puedes hacer *traspasos* sin pagar "
            "impuestos. Si piensas aplicar esta regla, es mejor usar fondos indexados (p. ej. un fondo MSCI World) y un "
            "fondo monetario que ETF, porque vender un ETF sí tributa.")


def bloque_historial_ideas():
    inf = cargar_informe()
    if not inf:
        return
    h = inf.get("historial_ideas", {})
    st.subheader("📅 Acierto real de las ideas del día (en tiempo real)")
    st.caption("Cada idea del día se guarda en el momento y, un mes después, se comprueba qué pasó. Es la prueba "
               "más honesta: nadie conocía el futuro cuando se dio la idea.")
    if not h.get("evaluadas"):
        st.info(f"Aún no hay ideas con un mes de antigüedad ({h.get('pendientes', 0)} pendientes de evaluar). "
                "Este historial irá creciendo cada día.")
        return
    c = st.columns(3)
    c[0].metric("Ideas evaluadas", h["evaluadas"])
    c[1].metric("Subieron en 1 mes", f"{h['suben'] * 100:.0f}%", pct(h["rent_media"] * 100, 2))
    if h.get("baten_indice") is not None:
        c[2].metric("Batieron a su índice", f"{h['baten_indice'] * 100:.0f}%", pct(h["exceso_medio"] * 100, 2))
    ult = pd.DataFrame(h.get("ultimas", []))
    if not ult.empty:
        ult["Empresa"] = ult["ticker"].map(nombre_de)
        st.dataframe(pd.DataFrame({"Fecha": ult["fecha"], "Empresa": ult["Empresa"],
                                   "1 mes después": [pct(x * 100, 1) for x in ult["ret"]],
                                   "Su índice": [pct(x * 100, 1) if pd.notna(x) else "—" for x in ult["ret_indice"]]}),
                     hide_index=True, width="stretch")
    pn = inf.get("patron_noticias", {})
    if pn.get("dias", 0) >= 30 and pn.get("correlacion") is not None:
        st.subheader("📰 ¿Anticipan algo las noticias?")
        st.markdown(f"Con {pn['dias']} días archivados: la semana siguiente a días de noticias muy positivas el IBEX "
                    f"se movió de media {pct((pn['semana_tras_positivas'] or 0) * 100, 2)}, y tras días muy negativos "
                    f"{pct((pn['semana_tras_negativas'] or 0) * 100, 2)} (media de todas las semanas: "
                    f"{pct(pn['semana_media'] * 100, 2)}).")
    elif pn:
        st.caption(f"📰 Archivo de noticias: {pn.get('dias', 0)} días. Con al menos 30 se empezará a medir si el tono "
                   "de las noticias anticipa los movimientos del mercado.")


def tickers_para_seleccion() -> list[str]:
    return list(TODAS_LAS_ACCIONES)


# --------------------------------------------------------------------------- laboratorio
RUTA_LAB = Path(__file__).resolve().parent / "informe" / "experimentos.json"


@st.cache_data(ttl=3600, show_spinner=False)
def _leer_lab(mtime: float) -> dict | None:
    try:
        return json.loads(RUTA_LAB.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def cargar_laboratorio() -> dict | None:
    return _leer_lab(RUTA_LAB.stat().st_mtime) if RUTA_LAB.exists() else None


def nivel_auc(auc: float | None) -> str:
    if auc is None:
        return "—"
    if auc >= 0.65:
        return "🟢 Bastante predecible"
    if auc >= 0.58:
        return "🟡 Algo predecible"
    if auc >= 0.53:
        return "🟠 Muy poco"
    return "🔴 Azar"


def bloque_laboratorio():
    lab = cargar_laboratorio()
    if not lab:
        return
    pf = perfil()
    st.subheader("🔬 Laboratorio: qué funciona de verdad (datos reales, años no vistos)")
    st.caption(f"Última revisión: {lab.get('fecha', '—')}. Se repite automáticamente cada mes con datos nuevos.")
    filas = []
    for nombre, m in lab.get("modelos", {}).items():
        filas.append({"Pregunta": m.get("pregunta", nombre), "¿Se puede predecir?": nivel_auc(m.get("auc")),
                      "AUC": round(m["auc"], 3) if m.get("auc") is not None else None,
                      "Ocurre si el modelo dice 'poco probable'": f"{m['tramo_bajo'] * 100:.0f}%",
                      "Ocurre si dice 'muy probable'": f"{m['tramo_alto'] * 100:.0f}%"})
    if filas:
        st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch")
        st.caption("AUC: 0,50 = lanzar una moneda; 0,55-0,60 ya es útil en bolsa; más de 0,65 es una señal fuerte. "
                   "Las columnas de la derecha dicen con qué frecuencia ocurrió de verdad lo que el modelo predecía.")
    rot = pd.DataFrame(lab.get("rotacion", []))
    if not rot.empty:
        st.markdown("**Carteras mensuales: quedarse cada mes con las N mejores según cada criterio**")
        rot = rot.sort_values("sharpe", ascending=False)
        tabla = pd.DataFrame({
            "Criterio": rot["senal"], "N": rot["n"], "Filtro mercado": rot["filtro_mercado"].map({True: "sí", False: "no"}),
            "Rentab. anual %": rot["cagr_pct"].round(1), "Peor caída %": rot["max_caida_pct"].round(1),
            "Rentab./riesgo": rot["sharpe"].round(2), "Comisiones €": rot["gastos"].round(0)})
        if pf.movil:
            tabla = tabla[["Criterio", "N", "Rentab. anual %", "Peor caída %"]]
        st.dataframe(tabla, hide_index=True, width="stretch", height=380)
        ref = rot[rot["senal"] == "Todas a partes iguales"]
        if len(ref):
            r = ref.iloc[0]
            st.caption(f"Referencia (todas las acciones a partes iguales): {r['cagr_pct']:.1f}% al año con una peor "
                       f"caída de {r['max_caida_pct']:.0f}%. Periodo {r['desde']} → {r['hasta']}. Rentab./riesgo = "
                       "rentabilidad dividida por la volatilidad (más alto = mejor relación ganancia/sustos).")
    idx = lab.get("indices", {})
    if idx:
        st.markdown("**Índices: ¿protege salir cuando el índice cae por debajo de su media?** (historia completa)")
        filas = []
        for t, variantes in idx.items():
            for v in variantes:
                filas.append({"Índice": nombre_de(t), "Regla": f"media {v['media']}" + (f" ±{v['banda']:.0%}" if v["banda"] else ""),
                              "Mantener %/año": round(v["mantener"]["cagr_pct"], 1),
                              "Mantener peor caída": f"{v['mantener']['max_caida_pct']:.0f}%",
                              "Con filtro %/año": round(v["filtro"]["cagr_pct"], 1),
                              "Con filtro peor caída": f"{v['filtro']['max_caida_pct']:.0f}%",
                              "Tiempo invertido": f"{v['tiempo_invertido']:.0%}",
                              "Desde": v["mantener"]["desde"][:4]})
        st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch")
