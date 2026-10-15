"""Asistente de Bolsa para principiantes (pensado para operar con el broker de Bankinter).

Ejecutar:  streamlit run app.py
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from bolsa import asesor, bankinter, costes, noticias, senales
from bolsa.indicadores import calcular_todo
from bolsa.tickers import INDICES, MERCADOS, TERMOMETROS, TODAS_LAS_ACCIONES, mercado_de, nombre_de, sector_de
from paginas_extra import bloque_operar, pagina_bankinter, pagina_cartera_virtual, pagina_simulador
from paginas_hoy import (bloque_fases, bloque_que_puede_pasar_accion, pagina_carteras, pagina_hoy, pagina_plan,
                         pagina_radar_global)
from ui_comun import (Perfil, cargar_fundamentales, cargar_historico, cargar_informe, cargar_noticias, cargar_varios,
                      es_movil, estrategia_actual, eur, fila_informe, fx, mercado_alcista_para, moneda_de,
                      noticias_empresa, num, pct)

st.set_page_config(page_title="Asistente de Bolsa", page_icon="📈", layout="wide",
                   initial_sidebar_state="collapsed")

AVISO = ("⚠️ **Herramienta educativa, no es asesoramiento financiero.** Ningún sistema puede "
         "garantizar beneficios ni predecir la bolsa con certeza: invierte solo dinero que no vayas a "
         "necesitar en años y que puedas permitirte ver bajar un 30% sin vender por miedo.")


# --------------------------------------------------------------------------- barra lateral (perfil)
with st.sidebar:
    st.title("⚙️ Tu perfil")
    movil = st.toggle("📱 Vista para móvil", value=es_movil(),
                      help="Gráficos más bajos y tablas con menos columnas. Se activa sola en el móvil.")
    capital = st.number_input("Dinero que tienes para invertir (€)", min_value=100.0, value=3000.0, step=100.0)
    riesgo = st.slider("Máximo que aceptas perder por operación (% de tu dinero)", 0.5, 5.0, 1.0, 0.5,
                       help="Regla de oro de los profesionales: no arriesgar más de un 1-2% del capital "
                            "en una sola operación. Así, aunque falles varias veces seguidas, sigues en el juego.")
    with st.expander("Tus comisiones en Bankinter"):
        broker_cero = st.toggle("Tengo el servicio Bróker Cero", value=False,
                                help="Con Bróker Cero, comprar y vender acciones españolas por Internet cuesta 0 € "
                                     "(solo pagas los cánones de la bolsa).")
        canon = st.number_input("Cánones de bolsa en España por operación (€, aprox.)", 0.0, 10.0, 1.0, 0.5)
        tarifa = costes.Tarifa(broker_cero=broker_cero, canon_nacional=canon)
        st.caption("Tarifa pública de Bankinter (oct. 2026): acciones españolas 3,95 € hasta 2.000 € y 8 € hasta "
                   "60.000 € por operación; extranjeras 20 € por operación, +1 % si se cambia de divisa, y una "
                   "custodia mínima de 24 € al año por valor. Compruébala en Bankinter → Bróker → Tarifas.")
    st.divider()
    st.caption(f"Cotizaciones de Yahoo Finance (retraso ~15 min). Noticias de {len(noticias.FUENTES_RSS)} "
               "fuentes RSS en español e inglés. Se actualizan solas cada 5-10 minutos.")
    if st.button("🔄 Actualizar ahora", width="stretch"):
        st.cache_data.clear()
        st.rerun()

ALTO_GRAFICO = 430 if movil else 560
st.session_state["_perfil"] = Perfil(movil=movil, capital=capital, riesgo=riesgo, tarifa=tarifa)


# --------------------------------------------------------------------------- componentes
def tarjeta_noticia(n: noticias.Noticia, expandida: bool = False):
    estrellas = "🔥" * max(1, round(n.impacto / 2)) if n.impacto >= 4 else "·"
    empresas = ", ".join(nombre_de(t) for t in n.empresas)
    with st.expander(f"{n.etiqueta_sentimiento} · {estrellas} · {n.titulo}", expanded=expandida):
        st.markdown(f"**[{n.titulo}]({n.enlace})**")
        st.caption(f"{n.fuente} · {noticias.hace_cuanto(n)} · Impacto {n.impacto}/10"
                   + (f" · Publicada en {n.repeticiones} medios" if n.repeticiones > 1 else "")
                   + (f" · Empresas: {empresas}" if empresas else ""))
        if n.resumen and n.resumen.lower()[:60] not in n.titulo.lower():
            st.write(n.resumen)
        if n.explicaciones:
            st.markdown("**💡 Por qué importa:**")
            for e in n.explicaciones[:3]:
                st.markdown(f"- {e}")
        else:
            st.caption("Noticia sin un tema macro clave detectado: probablemente impacto limitado.")


def grafico(df: pd.DataFrame, titulo: str, plan: senales.Plan | None = None) -> go.Figure:
    d = calcular_todo(df).tail(260)
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
    fig.update_layout(title=None if movil else titulo, height=ALTO_GRAFICO, xaxis_rangeslider_visible=False,
                      legend=dict(orientation="h", y=1.08), margin=dict(l=5, r=5, t=40, b=5))
    return fig


def bloque_fundamentales(ticker: str, f: dict):
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


def pagina_resumen():
    st.title("🌍 Mercados")
    st.info(AVISO)

    with st.spinner("Descargando cotizaciones..."):
        hist = cargar_varios(tuple(list(INDICES) + list(TERMOMETROS)))
    if not hist:
        st.error("No se han podido descargar cotizaciones. Revisa tu conexión a Internet y pulsa 'Actualizar'.")
        return

    st.subheader("Los grandes índices")
    st.caption("Un índice es una 'cesta' con las principales empresas de una bolsa. 🟢/🔴 indica si está por "
               "encima o por debajo de su media de 200 sesiones (≈1 año): la forma más simple de saber si el "
               "mercado está en tendencia alcista.")
    cols = st.columns(2 if movil else len(INDICES))
    alcistas = 0
    for i, (t, info) in enumerate(INDICES.items()):
        col = cols[i % len(cols)]
        if t not in hist:
            col.metric(info["nombre"], "sin datos")
            continue
        e = senales.estado_indice(hist[t])
        alcistas += e["alcista"]
        col.metric(f"{'🟢' if e['alcista'] else '🔴'} {info['nombre']}", f"{e['precio']:,.0f}".replace(",", "."),
                   pct(e["var_1d"]), help=f"{info['que_es']}\n\n{e['texto']}")
        col.caption(f"1 mes {pct(e['var_1m'], 1)} · 1 año {pct(e['var_1a'], 1)}")

    st.subheader("Termómetros")
    cols = st.columns(len(TERMOMETROS))
    for col, (t, info) in zip(cols, TERMOMETROS.items()):
        if t in hist:
            c = hist[t]["Close"]
            col.metric(info["nombre"], f"{c.iloc[-1]:.2f}", pct((c.iloc[-1] / c.iloc[-2] - 1) * 100),
                       delta_color="inverse" if t == "^VIX" else "normal", help=info["que_es"])
            if not movil:
                col.caption(info["que_es"])

    with st.spinner("Leyendo noticias de todas las fuentes..."):
        lista, fallos = cargar_noticias()
    sent = noticias.sentimiento_medio([n for n in lista if n.impacto >= 4][:40])

    vix = float(hist["^VIX"]["Close"].iloc[-1]) if "^VIX" in hist else None
    st.subheader("🚦 Semáforo del mercado")
    if alcistas >= 4 and (vix is None or vix < 22):
        st.success("**VERDE · Mercado alcista y tranquilo.** Buen entorno para invertir de forma "
                   "escalonada en buenas empresas o índices. Aun así, no persigas acciones que ya han subido mucho.")
    elif alcistas >= 3:
        st.warning("**ÁMBAR · Mercado mixto.** Algunas bolsas van bien y otras no. Sé selectivo, entra "
                   "poco a poco y usa siempre stop-loss.")
    else:
        st.error("**ROJO · Mercado débil o nervioso.** La mayoría de índices están por debajo de su media "
                 "de 200 sesiones. Para un principiante lo prudente es esperar o, si inviertes a largo plazo "
                 "en índices, seguir con aportaciones pequeñas y periódicas.")
    tono = "positivo 🟢" if sent > 0.15 else "negativo 🔴" if sent < -0.15 else "neutro ⚪"
    st.caption(f"Tono de las noticias importantes: **{tono}** ({sent:+.2f} en escala -1 a +1), "
               f"según {len(lista)} noticias de {len(noticias.FUENTES_RSS) - len(fallos)} fuentes."
               + (f" VIX: {vix:.1f}." if vix else ""))

    bloque_fases(cargar_informe())


def pagina_noticias():
    st.title("📰 Noticias que mueven el mercado")
    st.caption(f"Se leen **{len(noticias.FUENTES_RSS)} fuentes** (prensa española, Google News, CNBC, MarketWatch, "
               "Yahoo Finance...) y se ordenan por **impacto estimado** (0-10): temas que históricamente mueven las "
               "bolsas, cuántos medios publican la misma noticia y lo reciente que es. Despliega cada una para ver "
               "**por qué importa**.")
    with st.spinner("Leyendo todas las fuentes..."):
        lista, fallos = cargar_noticias()
    st.caption(f"{len(lista)} noticias únicas de las últimas 72 h."
               + (f" Fuentes no disponibles ahora: {', '.join(fallos)}." if fallos else ""))
    if not lista:
        st.error("No se han podido descargar noticias.")
        return

    c1, c2, c3 = st.columns(3)
    minimo = c1.slider("Impacto mínimo", 0, 10, 3)
    tono = c2.selectbox("Tono", ["Todas", "🟢 Positivas", "🔴 Negativas"])
    empresas = sorted({t for n in lista for t in n.empresas}, key=nombre_de)
    filtro_emp = c3.selectbox("Empresa", ["Todas"] + empresas, format_func=lambda t: t if t == "Todas" else nombre_de(t))

    filtradas = [n for n in lista if n.impacto >= minimo
                 and (tono == "Todas" or (tono.startswith("🟢") and n.sentimiento > 0) or (tono.startswith("🔴") and n.sentimiento < 0))
                 and (filtro_emp == "Todas" or filtro_emp in n.empresas)]
    st.write(f"**{len(filtradas)}** noticias")

    menciones: dict[str, list[int]] = {}
    for n in lista:
        for t in n.empresas:
            menciones.setdefault(t, []).append(n.sentimiento)
    if menciones:
        with st.expander("🏢 Empresas más mencionadas"):
            filas = [{"Empresa": nombre_de(t), "Noticias": len(s), "Tono medio": round(sum(s) / len(s), 2)}
                     for t, s in menciones.items()]
            st.dataframe(pd.DataFrame(filas).sort_values("Noticias", ascending=False),
                         hide_index=True, width="stretch")
            st.caption("Que una empresa salga mucho en las noticias no significa que haya que comprarla. "
                       "Analízala en '🔍 Analizar'.")

    for i, n in enumerate(filtradas[:80]):
        tarjeta_noticia(n, expandida=i < 3 and not movil)


def pagina_analizar():
    st.title("🔍 Analizar una acción")
    pre = st.session_state.pop("analizar_ticker", None)
    if pre in TODAS_LAS_ACCIONES:
        st.session_state["an_mercado"] = mercado_de(pre)
        st.session_state["an_empresa"] = pre
    c1, c2 = st.columns([1, 2])
    grupo = c1.selectbox("Mercado", list(MERCADOS), key="an_mercado")
    opciones = list(MERCADOS[grupo])
    if st.session_state.get("an_empresa") not in opciones:
        st.session_state.pop("an_empresa", None)
    ticker = c2.selectbox("Empresa", opciones, key="an_empresa", format_func=nombre_de)
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
    titulo = nombre_de(ticker) if ticker in TODAS_LAS_ACCIONES else fund.get("longName", ticker)
    precio_txt = eur(ev.precio, m) + (f" (≈ {eur(ev.precio * f_eur)})" if f_eur and m != "€" else "")
    st.header(f"{titulo} · {precio_txt}")
    st.caption(f"{sector_de(ticker)} · {bankinter.mercado_de(ticker)} · hoy {pct(ev.datos['var_1d'])} · "
               f"último año {pct(ev.datos['var_1a'], 0)}")

    datos_v = fila or {"puntuacion": ev.puntuacion, "mercado_alcista": mercado_ok,
                       "resultados_pronto": any("resultados" in a for a in ev.avisos)}
    etiqueta, color, explicacion = asesor.veredicto(datos_v)
    c1, c2 = st.columns([1, 2])
    with c1:
        st.markdown(f"### :{color}[{etiqueta}]")
        st.write(explicacion)
        if fila and fila.get("nota") is not None:
            st.metric("Nota global", f"{fila['nota']}/100", f"puesto {fila['puesto']} de {fila['de']}",
                      delta_color="off", help="Su puesto frente a todas las demás acciones combinando lo que ha "
                                              "funcionado con datos reales: subida del último año (50 %), "
                                              "tendencia (30 %) y menor riesgo de caída (20 %).")
        if riesgo_modelo:
            st.metric("Riesgo de caer más de un 10 % el próximo mes", pct(riesgo_modelo["prob"] * 100, 0, False),
                      f"lo normal: {pct(riesgo_modelo['base'] * 100, 0, False)}", delta_color="off")
    with c2:
        st.plotly_chart(grafico(df, "Último año", ev.plan), width="stretch")
        st.caption("Velas: cada día (verde si subió, roja si bajó). Naranja: media de 50 sesiones (≈3 meses). "
                   "Morada: media de 200 sesiones (≈1 año). Abajo, el RSI: por encima de 70 ha subido muy deprisa, "
                   "por debajo de 30 ha caído muy deprisa.")
    for a in ev.avisos:
        st.warning(a)

    with st.expander(f"🧠 Por qué (puntuación técnica {ev.puntuacion}/100, explicada paso a paso)"):
        for mo in sorted(ev.motivos, key=lambda x: -abs(x.puntos)):
            st.markdown(f"{mo.icono} **{mo.titulo}** ({mo.puntos:+d})  \n{mo.explicacion}")

    importe_ref = 1_000.0
    if ev.plan:
        st.subheader("📋 Si decides comprar")
        p = ev.plan
        if f_eur is None:
            st.warning("No se ha podido obtener el tipo de cambio de su divisa: no se pueden calcular importes en "
                       "euros para esta acción.")
        else:
            n = min(costes.tamano_por_riesgo(capital, riesgo, p.entrada * f_eur, p.stop * f_eur),
                    costes.acciones_asequibles(capital, p.entrada * f_eur, ticker, tarifa))
            importe = n * p.entrada * f_eur
            importe_ref = importe or importe_ref
            cap_empresa = fund.get("marketCap")
            iv = costes.coste_ida_y_vuelta(importe, ticker, tarifa, capitalizacion=cap_empresa) if importe else None
            c = st.columns(2 if movil else 4)
            c[0].metric("Comprar", f"{n} acciones", f"≈ {eur(importe)}", delta_color="off")
            c[1].metric("Stop-loss (vender si baja a)", eur(p.stop, m), pct(-p.riesgo_pct), delta_color="off")
            c[2 % len(c)].metric("Objetivo", eur(p.objetivo, m), pct(p.beneficio_pct))
            if iv:
                c[3 % len(c)].metric("Costes Bankinter", eur(iv["total"]), f"{pct(iv['pct'], 2, False)} del importe",
                                     delta_color="off", help="Comprar + vender + 1 año de custodia (si es extranjera).")
            st.markdown(
                f"Si sale mal y salta el stop, perderías unos **{eur(n * (p.entrada - p.stop) * f_eur)}** "
                f"(el {num(riesgo, 1)} % de tus {eur(capital)}, como has fijado en tu perfil). Si llega al objetivo, "
                f"ganarías unos **{eur(n * (p.objetivo - p.entrada) * f_eur)}** antes de impuestos.")
            st.caption(f"El stop-loss está a {num(estrategia_actual().stop_atr, 1)} veces lo que se mueve en un día normal "
                       "(para que el ruido diario no lo active) y el objetivo al doble de esa distancia: así ganas 2 € "
                       "por cada 1 € que arriesgas.")
            if n == 0:
                st.info("Con tu dinero y tu riesgo máximo no llega para comprar ni una acción con este stop-loss.")
            elif iv and iv["pct"] > 2:
                st.warning(f"Los costes se comerían un {pct(iv['pct'], 1, False)} de la inversión. "
                           + ("En Bankinter, las acciones extranjeras pagan 20 € por operación, un 1 % de cambio de "
                              "divisa y una custodia mínima de 24 € al año: solo compensan con unos 5.000 € o más."
                              if not costes.es_nacional(ticker) else "Con importes tan pequeños, la comisión mínima "
                              "pesa mucho."))
            if color != "green":
                st.info(f"El veredicto de hoy es «{etiqueta}», no de compra. Si aun así compras, usa poco dinero.")
            bloque_operar(ticker, n, p, f_eur)

    st.subheader("🌦️ Qué le puede pasar a tu dinero")
    bloque_que_puede_pasar_accion(ticker, df, importe_ref)

    st.subheader("🏢 La empresa en números")
    bloque_fundamentales(ticker, fund)

    st.subheader("📰 Noticias de la empresa")
    if news:
        for n_ in news[:8]:
            tarjeta_noticia(n_)
    else:
        st.caption("No se han encontrado noticias recientes.")


def pagina_radar():
    if pagina_radar_global():
        return
    st.title("📡 Radar")
    st.info("El radar usa el informe diario, que todavía no se ha generado. Se crea solo cada día laborable al "
            "cierre de Wall Street (GitHub → Actions → «Actualización diaria»). Mientras tanto, usa 🔍 Analizar.")


def pagina_calculadoras():
    st.title("🧮 Calculadoras")
    t1, t2, t3 = st.tabs(["💶 Coste", "🏛️ Impuestos", "🌱 Cada mes"])
    with t1:
        st.caption("Cuánto te cuesta en Bankinter comprar, mantener un año y vender, según dónde cotice el valor.")
        importe = st.number_input("Importe que vas a invertir (€)", 50.0, 1_000_000.0, 1000.0, 50.0)
        tipos_valor = {"Acción española (IBEX, Mercado Continuo)": "SAN.MC",
                       "Acción europea en euros (Alemania, Países Bajos...)": "SAP.DE",
                       "Acción francesa (paga tasa Tobin del 0,4 %)": "MC.PA",
                       "Acción de EEUU (en dólares)": "AAPL"}
        tipo = st.radio("¿Qué vas a comprar?", list(tipos_valor))
        ref = tipos_valor[tipo]
        cc = costes.coste_compra(importe, ref, tarifa)
        iv = costes.coste_ida_y_vuelta(importe, ref, tarifa)
        c = st.columns(1 if movil else 3)
        c[0].metric("Al comprar", eur(cc["total"]), f"{cc['pct']:.2f} %".replace(".", ","), delta_color="off")
        c[1 % len(c)].metric("Al vender", eur(iv["venta"]))
        c[2 % len(c)].metric("Custodia (1 año)", eur(iv["custodia"]))
        detalle = [f"comisión {eur(cc['comision'])}"]
        if cc["cambio"]:
            detalle.append(f"cambio de divisa {eur(cc['cambio'])}")
        if cc["itf"]:
            detalle.append(f"tasa Tobin {eur(cc['itf'])}")
        st.caption("Compra: " + " + ".join(detalle) + ".")
        pct_total = f"{iv['pct']:.2f}".replace(".", ",")
        st.markdown(f"**En total, comprar, mantener un año y vender cuesta {eur(iv['total'])} ({pct_total} %)**: "
                    "la inversión tiene que subir al menos eso para que empieces a ganar.")
        if iv["pct"] > 2:
            st.warning("Es un coste alto para este importe. Con poco dinero, las acciones españolas o un fondo "
                       "indexado (sin comisión por aportación) salen mucho más baratos.")
    with t2:
        compra = st.number_input("Precio total de compra (€)", 0.0, 10_000_000.0, 1000.0, 50.0)
        venta = st.number_input("Precio total de venta (€)", 0.0, 10_000_000.0, 1300.0, 50.0)
        g = venta - compra
        imp = costes.impuesto_ganancia(g)
        c = st.columns(1 if movil else 3)
        c[0].metric("Ganancia", eur(g))
        c[1 % len(c)].metric("IRPF aproximado", eur(imp))
        c[2 % len(c)].metric("Te queda limpio", eur(g - imp))
        st.caption("Tramos del ahorro: 19% hasta 6.000 €, 21% hasta 50.000 €, 23% hasta 200.000 €, "
                   "27% hasta 300.000 €, 30% a partir de ahí. Las pérdidas se pueden compensar con ganancias "
                   "(durante 4 años). Ojo con la 'regla de los 2 meses': si vendes con pérdidas y recompras la "
                   "misma acción en menos de 2 meses, no puedes aplicar esa pérdida todavía. "
                   "Bankinter te envía el informe fiscal para la declaración.")
    with t3:
        st.write("Para la mayoría de personas, la forma más eficaz de hacer crecer el dinero es **aportar una "
                 "cantidad fija cada mes a un fondo indexado** mundial, sin intentar adivinar el mejor momento.")
        c = st.columns(2 if movil else 4)
        inicial = c[0].number_input("Dinero inicial (€)", 0.0, 1_000_000.0, 1000.0, 100.0)
        mensual = c[1].number_input("Aportación mensual (€)", 0.0, 10_000.0, 150.0, 10.0)
        anos = c[2 % len(c)].slider("Años", 1, 40, 15)
        rent = c[3 % len(c)].slider("Rentabilidad anual supuesta (%)", 0.0, 12.0, 7.0, 0.5,
                                    help="La bolsa mundial ha dado históricamente ~7% anual de media "
                                         "(con años de -40% y años de +30%). No está garantizado.")
        filas = costes.simular_aportaciones(mensual, anos, rent, inicial)
        tabla = pd.DataFrame(filas).set_index("Año")
        st.area_chart(tabla[["Aportado", "Ganancia"]], height=ALTO_GRAFICO - 150)
        f = filas[-1]
        st.success(f"Aportando {eur(mensual)} al mes durante {anos} años habrías puesto **{eur(f['Aportado'])}** "
                   f"y tendrías unos **{eur(f['Valor'])}**. El interés compuesto hace el resto.")


def pagina_aprende():
    st.title("🎓 Aprende: lo básico para invertir con cabeza")
    st.info(AVISO)
    st.markdown("""
### 1. Lo que funciona y lo que no (comprobado con datos reales)
- ❌ **Adivinar si una acción subirá el mes que viene.** Con 10 años de 130 empresas, ningún modelo lo hace mejor
  que lanzar una moneda. Desconfía de quien te lo prometa: por eso la app no te da «probabilidades de subir».
- ✅ **Estimar el riesgo de una caída fuerte.** Las acciones con riesgo «alto» cayeron más de un 10 % en un mes unas
  tres veces más a menudo que las de riesgo «bajo». La app lo usa para que evites sustos.
- ✅ **Carteras sencillas revisadas una vez al mes** (📦 Carteras modelo). En España, quedarse cada mes con las 8
  acciones que más subieron el último año ganó más que la media (2020-2026), con caídas parecidas a la bolsa.
- ✅ **Lo más rentable para casi todo el mundo**: aportar cada mes a un **fondo indexado** mundial, durante años,
  sin vender cuando la bolsa cae.

### 2. Tu plan en tres partes (🎯 Mi plan te dice cuánto en cada una)
1. **Colchón de emergencia** (3-6 meses de gastos) fuera de la bolsa.
2. **El núcleo: un fondo indexado mundial** con aportaciones mensuales.
3. **Una parte pequeña en acciones españolas** de la cartera modelo de tu perfil.

### 3. Cómo usar Bankinter con esta app
| Para… | En Bankinter | Por qué |
|---|---|---|
| Comprar una acción | Bróker → buscar el nombre → **Comprar** → orden **Limitada** | Nunca pagas más del precio que pones. |
| Limitar pérdidas | Orden **Stop** de venta: condición «menor o igual que» + **precio límite** | Bankinter exige precio límite; ponlo un 2 % por debajo para que se ejecute aunque caiga deprisa. |
| Pérdidas y objetivo a la vez | **Stop relacionadas** | Al ejecutarse una, Bankinter cancela la otra. |
| Que el stop suba solo | **Stop dinámica** | Sube con la cotización y no baja nunca. |
| Subir un stop | Cancelar la orden stop y crear otra | En Bankinter las órdenes stop no se modifican. |
| Aportar cada mes | **Fondos** → fondo indexado → aportaciones periódicas | Sin comisión por aportación (un ETF extranjero cuesta 20 € cada compra). |

**Lo que cuesta en Bankinter** (tarifa pública, octubre 2026; compruébala en Bróker → Tarifas):
- Acciones españolas: **3,95 €** hasta 2.000 € y **8 €** hasta 60.000 € por operación (**0 €** con Bróker Cero), más
  pequeños cánones de bolsa y la tasa Tobin (0,2 % al comprar empresas grandes).
- Acciones extranjeras: **20 €** por operación, **+1 %** si cotizan en otra divisa (dólares) y una **custodia mínima
  de 24 € al año por valor**. Por eso, con poco dinero, mejor acciones españolas y fondos indexados.

### 4. Cómo leer la app
- **Veredicto**: la conclusión para cada acción (Candidata a comprar, Neutral, Esperar…), la misma en toda la app.
- **Nota global (0-100)**: su puesto frente a las demás (100 = la mejor de hoy).
- **Riesgo de caída**: probabilidad de que caiga más de un 10 % en algún momento del próximo mes, frente a lo normal.
- **Stop-loss**: precio al que vender si sale mal, para que la pérdida sea pequeña.

### 5. Reglas de oro
1. **No inviertas dinero que vayas a necesitar** en los próximos 3-5 años.
2. **Diversifica**: un fondo indexado ya tiene miles de empresas; en acciones sueltas, sectores distintos.
3. **No arriesgues más del 1-2 % de tu dinero en una operación** (la app calcula cuántas acciones comprar).
4. **Pon siempre stop-loss** en acciones sueltas y no lo bajes nunca.
5. **No persigas** una acción que ha subido un 20 % en una semana.
6. **Las noticias llegan tarde**: cuando las lees, el precio ya se ha movido. Sirven para entender, no para correr.
7. **Las comisiones importan**: pocas operaciones y bien pensadas.
8. **Las emociones son tu mayor enemigo**: ten un plan y síguelo.

### 6. Diccionario rápido
| Término | Qué significa |
|---|---|
| **Fondo indexado** | Fondo que copia un índice (p. ej. MSCI World): miles de empresas con comisiones muy bajas. |
| **ETF** | Fondo que se compra y vende como una acción. En España tributa al venderlo (los fondos permiten traspasos sin impuestos). |
| **Momentum** | Las acciones que más han subido en el último año tienden a seguir haciéndolo algo mejor durante unos meses. |
| **Media de 200 sesiones** | Precio medio del último año: si el precio está por encima, la tendencia es alcista. |
| **RSI** | De 0 a 100: más de 70, ha subido muy deprisa; menos de 30, ha caído muy deprisa. |
| **Dividendo** | Parte del beneficio que la empresa reparte a sus accionistas. |
| **PER** | Cuántos años de beneficios pagas al comprar la acción. |
| **VIX** | El «índice del miedo» de Wall Street. |

### 7. Calendario que mueve los mercados
- Reuniones del **BCE** (cada ~6 semanas, jueves) y de la **Fed** (8 al año, miércoles por la tarde en España).
- **IPC** de EEUU (hacia mediados de mes) y **empleo** de EEUU (primer viernes de mes, 14:30 h).
- **Resultados de las empresas**: enero-febrero, abril-mayo, julio-agosto y octubre-noviembre.
- **Horario**: Bolsa española de 9:00 a 17:30; Wall Street de 15:30 a 22:00 (hora peninsular).
""")


PAGINAS = {
    "hoy": st.Page(pagina_hoy, title="Hoy", icon="🧭", default=True),
    "plan": st.Page(pagina_plan, title="Mi plan", icon="🎯"),
    "analizar": st.Page(pagina_analizar, title="Analizar", icon="🔍"),
    "radar": st.Page(pagina_radar, title="Radar", icon="📡"),
    "carteras": st.Page(pagina_carteras, title="Carteras modelo", icon="📦"),
    "noticias": st.Page(pagina_noticias, title="Noticias", icon="📰"),
    "mercados": st.Page(pagina_resumen, title="Mercados", icon="🌍"),
    "bankinter": st.Page(pagina_bankinter, title="Mi Bankinter", icon="🏦"),
    "virtual": st.Page(pagina_cartera_virtual, title="Cartera virtual", icon="🎮"),
    "simulador": st.Page(pagina_simulador, title="Simulador y modelos", icon="🧪"),
    "calculadoras": st.Page(pagina_calculadoras, title="Calculadoras", icon="🧮"),
    "aprende": st.Page(pagina_aprende, title="Aprende", icon="🎓"),
}
st.session_state["_paginas"] = PAGINAS
nav = st.navigation({
    "Inicio": [PAGINAS["hoy"], PAGINAS["plan"]],
    "Invertir": [PAGINAS["analizar"], PAGINAS["radar"], PAGINAS["carteras"], PAGINAS["noticias"],
                 PAGINAS["mercados"]],
    "Mis carteras": [PAGINAS["bankinter"], PAGINAS["virtual"]],
    "Aprender y probar": [PAGINAS["simulador"], PAGINAS["calculadoras"], PAGINAS["aprende"]],
}, position="top")
nav.run()
