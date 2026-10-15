"""Páginas de simulación con dinero virtual, entrenamiento de la estrategia y tu cartera real (de cualquier banco)."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st

import plotly.graph_objects as go

from bolsa import (asesor, asesor_diario, avisos, bankinter, comparativa, dividendos, reequilibrio, semanal, cartera, costes, diagnostico, estrategias, experimentos, horario, importador,
                   patrones, senales, simulador)
from bolsa.simulador import Parametros
from bolsa.activos import CLASES, clase_de
from bolsa.tickers import EEUU, ETFS, IBEX35, TODAS_LAS_ACCIONES, nombre_de
from ui_comun import (palabras_de_la_pagina, cargar_dividendos, cargar_noticias, mostrar_plotly, reducir, selector_valor, almacen_actual, cargar_activos, enlace, cargar_fundamentales_varios, cargar_informe, cargar_historico, cargar_varios,
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
            "- ✅ Comisiones reales de tu bróker (las de la barra lateral), tasa Tobin, cambio de divisa, stop-loss y "
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
        st.line_chart(reducir(pd.DataFrame({"Estrategia": r.curva, "Comprar y mantener": mant})),
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
    st.line_chart(reducir(pd.DataFrame({"Entrenada": wf["curva_entrenada"], "Por defecto": wf["curva_defecto"],
                                        "Comprar y mantener": wf["curva_mantener"]})), height=300 if pf.movil else 400)
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
               "y stop que se ejecutan cuando el precio llega de verdad, órdenes pendientes y las comisiones de "
               "tu bróker. Cuando lleves unos meses, compara: ¿has ganado más que el robot? ¿y que el IBEX?")
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
            st.line_chart(reducir(pd.DataFrame({"Robot": r.curva, "Comprar y mantener": mant})), height=280)
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
        st.line_chart(reducir(pd.DataFrame({"Robot": curva, "Todas a partes iguales": ref})), height=280)
    filas = [{"Empresa": nombre_de(t), "Acciones": n, "Valor": eur(n * float(cierres[t].iloc[-1]))}
             for t, n in met["cartera_final"].items()]
    st.markdown("**Lo que tiene ahora el robot**")
    if filas:
        st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch")
    st.caption(f"Liquidez: {eur(met['efectivo_final'])}. Se revisa cada 21 sesiones (≈1 mes) desde su creación.")
    if len(curva) < 60:
        st.caption("Con pocas semanas el resultado es casi azar. Dale al menos 6 meses antes de sacar conclusiones.")


# --------------------------------------------------------------------------- 🏦 Mi cartera Bankinter
CONSEJO_CLASE = {
    "Fondos y ETF": "Fondo o ETF diversificado: no necesita stop-loss. Mantén las aportaciones y revisa el reparto "
                    "una vez al año.",
    "Renta fija": "Renta fija: amortigua las caídas de la bolsa. Mantener según tu plan.",
    "Monetario y liquidez": "Monetario: dinero casi sin riesgo para lo que necesites pronto.",
    "Oro y materias primas": "Oro o materias primas: protegen en algunas crisis pero no dan rentas. Mantén su peso "
                             "pequeño (el diagnóstico te avisa si se pasa).",
    "Criptomonedas": "Criptomoneda: muy volátil (ha caído más de un 70 % varias veces). Mantén su peso pequeño y no "
                     "compres ni vendas en caliente.",
}


def nombre_posicion(t: str, pos: dict) -> str:
    n = nombre_de(t)
    return pos.get("nombre") or n if n == t else n


def _var_1d(df: pd.DataFrame) -> float | None:
    c = df["Close"].dropna()
    return float(c.iloc[-1] / c.iloc[-2] - 1) if len(c) > 1 else None


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
        clase = pos.get("clase") or clase_de(t)
        base = {"ticker": t, "pos": pos, "clase": clase, "nombre": nombre_posicion(t, pos)}
        df = hist.get(t)
        if df is None or df.empty:
            filas.append({**base, "precio": None, "nivel": "sin_datos", "ev": None, "fx": fx(t) or 1.0,
                          "consejo": "No hay cotización para este valor (revisa su código)."})
            continue
        if clase != "Acciones":
            filas.append({**base, "precio": float(df["Close"].iloc[-1]), "nivel": "mantener", "ev": None,
                          "var_1d": _var_1d(df),
                          "consejo": CONSEJO_CLASE[clase], "fx": fx(t, funds.get(t)) or 1.0})
            continue
        ev = senales.evaluar(t, df, mercado_alcista=mercado_alcista_para(t), fundamentales=funds.get(t),
                             stop_atr=p.stop_atr, ratio_objetivo=p.ratio_objetivo)
        stop_sug = max(ev.plan.stop, pos.get("stop") or 0) if ev.plan else None
        nivel, texto = bankinter.consejo_posicion(
            ev.precio, pos["precio_medio"], pos.get("stop"), stop_sug, ev.puntuacion, p.umbral_venta,
            any("resultados" in a for a in ev.avisos))
        filas.append({**base, "precio": ev.precio, "nivel": nivel, "consejo": texto, "var_1d": _var_1d(df),
                      "ev": ev, "stop_sugerido": stop_sug, "fx": fx(t, funds.get(t)) or 1.0,
                      "resultados_pronto": any("resultados" in a for a in ev.avisos)})
    return filas


ICONO_NIVEL = {"vender": "🔴", "vigilar": "🟠", "poner_stop": "🟡", "subir_stop": "🟢⬆️", "mantener": "🟢",
               "sin_datos": "⚪"}


def asesor_hoy(inf: dict | None):
    """«🧑‍💼 Tu asesor hoy»: tu dinero y qué hacer hoy, en orden de importancia."""
    pf = perfil()
    d = datos_usuario()
    cr = d.get("cartera_real")
    with st.container(border=True):
        st.markdown("#### 🧑‍💼 Tu asesor hoy")
        if not cr or not cr.get("posiciones"):
            st.markdown("Importa tu cartera desde **cualquier banco** (Bankinter, CaixaBank, BBVA, Trade Republic, "
                        "Kutxabank...) en 🏦 Mi cartera y aquí verás cada día cuánto vale tu dinero y qué hacer con él.")
            enlace("bankinter", "Ir a Mi cartera", "🏦")
            return
        try:
            filas = revisar_cartera_real()
            activos_hoy = cargar_activos()
        except Exception as e:  # noqa: BLE001 - la página Hoy nunca debe romperse por la cartera
            st.caption(f"No se ha podido revisar tu cartera ahora mismo ({e}).")
            return
        filas_inf = {r["ticker"]: r for r in (inf or {}).get("ranking", [])}
        posiciones = [{"ticker": f["ticker"], "acciones": f["pos"]["acciones"], "precio_medio": f["pos"]["precio_medio"],
                       "fx_medio": f["pos"].get("fx_medio", 1.0), "precio": f["precio"], "fx": f["fx"],
                       "stop": f["pos"].get("stop"), "clase": f["clase"], "nombre": f["nombre"]}
                      for f in filas if f["precio"]]
        dg = diagnostico.diagnosticar(posiciones, d.get("otros_ahorros", 0.0), _perfil_guardado(), pf.tarifa,
                                      filas_inf)
        valor = sum(p["acciones"] * p["precio"] * p["fx"] for p in posiciones)
        cambio = sum(p["acciones"] * p["precio"] * p["fx"] * (1 - 1 / (1 + f["var_1d"]))
                     for p, f in zip(posiciones, [f for f in filas if f["precio"]]) if f.get("var_1d") is not None)
        invertido = sum(p["acciones"] * p["precio_medio"] * p["fx_medio"] for p in posiciones)
        c = st.columns(3 if not pf.movil else 1)
        c[0].metric("Tu dinero invertido vale", eur(valor), f"{eur(cambio)} en la última sesión", delta_color="normal")
        c[1 % len(c)].metric("Ganancia o pérdida total", eur(valor - invertido),
                             pct((valor / invertido - 1) * 100, 1) if invertido else None)
        if dg.get("clases"):
            principal = max(dg["clases"].items(), key=lambda x: x[1])
            c[2 % len(c)].metric("Reparto", f"{principal[1] * 100:.0f} % {principal[0].lower()}",
                                 TITULO_SEMAFORO.get(dg["semaforo"], ""), delta_color="off")
        try:
            proximos_div = dividendos.calendario(resumenes_dividendos(filas), dias=10)
        except Exception:  # noqa: BLE001 - sin datos de dividendos, el resto sigue
            proximos_div = []
        for a in asesor_diario.plan_del_dia(dg, filas, inf, activos_hoy, dividendos=proximos_div):
            st.markdown(f"{a['icono']} **{a['titulo']}** — {a['texto']}")
        bloque_semana(posiciones)
        enlace("bankinter", "Ver el diagnóstico completo de tu cartera", "🩺")
        st.caption("Consejos educativos a partir de tus datos y de reglas de gestión prudente; no sustituyen a un "
                   "asesor financiero registrado en la CNMV.")


def bloque_telegram():
    """Avisos gratis al móvil: guía paso a paso y mensaje de prueba."""
    with st.expander("🔔 Avisos al móvil por Telegram (gratis)"):
        st.markdown(
            "Cada día laborable por la noche recibirás el resumen del mercado, las ideas del día y **avisos de tu "
            "cartera** (stops, resultados…). Los viernes, además, el **resumen de tu semana**.\n\n"
            "1. En Telegram, busca **@BotFather** → escribe `/newbot` → ponle un nombre → copia el **token** que te da.\n"
            "2. Escribe cualquier cosa a tu bot nuevo. Luego abre en el navegador "
            "`https://api.telegram.org/bot<TOKEN>/getUpdates` (con tu token) y copia el número de **\"chat\":{\"id\"**.\n"
            "3. En **GitHub → tu repositorio → Settings → Secrets and variables → Actions → New repository secret**, "
            "crea estos cuatro: `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`, `GIST_TOKEN` y `GIST_ID` (los dos últimos, los "
            "mismos del Gist que pusiste en Streamlit: así el aviso conoce tu cartera).\n"
            "4. Prueba aquí abajo que el bot te llega.")
        c = st.columns(2)
        token = c[0].text_input("Token del bot", type="password", key="tg_token")
        chat = c[1].text_input("Chat id", key="tg_chat")
        if st.button("📨 Enviar mensaje de prueba", disabled=not (token and chat)):
            try:
                ok = avisos.enviar_telegram(token.strip(), chat.strip(),
                                            "✅ Prueba de la app de bolsa: los avisos funcionan.")
            except Exception as e:  # noqa: BLE001
                ok = False
                st.error(f"No se pudo enviar: {e}")
            if ok:
                st.success("¡Enviado! Míralo en Telegram. El token no se guarda en la app.")
            else:
                st.warning("Telegram no lo aceptó. Revisa el token y el chat id (y que hayas escrito antes a tu bot).")


def bloque_semana(posiciones: list[dict]):
    """Tu semana en palabras: cambio de tu dinero, qué lo ha movido y noticias de lo que tienes."""
    try:
        tickers = tuple(sorted({p["ticker"] for p in posiciones} | {"^IBEX", "IWDA.AS"}))
        hist = cargar_varios(tickers, "1mo")
        try:
            lista, _ = cargar_noticias()
            titulares = [{"titulo": n.titulo, "empresas": n.empresas} for n in lista if n.empresas]
        except Exception:  # noqa: BLE001
            titulares = []
        r = semanal.resumen(posiciones, hist, {"IBEX 35": hist.get("^IBEX"),
                                               "Fondo indexado mundial": hist.get("IWDA.AS")}, titulares)
    except Exception:  # noqa: BLE001 - el resumen nunca debe romper la página
        return
    lineas = semanal.texto(r)
    if lineas:
        with st.expander(f"📅 Tu semana: {lineas[0].split('(')[0].replace('Esta semana tu dinero ha cambiado ', '')}"
                         .strip()):
            for x in lineas:
                st.markdown(f"- {x}")


def avisos_resumen():
    """Bloque corto para la página de Resumen."""
    try:
        filas = revisar_cartera_real()
    except Exception:  # noqa: BLE001 - el resumen nunca debe romperse por la cartera
        return
    avisos = [f for f in filas if f["nivel"] in ("vender", "vigilar", "poner_stop", "subir_stop")]
    if avisos:
        with st.container(border=True):
            st.markdown(f"**🏦 Tu cartera: {len(avisos)} aviso(s)**")
            for f in avisos:
                st.markdown(f"{ICONO_NIVEL[f['nivel']]} **{f['nombre']}**: {f['consejo']}")


def pagina_bankinter():
    pf = perfil()
    broker = bankinter.BROKER if bankinter.BROKER != "Otro" else "tu banco"
    st.title("🏦 Mi cartera")
    with st.expander(f"🔒 Cómo se conecta con {broker} (y por qué no te pide la contraseña)"):
        st.markdown(
            f"Ni {broker} ni ningún banco español ofrece a particulares una forma oficial de que otra app lea tus "
            "inversiones o envíe órdenes. Darle tu usuario y contraseña a una app que no es tu banco es peligroso "
            "(quien la tenga puede mover tu dinero), va contra las condiciones de tu banco y, con la doble "
            "verificación, ni siquiera funcionaría bien. Por eso la app es tu **copiloto**:\n"
            "1. **Descargas** tus posiciones (CSV o Excel) o **copias la tabla** de la web o la app de tu banco.\n"
            "2. La app las **analiza**: acciones, fondos, ETF, oro, criptomonedas...\n"
            "3. Cada día te **aconseja** qué hacer y te deja la **orden escrita** para copiarla en tu bróker.\n\n"
            "Tú das siempre la última orden. Tus datos se guardan solo en tu copia de la app.")
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
            vista.append({"": ICONO_NIVEL[f["nivel"]], "Activo": f["nombre"], "Tipo": f["clase"],
                          "Títulos": pos["acciones"],
                          "Precio medio": round(pos["precio_medio"], 2),
                          "Precio actual": round(precio, 2) if precio else None,
                          "Valor (€)": round(valor, 2) if valor else None,
                          "Ganancia (%)": round((precio / pos["precio_medio"] - 1) * 100, 1) if precio else None,
                          "Stop-loss": pos.get("stop")})
        tabla = pd.DataFrame(vista)
        c = st.columns(2)
        c[0].metric("Valor de tu cartera", eur(total))
        c[1].metric("Ganancia o pérdida (sin vender)", eur(ganancia))
        st.caption("Precios en la divisa de cada valor, como en tu bróker; valores y ganancias en euros. La "
                   "ganancia en % es la del precio (sin comisiones ni efecto divisa).")
        if pf.movil:
            tabla = tabla[["", "Activo", "Ganancia (%)", "Valor (€)"]]
        st.dataframe(tabla, hide_index=True, width="stretch")
        comparado = bloque_diagnostico(filas)

        bloque_dividendos(filas)
        bloque_comparativa(filas)

        st.subheader("Qué hacer con cada posición")
        for f in filas:
            posicion_detalle(f, cr)

        if not comparado:
            st.subheader("🌦️ Qué le puede pasar a tu cartera")
            from paginas_hoy import bloque_que_puede_pasar
            pesos = {f["ticker"]: f["pos"]["acciones"] * f["precio"] * f["fx"] for f in filas if f["precio"]}
            bloque_que_puede_pasar(pesos, total, 0.0, 0)
    else:
        st.caption("Aún no has registrado posiciones. Impórtalas de tu banco o añádelas a mano.")

    palabras_de_la_pagina(["Concentración", "Diversificación", "Sector", "Volatilidad", "Caída máxima", "Stop-loss",
                           "Dividendo", "Fecha ex-dividendo", "Retención", "Ganancia patrimonial", "Base del ahorro",
                           "Compensación de pérdidas", "Regla de los 2 meses", "Fondo indexado", "Rebalanceo"])
    bloque_telegram()

    st.subheader("➕ Añadir posiciones")
    t2, t3, t1 = st.tabs(["📥 Archivo de tu banco", "📋 Pegar tabla", "✍️ A mano"])
    with t2:
        st.markdown(
            "En la web o la app de tu banco, entra en tu **cartera de valores / posición** y busca **Exportar**, "
            "**Descargar** o el icono de Excel. Sirve el CSV o Excel de cualquier banco (Bankinter, CaixaBank, BBVA, "
            "Santander, ING, Kutxabank, Trade Republic, MyInvestor, Degiro...): la app reconoce columnas como "
            "*Valor*, *ISIN*, *Títulos/Participaciones/Cantidad* y *Precio medio*.\n\n"
            "En **Bankinter**: Bróker → **Posición global** → descargar («Posición global.csv»; formato comprobado).")
        archivo = st.file_uploader("Archivo de posiciones", type=["xlsx", "xls", "csv", "txt"])
        if archivo:
            try:
                leidas = importador.leer_archivo(archivo, archivo.name, resolver=buscar_simbolo)
            except Exception as e:  # noqa: BLE001
                st.error(f"No se ha podido leer el archivo: {e}")
                leidas = pd.DataFrame()
            revisar_e_importar(leidas, "archivo")
    with t3:
        st.markdown("Si tu banco solo enseña la cartera en pantalla (o en PDF), **selecciona la tabla, cópiala y "
                    "pégala aquí** con la fila de títulos de las columnas.")
        texto = st.text_area("Tabla copiada", height=150,
                             placeholder="Valor	ISIN	Títulos	Precio medio\nIBERDROLA	ES0144580Y14	200	12,50")
        if texto.strip():
            revisar_e_importar(importador.leer_texto(texto, resolver=buscar_simbolo), "pegado")
    with t1:
        ticker = selector_valor("alta", solo_invertibles=True)
        with st.form("alta_real"):
            otro = st.text_input("¿Otro activo? Escribe su ISIN, su código (BTC-EUR, 4GLD.DE...) o su nombre",
                                 "").strip()
            c = st.columns(2 if pf.movil else 4)
            n = c[0].number_input("Cantidad (títulos o participaciones)", 0.0, 1e9, 10.0, format="%.6g")
            precio = c[1].number_input("Precio medio de compra", 0.0, value=0.0, format="%.4f")
            f_compra = c[2 % len(c)].date_input("Fecha de compra", date.today(), format="DD/MM/YYYY")
            stop = c[3 % len(c)].number_input("Stop-loss puesto (0 si no tienes)", 0.0, value=0.0)
            if st.form_submit_button("Guardar posición", type="primary"):
                t, nombre, tipo = ticker, "", None
                if otro:
                    hallado = buscar_simbolo(otro) if (importador.es_isin(otro) or " " in otro
                                                       or len(otro) > 12) else None
                    if hallado:
                        t, nombre, tipo = hallado["symbol"], hallado["name"], hallado.get("type")
                    else:
                        t = importador.ticker_cripto(otro) or otro.upper()
                err = cartera.comprar(cr, t, _cantidad(n), precio, pf.tarifa, f_compra.isoformat(), stop or None,
                                      nota="Registrada a mano", fx=fx(t) or 1.0)
                if err:
                    st.error(err)
                else:
                    cr["posiciones"][t].update(nombre=nombre or cr["posiciones"][t].get("nombre"),
                                               clase=clase_de(t, tipo, nombre))
                    guardar_datos()
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


def resumenes_dividendos(filas: list[dict]) -> list[dict]:
    funds = cargar_fundamentales_varios(tuple(sorted(f["ticker"] for f in filas)))
    salida = []
    for f in filas:
        if not f["precio"] or f["clase"] not in ("Acciones", "Fondos y ETF"):
            continue
        r = dividendos.resumen(f["ticker"], cargar_dividendos(f["ticker"]), (funds.get(f["ticker"]) or {}).get(
            "exDividendDate"), f["pos"]["acciones"], f["precio"], f["fx"],
            fecha_compra=f["pos"].get("fecha") if f["pos"].get("fecha", "") < date.today().isoformat() else None)
        salida.append({**r, "nombre": f["nombre"]})
    return salida


def bloque_dividendos(filas: list[dict]):
    """Cuánto cobras en dividendos, cuándo, y la rentabilidad contando dividendos."""
    with st.spinner("Consultando dividendos..."):
        lista = resumenes_dividendos(filas)
    if not lista or not any(r["bruto_ano"] for r in lista):
        return
    st.subheader("💶 Dividendos")
    valor = sum(f["pos"]["acciones"] * f["precio"] * f["fx"] for f in filas if f["precio"])
    bruto = sum(r["bruto_ano"] for r in lista)
    c = st.columns(3 if not perfil().movil else 1)
    c[0].metric("Al año (bruto)", eur(bruto), help="Lo pagado por tus acciones en los últimos 12 meses.")
    c[1 % len(c)].metric("Te quedan (neto)", eur(sum(r["neto_ano"] for r in lista)),
                         "tras la retención del 19 %", delta_color="off")
    c[2 % len(c)].metric("Rentabilidad por dividendo", pct(bruto / valor * 100, 2, False) if valor else "—")
    st.dataframe(pd.DataFrame([{
        "Empresa": r["nombre"], "Por acción (12 meses)": num(r["por_accion_ano"], 3),
        "Rentabilidad": pct(r["rentabilidad"] * 100, 2, False), "Al año (bruto)": eur(r["bruto_ano"]),
        "Próxima fecha ex-dividendo": (r["proximo"].strftime("%d/%m/%Y") + ("" if r["proximo_confirmado"]
                                                                          else " (estimada)")) if r["proximo"] else "—",
        "Próximo cobro (bruto, aprox.)": eur(r["proximo_importe"]) if r["proximo_importe"] else "—"}
        for r in sorted(lista, key=lambda x: -x["bruto_ano"]) if r["bruto_ano"]]), hide_index=True, width="stretch")
    cobrado = sum(r["cobrado_desde_compra"] for r in lista)
    if cobrado:
        st.caption(f"Desde las fechas de compra que tienes apuntadas has cobrado ≈ {eur(cobrado)} brutos en dividendos: "
                   "súmalos a la ganancia para ver tu rentabilidad real.")
    st.caption("Para cobrar un dividendo tienes que tener las acciones al cierre del día anterior a la fecha "
               "ex-dividendo. Ese día la acción baja más o menos lo que paga. El próximo cobro se estima con el último "
               "pago (el definitivo lo anuncia la empresa). Los de empresas extranjeras pagan además impuesto en su país "
               "(se recupera en parte en la renta). Los fondos y ETF de acumulación no reparten: reinvierten.")


@st.fragment
def bloque_comparativa(filas: list[dict]):
    """Tu cartera (con el reparto de hoy) frente a un fondo indexado mundial y el IBEX."""
    st.subheader("📊 Tu cartera frente a un fondo indexado")
    anos = st.segmented_control("Periodo", [1, 3, 5], default=3, format_func=lambda a: f"{a} año{'s' if a > 1 else ''}",
                                key="cmp_anos") or 3
    pesos = {f["ticker"]: f["pos"]["acciones"] * f["precio"] * f["fx"] for f in filas if f["precio"]}
    if not pesos:
        return
    with st.spinner("Calculando con la historia real..."):
        tickers = tuple(sorted(set(pesos) | set(comparativa.REFERENCIAS)))
        hist = cargar_varios(tickers, "10y")
        cambios = cargar_varios(tuple(costes.TICKER_CAMBIO.values()), "10y")
        hist_eur = costes.historicos_en_euros(hist, {d: cambios.get(t) for d, t in costes.TICKER_CAMBIO.items()})
        if "^IBEX" in hist:
            hist_eur["^IBEX"] = hist["^IBEX"]
        res = comparativa.comparar(hist_eur, pesos, int(anos))
    if not res:
        st.caption("No hay historia suficiente para comparar.")
        return
    st.dataframe(pd.DataFrame([{
        "": nombre, "Rentabilidad total": pct(m["total"] * 100, 1),
        "Al año": pct(m["anual"] * 100, 1) if m.get("anual") is not None else "—",
        "Volatilidad": pct(m["volatilidad"] * 100, 0, False), "Peor caída": pct(m["peor_caida"] * 100, 0),
        "Peor mes": pct(m["peor_mes"] * 100, 0) if m.get("peor_mes") is not None else "—"} for nombre, m in res.items()]),
        hide_index=True, width="stretch")
    curvas = pd.DataFrame({nombre.split(" (")[0]: m["curva"] * 10_000 for nombre, m in res.items()}).ffill()
    st.line_chart(reducir(curvas), height=260)
    texto = comparativa.conclusion(res)
    if texto:
        st.info(texto)
    st.caption("Ojo: es mirar atrás con las empresas que tienes hoy, que precisamente son las que te gustaron por cómo "
               "les ha ido; elegirlas al principio del periodo, sin saberlo, no era lo mismo. Sirve sobre todo para "
               "comparar el **riesgo** (volatilidad y caídas).")
    st.caption("Qué habrían hecho 10.000 € con tu reparto de hoy frente a las alternativas. Precios ajustados por "
               "dividendos (el IBEX es solo el índice de precios, sin dividendos). Volatilidad: cuánto se mueve al año; "
               "a más volatilidad, más sustos.")


def bloque_plan_fiscal(dg: dict, posiciones: list[dict]):
    """Plan por pasos con calendario fiscal (qué vender este año y qué en enero) y entrada al fondo en tramos."""
    d = datos_usuario()
    st.markdown("#### 📅 Plan por pasos (calendario fiscal)")
    otras = st.number_input("Ganancias (+) o pérdidas (−) que ya has realizado este año al vender (€)", -1e7, 1e7,
                            float(d.get("ganancias_ano", 0.0)), 500.0,
                            help="Cuentan para el IRPF del año junto con estas ventas. Míralo en tus operaciones de "
                                 "este año o en el informe fiscal provisional de tu bróker.")
    if otras != d.get("ganancias_ano", 0.0):
        d["ganancias_ano"] = otras
        guardar_datos()
    plan = reequilibrio.planificar(dg["propuesta"], dg["liberado"], dg["destino"], otras_ganancias_ano=otras)
    (st.success if plan["ahorro"] > 0 else st.info)(plan["motivo"])
    k = st.columns(2)
    k[0].metric("IRPF vendiendo todo ahora", eur(plan["irpf_todo_ahora"]))
    k[1].metric("IRPF con este plan", eur(plan["irpf_plan"]),
                f"−{eur(plan['ahorro'])}" if plan["ahorro"] > 0 else None, delta_color="inverse")
    for i, paso in enumerate(plan["pasos"], 1):
        with st.container(border=True):
            st.markdown(f"**Paso {i} · {paso['cuando']}** — IRPF de ese año por estas ventas: ≈ {eur(paso['irpf'])}")
            st.dataframe(pd.DataFrame([{"Vender": v["nombre"], "Títulos": v["acciones"], "Importe": eur(v["importe"]),
                                        "Ganancia (+) / pérdida (−)": eur(v["ganancia"])} for v in paso["ventas"]]),
                         hide_index=True, width="stretch")
            st.caption(paso["nota"])
    if plan["aportaciones"]:
        with st.container(border=True):
            st.markdown(f"**Después: el dinero al fondo en {plan['tramos']} tramos mensuales** (así no lo inviertes "
                        "todo justo antes de una caída)")
            st.dataframe(pd.DataFrame([{"Fecha": a["fecha"].strftime("%d/%m/%Y"),
                                        **{prod: eur(imp) for prod, imp in a["productos"].items()}}
                                       for a in plan["aportaciones"]]), hide_index=True, width="stretch")
    vendidas = {v["ticker"] for v in dg["propuesta"]}
    en_perdidas = [{"nombre": p.get("nombre") or nombre_de(p["ticker"]),
                    "ganancia": p["acciones"] * (p["precio"] * p.get("fx", 1.0)
                                                 - p["precio_medio"] * p.get("fx_medio", 1.0))}
                   for p in posiciones if p["ticker"] not in vendidas]
    en_perdidas = [p for p in en_perdidas if p["ganancia"] < 0]
    if en_perdidas and dg["ganancia_realizada"] + otras > 0:
        extra = reequilibrio.ahorro_por_perdidas(en_perdidas, dg["ganancia_realizada"] + otras)
        if extra > 10:
            st.caption(f"💡 Si además quisieras reducir {', '.join(p['nombre'] for p in en_perdidas)}, venderla(s) "
                       f"con pérdidas te ahorraría ≈ {eur(extra)} de IRPF este año. Hazlo solo si de verdad quieres "
                       "reducirla(s): si recompras antes de 2 meses, Hacienda no te deja usar esa pérdida.")


@st.fragment
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
    otros = c[1].number_input("Dinero en cuentas y depósitos (€)", 0.0, 100_000_000.0,
                              float(d.get("otros_ahorros", 0.0)), 1000.0,
                              help="Lo que tienes en liquidez fuera de estas inversiones. Los fondos, planes o "
                                   "acciones de otros bancos, mejor impórtalos como posiciones para analizarlos.")
    if otros != d.get("otros_ahorros", 0.0):
        d["otros_ahorros"] = otros
        guardar_datos()
    perfil_nombre = None if perfil_txt == "Aún no lo sé" else perfil_txt
    inf = cargar_informe() or {}
    filas_inf = {r["ticker"]: r for r in inf.get("ranking", [])}
    posiciones = [{"ticker": f["ticker"], "acciones": f["pos"]["acciones"], "precio_medio": f["pos"]["precio_medio"],
                   "fx_medio": f["pos"].get("fx_medio", 1.0), "precio": f["precio"], "fx": f["fx"],
                   "stop": f["pos"].get("stop"), "clase": f["clase"], "nombre": f["nombre"]}
                  for f in filas if f["precio"]]
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
    mostrar_plotly(figura)

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
               "Tu bróker puede incluir las comisiones en su «precio medio»: el informe fiscal que te envía es el "
               "que vale para la declaración.")
    with st.expander(f"📋 Órdenes de venta para copiar en {bankinter._donde()}"):
        for v in dg["propuesta"]:
            st.code(bankinter.ticket_venta(v["ticker"], v["acciones"], v["precio"]), language=None)

    bloque_plan_fiscal(dg, posiciones)

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


@st.cache_data(ttl=86_400, show_spinner=False)
def buscar_simbolo(consulta: str) -> dict | None:
    from bolsa import datos

    return datos.buscar_simbolo(consulta)


def _cantidad(x: float):
    return int(x) if float(x).is_integer() else round(float(x), 8)


def revisar_e_importar(leidas: pd.DataFrame, origen: str):
    pf = perfil()
    d = datos_usuario()
    if leidas.empty:
        st.error("No se han encontrado posiciones. Comprueba que la tabla tiene columnas de nombre o ISIN, "
                 "cantidad (títulos/participaciones) y precio medio.")
        return
    st.caption("Revisa la tabla. Si algún código está vacío o mal, corrígelo con el de Yahoo Finance (ej. SAN.MC, "
               "IWDA.AS, BTC-EUR). Los fondos de inversión suelen tener un código que empieza por 0P.")
    editada = st.data_editor(leidas, hide_index=True, width="stretch", num_rows="dynamic", key=f"ed_{origen}",
                             column_config={"clase": st.column_config.SelectboxColumn("Tipo", options=CLASES)})
    reemplazar = st.checkbox("Reemplazar mi cartera actual por esta", value=True, key=f"rep_{origen}")
    if st.button("📥 Importar", type="primary", key=f"imp_{origen}"):
        cr = d["cartera_real"] = cartera.nueva(None) if reemplazar else d.setdefault("cartera_real",
                                                                                      cartera.nueva(None))
        malas = []
        for _, r in editada.iterrows():
            if not r["ticker"] or not r["precio_medio"] or pd.isna(r["precio_medio"]):
                malas.append(str(r["nombre"]))
                continue
            tk = str(r["ticker"]).strip().upper()
            cartera.comprar(cr, tk, _cantidad(r["acciones"]), float(r["precio_medio"]), pf.tarifa,
                            nota=f"Importada ({origen})", fx=fx(tk) or 1.0)
            cr["posiciones"][tk].update(nombre=str(r["nombre"]), clase=r["clase"] if r["clase"] in CLASES
                                        else clase_de(tk, None, str(r["nombre"])))
        guardar_datos()
        if malas:
            st.warning("No se importaron (falta código o precio): " + ", ".join(malas))
        st.rerun()


def posicion_detalle(f: dict, cr: dict):
    pf = perfil()
    t, pos = f["ticker"], f["pos"]
    with st.expander(f"{ICONO_NIVEL[f['nivel']]} {f['nombre']} — {f['consejo'][:70]}"):
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
            cartera.vender(cr, t, pos["acciones"], precio_v, pf.tarifa, motivo="Venta registrada", fx=f["fx"])
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
    donde = bankinter._donde()
    st.markdown(f"**📱 Cómo hacerlo en {donde}**")
    st.markdown(
        f"1. Abre la app de {donde}" + (" → **Bróker**" if bankinter.es_bankinter() else "")
        + f" → busca **{nombre_de(ticker).split(' (')[0]}** ({bankinter.mercado_de(ticker)}).\n"
        "2. **Compra** con orden **Limitada** (no «a mercado»): así nunca pagas más del precio que fijes.\n"
        "3. Cuando se ejecute, crea la **protección**: "
        + ("órdenes «stop relacionadas» (stop-loss + objetivo a la vez)" if bankinter.es_bankinter()
           else "una orden OCO (stop-loss + objetivo a la vez), si tu bróker la tiene,")
        + " o, si prefieres, solo una orden **Stop** de venta.")
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
    with c2.popover(f"🏦 Ya la compré en {donde}", width="stretch"):
        with st.form(f"real_{ticker}"):
            n_real = st.number_input("Títulos comprados", 1, 10_000_000, n)
            precio = st.number_input("Precio al que se ejecutó", 0.0, value=round(plan.entrada, 2))
            stop = st.number_input("Stop-loss que has puesto", 0.0, value=round(plan.stop, 2))
            if st.form_submit_button("Registrar en mi cartera", type="primary"):
                cr = d.setdefault("cartera_real", cartera.nueva(None))
                cartera.comprar(cr, ticker, int(n_real), precio, pf.tarifa, stop=stop or None,
                                nota="Comprada tras analizarla", fx=f_eur)
                guardar_datos()
                st.success("Registrada. La verás en 🏦 Mi cartera, que la vigilará cada día.")


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
