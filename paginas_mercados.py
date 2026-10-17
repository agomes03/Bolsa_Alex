"""Página Mercados: índices, divisas, materias primas, cripto, fondos y acciones, como en el bróker."""

from __future__ import annotations

import os
import threading
import time

import pandas as pd
import streamlit as st

from bolsa.tickers import CATALOGO, CATEGORIAS, nombre_de
from paginas_hoy import bloque_fases
from ui_comun import (SEGUNDOS_PRECIOS, SEGUNDOS_REFRESCO, al_dia, cargar_activos, cargar_informe, cargar_varios,
                      cotizaciones_ahora, ir_a, linea_actualizado, num, palabras_de_la_pagina, pct, perfil)


BANDERAS = {"^IBEX": "🇪🇸", "^STOXX50E": "🇪🇺", "^GDAXI": "🇩🇪", "^FCHI": "🇫🇷", "FTSEMIB.MI": "🇮🇹", "^AEX": "🇳🇱",
            "^FTSE": "🇬🇧", "^SSMI": "🇨🇭", "^GSPC": "🇺🇸", "^NDX": "🇺🇸", "^IXIC": "🇺🇸", "^DJI": "🇺🇸", "^RUT": "🇺🇸",
            "^GSPTSE": "🇨🇦", "^BVSP": "🇧🇷", "^N225": "🇯🇵", "^HSI": "🇭🇰", "000001.SS": "🇨🇳", "^KS11": "🇰🇷",
            "^NSEI": "🇮🇳", "^AXJO": "🇦🇺"}
PESTANAS = ["Índices", "Acciones", "Fondos indexados", "Fondos de gestión activa", "ETF y oro",
            "ETF temáticos y sectoriales", "Renta fija", "Divisas", "Materias primas", "Criptomonedas",
            "Tipos de interés y macro"]
CORTOS = {"Fondos de gestión activa": "Fondos activos", "ETF temáticos y sectoriales": "ETF temáticos",
          "Tipos de interés y macro": "Tipos y macro"}
ZONAS = {"España": CATEGORIAS["Acciones de España"], "Europa": CATEGORIAS["Acciones de Europa"],
         "EEUU": CATEGORIAS["Acciones de EEUU"], "Resto del mundo": CATEGORIAS["Acciones del resto del mundo"],
         "SOCIMIs e inmobiliarias": CATEGORIAS["SOCIMIs e inmobiliarias"]}
GRUPOS_ACCIONES = [g for gs in ZONAS.values() for g in gs]


def filas_grupo(tickers: tuple[str, ...], completar: bool = True) -> list[dict]:
    """Precio, variaciones y tendencia de un grupo, al día (se renueva solo cada minuto, por detrás: al volver a
    un grupo ya visto sale al momento)."""
    return al_dia(("precios", "tabla", tickers), lambda: _descargar_filas(tickers, completar),
                  SEGUNDOS_PRECIOS - 15)[0] or []


def _descargar_filas(tickers: tuple[str, ...], completar: bool = True) -> list[dict]:
    """Todo el grupo con las cotizaciones en bloque (150 valores por petición, menos de un segundo). Lo que Yahoo
    no dé así se calcula con el histórico (más lento), salvo con `completar=False` (precarga en segundo plano)."""
    from bolsa import datos

    try:
        rapidas = datos.cotizaciones_bloque(list(tickers))
    except Exception:  # noqa: BLE001
        rapidas = {}
    por_ticker = {}
    for t, q in rapidas.items():
        por_ticker[t] = {"ticker": t, "precio": q["precio"],
                         "var_abs": q["precio"] - q["anterior"] if q.get("anterior") else None,
                         "var_1d": q.get("variacion_pct"), "var_1a": q.get("var_1a"), "alcista": q.get("alcista"),
                         "desde_maximo": q.get("desde_maximo"), "fecha": q["fecha"].strftime("%d/%m")}
    faltan = tuple(t for t in tickers if t not in por_ticker)
    if faltan and completar:
        por_ticker.update({f["ticker"]: f for f in _filas_del_historico(faltan)})
    return [por_ticker[t] for t in tickers if t in por_ticker]


def _filas_del_historico(tickers: tuple[str, ...]) -> list[dict]:
    """Plan B: una descarga de 2 años para el grupo, con el precio de ahora encima."""
    from bolsa import activos as act

    hist = cargar_varios(tickers, "2y")         # con "1y" a veces faltaba un día para la variación de 1 año
    try:
        ahora = cotizaciones_ahora(tickers, esperar=False)
    except Exception:  # noqa: BLE001
        ahora = {}
    filas = []
    for t in tickers:
        df = hist.get(t)
        e = act.estado(df) if df is not None else None
        if not e:
            continue
        c = df["Close"].dropna()
        f = {"ticker": t, "precio": e["precio"], "var_abs": float(c.iloc[-1] - c.iloc[-2]) if len(c) > 1 else None,
             "var_1d": e["var_1d"], "var_1a": e["var_1a"], "alcista": e["alcista"],
             "desde_maximo": e["desde_maximo"], "fecha": c.index[-1].strftime("%d/%m")}
        q = ahora.get(t)
        if q:
            f.update(precio=q["precio"], var_1d=q.get("variacion_pct"), fecha=q["fecha"].strftime("%d/%m"),
                     var_abs=q["precio"] - q["anterior"] if q.get("anterior") else f["var_abs"])
        filas.append(f)
    return filas


def _decimales(t: str) -> int:
    return 4 if t.endswith("=X") else 2


def pagina_resumen():
    st.title("🌍 Mercados")
    pestana = st.segmented_control("Ver", PESTANAS, default="Índices", key="mk_pestana",
                                   format_func=lambda p: CORTOS.get(p, p), label_visibility="collapsed") or "Índices"
    if pestana == "Acciones":
        c = st.columns(2)
        zona = c[0].selectbox("Zona", list(ZONAS), key="mk_zona")
        if st.session_state.get("mk_acciones") not in ZONAS[zona]:
            st.session_state.pop("mk_acciones", None)
        grupo = c[1].selectbox("Mercado o sector", ZONAS[zona], key="mk_acciones",
                               disabled=len(ZONAS[zona]) == 1)
    else:
        grupo = pestana
    precargar_grupos(grupo)
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
        "Fondos de gestión activa": "Fondos españoles y de autor (Cobas, Magallanes, azValor, Bestinver...): un gestor "
                                    "elige las empresas. Cobran más que los indexados (1-2 % al año) y la mayoría no "
                                    "bate a su índice a largo plazo. Se pueden traspasar sin pagar impuestos.",
        "ETF temáticos y sectoriales": "Apuestas por un sector o una idea (semiconductores, defensa, IA, dividendos...). "
                                       "Útiles como complemento pequeño; para el núcleo de la cartera, mejor un ETF "
                                       "mundial.",
        "Renta fija": "Bonos y monetarios: menos subidas y bajadas que la bolsa. Las Letras del Tesoro se compran "
                      "directamente en tesoro.es o en tu banco (calcula lo que te darían en Calculadoras → "
                      "Letras del Tesoro); aquí tienes fondos y ETF que las llevan dentro.",
        "SOCIMIs e inmobiliarias": "Empresas que viven de alquilar inmuebles. Reparten buena parte del beneficio en "
                                   "dividendos y sufren cuando suben los tipos de interés.",
        "España (BME Growth y SOCIMIs pequeñas)": "Empresas pequeñas y SOCIMIs del mercado BME Growth: se negocian "
                                                  "poco, así que el precio puede saltar mucho y costar vender.",
        "Latibex (Latinoamérica en euros)": "Empresas de Latinoamérica (Petrobras, Vale, bancos de Brasil...) que se "
                                            "compran en euros en la bolsa de Madrid.",
    }.get(grupo) or ("Cotizan en dólares: lo que ganes o pierdas también depende del cambio euro/dólar."
                     if grupo.startswith("EEUU") else None)
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
    return [dict(f) for f in filas_grupo(tickers)]


def precargar_grupos(actual: str) -> None:
    """Al entrar en Mercados, descarga en segundo plano los demás grupos (unos pocos a la vez), para que al
    cambiar de pestaña la tabla salga al momento. Se repite cada 25 min."""
    if os.environ.get("PYTEST_CURRENT_TEST") or time.time() - st.session_state.get("_mk_precarga", 0) < 1500:
        return
    st.session_state["_mk_precarga"] = time.time()
    from concurrent.futures import ThreadPoolExecutor
    from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx

    ctx = get_script_run_ctx()
    # Con las cotizaciones en bloque cada grupo es una o dos peticiones: se precargan todos (unos 3 s en total).
    grupos = [g for g in [*PESTANAS, *GRUPOS_ACCIONES] if g != actual and g in CATALOGO]

    def uno(g: str) -> None:
        add_script_run_ctx(threading.current_thread(), ctx)
        try:
            filas_grupo(tuple(CATALOGO[g]), completar=False)
        except BaseException:  # noqa: BLE001 - si falla (o la página se recarga), se descargará al abrir ese grupo
            pass

    def todos() -> None:
        with ThreadPoolExecutor(max_workers=3) as pool:
            list(pool.map(uno, grupos))

    threading.Thread(target=todos, daemon=True).start()


@st.fragment(run_every=SEGUNDOS_REFRESCO)
def bloque_mercado(grupo: str) -> bool:
    """Tarjetas de índices y tabla del grupo, con precios de ahora. Se refresca solo cada minuto."""
    hueco = st.empty()
    if st.session_state.get("_mk_pintado") != grupo:
        # Al cambiar de grupo, la tabla anterior se quita al momento (si no, Streamlit la deja a la vista,
        # apagada, hasta que llega la nueva y parece que no ha cambiado)
        hueco.info(f"⏳ Cargando {grupo}…")
    with st.spinner("Descargando cotizaciones..."):
        filas = filas_al_dia(tuple(CATALOGO[grupo]))
    if not filas:
        hueco.error("No se han podido descargar cotizaciones ahora mismo. Se volverá a intentar en un minuto.")
        return False
    st.session_state["_mk_pintado"] = grupo
    with hueco.container():
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
