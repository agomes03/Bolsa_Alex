"""Funciones compartidas por todas las páginas: descarga de datos (con caché), formatos,
perfil del usuario y almacenamiento de carteras/estrategia."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import pandas as pd
import streamlit as st

from bolsa import almacen, costes, datos, noticias, prediccion, senales
from bolsa.simulador import Parametros
from bolsa.tickers import TODAS_LAS_ACCIONES, nombre_de


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
