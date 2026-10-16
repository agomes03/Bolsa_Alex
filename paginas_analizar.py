"""Páginas Analizar (un valor a fondo) y Radar."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from bolsa import asesor, bankinter, costes, noticias, senales
from bolsa.activos import clase_de
from bolsa.indicadores import calcular_todo
from bolsa.tickers import NO_INVERTIBLES, nombre_de, sector_de, TODOS_LOS_VALORES
from paginas_extra import bloque_operar, limite_empresa, pesos_cartera_real
from paginas_hoy import bloque_que_puede_pasar_accion, pagina_radar_global
from paginas_noticias import tarjeta_noticia
from ui_comun import (alto_grafico, cargar_fundamentales, cargar_historico, cargar_informe, cotizaciones_ahora, eur,
                      fila_informe, fx,
                      mercado_alcista_para, moneda_de, mostrar_plotly, noticias_empresa, num, palabras_de_la_pagina,
                      pct, perfil, selector_valor)


def grafico(df: pd.DataFrame, titulo: str, plan: senales.Plan | None = None) -> go.Figure:
    # Solo lo necesario: un año visible (medio año en el móvil) más 200 sesiones para calcular la media larga.
    movil = perfil().movil
    visibles = 130 if movil else 260
    d = calcular_todo(df.tail(visibles + 210)).tail(visibles)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.72, 0.28], vertical_spacing=0.04)
    fig.add_trace(go.Candlestick(x=d.index, open=d["Open"], high=d["High"], low=d["Low"], close=d["Close"],
                                 name="Precio", showlegend=False), row=1, col=1)
    for col, color in (("SMA50", "#f59e0b"), ("SMA200", "#6366f1")):
        fig.add_trace(go.Scatter(x=d.index, y=d[col], name=f"Media {col[3:]}",
                                 line=dict(color=color, width=1.6)), row=1, col=1)
    if plan:
        for y, txt, color in ((plan.stop, "Stop-loss", "#dc2626"), (plan.objetivo, "Objetivo", "#16a34a")):
            fig.add_hline(y=y, line_dash="dash", line_color=color, annotation_text=txt, row=1, col=1)
    fig.add_trace(go.Scatter(x=d.index, y=d["RSI"], name="RSI", line=dict(color="#0ea5e9")), row=2, col=1)
    fig.add_hrect(y0=70, y1=100, fillcolor="#dc2626", opacity=0.08, line_width=0, row=2, col=1)
    fig.add_hrect(y0=0, y1=30, fillcolor="#16a34a", opacity=0.08, line_width=0, row=2, col=1)
    fig.update_yaxes(range=[0, 100], row=2, col=1, title_text="RSI")
    fig.update_layout(title=None if movil else titulo, height=alto_grafico(), xaxis_rangeslider_visible=False,
                      legend=dict(orientation="h", y=1.08), margin=dict(l=5, r=5, t=40, b=5))
    return fig


def bloque_fundamentales(ticker: str, f: dict):
    movil = perfil().movil
    if not f:
        st.caption("No hay datos de la empresa disponibles.")
        return
    m = moneda_de(ticker)

    def fmt(v, tipo):
        if v is None:
            return "—"
        if tipo == "pct":
            return f"{v * 100:.1f}%"
        if tipo == "x":
            return f"{v:.1f}"
        if tipo == "cap":
            return f"{v / 1e9:,.1f} mil M".replace(",", ".")
        return eur(v, m)

    filas = [
        ("Tamaño (capitalización)", fmt(f.get("marketCap"), "cap"), "Lo que vale la empresa entera en bolsa."),
        ("PER", fmt(f.get("trailingPE"), "x"), "Años de beneficios que pagas. <12 barato, 12-25 normal, >25 caro."),
        ("PER futuro", fmt(f.get("forwardPE"), "x"), "Igual, pero con los beneficios esperados del año próximo."),
        ("Rentabilidad por dividendo", fmt(f.get("trailingAnnualDividendYield"), "pct"),
         "Lo que te pagan al año por cada 100 € invertidos."),
        ("Margen de beneficio", fmt(f.get("profitMargins"), "pct"), "De cada 100 € que vende, cuántos gana."),
        ("Crecimiento de ventas", fmt(f.get("revenueGrowth"), "pct"), "Respecto al mismo trimestre del año anterior."),
        ("Rentabilidad sobre fondos propios (ROE)", fmt(f.get("returnOnEquity"), "pct"),
         "Lo bien que usa el dinero de sus accionistas. >15% es muy bueno."),
        ("Precio objetivo de analistas", fmt(f.get("targetMeanPrice"), "eur"),
         f"Media de {f.get('numberOfAnalystOpinions', 0)} analistas. Rango "
         f"{fmt(f.get('targetLowPrice'), 'eur')} – {fmt(f.get('targetHighPrice'), 'eur')}."),
        ("Recomendación media", senales.RECOMENDACIONES.get(f.get("recommendationKey", ""), "—"), ""),
    ]
    tabla = pd.DataFrame(filas, columns=["Dato", "Valor", "Qué significa"])
    if movil:
        tabla = tabla[["Dato", "Valor"]]
    st.dataframe(tabla, hide_index=True, width="stretch")


def plan_de_compra(ticker, ev, fund, f_eur, m, etiqueta, color) -> float:
    """Plan con stop-loss, costes y órdenes. Si el veredicto no es de compra, queda plegado."""
    pf = perfil()
    movil, capital, riesgo, tarifa = pf.movil, pf.capital, pf.riesgo, pf.tarifa
    if color == "green":
        st.subheader("📋 Si decides comprar")
        contenedor = st.container()
    else:
        contenedor = st.expander(f"📋 Si aun así decides comprar (el veredicto de hoy es «{etiqueta}»)")
    importe = 0.0
    with contenedor:
        p = ev.plan
        if f_eur is None:
            st.warning("No se ha podido obtener el tipo de cambio de su divisa: no se pueden calcular importes en "
                       "euros para esta acción.")
        else:
            # Como mucho el 20 % del dinero en una sola empresa (diversificación), aunque el stop esté muy cerca.
            n = min(costes.tamano_por_riesgo(capital, riesgo, p.entrada * f_eur, p.stop * f_eur),
                    costes.acciones_asequibles(capital * 0.20, p.entrada * f_eur, ticker, tarifa))
            importe = n * p.entrada * f_eur
            cap_empresa = fund.get("marketCap")
            iv = costes.coste_ida_y_vuelta(importe, ticker, tarifa, capitalizacion=cap_empresa) if importe else None
            c = st.columns(2 if movil else 4)
            c[0].metric("Comprar", f"{n} {'acción' if n == 1 else 'acciones'}", f"≈ {eur(importe)}",
                    delta_color="off", delta_arrow="off")
            c[1].metric("Stop-loss (vender si baja a)", eur(p.stop, m), pct(-p.riesgo_pct), delta_color="off", delta_arrow="off")
            c[2 % len(c)].metric("Objetivo", eur(p.objetivo, m), pct(p.beneficio_pct))
            if iv:
                c[3 % len(c)].metric("Costes Bankinter", eur(iv["total"]), f"{pct(iv['pct'], 2, False)} del importe",
                                     delta_color="off", delta_arrow="off", help="Comprar + vender + 1 año de custodia (si es extranjera).")
            st.markdown(
                f"Si sale mal y salta el stop, perderías unos **{eur(n * (p.entrada - p.stop) * f_eur)}** "
                f"(como máximo el {num(riesgo, 1)} % de tus {eur(capital)}). Si llega al objetivo, "
                f"ganarías unos **{eur(n * (p.objetivo - p.entrada) * f_eur)}** antes de impuestos. Nunca más del "
                "20 % de tu dinero en una sola empresa.")
            st.caption("El stop-loss está a 2 veces lo que se mueve en un día normal (para que el ruido diario no lo "
                       "active) y el objetivo al doble de esa distancia: así ganas 2 € por cada 1 € que arriesgas.")
            if n == 0:
                st.info("Con tu dinero y tu riesgo máximo no llega para comprar ni una acción con este stop-loss.")
            elif iv and iv["pct"] > 2:
                st.warning(f"Los costes se comerían un {pct(iv['pct'], 1, False)} de la inversión. "
                           + ("En Bankinter, las acciones extranjeras pagan 20 € por operación, un 1 % de cambio de "
                              "divisa y una custodia mínima de 24 € al año: solo compensan con unos 5.000 € o más."
                              if not costes.es_nacional(ticker) else "Con importes tan pequeños, la comisión mínima "
                              "pesa mucho."))
            if color != "green":
                st.info("Si aun así compras, que sea con poco dinero y con el stop-loss puesto desde el primer día.")
            bloque_operar(ticker, n, p, f_eur)
    return importe


def pagina_analizar():
    movil = perfil().movil
    st.title("🔍 Analizar")
    pre = st.session_state.pop("analizar_ticker", None)
    ticker = selector_valor("an", defecto=pre)
    otro = st.text_input("¿No está en la lista? Escribe su código de Yahoo Finance (ej. KO, SAP.DE)", "").strip().upper()
    if otro:
        ticker = otro

    with st.spinner(f"Analizando {nombre_de(ticker)}..."):
        df = cargar_historico(ticker, "10y")
        if df.empty or len(df) < 30:
            st.error("No hay datos suficientes para ese código. Comprueba que está bien escrito.")
            return
        with ThreadPoolExecutor(max_workers=2) as pool:
            f_fund = pool.submit(cargar_fundamentales, ticker)
            f_news = pool.submit(noticias_empresa, ticker)
            fund, news = f_fund.result(), f_news.result()
        fila = fila_informe(ticker)
        inf = cargar_informe()
        riesgo_modelo = None
        if fila and fila.get("riesgo_caida") is not None and inf and inf.get("modelo_riesgo", {}).get("fiabilidad") != "Baja":
            riesgo_modelo = {"prob": fila["riesgo_caida"], "base": inf["modelo_riesgo"]["metricas"]["tasa_subidas"]}
        recientes = [n for n in news if n.horas is None or n.horas < 24 * 7]
        mercado_ok = mercado_alcista_para(ticker)
        ev = senales.evaluar(ticker, df,
                             sentimiento_noticias=noticias.sentimiento_medio(recientes) if recientes else None,
                             n_noticias=len(recientes), mercado_alcista=mercado_ok, fundamentales=fund,
                             riesgo=riesgo_modelo)

    m = moneda_de(ticker, fund)
    f_eur = fx(ticker, fund)
    titulo = nombre_de(ticker) if ticker in TODOS_LOS_VALORES else fund.get("longName", ticker)
    try:
        q = cotizaciones_ahora([ticker]).get(ticker)
    except Exception:  # noqa: BLE001 - sin precio reciente, se queda el del histórico
        q = None
    precio_hoy = q["precio"] if q else ev.precio
    precio_txt = eur(precio_hoy, m) + (f" (≈ {eur(precio_hoy * f_eur)})" if f_eur and m != "€" else "")
    st.header(f"{titulo} · {precio_txt}")
    st.caption(f"{sector_de(ticker)} · {bankinter.mercado_de(ticker)} · hoy {pct(ev.datos['var_1d'])} · "
               f"último año {pct(ev.datos['var_1a'], 0)}")
    if q:
        cuando = {"tiempo_real": "⚡ Ahora mismo (tiempo real)", "directo": "🟢 Ahora (unos 15 min de retraso)"}.get(
            q["estado"], f"🔒 Bolsa cerrada · cierre del {q['fecha']:%d/%m}")
        st.markdown(f"{cuando}: **{eur(q['precio'], m)}**"
                    + (f" ({pct(q['variacion_pct'], 2)} en la sesión)" if q.get("variacion_pct") is not None else ""))

    datos_v = fila or {"puntuacion": ev.puntuacion, "mercado_alcista": mercado_ok,
                       "resultados_pronto": any("resultados" in a for a in ev.avisos)}
    etiqueta, color, explicacion = asesor.veredicto(datos_v)
    c1, c2 = st.columns([1, 2])
    with c1:
        st.markdown(f"### :{color}[{etiqueta}]")
        st.write(explicacion)
        if fila and fila.get("nota") is not None:
            st.metric("Nota global", f"{fila['nota']}/100", f"puesto {fila['puesto']} de {fila['de']}",
                      delta_color="off", delta_arrow="off", help="Su puesto frente a todas las demás acciones combinando lo que ha "
                                              "funcionado con datos reales: subida del último año (50 %), "
                                              "tendencia (30 %) y menor riesgo de caída (20 %).")
        if riesgo_modelo:
            st.metric("Riesgo de caer más de un 10 % el próximo mes", pct(riesgo_modelo["prob"] * 100, 0, False),
                      f"lo normal: {pct(riesgo_modelo['base'] * 100, 0, False)}", delta_color="off", delta_arrow="off")
    with c2:
        mostrar_plotly(grafico(df, "Último año" if not movil else "Últimos 6 meses", ev.plan))
        st.caption("Velas: cada día (verde si subió, roja si bajó). Naranja: media de 50 sesiones (≈3 meses). "
                   "Morada: media de 200 sesiones (≈1 año). Abajo, el RSI: por encima de 70 ha subido muy deprisa, "
                   "por debajo de 30 ha caído muy deprisa.")
    for a in ev.avisos:
        st.warning(a)
    peso = pesos_cartera_real().get(ticker, 0.0)
    tope = limite_empresa()
    if peso > tope:
        st.warning(f"⚖️ **Ya tienes demasiada:** {titulo} es el {peso * 100:.0f} % de tu dinero. Aunque hoy tenga buen "
                   "veredicto, no compres más: para tu perfil, lo prudente es que ninguna empresa pase del "
                   f"{tope * 100:.0f} %. Mira en 🏦 Mi cartera cómo repartir el riesgo.")
        etiqueta, color = "Ya tienes demasiada", "orange"

    with st.expander(f"🧠 Por qué (puntuación técnica {ev.puntuacion}/100, explicada paso a paso)"):
        for mo in sorted(ev.motivos, key=lambda x: -abs(x.puntos)):
            st.markdown(f"{mo.icono} **{mo.titulo}** ({mo.puntos:+d})  \n{mo.explicacion}")

    clase = clase_de(ticker, None, fund.get("longName", ""))
    if ticker in NO_INVERTIBLES or ticker.startswith("^"):
        st.info("Esto es un **índice o indicador**: sirve de termómetro y no se compra directamente. Para invertir "
                "en un índice se usa un fondo indexado o un ETF que lo copie (los tienes en «Fondos indexados» y "
                "«ETF y oro»).")
    elif clase in ("Fondos y ETF", "Renta fija", "Monetario y liquidez"):
        st.info("Es un **fondo o ETF diversificado**: se invierte con aportaciones periódicas y a largo plazo, sin "
                "stop-loss. Puedes practicar con él en 🎮 Cartera virtual.")
        st.subheader("🌦️ Qué le puede pasar a tu dinero")
        bloque_que_puede_pasar_accion(ticker, df, 1_000.0)
    else:
        importe_ref = 1_000.0
        if ev.plan:
            importe_ref = plan_de_compra(ticker, ev, fund, f_eur, m, etiqueta, color) or importe_ref
        st.subheader("🌦️ Qué le puede pasar a tu dinero")
        bloque_que_puede_pasar_accion(ticker, df, importe_ref)

    if clase == "Acciones":
        st.subheader("🏢 La empresa en números")
        bloque_fundamentales(ticker, fund)

    st.subheader("📰 Noticias")
    if news:
        for n_ in news[:8]:
            tarjeta_noticia(n_)
    else:
        st.caption("No se han encontrado noticias recientes.")
    palabras_de_la_pagina(["Veredicto", "Nota global", "Riesgo de caída", "Tendencia", "Media de 200 sesiones", "RSI",
                           "Volatilidad", "Stop-loss", "Objetivo de precio", "Orden limitada", "PER", "Dividendo",
                           "Rentabilidad por dividendo", "Precio objetivo de los analistas"])


def pagina_radar():
    if pagina_radar_global():
        return
    st.title("📡 Radar")
    st.info("El radar usa el informe diario, que todavía no se ha generado. Se crea solo cada día laborable al "
            "cierre de Wall Street (GitHub → Actions → «Actualización diaria»). Mientras tanto, usa 🔍 Analizar.")
