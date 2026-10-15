"""Asistente de Bolsa para principiantes (pensado para operar con el broker de Bankinter).

Ejecutar:  streamlit run app.py
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from bolsa import costes, noticias, prediccion, senales
from bolsa.indicadores import calcular_todo
from bolsa.tickers import (IBEX35, INDICES, MERCADOS, TERMOMETROS, TODAS_LAS_ACCIONES, mercado_de, nombre_de,
                          sector_de)
from paginas_extra import acciones_rapidas, pagina_bankinter, pagina_cartera_virtual, pagina_simulador
from paginas_hoy import (bloque_fases, bloque_modelo_conjunto, bloque_que_puede_pasar_accion, pagina_hoy,
                         pagina_plan, pagina_radar_global)
from ui_comun import (Perfil, cargar_fundamentales, cargar_fundamentales_varios, cargar_historico,
                      cargar_informe, cargar_noticias, cargar_predicciones, cargar_varios, datos_usuario, es_movil,
                      estrategia_actual, eur, fila_informe, mercado_alcista_para, moneda_de, noticias_empresa, pct,
                      predicciones_radar)

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
    with st.expander("Comisiones Bankinter (ajústalas)"):
        st.caption("Valores orientativos. Consulta tu tarifa real en la app: Broker → Tarifas.")
        tarifa = costes.Tarifa(
            pct=st.number_input("Comisión (%)", 0.0, 2.0, 0.20, 0.01),
            minimo=st.number_input("Comisión mínima (€)", 0.0, 50.0, 6.0, 0.5),
            canon_fijo=st.number_input("Cánones fijos (€)", 0.0, 20.0, 1.0, 0.5),
        )
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


def grafico_prediccion(df: pd.DataFrame, preds: dict[str, prediccion.Prediccion]) -> go.Figure:
    """Abanico: precio de los últimos meses y rango probable a 1 semana, 1 mes y 3 meses."""
    c = df["Close"].tail(130)
    ultimo = c.index[-1]
    fechas = [ultimo] + [ultimo + pd.tseries.offsets.BDay(p.sesiones) for p in preds.values()]
    precio = float(c.iloc[-1])
    p10 = [precio] + [p.precio_p10 for p in preds.values()]
    p50 = [precio] + [p.precio_mediana for p in preds.values()]
    p90 = [precio] + [p.precio_p90 for p in preds.values()]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=c.index, y=c, name="Precio", line=dict(color="#334155")))
    fig.add_trace(go.Scatter(x=fechas, y=p90, line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=fechas, y=p10, fill="tonexty", fillcolor="rgba(99,102,241,0.18)",
                             line=dict(width=0), name="Rango probable (8 de cada 10 casos)"))
    fig.add_trace(go.Scatter(x=fechas, y=p50, name="Escenario central", line=dict(color="#6366f1", dash="dash"),
                             mode="lines+markers"))
    fig.update_layout(height=ALTO_GRAFICO - 80, margin=dict(l=5, r=5, t=30, b=5),
                      legend=dict(orientation="h", y=1.12))
    return fig


ICONO_FIAB = {"Alta": "🟢 Alta", "Media": "🟡 Media", "Baja": "🔴 Baja", "Sin datos": "⚪ Sin datos"}


def bloque_predicciones(ticker: str, df: pd.DataFrame, preds: dict[str, prediccion.Prediccion]):
    m = moneda_de(ticker)
    cols = st.columns(1 if movil else len(preds))
    for i, p in enumerate(preds.values()):
        with cols[0 if movil else i]:
            with st.container(border=True):
                st.markdown(f"**{p.horizonte}** · {p.direccion}")
                st.metric("Probabilidad de subir", f"{p.prob_subida * 100:.0f}%",
                          f"central {p.rent_mediana * 100:+.1f}%")
                st.caption(f"Rango probable: {eur(p.precio_p10, m)} – {eur(p.precio_p90, m)}")
                if p.acierto is not None:
                    st.caption(f"Fiabilidad: **{ICONO_FIAB[p.fiabilidad]}** · acertó {p.acierto * 100:.0f}% "
                               f"(azar: {p.acierto_referencia * 100:.0f}%)")
                if p.fiabilidad in ("Baja", "Sin datos"):
                    st.caption("⚠️ No fiable para esta acción: tómalo solo como referencia.")
    st.plotly_chart(grafico_prediccion(df, preds), width="stretch")
    with st.expander("¿Cómo se calcula y cuánto me puedo fiar?"):
        for p in preds.values():
            st.markdown(f"**{p.horizonte}:** {prediccion.explicar(p)}")
            if p.acierto_seguro is not None and p.n_seguro >= 10:
                st.caption(f"Cuando el modelo estaba muy seguro (más de 65% o menos de 35%) acertó el "
                           f"{p.acierto_seguro * 100:.0f}% de {p.n_seguro} veces.")
        st.info("Un acierto del 55-60% ya es bueno en bolsa: los mejores fondos del mundo viven de pequeñas "
                "ventajas repetidas muchas veces, con riesgo controlado. **Nadie** acierta el 90%. "
                "Por eso la predicción solo suma puntos cuando ha demostrado acertar más que el azar, y "
                "siempre debes usar stop-loss.")


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


def bloque_bankinter(ticker: str, ev: senales.Evaluacion, n_acciones: int):
    nombre = nombre_de(ticker)
    mercado = "Mercado Continuo (España)" if ticker.endswith(".MC") else "el mercado de EEUU / internacional"
    m = moneda_de(ticker)
    pasos = [
        "Abre la app de **Bankinter** → menú **Broker** (o 'Bolsa').",
        f"Pulsa en buscar y escribe **{nombre}** (cotiza en {mercado}).",
        "Pulsa **Comprar**.",
        f"Tipo de orden: **Limitada**, con precio límite **{eur(ev.precio, m)}** o ligeramente inferior. "
        "La orden limitada asegura que nunca pagas más de ese precio (la 'a mercado' compra al precio "
        "que haya, y puede sorprenderte).",
        f"Número de títulos: **{n_acciones}**.",
        "Validez: 'hasta fin de semana' o la fecha que quieras. Si el precio no baja a tu límite, no se ejecuta y no pasa nada.",
    ]
    if ev.plan:
        pasos.append(f"Cuando se ejecute, crea una orden de **venta stop (stop-loss)** a **{eur(ev.plan.stop, m)}**. "
                     "Si la acción cae hasta ahí, se vende sola y limitas la pérdida. "
                     "Es tu cinturón de seguridad: no lo quites ni lo bajes.")
        pasos.append(f"Opcional: orden de venta limitada en el objetivo **{eur(ev.plan.objetivo, m)}** "
                     "o, mejor, ve subiendo el stop-loss a medida que la acción suba.")
    if not ticker.endswith(".MC"):
        pasos.append("En acciones de EEUU pagas en dólares: Bankinter cambia la divisa y cobra por ello. "
                     "Si el dólar baja frente al euro, pierdes algo aunque la acción no se mueva.")
    for i, p in enumerate(pasos, 1):
        st.markdown(f"{i}. {p}")


# --------------------------------------------------------------------------- páginas
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

    st.subheader("🔮 Previsión de los índices a 1 mes")
    cols = st.columns(1 if movil else 2)
    for i, t in enumerate(("^IBEX", "^GSPC")):
        p = cargar_predicciones(t).get("1 mes")
        with cols[i % len(cols)].container(border=True):
            if not p:
                st.caption(f"{nombre_de(t)}: sin datos suficientes.")
                continue
            st.markdown(f"**{nombre_de(t)}** · {p.direccion}")
            st.metric("Probabilidad de subir en 1 mes", f"{p.prob_subida * 100:.0f}%",
                      f"central {p.rent_mediana * 100:+.1f}%")
            st.caption(f"Rango probable {p.precio_p10:,.0f} – {p.precio_p90:,.0f}".replace(",", ".")
                       + (f" · Fiabilidad {ICONO_FIAB[p.fiabilidad]} (acertó {p.acierto * 100:.0f}%)"
                          if p.acierto is not None else ""))

    st.subheader("📰 Las 5 noticias más influyentes ahora")
    for n in lista[:5]:
        tarjeta_noticia(n)

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
    st.caption("Revisa tendencia, si está cara o barata, impulso, datos de la empresa, opinión de los analistas, "
               "noticias y un modelo estadístico de predicción, y te lo explica en lenguaje claro.")

    pre = st.session_state.pop("analizar_ticker", None)
    if pre in TODAS_LAS_ACCIONES:
        st.session_state["an_mercado"] = mercado_de(pre)
        st.session_state["an_empresa"] = pre
    c1, c2 = st.columns([1, 2])
    grupo = c1.selectbox("Mercado", list(MERCADOS), key="an_mercado")
    opciones = list(MERCADOS[grupo])
    if st.session_state.get("an_empresa") not in opciones:
        st.session_state.pop("an_empresa", None)
    ticker = c2.selectbox("Empresa", opciones, key="an_empresa", format_func=lambda t: f"{nombre_de(t)} ({t})")
    otro = st.text_input("…u otro ticker de Yahoo Finance (ej. KO, SAP.DE, 7203.T)", "").strip().upper()
    if otro:
        ticker = otro

    with st.spinner(f"Analizando {nombre_de(ticker)}: cotizaciones, empresa, noticias y modelo..."):
        df = cargar_historico(ticker, "10y")
        if df.empty or len(df) < 30:
            st.error("No hay datos suficientes para ese ticker. Comprueba que está bien escrito.")
            return
        with ThreadPoolExecutor(max_workers=3) as pool:
            f_fund = pool.submit(cargar_fundamentales, ticker)
            f_news = pool.submit(noticias_empresa, ticker)
            f_pred = pool.submit(cargar_predicciones, ticker)
            fund, news, preds = f_fund.result(), f_news.result(), f_pred.result()
        recientes = [n for n in news if n.horas is None or n.horas < 24 * 7]
        estrategia = estrategia_actual()
        ev = senales.evaluar(ticker, df,
                             sentimiento_noticias=noticias.sentimiento_medio(recientes) if recientes else None,
                             n_noticias=len(recientes), mercado_alcista=mercado_alcista_para(ticker),
                             fundamentales=fund, prediccion=preds.get("1 mes"),
                             stop_atr=estrategia.stop_atr, ratio_objetivo=estrategia.ratio_objetivo)

    m = moneda_de(ticker)
    titulo = nombre_de(ticker) if ticker in TODAS_LAS_ACCIONES else fund.get("longName", ticker)
    st.header(f"{titulo}  ·  {eur(ev.precio, m)}")
    st.caption(f"Sector: {sector_de(ticker)} · Hoy {pct(ev.datos['var_1d'])} · 1 mes {pct(ev.datos['var_1m'], 1)} "
               f"· 1 año {pct(ev.datos['var_1a'], 1)}")

    c1, c2 = st.columns([1, 2])
    with c1:
        st.metric("Puntuación del asistente", f"{ev.puntuacion}/100")
        st.progress(ev.puntuacion / 100)
        st.markdown(f"### :{ev.color}[{ev.veredicto}]")
        st.write(ev.resumen)
        if "estrategia" in datos_usuario():
            st.caption(f"🏋️ Tu estrategia entrenada compra a partir de **{estrategia.umbral_compra}** puntos "
                       f"y vende por debajo de **{estrategia.umbral_venta}**.")
    with c2:
        st.plotly_chart(grafico(df, "Último año: velas, medias móviles y RSI", ev.plan), width="stretch")
        st.caption("Cada vela es un día: verde si cerró por encima de lo que abrió, roja si por debajo. "
                   "Naranja = media de 50 sesiones (≈3 meses). Morada = media de 200 sesiones (≈1 año). "
                   "Abajo, el RSI: zona roja = sobrecomprada, zona verde = sobrevendida.")

    for a in ev.avisos:
        st.warning(a)

    st.subheader("🔮 Predicción")
    bloque_modelo_conjunto(ticker, fila_informe(ticker))
    if preds:
        bloque_predicciones(ticker, df, preds)
    else:
        st.caption("Se necesitan al menos 2-3 años de historial para hacer predicciones.")

    st.subheader("🧠 Por qué dice esto (explicado paso a paso)")
    for mo in sorted(ev.motivos, key=lambda x: -abs(x.puntos)):
        with st.expander(f"{mo.icono} {mo.titulo}  ({mo.puntos:+d})"):
            st.write(mo.explicacion)

    if ev.plan:
        st.subheader("📋 Tu plan de operación")
        p = ev.plan
        n_riesgo = costes.tamano_por_riesgo(capital, riesgo, p.entrada, p.stop)
        importe = n_riesgo * p.entrada
        cc = costes.coste_compra(importe, ticker, tarifa)
        c = st.columns(2 if movil else 4)
        c[0].metric("Precio de compra", eur(p.entrada, m))
        c[1].metric("Stop-loss (salida si falla)", eur(p.stop, m), f"-{p.riesgo_pct:.1f}%", delta_color="off")
        c[2 % len(c)].metric("Objetivo", eur(p.objetivo, m), f"+{p.beneficio_pct:.1f}%")
        c[3 % len(c)].metric("Acciones a comprar", n_riesgo, help="Calculado para que, si salta el stop-loss, "
                             f"pierdas como mucho el {riesgo}% de tu dinero.")
        st.markdown(
            f"Con **{eur(capital)}** y un riesgo máximo del **{riesgo}%** ({eur(capital * riesgo / 100)}), "
            f"comprarías **{n_riesgo} acciones** por unos **{eur(importe, m)}**. "
            f"Si sale mal y salta el stop, perderías unos **{eur(n_riesgo * (p.entrada - p.stop), m)}**. "
            f"Si llega al objetivo, ganarías unos **{eur(n_riesgo * (p.objetivo - p.entrada), m)}** (antes de impuestos). "
            f"Comisiones e impuestos de compra estimados: **{eur(cc['total'])}** ({cc['pct']:.2f}%).")
        ratio = estrategia.ratio_objetivo or 2.0
        st.caption(f"El stop-loss se coloca a {estrategia.stop_atr:g} veces el movimiento diario típico (ATR) por "
                   f"debajo del precio, y el objetivo a {ratio:g} veces esa distancia: ganas {ratio:g} € por cada "
                   f"1 € que arriesgas. Así, aunque aciertes solo {100 / (1 + ratio):.0f} de cada 100 veces, "
                   "a la larga no pierdes (sin contar comisiones).")
        if estrategia.ratio_objetivo == 0:
            st.caption("🏋️ Tu estrategia entrenada prefiere **no fijar objetivo**: deja correr las ganancias y "
                       "ve subiendo el stop-loss a medida que la acción sube.")
        if importe and cc["pct"] > 1:
            st.warning("Las comisiones se comen más del 1% de la compra. Con importes pequeños el mínimo de "
                       "comisión pesa mucho: mejor juntar más dinero y hacer menos operaciones.")
        if ev.puntuacion < 55:
            st.info("Con la puntuación actual el asistente **no recomienda entrar todavía**. "
                    "Guarda este plan y vuelve a revisarlo en unos días.")
        with st.expander("📱 Cómo hacerlo en la app de Bankinter"):
            bloque_bankinter(ticker, ev, n_riesgo)
        acciones_rapidas(ticker, ev, n_riesgo)

    st.subheader("🌦️ Qué le puede pasar a tu dinero")
    importe_ref = (costes.tamano_por_riesgo(capital, riesgo, ev.plan.entrada, ev.plan.stop) * ev.precio
                   if ev.plan else 0) or 1_000.0
    bloque_que_puede_pasar_accion(ticker, df, importe_ref)

    st.subheader("🏢 La empresa en números")
    bloque_fundamentales(ticker, fund)

    st.subheader(f"📰 Noticias de la empresa ({len(news)})")
    if news:
        for n in news[:12]:
            tarjeta_noticia(n)
    else:
        st.caption("No se han encontrado noticias recientes.")

    with st.expander("🧪 ¿Funciona seguir la tendencia? Prueba con el pasado (10 años)"):
        bt = senales.backtest_media200(df, tarifa.pct)
        if bt:
            curvas = pd.DataFrame({"Comprar y mantener": bt["curva_mantener"],
                                   "Solo por encima de la media 200": bt["curva_estrategia"]})
            st.line_chart(curvas, height=ALTO_GRAFICO - 150)
            c = st.columns(2)
            c[0].metric("Comprar y mantener", pct(bt["rent_mantener"], 0), f"peor caída {bt['caida_mantener']:.0f}%",
                        delta_color="off")
            c[1].metric("Regla de la media 200", pct(bt["rent_estrategia"], 0),
                        f"peor caída {bt['caida_estrategia']:.0f}% · {bt['operaciones']} operaciones", delta_color="off")
            st.caption("Normalmente la regla de la media de 200 no gana más que 'comprar y mantener', "
                       "pero **evita gran parte de las caídas fuertes**, que es lo que hace que los principiantes "
                       "vendan en el peor momento. Rentabilidades pasadas no garantizan las futuras.")
        else:
            st.caption("No hay historial suficiente.")


def pagina_radar():
    if pagina_radar_global():
        return
    st.title("📡 Radar del IBEX 35")
    st.caption("Analiza las 35 empresas a la vez (tendencia, impulso, noticias, analistas y modelo estadístico) "
               "y las ordena por puntuación. Úsalo para encontrar candidatas y luego estúdialas en '🔍 Analizar'.")
    con_analistas = st.toggle("Incluir datos de empresa y analistas (más lento la primera vez)", value=True)
    with st.spinner("Analizando las 35 empresas (la primera vez puede tardar 30-60 segundos)..."):
        tickers = tuple(IBEX35)
        hist = cargar_varios(tickers, "10y")
        ibex = cargar_historico("^IBEX")
        alcista = senales.estado_indice(ibex)["alcista"] if not ibex.empty else None
        lista, _ = cargar_noticias()
        preds = predicciones_radar(tickers)
        funds = cargar_fundamentales_varios(tickers) if con_analistas else {}
    if not hist:
        st.error("No se han podido descargar cotizaciones.")
        return
    filas = []
    for t, df in hist.items():
        if len(df) < 60:
            continue
        rel = [n for n in lista if t in n.empresas]
        p = preds.get(t)
        ev = senales.evaluar(t, df, noticias.sentimiento_medio(rel) if rel else None, len(rel), alcista,
                             fundamentales=funds.get(t), prediccion=p)
        objetivo = (funds.get(t) or {}).get("targetMeanPrice")
        filas.append({
            "Empresa": nombre_de(t), "Puntuación": ev.puntuacion, "Veredicto": ev.veredicto,
            # Si el modelo no ha demostrado acertar con esta empresa, no mostramos su probabilidad.
            "Prob. subir 1 mes": round(p.prob_subida * 100) if p and p.fiabilidad in ("Alta", "Media") else None,
            "Fiabilidad modelo": ICONO_FIAB[p.fiabilidad] if p else "—",
            "Precio €": round(ev.precio, 2), "Hoy %": round(ev.datos["var_1d"], 2),
            "1 mes %": round(ev.datos["var_1m"], 1),
            "1 año %": round(ev.datos["var_1a"], 1) if not pd.isna(ev.datos["var_1a"]) else None,
            "Potencial analistas %": round((objetivo / ev.precio - 1) * 100, 1) if objetivo else None,
            "RSI": round(ev.datos["rsi"]) if ev.datos["rsi"] else None,
            "Noticias": len(rel), "Sector": sector_de(t), "Ticker": t,
        })
    tabla = pd.DataFrame(filas).sort_values("Puntuación", ascending=False)
    if movil:
        tabla = tabla[["Empresa", "Puntuación", "Prob. subir 1 mes", "Hoy %"]]
    st.dataframe(tabla, hide_index=True, width="stretch", height=35 * len(tabla) + 40,
                 column_config={
                     "Puntuación": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d"),
                     "Prob. subir 1 mes": st.column_config.NumberColumn(format="%d%%"),
                 })
    top = tabla[tabla["Puntuación"] >= 70]
    if len(top):
        st.success("En zona de compra según el asistente: " + ", ".join(top["Empresa"]) +
                   ". Recuerda: diversifica (no más de un 10-20% de tu dinero en una sola empresa) "
                   "y no concentres todo en un mismo sector.")
    else:
        st.info("Ahora mismo ninguna empresa supera 70 puntos. No pasa nada: no invertir también es una decisión.")
    examinadas = [p for p in preds.values() if p.acierto is not None]
    if examinadas:
        medio = sum(p.acierto for p in examinadas) / len(examinadas) * 100
        ref = sum(p.acierto_referencia for p in examinadas) / len(examinadas) * 100
        st.caption(f"Acierto medio del modelo a 1 mes en el IBEX 35, examinado con datos pasados: **{medio:.0f}%** "
                   f"(decir siempre lo mismo: {ref:.0f}%). Fíate más de las empresas con fiabilidad 🟢.")


def pagina_calculadoras():
    st.title("🧮 Calculadoras")
    t1, t2, t3 = st.tabs(["💶 Coste", "🏛️ Impuestos", "🌱 Cada mes"])
    with t1:
        importe = st.number_input("Importe que vas a invertir (€)", 50.0, 1_000_000.0, 1000.0, 50.0)
        espanola = st.checkbox("Es una acción española del IBEX (paga el Impuesto de Transacciones Financieras)", True)
        cc = costes.coste_compra(importe, "X.MC" if espanola else "X", tarifa)
        c = st.columns(1 if movil else 3)
        c[0].metric("Comisión broker + cánones", eur(cc["comision"]))
        c[1 % len(c)].metric("Impuesto Transacciones (0,2%)", eur(cc["itf"]))
        c[2 % len(c)].metric("Total", eur(cc["total"]), f"{cc['pct']:.2f}% del importe", delta_color="off")
        st.caption(f"Al vender pagarás de nuevo la comisión (≈{eur(tarifa.coste(importe))}). "
                   f"Para cubrir compra y venta la acción tiene que subir al menos un "
                   f"{(cc['total'] + tarifa.coste(importe)) / importe * 100:.2f}% antes de que ganes algo.")
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
                 "cantidad fija cada mes a un fondo indexado o ETF** (por ejemplo, del MSCI World o del S&P 500), "
                 "sin intentar adivinar el mejor momento.")
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
### 1. La verdad incómoda primero
- **Nadie predice la bolsa con precisión**: ni los bancos, ni los fondos, ni ningún programa. Si alguien te
  promete aciertos del 90%, te está engañando. En bolsa, acertar el **55-60%** de las veces con el riesgo
  controlado ya es excelente.
- Por eso este asistente **mide su propio acierto** con datos pasados y te lo enseña. Úsalo para **evitar
  malos momentos** y **tener un plan**, no como una bola de cristal.
- La "mayor rentabilidad" a largo plazo la consigue quien **está mucho tiempo invertido, diversifica,
  paga pocas comisiones y no vende por pánico**.
- Estrategia sensata para empezar:
  - **70-80%** de lo que inviertas: aportaciones mensuales a un **ETF o fondo indexado** mundial o del S&P 500.
  - **20-30%**: acciones individuales elegidas con este asistente, para aprender y buscar algo extra.
  - Antes, un **colchón de emergencia** (3-6 meses de gastos) fuera de la bolsa.

### 2. Cómo leer la predicción 🔮
- **Probabilidad de subir**: de las situaciones del pasado más parecidas a la de hoy, en cuántas subió.
  60% no significa que vaya a subir: significa que de cada 10 veces así, unas 6 subió y 4 bajó.
- **Rango probable**: entre qué precios quedó en 8 de cada 10 casos parecidos.
- **Fiabilidad**: 🟢 Alta / 🟡 Media si en el examen con el pasado acertó claramente más que el azar;
  🔴 Baja si no. **Con fiabilidad baja, ignora la predicción.**

### 3. Cómo usar este asistente
**Antes de arriesgar dinero real (una vez):**
1. **🧪 Simulador → Entrenar**: la app prueba muchas combinaciones de reglas con 10 años de datos y te dice,
   en años que no ha visto, si habría ganado dinero frente a simplemente comprar y mantener.
2. **🎮 Cartera virtual**: crea el **robot** y practica tú también con dinero ficticio durante unas semanas.

**Rutina (5-10 minutos):**
1. **🧭 Hoy**: semáforo, resumen en pocas palabras, ideas del día, qué puede pasar y avisos de tu cartera.
   Se actualiza solo cada día laborable con los datos del cierre.
2. **📰 Noticias**: lee las 3-5 más influyentes y su "por qué importa".
3. **📡 Radar**: busca empresas con puntuación alta (≥ 70) y fiabilidad 🟢/🟡.
4. **🔍 Analizar**: entra en la candidata, lee motivos, predicción, analistas y el plan.
5. **Bankinter**: copia la **orden lista** que te prepara la app (orden limitada + stop-loss).
6. **🏦 Mi Bankinter**: registra la compra. La app la vigilará y te dirá cuándo subir el stop o vender.

### 3 bis. ¿De dónde salen las recomendaciones?
- Cada noche un proceso automático descarga 10 años de datos de **unas 130 empresas** (España, Europa y EEUU),
  los grandes índices mundiales (algunos con casi 100 años de historia) y cientos de noticias.
- Reentrena los modelos **sin mirar el futuro** y los examina con años que no han visto. Si un modelo no supera
  al azar, la app lo marca como poco fiable y **no lo usa** para recomendarte nada.
- Guarda cada idea del día y, un mes después, comprueba si acertó: en **🧪 Simulador y modelos** puedes ver
  ese historial real, que es la prueba más honesta de todas.
- **🎯 Mi plan** te dice dónde invertir según tu perfil: la mayor parte en fondos indexados (lo que mejor
  funciona para casi todo el mundo) y una parte pequeña en acciones individuales diversificadas.

### 4. Diccionario rápido
| Término | Qué significa |
|---|---|
| **Acción** | Un trocito de una empresa. Si a la empresa le va bien, suele subir de precio y/o pagar dividendos. |
| **Índice (IBEX 35, S&P 500)** | Una cesta con las principales empresas de una bolsa. Sirve de termómetro. |
| **ETF** | Un fondo que se compra como una acción y replica un índice: con una compra tienes cientos de empresas. |
| **Dividendo** | Parte del beneficio que la empresa reparte entre sus accionistas. |
| **PER** | Precio / beneficio: cuántos años de beneficios pagas al comprar. |
| **Precio objetivo** | Precio al que los analistas creen que llegará la acción en 12 meses. |
| **Media móvil (50 / 200)** | El precio medio de las últimas 50 o 200 sesiones. Muestra la tendencia. |
| **RSI** | Indicador de 0 a 100. >70: ha subido demasiado rápido. <30: ha caído demasiado rápido. |
| **MACD** | Indicador de impulso: dice si el precio está acelerando al alza o a la baja. |
| **ATR** | Lo que se mueve una acción en un día normal. Sirve para colocar el stop-loss. |
| **Orden limitada** | Compras/vendes solo si el precio llega al que tú fijas. **Úsala siempre.** |
| **Stop-loss** | Orden que vende automáticamente si el precio cae hasta un nivel. Limita las pérdidas. |
| **Volatilidad** | Cuánto sube y baja el precio. Más volatilidad = más riesgo. |
| **OPA** | Oferta de una empresa para comprar otra. |
| **VIX** | El "índice del miedo" de Wall Street. |

### 5. Reglas de oro
1. **No inviertas dinero que vayas a necesitar** en los próximos 3-5 años.
2. **Diversifica**: varias empresas de distintos sectores, o directamente un ETF.
3. **No arriesgues más del 1-2% de tu capital en una operación** (el asistente calcula cuántas acciones comprar).
4. **Pon siempre stop-loss** en acciones individuales, y no lo muevas hacia abajo.
5. **Compra en varias veces** en lugar de todo de golpe.
6. **No persigas** una acción que ha subido un 20% en una semana.
7. **Las noticias ya están en el precio** muy rápido: úsalas para entender el contexto, no para comprar con prisa.
8. **Controla las comisiones**: operar mucho con poco dinero hace que el broker gane más que tú.
9. **Las emociones son tu mayor enemigo**: ten un plan y síguelo.

### 6. Calendario que mueve los mercados
- **Reuniones del BCE** (cada ~6 semanas, jueves) y de la **Fed** (8 al año, miércoles por la tarde en España).
- **IPC / inflación** (EEUU: hacia mediados de mes) y **empleo de EEUU** (primer viernes de mes, 14:30 h).
- **Temporada de resultados**: enero-febrero, abril-mayo, julio-agosto y octubre-noviembre.
- **Horario de la Bolsa española**: 9:00 a 17:30. **Wall Street**: 15:30 a 22:00 (hora España).

### 7. Tenerla en el móvil 📱
Abre el enlace de la app en el navegador del móvil y usa **"Añadir a pantalla de inicio"**
(Safari: botón compartir; Chrome: menú ⋮). Quedará como un icono más, junto a la app de Bankinter.
""")


PAGINAS = {
    "hoy": st.Page(pagina_hoy, title="Hoy", icon="🧭", default=True),
    "plan": st.Page(pagina_plan, title="Mi plan", icon="🎯"),
    "analizar": st.Page(pagina_analizar, title="Analizar", icon="🔍"),
    "radar": st.Page(pagina_radar, title="Radar", icon="📡"),
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
    "Invertir": [PAGINAS["analizar"], PAGINAS["radar"], PAGINAS["noticias"], PAGINAS["mercados"]],
    "Mis carteras": [PAGINAS["bankinter"], PAGINAS["virtual"]],
    "Aprender y probar": [PAGINAS["simulador"], PAGINAS["calculadoras"], PAGINAS["aprende"]],
}, position="top")
nav.run()
