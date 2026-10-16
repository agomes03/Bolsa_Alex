"""Página Seguimiento: tus avisos de precio, tu aportación mensual, tu diario de inversiones y la ayuda para la
Renta. Y el bloque «📌 Tus pendientes» que se ve arriba en 🧭 Hoy."""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from bolsa import agenda, alertas, aportaciones, asesor, diario, renta
from bolsa.costes import simular_aportaciones
from bolsa.tickers import nombre_de
from paginas_extra import _perfil_guardado, nombre_posicion, revisar_cartera_real
from ui_comun import (cargar_dividendos_varios, cargar_varios, cuenta_activa, datos_usuario, enlace, eur, fx, guardar_datos,
                      palabras_de_la_pagina, perfil, selector_valor)

DESTINO_CORTO = {
    "Fondo indexado mundial": "Fondo indexado mundial (MSCI World o FTSE All-World, comisión < 0,3 %)",
    "Monetario / Letras del Tesoro": "Fondo monetario, Letras del Tesoro o cuenta remunerada",
    "Renta fija a corto plazo": "Fondo de deuda pública europea a corto plazo (1-3 años)",
    "Acciones individuales": "Acciones sueltas: guárdalo en la cuenta hasta juntar unos 1.000 € (comprar menos "
                             "cuesta mucho en comisiones)",
}


# --------------------------------------------------------------------------- comunes
def _ultimo_precio(ticker: str) -> float | None:
    try:
        df = cargar_varios((ticker,), "1mo").get(ticker)
    except Exception:  # noqa: BLE001
        return None
    return float(df["Close"].dropna().iloc[-1]) if df is not None and not df.empty else None


def _elegir_valor(clave: str) -> tuple[str, str]:
    """De tu cartera (lo más habitual) o cualquier valor del catálogo. Devuelve (ticker, nombre)."""
    cr = datos_usuario().get("cartera_real") or {}
    mias = {t: nombre_posicion(t, p) for t, p in cr.get("posiciones", {}).items()}
    origen = "Cualquier valor"
    if mias:
        origen = st.radio("¿De dónde?", ["De mi cartera", "Cualquier valor"], horizontal=True, key=f"{clave}_origen")
    if origen == "De mi cartera":
        t = st.selectbox("Valor", list(mias), format_func=mias.get, key=f"{clave}_mio")
        return t, mias[t]
    t = selector_valor(clave)
    return t, nombre_de(t)


def actualizar_alertas() -> None:
    """Comprueba los avisos activos con las cotizaciones desde que se crearon y guarda los que han saltado."""
    d = cuenta_activa()
    activas = [a for a in d.get("alertas", []) if not a.get("disparada")]
    if not activas:
        return
    try:
        hist = cargar_varios(tuple(sorted({a["ticker"] for a in activas})), "1y")
    except Exception:  # noqa: BLE001 - sin datos, se comprueban la próxima vez
        return
    if alertas.revisar(d["alertas"], hist):
        guardar_datos()


def bloque_pendientes() -> None:
    """«📌 Tus pendientes» (arriba en Hoy). No muestra nada si no hay pendientes."""
    try:
        actualizar_alertas()
        items = agenda.pendientes(cuenta_activa())
    except Exception:  # noqa: BLE001 - Hoy nunca debe romperse por esto
        return
    if not items:
        return
    with st.container(border=True):
        d = datos_usuario()
        varias = len(d.get("cuentas", {})) > 1
        st.markdown("#### 📌 Tus pendientes" + (f" · 👤 {d['cuenta_activa']}" if varias else ""))
        for x in items:
            st.markdown(f"{x['icono']} **{x['titulo']}** — {x['texto']}")
        enlace("seguimiento", "Ir a Seguimiento", "📒")


# --------------------------------------------------------------------------- página
def pagina_seguimiento():
    st.title("📒 Seguimiento")
    st.caption("Lo que tú te has propuesto: avisos de precio, tu aportación de cada mes, el diario de tus decisiones "
               "y tus datos para la Renta. Lo pendiente aparece también arriba en 🧭 Hoy.")
    actualizar_alertas()
    t1, t2, t3, t4 = st.tabs(["🔔 Avisos de precio", "💶 Aportación mensual", "📓 Diario", "🧾 Renta"])
    with t1:
        tab_alertas()
    with t2:
        tab_aportacion()
    with t3:
        tab_diario()
    with t4:
        tab_renta()
    palabras_de_la_pagina(["Stop-loss", "Fondo indexado", "Rebalanceo", "Ganancia patrimonial", "Base del ahorro",
                           "Compensación de pérdidas", "Regla de los 2 meses", "Retención", "Dividendo"])


def tab_alertas():
    d = cuenta_activa()
    lista = d.setdefault("alertas", [])
    st.markdown("Pon el precio que te interesa y la app te avisa: **aquí y en 🧭 Hoy** cuando lo toque y, si tienes "
                "Telegram activado (🏦 Mi cartera → Avisos al móvil), **al móvil en menos de una hora** en horario "
                "de mercado.")
    t, nombre = _elegir_valor("alerta")
    precio_actual = _ultimo_precio(t)
    if precio_actual:
        st.caption(f"Último precio de {nombre}: **{precio_actual:,.2f}**".replace(",", "X").replace(".", ",")
                   .replace("X", "."))
    with st.form("nueva_alerta", border=True):
        c = st.columns(2)
        tipo = c[0].radio("Avísame si…", list(alertas.TIPOS), format_func=lambda k: alertas.TIPOS[k].capitalize(),
                          horizontal=True)
        precio = c[1].number_input("Precio", min_value=0.0, value=round((precio_actual or 0) * 0.95, 2), step=0.5)
        nota = st.text_input("Nota para ti (opcional)", placeholder="p. ej. «si baja de aquí, vendo la mitad»")
        if st.form_submit_button("➕ Crear aviso", width="stretch"):
            err = alertas.nueva(lista, t, nombre, tipo, precio, precio_actual, nota)
            if err:
                st.error(err)
            else:
                guardar_datos()
                st.success("Aviso creado.")
                st.rerun()
    if not lista:
        st.caption("Aún no tienes avisos. Idea: uno un 10 % por debajo del precio de cada valor grande de tu cartera.")
        return
    activas = [a for a in lista if not a.get("disparada")]
    saltadas = [a for a in lista if a.get("disparada")]
    if saltadas:
        st.markdown("**Han saltado**")
        for a in sorted(saltadas, key=lambda x: x["disparada"], reverse=True):
            with st.container(border=True):
                st.markdown(f"🔔 **{alertas.texto(a, a.get('precio_disparo'))}** · "
                            f"{date.fromisoformat(a['disparada']).strftime('%d/%m/%Y')}")
                c = st.columns(3)
                if not a.get("vista") and c[0].button("👍 Visto", key=f"al_v_{a['id']}"):
                    a["vista"] = True
                    guardar_datos()
                    st.rerun()
                if c[1].button("🔁 Volver a activar", key=f"al_r_{a['id']}"):
                    a.update(disparada=None, precio_disparo=None, vista=False, creada=date.today().isoformat())
                    guardar_datos()
                    st.rerun()
                if c[2].button("🗑️ Borrar", key=f"al_b_{a['id']}"):
                    lista.remove(a)
                    guardar_datos()
                    st.rerun()
    if activas:
        st.markdown("**Vigilando**")
        for a in activas:
            c = st.columns([5, 1])
            c[0].markdown(f"⏳ {alertas.describir(a)}" + (f" · _{a['nota']}_" if a.get("nota") else ""))
            if c[1].button("🗑️", key=f"al_b_{a['id']}", help="Borrar este aviso"):
                lista.remove(a)
                guardar_datos()
                st.rerun()


def _posiciones_valoradas() -> list[dict]:
    try:
        filas = revisar_cartera_real()
    except Exception:  # noqa: BLE001
        return []
    return [{"clase": f["clase"], "valor": f["pos"]["acciones"] * f["precio"] * f["fx"]} for f in filas if f["precio"]]


def tab_aportacion():
    d = cuenta_activa()
    cfg = d.setdefault("aportacion", {"importe": 0.0, "dia": 1, "hechas": []})
    st.markdown("Meter una cantidad fija cada mes, pase lo que pase en la bolsa, es lo que mejor funciona a largo "
                "plazo para la mayoría de la gente: no hay que adivinar cuándo entrar.")
    c = st.columns(2)
    importe = c[0].number_input("¿Cuánto cada mes? (€, 0 = sin aportación)", 0.0, 100_000.0,
                                float(cfg.get("importe", 0.0)), 50.0)
    dia = c[1].number_input("¿Qué día del mes?", 1, 31, int(cfg.get("dia", 1)),
                            help="Mejor unos días después de cobrar la nómina.")
    if (importe, dia) != (cfg.get("importe"), cfg.get("dia")):
        cfg["importe"], cfg["dia"] = float(importe), int(dia)
        guardar_datos()
    if not importe:
        return

    hoy = date.today()
    proxima = aportaciones.proxima(cfg, hoy)
    racha = aportaciones.racha(cfg, hoy)
    k = st.columns(3 if not perfil().movil else 2)
    k[0].metric("Próxima", "Hoy" if proxima == hoy else proxima.strftime("%d/%m/%Y"))
    k[1 % len(k)].metric("Meses seguidos", racha)
    k[2 % len(k)].metric("Aportado con la app", eur(sum(h["importe"] for h in cfg.get("hechas", []))))

    perfil_nombre = _perfil_guardado()
    objetivo = asesor.REPARTOS[perfil_nombre or "Moderado"]
    actuales = aportaciones.valores_por_destino(_posiciones_valoradas(), d.get("otros_ahorros", 0.0))
    reparto = aportaciones.repartir(importe, actuales, objetivo)
    st.subheader("A dónde llevarla este mes")
    st.caption(f"Según tu reparto ideal ({perfil_nombre or 'Moderado: haz el test de 🎯 Mi plan para afinarlo'}) y "
               "lo que ya tienes en 🏦 Mi cartera. El dinero nuevo va a lo que está por debajo de su objetivo: así "
               "reequilibras sin vender ni pagar impuestos.")
    for destino, euros in reparto.items():
        st.markdown(f"- **{eur(euros)}** → {DESTINO_CORTO.get(destino, destino)}")
    if "Fondo indexado mundial" in reparto:
        st.caption("En Bankinter, los fondos indexados se compran sin comisión de compra y puedes programar una "
                   "aportación periódica automática en el propio fondo (Fondos → tu fondo → Aportaciones periódicas).")

    if aportaciones.hecha_este_mes(cfg, hoy):
        st.success("✅ Este mes ya está hecha.")
    elif st.button("✅ Ya he hecho la aportación de este mes", width="stretch"):
        cfg.setdefault("hechas", []).append({"fecha": hoy.isoformat(), "importe": float(importe), "destino": reparto})
        guardar_datos()
        st.rerun()

    final = simular_aportaciones(importe, 20, 6.0)[-1]
    st.info(f"Si mantienes {eur(importe)} al mes durante 20 años y la inversión rinde de media un 6 % al año "
            f"(orientativo, como un fondo mundial en el pasado, sin garantía), aportarías {eur(final['Aportado'])} "
            f"y tendrías unos **{eur(final['Valor'])}**.")
    if cfg.get("hechas"):
        with st.expander("Historial de aportaciones"):
            st.dataframe(pd.DataFrame([{"Fecha": h["fecha"], "Importe (€)": h["importe"]}
                                       for h in reversed(cfg["hechas"])]), hide_index=True, width="stretch")


def tab_diario():
    d = cuenta_activa()
    lista = d.setdefault("diario", [])
    st.markdown("Apunta **por qué** haces cada cosa (o por qué decides no hacer nada). Cuando pase el tiempo que "
                "elijas, la app te enseña qué ocurrió después. Es la mejor forma de aprender de tus decisiones.")
    revisar = diario.pendientes(lista)
    for e in revisar:
        ev = diario.evaluar(e, _ultimo_precio(e["ticker"]))
        with st.container(border=True):
            st.markdown(f"📓 **Toca revisar:** {e['accion']} de **{e['nombre']}** el "
                        f"{date.fromisoformat(e['fecha']).strftime('%d/%m/%Y')}")
            st.markdown(f"Tu motivo: _«{e['motivo']}»_")
            st.markdown(ev["frase"])
            st.caption("Un buen resultado no siempre significa una buena decisión (y al revés). Pregúntate: ¿pasó lo "
                       "que esperabas, por el motivo que pensabas?")
            leccion = st.text_input("¿Qué aprendes? (opcional)", key=f"dia_l_{e['id']}")
            if st.button("Marcar como revisado", key=f"dia_r_{e['id']}"):
                diario.marcar_revisada(lista, e["id"], leccion)
                guardar_datos()
                st.rerun()

    with st.expander("➕ Nuevo apunte", expanded=not lista):
        t, nombre = _elegir_valor("diario")
        precio_actual = _ultimo_precio(t)
        with st.form("nuevo_apunte", border=False):
            c = st.columns(2)
            accion = c[0].selectbox("¿Qué haces?", diario.ACCIONES)
            precio = c[1].number_input("Precio", 0.0, value=float(round(precio_actual or 0.0, 2)), step=0.1)
            motivo = st.text_area("¿Por qué? (en una o dos frases)",
                                  placeholder="p. ej. «Vendo la mitad de Indra porque pesa demasiado en mi cartera»")
            cuando = st.selectbox("Revisarlo dentro de", list(diario.REVISAR_EN), index=1)
            if st.form_submit_button("Guardar apunte", width="stretch"):
                err = diario.nueva(lista, t, nombre, accion, precio, motivo, diario.REVISAR_EN[cuando])
                if err:
                    st.error(err)
                else:
                    guardar_datos()
                    st.rerun()
    if not lista:
        return
    tickers = tuple(sorted({e["ticker"] for e in lista}))
    try:
        hist = cargar_varios(tickers, "1mo")
    except Exception:  # noqa: BLE001
        hist = {}
    filas = []
    for e in sorted(lista, key=lambda x: x["fecha"], reverse=True):
        df = hist.get(e["ticker"])
        ahora = float(df["Close"].iloc[-1]) if df is not None and not df.empty else None
        ev = diario.evaluar(e, ahora)
        filas.append({"Fecha": e["fecha"], "Valor": e["nombre"], "Qué": e["accion"], "Precio": e.get("precio"),
                      "Ahora": round(ahora, 2) if ahora else None,
                      "Cambio (%)": round(ev["cambio"] * 100, 1) if ev["cambio"] is not None else None,
                      "Por qué": e["motivo"], "Lección": e.get("leccion", "")})
    tabla = pd.DataFrame(filas)
    if perfil().movil:
        tabla = tabla[["Fecha", "Valor", "Qué", "Cambio (%)"]]
    st.dataframe(tabla, hide_index=True, width="stretch")
    borrar = st.selectbox("Borrar un apunte", [None] + [e["id"] for e in lista],
                          format_func=lambda i: "—" if i is None else next(
                              f"{e['fecha']} · {e['accion']} · {e['nombre']}" for e in lista if e["id"] == i))
    if borrar is not None and st.button("🗑️ Borrar este apunte"):
        d["diario"] = [e for e in lista if e["id"] != borrar]
        guardar_datos()
        st.rerun()


def tab_renta():
    d = cuenta_activa()
    cr = d
    historial = cr.get("historial", [])
    hoy = date.today()
    anio = st.selectbox("Año", [hoy.year, hoy.year - 1], index=1 if hoy.month <= 6 else 0,
                        format_func=lambda a: f"{a} (Renta que se presenta en {a + 1})")
    st.markdown("Tus **ventas** y **dividendos** del año con lo que has registrado en 🏦 Mi cartera, ya colocados "
                "como los pide Hacienda. Compáralo con el **borrador** de Renta Web (tu banco ya envía estos datos a "
                "Hacienda): si algo no cuadra, manda el **certificado fiscal** de tu banco.")
    anteriores = st.number_input("Pérdidas de años anteriores aún sin compensar (€, de tus últimas 4 declaraciones)",
                                 0.0, 1e7, float(d.get("perdidas_anteriores", 0.0)), 100.0,
                                 help="Aparecen en tu declaración del año pasado como «saldos negativos pendientes de "
                                      "compensar».")
    if anteriores != d.get("perdidas_anteriores", 0.0):
        d["perdidas_anteriores"] = anteriores
        guardar_datos()

    nombres = {h["ticker"]: nombre_de(h["ticker"]) for h in historial}
    nombres.update({t: nombre_posicion(t, p) for t, p in cr.get("posiciones", {}).items()})
    ventas = renta.ventas_del_ano(historial, anio, nombres)
    tickers = tuple(sorted({h["ticker"] for h in historial if h.get("tipo") == "Compra"}))
    try:
        divs = cargar_dividendos_varios(tickers) if tickers else {}
        cambios = {t: fx(t) or 1.0 for t in tickers}
    except Exception:  # noqa: BLE001
        divs, cambios = {}, {}
        st.caption("No se han podido descargar los dividendos ahora mismo.")
    dividendos = renta.dividendos_del_ano(historial, divs, cambios, anio, nombres)
    if any(h.get("tipo") == "Compra" and h["fecha"][:4] == str(anio) for h in historial):
        st.caption("Los dividendos se cuentan desde la fecha de compra que tiene la app. Si importaste tu cartera "
                   f"en {anio} sin poner la fecha real de compra, faltarán los cobrados antes: para esos, mira el "
                   "certificado fiscal de tu banco.")
    if not ventas and not dividendos:
        st.info(f"No hay ventas ni dividendos registrados en {anio}. Cuando vendas algo, regístralo en 🏦 Mi cartera → "
                "tu posición → «Registrar venta»: así la app lleva la cuenta para la Renta.")
        return
    r = renta.resumen(ventas, dividendos, anteriores)
    k = st.columns(2 if perfil().movil else 4)
    k[0].metric("Resultado de tus ventas", eur(r["saldo_ventas"]))
    k[1].metric("Dividendos (bruto)", eur(r["dividendos_brutos"]))
    k[2 % len(k)].metric("Base del ahorro", eur(r["base_ahorro"]))
    k[3 % len(k)].metric("IRPF de esta parte (aprox.)", eur(r["cuota"]),
                         f"{eur(r['retenciones'])} ya retenidos", delta_color="off", delta_arrow="off")
    pagar = r["a_pagar"]
    st.markdown(f"Con lo ya retenido, esta parte de tu declaración **{'suma unos ' + eur(pagar) + ' a pagar' if pagar > 0 else 'te devuelve unos ' + eur(-pagar)}**"
                " (se junta con el resto de tu declaración: nómina, etc.).")
    if r["perdidas_anteriores_usadas"]:
        st.caption(f"Se han usado {eur(r['perdidas_anteriores_usadas'])} de pérdidas de años anteriores.")
    if r["compensacion_cruzada"]:
        st.caption(f"Tus pérdidas en ventas compensan {eur(r['compensacion_cruzada'])} de dividendos (máximo, el 25 %).")
    if r["perdidas_para_futuro"]:
        st.success(f"Te quedan {eur(r['perdidas_para_futuro'])} de pérdidas para compensar en los próximos 4 años. "
                   "Apúntalo: Hacienda lo arrastra, pero conviene comprobarlo.")
    for v in r["aplazadas"]:
        st.warning(f"⚠️ La pérdida de {eur(-v['resultado'])} al vender {v['nombre']} el {v['fecha']} **no se puede "
                   "restar este año**: compraste el mismo valor dos meses antes o después (regla de los 2 meses). Se "
                   "restará cuando vendas esas acciones recompradas.")

    if ventas:
        st.subheader("Ventas → «Ganancias y pérdidas patrimoniales (acciones admitidas a negociación)»")
        st.dataframe(pd.DataFrame([{"Fecha": v["fecha"], "Valor": v["nombre"], "Títulos": v["acciones"],
                                    "Venta (€)": round(v["importe_venta"], 2), "Compra (€)": round(v["importe_compra"], 2),
                                    "Resultado (€)": round(v["resultado"], 2)} for v in ventas]),
                     hide_index=True, width="stretch")
        st.caption("Importes con los gastos de compra y venta ya incluidos, como pide Hacienda. La app usa el precio "
                   "medio de compra; si compraste el mismo valor varias veces a precios distintos, Hacienda usa las "
                   "primeras compradas primero (FIFO) y la cifra puede variar algo: la buena es la de tu banco.")
    if dividendos:
        st.subheader("Dividendos → «Rendimientos del capital mobiliario»")
        st.dataframe(pd.DataFrame([{"Fecha ex": x["fecha"], "Valor": x["nombre"], "Títulos": x["acciones"],
                                    "Bruto (€)": round(x["bruto"], 2), "Retención 19 % (€)": round(x["retencion"], 2)}
                                   for x in dividendos]), hide_index=True, width="stretch")
        st.caption("Estimado con tus títulos en cada fecha ex-dividendo. Los gastos de custodia de tu banco también "
                   "se pueden restar de los dividendos.")
        if r["hay_extranjeros"]:
            st.caption("Dividendos extranjeros: el país de origen también retiene (EEUU, un 15 % con el formulario "
                       "W-8BEN). Esa retención se deduce en la casilla de «deducción por doble imposición "
                       "internacional», hasta el 15 %.")
    st.download_button("📥 Descargar para Excel (CSV)", renta.tabla_csv(ventas, dividendos),
                       file_name=f"renta_{anio}_inversiones.csv", mime="text/csv", width="stretch")
    st.caption("Estimación educativa para preparar la declaración, no sustituye a tu certificado fiscal ni a un "
               "asesor fiscal.")
