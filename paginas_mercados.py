"""Página Mercados: índices, divisas, materias primas, cripto, fondos y acciones, como en el bróker."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from bolsa.tickers import CATALOGO, nombre_de
from paginas_hoy import bloque_fases
from ui_comun import (SEGUNDOS_REFRESCO, cargar_activos, cargar_informe, cargar_varios, cotizaciones_ahora, ir_a,
                      linea_actualizado, num, palabras_de_la_pagina, pct, perfil)


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

    hist = cargar_varios(tickers, "2y")         # con "1y" a veces faltaba un día para la variación de 1 año
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
    if not bloque_mercado(grupo):
        return
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

    palabras_de_la_pagina(["Índice bursátil", "Tendencia", "Media de 200 sesiones", "Volatilidad", "VIX", "Bono",
                           "Tipos de interés", "Fondo indexado", "ETF", "Valor liquidativo", "Criptomonedas", "Oro"])
    if grupo == "Índices":
        with st.expander("📖 Lectura en palabras de cada tipo de activo"):
            for a in cargar_activos():
                st.markdown(f"- {a['lectura']}")
        bloque_fases(cargar_informe())


def filas_al_dia(tickers: tuple[str, ...]) -> list[dict]:
    """Tendencia y variación anual del histórico (se descarga cada 10 min) con el precio de ahora encima."""
    filas = [dict(f) for f in filas_grupo(tickers)]
    try:     # sin esperar: mientras llegan los precios de ahora, se ve el último cierre
        ahora = cotizaciones_ahora(tickers, esperar=False)
    except Exception:  # noqa: BLE001
        ahora = {}
    for f in filas:
        q = ahora.get(f["ticker"])
        if q:
            f["precio"] = q["precio"]
            f["var_1d"] = q.get("variacion_pct")
            f["var_abs"] = q["precio"] - q["anterior"] if q.get("anterior") else f["var_abs"]
            f["fecha"] = q["fecha"].strftime("%d/%m")
    return filas


@st.fragment(run_every=SEGUNDOS_REFRESCO)
def bloque_mercado(grupo: str) -> bool:
    """Tarjetas de índices y tabla del grupo, con precios de ahora. Se refresca solo cada minuto."""
    with st.spinner("Descargando cotizaciones..."):
        filas = filas_al_dia(tuple(CATALOGO[grupo]))
    if not filas:
        st.error("No se han podido descargar cotizaciones ahora mismo. Se volverá a intentar en un minuto.")
        return False
    if grupo == "Índices":
        tarjetas_indices(filas)
    tabla_mercado(grupo, filas)
    st.caption(linea_actualizado())
    return True


def tarjetas_indices(filas: list[dict]):
    movil = perfil().movil
    principales = ["^IBEX", "^STOXX50E", "^GSPC", "^NDX", "^GDAXI", "^FCHI", "^FTSE", "^N225"]
    por_t = {f["ticker"]: f for f in filas}
    elegidos = [por_t[t] for t in principales if t in por_t]
    cols = st.columns(2 if movil else 4)
    for i, f in enumerate(elegidos):
        with cols[i % len(cols)].container(border=True):
            st.metric(f"{BANDERAS.get(f['ticker'], '')} {nombre_de(f['ticker']).split(' (')[0]}",
                      num(f["precio"], 2), pct(f["var_1d"], 2) if f["var_1d"] is not None else None,
                      help=f"Precio del {f['fecha']}. 1 año: {pct(f['var_1a'], 1)}.")


def tabla_mercado(grupo: str, filas: list[dict]):
    movil = perfil().movil
    invertible = grupo not in ("Índices", "Tipos de interés y macro")
    vista = pd.DataFrame([{
        "": ("🟢" if f["alcista"] else "🔴") if f["alcista"] is not None else "⚪",
        "Activo": f"{BANDERAS.get(f['ticker'], '')} {nombre_de(f['ticker'])}".strip(),
        "Último": round(f["precio"], _decimales(f["ticker"])),
        "V. diaria": round(f["var_abs"], _decimales(f["ticker"])) if f["var_abs"] is not None else None,
        "Hoy %": round(f["var_1d"], 2) if f["var_1d"] is not None else None,
        "1 año %": round(f["var_1a"], 1) if f["var_1a"] is not None else None,
        "Fecha": f["fecha"]} for f in filas])
    if movil:
        vista = vista[["", "Activo", "Último", "Hoy %"]]
    estilo = vista.style.map(lambda v: "color: #16a34a" if isinstance(v, (int, float)) and v > 0 else
                             "color: #dc2626" if isinstance(v, (int, float)) and v < 0 else "",
                             subset=[c for c in ("V. diaria", "Hoy %", "1 año %") if c in vista.columns])
    sel = st.dataframe(estilo, hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row",
                       key=f"mk_tabla_{grupo}",
                       column_config={"": st.column_config.TextColumn(width=28),
                                      "Activo": st.column_config.TextColumn(width="medium"),
                                      "Último": st.column_config.NumberColumn(format="localized"),
                                      "V. diaria": st.column_config.NumberColumn(format="localized"),
                                      "Hoy %": st.column_config.NumberColumn(format="%.2f %%")})
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
