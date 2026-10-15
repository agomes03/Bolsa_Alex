"""Páginas de simulación con dinero virtual, entrenamiento de la estrategia y cartera de Bankinter."""

from __future__ import annotations

import json
from datetime import date, datetime

import pandas as pd
import streamlit as st

from bolsa import bankinter, cartera, costes, estrategias, experimentos, senales, simulador
from bolsa.costes import acciones_asequibles, tamano_por_riesgo
from bolsa.simulador import Parametros
from bolsa.tickers import EEUU, ETFS, IBEX35, TODAS_LAS_ACCIONES, nombre_de, sector_de
from ui_comun import (almacen_actual, cargar_fundamentales_varios, cargar_historico, cargar_varios,
                      datos_usuario, estrategia_actual, eur, fecha, fx, guardar_datos, mercado_alcista_para, moneda_de,
                      num, pct, perfil, ultimo_precio)

UNIVERSOS = {
    "IBEX 35": (tuple(IBEX35), "^IBEX"),
    "EEUU (grandes empresas)": (tuple(EEUU), "^GSPC"),
    "IBEX 35 + EEUU": (tuple(IBEX35) + tuple(EEUU), "^IBEX"),
}


@st.cache_resource
def _universos() -> dict:
    """Caché compartida de universos preparados (se recalculan cada 6 horas)."""
    return {}


def universo_con_barra(nombre: str) -> simulador.Universo | None:
    clave = (nombre, datetime.now().strftime("%Y-%m-%d"), datetime.now().hour // 6)
    cache = _universos()
    if clave in cache:
        return cache[clave]
    barra = st.empty()

    def progreso(x, texto):
        barra.progress(min(max(x, 0.0), 1.0), f"Preparando 10 años de datos y predicciones históricas… {texto}")

    tickers, indice = UNIVERSOS[nombre]
    try:
        u = simulador.preparar_universo(cargar_varios(tickers, "10y"), cargar_historico(indice, "10y"),
                                        progreso=progreso)
    except ValueError as e:
        barra.empty()
        st.error(f"No hay datos suficientes para simular: {e}")
        return None
    barra.empty()
    for k in [k for k in cache if k[0] == nombre]:
        del cache[k]
    cache[clave] = u
    return u


def tabla_operaciones(ops: pd.DataFrame, limite: int = 200) -> pd.DataFrame:
    if ops.empty:
        return ops
    t = ops.copy()
    t["Empresa"] = t["Empresa"].map(nombre_de)
    for col in ("Compra", "Venta"):
        if col in t:
            t[col] = pd.to_datetime(t[col]).dt.strftime("%d/%m/%Y")
    return t.round(2).iloc[::-1].head(limite)


def tarjetas_metricas(m: dict, titulo: str, capital: float, contenedor=None):
    c = contenedor or st
    with c.container(border=True):
        st.markdown(f"**{titulo}**")
        st.metric("Capital final", eur(m["capital_final"]), pct(m["rentabilidad_pct"], 1))
        st.metric("Rentabilidad anual media", pct(m["cagr_pct"], 1))
        st.metric("Peor caída desde máximos", pct(m["max_caida_pct"], 1), delta_color="off",
                  help="El mayor susto: cuánto llegó a bajar el dinero desde su punto más alto.")
        if m.get("operaciones"):
            st.caption(f"{m['operaciones']} operaciones · ganadoras {m['acierto_pct']:.0f}% · "
                       f"ganancia media {pct(m['ganancia_media_pct'], 1)} · pérdida media "
                       f"{pct(m['perdida_media_pct'], 1)}"
                       + (f" · comisiones pagadas {eur(m['gastos'])}" if m.get("gastos") else ""))


def veredicto_simulacion(e: dict, mant: dict) -> None:
    if e["cagr_pct"] > mant["cagr_pct"] and e["max_caida_pct"] >= mant["max_caida_pct"]:
        st.success("✅ En los años que el entrenamiento NO había visto, la estrategia ganó más que comprar y "
                   "mantener y con menos sustos. Es una buena señal, pero el pasado no garantiza el futuro: "
                   "empieza con el robot virtual antes de arriesgar dinero real.")
    elif e["cagr_pct"] > 0 and e["max_caida_pct"] > mant["max_caida_pct"]:
        st.info("🟡 La estrategia ganó dinero y tuvo caídas más pequeñas que comprar y mantener, aunque ganó "
                "menos. Es más tranquila: útil si te asustan las caídas.")
    elif e["cagr_pct"] > 0:
        st.warning("🟠 La estrategia ganó dinero, pero menos que simplemente comprar y mantener. "
                   "Es lo más habitual en bolsa: por eso se recomienda que la mayor parte de tu dinero vaya a "
                   "un fondo indexado y uses las acciones individuales solo para una parte.")
    else:
        st.error("❌ En los años no vistos la estrategia perdió dinero. No la uses con dinero real: es mejor "
                 "un fondo indexado con aportaciones mensuales. Prueba otro objetivo o más iteraciones, y "
                 "recuerda que las comisiones pesan mucho si haces muchas operaciones con poco capital.")


# --------------------------------------------------------------------------- 🧪 Simulador
def pagina_simulador():
    pf = perfil()
    st.title("🧪 Simulador con dinero virtual")
    st.caption("Comprueba con los últimos 10 años si las reglas de la app habrían ganado dinero: un operador "
               "virtual compra y vende **día a día usando solo lo que se sabía en cada momento**, paga "
               "comisiones e impuestos y respeta los stop-loss. Después puedes **entrenar** las reglas para "
               "reducir los errores de inversión.")
    c1, c2 = st.columns(2)
    universo = c1.selectbox("Acciones con las que opera", list(UNIVERSOS))
    capital = c2.number_input("Dinero virtual (€)", 1_000.0, 1_000_000.0, 10_000.0, 1_000.0)
    with st.expander("ℹ️ Qué se tiene en cuenta y qué no"):
        st.markdown(
            "- ✅ Tendencia, medias, RSI, MACD, ambiente del mercado y el **modelo de predicción** (recalculado "
            "cada semana solo con datos pasados).\n"
            "- ✅ Comisiones reales de Bankinter (según tu perfil), tasa Tobin, cambio de divisa, stop-loss y "
            "objetivos. Todo en euros.\n"
            "- ❌ Noticias y analistas: no existe un histórico gratuito de 10 años, así que no se pueden simular.\n"
            "- ⚠️ Se usan las empresas que están HOY en el índice (las que salieron por ir mal no aparecen), "
            "lo que hace los resultados algo optimistas.\n"
            "- ⚠️ No incluye impuestos sobre las ganancias (IRPF).")
    t0, t1, t2 = st.tabs(["🌍 Resultados diarios (todas las empresas)", "▶️ Probar aquí",
                          "🏋️ Entrenar aquí"])
    with t0:
        from paginas_hoy import bloque_entrenamiento_diario, bloque_historial_ideas, bloque_laboratorio
        bloque_entrenamiento_diario()
        bloque_historial_ideas()
        bloque_laboratorio()
    if not st.session_state.get("sim_local"):
        with t1:
            st.caption("Simula aquí mismo con el grupo de acciones que elijas (descarga 10 años de datos: tarda "
                       "un poco la primera vez).")
            if st.button("Cargar datos y simular", key="sim_local_btn"):
                st.session_state["sim_local"] = True
                st.rerun()
        with t2:
            st.caption("Pulsa 'Cargar datos y simular' en la pestaña anterior para entrenar aquí.")
        return
    u = universo_con_barra(universo)
    if u is None:
        return
    st.caption(f"{len(u.tickers)} acciones · datos de {u.fechas[u.inicio]:%d/%m/%Y} a {u.fechas[-1]:%d/%m/%Y}")

    with t1:
        guardada = datos_usuario().get("estrategia")
        opciones = ["Reglas entrenadas (las que usa la app)", "Reglas por defecto"] if guardada else ["Reglas por defecto"]
        cual = st.radio("Reglas", opciones, horizontal=True)
        p = estrategia_actual() if cual.startswith("Reglas entrenadas") else \
            Parametros(riesgo_pct=pf.riesgo)
        anos = st.select_slider("Periodo", options=[1, 2, 3, 5, 10], value=10, format_func=lambda x: f"Últimos {x} años")
        inicio = max(u.inicio, len(u.fechas) - 252 * anos)
        with st.expander("Ver las reglas"):
            for linea in p.describir():
                st.markdown(f"- {linea}")
        r = simulador.simular(u, p, pf.tarifa, capital, inicio)
        mant = simulador.comprar_y_mantener(u, pf.tarifa, capital, inicio, len(u.fechas))
        m_mant = simulador.metricas(mant, pd.DataFrame(), capital)
        cols = st.columns(1 if pf.movil else 2)
        tarjetas_metricas(r.metricas, "🤖 Estrategia de la app", capital, cols[0])
        tarjetas_metricas(m_mant, "🧺 Comprar y mantener (referencia)", capital, cols[-1])
        st.line_chart(pd.DataFrame({"Estrategia": r.curva, "Comprar y mantener": mant}),
                      height=300 if pf.movil else 380)
        if cual.startswith("Reglas entrenadas"):
            st.caption("⚠️ Estas reglas se eligieron mirando estos mismos años, así que este resultado es "
                       "optimista. El dato honesto es el de la pestaña **Entrenar** (años no vistos).")
        if not r.operaciones.empty:
            motivos = r.operaciones["Motivo"].value_counts()
            st.caption("Cómo terminaron las operaciones: " + " · ".join(f"{k}: {v}" for k, v in motivos.items()))
            with st.expander(f"📜 Ver las {len(r.operaciones)} operaciones"):
                st.dataframe(tabla_operaciones(r.operaciones), hide_index=True, width="stretch")

    with t2:
        st.markdown(
            "El entrenamiento **prueba muchas combinaciones de reglas** (cuándo comprar, cuándo vender, dónde "
            "poner el stop-loss, cuánto fiarse del modelo, cuántas empresas a la vez…) y se queda con la que "
            "**menos error de inversión** comete. Para no hacerse trampas, entrena con unos años y **comprueba "
            "en el año siguiente, que no ha visto**; luego avanza un año y repite (*walk-forward*).")
        c1, c2, c3 = st.columns(3)
        objetivo = c1.selectbox("¿Qué es 'menos error' para ti?", list(simulador.OBJETIVOS),
                                help="Equilibrado: ganar sin grandes sustos. Menos pérdidas: la caída más pequeña "
                                     "posible ganando dinero. Máxima rentabilidad: lo que más gane, aunque asuste.")
        iteraciones = c2.slider("Combinaciones a probar", 10, 200, 40, 10,
                                help="Más combinaciones = más lento. Ojo: probar demasiadas aumenta el riesgo de "
                                     "encontrar reglas que solo funcionaron por casualidad.")
        anos_entreno = c3.slider("Años de entrenamiento", 2, 5, 3)
        if st.button("🏋️ Entrenar ahora", type="primary", width="stretch"):
            barra = st.progress(0.0, "Empezando…")
            try:
                wf = simulador.walk_forward(u, pf.tarifa, capital, iteraciones, objetivo, anos_entreno,
                                            base=Parametros(riesgo_pct=pf.riesgo),
                                            progreso=lambda x, t: barra.progress(min(x, 1.0), t))
            except ValueError as e:
                barra.empty()
                st.error(str(e))
                return
            barra.empty()
            st.session_state["_wf"] = wf
            datos_usuario()["estrategia"] = {
                "parametros": wf["parametros_finales"].a_dict(), "fecha": date.today().isoformat(),
                "universo": universo, "objetivo": objetivo, "iteraciones": wf["iteraciones"],
                "fuera_de_muestra": {k: v for k, v in wf["metricas_entrenada"].items()},
                "comprar_y_mantener": {k: v for k, v in wf["metricas_mantener"].items()},
            }
            guardar_datos()
        wf = st.session_state.get("_wf")
        guardada = datos_usuario().get("estrategia")
        if wf:
            mostrar_entrenamiento(wf, capital)
        elif guardada:
            st.info(f"Última estrategia entrenada el {guardada['fecha']} con {guardada['universo']} "
                    f"({guardada['iteraciones']} combinaciones, objetivo '{guardada['objetivo']}').")
            e, m = guardada["fuera_de_muestra"], guardada["comprar_y_mantener"]
            st.markdown(f"En años no vistos: rentabilidad anual **{pct(e['cagr_pct'], 1)}** con peor caída "
                        f"**{pct(e['max_caida_pct'], 1)}** (comprar y mantener: {pct(m['cagr_pct'], 1)} / "
                        f"{pct(m['max_caida_pct'], 1)}).")
            for linea in Parametros.desde_dict(guardada["parametros"]).describir():
                st.markdown(f"- {linea}")


def mostrar_entrenamiento(wf: dict, capital: float):
    pf = perfil()
    st.subheader("Resultado en años NO vistos por el entrenamiento")
    cols = st.columns(1 if pf.movil else 3)
    tarjetas_metricas(wf["metricas_entrenada"], "🏋️ Estrategia entrenada", capital, cols[0])
    tarjetas_metricas(wf["metricas_defecto"], "📏 Reglas por defecto", capital, cols[1 % len(cols)])
    tarjetas_metricas(wf["metricas_mantener"], "🧺 Comprar y mantener", capital, cols[2 % len(cols)])
    st.line_chart(pd.DataFrame({"Entrenada": wf["curva_entrenada"], "Por defecto": wf["curva_defecto"],
                                "Comprar y mantener": wf["curva_mantener"]}), height=300 if pf.movil else 400)
    veredicto_simulacion(wf["metricas_entrenada"], wf["metricas_mantener"])

    st.subheader("Año a año")
    filas = []
    for tr in wf["tramos"]:
        p: Parametros = tr["Reglas elegidas"]
        filas.append({"Entrenado con": tr["Entrenado con"], "Probado en": tr["Probado en (no visto)"],
                      "Entrenada %": round(tr["Resultado prueba %"], 1),
                      "Por defecto %": round(tr["Reglas por defecto %"], 1),
                      "Mantener %": round(tr["Comprar y mantener %"], 1),
                      "En entreno %": round(tr["Resultado entreno %"], 1),
                      "Reglas": f"compra≥{p.umbral_compra}, vende<{p.umbral_venta}, stop {p.stop_atr:g}×ATR, "
                                f"obj {'dinámico' if p.ratio_objetivo == 0 else f'{p.ratio_objetivo:g}×'}, "
                                f"modelo {p.peso_modelo:g}, máx {p.max_posiciones}"})
    st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch")
    st.caption("Si 'En entreno %' es mucho mayor que 'Entrenada %', las reglas se ajustaron demasiado al pasado "
               "(sobreajuste): funcionaban en los años que vio, pero no tanto en los nuevos. Es normal y es "
               "justo lo que este método te deja ver.")

    st.subheader("✅ Reglas que usará la app a partir de ahora")
    st.caption("Entrenadas con los años más recientes. Se aplican al plan de operación (stop-loss y objetivo) "
               "y al robot virtual que crees a partir de ahora.")
    for linea in wf["parametros_finales"].describir():
        st.markdown(f"- {linea}")
    if not wf["operaciones"].empty:
        with st.expander(f"📜 Operaciones en años no vistos ({len(wf['operaciones'])})"):
            st.dataframe(tabla_operaciones(wf["operaciones"]), hide_index=True, width="stretch")


# --------------------------------------------------------------------------- 🎮 Cartera virtual
def pagina_cartera_virtual():
    st.title("🎮 Cartera virtual")
    st.caption("Practica sin arriesgar nada: compra y vende con dinero ficticio a precios reales. Los stop-loss "
               "y objetivos se ejecutan solos, igual que en el broker. Cuando lleves unos meses, compara: "
               "¿has ganado más que el robot? ¿y que comprar y mantener?")
    t1, t2 = st.tabs(["🙋 Mis operaciones virtuales", "🤖 Robot automático"])
    with t1:
        cartera_manual()
    with t2:
        robot()
    copia_seguridad()


def cartera_manual():
    pf = perfil()
    d = datos_usuario()
    cv = d.setdefault("cartera_virtual", cartera.nueva(10_000.0))
    posiciones = tuple(sorted(cv["posiciones"]))
    hist = cargar_varios(posiciones, "1y") if posiciones else {}
    fx_pos = {t: fx(t) or 1.0 for t in cv["posiciones"]}
    eventos = cartera.revisar_ordenes(cv, hist, pf.tarifa, fx_pos)
    if eventos:
        guardar_datos()
        for e in eventos:
            st.info("🔔 " + e)
    precios = {t: ultimo_precio(hist.get(t)) for t in cv["posiciones"]}
    tabla, res = cartera.valorar(cv, precios, fx_pos)
    c = st.columns(2 if pf.movil else 4)
    c[0].metric("Valor total", eur(res["total"]), pct(res["ganancia_pct"], 1))
    c[1].metric("Ganancia / pérdida", eur(res["ganancia"]))
    c[2 % len(c)].metric("Dinero disponible", eur(res["efectivo"]))
    c[3 % len(c)].metric("Operaciones cerradas", f"{res['ganadoras']}/{res['operaciones_cerradas']} ganadoras")
    st.caption(f"Empezaste con {eur(cv['capital_inicial'])} el {fecha(cv['creada'])}. Los importes están en euros; "
               "los precios, en la divisa de cada acción (como en Bankinter).")

    if len(tabla):
        st.subheader("Posiciones abiertas")
        vista = pd.DataFrame({
            "Empresa": tabla["ticker"].map(nombre_de), "Acciones": tabla["acciones"],
            "Precio compra": tabla["precio_medio"].round(2), "Precio actual": tabla["precio"].round(2),
            "Resultado (€)": tabla["resultado"].round(2), "Resultado (%)": tabla["resultado_pct"].round(1),
            "Stop-loss": tabla["stop"], "Objetivo": tabla["objetivo"]})
        st.dataframe(vista, hide_index=True, width="stretch")
        c1, c2 = st.columns([2, 1])
        vender_t = c1.selectbox("Vender", list(cv["posiciones"]), format_func=nombre_de, key="v_vender")
        if c2.button("Vender todo a precio actual", width="stretch") and precios.get(vender_t):
            cartera.vender(cv, vender_t, cv["posiciones"][vender_t]["acciones"], precios[vender_t], pf.tarifa,
                           motivo="Venta manual", fx=fx_pos.get(vender_t, 1.0))
            guardar_datos()
            st.rerun()

    st.subheader("Comprar con dinero virtual")
    ticker = st.selectbox("Empresa", list(TODAS_LAS_ACCIONES), format_func=nombre_de, key="v_ticker")
    df = cargar_historico(ticker, "2y")
    f_eur = fx(ticker)
    if df.empty or f_eur is None:
        st.error("No hay cotización o tipo de cambio disponible.")
    else:
        p = estrategia_actual()
        ev = senales.evaluar(ticker, df, mercado_alcista=mercado_alcista_para(ticker),
                             stop_atr=p.stop_atr, ratio_objetivo=p.ratio_objetivo)
        st.caption(f"Precio: **{eur(ev.precio, moneda_de(ticker))}**. Para el análisis completo, usa 🔍 Analizar.")
        patrimonio = res["total"]
        sugeridas = 0
        if ev.plan:
            sugeridas = min(tamano_por_riesgo(patrimonio, pf.riesgo, ev.precio * f_eur, ev.plan.stop * f_eur),
                            acciones_asequibles(res["efectivo"], ev.precio * f_eur, ticker, pf.tarifa))
        with st.form("compra_virtual"):
            c = st.columns(3)
            n = c[0].number_input("Acciones", 1, 1_000_000, max(sugeridas, 1))
            stop = c[1].number_input("Stop-loss", 0.0, value=round(ev.plan.stop, 2) if ev.plan else 0.0)
            obj = c[2].number_input("Objetivo", 0.0, value=round(ev.plan.objetivo, 2) if ev.plan else 0.0)
            if st.form_submit_button("🎮 Comprar", type="primary", width="stretch"):
                err = cartera.comprar(cv, ticker, int(n), ev.precio, pf.tarifa, stop=stop or None,
                                      objetivo=obj or None, nota=f"Puntuación {ev.puntuacion}", fx=f_eur)
                if err:
                    st.error(err)
                else:
                    guardar_datos()
                    st.success(f"Comprado: {n} acciones de {nombre_de(ticker)}.")
                    st.rerun()

    if cv["historial"]:
        with st.expander(f"📜 Historial ({len(cv['historial'])} movimientos)"):
            h = pd.DataFrame(cv["historial"]).iloc[::-1]
            h["ticker"] = h["ticker"].map(nombre_de)
            st.dataframe(h.round(2), hide_index=True, width="stretch")
    with st.expander("♻️ Empezar de cero"):
        nuevo = st.number_input("Nuevo capital virtual (€)", 500.0, 1_000_000.0, 10_000.0, 500.0, key="v_reset_cap")
        if st.button("Reiniciar mi cartera virtual"):
            d["cartera_virtual"] = cartera.nueva(nuevo)
            guardar_datos()
            st.rerun()


def robot():
    pf = perfil()
    d = datos_usuario()
    rb = d.get("robot")
    st.markdown("El robot opera **solo**, siguiendo las reglas entrenadas, con dinero virtual. Es una prueba "
                "**en tiempo real y sin trampas**: desde el día que lo creas, nadie conoce el futuro. "
                "Vuelve cada pocos días y mira si de verdad gana dinero.")
    if not rb:
        tipo = st.radio("¿Qué hará el robot?", ["📦 Seguir una cartera modelo cada mes (recomendado)",
                                                 "🎯 Comprar y vender con reglas y stop-loss"])
        cap = st.number_input("Dinero virtual del robot (€)", 1_000.0, 1_000_000.0, 10_000.0, 1_000.0)
        if tipo.startswith("📦"):
            clave = st.selectbox("Cartera modelo", list(estrategias.CARTERAS),
                                 format_func=lambda k: estrategias.CARTERAS[k].nombre)
            st.caption(estrategias.CARTERAS[clave].descripcion + " Es la opción que mejor ha funcionado con datos "
                       "reales; las reglas de compra/venta diarias rindieron menos que comprar y mantener.")
            if st.button("🤖 Crear robot", type="primary"):
                d["robot"] = {"tipo": "cartera", "cartera": clave, "creado": date.today().isoformat(), "capital": cap}
                guardar_datos()
                st.rerun()
            return
        universo = st.selectbox("Acciones con las que opera", list(UNIVERSOS), key="rb_univ")
        p = estrategia_actual()
        with st.expander("Reglas que seguirá"):
            for linea in p.describir():
                st.markdown(f"- {linea}")
            if "estrategia" not in d:
                st.caption("Son las reglas por defecto. Si entrenas la estrategia en 🧪 Simulador, el robot "
                           "nuevo usará las entrenadas.")
        if st.button("🤖 Crear robot", type="primary"):
            d["robot"] = {"tipo": "reglas", "creado": date.today().isoformat(), "capital": cap, "universo": universo,
                          "parametros": p.a_dict()}
            guardar_datos()
            st.rerun()
        return
    if rb.get("tipo") == "cartera":
        robot_cartera(rb)
        boton_reiniciar_robot(d)
        return

    u = universo_con_barra(rb["universo"])
    if u is None:
        return
    p = Parametros.desde_dict(rb["parametros"])
    i0 = int(u.fechas.searchsorted(pd.Timestamp(rb["creado"]), side="right"))
    st.caption(f"Creado el {rb['creado']} con {eur(rb['capital'])} · {rb['universo']}")
    abiertas: set[str] = set()
    if i0 >= len(u.fechas):
        st.info("Todavía no ha habido ninguna sesión de bolsa desde que creaste el robot. "
                "Mañana empezará a operar con la apertura.")
    else:
        r = simulador.simular(u, p, pf.tarifa, rb["capital"], inicio=i0, liquidar=False)
        mant = simulador.comprar_y_mantener(u, pf.tarifa, rb["capital"], i0, len(u.fechas))
        valor = float(r.curva.iloc[-1])
        abiertas = set(r.abiertas["Empresa"]) if not r.abiertas.empty else set()
        c = st.columns(2 if pf.movil else 3)
        c[0].metric("Valor del robot", eur(valor), pct((valor / rb["capital"] - 1) * 100, 2))
        c[1].metric("Comprar y mantener", eur(float(mant.iloc[-1])),
                    pct((float(mant.iloc[-1]) / rb["capital"] - 1) * 100, 2))
        c[2 % len(c)].metric("Operaciones cerradas", len(r.operaciones))
        if len(r.curva) > 1:
            st.line_chart(pd.DataFrame({"Robot": r.curva, "Comprar y mantener": mant}), height=280)
        if not r.abiertas.empty:
            st.markdown("**Posiciones abiertas del robot**")
            a = r.abiertas.copy()
            a["Empresa"] = a["Empresa"].map(nombre_de)
            a["Compra"] = pd.to_datetime(a["Compra"]).dt.strftime("%d/%m/%Y")
            st.dataframe(a.round(2), hide_index=True, width="stretch")
        if not r.operaciones.empty:
            with st.expander("📜 Operaciones cerradas"):
                st.dataframe(tabla_operaciones(r.operaciones), hide_index=True, width="stretch")
        if len(r.curva) < 60:
            st.caption("Con pocas semanas el resultado es casi azar. Dale al menos 3-6 meses antes de sacar "
                       "conclusiones.")
    manana = simulador.senales_hoy(u, p, excluir=abiertas)
    st.markdown("**🔭 Qué compraría en la próxima apertura** (si tiene hueco)")
    if manana.empty:
        st.caption("Ninguna acción cumple ahora las condiciones de compra.")
    else:
        m = manana.head(p.max_posiciones).copy()
        m["Empresa"] = m["Empresa"].map(nombre_de)
        st.dataframe(m.round(2), hide_index=True, width="stretch")
    boton_reiniciar_robot(d)


def boton_reiniciar_robot(d: dict):
    with st.expander("♻️ Reiniciar el robot"):
        st.caption("Borra el robot actual. Podrás crear uno nuevo.")
        if st.button("Borrar robot"):
            d.pop("robot", None)
            guardar_datos()
            st.rerun()


def robot_cartera(rb: dict):
    """Robot que replica una cartera modelo con rotación mensual desde el día en que se creó."""
    pf = perfil()
    c = estrategias.CARTERAS[rb["cartera"]]
    st.caption(f"{c.nombre} · creado el {fecha(rb['creado'])} con {eur(rb['capital'])}")
    with st.spinner("Calculando la cartera del robot con datos de todas las empresas..."):
        acciones = tuple(t for t in TODAS_LAS_ACCIONES if t not in ETFS and (c.universo == "global" or t.endswith(".MC")))
        hist = costes.historicos_en_euros(cargar_varios(acciones, "2y"), {"USD": cargar_historico("EURUSD=X", "2y")})
        refs = {k: cargar_historico(k, "2y") for k in ("^IBEX", "^STOXX50E", "^GSPC")}
        cierres = estrategias.cierres_acciones(hist, c.universo)
        perm = estrategias.permitido(cierres, {k: v for k, v in refs.items() if not v.empty})
    if cierres.empty:
        st.error("No se han podido descargar cotizaciones.")
        return
    inicio = cierres.index[cierres.index > pd.Timestamp(rb["creado"])]
    if inicio.empty:
        st.info("Todavía no ha habido ninguna sesión desde que creaste el robot. En la próxima comprará esto:")
        comp = estrategias.composicion_hoy(cierres, perm, c)
        st.dataframe(pd.DataFrame([{"Empresa": nombre_de(x["ticker"]), "Precio (€)": round(x["precio_eur"], 2)}
                                   for x in comp]), hide_index=True, width="stretch")
        return
    sig = estrategias.senal(cierres, c.senal)
    curva, met = experimentos.simular_rotacion(cierres, sig, c.n, pf.tarifa, rb["capital"],
                                               perm if c.filtro_mercado else None, inicio=inicio[0],
                                               max_por_sector=c.max_por_sector)
    unos = pd.DataFrame(1.0, index=cierres.index, columns=cierres.columns)
    ref, met_ref = experimentos.simular_rotacion(cierres, unos, len(cierres.columns), pf.tarifa, rb["capital"],
                                                 inicio=inicio[0])
    valor = float(curva.iloc[-1])
    cols = st.columns(2 if pf.movil else 3)
    cols[0].metric("Valor del robot", eur(valor), pct((valor / rb["capital"] - 1) * 100, 2))
    cols[1].metric("Todas a partes iguales", eur(float(ref.iloc[-1])),
                   pct((float(ref.iloc[-1]) / rb["capital"] - 1) * 100, 2))
    cols[2 % len(cols)].metric("Comisiones pagadas", eur(met.get("gastos", 0.0)))
    if len(curva) > 1:
        st.line_chart(pd.DataFrame({"Robot": curva, "Todas a partes iguales": ref}), height=280)
    filas = [{"Empresa": nombre_de(t), "Acciones": n, "Valor": eur(n * float(cierres[t].iloc[-1]))}
             for t, n in met["cartera_final"].items()]
    st.markdown("**Lo que tiene ahora el robot**")
    if filas:
        st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch")
    st.caption(f"Liquidez: {eur(met['efectivo_final'])}. Se revisa cada 21 sesiones (≈1 mes) desde su creación.")
    if len(curva) < 60:
        st.caption("Con pocas semanas el resultado es casi azar. Dale al menos 6 meses antes de sacar conclusiones.")


# --------------------------------------------------------------------------- 🏦 Mi cartera Bankinter
def revisar_cartera_real() -> list[dict]:
    """Analiza cada posición real y devuelve filas con precio, resultado y consejo."""
    cr = datos_usuario().get("cartera_real")
    if not cr or not cr["posiciones"]:
        return []
    p = estrategia_actual()
    tickers = tuple(sorted(cr["posiciones"]))
    hist = cargar_varios(tickers, "2y")
    funds = cargar_fundamentales_varios(tickers)
    filas = []
    for t, pos in cr["posiciones"].items():
        df = hist.get(t)
        if df is None or df.empty:
            filas.append({"ticker": t, "pos": pos, "precio": None, "nivel": "sin_datos",
                          "consejo": "No hay cotización para este valor (revisa el ticker).", "ev": None})
            continue
        ev = senales.evaluar(t, df, mercado_alcista=mercado_alcista_para(t), fundamentales=funds.get(t),
                             stop_atr=p.stop_atr, ratio_objetivo=p.ratio_objetivo)
        stop_sug = max(ev.plan.stop, pos.get("stop") or 0) if ev.plan else None
        nivel, texto = bankinter.consejo_posicion(
            ev.precio, pos["precio_medio"], pos.get("stop"), stop_sug, ev.puntuacion, p.umbral_venta,
            any("resultados" in a for a in ev.avisos))
        filas.append({"ticker": t, "pos": pos, "precio": ev.precio, "nivel": nivel, "consejo": texto,
                      "ev": ev, "stop_sugerido": stop_sug, "fx": fx(t, funds.get(t)) or 1.0})
    return filas


ICONO_NIVEL = {"vender": "🔴", "vigilar": "🟠", "poner_stop": "🟡", "subir_stop": "🟢⬆️", "mantener": "🟢",
               "sin_datos": "⚪"}


def avisos_resumen():
    """Bloque corto para la página de Resumen."""
    try:
        filas = revisar_cartera_real()
    except Exception:  # noqa: BLE001 - el resumen nunca debe romperse por la cartera
        return
    avisos = [f for f in filas if f["nivel"] in ("vender", "vigilar", "poner_stop", "subir_stop")]
    if avisos:
        with st.container(border=True):
            st.markdown(f"**🏦 Tu cartera de Bankinter: {len(avisos)} aviso(s)**")
            for f in avisos:
                st.markdown(f"{ICONO_NIVEL[f['nivel']]} **{nombre_de(f['ticker'])}**: {f['consejo']}")


def pagina_bankinter():
    pf = perfil()
    st.title("🏦 Mi cartera de Bankinter")
    st.info("**Cómo trabaja esta app con Bankinter.** Bankinter no permite que apps externas lean tu cuenta ni "
            "envíen órdenes (no tiene API pública para particulares), así que la app es tu **copiloto**: "
            "apuntas o importas lo que tienes, la app lo vigila cada día y te dice **qué orden poner en "
            "Bankinter** (y te la deja escrita para copiarla). Tú das siempre la última orden.")
    d = datos_usuario()
    cr = d.setdefault("cartera_real", cartera.nueva(None))

    filas = revisar_cartera_real()
    if filas:
        avisos = [f for f in filas if f["nivel"] not in ("mantener",)]
        if avisos:
            st.warning(f"🔔 {len(avisos)} posición(es) necesitan tu atención.")
        vista, total, ganancia = [], 0.0, 0.0
        for f in filas:
            pos, precio = f["pos"], f["precio"]
            valor = pos["acciones"] * precio * f["fx"] if precio else None
            invertido = pos["acciones"] * pos["precio_medio"] * pos.get("fx_medio", 1.0)
            total += valor or 0
            ganancia += (valor - invertido) if valor else 0
            vista.append({"": ICONO_NIVEL[f["nivel"]], "Empresa": nombre_de(f["ticker"]), "Títulos": pos["acciones"],
                          "Precio medio": round(pos["precio_medio"], 2),
                          "Precio actual": round(precio, 2) if precio else None,
                          "Valor (€)": round(valor, 2) if valor else None,
                          "Ganancia (%)": round((precio / pos["precio_medio"] - 1) * 100, 1) if precio else None,
                          "Stop-loss": pos.get("stop")})
        tabla = pd.DataFrame(vista)
        c = st.columns(2)
        c[0].metric("Valor de tu cartera", eur(total))
        c[1].metric("Ganancia o pérdida (sin vender)", eur(ganancia))
        st.caption("Precios en la divisa de cada valor, como en Bankinter; valores y ganancias en euros. La ganancia "
                   "en % es la del precio (sin comisiones ni efecto divisa).")
        if pf.movil:
            tabla = tabla[["", "Empresa", "Ganancia (%)", "Valor (€)"]]
        st.dataframe(tabla, hide_index=True, width="stretch")
        concentracion(filas, total)

        st.subheader("Qué hacer con cada posición")
        for f in filas:
            posicion_detalle(f, cr)

        st.subheader("🌦️ Qué le puede pasar a tu cartera")
        from paginas_hoy import bloque_que_puede_pasar
        pesos = {f["ticker"]: f["pos"]["acciones"] * f["precio"] * f["fx"] for f in filas if f["precio"]}
        bloque_que_puede_pasar(pesos, total, 0.0, 0)
    else:
        st.caption("Aún no has registrado posiciones. Añádelas a mano o impórtalas desde un Excel.")

    st.subheader("➕ Añadir posiciones")
    t1, t2 = st.tabs(["✍️ A mano", "📥 Importar de Bankinter (Excel/CSV)"])
    with t1:
        with st.form("alta_real"):
            ticker = st.selectbox("Empresa", list(TODAS_LAS_ACCIONES), format_func=nombre_de)
            otro = st.text_input("¿No está en la lista? Su código de Yahoo Finance", "").strip().upper()
            c = st.columns(2 if pf.movil else 4)
            n = c[0].number_input("Títulos", 1, 10_000_000, 10)
            precio = c[1].number_input("Precio medio (el que muestra Bankinter)", 0.0, value=0.0, format="%.4f")
            f_compra = c[2 % len(c)].date_input("Fecha de compra", date.today())
            stop = c[3 % len(c)].number_input("Stop-loss puesto (0 si no tienes)", 0.0, value=0.0)
            if st.form_submit_button("Guardar posición", type="primary"):
                t = otro or ticker
                err = cartera.comprar(cr, t, int(n), precio, pf.tarifa, f_compra.isoformat(), stop or None,
                                      nota="Registrada a mano", fx=fx(t) or 1.0)
                if err:
                    st.error(err)
                else:
                    guardar_datos()
                    st.rerun()
    with t2:
        st.markdown(
            "1. En **bankinter.com** (ordenador), entra en **Bróker → Posición**.\n"
            "2. Si tu pantalla permite descargarla en Excel, hazlo; si no, selecciona la tabla, cópiala y pégala en "
            "una hoja de cálculo (Excel o Google Sheets) y guárdala.\n"
            "3. Súbela aquí. La app busca columnas como *Valor*, *Títulos* y *Precio medio* y te deja corregir "
            "cualquier fila antes de guardar.")
        archivo = st.file_uploader("Archivo de posiciones", type=["xlsx", "xls", "csv"])
        if archivo:
            try:
                leidas = bankinter.leer_archivo(archivo, archivo.name)
            except Exception as e:  # noqa: BLE001
                st.error(f"No se ha podido leer el archivo: {e}")
                leidas = pd.DataFrame()
            if leidas.empty:
                st.error("No se han encontrado posiciones. Comprueba que el archivo tiene columnas de valor, "
                         "títulos y precio medio.")
            else:
                st.caption("Revisa la tabla. Si algún ticker está vacío o mal, corrígelo (ej. SAN.MC, ITX.MC).")
                editada = st.data_editor(leidas, hide_index=True, width="stretch", num_rows="dynamic")
                reemplazar = st.checkbox("Reemplazar mi cartera actual por esta", value=True)
                if st.button("📥 Importar", type="primary"):
                    if reemplazar:
                        cr = d["cartera_real"] = cartera.nueva(None)
                    malas = []
                    for _, r in editada.iterrows():
                        if not r["ticker"] or not r["precio_medio"]:
                            malas.append(str(r["nombre"]))
                            continue
                        tk = str(r["ticker"]).upper()
                        cartera.comprar(cr, tk, int(r["acciones"]), float(r["precio_medio"]), pf.tarifa,
                                        nota="Importada de Bankinter", fx=fx(tk) or 1.0)
                    guardar_datos()
                    if malas:
                        st.warning("No se importaron (falta ticker o precio): " + ", ".join(malas))
                    st.rerun()
    copia_seguridad()


def concentracion(filas: list[dict], total: float):
    if total <= 0:
        return
    por_valor, por_sector = {}, {}
    for f in filas:
        if not f["precio"]:
            continue
        v = f["pos"]["acciones"] * f["precio"] * f["fx"]
        por_valor[f["ticker"]] = v
        s = sector_de(f["ticker"])
        por_sector[s] = por_sector.get(s, 0) + v
    for t, v in por_valor.items():
        if v / total > 0.25 and len(por_valor) > 1:
            st.warning(f"⚖️ {nombre_de(t)} pesa un {v / total * 100:.0f}% de tu cartera. Lo prudente es que "
                       "ninguna empresa supere el 20-25%.")
    for s, v in por_sector.items():
        if v / total > 0.4 and len(por_sector) > 1:
            st.warning(f"⚖️ El sector {s} pesa un {v / total * 100:.0f}%: estás poco diversificado.")


def posicion_detalle(f: dict, cr: dict):
    pf = perfil()
    t, pos = f["ticker"], f["pos"]
    with st.expander(f"{ICONO_NIVEL[f['nivel']]} {nombre_de(t)} — {f['consejo'][:70]}"):
        st.write(f["consejo"])
        if f["ev"]:
            for a in f["ev"].avisos:
                st.caption("⚠️ " + a)
        if f["nivel"] in ("poner_stop", "subir_stop") and f.get("stop_sugerido"):
            st.code(bankinter.ticket_stop(t, pos["acciones"], f["stop_sugerido"]), language=None)
        elif f["nivel"] in ("vender", "vigilar") and f["precio"]:
            st.code(bankinter.ticket_venta(t, pos["acciones"], f["precio"]), language=None)
        c = st.columns(3)
        nuevo_stop = c[0].number_input("Stop-loss que tienes puesto", 0.0, value=float(pos.get("stop") or 0.0),
                                       key=f"stop_{t}")
        if c[0].button("Guardar stop", key=f"gstop_{t}"):
            pos["stop"] = nuevo_stop or None
            guardar_datos()
            st.rerun()
        precio_v = c[1].number_input("Vendida a (precio)", 0.0, value=float(f["precio"] or 0.0), key=f"pv_{t}")
        if c[1].button("Registrar venta", key=f"vend_{t}"):
            cartera.vender(cr, t, pos["acciones"], precio_v, pf.tarifa, motivo="Venta en Bankinter", fx=f["fx"])
            guardar_datos()
            st.rerun()
        if c[2].button("🗑️ Quitar sin vender", key=f"del_{t}"):
            cr["posiciones"].pop(t, None)
            guardar_datos()
            st.rerun()


# --------------------------------------------------------------------------- operar en Bankinter (desde Analizar)
def bloque_operar(ticker: str, n: int, plan: senales.Plan, f_eur: float):
    """Pasos y órdenes exactas para Bankinter, y botones para registrar la operación (virtual o real)."""
    pf = perfil()
    n = max(n, 1)
    st.markdown("**📱 Cómo hacerlo en Bankinter**")
    st.markdown(
        f"1. Abre la app de Bankinter → **Bróker** → busca **{nombre_de(ticker).split(' (')[0]}** "
        f"({bankinter.mercado_de(ticker)}).\n"
        "2. **Compra** con orden **Limitada** (no «a mercado»): así nunca pagas más del precio que fijes.\n"
        "3. Cuando se ejecute, crea la **protección**: órdenes «stop relacionadas» (stop-loss + objetivo a la vez) o, "
        "si prefieres, solo una orden **Stop** de venta.")
    st.code(bankinter.ticket_compra(ticker, n, plan.entrada, tarifa=pf.tarifa, importe_eur=n * plan.entrada * f_eur),
            language=None)
    st.code(bankinter.ticket_stop_relacionadas(ticker, n, plan.stop, plan.objetivo), language=None)
    with st.expander("Otras formas de protegerte"):
        st.code(bankinter.ticket_stop(ticker, n, plan.stop), language=None)
        distancia = (1 - plan.stop / plan.entrada) * 100
        st.caption(f"También puedes usar una orden **Stop dinámica** con una distancia del {num(distancia, 1)} %: "
                   "sube sola cuando la acción sube y no baja nunca. Se ejecuta a mercado al activarse.")
    d = datos_usuario()
    c1, c2 = st.columns(2)
    if c1.button("🎮 Probarla con dinero virtual", width="stretch"):
        cv = d.setdefault("cartera_virtual", cartera.nueva(10_000.0))
        err = cartera.comprar(cv, ticker, n, plan.entrada, pf.tarifa, stop=plan.stop, objetivo=plan.objetivo,
                              nota="Desde Analizar", fx=f_eur)
        if err:
            st.error(err)
        else:
            guardar_datos()
            st.success("Añadida a tu 🎮 Cartera virtual. El stop-loss y el objetivo se ejecutarán solos.")
    with c2.popover("🏦 Ya la compré en Bankinter", width="stretch"):
        with st.form(f"real_{ticker}"):
            n_real = st.number_input("Títulos comprados", 1, 10_000_000, n)
            precio = st.number_input("Precio al que se ejecutó", 0.0, value=round(plan.entrada, 2))
            stop = st.number_input("Stop-loss que has puesto", 0.0, value=round(plan.stop, 2))
            if st.form_submit_button("Registrar en mi cartera", type="primary"):
                cr = d.setdefault("cartera_real", cartera.nueva(None))
                cartera.comprar(cr, ticker, int(n_real), precio, pf.tarifa, stop=stop or None,
                                nota="Comprada tras analizarla", fx=f_eur)
                guardar_datos()
                st.success("Registrada. La verás en 🏦 Mi Bankinter, que la vigilará cada día.")


# --------------------------------------------------------------------------- copia de seguridad
def copia_seguridad():
    with st.expander("💾 Copia de seguridad de tus datos"):
        st.caption(f"Tus carteras y la estrategia se guardan en: **{almacen_actual().descripcion}**.")
        if not almacen_actual().en_la_nube:
            st.caption("Si usas la app publicada en Internet (móvil), configura el guardado en la nube (ver README) "
                       "o descarga una copia de vez en cuando: esos servidores borran los archivos al reiniciarse.")
        st.download_button("⬇️ Descargar copia", json.dumps(datos_usuario(), ensure_ascii=False, indent=1,
                                                            default=str),
                           file_name=f"bolsa_datos_{date.today():%Y%m%d}.json", mime="application/json")
        subida = st.file_uploader("⬆️ Restaurar una copia", type=["json"], key="restaurar")
        if subida and st.button("Restaurar (sustituye los datos actuales)"):
            st.session_state["_datos"] = json.loads(subida.getvalue().decode("utf-8"))
            guardar_datos()
            st.success("Datos restaurados.")
            st.rerun()
