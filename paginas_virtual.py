"""🎮 Cartera virtual que funciona como el bróker: cotización en directo (con el retraso habitual), órdenes
limitadas, a mercado y stop que se ejecutan cuando el precio llega, órdenes pendientes y comisiones reales."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from bolsa import asesor, bankinter, cartera, costes, datos, ejercicios, horario, senales
from bolsa.activos import clase_de
from bolsa.tickers import nombre_de, sector_de
from paginas_extra import (ICONO_NIVEL, ficha_activo, pintar_tabla_posiciones, revisar_cartera_real, selector_activo,
                           tabla_posiciones)
from ui_comun import (cargar_diario_real, cargar_fundamentales, cargar_historico, cargar_informe, cargar_intradia,
                      cotizacion_al_instante, cotizaciones_ahora, datos_usuario, estrategia_actual, eur, fecha, fx,
                      guardar_datos, mercado_alcista_para, moneda_de, mostrar_plotly, num, palabras_de_la_pagina, pct,
                      perfil, selector_valor)
from ui_comun import precio as txt_precio

TIPOS = {"Limitada": "limitada", "A mercado": "mercado", "Stop (con límite)": "stop"}
EXPLICA_TIPO = {
    "limitada": "Solo se ejecuta a tu precio o mejor. Si el precio no llega, la orden espera hasta su validez.",
    "mercado": "Se ejecuta ya al precio que haya (o en la apertura si el mercado está cerrado). Rápida, pero no "
               "controlas el precio.",
    "stop": "Se queda dormida hasta que el precio baja a la activación; entonces lanza una venta limitada. Es la "
            "forma de poner un stop-loss en el bróker.",
}


def _cuando(iso: str) -> str:
    ts = pd.Timestamp(iso)
    return fecha(iso) if (ts.hour, ts.minute) == (0, 0) else f"{ts:%d/%m/%Y %H:%M}"


_SUFIJOS_EURO = (".MC", ".PA", ".DE", ".AS", ".MI", ".BR", ".LS", ".HE", ".F")


def _cotizacion_de_respaldo(ticker: str):
    """Si la cotización intradía no llega (Yahoo limita a veces), el último cierre del histórico y, si lo hay, el
    precio de ahora de la consulta en bloque. Así se puede operar igual."""
    try:
        diario = cargar_historico(ticker, "1y")
        q = datos.cotizacion(diario, None) if not diario.empty else None
        ahora = cotizaciones_ahora([ticker]).get(ticker)
    except Exception:  # noqa: BLE001
        return pd.DataFrame(), None
    if q and ahora:
        q.update(precio=ahora["precio"], variacion_pct=ahora.get("variacion_pct"), hora=pd.Timestamp(ahora["fecha"]),
                 anterior=ahora.get("anterior") or q.get("anterior"))
        q["variacion"] = q["precio"] - q["anterior"] if q.get("anterior") else None
    return diario, q


def _datos_valor(ticker: str):
    diario = cargar_diario_real(ticker)
    intra = cargar_intradia(ticker)
    q = datos.cotizacion(diario, intra)
    al_instante = cotizacion_al_instante(ticker)
    if q and al_instante:
        q.update({k: v for k, v in al_instante.items() if v is not None})
    return diario, intra, q


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
                # Sin tipo de cambio fiable se usa el de la compra (nunca 1: un valor en peniques saldría 100 veces).
                info[t] = {"barras": datos.barras_ejecucion(diario, intra), "q": q,
                           "abierto": horario.estado_mercado(t)["abierto"],
                           "fx": fx(t) or (cv["posiciones"].get(t) or {}).get("fx_medio")}
    barras = {t: v["barras"] for t, v in info.items()}
    eventos = cartera.revisar_ordenes(cv, barras, pf.tarifa, {t: v["fx"] for t, v in info.items() if v["fx"]})
    eventos += cartera.ejecutar_ordenes(cv, barras, pf.tarifa, ahora_iso,
                                        {t: (v["q"]["precio"], v["abierto"]) for t, v in info.items() if v["q"]})
    for e in st.session_state.pop("_avisos_virtual", []) + eventos:
        st.info(e)
    if eventos:
        guardar_datos()

    precios = {t: v["q"]["precio"] for t, v in info.items() if v["q"]}
    for t in cv["posiciones"]:       # sin cotización ahora: el último cierre (no vale 0)
        if t not in precios:
            hist = cargar_historico(t, "1y")
            if not hist.empty:
                precios[t] = float(hist["Close"].iloc[-1])
    fx_pos = {t: v["fx"] for t, v in info.items() if v["fx"]}
    _, res = cartera.valorar(cv, precios, fx_pos)
    libre = cartera.disponible(cv, pf.tarifa)
    c = st.columns(2 if pf.movil else 4)
    c[0].metric("Valor total", eur(res["total"]), pct(res["ganancia_pct"], 1))
    c[1].metric("Ganancia / pérdida", eur(res["ganancia"]))
    c[2 % len(c)].metric("Disponible para comprar", eur(libre),
                         help="Efectivo menos lo reservado por tus órdenes de compra pendientes (el «saldo "
                              "comprometido» del bróker).")
    c[3 % len(c)].metric("Operaciones cerradas", f"{res['ganadoras']}/{res['operaciones_cerradas']} ganadoras")
    st.caption(f"Empezaste con {eur(cv['capital_inicial'])} el {fecha(cv['creada'])}. Precios reales con unos 15 "
               "minutos de retraso, comisiones de tu bróker (barra lateral) y las mismas reglas de "
               "ejecución que el bróker.")

    bloque_evolucion(cv)
    if cv["posiciones"]:
        bloque_posiciones(cv, info)
    bloque_ordenes_pendientes(cv)
    bloque_operar_virtual(cv, libre, res["total"])
    bloque_ejercicios(cv)
    palabras_de_la_pagina(["Orden limitada", "Orden a mercado", "Orden stop", "Stop limitada", "Validez de la orden",
                           "Stop-loss", "Objetivo de precio", "Comisión", "Tasa Tobin", "Cambio de divisa", "Horquilla",
                           "Riesgo por operación"])

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
        mostrar_plotly(fig)


# --------------------------------------------------------------------------- posiciones
def bloque_posiciones(cv: dict, info: dict):
    pf = perfil()
    st.subheader("💼 Tu posición")
    # La misma tabla y el mismo consejo que en 🏦 Mi cartera, para seguirla igual que la real.
    filas = revisar_cartera_real(cv)
    vista, total, ganancia, cambio_hoy = tabla_posiciones(filas)
    f_activo = selector_activo(filas, "cv_activo")
    if f_activo:
        ficha_activo(f_activo, filas)
        _editar_stop_virtual(cv, info)
        return
    c = st.columns(3 if not pf.movil else 2)
    c[0].metric("Valor de tus posiciones", eur(total))
    c[1].metric("Ganancia o pérdida (sin vender)", eur(ganancia),
                pct(ganancia / (total - ganancia) * 100, 1) if total - ganancia else None)
    c[2 % len(c)].metric("Hoy", eur(cambio_hoy),
                         pct(cambio_hoy / (total - cambio_hoy) * 100, 2) if total - cambio_hoy else None)
    pintar_tabla_posiciones(vista, "Parte de lo que tienes en acciones y fondos (sin contar el efectivo).")
    if vista["Precio actual"].isna().any():
        st.warning("No hay cotización ahora mismo para algún valor: su valoración no se puede calcular.")
    atencion = [f for f in filas if f["nivel"] != "mantener"]
    with st.expander(f"📌 Qué haría el asesor con cada una ({len(atencion)} necesitan atención)" if atencion
                     else "📌 Qué haría el asesor con cada una"):
        for f in filas:
            st.markdown(f"{ICONO_NIVEL[f['nivel']]} **{f['nombre']}**: {f['consejo']}")
        st.caption("Igual que con tu cartera real: con el precio de ahora, tu stop-loss y la tendencia de cada valor.")

    _editar_stop_virtual(cv, info)


def _editar_stop_virtual(cv: dict, info: dict):
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
            st.success("Hecho." + (" En Bankinter tendrías que anular la orden stop y crear otra: allí no se modifican."
                                    if bankinter.es_bankinter() else ""))


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
            precio_o = f"activación {txt_precio(o['activacion'], m)} · límite {txt_precio(o['limite'], m)}"
        elif o["tipo"] == "limitada":
            precio_o = f"límite {txt_precio(o['limite'], m)}"
        else:
            precio_o = "a mercado"
        c1, c2 = st.columns([4, 1])
        c1.markdown(f"**{o['sentido'].capitalize()} {o['tipo']}** · {o['acciones']} {nombre_de(o['ticker'])} · "
                    f"{precio_o}  \n<small>Nº {o['id']} · enviada {_cuando(o['creada'])} · válida hasta "
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
    c[0].metric(f"{nombre_de(ticker).split(' (')[0]} · último", txt_precio(q["precio"], m), delta)
    c[1].markdown(f"{'🟢' if estado['abierto'] else '🔴'} {estado['texto']}  \n"
                  f"<small>Precio de las {pd.Timestamp(q['hora']):%H:%M} del {pd.Timestamp(q['hora']):%d/%m} "
                  + ("(⚡ tiempo real, Finnhub)" if q.get("tiempo_real") else
                     "(≈15 min de retraso; en tu bróker lo verás en tiempo real)") + f" · {sector_de(ticker)}</small>",
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
        mostrar_plotly(fig)

    fila = next((r for r in (cargar_informe() or {}).get("ranking", []) if r["ticker"] == ticker), None)
    if fila:
        etiqueta, _, explicacion = asesor.veredicto(fila)
        nota = f" · nota {fila['nota']}/100" if fila.get("nota") is not None else ""
        riesgo = f" · riesgo de caída {fila['riesgo_nivel']}" if fila.get("riesgo_nivel") else ""
        st.caption(f"📋 Veredicto de la app: **{etiqueta}**{nota}{riesgo}. {explicacion}")


VALIDEZ = ["Hasta fin de día", "Hasta fin de semana", "Hasta fin de mes", "Fecha concreta"]


def _hoy() -> date:
    """Hoy en España (el servidor puede ir con otra hora)."""
    return horario.ahora_madrid().date()


def _fecha_validez(opcion: str, concreta: date | None) -> date:
    hoy = _hoy()
    if opcion == "Hasta fin de día":
        return hoy
    if opcion == "Hasta fin de semana":         # el viernes (si hoy es sábado o domingo, el de la semana que viene)
        return hoy + timedelta(days=(4 - hoy.weekday()) % 7)
    if opcion == "Hasta fin de mes":
        siguiente = (hoy.replace(day=28) + timedelta(days=4)).replace(day=1)
        return siguiente - timedelta(days=1)
    return concreta or hoy


def _cabecera_orden(ticker: str, q: dict, sentido: str) -> None:
    """Cabecera como la de la orden de Bankinter: valor, precio, variación, hora y mercado, y la sesión."""
    m = moneda_de(ticker)
    corto = ticker.split(".")[0].replace("^", "")
    nombre = nombre_de(ticker).split(" (")[0].upper()
    var = q.get("variacion_pct")
    flecha = "↗" if (var or 0) >= 0 else "↘"
    color = "#16a34a" if (var or 0) >= 0 else "#ef4444"          # se leen en tema claro y oscuro
    hora = pd.Timestamp(q["hora"])
    st.markdown(f"<div class='orden-titulo'>ORDEN DE {'COMPRA' if sentido == 'compra' else 'VENTA'}</div>",
                unsafe_allow_html=True)
    c = st.columns([3, 2])
    c[0].markdown(
        f"<div class='orden-valor'>{corto} · {nombre}</div>"
        f"<div class='orden-precio'>{txt_precio(q['precio'], m)} <span style='color:{color}'>{flecha} "
        + (f"{pct(var, 2)}" if var is not None else "") + "</span></div>"
        f"<div class='orden-hora'>{hora:%H:%M} · {bankinter.mercado_de(ticker).upper()}</div>",
        unsafe_allow_html=True)
    c[1].markdown(
        "<div class='orden-caja'><div class='orden-caja-cab'><span>MÁXIMO</span><span>MÍNIMO</span></div>"
        f"<div class='orden-caja-val'><span>{num(q['maximo'], 3)}</span><span>{num(q['minimo'], 3)}</span></div>"
        f"<div class='orden-caja-pie'>Cierre anterior {num(q['anterior'], 3) if q.get('anterior') else '—'}</div>"
        "</div>", unsafe_allow_html=True)


def _cancelar_orden(ticker: str) -> None:
    """«Cancelar»: deja la orden como al principio (los valores propuestos por la app)."""
    for x in [x for x in st.session_state if isinstance(x, str) and x.startswith("v_") and ticker in x]:
        del st.session_state[x]
    st.session_state.pop("v_confirmar", None)


@st.fragment
def bloque_operar_virtual(cv: dict, libre: float, patrimonio: float):
    """Orden de compra o venta con el mismo formulario que el bróker (Bankinter): cuenta, tipo de orden, precio,
    títulos, importe y validez; «Continuar» enseña el resumen con los costes y «Confirmar» la envía."""
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
    if sentido == "venta":
        defecto = st.session_state.pop("v_defecto", None)
        if defecto in con_posicion:
            st.session_state["v_ticker_venta"] = defecto
        ticker = c[1].selectbox("Valor", con_posicion, format_func=nombre_de, key="v_ticker_venta")
    else:
        ticker = selector_valor("v_compra", solo_invertibles=True, defecto=st.session_state.pop("v_defecto", None))
    try:
        diario, _, q = _datos_valor(ticker)
    except Exception:  # noqa: BLE001 - Yahoo falla: se intenta con el histórico
        diario, q = pd.DataFrame(), None
    if not q:
        diario, q = _cotizacion_de_respaldo(ticker)
    f_eur = fx(ticker)
    if f_eur is None and ticker.endswith(_SUFIJOS_EURO):
        f_eur = 1.0
    if not q or f_eur is None:
        st.error("Yahoo no da ahora mismo la cotización de este valor (a veces limita las consultas). Prueba de nuevo "
                 "en un minuto con «🔄 Actualizar todo ahora» en el menú lateral.")
        return
    with st.expander(f"📈 Gráfico y datos de {nombre_de(ticker).split(' (')[0]}"):
        ficha_cotizacion(ticker, diario, q)
    m = moneda_de(ticker)
    precio = q["precio"]
    clave = f"{ticker}_{sentido}"
    confirmar = st.session_state.get("v_confirmar")
    if confirmar and confirmar.get("clave") != clave:
        st.session_state.pop("v_confirmar", None)
        confirmar = None

    # Propuesta de la app (stop-loss, objetivo y tamaño) para rellenar la orden.
    plan = None
    if sentido == "compra" and clase_de(ticker) not in ("Fondos y ETF", "Renta fija", "Monetario y liquidez"):
        hist = cargar_historico(ticker, "2y")
        if not hist.empty:
            p = estrategia_actual()
            plan = senales.evaluar(ticker, hist, mercado_alcista=mercado_alcista_para(ticker),
                                   stop_atr=p.stop_atr, ratio_objetivo=p.ratio_objetivo).plan

    try:     # la tasa Tobin solo la pagan las empresas grandes: hace falta su capitalización
        cap = cargar_fundamentales(ticker).get("marketCap")
    except Exception:  # noqa: BLE001
        cap = None
    tobin = costes.tasa_tobin_pct(ticker, cap)

    with st.container(border=True, key="orden_ticket"):
        _cabecera_orden(ticker, q, sentido)
        k = st.columns(2)
        k[0].selectbox("CUENTA VALORES", ["🎮 Cartera virtual"], key=f"v_cuenta_{clave}", disabled=True)
        k[1].selectbox("LIQUIDACIÓN", ["Efectivo virtual"], key=f"v_liq_{clave}", disabled=True)
        k[1].caption(f"Saldo disponible: {eur(libre)}")

        k = st.columns(2)
        tipos = ["Estándar"] + (["Stop (stop-loss)"] if sentido == "venta" else [])
        tipo_orden = k[0].selectbox("TIPO DE ORDEN", tipos, key=f"v_tipo_{clave}",
                                    help="Estándar: compra o venta normal. Stop: se queda dormida y vende si el "
                                         "precio baja a la activación (para limitar pérdidas).")
        limite = activacion = None
        if tipo_orden == "Estándar":
            precio_txt = k[0].selectbox("PRECIO", ["A mercado", "Limitado"], index=1, key=f"v_precio_{clave}",
                                        help="Limitado: solo se ejecuta a tu precio o mejor (lo recomendable). A "
                                             "mercado: al precio que haya, sin control del precio.")
            tipo = "mercado" if precio_txt == "A mercado" else "limitada"
            if tipo == "limitada":
                limite = k[1].number_input(f"PRECIO LÍMITE ({m})", 0.001, value=round(precio, 3), format="%.3f",
                                           key=f"v_lim_{ticker}_{sentido}")
        else:
            tipo = "stop"
            pos = cv["posiciones"][ticker]
            defecto = pos.get("stop") or round(precio * 0.93, 3)
            activacion = k[1].number_input(f"PRECIO DE ACTIVACIÓN ({m})", 0.001,
                                           value=float(min(defecto, precio * 0.999)), format="%.3f",
                                           key=f"v_act_{ticker}")
            limite = k[1].number_input(f"PRECIO LÍMITE ({m})", 0.001, value=round(activacion * 0.98, 3),
                                       format="%.3f", key=f"v_limst_{ticker}_{activacion}",
                                       help="Un 2 % por debajo de la activación, para que se ejecute aunque caiga "
                                            "deprisa (Bankinter lo exige en los stop).")
        st.caption(EXPLICA_TIPO[tipo])

        k = st.columns(2)
        if sentido == "compra":
            ref = precio * f_eur
            sugeridas = 0
            if plan and plan.stop < precio:
                sugeridas = min(costes.tamano_por_riesgo(patrimonio, pf.riesgo, ref, plan.stop * f_eur),
                                costes.acciones_asequibles(min(libre, patrimonio * 0.20), ref, ticker, pf.tarifa,
                                                           tobin))
            maximo = max(costes.acciones_asequibles(libre, ref, ticker, pf.tarifa, tobin), 1)
            n = k[0].number_input("TÍTULOS", 1, 10_000_000, max(min(sugeridas, maximo), 1), key=f"v_n_{ticker}_c",
                                  help=f"La app propone {sugeridas} para que, si salta el stop, pierdas como mucho el "
                                       f"{num(pf.riesgo, 1)} % de tu cartera y ninguna empresa pase del 20 %. Con tu "
                                       f"saldo puedes comprar hasta {maximo}.")
        else:
            libres = cartera.acciones_libres(cv, ticker)
            n = k[0].number_input("TÍTULOS EN VENTA", 0, max(libres, 0), libres, key=f"v_n_{ticker}_v")
            k[0].caption(f"Disponibles {libres}")
            if libres == 0:
                k[0].markdown("<span style='color:#dc2626'>No tienes títulos disponibles (están en otras órdenes "
                              "de venta).</span>", unsafe_allow_html=True)
        precio_estimado = limite if tipo == "limitada" else (activacion if tipo == "stop" else precio)
        importe = n * precio_estimado * f_eur
        k[1].text_input("IMPORTE APROXIMADO SIN COMISIONES", eur(importe), disabled=True,
                        key=f"v_importe_{clave}_{round(importe, 2)}")

        k = st.columns(2)
        opcion = k[0].selectbox("VALIDEZ", VALIDEZ, index=0 if tipo == "mercado" else 2, key=f"v_validez_{clave}")
        concreta = None
        if opcion == "Fecha concreta":
            concreta = k[1].date_input("Fecha", _hoy() + timedelta(days=7), min_value=_hoy(),
                                       max_value=_hoy() + timedelta(days=90), key=f"v_val_{clave}",
                                       format="DD/MM/YYYY")
        validez = _fecha_validez(opcion, concreta)
        estado = horario.estado_mercado(ticker)
        if validez == _hoy() and not estado["abierto"] and estado["apertura"].date() > _hoy():
            st.warning("El mercado ya ha cerrado por hoy: una orden «hasta fin de día» caducará sin ejecutarse. "
                       "Elige «Hasta fin de semana» o «Hasta fin de mes».")

        stop = objetivo = None
        if sentido == "compra":
            with st.expander("🛡️ Protección tras la compra (stop-loss y objetivo)", expanded=False):
                j = st.columns(2)
                stop = j[0].number_input(f"Stop-loss ({m}, 0 = sin stop)", 0.0,
                                         value=round(plan.stop, 3) if plan else 0.0, format="%.3f",
                                         key=f"v_slc_{ticker}")
                objetivo = j[1].number_input(f"Objetivo ({m}, 0 = sin objetivo)", 0.0,
                                             value=round(plan.objetivo, 3) if plan else 0.0, format="%.3f",
                                             key=f"v_objc_{ticker}")
                st.caption("Propuestos por la app según la volatilidad del valor. En Bankinter serían órdenes "
                           "«stop relacionadas», que se crean después de la compra.")
            stop, objetivo = stop or None, objetivo or None
            compra_a = limite if tipo == "limitada" else precio
            if stop and stop >= compra_a:
                # Pasa al poner un límite por debajo del stop propuesto: se recoloca a la misma distancia (en %)
                # bajo tu precio, en vez de no dejarte enviar la orden.
                distancia = (precio - plan.stop) / precio if plan and plan.stop < precio else 0.07
                stop = round(compra_a * (1 - distancia), 3)
                st.info(f"🛡️ Has puesto la compra por debajo del stop-loss propuesto: lo bajo a "
                        f"**{num(stop, 3)}** ({pct(-distancia * 100, 1)} bajo tu precio).")
            if tipo == "limitada" and limite > precio * 1.02:
                st.warning("Tu límite está muy por encima del precio actual: se ejecutará enseguida al precio de "
                           "mercado.")

        orden = dict(clave=clave, ticker=ticker, sentido=sentido, tipo=tipo, n=int(n), limite=limite,
                     activacion=activacion, validez=validez.isoformat(), stop=stop, objetivo=objetivo,
                     precio=precio, f_eur=f_eur, importe=importe, cap=cap)
        # Si cambias algo de la orden con el resumen abierto, el resumen ya no vale: se vuelve al formulario.
        if confirmar and any(confirmar.get(x) != orden[x] for x in ("ticker", "sentido", "tipo", "n", "limite",
                                                                     "activacion", "validez", "stop", "objetivo")):
            st.session_state.pop("v_confirmar", None)
            confirmar = None
        if not confirmar:
            b = st.columns(2)
            b[0].button("✕ CANCELAR", key=f"v_cancelar_{clave}", width="stretch", type="tertiary",
                        on_click=_cancelar_orden, args=(ticker,))
            # Sin callback: así el resumen se hace con lo que hay escrito AHORA (en el móvil se suele pulsar
            # «Continuar» sin salir antes del campo de títulos o de precio).
            if b[1].button("CONTINUAR", key=f"v_continuar_{sentido}", type="primary", width="stretch",
                           disabled=n <= 0):
                st.session_state["v_confirmar"] = orden
                st.rerun()
            return

    # Paso 2: resumen con los costes, como la pantalla de confirmación del bróker.
    o = confirmar
    with st.container(border=True, key="orden_confirmar"):
        que = "COMPRA" if o["sentido"] == "compra" else "VENTA"
        st.markdown(f"<div class='orden-titulo'>CONFIRMA TU ORDEN DE {que}</div>", unsafe_allow_html=True)
        como = {"mercado": "a mercado", "limitada": f"limitada a {num(o['limite'], 3)} {m}",
                "stop": f"stop: activación {num(o['activacion'], 3)} · límite {num(o['limite'], 3)} {m}"}[o["tipo"]]
        st.markdown(f"**{o['n']} títulos de {nombre_de(o['ticker'])}** · orden {como} · válida hasta "
                    f"**{fecha(o['validez'])}**")
        if o["sentido"] == "compra":
            o["importe"] = o["n"] * (o["limite"] if o["tipo"] == "limitada" else precio) * o["f_eur"]
            cc = costes.coste_compra(o["importe"], o["ticker"], pf.tarifa, o.get("cap"))
            filas = [("Importe aproximado", eur(o["importe"])), ("Comisión", eur(cc["comision"]))]
            if cc["cambio"]:
                filas.append(("Cambio de divisa", eur(cc["cambio"])))
            if cc["itf"]:
                filas.append((costes.nombre_tasa_tobin(o["ticker"]), eur(cc["itf"])))
            filas.append(("**Total aproximado**", f"**{eur(o['importe'] + cc['total'])}**"))
            if o.get("stop"):
                filas.append(("Stop-loss tras la compra", f"{num(o['stop'], 3)} {m}"))
        else:
            gastos = pf.tarifa.coste(o["importe"], o["ticker"])
            pos = cv["posiciones"][o["ticker"]]
            resultado = o["importe"] - gastos - o["n"] * pos["precio_medio"] * pos.get("fx_medio", 1.0) \
                - pos.get("gastos", 0.0) * o["n"] / pos["acciones"]
            filas = [("Importe aproximado", eur(o["importe"])), ("Comisión", eur(gastos)),
                     ("**Recibirías unos**", f"**{eur(o['importe'] - gastos)}**"),
                     ("Resultado de la operación", eur(resultado))]
            if resultado > 0:
                filas.append(("IRPF aproximado", eur(costes.impuesto_ganancia(resultado))))
        for etiqueta, valor in filas:
            c = st.columns([3, 2])
            c[0].markdown(etiqueta)
            c[1].markdown(valor)
        b = st.columns(2)
        b[0].button("← MODIFICAR", key="v_modificar", width="stretch", type="tertiary",
                    on_click=lambda: st.session_state.pop("v_confirmar", None))
        if b[1].button("CONFIRMAR ORDEN", key=f"v_enviar_{o['sentido']}", type="primary", width="stretch"):
            ahora_iso = f"{horario.ahora_madrid():%Y-%m-%dT%H:%M}"
            # Con el precio de AHORA (no el de cuando pulsaste «Continuar»).
            err = cartera.nueva_orden(cv, o["ticker"], o["sentido"], o["tipo"], o["n"], pf.tarifa,
                                      precio_ref=precio, ahora=ahora_iso, validez=o["validez"],
                                      limite=o["limite"], activacion=o["activacion"], fx=f_eur, stop=o["stop"],
                                      objetivo=o["objetivo"], capitalizacion=o.get("cap"))
            if err:
                st.error(err)
                return
            abierto = horario.estado_mercado(o["ticker"])["abierto"]
            eventos = cartera.ejecutar_ordenes(cv, {}, pf.tarifa, ahora_iso, {o["ticker"]: (precio, abierto)})
            guardar_datos()
            if not eventos:
                eventos = ["📨 Orden enviada. Queda pendiente: "
                           + ("se ejecutará en la apertura." if o["tipo"] == "mercado" else
                              "se ejecutará si el precio llega a tu límite." if o["tipo"] == "limitada" else
                              "se activará si el precio baja a la activación.")]
            st.session_state["_avisos_virtual"] = eventos
            st.session_state.pop("v_confirmar", None)
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
