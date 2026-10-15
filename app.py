"""Asistente de Bolsa para principiantes (pensado para operar con el broker de Bankinter).

Ejecutar:  streamlit run app.py
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from bolsa import costes, datos, noticias, senales
from bolsa.indicadores import calcular_todo
from bolsa.tickers import EEUU, ETFS, IBEX35, INDICES, TERMOMETROS, TODAS_LAS_ACCIONES, nombre_de, sector_de

st.set_page_config(page_title="Asistente de Bolsa", page_icon="📈", layout="wide")

AVISO = ("⚠️ **Herramienta educativa, no es asesoramiento financiero.** Ningún sistema puede "
         "garantizar beneficios: invierte solo dinero que no vayas a necesitar en años y que "
         "puedas permitirte ver bajar un 30% sin vender por miedo.")


# --------------------------------------------------------------------------- caché de datos
@st.cache_data(ttl=600, show_spinner=False)
def cargar_historico(ticker: str, periodo: str = "2y") -> pd.DataFrame:
    return datos.historico(ticker, periodo)


@st.cache_data(ttl=600, show_spinner=False)
def cargar_varios(tickers: tuple[str, ...], periodo: str = "2y") -> dict[str, pd.DataFrame]:
    return datos.varios(list(tickers), periodo)


@st.cache_data(ttl=300, show_spinner=False)
def cargar_noticias() -> tuple[list[noticias.Noticia], list[str]]:
    return noticias.descargar()


@st.cache_data(ttl=900, show_spinner=False)
def noticias_empresa(ticker: str) -> list[noticias.Noticia]:
    nombre = TODAS_LAS_ACCIONES[ticker][0].split(" (")[0]
    consulta = f'"{nombre}" acciones' if ticker.endswith(".MC") else f'"{nombre}" bolsa'
    lista, _ = noticias.descargar({"Google News": noticias.url_google_news(consulta)}, max_por_fuente=15)
    return lista


def mercado_alcista_para(ticker: str) -> bool | None:
    indice = "^IBEX" if ticker.endswith(".MC") else "^GSPC"
    h = cargar_historico(indice)
    return senales.estado_indice(h)["alcista"] if not h.empty else None


def pct(x: float | None, dec: int = 2) -> str:
    if x is None or pd.isna(x):
        return "—"
    return f"{x:+.{dec}f}%"


def eur(x: float, moneda: str = "€") -> str:
    return f"{x:,.2f} {moneda}".replace(",", "X").replace(".", ",").replace("X", ".")


def moneda_de(ticker: str) -> str:
    return "€" if ticker.endswith((".MC", ".AS")) else "$"


# --------------------------------------------------------------------------- barra lateral
with st.sidebar:
    st.title("📈 Asistente de Bolsa")
    pagina = st.radio("Ir a", [
        "🏠 Resumen del día",
        "📰 Noticias que mueven el mercado",
        "🔍 Analizar una acción",
        "📡 Radar del IBEX 35",
        "🧮 Calculadoras",
        "🎓 Aprende (empieza aquí)",
    ])
    st.divider()
    st.subheader("Tu perfil")
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
    st.caption("Cotizaciones de Yahoo Finance (retraso ~15 min). Noticias de RSS públicos. "
               "Se actualizan solas cada 5-10 minutos.")
    if st.button("🔄 Actualizar ahora"):
        st.cache_data.clear()
        st.rerun()


# --------------------------------------------------------------------------- componentes
def tarjeta_noticia(n: noticias.Noticia, expandida: bool = False):
    estrellas = "🔥" * max(1, round(n.impacto / 2)) if n.impacto >= 4 else "·"
    empresas = ", ".join(nombre_de(t) for t in n.empresas)
    cabecera = f"{n.etiqueta_sentimiento} · {estrellas} · {n.titulo}"
    with st.expander(cabecera, expanded=expandida):
        st.markdown(f"**[{n.titulo}]({n.enlace})**")
        st.caption(f"{n.fuente} · {noticias.hace_cuanto(n)} · Impacto {n.impacto}/10"
                   + (f" · Empresas: {empresas}" if empresas else ""))
        if n.resumen and n.resumen.lower() not in n.titulo.lower():
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
        fig.add_trace(go.Scatter(x=d.index, y=d[col], name=f"Media {col[3:]} sesiones",
                                 line=dict(color=color, width=1.6)), row=1, col=1)
    if plan:
        for y, txt, color in ((plan.stop, "Stop-loss", "#dc2626"), (plan.objetivo, "Objetivo", "#16a34a")):
            fig.add_hline(y=y, line_dash="dash", line_color=color, annotation_text=txt, row=1, col=1)
    fig.add_trace(go.Scatter(x=d.index, y=d["RSI"], name="RSI", line=dict(color="#0ea5e9")), row=2, col=1)
    fig.add_hrect(y0=70, y1=100, fillcolor="#dc2626", opacity=0.08, line_width=0, row=2, col=1)
    fig.add_hrect(y0=0, y1=30, fillcolor="#16a34a", opacity=0.08, line_width=0, row=2, col=1)
    fig.update_yaxes(range=[0, 100], row=2, col=1, title_text="RSI")
    fig.update_layout(title=titulo, height=560, xaxis_rangeslider_visible=False,
                      legend=dict(orientation="h", y=1.08), margin=dict(l=10, r=10, t=60, b=10))
    return fig


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
    st.title("🏠 Resumen del día")
    st.info(AVISO)

    with st.spinner("Descargando cotizaciones..."):
        hist = cargar_varios(tuple(list(INDICES) + list(TERMOMETROS)))
    if not hist:
        st.error("No se han podido descargar cotizaciones. Revisa tu conexión a Internet y pulsa 'Actualizar'.")
        return

    st.subheader("Los grandes índices")
    st.caption("Un índice es una 'cesta' con las principales empresas de una bolsa. Si sube, la mayoría de "
               "acciones suben. Las flechas 🟢/🔴 indican si están por encima o por debajo de su media de 200 "
               "sesiones (≈1 año), la forma más simple de saber si el mercado está en tendencia alcista.")
    cols = st.columns(len(INDICES))
    alcistas = 0
    for col, (t, info) in zip(cols, INDICES.items()):
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
            col.caption(info["que_es"])

    with st.spinner("Leyendo noticias..."):
        lista, _ = cargar_noticias()
    sent = noticias.sentimiento_medio([n for n in lista if n.impacto >= 4][:30])

    # Semáforo general
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
    st.caption(f"Tono de las noticias importantes de hoy: **{tono}** ({sent:+.2f} en escala -1 a +1)."
               + (f" VIX: {vix:.1f}." if vix else ""))

    st.subheader("📰 Las 5 noticias más influyentes ahora")
    for n in lista[:5]:
        tarjeta_noticia(n)


def pagina_noticias():
    st.title("📰 Noticias que mueven el mercado")
    st.caption("Se ordenan por **impacto estimado** (0-10): temas que históricamente mueven las bolsas "
               "(tipos de interés, inflación, aranceles, resultados, OPAs...) y lo recientes que son. "
               "Despliega cada una para ver **por qué importa**.")
    with st.spinner("Leyendo fuentes..."):
        lista, fallos = cargar_noticias()
    if fallos:
        st.caption(f"Fuentes no disponibles ahora: {', '.join(fallos)}")
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

    # Empresas más mencionadas
    menciones: dict[str, list[int]] = {}
    for n in lista:
        for t in n.empresas:
            menciones.setdefault(t, []).append(n.sentimiento)
    if menciones:
        with st.expander("🏢 Empresas más mencionadas hoy"):
            filas = [{"Empresa": nombre_de(t), "Ticker": t, "Noticias": len(s),
                      "Tono medio": round(sum(s) / len(s), 2)} for t, s in menciones.items()]
            st.dataframe(pd.DataFrame(filas).sort_values("Noticias", ascending=False),
                         hide_index=True, width="stretch")
            st.caption("Que una empresa salga mucho en las noticias no significa que haya que comprarla. "
                       "Analízala en '🔍 Analizar una acción'.")

    for i, n in enumerate(filtradas[:60]):
        tarjeta_noticia(n, expandida=i < 3)


def pagina_analizar():
    st.title("🔍 Analizar una acción")
    st.caption("Elige una empresa y el asistente revisa su tendencia, si está cara o barata a corto plazo, "
               "su impulso y las noticias, y te dice en lenguaje claro si es buen momento.")

    grupos = {"IBEX 35 (España)": IBEX35, "EEUU": EEUU, "ETF (fondos indexados)": ETFS}
    c1, c2 = st.columns([1, 2])
    grupo = c1.selectbox("Mercado", list(grupos))
    ticker = c2.selectbox("Empresa", list(grupos[grupo]), format_func=lambda t: f"{nombre_de(t)} ({t})")
    otro = st.text_input("…u otro ticker de Yahoo Finance (ej. ITX.MC, ASML.AS, KO)", "").strip().upper()
    if otro:
        ticker = otro

    with st.spinner(f"Analizando {nombre_de(ticker)}..."):
        df = cargar_historico(ticker)
        if df.empty or len(df) < 30:
            st.error("No hay datos suficientes para ese ticker. Comprueba que está bien escrito.")
            return
        news = noticias_empresa(ticker) if ticker in TODAS_LAS_ACCIONES else []
        recientes = [n for n in news if n.horas is None or n.horas < 24 * 7]
        ev = senales.evaluar(ticker, df,
                             sentimiento_noticias=noticias.sentimiento_medio(recientes) if recientes else None,
                             n_noticias=len(recientes), mercado_alcista=mercado_alcista_para(ticker))

    m = moneda_de(ticker)
    st.header(f"{nombre_de(ticker)}  ·  {eur(ev.precio, m)}")
    st.caption(f"Sector: {sector_de(ticker)} · Hoy {pct(ev.datos['var_1d'])} · 1 mes {pct(ev.datos['var_1m'], 1)} "
               f"· 1 año {pct(ev.datos['var_1a'], 1)}")

    c1, c2 = st.columns([1, 2])
    with c1:
        st.metric("Puntuación del asistente", f"{ev.puntuacion}/100")
        st.progress(ev.puntuacion / 100)
        st.markdown(f"### :{ev.color}[{ev.veredicto}]")
        st.write(ev.resumen)
    with c2:
        st.plotly_chart(grafico(df, "Último año: velas, medias móviles y RSI", ev.plan), width="stretch")
        st.caption("Cada vela es un día: verde si cerró por encima de lo que abrió, roja si por debajo. "
                   "Línea naranja = media de 50 sesiones (≈3 meses). Línea morada = media de 200 sesiones (≈1 año). "
                   "Abajo, el RSI: zona roja = sobrecomprada, zona verde = sobrevendida.")

    st.subheader("🧠 Por qué dice esto (explicado paso a paso)")
    for mo in sorted(ev.motivos, key=lambda x: -abs(x.puntos)):
        with st.expander(f"{mo.icono} {mo.titulo}  ({mo.puntos:+d})"):
            st.write(mo.explicacion)
    for a in ev.avisos:
        st.warning(a)

    if ev.plan:
        st.subheader("📋 Tu plan de operación")
        p = ev.plan
        n_riesgo = costes.tamano_por_riesgo(capital, riesgo, p.entrada, p.stop)
        importe = n_riesgo * p.entrada
        cc = costes.coste_compra(importe, ticker, tarifa)
        c = st.columns(4)
        c[0].metric("Precio de compra", eur(p.entrada, m))
        c[1].metric("Stop-loss (salida si falla)", eur(p.stop, m), f"-{p.riesgo_pct:.1f}%", delta_color="off")
        c[2].metric("Objetivo", eur(p.objetivo, m), f"+{p.beneficio_pct:.1f}%")
        c[3].metric("Acciones a comprar", n_riesgo, help="Calculado para que, si salta el stop-loss, "
                    f"pierdas como mucho el {riesgo}% de tu dinero.")
        st.markdown(
            f"Con **{eur(capital)}** y un riesgo máximo del **{riesgo}%** ({eur(capital * riesgo / 100)}), "
            f"comprarías **{n_riesgo} acciones** por unos **{eur(importe, m)}**. "
            f"Si sale mal y salta el stop, perderías unos **{eur(n_riesgo * (p.entrada - p.stop), m)}**. "
            f"Si llega al objetivo, ganarías unos **{eur(n_riesgo * (p.objetivo - p.entrada), m)}** (antes de impuestos). "
            f"Comisiones e impuestos de compra estimados: **{eur(cc['total'])}** ({cc['pct']:.2f}%).")
        st.caption("El stop-loss se coloca a 2 veces el movimiento diario típico (ATR) por debajo del precio, "
                   "y el objetivo al doble de distancia: así ganas el doble de lo que arriesgas. "
                   "Con esta proporción, aunque aciertes solo 4 de cada 10 veces, a la larga no pierdes.")
        if importe and cc["pct"] > 1:
            st.warning("Las comisiones se comen más del 1% de la compra. Con importes pequeños el mínimo de "
                       "comisión pesa mucho: mejor juntar más dinero y hacer menos operaciones.")
        if ev.puntuacion < 55:
            st.info("Con la puntuación actual el asistente **no recomienda entrar todavía**. "
                    "Guarda este plan y vuelve a revisarlo en unos días.")
        with st.expander("📱 Cómo hacerlo en la app de Bankinter"):
            bloque_bankinter(ticker, ev, n_riesgo)

    st.subheader("📰 Noticias recientes de la empresa")
    if news:
        for n in news[:8]:
            tarjeta_noticia(n)
    else:
        st.caption("No se han encontrado noticias recientes.")

    with st.expander("🧪 ¿Funciona seguir la tendencia? Prueba con el pasado (10 años)"):
        largo = cargar_historico(ticker, "10y")
        bt = senales.backtest_media200(largo, tarifa.pct) if not largo.empty else {}
        if bt:
            curvas = pd.DataFrame({"Comprar y mantener": bt["curva_mantener"],
                                   "Solo por encima de la media 200": bt["curva_estrategia"]})
            st.line_chart(curvas)
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
    st.title("📡 Radar del IBEX 35")
    st.caption("Analiza las 35 empresas a la vez y las ordena por puntuación. Úsalo para encontrar "
               "candidatas y luego estúdialas una a una en '🔍 Analizar una acción'.")
    with st.spinner("Analizando las 35 empresas (tarda unos segundos)..."):
        hist = cargar_varios(tuple(IBEX35))
        ibex = cargar_historico("^IBEX")
        alcista = senales.estado_indice(ibex)["alcista"] if not ibex.empty else None
        lista, _ = cargar_noticias()
    if not hist:
        st.error("No se han podido descargar cotizaciones.")
        return
    filas = []
    for t, df in hist.items():
        if len(df) < 60:
            continue
        rel = [n for n in lista if t in n.empresas]
        ev = senales.evaluar(t, df, noticias.sentimiento_medio(rel) if rel else None, len(rel), alcista)
        filas.append({
            "Empresa": nombre_de(t), "Ticker": t, "Sector": sector_de(t),
            "Puntuación": ev.puntuacion, "Veredicto": ev.veredicto,
            "Precio €": round(ev.precio, 2), "Hoy %": round(ev.datos["var_1d"], 2),
            "1 mes %": round(ev.datos["var_1m"], 1),
            "1 año %": round(ev.datos["var_1a"], 1) if not pd.isna(ev.datos["var_1a"]) else None,
            "RSI": round(ev.datos["rsi"], 0) if ev.datos["rsi"] else None,
            "Noticias hoy": len(rel),
        })
    tabla = pd.DataFrame(filas).sort_values("Puntuación", ascending=False)
    st.dataframe(tabla, hide_index=True, width="stretch", height=900,
                 column_config={"Puntuación": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d")})
    top = tabla[tabla["Puntuación"] >= 70]
    if len(top):
        st.success("En zona de compra según el asistente: " + ", ".join(top["Empresa"]) +
                   ". Recuerda: diversifica (no más de un 10-20% de tu dinero en una sola empresa) "
                   "y no concentres todo en un mismo sector.")
    else:
        st.info("Ahora mismo ninguna empresa supera 70 puntos. No pasa nada: no invertir también es una decisión.")


def pagina_calculadoras():
    st.title("🧮 Calculadoras")
    t1, t2, t3 = st.tabs(["💶 Coste de una compra", "🏛️ Impuestos al vender", "🌱 Invertir cada mes"])
    with t1:
        importe = st.number_input("Importe que vas a invertir (€)", 50.0, 1_000_000.0, 1000.0, 50.0)
        espanola = st.checkbox("Es una acción española del IBEX (paga el Impuesto de Transacciones Financieras)", True)
        cc = costes.coste_compra(importe, "X.MC" if espanola else "X", tarifa)
        c = st.columns(3)
        c[0].metric("Comisión broker + cánones", eur(cc["comision"]))
        c[1].metric("Impuesto Transacciones (0,2%)", eur(cc["itf"]))
        c[2].metric("Total", eur(cc["total"]), f"{cc['pct']:.2f}% del importe", delta_color="off")
        st.caption(f"Al vender pagarás de nuevo la comisión (≈{eur(tarifa.coste(importe))}). "
                   f"Para cubrir compra y venta la acción tiene que subir al menos un "
                   f"{(cc['total'] + tarifa.coste(importe)) / importe * 100:.2f}% antes de que ganes algo.")
    with t2:
        compra = st.number_input("Precio total de compra (€)", 0.0, 10_000_000.0, 1000.0, 50.0)
        venta = st.number_input("Precio total de venta (€)", 0.0, 10_000_000.0, 1300.0, 50.0)
        g = venta - compra
        imp = costes.impuesto_ganancia(g)
        c = st.columns(3)
        c[0].metric("Ganancia", eur(g))
        c[1].metric("IRPF aproximado", eur(imp))
        c[2].metric("Te queda limpio", eur(g - imp))
        st.caption("Tramos del ahorro: 19% hasta 6.000 €, 21% hasta 50.000 €, 23% hasta 200.000 €, "
                   "27% hasta 300.000 €, 30% a partir de ahí. Las pérdidas se pueden compensar con ganancias "
                   "(durante 4 años). Ojo con la 'regla de los 2 meses': si vendes con pérdidas y recompras la "
                   "misma acción en menos de 2 meses, no puedes aplicar esa pérdida todavía. "
                   "Bankinter te envía el informe fiscal para la declaración.")
    with t3:
        st.write("Para la mayoría de personas, la forma más eficaz de hacer crecer el dinero es **aportar una "
                 "cantidad fija cada mes a un fondo indexado o ETF** (por ejemplo, del MSCI World o del S&P 500), "
                 "sin intentar adivinar el mejor momento. A esto se le llama *Dollar Cost Averaging*.")
        c = st.columns(4)
        inicial = c[0].number_input("Dinero inicial (€)", 0.0, 1_000_000.0, 1000.0, 100.0)
        mensual = c[1].number_input("Aportación mensual (€)", 0.0, 10_000.0, 150.0, 10.0)
        anos = c[2].slider("Años", 1, 40, 15)
        rent = c[3].slider("Rentabilidad anual supuesta (%)", 0.0, 12.0, 7.0, 0.5,
                           help="La bolsa mundial ha dado históricamente ~7% anual de media "
                                "(con años de -40% y años de +30%). No está garantizado.")
        filas = costes.simular_aportaciones(mensual, anos, rent, inicial)
        tabla = pd.DataFrame(filas).set_index("Año")
        st.area_chart(tabla[["Aportado", "Ganancia"]])
        f = filas[-1]
        st.success(f"Aportando {eur(mensual)} al mes durante {anos} años habrías puesto **{eur(f['Aportado'])}** "
                   f"y tendrías unos **{eur(f['Valor'])}**. El interés compuesto hace el resto.")


def pagina_aprende():
    st.title("🎓 Aprende: lo básico para invertir con cabeza")
    st.info(AVISO)
    st.markdown("""
### 1. La verdad incómoda primero
- **Nadie acierta siempre el "momento perfecto"**: ni los profesionales. La mayoría de fondos de gestión activa
  rinden *menos* que el índice a 10 años. Este asistente te ayuda a **evitar malos momentos** y a **tener un plan**,
  no a adivinar el futuro.
- La "mayor rentabilidad" a largo plazo la consigue quien **está mucho tiempo invertido, diversifica,
  paga pocas comisiones y no vende por pánico**.
- Por eso, una estrategia sensata para empezar es:
  - **70-80%** de lo que inviertas: aportaciones mensuales a un **ETF o fondo indexado** mundial o del S&P 500.
  - **20-30%**: acciones individuales elegidas con este asistente, para aprender y buscar algo extra.
  - Ten antes un **colchón de emergencia** (3-6 meses de gastos) fuera de la bolsa.

### 2. Cómo usar este asistente (rutina de 10 minutos)
1. **🏠 Resumen del día**: mira el semáforo. Si está en rojo, no hay prisa por comprar.
2. **📰 Noticias**: lee las 3-5 más influyentes y su "por qué importa".
3. **📡 Radar**: busca empresas con puntuación alta (≥ 70).
4. **🔍 Analizar**: entra en la candidata, lee los motivos y el plan.
5. **Bankinter**: compra con **orden limitada** y pon el **stop-loss** inmediatamente.
6. Apunta por qué compraste. Revisa una vez por semana, no cada hora.

### 3. Diccionario rápido
| Término | Qué significa |
|---|---|
| **Acción** | Un trocito de una empresa. Si a la empresa le va bien, suele subir de precio y/o pagar dividendos. |
| **Índice (IBEX 35, S&P 500)** | Una cesta con las principales empresas de una bolsa. Sirve de termómetro. |
| **ETF** | Un fondo que se compra como una acción y replica un índice: con una compra tienes cientos de empresas. |
| **Dividendo** | Parte del beneficio que la empresa reparte entre sus accionistas. |
| **Media móvil (50 / 200)** | El precio medio de las últimas 50 o 200 sesiones. Suaviza el ruido y muestra la tendencia. |
| **RSI** | Indicador de 0 a 100. >70: ha subido demasiado rápido. <30: ha caído demasiado rápido. |
| **MACD** | Indicador de impulso: dice si el precio está acelerando al alza o a la baja. |
| **ATR** | Lo que se mueve una acción en un día normal. Sirve para colocar el stop-loss. |
| **Orden limitada** | Compras/vendes solo si el precio llega al que tú fijas. **Úsala siempre.** |
| **Orden a mercado** | Compras/vendes al precio que haya en ese momento. Rápida, pero puedes pagar de más. |
| **Stop-loss** | Orden que vende automáticamente si el precio cae hasta un nivel. Limita las pérdidas. |
| **Volatilidad** | Cuánto sube y baja el precio. Más volatilidad = más riesgo. |
| **OPA** | Oferta de una empresa para comprar otra. |
| **VIX** | El "índice del miedo" de Wall Street. |

### 4. Reglas de oro
1. **No inviertas dinero que vayas a necesitar** en los próximos 3-5 años.
2. **Diversifica**: varias empresas de distintos sectores, o directamente un ETF.
3. **No arriesgues más del 1-2% de tu capital en una operación** (el asistente calcula cuántas acciones comprar).
4. **Pon siempre stop-loss** en acciones individuales, y no lo muevas hacia abajo.
5. **Compra en varias veces** en lugar de todo de golpe.
6. **No persigas** una acción que ha subido un 20% en una semana.
7. **Las noticias ya están en el precio** muy rápido: cuando lees un titular, los profesionales ya han operado.
   Úsalas para entender el contexto, no para comprar con prisa.
8. **Controla las comisiones**: operar mucho con poco dinero hace que el broker gane más que tú.
9. **Las emociones son tu mayor enemigo**: miedo cuando cae, euforia cuando sube. Ten un plan y síguelo.

### 5. Calendario que mueve los mercados
- **Reuniones del BCE** (cada ~6 semanas, jueves) y de la **Fed** (8 al año, miércoles por la tarde en España).
- **IPC / inflación** (EEUU: hacia mediados de mes) y **empleo de EEUU** (primer viernes de mes, 14:30 h).
- **Temporada de resultados**: enero-febrero, abril-mayo, julio-agosto y octubre-noviembre.
- **Horario de la Bolsa española**: 9:00 a 17:30. **Wall Street**: 15:30 a 22:00 (hora España).
""")


PAGINAS = {
    "🏠 Resumen del día": pagina_resumen,
    "📰 Noticias que mueven el mercado": pagina_noticias,
    "🔍 Analizar una acción": pagina_analizar,
    "📡 Radar del IBEX 35": pagina_radar,
    "🧮 Calculadoras": pagina_calculadoras,
    "🎓 Aprende (empieza aquí)": pagina_aprende,
}
PAGINAS[pagina]()
