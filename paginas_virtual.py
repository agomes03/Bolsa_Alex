"""🎮 Cartera virtual que funciona como el bróker: cotización en directo (con el retraso habitual), órdenes
limitadas, a mercado y stop que se ejecutan cuando el precio llega, órdenes pendientes y comisiones reales."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from bolsa import asesor, cartera, costes, datos, ejercicios, horario, senales
from bolsa.tickers import TODAS_LAS_ACCIONES, nombre_de, sector_de
from ui_comun import (cargar_diario_real, cargar_historico, cargar_informe, cargar_intradia, datos_usuario,
                      estrategia_actual, eur, fecha, fx, guardar_datos, mercado_alcista_para, moneda_de, num, pct,
                      perfil)

TIPOS = {"Limitada": "limitada", "A mercado": "mercado", "Stop (con límite)": "stop"}
EXPLICA_TIPO = {
    "limitada": "Solo se ejecuta a tu precio o mejor. Si el precio no llega, la orden espera hasta su validez.",
    "mercado": "Se ejecuta ya al precio que haya (o en la apertura si el mercado está cerrado). Rápida, pero no "
               "controlas el precio.",
    "stop": "Se queda dormida hasta que el precio baja a la activación; entonces lanza una venta limitada. Es la "
            "forma de poner un stop-loss en Bankinter.",
}


def _cuando(iso: str) -> str:
    ts = pd.Timestamp(iso)
    return fecha(iso) if (ts.hour, ts.minute) == (0, 0) else f"{ts:%d/%m/%Y %H:%M}"


def _datos_valor(ticker: str):
    diario = cargar_diario_real(ticker)
    intra = cargar_intradia(ticker)
    return diario, intra, datos.cotizacion(diario, intra)


def cartera_manual():
    pf = perfil()
    d = datos_usuario()
    cv = d.setdefault("cartera_virtual", cartera.nueva(10_000.0))
    ahora = horario.ahora_madrid()
    ahora_iso = f"{ahora:%Y-%m-%dT%H:%M}"

    # 1. Actualizar: ejecutar órdenes pendientes y stop/objetivos con los precios reales desde la última vez.
    tickers = sorted(set(cv["posiciones"]) | {o["ticker"] for o in cv.get("ordenes", [])})
    info = {}
    if tickers:
        with st.spinner("Actualizando cotizaciones..."):
            for t in tickers:
                diario, intra, q = _datos_valor(t)
                info[t] = {"barras": datos.barras_ejecucion(diario, intra), "q": q,
                           "abierto": horario.estado_mercado(t)["abierto"], "fx": fx(t) or 1.0}
    barras = {t: v["barras"] for t, v in info.items()}
    eventos = cartera.revisar_ordenes(cv, barras, pf.tarifa, {t: v["fx"] for t, v in info.items()})
    eventos += cartera.ejecutar_ordenes(cv, barras, pf.tarifa, ahora_iso,
                                        {t: (v["q"]["precio"], v["abierto"]) for t, v in info.items() if v["q"]})
    for e in st.session_state.pop("_avisos_virtual", []) + eventos:
        st.info(e)
    if eventos:
        guardar_datos()

    precios = {t: v["q"]["precio"] for t, v in info.items() if v["q"]}
    fx_pos = {t: v["fx"] for t, v in info.items()}
    tabla, res = cartera.valorar(cv, precios, fx_pos)
    libre = cartera.disponible(cv, pf.tarifa)
    c = st.columns(2 if pf.movil else 4)
    c[0].metric("Valor total", eur(res["total"]), pct(res["ganancia_pct"], 1))
    c[1].metric("Ganancia / pérdida", eur(res["ganancia"]))
    c[2 % len(c)].metric("Disponible para comprar", eur(libre),
                         help="Efectivo menos lo reservado por tus órdenes de compra pendientes (el «saldo "
                              "comprometido» del bróker).")
    c[3 % len(c)].metric("Operaciones cerradas", f"{res['ganadoras']}/{res['operaciones_cerradas']} ganadoras")
    st.caption(f"Empezaste con {eur(cv['capital_inicial'])} el {fecha(cv['creada'])}. Precios reales con unos 15 "
               "minutos de retraso, comisiones de tu tarifa de Bankinter (barra lateral) y las mismas reglas de "
               "ejecución que el bróker.")

    bloque_evolucion(cv)
    if len(tabla):
        bloque_posiciones(cv, tabla, res, info)
    bloque_ordenes_pendientes(cv)
    bloque_operar_virtual(cv, libre, res["total"])
    bloque_ejercicios(cv)

    if cv["historial"]:
        with st.expander(f"📜 Historial ({len(cv['historial'])} movimientos)"):
            h = pd.DataFrame(cv["historial"]).iloc[::-1]
            vista = pd.DataFrame({
                "Fecha": h["fecha"].map(_cuando), "Operación": h["tipo"], "Empresa": h["ticker"].map(nombre_de),
                "Títulos": h["acciones"], "Precio": pd.to_numeric(h["precio"], errors="coerce").round(3),
                "Gastos (€)": pd.to_numeric(h["gastos"], errors="coerce").round(2),
                "Resultado (€)": pd.to_numeric(h["resultado"], errors="coerce").round(2),
                "Detalle": h["motivo"]})
            st.dataframe(vista, hide_index=True, width="stretch")
    with st.expander("♻️ Empezar de cero"):
        nuevo = st.number_input("Nuevo capital virtual (€)", 500.0, 1_000_000.0, 10_000.0, 500.0, key="v_reset_cap")
        if st.button("Reiniciar mi cartera virtual"):
            d["cartera_virtual"] = cartera.nueva(nuevo)
            guardar_datos()
            st.rerun()


# --------------------------------------------------------------------------- evolución
def bloque_evolucion(cv: dict):
    if not cv["historial"] or (date.today() - date.fromisoformat(cv["creada"])).days < 2:
        return
    with st.expander("📈 Evolución de tu cartera frente al IBEX 35"):
        operados = sorted({h["ticker"] for h in cv["historial"] if h["tipo"] in ("Compra", "Venta")})
        cierres = {}
        for t in operados:
            df = cargar_diario_real(t)
            if not df.empty:
                cierres[t] = df["Close"] * (fx(t) or 1.0)
        curva = cartera.evolucion(cv, cierres)
        ibex = cargar_diario_real("^IBEX")
        if curva.empty:
            st.caption("Aún no hay suficientes días para dibujar la evolución.")
            return
        fig = go.Figure(go.Scatter(x=curva.index, y=curva.values, name="Tu cartera", line=dict(width=3)))
        if not ibex.empty:
            ref = ibex["Close"].reindex(curva.index, method="ffill").dropna()
            if len(ref):
                fig.add_scatter(x=ref.index, y=ref / ref.iloc[0] * cv["capital_inicial"], name="IBEX 35",
                                line=dict(dash="dot"))
                st.caption(f"Tu cartera: {pct((curva.iloc[-1] / cv['capital_inicial'] - 1) * 100, 1)} · "
                           f"IBEX 35 en el mismo tiempo: {pct((ref.iloc[-1] / ref.iloc[0] - 1) * 100, 1)} "
                           "(sin dividendos).")
        fig.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=0), legend=dict(orientation="h", y=-0.2),
                          yaxis_title="€")
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


# --------------------------------------------------------------------------- posiciones
def bloque_posiciones(cv: dict, tabla: pd.DataFrame, res: dict, info: dict):
    pf = perfil()
    st.subheader("💼 Tu posición")
    var = {t: (v["q"] or {}).get("variacion_pct") for t, v in info.items()}
    def r(serie, dec):
        return pd.to_numeric(serie, errors="coerce").round(dec)

    vista = pd.DataFrame({
        "Valor": tabla["ticker"].map(nombre_de), "Títulos": tabla["acciones"],
        "Último": r(tabla["precio"], 3), "Var. día (%)": r(tabla["ticker"].map(var), 2),
        "Precio medio": r(tabla["precio_medio"], 3), "Valoración (€)": r(tabla["valor"], 2),
        "Rentab. (€)": r(tabla["resultado"], 2), "Rentab. (%)": r(tabla["resultado_pct"], 2),
        "Peso (%)": r(pd.to_numeric(tabla["valor"], errors="coerce") / res["total"] * 100, 1),
        "Stop": tabla["stop"], "Objetivo": tabla["objetivo"]})
    if pf.movil:
        vista = vista[["Valor", "Títulos", "Último", "Var. día (%)", "Rentab. (%)"]]
    st.dataframe(vista, hide_index=True, width="stretch")
    if vista["Último"].isna().any():
        st.warning("No hay cotización ahora mismo para algún valor: su valoración no se puede calcular.")
    st.caption("Como en «Posición» de Bankinter. Precios en la divisa de cada valor; importes en euros (la "
               "rentabilidad incluye las comisiones de compra).")

    with st.expander("✏️ Cambiar stop-loss u objetivo de una posición"):
        t = st.selectbox("Posición", list(cv["posiciones"]), format_func=nombre_de, key="v_cambiar_t")
        pos = cv["posiciones"][t]
        precio = info.get(t, {}).get("q", {}) or {}
        ultimo = precio.get("precio") or pos["precio_medio"]
        k = st.columns(2)
        stop = k[0].number_input("Stop-loss (0 = sin stop)", 0.0, value=float(pos.get("stop") or 0.0),
                                 key=f"v_stop_{t}", format="%.3f")
        obj = k[1].number_input("Objetivo (0 = sin objetivo)", 0.0, value=float(pos.get("objetivo") or 0.0),
                                key=f"v_obj_{t}", format="%.3f")
        if pos.get("stop") and stop and stop < pos["stop"]:
            st.warning("Estás bajando el stop-loss: la regla de oro es no bajarlo nunca (solo subirlo).")
        if stop and stop >= ultimo:
            st.error("El stop-loss tiene que estar por debajo del precio actual.")
        elif st.button("Guardar cambios", key=f"v_guardar_{t}"):
            pos["stop"], pos["objetivo"] = (stop or None), (obj or None)
            guardar_datos()
            st.success("Hecho. En Bankinter tendrías que anular la orden stop y crear otra: allí no se modifican.")


# --------------------------------------------------------------------------- órdenes pendientes
def bloque_ordenes_pendientes(cv: dict):
    pf = perfil()
    ordenes = cv.get("ordenes", [])
    if not ordenes:
        return
    st.subheader(f"🧾 Órdenes pendientes ({len(ordenes)})")
    for o in ordenes:
        m = moneda_de(o["ticker"])
        if o["tipo"] == "stop":
            precio = f"activación {eur(o['activacion'], m)} · límite {eur(o['limite'], m)}"
        elif o["tipo"] == "limitada":
            precio = f"límite {eur(o['limite'], m)}"
        else:
            precio = "a mercado"
        c1, c2 = st.columns([4, 1])
        c1.markdown(f"**{o['sentido'].capitalize()} {o['tipo']}** · {o['acciones']} {nombre_de(o['ticker'])} · "
                    f"{precio}  \n<small>Nº {o['id']} · enviada {_cuando(o['creada'])} · válida hasta "
                    f"{fecha(o['validez'])}</small>", unsafe_allow_html=True)
        if c2.button("Anular", key=f"v_anular_{o['id']}", width="stretch"):
            cartera.cancelar_orden(cv, o["id"], fecha=f"{horario.ahora_madrid():%Y-%m-%dT%H:%M}")
            guardar_datos()
            st.rerun()
    reservado = cartera.comprometido(cv, pf.tarifa)
    if reservado:
        st.caption(f"Dinero reservado por las órdenes de compra: {eur(reservado)}.")


# --------------------------------------------------------------------------- ficha y orden
def ficha_cotizacion(ticker: str, diario: pd.DataFrame, q: dict):
    pf = perfil()
    m = moneda_de(ticker)
    estado = horario.estado_mercado(ticker)
    delta = f"{num(q['variacion'], 3)} ({pct(q['variacion_pct'], 2)})" if q.get("variacion") is not None else None
    c = st.columns([2, 3]) if not pf.movil else [st.container(), st.container()]
    c[0].metric(f"{nombre_de(ticker).split(' (')[0]} · último", eur(q["precio"], m), delta)
    c[1].markdown(f"{'🟢' if estado['abierto'] else '🔴'} {estado['texto']}  \n"
                  f"<small>Precio de las {pd.Timestamp(q['hora']):%H:%M} del {pd.Timestamp(q['hora']):%d/%m} "
                  f"(≈15 min de retraso; en Bankinter lo verás en tiempo real) · {sector_de(ticker)}</small>",
                  unsafe_allow_html=True)
    k = st.columns(3 if pf.movil else 6)
    k[0].metric("Apertura", num(q["apertura"], 3))
    k[1].metric("Máximo", num(q["maximo"], 3))
    k[2].metric("Mínimo", num(q["minimo"], 3))
    k[3 % len(k)].metric("Cierre anterior", num(q["anterior"], 3) if q.get("anterior") else "—")
    k[4 % len(k)].metric("Volumen", num(q["volumen"], 0))
    k[5 % len(k)].metric("Rango 1 año", f"{num(q['min_52s'], 2)} – {num(q['max_52s'], 2)}" if q.get("min_52s") else "—")

    rango = st.segmented_control("Gráfico", ["Hoy", "1 mes", "1 año"], default="Hoy", key=f"v_rango_{ticker}",
                                 label_visibility="collapsed") or "Hoy"
    if rango == "Hoy" and q.get("sesion") is not None and len(q["sesion"]) > 1:
        serie = q["sesion"]["Close"]
    else:
        dias = 23 if rango == "1 mes" else 260
        serie = diario["Close"].iloc[-dias:] if not diario.empty else pd.Series(dtype=float)
    if len(serie) > 1:
        sube = serie.iloc[-1] >= (q.get("anterior") if rango == "Hoy" and q.get("anterior") else serie.iloc[0])
        fig = go.Figure(go.Scatter(x=serie.index, y=serie.values, line=dict(color="#2ca02c" if sube else "#d62728")))
        if rango == "Hoy" and q.get("anterior"):
            fig.add_hline(y=q["anterior"], line_dash="dot", annotation_text="cierre anterior")
        fig.update_layout(height=220, margin=dict(l=0, r=0, t=10, b=0), showlegend=False)
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    fila = next((r for r in (cargar_informe() or {}).get("ranking", []) if r["ticker"] == ticker), None)
    if fila:
        etiqueta, _, explicacion = asesor.veredicto(fila)
        nota = f" · nota {fila['nota']}/100" if fila.get("nota") is not None else ""
        riesgo = f" · riesgo de caída {fila['riesgo_nivel']}" if fila.get("riesgo_nivel") else ""
        st.caption(f"📋 Veredicto de la app: **{etiqueta}**{nota}{riesgo}. {explicacion}")


def bloque_operar_virtual(cv: dict, libre: float, patrimonio: float):
    pf = perfil()
    st.subheader("🛒 Operar")
    c = st.columns(2)
    con_posicion = list(cv["posiciones"])
    sentido_txt = c[0].segmented_control("Operación", ["Comprar", "Vender"], default="Comprar", key="v_sentido") \
        or "Comprar"
    sentido = "compra" if sentido_txt == "Comprar" else "venta"
    if sentido == "venta" and not con_posicion:
        st.info("Aún no tienes acciones que vender. Compra alguna primero.")
        return
    opciones = con_posicion if sentido == "venta" else list(TODAS_LAS_ACCIONES)
    ticker = c[1].selectbox("Valor", opciones, format_func=nombre_de, key=f"v_ticker_{sentido}")
    diario, intra, q = _datos_valor(ticker)
    f_eur = fx(ticker)
    if not q or f_eur is None:
        st.error("No hay cotización o tipo de cambio disponible para este valor ahora mismo.")
        return
    ficha_cotizacion(ticker, diario, q)
    m = moneda_de(ticker)
    precio = q["precio"]

    # Propuesta de la app (stop-loss, objetivo y tamaño) para rellenar la orden.
    plan = None
    if sentido == "compra":
        hist = cargar_historico(ticker, "2y")
        if not hist.empty:
            p = estrategia_actual()
            plan = senales.evaluar(ticker, hist, mercado_alcista=mercado_alcista_para(ticker),
                                   stop_atr=p.stop_atr, ratio_objetivo=p.ratio_objetivo).plan

    tipos = ["Limitada", "A mercado"] + (["Stop (con límite)"] if sentido == "venta" else [])
    tipo_txt = st.radio("Tipo de orden", tipos, horizontal=True, key=f"v_tipo_{sentido}")
    tipo = TIPOS[tipo_txt]
    st.caption(EXPLICA_TIPO[tipo])

    k = st.columns(2 if pf.movil else 4)
    limite = activacion = stop = objetivo = None
    if sentido == "compra":
        ref = precio * f_eur
        sugeridas = 0
        if plan and plan.stop < precio:
            sugeridas = min(costes.tamano_por_riesgo(patrimonio, pf.riesgo, ref, plan.stop * f_eur),
                            costes.acciones_asequibles(min(libre, patrimonio * 0.20), ref, ticker, pf.tarifa))
        maximo = max(costes.acciones_asequibles(libre, ref, ticker, pf.tarifa), 1)
        n = k[0].number_input("Títulos", 1, 10_000_000, max(min(sugeridas, maximo), 1), key=f"v_n_{ticker}_c",
                              help=f"La app propone {sugeridas} para que, si salta el stop, pierdas como mucho el "
                                   f"{num(pf.riesgo, 1)} % de tu cartera y ninguna empresa pase del 20 %.")
    else:
        libres = cartera.acciones_libres(cv, ticker)
        if libres == 0:
            st.info("Todas tus acciones de este valor ya están en otras órdenes de venta.")
            return
        n = k[0].number_input("Títulos", 1, libres, libres, key=f"v_n_{ticker}_v")
    if tipo == "limitada":
        limite = k[1].number_input(f"Precio límite ({m})", 0.001, value=round(precio, 3), format="%.3f",
                                   key=f"v_lim_{ticker}_{sentido}")
    elif tipo == "stop":
        pos = cv["posiciones"][ticker]
        defecto = pos.get("stop") or round(precio * 0.93, 3)
        activacion = k[1].number_input(f"Activación ({m})", 0.001, value=float(min(defecto, precio * 0.999)),
                                       format="%.3f", key=f"v_act_{ticker}")
        limite = k[2 % len(k)].number_input(f"Límite ({m})", 0.001, value=round(activacion * 0.98, 3), format="%.3f",
                                            key=f"v_limst_{ticker}", help="Bankinter lo exige. Un 2 % por debajo de la "
                                                                        "activación para que se ejecute aunque caiga deprisa.")
    validez = k[-1].date_input("Válida hasta", date.today() + timedelta(days=0 if tipo == "mercado" else 7),
                               min_value=date.today(), max_value=date.today() + timedelta(days=90),
                               key=f"v_val_{ticker}_{sentido}", format="DD/MM/YYYY")
    if sentido == "compra":
        j = st.columns(2)
        stop = j[0].number_input(f"Stop-loss tras la compra ({m}, 0 = sin stop)", 0.0,
                                 value=round(plan.stop, 3) if plan else 0.0, format="%.3f", key=f"v_slc_{ticker}")
        objetivo = j[1].number_input(f"Objetivo ({m}, 0 = sin objetivo)", 0.0,
                                     value=round(plan.objetivo, 3) if plan else 0.0, format="%.3f", key=f"v_objc_{ticker}")
        stop, objetivo = stop or None, objetivo or None
        compra_a = limite if tipo == "limitada" else precio
        if stop and stop >= compra_a:
            st.warning(f"El stop-loss ({num(stop, 3)}) tiene que quedar por debajo del precio de compra "
                       f"({num(compra_a, 3)}). Bájalo o pon 0 si no quieres stop.")

    # Estimación de costes, como la pantalla de confirmación del bróker.
    precio_estimado = limite if tipo == "limitada" else (activacion if tipo == "stop" else precio)
    importe = n * precio_estimado * f_eur
    if sentido == "compra":
        cc = costes.coste_compra(importe, ticker, pf.tarifa)
        partes = [f"comisión {eur(cc['comision'])}"] + ([f"cambio de divisa {eur(cc['cambio'])}"] if cc["cambio"] else []) \
            + ([f"tasa Tobin {eur(cc['itf'])}"] if cc["itf"] else [])
        texto = (f"**Importe estimado: {eur(importe)}** + gastos {eur(cc['total'])} ({', '.join(partes)}) = "
                 f"**{eur(importe + cc['total'])}**")
    else:
        gastos = pf.tarifa.coste(importe, ticker)
        pos = cv["posiciones"][ticker]
        resultado = importe - gastos - n * pos["precio_medio"] * pos.get("fx_medio", 1.0) \
            - pos.get("gastos", 0.0) * n / pos["acciones"]
        texto = (f"**Recibirías unos {eur(importe - gastos)}** (importe {eur(importe)} − comisión {eur(gastos)}). "
                 f"Resultado estimado de la operación: **{eur(resultado)}**"
                 + (f", unos {eur(costes.impuesto_ganancia(resultado))} de IRPF." if resultado > 0 else "."))
    st.markdown("🧮 " + texto)
    if tipo == "limitada" and sentido == "compra" and limite > precio * 1.02:
        st.warning("Tu límite está muy por encima del precio actual: se ejecutará enseguida al precio de mercado.")

    if st.button("📨 Enviar orden", type="primary", width="stretch", key=f"v_enviar_{sentido}"):
        ahora_iso = f"{horario.ahora_madrid():%Y-%m-%dT%H:%M}"
        err = cartera.nueva_orden(cv, ticker, sentido, tipo, int(n), pf.tarifa, precio_ref=precio, ahora=ahora_iso,
                                  validez=validez.isoformat(), limite=limite, activacion=activacion, fx=f_eur,
                                  stop=stop, objetivo=objetivo)
        if err:
            st.error(err)
            return
        abierto = horario.estado_mercado(ticker)["abierto"]
        eventos = cartera.ejecutar_ordenes(cv, {}, pf.tarifa, ahora_iso, {ticker: (precio, abierto)})
        guardar_datos()
        if not eventos:
            eventos = ["📨 Orden enviada. Queda pendiente: "
                       + ("se ejecutará en la apertura." if tipo == "mercado" else
                          "se ejecutará si el precio llega a tu límite." if tipo == "limitada" else
                          "se activará si el precio baja a la activación.")]
        st.session_state["_avisos_virtual"] = eventos
        st.rerun()


# --------------------------------------------------------------------------- ejercicios
def bloque_ejercicios(cv: dict):
    progreso = ejercicios.progreso(cv)
    hechos = sum(h for _, h in progreso)
    with st.expander(f"🏋️ Ejercicios para practicar ({hechos}/{len(progreso)} hechos)"):
        st.progress(hechos / len(progreso))
        for e, hecho in progreso:
            st.markdown(f"{'✅' if hecho else '⬜'} **{e.titulo}**  \n{e.como}  \n<small>Aprendes: {e.aprendes}</small>",
                        unsafe_allow_html=True)
