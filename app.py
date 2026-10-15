"""Asistente de Bolsa para principiantes (pensado para operar con el broker de Bankinter).

Ejecutar:  streamlit run app.py
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from bolsa import aprendizaje, asesor, bankinter, costes, noticias, senales
from bolsa.activos import clase_de
from bolsa.indicadores import calcular_todo
from bolsa.tickers import CATALOGO, NO_INVERTIBLES, TODOS_LOS_VALORES, nombre_de, sector_de
from paginas_acierto import pagina_acierto
from paginas_chat import pagina_chat
from paginas_extra import bloque_operar, pagina_bankinter, pagina_cartera_virtual, pagina_simulador
from paginas_hoy import (bloque_fases, bloque_que_puede_pasar_accion, pagina_carteras, pagina_hoy, pagina_plan,
                         pagina_radar_global)
from ui_comun import (Perfil, estado_guardado, palabras_de_la_pagina, ir_a, mostrar_plotly, reducir, selector_valor, cargar_activos, conclusion_noticia, mostrar_conclusion, cargar_fundamentales, cargar_historico, cargar_informe, cargar_noticias, cargar_varios,
                      datos_usuario, es_movil, guardar_datos, eur, fila_informe, fx, mercado_alcista_para, moneda_de,
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
    _plan = datos_usuario().get("perfil_inversor") or {}
    _defecto = 3000.0
    if _plan:
        from bolsa import asesor as _asesor
        _perfil = _asesor.perfil_inversor(_plan["horizonte"], _plan["reaccion"], _plan["experiencia"], _plan["colchon"])
        _defecto = max(100.0, _plan["importe"] * _asesor.REPARTOS[_perfil.nombre]["Acciones individuales"] / 100)
    capital = st.number_input("Dinero para acciones sueltas (€)", min_value=100.0, value=float(round(_defecto, -1)),
                              step=100.0, help="La parte de tu dinero para comprar acciones concretas (en 🎯 Mi plan "
                                               "se calcula según tu perfil). Se usa para decirte cuántas comprar.")
    riesgo = st.slider("Máximo que aceptas perder por operación (% de ese dinero)", 0.5, 5.0, 1.0, 0.5,
                       help="Regla de oro de los profesionales: no arriesgar más de un 1-2% del capital "
                            "en una sola operación. Así, aunque falles varias veces seguidas, sigues en el juego.")
    _d = datos_usuario()
    broker = st.selectbox("Tu banco o bróker", costes.BROKERS,
                          index=costes.BROKERS.index(_d.get("broker", "Bankinter")) if _d.get("broker") in
                          costes.BROKERS else 0,
                          help="Se usa para las comisiones y para escribir las órdenes con los pasos de tu bróker.")
    if broker != _d.get("broker", "Bankinter"):
        _d["broker"] = broker
        guardar_datos()
    bankinter.BROKER = broker
    with st.expander(f"Tus comisiones en {broker if broker != 'Otro' else 'tu bróker'}"):
        if broker == "Bankinter":
            broker_cero = st.toggle("Tengo el servicio Bróker Cero", value=False,
                                    help="Con Bróker Cero, comprar y vender acciones españolas por Internet cuesta 0 € "
                                         "(solo pagas los cánones de la bolsa).")
            canon = st.number_input("Cánones de bolsa en España por operación (€, aprox.)", 0.0, 10.0, 1.0, 0.5)
            tarifa = costes.Tarifa(broker_cero=broker_cero, canon_nacional=canon)
            st.caption("Tarifa pública de Bankinter (oct. 2026): acciones españolas 3,95 € hasta 2.000 € y 8 € hasta "
                       "60.000 € por operación; extranjeras 20 € por operación, +1 % si se cambia de divisa, y una "
                       "custodia mínima de 24 € al año por valor. Compruébala en Bankinter → Bróker → Tarifas.")
        else:
            base = costes.TARIFAS_PRECARGADAS.get(broker, costes.TarifaPersonal(broker))
            guardada = _d.get("tarifas", {}).get(broker, {})
            v = {k: float(guardada.get(k, getattr(base, k))) for k in
                 ("nacional_fija", "internacional_fija", "divisa_pct", "custodia_anual_valor", "canon_nacional")}
            st.caption("Pon las comisiones de tu tarifa (están en la web de tu banco, apartado «tarifas» o "
                       "«comisiones» del bróker)." + (" Precargada la de Trade Republic: 1 € por operación."
                                                      if broker in costes.TARIFAS_PRECARGADAS else ""))
            v["nacional_fija"] = st.number_input("Por operación en España (€)", 0.0, 100.0, v["nacional_fija"], 0.5)
            v["internacional_fija"] = st.number_input("Por operación en el extranjero (€)", 0.0, 200.0,
                                                      v["internacional_fija"], 0.5)
            v["divisa_pct"] = st.number_input("Cambio de divisa (%)", 0.0, 5.0, v["divisa_pct"], 0.05)
            v["custodia_anual_valor"] = st.number_input("Custodia por valor extranjero y año (€)", 0.0, 200.0,
                                                        v["custodia_anual_valor"], 1.0)
            v["canon_nacional"] = st.number_input("Cánones de bolsa en España (€)", 0.0, 10.0, v["canon_nacional"], 0.5)
            if v != {k: float(guardada.get(k, getattr(base, k))) for k in v}:
                _d.setdefault("tarifas", {})[broker] = v
                guardar_datos()
            tarifa = costes.TarifaPersonal(broker, nacional_fija=v["nacional_fija"],
                                           internacional_fija=v["internacional_fija"], divisa_pct=v["divisa_pct"],
                                           custodia_anual_valor=v["custodia_anual_valor"],
                                           canon_nacional=v["canon_nacional"])
    st.divider()
    st.caption(f"Cotizaciones de Yahoo Finance (retraso ~15 min). Noticias de {len(noticias.FUENTES_RSS)} "
               "fuentes RSS en español e inglés. Se actualizan solas cada 5-10 minutos.")
    _texto_guardado, _ayuda_guardado = estado_guardado()
    st.caption(_texto_guardado, help=_ayuda_guardado)
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
        mostrar_conclusion(conclusion_noticia(n.titulo, n.resumen, n.empresas, n.sentimiento))
        if n.resumen and n.resumen.lower()[:60] not in n.titulo.lower():
            st.write(n.resumen)
        if n.explicaciones:
            st.markdown("**📚 Para entenderla:**")
            for e in n.explicaciones[:3]:
                st.markdown(f"- {e}")
        else:
            st.caption("Noticia sin un tema macro clave detectado: probablemente impacto limitado.")


def grafico(df: pd.DataFrame, titulo: str, plan: senales.Plan | None = None) -> go.Figure:
    # Solo lo necesario: un año visible (medio año en el móvil) más 200 sesiones para calcular la media larga.
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


BANDERAS = {"^IBEX": "🇪🇸", "^STOXX50E": "🇪🇺", "^GDAXI": "🇩🇪", "^FCHI": "🇫🇷", "FTSEMIB.MI": "🇮🇹", "^AEX": "🇳🇱",
            "^FTSE": "🇬🇧", "^SSMI": "🇨🇭", "^GSPC": "🇺🇸", "^NDX": "🇺🇸", "^IXIC": "🇺🇸", "^DJI": "🇺🇸", "^RUT": "🇺🇸",
            "^GSPTSE": "🇨🇦", "^BVSP": "🇧🇷", "^N225": "🇯🇵", "^HSI": "🇭🇰", "000001.SS": "🇨🇳", "^KS11": "🇰🇷",
            "^NSEI": "🇮🇳", "^AXJO": "🇦🇺"}
PESTANAS = ["Índices", "Divisas", "Materias primas", "Criptomonedas", "Tipos de interés y macro", "Fondos indexados",
            "ETF y oro", "Acciones"]
GRUPOS_ACCIONES = ["España (IBEX 35)", "España (Mercado Continuo)", "Europa", "EEUU", "Reino Unido, Suiza y Nórdicos",
                   "Asia", "Otros mercados"]


@st.cache_data(ttl=600, show_spinner=False)
def filas_grupo(tickers: tuple[str, ...]) -> list[dict]:
    """Último precio, variaciones y tendencia de un grupo (una sola descarga para todo el grupo)."""
    from bolsa import activos as act

    hist = cargar_varios(tickers, "1y")
    filas = []
    for t in tickers:
        df = hist.get(t)
        e = act.estado(df) if df is not None else None
        if not e:
            continue
        c = df["Close"].dropna()
        filas.append({"ticker": t, "precio": e["precio"], "var_abs": float(c.iloc[-1] - c.iloc[-2]) if len(c) > 1 else None,
                      "var_1d": e["var_1d"], "var_1a": e["var_1a"], "alcista": e["alcista"],
                      "desde_maximo": e["desde_maximo"], "fecha": c.index[-1].strftime("%d/%m")})
    return filas


def _decimales(t: str) -> int:
    return 4 if t.endswith("=X") else 2


def pagina_resumen():
    st.title("🌍 Mercados")
    pestana = st.segmented_control("Ver", PESTANAS, default="Índices", key="mk_pestana",
                                   label_visibility="collapsed") or "Índices"
    if pestana == "Acciones":
        grupo = st.selectbox("Mercado", GRUPOS_ACCIONES, key="mk_acciones")
    else:
        grupo = pestana
    tickers = tuple(CATALOGO[grupo])
    with st.spinner("Descargando cotizaciones..."):
        filas = filas_grupo(tickers)
    if not filas:
        st.error("No se han podido descargar cotizaciones ahora mismo. Pulsa «Actualizar ahora» en la barra lateral.")
        return

    if grupo == "Índices":
        tarjetas_indices(filas)
    texto_ayuda = {
        "Divisas": "Cuántos euros vale 1 unidad de cada moneda. Si sube, esa moneda se ha revalorizado frente al euro "
                   "(tus inversiones en ella valen más en euros).",
        "Materias primas": "Precios de los futuros en dólares. Para invertir en oro desde España lo habitual es un ETC "
                           "de oro físico en euros (pestaña «ETF y oro»).",
        "Tipos de interés y macro": "Rentabilidad de los bonos de EEUU en %, el VIX (miedo) y el dólar. Si los tipos "
                                    "suben, la bolsa y los bonos que ya existen suelen bajar.",
        "Fondos indexados": "Fondos que copian un índice, con su valor liquidativo (se calcula una vez al día). Se "
                            "contratan en la sección de fondos de tu banco y permiten traspasos sin impuestos.",
        "Criptomonedas": "Precios en euros. Muy volátiles: solo una parte pequeña de tu dinero.",
    }.get(grupo)
    if texto_ayuda:
        st.caption(texto_ayuda)
    tabla_mercado(grupo, filas)

    palabras_de_la_pagina(["Índice bursátil", "Tendencia", "Media de 200 sesiones", "Volatilidad", "VIX", "Bono",
                           "Tipos de interés", "Fondo indexado", "ETF", "Valor liquidativo", "Criptomonedas", "Oro"])
    if grupo == "Índices":
        with st.expander("📖 Lectura en palabras de cada tipo de activo"):
            for a in cargar_activos():
                st.markdown(f"- {a['lectura']}")
        bloque_fases(cargar_informe())


def tarjetas_indices(filas: list[dict]):
    principales = ["^IBEX", "^STOXX50E", "^FTSE", "^N225", "^GDAXI", "^FCHI", "^NDX", "^DJI"]
    por_t = {f["ticker"]: f for f in filas}
    elegidos = [por_t[t] for t in principales if t in por_t]
    cols = st.columns(2 if movil else 4)
    for i, f in enumerate(elegidos):
        with cols[i % len(cols)].container(border=True):
            st.metric(f"{BANDERAS.get(f['ticker'], '')} {nombre_de(f['ticker']).split(' (')[0]}",
                      num(f["precio"], 2), pct(f["var_1d"], 2) if f["var_1d"] is not None else None,
                      help=f"Último cierre: {f['fecha']}. 1 año: {pct(f['var_1a'], 1)}.")


@st.fragment
def tabla_mercado(grupo: str, filas: list[dict]):
    invertible = grupo not in ("Índices", "Tipos de interés y macro")
    vista = pd.DataFrame([{
        "": ("🟢" if f["alcista"] else "🔴") if f["alcista"] is not None else "⚪",
        "Activo": f"{BANDERAS.get(f['ticker'], '')} {nombre_de(f['ticker'])}".strip(),
        "Último": round(f["precio"], _decimales(f["ticker"])),
        "V. diaria": round(f["var_abs"], _decimales(f["ticker"])) if f["var_abs"] is not None else None,
        "V. diaria %": round(f["var_1d"], 2) if f["var_1d"] is not None else None,
        "1 año %": round(f["var_1a"], 1) if f["var_1a"] is not None else None,
        "Fecha": f["fecha"]} for f in filas])
    if movil:
        vista = vista[["", "Activo", "Último", "V. diaria %"]]
    estilo = vista.style.map(lambda v: "color: #16a34a" if isinstance(v, (int, float)) and v > 0 else
                             "color: #dc2626" if isinstance(v, (int, float)) and v < 0 else "",
                             subset=[c for c in ("V. diaria", "V. diaria %", "1 año %") if c in vista.columns])
    sel = st.dataframe(estilo, hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row",
                       key=f"mk_tabla_{grupo}",
                       column_config={"Último": st.column_config.NumberColumn(format="localized"),
                                      "V. diaria": st.column_config.NumberColumn(format="localized")})
    st.caption("🟢/🔴: por encima o por debajo de su media de un año (tendencia). Toca una fila para operar o analizar.")
    filas_sel = sel.selection.rows if sel and sel.selection else []
    if not filas_sel:
        return
    t = filas[filas_sel[0]]["ticker"]
    c = st.columns(3 if invertible else 1)
    if invertible:
        if c[0].button(f"🛒 Comprar {nombre_de(t).split(' (')[0]}", type="primary", width="stretch"):
            ir_a("virtual", v_defecto=t, v_sentido="Comprar")
        if c[1].button("💰 Vender", width="stretch"):
            ir_a("virtual", v_defecto=t, v_sentido="Vender")
    if c[-1].button("🔍 Analizar", width="stretch"):
        ir_a("analizar", analizar_ticker=t)
    if invertible:
        st.caption("Comprar y vender te llevan a la 🎮 Cartera virtual para practicar con dinero ficticio y precios reales.")


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


def plan_de_compra(ticker, ev, fund, f_eur, m, etiqueta, color) -> float:
    """Plan con stop-loss, costes y órdenes. Si el veredicto no es de compra, queda plegado."""
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
                    delta_color="off")
            c[1].metric("Stop-loss (vender si baja a)", eur(p.stop, m), pct(-p.riesgo_pct), delta_color="off")
            c[2 % len(c)].metric("Objetivo", eur(p.objetivo, m), pct(p.beneficio_pct))
            if iv:
                c[3 % len(c)].metric("Costes Bankinter", eur(iv["total"]), f"{pct(iv['pct'], 2, False)} del importe",
                                     delta_color="off", help="Comprar + vender + 1 año de custodia (si es extranjera).")
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
        mostrar_plotly(grafico(df, "Último año" if not movil else "Últimos 6 meses", ev.plan))
        st.caption("Velas: cada día (verde si subió, roja si bajó). Naranja: media de 50 sesiones (≈3 meses). "
                   "Morada: media de 200 sesiones (≈1 año). Abajo, el RSI: por encima de 70 ha subido muy deprisa, "
                   "por debajo de 30 ha caído muy deprisa.")
    for a in ev.avisos:
        st.warning(a)

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
        st.area_chart(reducir(tabla[["Aportado", "Ganancia"]]), height=ALTO_GRAFICO - 150)
        f = filas[-1]
        st.success(f"Aportando {eur(mensual)} al mes durante {anos} años habrías puesto **{eur(f['Aportado'])}** "
                   f"y tendrías unos **{eur(f['Valor'])}**. El interés compuesto hace el resto.")


def pagina_aprende():
    st.title("🎓 Aprende")
    q = st.text_input("🔎 ¿Qué palabra no entiendes?", placeholder="stop-loss, PER, plusvalía, spread, tasa Tobin...",
                      help="Busca en el diccionario, en las guías paso a paso y en el test. Vale sin tildes, con "
                           "siglas y con términos en inglés.")
    if q.strip():
        aprende_resultados(q)
        st.divider()
    t1, t2, t3, t4 = st.tabs(["📘 Lo esencial", "📖 Diccionario", "🛠️ Cómo se hace", "✅ Ponte a prueba"])
    with t1:
        aprende_esencial()
    with t2:
        aprende_diccionario()
    with t3:
        aprende_guias()
    with t4:
        aprende_test()


def aprende_esencial():
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

### 3. Reglas de oro
1. **No inviertas dinero que vayas a necesitar** en los próximos 3-5 años.
2. **Diversifica**: ninguna empresa por encima del 20 % de tu dinero, ningún sector por encima del 40 %.
3. **No arriesgues más del 1-2 % de tu dinero en una operación** (la app calcula cuántas acciones comprar).
4. **Pon siempre stop-loss** en acciones sueltas y no lo bajes nunca.
5. **No persigas** una acción que ha subido un 20 % en una semana.
6. **Las noticias llegan tarde**: cuando las lees, el precio ya se ha movido. Sirven para entender, no para correr.
7. **Las comisiones importan**: pocas operaciones y bien pensadas.
8. **Las emociones son tu mayor enemigo**: ten un plan y síguelo.

### 4. Calendario que mueve los mercados
- Reuniones del **BCE** (cada ~6 semanas, jueves) y de la **Fed** (8 al año, miércoles por la tarde en España).
- **IPC** de EEUU (hacia mediados de mes) y **empleo** de EEUU (primer viernes de mes, 14:30 h).
- **Resultados de las empresas**: enero-febrero, abril-mayo, julio-agosto y octubre-noviembre.
- **Horario**: Bolsa española de 9:00 a 17:30; Wall Street de 15:30 a 22:00 (hora peninsular; una hora antes
  unas semanas de marzo y de octubre-noviembre por el cambio de hora).
""")


def _termino_md(t) -> str:
    texto = f"**{t.termino}** · _{t.categoria}_\n\n{t.definicion}"
    if t.ejemplo:
        texto += f"\n\n> 💡 {t.ejemplo}"
    if t.ver:
        texto += f"\n\n<small>Ver también: {', '.join(t.ver)}</small>"
    return texto


def aprende_resultados(q: str):
    terminos = aprendizaje.buscar(q)
    guias = aprendizaje.buscar_guias(q)
    preguntas = aprendizaje.buscar_preguntas(q)
    if not (terminos or guias or preguntas):
        parecidos = aprendizaje.parecidos(q)
        if parecidos:
            st.info(f"No aparece «{q}». ¿Quizás buscabas…?")
            for t in parecidos[:3]:
                with st.container(border=True):
                    st.markdown(_termino_md(t), unsafe_allow_html=True)
        else:
            st.info(f"No aparece «{q}». Prueba con otra palabra o mira los temas del 📖 Diccionario.")
        return
    # Los que coinciden en el nombre se muestran abiertos; el resto, plegados para no llenar la pantalla.
    for i, t in enumerate(terminos[:12]):
        if i < 3:
            with st.container(border=True):
                st.markdown(_termino_md(t), unsafe_allow_html=True)
        else:
            with st.expander(f"📖 {t.termino}"):
                st.markdown(_termino_md(t), unsafe_allow_html=True)
    if len(terminos) > 12:
        st.caption(f"Y {len(terminos) - 12} términos más: escribe una palabra más concreta.")
    for g in guias:
        with st.expander(f"🛠️ Guía: {g.titulo}"):
            _guia(g)
    for p in preguntas:
        with st.expander(f"✅ Del test: {p.pregunta[:70]}"):
            st.markdown(f"**{p.pregunta}**\n\nRespuesta: **{p.opciones[p.correcta]}**. {p.explicacion}")


def aprende_diccionario():
    st.caption(f"{len(aprendizaje.GLOSARIO)} términos explicados en lenguaje sencillo, con ejemplos en euros. "
               "Para buscar una palabra, usa el buscador de arriba.")
    for nombre in aprendizaje.CATEGORIAS:
        terminos = aprendizaje.buscar(categoria=nombre)
        with st.expander(f"{nombre} ({len(terminos)})"):
            for t in terminos:
                st.markdown(_termino_md(t), unsafe_allow_html=True)


def _guia(g):
    st.markdown(f"**Para qué:** {g.para_que}")
    st.markdown("\n".join(f"{i}. {p}" for i, p in enumerate(g.pasos, 1)))
    if g.errores:
        st.markdown("**Errores típicos:**\n" + "\n".join(f"- ❌ {e}" for e in g.errores))
    if g.en_la_app:
        st.caption("📱 " + g.en_la_app)


def aprende_guias():
    st.caption("Paso a paso, con lo que tienes que pulsar en Bankinter y en esta app. Los nombres de los menús de "
               "Bankinter pueden variar un poco entre la web y la app del móvil.")
    for g in aprendizaje.GUIAS:
        with st.expander(f"🛠️ {g.titulo}"):
            _guia(g)

    with st.expander("🧮 Practica: cuántas acciones comprar y dónde poner el stop"):
        st.write("La cantidad no se elige a ojo: sale de cuánto aceptas perder si la operación sale mal.")
        k = st.columns(2 if movil else 4)
        dinero = k[0].number_input("Tu dinero para acciones (€)", 500.0, 10_000_000.0, 10_000.0, 500.0)
        riesgo_p = k[1].number_input("Riesgo por operación (%)", 0.25, 5.0, 1.0, 0.25)
        entrada = k[2 % len(k)].number_input("Precio de compra (€)", 0.1, 100_000.0, 20.0, 0.5)
        stop_p = k[3 % len(k)].number_input("Stop-loss (€)", 0.0, 100_000.0, 18.0, 0.5)
        if stop_p >= entrada:
            st.warning("El stop-loss tiene que estar por debajo del precio de compra.")
        else:
            n = costes.tamano_por_riesgo(dinero, riesgo_p, entrada, stop_p)
            arriesgado = dinero * riesgo_p / 100
            st.markdown(
                f"1. Lo máximo que aceptas perder: {num(riesgo_p, 2)} % de {eur(dinero)} = **{eur(arriesgado)}**.\n"
                f"2. Si salta el stop, pierdes {eur(entrada)} − {eur(stop_p)} = **{eur(entrada - stop_p)} por acción**.\n"
                f"3. Acciones: {eur(arriesgado)} / {eur(entrada - stop_p)} = **{n} "
                f"{'acción' if n == 1 else 'acciones'}** ({eur(n * entrada)}, el "
                f"{num(n * entrada / dinero * 100, 0)} % de tu dinero).")
            if n * entrada > dinero * 0.20:
                st.info(f"Eso supera el 20 % de tu dinero en una sola empresa: por diversificación, la app lo limita a "
                        f"unas {costes.acciones_asequibles(dinero * 0.20, entrada, 'SAN.MC', tarifa)} acciones.")

    st.markdown("#### Resumen: qué orden usar en Bankinter")
    st.markdown("""
| Para… | En Bankinter | Por qué |
|---|---|---|
| Comprar una acción | Bróker → buscar el nombre → **Comprar** → orden **Limitada** | Nunca pagas más del precio que pones. |
| Limitar pérdidas | Orden **Stop** de venta: «menor o igual que» + **precio límite** | Bankinter exige precio límite; ponlo un 2 % por debajo para que se ejecute aunque caiga deprisa. |
| Pérdidas y objetivo a la vez | **Stop relacionadas** | Al ejecutarse una, Bankinter cancela la otra. |
| Que el stop suba solo | **Stop dinámica** | Sube con la cotización y no baja nunca. |
| Subir un stop | Anular la orden stop y crear otra | En Bankinter las órdenes stop no se modifican. |
| Aportar cada mes | **Fondos** → fondo indexado → aportación periódica | Sin comisión por aportación (un ETF extranjero cuesta 20 € cada compra). |
| Revisar tu cartera | Bróker → **Posición global** → descargar | Súbelo en 🏦 Mi cartera para el diagnóstico. |

**Lo que cuesta en Bankinter** (tarifa pública, octubre 2026; compruébala en Bróker → Tarifas):
- Acciones españolas: **3,95 €** hasta 2.000 € y **8 €** hasta 60.000 € por operación (**0 €** con Bróker Cero), más
  un canon de bolsa de ~1 € y la tasa Tobin (0,2 % al comprar empresas de más de 1.000 millones).
- Acciones extranjeras: **20 €** por operación, **+1 %** si cotizan en otra divisa y una **custodia mínima de 24 € al
  año por valor**. Con poco dinero, mejor acciones españolas y fondos indexados.
""")


def aprende_test():
    st.caption(f"{len(aprendizaje.PREGUNTAS)} preguntas sobre situaciones reales. Sin nota que guardar: solo para "
               "comprobar que lo tienes claro.")
    with st.form("test_aprende"):
        respuestas = [st.radio(f"**{i}.** {p.pregunta}", p.opciones, index=None, key=f"test_{i}")
                      for i, p in enumerate(aprendizaje.PREGUNTAS, 1)]
        corregir = st.form_submit_button("Corregir", type="primary")
    if not corregir:
        return
    aciertos = 0
    for i, (p, r) in enumerate(zip(aprendizaje.PREGUNTAS, respuestas), 1):
        bien = r == p.opciones[p.correcta]
        aciertos += bien
        icono = "✅" if bien else ("⬜" if r is None else "❌")
        st.markdown(f"{icono} **{i}.** {p.opciones[p.correcta]} — {p.explicacion}")
    n = len(aprendizaje.PREGUNTAS)
    (st.success if aciertos >= n * 0.8 else st.info)(
        f"Has acertado {aciertos} de {n}." + ("" if aciertos >= n * 0.8 else
                                            " Repasa las guías de 🛠️ Cómo se hace y vuelve a intentarlo."))


PAGINAS = {
    "hoy": st.Page(pagina_hoy, title="Hoy", icon="🧭", default=True),
    "plan": st.Page(pagina_plan, title="Mi plan", icon="🎯"),
    "analizar": st.Page(pagina_analizar, title="Analizar", icon="🔍"),
    "radar": st.Page(pagina_radar, title="Radar", icon="📡"),
    "carteras": st.Page(pagina_carteras, title="Carteras modelo", icon="📦"),
    "noticias": st.Page(pagina_noticias, title="Noticias", icon="📰"),
    "mercados": st.Page(pagina_resumen, title="Mercados", icon="🌍"),
    "bankinter": st.Page(pagina_bankinter, title="Mi cartera", icon="🏦"),
    "virtual": st.Page(pagina_cartera_virtual, title="Cartera virtual", icon="🎮"),
    "simulador": st.Page(pagina_simulador, title="Simulador y modelos", icon="🧪"),
    "calculadoras": st.Page(pagina_calculadoras, title="Calculadoras", icon="🧮"),
    "aprende": st.Page(pagina_aprende, title="Aprende", icon="🎓"),
    "chat": st.Page(pagina_chat, title="Pregunta", icon="💬"),
    "acierto": st.Page(pagina_acierto, title="¿Acierta la app?", icon="✅"),
}
st.session_state["_paginas"] = PAGINAS
nav = st.navigation({
    "Inicio": [PAGINAS["hoy"], PAGINAS["plan"], PAGINAS["chat"]],
    "Invertir": [PAGINAS["analizar"], PAGINAS["radar"], PAGINAS["carteras"], PAGINAS["noticias"],
                 PAGINAS["mercados"]],
    "Mis carteras": [PAGINAS["bankinter"], PAGINAS["virtual"]],
    "Aprender y probar": [PAGINAS["acierto"], PAGINAS["simulador"], PAGINAS["calculadoras"], PAGINAS["aprende"]],
}, position="top")
nav.run()
