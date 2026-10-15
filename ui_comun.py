"""Funciones compartidas por todas las páginas: descarga de datos (con caché), formatos,
perfil del usuario y almacenamiento de carteras/estrategia."""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from bolsa import almacen, costes, datos, noticias, prediccion, senales
from bolsa.simulador import Parametros
from bolsa.tickers import TODAS_LAS_ACCIONES, indice_de_referencia, nombre_de


# --------------------------------------------------------------------------- caché de datos
@st.cache_data(ttl=600, show_spinner=False)
def cargar_historico(ticker: str, periodo: str = "2y") -> pd.DataFrame:
    return datos.historico(ticker, periodo)


@st.cache_data(ttl=600, show_spinner=False)
def cargar_varios(tickers: tuple[str, ...], periodo: str = "2y") -> dict[str, pd.DataFrame]:
    return datos.varios(list(tickers), periodo)


@st.cache_data(ttl=60, show_spinner=False)
def cargar_intradia(ticker: str) -> pd.DataFrame:
    """Velas de 5 minutos del último mes, sin ajustar (los precios del bróker), en hora de Madrid."""
    return datos.intradia(ticker, "1mo", "5m")


@st.cache_data(ttl=900, show_spinner=False)
def cargar_diario_real(ticker: str, periodo: str = "1y") -> pd.DataFrame:
    """Histórico diario sin ajustar por dividendos (como lo muestra el bróker)."""
    return datos.diario_sin_ajustar(ticker, periodo)


@st.cache_data(ttl=900, show_spinner=False)
def cargar_activos() -> list[dict]:
    """Lectura de todo tipo de activos: bolsas, fondo mundial, renta fija, monetario, oro, petróleo, bitcoin..."""
    from bolsa import activos

    return activos.resumen(datos.varios(list(activos.ACTIVOS), "2y"))


@st.cache_data(ttl=300, show_spinner=False)
def cargar_noticias() -> tuple[list[noticias.Noticia], list[str]]:
    return noticias.descargar()


@st.cache_data(ttl=3600, show_spinner=False)
def cargar_fundamentales(ticker: str) -> dict:
    return datos.fundamentales(ticker)


@st.cache_data(ttl=3600, show_spinner=False)
def cargar_fundamentales_varios(tickers: tuple[str, ...]) -> dict[str, dict]:
    with ThreadPoolExecutor(max_workers=8) as pool:
        return dict(zip(tickers, pool.map(datos.fundamentales, tickers)))


@st.cache_data(ttl=900, show_spinner=False)
def noticias_empresa(ticker: str) -> list[noticias.Noticia]:
    nombre = nombre_de(ticker)
    extra = [noticias.Noticia(n["titulo"], n["enlace"], n["fuente"], n["fecha"], n["resumen"][:400])
             for n in datos.noticias_yahoo(ticker)]
    lista, _ = noticias.descargar(noticias.fuentes_empresa(ticker, nombre), max_por_fuente=25,
                                  extra=extra, max_horas=24 * 10)
    # Las fuentes de Google/Yahoo traen a veces noticias de otras empresas: quedarnos con las que la nombran.
    if ticker in TODAS_LAS_ACCIONES and TODAS_LAS_ACCIONES[ticker][2]:
        lista = [n for n in lista if ticker in n.empresas] or lista
    return lista


@st.cache_data(ttl=3600, show_spinner=False)
def cargar_predicciones(ticker: str) -> dict[str, prediccion.Prediccion]:
    df = cargar_historico(ticker, "10y")
    return prediccion.predecir_todos(df) if len(df) > 500 else {}


@st.cache_data(ttl=3600, show_spinner=False)
def predicciones_radar(tickers: tuple[str, ...]) -> dict[str, prediccion.Prediccion]:
    hist = cargar_varios(tickers, "10y")
    salida = {}
    for t, df in hist.items():
        p = prediccion.predecir(df, 21, "1 mes", n_pruebas=80) if len(df) > 500 else None
        if p:
            salida[t] = p
    return salida


def mercado_alcista_para(ticker: str) -> bool | None:
    h = cargar_historico(indice_de_referencia(ticker))
    return senales.estado_indice(h)["alcista"] if not h.empty else None


def num(x: float | None, dec: int = 2) -> str:
    """Número en formato español: 1.234,56."""
    if x is None or pd.isna(x):
        return "—"
    return f"{x:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pct(x: float | None, dec: int = 1, signo: bool = True) -> str:
    """Porcentaje (x ya en %) en formato español: +3,2 %."""
    if x is None or pd.isna(x):
        return "—"
    texto = num(abs(x), dec)
    if signo:
        texto = ("+" if x > 0 else "−" if x < 0 else "") + texto
    elif x < 0:
        texto = "−" + texto
    return f"{texto} %"


def eur(x: float | None, moneda: str = "€") -> str:
    return "—" if x is None or pd.isna(x) else f"{num(x, 2)} {moneda}"


def fecha(iso: str | None) -> str:
    """'2026-10-15' -> '15/10/2026'."""
    if not iso:
        return "—"
    try:
        return date.fromisoformat(str(iso)[:10]).strftime("%d/%m/%Y")
    except ValueError:
        return str(iso)


def hora_espana(iso_utc: str | None) -> str:
    """Fecha y hora UTC (ISO) en hora peninsular española."""
    if not iso_utc:
        return "—"
    from datetime import datetime
    from zoneinfo import ZoneInfo

    try:
        d = datetime.fromisoformat(iso_utc.replace("Z", "+00:00"))
        return d.astimezone(ZoneInfo("Europe/Madrid")).strftime("%d/%m/%Y a las %H:%M")
    except ValueError:
        return iso_utc


def moneda_de(ticker: str, info: dict | None = None) -> str:
    """Símbolo de la divisa en la que cotiza (la que verás en Bankinter)."""
    return costes.simbolo(ticker, info)


@st.cache_data(ttl=3600, show_spinner=False)
def tipos_cambio() -> dict[str, float]:
    """Unidades de cada divisa por 1 euro (último cierre)."""
    pares = {div: t for div, t in costes.TICKER_CAMBIO.items() if div != "GBp"}
    hist = datos.varios(sorted(set(pares.values())), "1mo")   # una sola descarga para todas las divisas
    salida = {}
    for div, t in pares.items():
        df = hist.get(t)
        if df is not None and not df.empty:
            salida[div] = float(df["Close"].iloc[-1])
    return salida


def fx(ticker: str, info: dict | None = None) -> float | None:
    """Euros que vale 1 unidad de la divisa del valor (1 para valores en euros; None si no se sabe)."""
    return costes.euros_por_unidad(costes.divisa(ticker, info), tipos_cambio())


def es_movil() -> bool:
    try:
        ua = st.context.headers.get("User-Agent", "") or ""
    except Exception:  # noqa: BLE001
        ua = ""
    return bool(re.search(r"Mobi|Android|iPhone|iPad", ua))


# --------------------------------------------------------------------------- perfil y datos del usuario
@dataclass
class Perfil:
    movil: bool
    capital: float
    riesgo: float
    tarifa: costes.Tarifa


def perfil() -> Perfil:
    return st.session_state["_perfil"]


@st.cache_resource
def _almacen() -> almacen.Almacen:
    return almacen.desde_secrets(st.secrets)


def almacen_actual() -> almacen.Almacen:
    return _almacen()


def datos_usuario() -> dict:
    """Carteras y estrategia del usuario (se cargan una vez por sesión)."""
    if "_datos" not in st.session_state:
        try:
            st.session_state["_datos"] = _almacen().cargar()
        except Exception as e:  # noqa: BLE001
            st.warning(f"No se pudieron cargar tus datos guardados ({e}). Empiezas con datos vacíos.")
            st.session_state["_datos"] = {}
    return st.session_state["_datos"]


def guardar_datos() -> None:
    try:
        _almacen().guardar(datos_usuario())
    except Exception as e:  # noqa: BLE001
        st.error(f"No se han podido guardar los datos: {e}. Descarga una copia de seguridad por si acaso.")


def estrategia_actual() -> Parametros:
    """Reglas entrenadas (si las hay) con el riesgo del perfil del usuario."""
    guardada = datos_usuario().get("estrategia", {}).get("parametros")
    p = Parametros.desde_dict(guardada) if guardada else Parametros()
    return Parametros(**{**p.a_dict(), "riesgo_pct": perfil().riesgo})


def ultimo_precio(df: pd.DataFrame) -> float | None:
    return float(df["Close"].iloc[-1]) if df is not None and not df.empty else None


# --------------------------------------------------------------------------- informe diario
RUTA_INFORME = Path(__file__).resolve().parent / "informe" / "informe.json"


@st.cache_data(ttl=600, show_spinner=False)
def _leer_informe(mtime: float) -> dict | None:
    try:
        return json.loads(RUTA_INFORME.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def cargar_informe() -> dict | None:
    """Informe generado cada noche por la actualización automática (None si aún no existe)."""
    if not RUTA_INFORME.exists():
        return None
    return _leer_informe(RUTA_INFORME.stat().st_mtime)


def dias_informe(inf: dict) -> int:
    return (date.today() - date.fromisoformat(inf.get("datos_hasta", inf["fecha"]))).days


def fila_informe(ticker: str) -> dict | None:
    inf = cargar_informe()
    if not inf:
        return None
    return next((r for r in inf.get("ranking", []) if r["ticker"] == ticker), None)


def mostrar_plotly(fig, alto: int | None = None):
    """Gráfico fluido: sin barra de herramientas y, en el móvil, sin capturar el deslizamiento ni el zoom (así la
    página se desplaza bien con el dedo)."""
    fig.update_layout(dragmode=False, margin=dict(l=0, r=0, t=30, b=0), **({"height": alto} if alto else {}))
    if st.session_state.get("_perfil") and st.session_state["_perfil"].movil:
        fig.update_xaxes(fixedrange=True)
        fig.update_yaxes(fixedrange=True)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False, "scrollZoom": False, "responsive": True})


def reducir(datos, max_puntos: int = 400):
    """Menos puntos en curvas largas (a la vista es igual y el móvil dibuja mucho más rápido)."""
    if datos is None or len(datos) <= max_puntos:
        return datos
    paso = -(-len(datos) // max_puntos)
    salida = datos.iloc[::paso]
    return salida if salida.index[-1] == datos.index[-1] else pd.concat([salida, datos.iloc[[-1]]])


def selector_valor(clave: str, solo_invertibles: bool = False, defecto: str | None = None,
                   etiqueta: str = "Valor") -> str:
    """Elige grupo (España, EEUU, Asia, Fondos, Cripto, Divisas...) y valor. Devuelve el ticker."""
    from bolsa.tickers import CATALOGO, NO_INVERTIBLES, grupo_de

    grupos = [g for g, d in CATALOGO.items() if not solo_invertibles or any(t not in NO_INVERTIBLES for t in d)]
    if defecto and grupo_de(defecto) in grupos and st.session_state.get(f"{clave}_def") != defecto:
        st.session_state[f"{clave}_grupo"] = grupo_de(defecto)
        st.session_state[f"{clave}_valor"] = defecto
        st.session_state[f"{clave}_def"] = defecto
    c = st.columns([1, 2])
    grupo = c[0].selectbox("Mercado o tipo", grupos, key=f"{clave}_grupo")
    opciones = [t for t in CATALOGO[grupo] if not solo_invertibles or t not in NO_INVERTIBLES]
    if st.session_state.get(f"{clave}_valor") not in opciones:
        st.session_state.pop(f"{clave}_valor", None)
    return c[1].selectbox(etiqueta, opciones, key=f"{clave}_valor", format_func=nombre_de)


def enlace(pagina: str, texto: str, icono: str | None = None):
    """Enlace a otra página de la app (no hace nada si la página no existe)."""
    paginas = st.session_state.get("_paginas", {})
    if pagina in paginas:
        try:
            st.page_link(paginas[pagina], label=texto, icon=icono)
        except Exception:  # noqa: BLE001 - un enlace nunca debe romper la página
            pass


def conclusion_noticia(titulo: str, resumen: str, empresas: list[str], sentimiento: int) -> dict | None:
    """Conclusión sencilla de una noticia con los datos de la app y tu cartera."""
    from bolsa import conclusiones

    filas = {r["ticker"]: r for r in (cargar_informe() or {}).get("ranking", [])}
    mias = set((datos_usuario().get("cartera_real") or {}).get("posiciones", {}))
    return conclusiones.concluir(titulo, resumen, empresas, sentimiento, filas, mias)


def mostrar_conclusion(c: dict | None):
    if not c:
        return
    with st.container(border=True):
        st.markdown(f"**{c['icono']} {c['titulo']}** — 📍 *Dónde repercute:* {c['donde']}")
        st.markdown(f"**Qué suele pasar:** {c['efecto']}  \n**💡 Oportunidad / qué hacer:** {c['oportunidad']}")
        if c["te_afecta"]:
            st.markdown(f"**📌 {c['te_afecta']}**")


def ir_a(pagina: str, **estado):
    """Navega a otra página (p. ej. 'analizar') guardando valores en la sesión."""
    st.session_state.update(estado)
    paginas = st.session_state.get("_paginas", {})
    if pagina in paginas:
        st.switch_page(paginas[pagina])
