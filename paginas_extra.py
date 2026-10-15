"""Páginas de simulación con dinero virtual, entrenamiento de la estrategia y cartera de Bankinter."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st

import plotly.graph_objects as go

from bolsa import (asesor, bankinter, cartera, costes, diagnostico, estrategias, experimentos, horario, patrones,
                   senales, simulador)
from bolsa.simulador import Parametros
from bolsa.tickers import EEUU, ETFS, IBEX35, TODAS_LAS_ACCIONES, nombre_de
from ui_comun import (almacen_actual, cargar_fundamentales_varios, cargar_informe, cargar_historico, cargar_varios,
                      datos_usuario, estrategia_actual, eur, fecha, fx, guardar_datos, mercado_alcista_para, num,
                      pct, perfil)

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
    st.caption("Practica sin arriesgar nada, como si fuera el bróker: precios reales, órdenes limitadas, a mercado "
               "y stop que se ejecutan cuando el precio llega de verdad, órdenes pendientes y comisiones de "
               "Bankinter. Cuando lleves unos meses, compara: ¿has ganado más que el robot? ¿y que el IBEX?")
    t1, t2 = st.tabs(["🙋 Mis operaciones virtuales", "🤖 Robot automático"])
    with t1:
        from paginas_virtual import cartera_manual
        cartera_manual()
    with t2:
        robot()
    copia_seguridad()


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
        comparado = bloque_diagnostico(filas)

        st.subheader("Qué hacer con cada posición")
        for f in filas:
            posicion_detalle(f, cr)

        if not comparado:
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
            "1. En Bankinter, entra en **Bróker → Posición global** y descárgala (sale un archivo "
            "«Posición global.csv»).\n"
            "2. Súbelo aquí tal cual. La app lee *Valor*, *Ticker*, *Títulos* y *Precio medio* y te deja corregir "
            "cualquier fila antes de guardar.\n"
            "3. Después, en cada posición, apunta el stop-loss si ya lo tienes puesto en Bankinter (el archivo no "
            "lo incluye).")
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


ICONO_GRAVEDAD = {"alta": "🔴", "media": "🟠", "baja": "🔵", "ok": "🟢"}
TITULO_SEMAFORO = {"rojo": "🔴 Necesita cambios", "ambar": "🟠 Mejorable", "verde": "🟢 Bien construida"}


def _perfil_guardado() -> str | None:
    p = datos_usuario().get("perfil_inversor")
    if not p:
        return None
    try:
        return asesor.perfil_inversor(p["horizonte"], p["reaccion"], p["experiencia"], p["colchon"],
                                      p.get("deudas", False)).nombre
    except (KeyError, TypeError):
        return None


def bloque_diagnostico(filas: list[dict]) -> bool:
    """Revisión de la cartera como la haría un asesor, con una propuesta concreta y sus costes.
    Devuelve True si ya ha mostrado la comparación con crisis reales."""
    pf = perfil()
    d = datos_usuario()
    st.subheader("🩺 Diagnóstico de tu cartera")
    guardado = _perfil_guardado()
    c = st.columns(2)
    opciones = ["Conservador", "Moderado", "Dinámico", "Aún no lo sé"]
    perfil_txt = c[0].selectbox("Tu perfil", opciones, index=opciones.index(guardado) if guardado else 3,
                                help="Calcúlalo en 🎯 Mi plan (5 preguntas). Decide cuánto conviene tener en "
                                     "acciones sueltas y cuánto en fondos.")
    otros = c[1].number_input("Otros ahorros e inversiones (€)", 0.0, 100_000_000.0,
                              float(d.get("otros_ahorros", 0.0)), 1000.0,
                              help="Cuentas, depósitos, fondos... Lo que no son estas acciones. Cuenta para saber "
                                   "cuánto pesa cada empresa en todo tu dinero.")
    if otros != d.get("otros_ahorros", 0.0):
        d["otros_ahorros"] = otros
        guardar_datos()
    perfil_nombre = None if perfil_txt == "Aún no lo sé" else perfil_txt
    inf = cargar_informe() or {}
    filas_inf = {r["ticker"]: r for r in inf.get("ranking", [])}
    posiciones = [{"ticker": f["ticker"], "acciones": f["pos"]["acciones"], "precio_medio": f["pos"]["precio_medio"],
                   "fx_medio": f["pos"].get("fx_medio", 1.0), "precio": f["precio"], "fx": f["fx"],
                   "stop": f["pos"].get("stop")} for f in filas if f["precio"]]
    dg = diagnostico.diagnosticar(posiciones, otros, perfil_nombre, pf.tarifa, filas_inf)
    if dg["semaforo"] == "sin_datos":
        return False

    mayor = dg["empresas"][0]
    m = st.columns(2 if pf.movil else 4)
    m[0].metric("Estado", TITULO_SEMAFORO[dg["semaforo"]])
    m[1].metric("Mayor peso", f"{mayor['peso'] * 100:.0f} %".replace(".", ","), mayor["nombre"], delta_color="off")
    m[2 % len(m)].metric("Equivale a", f"{num(dg['n_efectivo'], 1)} empresas",
                         help="1 / suma de los pesos al cuadrado: cuántas empresas a partes iguales tendrían el "
                              "mismo riesgo de concentración. Lo prudente es 5 o más (un fondo indexado: más de 1.000).")
    pais, w_pais = max(dg["paises"].items(), key=lambda x: x[1])
    m[3 % len(m)].metric("País principal", f"{pais} {w_pais * 100:.0f} %")

    figura = go.Figure(go.Bar(x=[e["peso"] * 100 for e in dg["empresas"]], y=[e["nombre"] for e in dg["empresas"]],
                              orientation="h", marker_color=["#d62728" if e["peso"] > diagnostico.MAX_EMPRESA
                                                             else "#2ca02c" for e in dg["empresas"]],
                              text=[f"{e['peso'] * 100:.0f} %" for e in dg["empresas"]], textposition="auto"))
    figura.add_vline(x=diagnostico.MAX_EMPRESA * 100, line_dash="dash",
                     annotation_text=f"máximo prudente {diagnostico.MAX_EMPRESA * 100:.0f} %")
    figura.update_layout(height=80 + 45 * len(dg["empresas"]), margin=dict(l=0, r=0, t=30, b=0),
                         xaxis_title="% de tu dinero", yaxis=dict(autorange="reversed"))
    st.plotly_chart(figura, width="stretch", config={"displayModeBar": False})

    for x in dg["hallazgos"]:
        with st.expander(f"{ICONO_GRAVEDAD[x['gravedad']]} {x['titulo']}", expanded=x["gravedad"] == "alta"):
            st.write(x["texto"])

    if not dg["propuesta"]:
        return False
    st.markdown("#### 🧭 Propuesta: repartir el riesgo")
    st.write(f"Para que ninguna empresa pase del {diagnostico.MAX_EMPRESA * 100:.0f} % de tu dinero, venderías:")
    st.dataframe(pd.DataFrame([{
        "Empresa": v["nombre"], "Vender": f"{v['acciones']} {'acción' if v['acciones'] == 1 else 'acciones'}",
        "Importe": eur(v["importe"]), "Ganancia (+) o pérdida (−) a declarar": eur(v["ganancia"]),
        "Peso después": f"{v['queda_peso'] * 100:.0f} %"} for v in dg["propuesta"]]),
        hide_index=True, width="stretch")
    k = st.columns(1 if pf.movil else 3)
    k[0].metric("Comisiones de venta", eur(dg["costes_venta"]))
    k[1 % len(k)].metric("IRPF aproximado", eur(dg["impuesto"]),
                         help="Sobre la ganancia neta de estas ventas (las pérdidas compensan las ganancias). "
                              "Depende también de tus otras ganancias y pérdidas del año.")
    k[2 % len(k)].metric("Dinero para diversificar", eur(dg["liberado"]))
    st.markdown("**A dónde llevar ese dinero**" + ("" if perfil_nombre else " (indica tu perfil para afinarlo)") + ":")
    for producto, importe in dg["destino"].items():
        st.markdown(f"- **{eur(importe)} → {producto}**: {asesor.PRODUCTOS[producto]['que']}")
    st.caption("Si tienes ganancias grandes, puedes repartir las ventas en dos años fiscales para pagar menos IRPF. "
               "Si vendes una acción con pérdidas, no la recompres en 2 meses (o no podrás aplicar esa pérdida). "
               "Bankinter puede incluir las comisiones en su «precio medio»: el informe fiscal que te envía es el "
               "que vale para la declaración.")
    with st.expander("📋 Órdenes de venta para copiar en Bankinter"):
        for v in dg["propuesta"]:
            st.code(bankinter.ticket_venta(v["ticker"], v["acciones"], v["precio"]), language=None)

    st.markdown("#### 🔬 Qué habría pasado en crisis reales")
    with st.spinner("Comparando tu cartera y la propuesta con 10 años de historia real..."):
        todos = tuple(sorted(set(dg["pesos_antes"]) | set(dg["pesos_despues"])))
        hist = cargar_varios(todos, "10y")
        cambios = cargar_varios(tuple(costes.TICKER_CAMBIO.values()), "10y")
        hist_eur = costes.historicos_en_euros(hist, {d: cambios.get(t) for d, t in costes.TICKER_CAMBIO.items()})
        est_a = {e["crisis"]: e["cambio"] for e in patrones.prueba_estres(hist_eur, dg["pesos_antes"])}
        est_d = {e["crisis"]: e["cambio"] for e in patrones.prueba_estres(hist_eur, dg["pesos_despues"])}
        esc_a = patrones.escenarios(patrones.rentabilidades_cartera(hist_eur, dg["pesos_antes"]))
        esc_d = patrones.escenarios(patrones.rentabilidades_cartera(hist_eur, dg["pesos_despues"]))
    total = sum(dg["pesos_antes"].values())
    filas_t = [{"Situación": cr, "Tu cartera hoy": f"{pct(est_a[cr] * 100, 0)} ({eur(total * est_a[cr])})",
                "Con la propuesta": f"{pct(est_d[cr] * 100, 0)} ({eur(total * est_d[cr])})"}
               for cr in est_a if cr in est_d]
    if esc_a and esc_d:
        filas_t.append({"Situación": "Un año malo (1 de cada 20)",
                        "Tu cartera hoy": f"{pct(esc_a['p5'] * 100, 0)} ({eur(total * esc_a['p5'])})",
                        "Con la propuesta": f"{pct(esc_d['p5'] * 100, 0)} ({eur(total * esc_d['p5'])})"})
    if filas_t:
        st.dataframe(pd.DataFrame(filas_t), hide_index=True, width="stretch")
        st.caption("Con los precios reales de cada crisis (solo los valores que ya cotizaban). La propuesta no "
                   "promete ganar más: reduce cuánto depende tu dinero de pocas empresas.")
    return bool(filas_t)


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
        ahora_iso = f"{horario.ahora_madrid():%Y-%m-%dT%H:%M}"
        validez = (date.today() + timedelta(days=7)).isoformat()
        err = cartera.nueva_orden(cv, ticker, "compra", "limitada", n, pf.tarifa, precio_ref=plan.entrada,
                                  ahora=ahora_iso, validez=validez, limite=round(plan.entrada, 3), fx=f_eur,
                                  stop=plan.stop, objetivo=plan.objetivo)
        if err:
            st.error(err)
        else:
            cartera.ejecutar_ordenes(cv, {}, pf.tarifa, ahora_iso,
                                     {ticker: (plan.entrada, horario.estado_mercado(ticker)["abierto"])})
            guardar_datos()
            st.success(f"Orden limitada enviada a tu 🎮 Cartera virtual: {n} títulos a {num(plan.entrada, 3)} como "
                       "máximo, válida 7 días. Al ejecutarse se le pondrán el stop-loss y el objetivo.")
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
