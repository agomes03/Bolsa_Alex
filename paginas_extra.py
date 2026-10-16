"""Páginas de simulación con dinero virtual, entrenamiento de la estrategia y tu cartera real (de cualquier banco)."""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st

import plotly.graph_objects as go

from bolsa import (alertas, asesor, asesor_diario, avisos, bankinter, cartera, comparativa, costes, cuentas,
                   decision, diagnostico, dividendos, estrategias, eventos, experimentos, fondos, horario, importador,
                   patrones, reequilibrio, rentabilidad, semanal, senales, simulador)
from bolsa.simulador import Parametros
from bolsa.activos import CLASES, clase_de
from bolsa.tickers import EEUU, ETFS, IBEX35, TODAS_LAS_ACCIONES, nombre_de
from ui_comun import (SEGUNDOS_REFRESCO, almacen_actual, cargar_activos, cargar_analistas, cargar_composiciones,
                      cargar_dividendos_varios, cargar_fundamentales, cargar_fundamentales_varios, cargar_historico,
                      cargar_informe, cargar_noticias, cargar_varios, cotizaciones_ahora, cuenta_activa,
                      datos_usuario, descargas_en_paralelo, enlace, estrategia_actual, eur, fecha, fx, guardar_datos,
                      historia_larga_eur, linea_actualizado, mercado_alcista_para, mostrar_plotly, num,
                      olvidar_campos_de_cuenta, palabras_de_la_pagina, pct, perfil, pestanas, privado, reducir,
                      selector_valor)

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
        st.metric("Peor caída desde máximos", pct(m["max_caida_pct"], 1), delta_color="off", delta_arrow="off",
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
    t1, t2 = pestanas(["🙋 Mis operaciones virtuales", "🤖 Robot automático"], "cv_pestana")
    with t1:
        if t1.open:
            from paginas_virtual import cartera_manual
            cartera_manual()
    with t2:
        if t2.open:
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


def revisar_cartera_real(cr: dict | None = None) -> list[dict]:
    """Analiza cada posición real y devuelve filas con precio, resultado y consejo. Sin `cr`, la de la cuenta
    activa."""
    cr = cr if cr is not None else datos_usuario().get("cartera_real")
    if not cr or not cr["posiciones"]:
        return []
    p = estrategia_actual()
    tickers = tuple(sorted(cr["posiciones"]))
    hist = cargar_varios(tickers, "2y")
    funds = cargar_fundamentales_varios(tickers)
    try:
        ahora = cotizaciones_ahora(tickers)
    except Exception:  # noqa: BLE001 - sin precio de ahora, se usa el del histórico
        ahora = {}
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
        # El consejo se da con el precio de ahora (el histórico diario puede ser el cierre de ayer): si hoy ha
        # perforado tu stop-loss, se dice ya. Y un stop sugerido nunca queda por encima del precio.
        precio = (ahora.get(t) or {}).get("precio") or ev.precio
        stop_sug = max(min(ev.plan.stop, precio * 0.98), pos.get("stop") or 0) if ev.plan else None
        nivel, texto = bankinter.consejo_posicion(
            precio, pos["precio_medio"], pos.get("stop"), stop_sug, ev.puntuacion, p.umbral_venta,
            any("resultados" in a for a in ev.avisos), pos.get("sin_stop", False), pos.get("alarma"))
        filas.append({**base, "precio": ev.precio, "nivel": nivel, "consejo": texto, "var_1d": _var_1d(df),
                      "ev": ev, "stop_sugerido": stop_sug, "fx": fx(t, funds.get(t)) or 1.0,
                      "resultados_pronto": any("resultados" in a for a in ev.avisos)})
    _precios_frescos(filas)
    return filas


def _precios_frescos(filas: list[dict]) -> None:
    """Sustituye el precio del histórico diario (que Yahoo a veces publica con horas de retraso) por el de ahora o
    el del último cierre, y guarda de dónde sale (en directo, tiempo real o cierre)."""
    try:
        ahora = cotizaciones_ahora([f["ticker"] for f in filas if f["precio"]])
    except Exception:  # noqa: BLE001 - sin precio reciente, se queda el del histórico
        return
    for f in filas:
        q = ahora.get(f["ticker"])
        if q and f["precio"]:
            f["precio"] = q["precio"]
            f["cotizacion"] = q
            if q.get("variacion_pct") is not None:
                f["var_1d"] = q["variacion_pct"] / 100


def limite_empresa() -> float:
    """Lo máximo que debería pesar una empresa según el perfil de la cuenta activa."""
    return diagnostico.limites_de(_perfil_guardado())["empresa"]


def pesos_cartera_real() -> dict[str, float]:
    """Parte de tu dinero (cartera + ahorros apuntados) en cada valor que tienes. Vacío si no hay cartera."""
    try:
        filas = revisar_cartera_real()
    except Exception:  # noqa: BLE001 - sin datos, sin pesos
        return {}
    valores = {f["ticker"]: f["pos"]["acciones"] * f["precio"] * f["fx"] for f in filas if f["precio"]}
    total = sum(valores.values()) + max(cuenta_activa().get("otros_ahorros", 0.0), 0.0)
    return {t: v / total for t, v in valores.items()} if total > 0 else {}


ICONO_NIVEL = {"vender": "🔴", "vigilar": "🟠", "poner_stop": "🟡", "subir_stop": "🟢⬆️", "mantener": "🟢",
               "sin_datos": "⚪"}


@st.fragment(run_every=SEGUNDOS_REFRESCO)
def asesor_hoy(inf: dict | None):
    """«🧑‍💼 Tu asesor hoy»: tu dinero, qué hacer con cada acción y lo demás de hoy. Se refresca solo cada minuto."""
    pf = perfil()
    d = datos_usuario()
    cr = d.get("cartera_real")
    with st.container(border=True):
        nombre_cuenta = d.get("cuenta_activa") if len(d.get("cuentas", {})) > 1 else None
        st.markdown("#### 🧑‍💼 Tu asesor hoy" + (f" · 👤 {nombre_cuenta}" if nombre_cuenta else ""))
        if not cr or not cr.get("posiciones"):
            st.markdown("Importa tu cartera desde **cualquier banco** (Bankinter, CaixaBank, BBVA, Trade Republic, "
                        "Kutxabank...) en 🏦 Mi cartera y aquí verás cada día cuánto vale tu dinero y qué hacer con él.")
            enlace("bankinter", "Ir a Mi cartera", "🏦")
            return
        tickers = sorted(cr["posiciones"])
        acciones = tuple(t for t in tickers if (cr["posiciones"][t].get("clase") or clase_de(t)) == "Acciones")
        try:
            # Lo que se necesita más abajo (analistas, dividendos, otros activos) se descarga a la vez que se
            # revisa la cartera: la primera carga de la mañana tarda la mitad.
            with descargas_en_paralelo(cargar_activos, lambda: cargar_analistas(acciones),
                                       lambda: cargar_dividendos_varios(
                                           [t for t in tickers if (cr["posiciones"][t].get("clase") or clase_de(t))
                                            in ("Acciones", "Fondos y ETF")])):
                filas = revisar_cartera_real()
            activos_hoy = cargar_activos()
        except Exception as e:  # noqa: BLE001 - la página Hoy nunca debe romperse por la cartera
            st.caption(f"No se ha podido revisar tu cartera ahora mismo ({e}).")
            return
        filas_inf = {r["ticker"]: r for r in (inf or {}).get("ranking", [])}
        posiciones = [{"ticker": f["ticker"], "acciones": f["pos"]["acciones"], "precio_medio": f["pos"]["precio_medio"],
                       "fx_medio": f["pos"].get("fx_medio", 1.0), "precio": f["precio"], "fx": f["fx"],
                       "stop": f["pos"].get("stop"), "clase": f["clase"], "nombre": f["nombre"],
                   "sin_stop": f["pos"].get("sin_stop", False)}
                      for f in filas if f["precio"]]
        dg = diagnostico.diagnosticar(posiciones, cuenta_activa().get("otros_ahorros", 0.0), _perfil_guardado(),
                                      pf.tarifa,
                                      filas_inf)
        valor = sum(p["acciones"] * p["precio"] * p["fx"] for p in posiciones)
        cambio = sum(p["acciones"] * p["precio"] * p["fx"] * (1 - 1 / (1 + f["var_1d"]))
                     for p, f in zip(posiciones, [f for f in filas if f["precio"]]) if f.get("var_1d") is not None)
        invertido = sum(p["acciones"] * p["precio_medio"] * p["fx_medio"] for p in posiciones)
        c = st.columns(3 if not pf.movil else 2)
        c[0].metric("Tu dinero invertido vale", eur(valor), f"{eur(cambio)} en la sesión", delta_color="normal")
        c[1 % len(c)].metric("Ganancia o pérdida total", eur(valor - invertido),
                             pct((valor / invertido - 1) * 100, 1) if invertido else None)
        if dg.get("clases"):
            principal = max(dg["clases"].items(), key=lambda x: x[1])
            c[2 % len(c)].metric("Reparto", f"{principal[1] * 100:.0f} % {principal[0].lower()}",
                                 TITULO_SEMAFORO.get(dg["semaforo"], ""), delta_color="off", delta_arrow="off")
        st.caption(linea_actualizado())
        decisiones_por_accion(filas)
        try:
            proximos_div = dividendos.calendario(resumenes_dividendos(filas), dias=10)
        except Exception:  # noqa: BLE001 - sin datos de dividendos, el resto sigue
            proximos_div = []
        # Lo de cada acción ya está arriba: aquí, solo lo del mercado, el calendario y el resto de la cartera.
        dg_resto = {**dg, "hallazgos": [x for x in dg.get("hallazgos", []) if not x["titulo"].startswith("Sin stop")
                                        and " pesa el " not in x["titulo"]]}
        resto = asesor_diario.plan_del_dia(dg_resto, [{**f, "nivel": "mantener"} for f in filas], inf, activos_hoy,
                                           dividendos=proximos_div)
        resto = [a for a in resto if a["titulo"] != "Nada urgente hoy"]
        if resto:
            st.markdown("**Además, hoy:**")
            for a in resto:
                st.markdown(f"{a['icono']} **{a['titulo']}** — {a['texto']}")
        bloque_eventos_cerca(filas)
        bloque_semana(posiciones)
        enlace("bankinter", "Ver el diagnóstico completo de tu cartera", "🩺")
        st.caption("Consejos educativos a partir de tus datos y de reglas de gestión prudente; no sustituyen a un "
                   "asesor financiero registrado en la CNMV.")


def eventos_de(filas_o_tickers, dias: int = 30) -> list[dict]:
    """Resultados y dividendos de los próximos `dias` días para tus valores (o una lista de tickers)."""
    nombres = ({f["ticker"]: f["nombre"] for f in filas_o_tickers} if filas_o_tickers and
               isinstance(filas_o_tickers[0], dict) else {t: nombre_de(t) for t in filas_o_tickers})
    if not nombres:
        return []
    try:
        funds = cargar_fundamentales_varios(tuple(sorted(nombres)))
    except Exception:  # noqa: BLE001
        return []
    return eventos.proximos(nombres, funds, dias=dias)


def bloque_eventos_cerca(filas: list[dict]) -> None:
    """«📅 Próximos 14 días» en Hoy: resultados, fecha ex-dividendo y pagos de tus valores."""
    lista = eventos_de(filas, 14)
    if not lista:
        return
    st.markdown("**📅 Próximos 14 días:**")
    for e in lista:
        st.markdown(f"{e['icono']} **{e['nombre']}** — {e['titulo'].lower()} {eventos.cuando(e)}")
    st.caption("Fechas de Yahoo Finance; las de resultados a veces son estimadas. Todo el calendario en 📒 Seguimiento.")


def _ocultar_importes(texto: str) -> str:
    texto = re.sub(r"\(≈ [\d.,]+ €\)", "(≈ ••• €)", texto)
    return re.sub(r"unas [\d.,]+ acciones", "unas ••• acciones", texto)


def decisiones_por_accion(filas: list[dict]) -> None:
    """«📌 Qué hacer con cada acción»: esperar, diversificar, poner stop-loss, vigilar o vender, con lo que ve la app
    y el consenso de los analistas de los brókers."""
    con_precio = [f for f in filas if f["precio"]]
    if not con_precio:
        return
    valores = {f["ticker"]: f["pos"]["acciones"] * f["precio"] * f["fx"] for f in con_precio}
    total = sum(valores.values()) + max(cuenta_activa().get("otros_ahorros", 0.0), 0.0)
    acciones = tuple(sorted(f["ticker"] for f in con_precio if f["clase"] == "Acciones"))
    try:
        funds = cargar_fundamentales_varios(acciones)
        extra = cargar_analistas(acciones)
    except Exception:  # noqa: BLE001 - sin datos de analistas, se decide con el resto
        funds, extra = {}, {}
    tope = limite_empresa()
    lista = []
    for f in con_precio:
        analistas = (decision.consenso(funds.get(f["ticker"]), f["precio"], extra.get(f["ticker"]))
                     if f["clase"] == "Acciones" else None)
        lista.append((f, decision.decidir(f, valores[f["ticker"]], total, tope, analistas, f["precio"] * f["fx"])))
    orden = list(decision.ACCIONES)
    lista.sort(key=lambda x: orden.index(x[1]["clave"]))
    if privado():                    # sin importes ni número de acciones
        for _, d in lista:
            d["situacion"] = re.sub(r"Tienes [\d.,]+ acciones", "Tienes acciones", d.get("situacion") or "")
            d["texto"] = _ocultar_importes(d["texto"])
            d["tambien"] = [_ocultar_importes(x) for x in d["tambien"]]
    st.markdown("**📌 Qué hacer con cada acción tuya**")
    for f, d in lista:
        with st.container(border=True):
            st.markdown(f"**{f['nombre']}** · {d['peso'] * 100:.0f} % de tu dinero"
                        + (f"  \n<small>{d['situacion']}</small>" if d.get("situacion") else ""),
                        unsafe_allow_html=True)
            st.markdown(f"👉 Te recomiendo: {d['icono']} **{d['titulo']}**  \n{d['texto']}")
            for x in d["tambien"]:
                st.markdown(x)
            for m in d["motivos"]:
                st.caption(m)
            if d.get("analistas"):
                with st.expander("🏦 Qué dicen los analistas"):
                    for linea in d["analistas"]:
                        st.markdown(f"- {linea}")
    st.caption("Analistas: los de los bancos y brókers que siguen cada empresa (entre 10 y 30 en las grandes), "
               "recogidos por Yahoo Finance: qué recomiendan, a qué precio creen que llegará (la mediana, que no "
               "distorsiona un analista extremo) y si suben o bajan sus previsiones. La fiabilidad sube cuantos más "
               "son y más de acuerdo están. No se usan foros: ahí opina cualquiera, sin responsabilidad y a veces "
               "para mover el precio. Los analistas también fallan: es una mirada más, no la decisión.")


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
    broker = bankinter.broker() if bankinter.broker() != "Otro" else "tu banco"
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
    nombres = list(cuentas.asegurar(d))
    elegida = d["cuenta_activa"]
    cr = d["cartera_real"]
    if len(nombres) > 1:
        st.info(f"👤 Estás viendo la cuenta **{elegida}**. Cámbiala en el menú lateral (»): la app asesora a cada "
                "cuenta por separado y no las suma.")
    bloque_cuentas(d)

    filas = revisar_cartera_real()
    if filas:
        resumen_cartera(nombres, elegida)
        p_hacer, p_diag, p_div, p_comp, p_anadir = pestanas(["📋 Qué hacer", "🩺 Diagnóstico", "💶 Dividendos",
                                                              "📈 Rentabilidad", "➕ Añadir"], "mc_pestana")
        with p_hacer:
            if p_hacer.open:
                bloque_vigilar_todas(filas)
                for f in filas:
                    posicion_detalle(f, cr)
                bloque_telegram()
        with p_diag:
            if p_diag.open:
                comparado = bloque_diagnostico(filas)
                if not comparado:
                    st.subheader("🌦️ Qué le puede pasar a tu cartera")
                    from paginas_hoy import bloque_que_puede_pasar
                    pesos = {f["ticker"]: f["pos"]["acciones"] * f["precio"] * f["fx"] for f in filas if f["precio"]}
                    bloque_que_puede_pasar(pesos, sum(pesos.values()), 0.0, 0)
        with p_div:
            if p_div.open:
                bloque_dividendos(filas)
        with p_comp:
            if p_comp.open:
                bloque_comparativa(filas)
        with p_anadir:
            if p_anadir.open:
                bloque_anadir()
    else:
        st.caption("Aún no has registrado posiciones en esta cuenta. Impórtalas de tu banco o añádelas a mano.")
        bloque_anadir()
        bloque_telegram()

    palabras_de_la_pagina(["Concentración", "Diversificación", "Sector", "Volatilidad", "Caída máxima", "Stop-loss",
                           "Dividendo", "Fecha ex-dividendo", "Retención", "Ganancia patrimonial", "Base del ahorro",
                           "Compensación de pérdidas", "Regla de los 2 meses", "Fondo indexado", "Rebalanceo"])


def tabla_posiciones(filas: list[dict]) -> tuple[pd.DataFrame, float, float, float]:
    """La tabla de posiciones como la del bróker (Mi cartera y Cartera virtual usan la misma) y los totales:
    (tabla, valor, ganancia sin vender, cambio de hoy), en euros."""
    vista, total, ganancia, cambio_hoy = [], 0.0, 0.0, 0.0
    valores = {f["ticker"]: f["pos"]["acciones"] * f["precio"] * f["fx"] for f in filas if f["precio"]}
    total_valor = sum(valores.values())
    for f in filas:
        pos, precio = f["pos"], f["precio"]
        valor = valores.get(f["ticker"])
        invertido = pos["acciones"] * pos["precio_medio"] * pos.get("fx_medio", 1.0)
        total += valor or 0
        ganancia += (valor - invertido) if valor else 0
        if valor and f.get("var_1d") is not None:
            cambio_hoy += valor - valor / (1 + f["var_1d"])
        proteccion = (f"stop {num(pos['stop'], 2)}" if pos.get("stop") else
                      f"alarma {num(pos['alarma'], 2)}" if pos.get("sin_stop") and pos.get("alarma") else
                      "sin stop")
        if pos.get("objetivo"):
            proteccion += f" · objetivo {num(pos['objetivo'], 2)}"
        vista.append({
            "": ICONO_NIVEL[f["nivel"]], "Activo": f["nombre"],
            "Precio actual": round(precio, 2) if precio else None,
            "Hoy (%)": round(f["var_1d"] * 100, 2) if f.get("var_1d") is not None else None,
            "Precio compra": round(pos["precio_medio"], 2),
            "Títulos": pos["acciones"],
            "Invertido (€)": round(invertido, 2),
            "Valor (€)": round(valor, 2) if valor else None,
            "Ganancia (€)": round(valor - invertido, 2) if valor else None,
            "Ganancia (%)": round((precio / pos["precio_medio"] - 1) * 100, 1) if precio else None,
            "Peso (%)": round(valor / total_valor * 100, 1) if valor and total_valor else None,
            "Protección": proteccion, "Tipo": f["clase"],
            "Precio de": ({"tiempo_real": "⚡ tiempo real", "directo": "🟢 ahora (~15 min)"}.get(
                f["cotizacion"]["estado"], f"cierre {f['cotizacion']['fecha']:%d/%m}") if f.get("cotizacion")
                else "—")})
    return pd.DataFrame(vista), total, ganancia, cambio_hoy


def pintar_tabla_posiciones(tabla: pd.DataFrame, ayuda_peso: str) -> None:
    pf = perfil()
    if privado():                   # sin euros: precios, porcentajes y peso sí
        tabla = tabla.drop(columns=["Títulos", "Invertido (€)", "Valor (€)", "Ganancia (€)"])
    if pf.movil:
        tabla = tabla[[c for c in ("", "Activo", "Precio actual", "Hoy (%)", "Precio compra", "Ganancia (%)",
                                   "Ganancia (€)", "Valor (€)", "Peso (%)", "Títulos", "Protección") if c in tabla]]
    st.dataframe(tabla, hide_index=True, width="stretch", column_config={
        "": st.column_config.TextColumn(width=30, pinned=True),
        "Activo": st.column_config.TextColumn(pinned=True),
        "Precio actual": st.column_config.NumberColumn(format="localized",
                                                       help="En la moneda del valor, como en tu bróker."),
        "Hoy (%)": st.column_config.NumberColumn(format="%+.2f %%", help="Frente al cierre anterior."),
        "Precio compra": st.column_config.NumberColumn(format="localized", help="Tu precio medio de compra."),
        "Invertido (€)": st.column_config.NumberColumn(format="localized"),
        "Valor (€)": st.column_config.NumberColumn(format="localized"),
        "Ganancia (€)": st.column_config.NumberColumn(format="localized"),
        "Ganancia (%)": st.column_config.NumberColumn(format="%+.1f %%"),
        "Peso (%)": st.column_config.NumberColumn(format="%.1f %%", help=ayuda_peso),
    })
    st.caption("Precios en la moneda de cada valor, como en tu bróker; invertido, valor y ganancias en euros. La "
               "ganancia en % es la del precio (sin comisiones ni efecto divisa). "
               + " · ".join(f"{i} {t}" for t, i in (("vender", "🔴"), ("vigilar", "🟠"), ("poner stop", "🟡"),
                                                     ("subir stop", "🟢⬆️"), ("mantener", "🟢")))
               + (". En el móvil, desliza la tabla hacia la izquierda para ver más columnas." if pf.movil else "."))


@st.fragment(run_every=SEGUNDOS_REFRESCO)
def resumen_cartera(nombres: list[str], elegida: str):
    """Valor, ganancia, cambio de hoy y tabla de posiciones. Se refresca solo cada minuto."""
    pf = perfil()
    filas = revisar_cartera_real()
    if not filas:
        return
    avisos = [f for f in filas if f["nivel"] not in ("mantener",)]
    if avisos:
        st.warning(f"🔔 {len(avisos)} posición(es) necesitan tu atención.")
    tabla, total, ganancia, cambio_hoy = tabla_posiciones(filas)
    c = st.columns(3 if not pf.movil else 2)
    c[0].metric("Valor de tu cartera" if len(nombres) == 1 else f"Valor de «{elegida}»", eur(total))
    c[1].metric("Ganancia o pérdida (sin vender)", eur(ganancia),
                pct(ganancia / (total - ganancia) * 100, 1) if total - ganancia else None)
    c[2 % len(c)].metric("Hoy", eur(cambio_hoy),
                         pct(cambio_hoy / (total - cambio_hoy) * 100, 2) if total - cambio_hoy else None)
    pintar_tabla_posiciones(tabla, "Parte de lo que tienes invertido en esta cuenta. En 🧭 Hoy el peso cuenta "
                                   "también el dinero en cuentas y depósitos, por eso allí puede salir algo menor.")
    st.caption(linea_actualizado())


def bloque_cuentas(d: dict):
    """Crear, renombrar o borrar cuentas (por ejemplo, dos cuentas de valores en Bankinter)."""
    lista = d["cuentas"]
    with st.expander(f"🗂️ Cuentas ({len(lista)})" if len(lista) > 1 else "🗂️ ¿Llevas más de una cuenta?"):
        st.caption("Añade una cuenta por persona o por cuenta de valores (la tuya, la de tu madre, la de tu "
                   "hermano...). Cada una tiene sus acciones, su perfil, sus ahorros, sus avisos y su bróker, y la app "
                   "asesora a cada una por separado: nunca las suma. Cambias de cuenta en el menú lateral (»).")
        for n, c in lista.items():
            st.markdown(f"- {'👉 ' if n == d['cuenta_activa'] else ''}**{n}**: "
                        f"{len(c.get('posiciones', {}))} posiciones")
        c = st.columns([3, 1])
        nueva = c[0].text_input("Nombre de la nueva cuenta", placeholder="p. ej. Mamá", key="cta_nueva")
        if c[1].button("➕ Añadir", key="cta_anadir", width="stretch"):
            err = cuentas.nueva_cuenta(d, nueva)
            if err:
                st.error(err)
            else:
                cuentas.activar(d, nueva.strip())       # se abre la nueva para empezar a rellenarla
                olvidar_campos_de_cuenta()
                guardar_datos()
                st.rerun()
        c = st.columns([2, 2, 1])
        cual = c[0].selectbox("Cuenta", list(lista), key="cta_cual")
        nombre = c[1].text_input("Nuevo nombre", key="cta_nombre")
        if c[2].button("✏️ Renombrar", key="cta_renombrar", width="stretch"):
            err = cuentas.renombrar(d, cual, nombre)
            if err:
                st.error(err)
            else:
                guardar_datos()
                st.rerun()
        if len(lista) > 1:
            seguro = st.checkbox(f"Quiero borrar «{cual}» y lo que tiene apuntado", key="cta_seguro")
            if st.button(f"🗑️ Borrar «{cual}»", key="cta_borrar", disabled=not seguro):
                cuentas.borrar(d, cual)
                olvidar_campos_de_cuenta()
                guardar_datos()
                st.rerun()


def bloque_anadir():
    """Añadir posiciones a la cuenta activa: archivo del banco, tabla pegada o a mano; y copia de seguridad."""
    pf = perfil()
    d = datos_usuario()
    cuenta = d["cuenta_activa"]
    st.markdown("#### ➕ Añadir posiciones" + (f" a «{cuenta}»" if len(d["cuentas"]) > 1 else ""))
    cr = d["cuentas"][cuenta]
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
            revisar_e_importar(leidas, "archivo", cuenta)
    with t3:
        st.markdown("Si tu banco solo enseña la cartera en pantalla (o en PDF), **selecciona la tabla, cópiala y "
                    "pégala aquí** con la fila de títulos de las columnas.")
        texto = st.text_area("Tabla copiada", height=150,
                             placeholder="Valor	ISIN	Títulos	Precio medio\nIBERDROLA	ES0144580Y14	200	12,50")
        if texto.strip():
            revisar_e_importar(importador.leer_texto(texto, resolver=buscar_simbolo), "pegado", cuenta)
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
            solo_vigilar = st.checkbox(f"La compré sin stop-loss: vigílala y avísame si cae un "
                                       f"{CAIDA_ALARMA * 100:.0f} %", value=True,
                                       help="Solo si no pones stop-loss. Avisar no es vender: la decisión es tuya.")
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
                                      nota="Registrada a mano",
                                      fx=fx(t, cargar_fundamentales(t)) or 1.0)
                if err:
                    st.error(err)
                else:
                    cr["posiciones"][t].update(nombre=nombre or cr["posiciones"][t].get("nombre"),
                                               clase=clase_de(t, tipo, nombre))
                    if solo_vigilar and not stop and cr["posiciones"][t]["clase"] == "Acciones":
                        try:
                            df = cargar_varios((t,), "1mo").get(t)
                            actual = float(df["Close"].iloc[-1]) if df is not None and not df.empty else precio
                        except Exception:  # noqa: BLE001
                            actual = precio
                        vigilar_sin_stop(t, nombre_posicion(t, cr["posiciones"][t]), None, actual)
                    guardar_datos()
                    st.rerun()
    copia_seguridad()


ICONO_GRAVEDAD = {"alta": "🔴", "media": "🟠", "baja": "🔵", "ok": "🟢"}
TITULO_SEMAFORO = {"rojo": "🔴 Necesita cambios", "ambar": "🟠 Mejorable", "verde": "🟢 Bien construida"}


def _perfil_guardado() -> str | None:
    """El perfil de la cuenta: el que elegiste a mano en el Diagnóstico o, si no, el del test de 🎯 Mi plan."""
    if cuenta_activa().get("perfil_elegido"):
        return cuenta_activa()["perfil_elegido"]
    p = cuenta_activa().get("perfil_inversor")
    if not p:
        return None
    try:
        return asesor.perfil_inversor(p["horizonte"], p["reaccion"], p["experiencia"], p["colchon"],
                                      p.get("deudas", False)).nombre
    except (KeyError, TypeError):
        return None


def resumenes_dividendos(filas: list[dict]) -> list[dict]:
    funds = cargar_fundamentales_varios(tuple(sorted(f["ticker"] for f in filas)))
    divs = cargar_dividendos_varios([f["ticker"] for f in filas if f["clase"] in ("Acciones", "Fondos y ETF")])
    salida = []
    for f in filas:
        if not f["precio"] or f["clase"] not in ("Acciones", "Fondos y ETF"):
            continue
        r = dividendos.resumen(f["ticker"], divs.get(f["ticker"]), (funds.get(f["ticker"]) or {}).get(
            "exDividendDate"), f["pos"]["acciones"], f["precio"], f["fx"],
            fecha_compra=f["pos"].get("fecha") if f["pos"].get("fecha", "") < date.today().isoformat() else None,
            historial=cuenta_activa().get("historial"))
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
    c = st.columns(3 if not perfil().movil else 2)
    c[0].metric("Al año (bruto)", eur(bruto), help="Lo pagado por tus acciones en los últimos 12 meses.")
    c[1 % len(c)].metric("Te quedan (neto)", eur(sum(r["neto_ano"] for r in lista)),
                         "tras la retención del 19 %", delta_color="off", delta_arrow="off")
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
def bloque_dentro_de_fondos(filas: list[dict]):
    """«🔍 Qué hay dentro de tus fondos»: empresas y sectores que tienes de verdad sumando tus acciones y lo que
    llevan tus fondos y ETF (las 10 mayores posiciones de cada uno), y si alguna la tienes por partida doble."""
    valores = {f["ticker"]: f["pos"]["acciones"] * f["precio"] * f["fx"] for f in filas if f["precio"]}
    fondos_tk = {f["ticker"]: valores[f["ticker"]] for f in filas if f["clase"] == "Fondos y ETF"
                 and f["ticker"] in valores}
    if not fondos_tk:
        return
    directas = {f["ticker"]: valores[f["ticker"]] for f in filas if f["clase"] == "Acciones" and f["ticker"] in valores}
    try:
        comp = cargar_composiciones(tuple(sorted(fondos_tk)))
    except Exception:  # noqa: BLE001
        return
    if not any(c.get("top") for c in comp.values()):
        return
    nombres = {f["ticker"]: f["nombre"] for f in filas}
    r = fondos.exposicion(directas, fondos_tk, comp, nombres)
    with st.expander("🔍 Qué hay dentro de tus fondos y ETF", expanded=bool(r["solapes"])):
        for e in r["solapes"]:
            dentro = ", ".join(sorted(set(e["fondos"])))
            st.warning(f"**{e['nombre']}**: la tienes directamente y también dentro de {dentro}. En total es el "
                       f"{e['peso'] * 100:.1f} % de tu dinero.")
        top = [e for e in r["empresas"] if e["via_fondos"] > 0][:15]
        st.dataframe(pd.DataFrame([{
            "Empresa": e["nombre"], "Directo (%)": round(e["directo"] / sum(valores.values()) * 100, 2),
            "Dentro de fondos (%)": round(e["via_fondos"] / sum(valores.values()) * 100, 2),
            "Total (%)": round(e["peso"] * 100, 2)} for e in top]), hide_index=True, width="stretch",
            column_config={c: st.column_config.NumberColumn(format="%.2f %%")
                           for c in ("Directo (%)", "Dentro de fondos (%)", "Total (%)")})
        if r["sectores"]:
            total_f = sum(fondos_tk.values())
            st.markdown("**Sectores dentro de tus fondos:** " + " · ".join(
                f"{s_} {v / total_f * 100:.0f} %" for s_, v in list(r["sectores"].items())[:6]))
        st.caption("Con las 10 mayores posiciones de cada fondo (Yahoo Finance); el resto del fondo está muy "
                   "repartido entre cientos de empresas. Así ves tu exposición REAL: un fondo mundial ya lleva mucha "
                   "tecnología de EEUU (Nvidia, Apple, Microsoft...).")


def bloque_rentabilidad_periodos(filas: list[dict]):
    """Rentabilidad de lo que tienes hoy en cada periodo (hoy, semana, mes, año...), frente al IBEX y a un fondo
    indexado mundial, como en Ghostfolio o en el bróker."""
    con_precio = [f for f in filas if f["precio"]]
    if not con_precio:
        return
    acciones = {f["ticker"]: f["pos"]["acciones"] for f in con_precio}
    hist = historia_larga_eur(tuple(acciones))
    cierres = {t: df["Close"] for t, df in hist.items() if df is not None and not df.empty}
    serie = rentabilidad.valor_diario(acciones, cierres)
    if len(serie) < 5:
        return
    _, total, _, cambio_hoy = tabla_posiciones(con_precio)
    hoy_pct = cambio_hoy / (total - cambio_hoy) * 100 if total - cambio_hoy else None
    try:
        refs_hoy = cotizaciones_ahora(("^IBEX", "IWDA.AS"), esperar=False)
    except Exception:  # noqa: BLE001
        refs_hoy = {}
    columnas = {"Tu cartera": rentabilidad.por_periodos(serie, hoy_pct)}
    for t, nombre in (("^IBEX", "IBEX 35"), ("IWDA.AS", "Fondo mundial")):
        if t in cierres:
            columnas[nombre] = rentabilidad.por_periodos(cierres[t], (refs_hoy.get(t) or {}).get("variacion_pct"))
    periodos = [p["periodo"] for p in columnas["Tu cartera"]]
    tabla = pd.DataFrame({"Periodo": periodos, **{
        nombre: [next((round(p["pct"], 2) for p in lista if p["periodo"] == per), None) for per in periodos]
        for nombre, lista in columnas.items()}})
    st.subheader("📈 Rentabilidad por periodos")
    st.dataframe(tabla, hide_index=True, width="stretch", column_config={
        n: st.column_config.NumberColumn(format="%+.2f %%") for n in columnas})
    st.caption("Cómo le ha ido a lo que tienes **hoy** en cada periodo (títulos de hoy × precio de cada día, en "
               "euros, con dividendos). No cuenta cuándo compraste ni lo que metiste o sacaste: es la «foto» de tu "
               "cartera actual, comparable con el IBEX (sin dividendos) y con un fondo indexado mundial.")


def bloque_comparativa(filas: list[dict]):
    """Tu cartera (con el reparto de hoy) frente a un fondo indexado mundial y el IBEX."""
    bloque_rentabilidad_periodos(filas)
    st.subheader("📊 Tu cartera frente a un fondo indexado")
    anos = st.segmented_control("Periodo", [1, 3, 5], default=3, format_func=lambda a: f"{a} año{'s' if a > 1 else ''}",
                                key="cmp_anos") or 3
    pesos = {f["ticker"]: f["pos"]["acciones"] * f["precio"] * f["fx"] for f in filas if f["precio"]}
    if not pesos:
        return
    with st.spinner("Calculando con la historia real..."):
        res = comparativa.comparar(historia_larga_eur(tuple(pesos)), pesos, int(anos))
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
    d = cuenta_activa()
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
    if plan["ahorro"] > 0:
        k = st.columns(2)
        k[0].metric("IRPF vendiendo todo ahora", eur(plan["irpf_todo_ahora"]))
        k[1].metric("IRPF con este plan", eur(plan["irpf_plan"]), f"-{eur(plan['ahorro'])}", delta_color="inverse")
    else:
        st.metric("IRPF aproximado de estas ventas", eur(plan["irpf_plan"]))
    for i, paso in enumerate(plan["pasos"], 1):
        with st.container(border=True):
            st.markdown(f"**Paso {i} · {paso['cuando']}** — IRPF de ese año por estas ventas: ≈ {eur(paso['irpf'])}")
            st.dataframe(pd.DataFrame([{"Vender": v["nombre"], "Títulos": v["acciones"], "Importe": eur(v["importe"]),
                                        "Resultado": eur(v["ganancia"])} for v in paso["ventas"]]),
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
    st.subheader("🩺 Diagnóstico de tu cartera")
    guardado = _perfil_guardado()
    c = st.columns(2)
    opciones = ["Conservador", "Moderado", "Dinámico", "Aún no lo sé"]
    if "perfil_diag" not in st.session_state:
        st.session_state["perfil_diag"] = guardado or "Aún no lo sé"
    perfil_txt = c[0].selectbox("Tu perfil", opciones, key="perfil_diag",
                                help="Calcúlalo en 🎯 Mi plan (5 preguntas). Decide cuánto conviene tener en "
                                     "acciones sueltas y cuánto en fondos.")
    otros = c[1].number_input("Dinero en cuentas y depósitos (€)", 0.0, 100_000_000.0,
                              float(cuenta_activa().get("otros_ahorros", 0.0)), 1000.0,
                              help="Lo que tienes en liquidez fuera de estas inversiones. Los fondos, planes o "
                                   "acciones de otros bancos, mejor impórtalos como posiciones para analizarlos.")
    if otros != cuenta_activa().get("otros_ahorros", 0.0):
        cuenta_activa()["otros_ahorros"] = otros
        guardar_datos()
    perfil_nombre = None if perfil_txt == "Aún no lo sé" else perfil_txt
    if perfil_nombre and perfil_nombre != guardado:    # se guarda: así Hoy usa los mismos límites
        cuenta_activa()["perfil_elegido"] = perfil_nombre
        guardar_datos()
    inf = cargar_informe() or {}
    filas_inf = {r["ticker"]: r for r in inf.get("ranking", [])}
    posiciones = [{"ticker": f["ticker"], "acciones": f["pos"]["acciones"], "precio_medio": f["pos"]["precio_medio"],
                   "fx_medio": f["pos"].get("fx_medio", 1.0), "precio": f["precio"], "fx": f["fx"],
                   "stop": f["pos"].get("stop"), "clase": f["clase"], "nombre": f["nombre"],
                   "sin_stop": f["pos"].get("sin_stop", False)}
                  for f in filas if f["precio"]]
    dg = diagnostico.diagnosticar(posiciones, otros, perfil_nombre, pf.tarifa, filas_inf)
    if dg["semaforo"] == "sin_datos":
        return False
    lim = dg["limites"]
    st.caption(("📏 **Límites para un perfil " + perfil_nombre.lower() + "**: " if perfil_nombre else
                "📏 **Sin perfil se usan los límites más amplios** (elige el tuyo para afinarlos): ")
               + f"máximo {lim['empresa'] * 100:.0f} % por empresa, {lim['sector'] * 100:.0f} % por sector y "
               f"{lim['pais'] * 100:.0f} % en un país; al menos {lim['empresas']} empresas"
               + (f"; como mucho {lim['bolsa'] * 100:.0f} % de tu dinero en bolsa." if lim.get("bolsa") else "."))

    mayor = dg["empresas"][0]
    m = st.columns(2 if pf.movil else 4)
    m[0].metric("Estado", TITULO_SEMAFORO[dg["semaforo"]])
    m[1].metric("Mayor peso", f"{mayor['peso'] * 100:.0f} %".replace(".", ","), mayor["nombre"], delta_color="off", delta_arrow="off")
    m[2 % len(m)].metric("Equivale a", f"{num(dg['n_efectivo'], 1)} empresas",
                         help="1 / suma de los pesos al cuadrado: cuántas empresas a partes iguales tendrían el "
                              "mismo riesgo de concentración. Lo prudente es 5 o más (un fondo indexado: más de 1.000).")
    if dg["paises"]:
        pais, w_pais = max(dg["paises"].items(), key=lambda x: x[1])
        m[3 % len(m)].metric("País principal", f"{pais} {w_pais * 100:.0f} %")
    else:                            # solo fondos, ETF u otros activos: no hay acciones de un país concreto
        m[3 % len(m)].metric("País principal", "Varios", "fondos y ETF", delta_color="off", delta_arrow="off")

    figura = go.Figure(go.Bar(x=[e["peso"] * 100 for e in dg["empresas"]], y=[e["nombre"] for e in dg["empresas"]],
                              orientation="h", marker_color=["#d62728" if e["peso"] > lim["empresa"]
                                                             else "#2ca02c" for e in dg["empresas"]],
                              text=[f"{e['peso'] * 100:.0f} %" for e in dg["empresas"]], textposition="auto"))
    figura.add_vline(x=lim["empresa"] * 100, line_dash="dash",
                     annotation_text=f"máximo prudente {lim['empresa'] * 100:.0f} %")
    figura.update_layout(height=80 + 45 * len(dg["empresas"]), margin=dict(l=0, r=0, t=30, b=0),
                         xaxis_title="% de tu dinero", yaxis=dict(autorange="reversed"))
    mostrar_plotly(figura)

    for x in dg["hallazgos"]:
        with st.expander(f"{ICONO_GRAVEDAD[x['gravedad']]} {x['titulo']}", expanded=x["gravedad"] == "alta"):
            st.write(x["texto"])
    bloque_dentro_de_fondos(filas)

    if not dg["propuesta"]:
        return False
    st.markdown("#### 🧭 Propuesta: repartir el riesgo")
    st.write(f"Para que ninguna empresa pase del {lim['empresa'] * 100:.0f} % de tu dinero, venderías:")
    propuesta = pd.DataFrame([{
        "Empresa": v["nombre"], "Vender (títulos)": v["acciones"], "Importe": eur(v["importe"]),
        "Resultado a declarar": eur(v["ganancia"]), "Peso después": f"{v['queda_peso'] * 100:.0f} %"}
        for v in dg["propuesta"]])
    if pf.movil:
        propuesta = propuesta[["Empresa", "Vender (títulos)", "Importe"]]
    st.dataframe(propuesta, hide_index=True, width="stretch")
    k = st.columns(2 if pf.movil else 3)
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
        hist_eur = historia_larga_eur(tuple(set(dg["pesos_antes"]) | set(dg["pesos_despues"])))
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


def revisar_e_importar(leidas: pd.DataFrame, origen: str, cuenta: str):
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
    varias = len(cuentas.asegurar(d)) > 1
    reemplazar = st.checkbox(f"Reemplazar lo que tengo en «{cuenta}» por esta tabla" if varias else
                             "Reemplazar mi cartera actual por esta", value=True, key=f"rep_{origen}")
    if st.button("📥 Importar" + (f" a «{cuenta}»" if varias else ""), type="primary", key=f"imp_{origen}"):
        previas = d["cuentas"][cuenta].get("posiciones", {})
        conservar = {t: {k: p[k] for k in ("stop", "sin_stop", "alarma") if p.get(k)} for t, p in previas.items()}
        cr = d["cuentas"][cuenta]
        if reemplazar:
            # Se vacían las posiciones, pero se quedan el perfil, los avisos, las ventas apuntadas (para la Renta)
            # y demás de la cuenta; solo se quitan las compras de importaciones anteriores.
            cr["posiciones"] = {}
            cr["historial"] = [h for h in cr.get("historial", []) if not (
                h.get("tipo") == "Compra" and str(h.get("motivo") or "").startswith("Importada"))]
        validas = editada[editada["ticker"].astype(str).str.strip().ne("") & editada["ticker"].notna()]
        try:     # la divisa real de cada valor (un ETF de Londres puede cotizar en dólares, no en peniques)
            funds = cargar_fundamentales_varios(tuple(sorted({str(t).strip().upper() for t in validas["ticker"]})))
        except Exception:  # noqa: BLE001
            funds = {}
        malas = []
        for _, r in editada.iterrows():
            cantidad = _cantidad(r["acciones"]) if not pd.isna(r["acciones"]) else 0
            if (not r["ticker"] or pd.isna(r["ticker"]) or not r["precio_medio"] or pd.isna(r["precio_medio"])
                    or not cantidad or cantidad <= 0):
                malas.append(str(r["nombre"]))
                continue
            tk = str(r["ticker"]).strip().upper()
            cartera.comprar(cr, tk, cantidad, float(r["precio_medio"]), pf.tarifa,
                            nota=f"Importada ({origen})", fx=fx(tk, funds.get(tk)) or 1.0)
            cr["posiciones"][tk].update(nombre=str(r["nombre"]), clase=r["clase"] if r["clase"] in CLASES
                                        else clase_de(tk, None, str(r["nombre"])), **conservar.get(tk, {}))
        guardar_datos()
        if malas:
            st.warning("No se importaron (falta código, títulos o precio): " + ", ".join(malas))
        st.rerun()


CAIDA_ALARMA = 0.10        # nivel de alarma por defecto: un 10 % por debajo del precio de hoy
NOTA_ALARMA = "Nivel de alarma de tu posición sin stop-loss"


def _posiciones_de(d: dict, ticker: str) -> list[dict]:
    """La posición de ese valor en la cuenta activa (lista vacía si no lo tiene)."""
    pos = cuentas.activa(d).get("posiciones", {}).get(ticker)
    return [pos] if pos else []


def vigilar_sin_stop(ticker: str, nombre: str, nivel: float | None, precio_actual: float | None) -> str | None:
    """Marca la posición como «sin stop-loss, solo vigilar» con su nivel de alarma y crea (o cambia) el aviso de
    precio que avisa en la app y por Telegram. Devuelve un error o None. No guarda: llama luego a guardar_datos()."""
    d = datos_usuario()
    if nivel is None and precio_actual:
        nivel = round(precio_actual * (1 - CAIDA_ALARMA), 2)
    lista = cuenta_activa().setdefault("alertas", [])
    lista[:] = [a for a in lista if not (a.get("ticker") == ticker and a.get("nota") == NOTA_ALARMA)]
    if nivel:
        err = alertas.nueva(lista, ticker, nombre, "baja", nivel, precio_actual, NOTA_ALARMA)
        if err:
            return err
    for pos in _posiciones_de(d, ticker):
        pos.update(sin_stop=True, alarma=nivel, stop=None)
    if not st.session_state.get(f"ss_{ticker}"):       # si el interruptor ya está encendido, no se toca
        try:
            st.session_state[f"ss_{ticker}"] = True
        except Exception:  # noqa: BLE001 - el interruptor ya se ha pintado en esta vuelta: se pondrá en la siguiente
            st.session_state.setdefault("_ss_resincronizar", set()).add(ticker)
    return None


def dejar_de_vigilar(ticker: str) -> None:
    d = datos_usuario()
    for pos in _posiciones_de(d, ticker):
        pos.pop("sin_stop", None)
        pos.pop("alarma", None)
    cta = cuenta_activa()
    cta["alertas"] = [a for a in cta.get("alertas", []) if not (a.get("ticker") == ticker and a.get("nota") == NOTA_ALARMA)]
    st.session_state[f"ss_{ticker}"] = False


def _al_cambiar_vigilancia(ticker: str) -> None:
    if not st.session_state.get(f"ss_{ticker}"):
        dejar_de_vigilar(ticker)
        guardar_datos()


def bloque_vigilar_todas(filas: list[dict]):
    """Un botón para marcar de golpe las acciones sin stop-loss como «solo vigilar»."""
    sin = [f for f in filas if f["clase"] == "Acciones" and f["precio"] and not f["pos"].get("stop")
           and not f["pos"].get("sin_stop")]
    if not sin:
        return
    with st.container(border=True):
        st.markdown(f"**¿Las compraste sin stop-loss a propósito?** ({', '.join(f['nombre'] for f in sin)})")
        st.caption(f"La app dejará de pedirte el stop y las vigilará por ti: te avisa (aquí, en 🧭 Hoy y por Telegram) "
                   f"si alguna cae un {CAIDA_ALARMA * 100:.0f} % desde el precio de hoy. Avisar no es vender: la "
                   "decisión es tuya. Puedes cambiar el nivel de cada una abajo.")
        if st.button("👀 Vigilarlas sin stop-loss", key="vigilar_todas", width="stretch"):
            for f in sin:
                vigilar_sin_stop(f["ticker"], f["nombre"], None, f["precio"])
            guardar_datos()
            st.rerun()


# Los botones de cada posición hacen su trabajo ANTES de pintar la página (callbacks): así basta con una pasada y el
# cambio se ve al momento, sin recalcular la página dos veces.
def _al_guardar_stop(t: str) -> None:
    pos = cuenta_activa()["posiciones"].get(t)
    if not pos:
        return
    nuevo = st.session_state.get(f"stop_{t}") or None
    pos["stop"] = nuevo
    if nuevo:
        dejar_de_vigilar(t)          # con stop-loss puesto ya no hace falta el nivel de alarma
    guardar_datos()


def _al_vender(t: str, nombre: str, fx_: float) -> None:
    cr = cuenta_activa()
    n, precio_v = st.session_state.get(f"nv_{t}"), st.session_state.get(f"pv_{t}") or 0.0
    por_que = (st.session_state.get(f"pq_{t}") or "").strip()
    err = cartera.vender(cr, t, n, precio_v, perfil().tarifa, motivo=por_que or "Venta registrada", fx=fx_)
    if err:
        st.session_state[f"err_{t}"] = err
        return
    if por_que:
        from bolsa import diario
        diario.nueva(cr.setdefault("diario", []), t, nombre, "Venta", precio_v, por_que)
    for k in (f"nv_{t}", f"pv_{t}", f"pq_{t}"):
        st.session_state.pop(k, None)
    guardar_datos()


def _al_quitar(t: str) -> None:
    cuenta_activa()["posiciones"].pop(t, None)
    guardar_datos()


def _al_vigilar(t: str, nombre: str, precio: float) -> None:
    err = vigilar_sin_stop(t, nombre, st.session_state.get(f"alarma_{t}") or None, precio)
    if err:
        st.session_state[f"err_{t}"] = err
    else:
        guardar_datos()


def _editar_posicion(f: dict, cr: dict):
    """Stop-loss, venta y quitar, en la cuenta `cr`."""
    t, pos = f["ticker"], f["pos"]
    if st.session_state.get(f"err_{t}"):
        st.error(st.session_state.pop(f"err_{t}"))
    c = st.columns(3)
    c[0].number_input("Stop-loss que tienes puesto", 0.0, value=float(pos.get("stop") or 0.0), key=f"stop_{t}")
    c[0].button("Guardar stop", key=f"gstop_{t}", on_click=_al_guardar_stop, args=(t,))
    entera = float(pos["acciones"]).is_integer()
    tiene = int(pos["acciones"]) if entera else float(pos["acciones"])
    c[1].number_input("Títulos vendidos", 1 if entera else 0.0001, tiene, tiene, 1 if entera else 0.0001,
                      key=f"nv_{t}", format=None if entera else "%.4f", help="Pon menos si solo has vendido una parte.")
    c[1].number_input("Vendida a (precio)", 0.0, value=float(f["precio"] or 0.0), key=f"pv_{t}")
    c[1].text_input("¿Por qué vendes? (va a tu 📓 diario)", key=f"pq_{t}")
    c[1].button("Registrar venta", key=f"vend_{t}", on_click=_al_vender, args=(t, f["nombre"], f["fx"]))
    c[2].button("🗑️ Quitar sin vender", key=f"del_{t}", on_click=_al_quitar, args=(t,))


def posicion_detalle(f: dict, cr: dict):
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
        _editar_posicion(f, cr)
        if f["clase"] == "Acciones" and f["precio"]:
            pendientes = st.session_state.get("_ss_resincronizar", set())
            if f"ss_{t}" not in st.session_state or t in pendientes:
                st.session_state[f"ss_{t}"] = bool(pos.get("sin_stop"))
                pendientes.discard(t)
            solo = st.toggle("Sin stop-loss: vigílala tú y avísame si cae", key=f"ss_{t}",
                             on_change=_al_cambiar_vigilancia, args=(t,),
                             help="Para acciones compradas sin stop-loss a propósito (largo plazo). La app deja de "
                                  "pedirte el stop y te avisa si baja de tu nivel de alarma; no vende nada.")
            if solo:
                v = st.columns([2, 1])
                v[0].number_input("Nivel de alarma (avisa, no vende)", 0.0,
                                          value=float(pos.get("alarma") or round(f["precio"] * (1 - CAIDA_ALARMA), 2)),
                                          key=f"alarma_{t}")
                v[1].button("Guardar", key=f"gss_{t}", width="stretch", on_click=_al_vigilar,
                            args=(t, f["nombre"], f["precio"]))


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
            if st.form_submit_button("Registrar en mi cartera" + (f" («{d['cuenta_activa']}»)"
                                                                  if len(d.get("cuentas", {})) > 1 else ""),
                                     type="primary"):
                cr = d["cartera_real"]
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
