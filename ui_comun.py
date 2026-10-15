"""Funciones compartidas por todas las páginas: descarga de datos (con caché), formatos,
perfil del usuario y almacenamiento de carteras/estrategia."""

from __future__ import annotations

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from bolsa import almacen, costes, datos, finnhub, noticias, prediccion, senales
from bolsa.simulador import Parametros
from bolsa.tickers import TODAS_LAS_ACCIONES, indice_de_referencia, nombre_de


# --------------------------------------------------------------------------- caché de datos
@st.cache_data(ttl=600, show_spinner=False)
def cargar_historico(ticker: str, periodo: str = "2y") -> pd.DataFrame:
    return datos.historico(ticker, periodo)


@st.cache_data(ttl=600, show_spinner=False)
def _varios_corto(tickers: tuple[str, ...], periodo: str) -> dict[str, pd.DataFrame]:
    return datos.varios(list(tickers), periodo)


@st.cache_data(ttl=21_600, show_spinner=False)
def _varios_largo(tickers: tuple[str, ...], periodo: str) -> dict[str, pd.DataFrame]:
    """Historias largas (10 años): solo cambian una vez al día, así que se guardan 6 horas."""
    return datos.varios(list(tickers), periodo)


def cargar_varios(tickers: tuple[str, ...], periodo: str = "2y") -> dict[str, pd.DataFrame]:
    clave = tuple(sorted(set(tickers)))      # el mismo grupo en otro orden reutiliza la caché
    return _varios_largo(clave, periodo) if periodo in ("5y", "10y", "max") else _varios_corto(clave, periodo)


REFERENCIAS_LARGAS = ("IWDA.AS", "IBGS.AS", "XEON.DE", "^IBEX")


def historia_larga_eur(tickers: tuple[str, ...] | list[str]) -> dict[str, pd.DataFrame]:
    """10 años de tus valores y de las referencias (fondo mundial, renta fija, monetario, IBEX) en euros, con
    una sola descarga compartida por todos los bloques que la necesitan."""
    hist = cargar_varios(tuple(set(tickers) | set(REFERENCIAS_LARGAS)), "10y")
    cambios = cargar_varios(tuple(set(costes.TICKER_CAMBIO.values())), "10y")
    hist_eur = costes.historicos_en_euros(hist, {d: cambios.get(t) for d, t in costes.TICKER_CAMBIO.items()})
    if "^IBEX" in hist:
        hist_eur["^IBEX"] = hist["^IBEX"]
    return hist_eur


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


@st.cache_data(ttl=43_200, show_spinner=False)
def _dividendos_varios(tickers: tuple[str, ...]) -> dict[str, pd.Series]:
    return datos.dividendos_varios(list(tickers))


def cargar_dividendos_varios(tickers) -> dict[str, pd.Series]:
    return _dividendos_varios(tuple(sorted(set(tickers))))


def clave_finnhub() -> str | None:
    """Clave de Finnhub de Secrets ([finnhub] api_key) o de la variable FINNHUB_API_KEY; None si no hay."""
    try:
        clave = (st.secrets.get("finnhub", {}) or {}).get("api_key")
    except Exception:  # noqa: BLE001 - sin archivo de secretos
        clave = None
    return (clave or os.environ.get("FINNHUB_API_KEY") or "").strip() or None


@st.cache_data(ttl=3600, show_spinner=False)
def _estado_finnhub(clave: str) -> tuple[bool, str]:
    return finnhub.comprobar(clave)


def estado_finnhub() -> tuple[bool, str] | None:
    """(funciona, mensaje) si hay clave de Finnhub; None si no está configurada."""
    clave = clave_finnhub()
    return _estado_finnhub(clave) if clave else None


def _a_noticias(items: list[dict]) -> list[noticias.Noticia]:
    return [noticias.Noticia(n["titulo"], n["enlace"], n["fuente"], n["fecha"], n["resumen"]) for n in items]


@st.cache_data(ttl=120, show_spinner=False)
def cargar_noticias() -> tuple[list[noticias.Noticia], list[str]]:
    extra = []
    clave = clave_finnhub()
    if clave:
        try:
            extra = _a_noticias(finnhub.noticias_mercado(clave))
        except Exception:  # noqa: BLE001 - si Finnhub falla, quedan las demás fuentes
            extra = []
    return noticias.descargar(extra=extra)


@st.cache_data(ttl=20, show_spinner=False)
def cotizacion_al_instante(ticker: str) -> dict | None:
    """Precio en tiempo real de Finnhub (acciones de EEUU con clave); None en los demás casos."""
    clave = clave_finnhub()
    if not clave or not finnhub.es_eeuu(ticker):
        return None
    try:
        return finnhub.cotizacion(ticker, clave)
    except Exception:  # noqa: BLE001 - se queda el precio de Yahoo
        return None


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
    clave = clave_finnhub()
    if clave and finnhub.es_eeuu(ticker):
        try:
            extra += _a_noticias(finnhub.noticias_empresa(ticker, clave))
        except Exception:  # noqa: BLE001
            pass
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
    """Porcentaje (x ya en %) en formato español: +3,2 %. El signo menos es el guion normal: st.metric solo pinta
    en rojo y con flecha hacia abajo las variaciones que empiezan por «-»."""
    if x is None or pd.isna(x):
        return "—"
    texto = num(abs(x), dec)
    if signo:
        texto = ("+" if x > 0 else "-" if x < 0 else "") + texto
    elif x < 0:
        texto = "-" + texto
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


def alto_grafico() -> int:
    """Alto de los gráficos grandes: más bajo en el móvil."""
    return 430 if perfil().movil else 560


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
    from datetime import datetime

    try:
        _almacen().guardar(datos_usuario())
        st.session_state["_guardado"] = (True, datetime.now(MADRID_TZ).strftime("%H:%M"), "")
    except Exception as e:  # noqa: BLE001
        st.session_state["_guardado"] = (False, datetime.now(MADRID_TZ).strftime("%H:%M"), str(e))
        st.error(f"No se han podido guardar los datos: {e}. Descarga una copia de seguridad por si acaso.")


def aviso_datos_antiguos(hueco) -> None:
    """Si Yahoo ha fallado y se están mostrando datos de respaldo, lo dice arriba de la página."""
    from datetime import datetime

    antiguo = datos.respaldo_mas_antiguo()
    if antiguo:
        cuando = datetime.fromtimestamp(antiguo, MADRID_TZ).strftime("%d/%m a las %H:%M")
        hueco.warning(f"⚠️ Yahoo Finance no responde ahora mismo: ves los últimos datos buenos guardados (del {cuando}). "
                      "Pulsa «🔄 Actualizar ahora» en la barra lateral dentro de un rato.")


def _clave_app() -> str | None:
    try:
        return (st.secrets.get("app", {}) or {}).get("password") or None
    except Exception:  # noqa: BLE001 - sin secrets.toml, Streamlit lanza excepción
        return None


def control_acceso() -> None:
    """Pide la contraseña de la app (Secrets: [app] password = "...") antes de mostrar nada. Sin contraseña
    configurada, la app se abre (y la barra lateral avisa de que conviene ponerla)."""
    import hmac
    import time

    clave = _clave_app()
    if not clave or st.session_state.get("_acceso_ok"):
        return
    st.title("🔒 Asistente de Bolsa")
    st.caption("Esta app contiene tu cartera. Introduce la contraseña para entrar.")
    espera = st.session_state.get("_acceso_espera", 0) - time.time()
    with st.form("acceso"):
        tecleada = st.text_input("Contraseña", type="password")
        entrar = st.form_submit_button("Entrar", type="primary", disabled=espera > 0)
    if espera > 0:
        st.warning(f"Demasiados intentos. Espera {int(espera) + 1} segundos.")
    elif entrar:
        if hmac.compare_digest(tecleada.encode(), str(clave).encode()):
            st.session_state["_acceso_ok"] = True
            st.session_state.pop("_acceso_fallos", None)
            st.rerun()
        fallos = st.session_state.get("_acceso_fallos", 0) + 1
        st.session_state["_acceso_fallos"] = fallos
        if fallos >= 5:
            st.session_state["_acceso_espera"] = time.time() + 30 * (fallos - 4)
        st.error("Contraseña incorrecta.")
    st.stop()


def hay_contrasena() -> bool:
    return _clave_app() is not None


def estado_guardado() -> tuple[str, str]:
    """(icono y texto corto, explicación) del lugar donde se guardan tus datos."""
    alm = _almacen()
    ok, hora, error = st.session_state.get("_guardado", (None, "", ""))
    if ok is False:
        return f"❌ No se pudo guardar ({hora})", f"Error: {error}. Revisa el token y el id del Gist en Secrets."
    if alm.en_la_nube:
        return ("💾 Datos guardados en la nube" + (f" · {hora}" if hora else ""),
                "Se guardan en tu Gist privado de GitHub: no se pierden aunque la app se reinicie.")
    return ("⚠️ Datos solo en esta sesión",
            "No hay Gist configurado: si la app se reinicia, se pierden tu cartera y tu perfil. Configúralo en "
            "Streamlit → Settings → Secrets ([gist] token e id) o descarga una copia de seguridad.")


def ayuda(termino: str) -> str:
    """Definición del diccionario para usar como ayuda (?) en cualquier página."""
    from bolsa import aprendizaje

    return aprendizaje.definicion(termino)


def palabras_de_la_pagina(terminos: list[str]):
    """Desplegable con la explicación de las palabras técnicas que aparecen en la página."""
    from bolsa import aprendizaje

    encontrados = [t for t in aprendizaje.GLOSARIO if t.termino in terminos]
    if not encontrados:
        return
    with st.expander("📖 Palabras de esta página"):
        for t in sorted(encontrados, key=lambda x: terminos.index(x.termino)):
            st.markdown(f"**{t.termino}**: {t.definicion}" + (f"  \n<small>💡 {t.ejemplo}</small>" if t.ejemplo else ""),
                        unsafe_allow_html=True)


def estrategia_actual() -> Parametros:
    """Reglas entrenadas (si las hay) con el riesgo del perfil del usuario."""
    guardada = datos_usuario().get("estrategia", {}).get("parametros")
    p = Parametros.desde_dict(guardada) if guardada else Parametros()
    return Parametros(**{**p.a_dict(), "riesgo_pct": perfil().riesgo})


def ultimo_precio(df: pd.DataFrame) -> float | None:
    return float(df["Close"].iloc[-1]) if df is not None and not df.empty else None


# --------------------------------------------------------------------------- informe diario
MADRID_TZ = ZoneInfo("Europe/Madrid")
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


# --------------------------------------------------------------------------- estilo y menú del móvil
ESTILOS = """
<style>
/* Cifras un poco más pequeñas: caben más sin hacer scroll. */
[data-testid="stMetricValue"] { font-size: clamp(1.3rem, 2.4vw, 1.9rem); }
@media (max-width: 640px) {
  [data-testid="stMainBlockContainer"] { padding: 2.75rem 0.85rem 4rem 0.85rem; }
  h1 { font-size: 1.75rem !important; }
  h2 { font-size: 1.35rem !important; }
  h3 { font-size: 1.15rem !important; }
  [data-testid="stMetricValue"] { font-size: 1.3rem; }
  [data-testid="stMetricLabel"] p { font-size: 0.8rem; }
  /* Filas de cifras (solo cifras): dos por fila en vez de una debajo de otra. */
  [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]):not(:has([data-testid="stPlotlyChart"], [data-testid="stDataFrame"], [data-testid="stButton"], [data-testid="stExpander"], [data-testid="stForm"])) {
    flex-direction: row !important; flex-wrap: wrap !important; gap: 0.25rem 0.75rem !important; }
  [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]):not(:has([data-testid="stPlotlyChart"], [data-testid="stDataFrame"], [data-testid="stButton"], [data-testid="stExpander"], [data-testid="stForm"])) > [data-testid="stColumn"] {
    flex: 1 1 calc(50% - 0.75rem) !important; min-width: calc(50% - 0.75rem) !important;
    width: calc(50% - 0.75rem) !important; }
  /* Menú de abajo: siempre a mano, como en la app de un banco. */
  .st-key-nav_movil { position: fixed; bottom: 0; left: 0; right: 0; z-index: 999990;
    background: var(--background-color, #fff); border-top: 1px solid rgba(128, 128, 128, 0.25);
    padding: 0.2rem 0.3rem calc(0.2rem + env(safe-area-inset-bottom)) 0.3rem; }
  .st-key-nav_movil [data-testid="stHorizontalBlock"] { flex-direction: row !important; flex-wrap: nowrap !important;
    gap: 0.1rem !important; }
  .st-key-nav_movil [data-testid="stColumn"] { min-width: 0 !important; width: 20% !important; flex: 1 1 0 !important; }
  .st-key-nav_movil a, .st-key-nav_movil button { flex-direction: column !important; padding: 0.2rem 0 !important;
    min-height: 0 !important; gap: 0 !important; justify-content: center; width: 100%; border: none !important; }
  .st-key-nav_movil a p, .st-key-nav_movil button p { font-size: 0.68rem !important; white-space: nowrap; }
  .st-key-nav_movil [data-testid="stPopoverButton"] span[data-has-shortcut] {
    display: flex; flex-direction: column; align-items: center; gap: 0; }
  .st-key-nav_movil [data-testid="stPopoverButton"] div[aria-hidden="true"] { display: none; }
}
@media (min-width: 641px) { .st-key-nav_movil { display: none; } }
</style>
"""

ACCESOS_MOVIL = [("hoy", "Hoy", "🧭"), ("bankinter", "Cartera", "🏦"), ("seguimiento", "Seguimiento", "📒"),
                 ("chat", "Pregunta", "💬")]


def estilos() -> None:
    st.html(ESTILOS)


def barra_movil(grupos: dict[str, list]) -> None:
    """Menú fijo abajo en el móvil con las 4 páginas que más se usan y «Más» con todas las demás."""
    def enlazar(destino, pagina, **kw):
        try:
            destino.page_link(pagina, **kw)
        except Exception:  # noqa: BLE001 - un enlace nunca debe romper la página
            pass

    paginas = st.session_state.get("_paginas", {})
    with st.container(key="nav_movil"):
        cols = st.columns(5)
        for col, (clave, texto, icono) in zip(cols, ACCESOS_MOVIL):
            if clave in paginas:
                enlazar(col, paginas[clave], label=texto, icon=icono)
        with cols[4].popover("Más", icon=":material/menu:", width="stretch"):
            for grupo, lista in grupos.items():
                st.caption(grupo)
                for p in lista:
                    enlazar(st, p)
