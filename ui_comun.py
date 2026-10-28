"""Funciones compartidas por todas las páginas: descarga de datos (con caché), formatos,
perfil del usuario y almacenamiento de carteras/estrategia."""

from __future__ import annotations

import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from bolsa import almacen, costes, cuentas, datos, finnhub, noticias, prediccion, senales
from bolsa.simulador import Parametros
from bolsa.tickers import TODAS_LAS_ACCIONES, indice_de_referencia, nombre_de


# --------------------------------------------------------------------------- caché de datos
# El histórico diario y los datos de las empresas cambian poco durante el día (el precio de ahora va aparte, cada
# minuto): se guardan más tiempo para que cambiar de página casi nunca tenga que esperar a una descarga.
@st.cache_data(ttl=1800, show_spinner=False)
def cargar_historico(ticker: str, periodo: str = "2y") -> pd.DataFrame:
    return datos.historico(ticker, periodo)


@st.cache_data(ttl=1800, show_spinner=False)
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


@st.cache_data(ttl=1800, show_spinner=False)
def cargar_diario_real(ticker: str, periodo: str = "1y") -> pd.DataFrame:
    """Histórico diario sin ajustar por dividendos (como lo muestra el bróker)."""
    return datos.diario_sin_ajustar(ticker, periodo)


@st.cache_data(ttl=1800, show_spinner=False)
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


SEGUNDOS_NOTICIAS = 60      # cada cuánto se vuelven a leer todas las fuentes (y se refrescan solas las páginas)


def _leer_noticias() -> tuple[list[noticias.Noticia], list[str]]:
    extra = []
    clave = clave_finnhub()
    if clave:
        try:
            extra = _a_noticias(finnhub.noticias_mercado(clave))
        except Exception:  # noqa: BLE001 - si Finnhub falla, quedan las demás fuentes
            extra = []
    return noticias.descargar(extra=extra)


def _descargar_noticias() -> tuple[list[noticias.Noticia], list[str], str]:
    (lista, fallos), hora = al_dia(("noticias",), _leer_noticias, SEGUNDOS_NOTICIAS - 15)
    return lista, fallos, hora


def cargar_noticias() -> tuple[list[noticias.Noticia], list[str]]:
    """Noticias de todas las fuentes, leídas de nuevo como mucho cada minuto."""
    lista, fallos, _ = _descargar_noticias()
    return lista, fallos


def hora_noticias() -> str:
    """Hora (Madrid) de la última lectura de las fuentes."""
    return _descargar_noticias()[2]


def linea_frescura(lista: list[noticias.Noticia]) -> str:
    """«🔄 Leídas a las 10:42:05 · la más reciente, de hace 3 min (Expansión)»."""
    f = noticias.frescura(lista)
    texto = f"🔄 Fuentes leídas a las **{hora_noticias()}** (se vuelven a leer cada minuto)"
    if f["minutos"] is not None:
        fuente = next(iter(f["por_fuente"]))
        texto += f" · la noticia más reciente es de hace **{f['minutos']:.0f} min** ({fuente})"
    return texto


SEGUNDOS_PRECIOS = 60       # cada cuánto se refrescan solos los precios en Hoy, Mi cartera, Radar y Mercados
SEGUNDOS_REFRESCO = 60      # con alguna bolsa abierta, cada cuánto se refrescan solas las páginas
SEGUNDOS_REFRESCO_CERRADO = 600   # con todo cerrado (noches, fines de semana) los precios no cambian


def segundos_refresco() -> int:
    """Cada minuto si la bolsa española, la europea o la de EEUU está abierta; si no, cada 10 minutos."""
    from bolsa import horario

    try:
        abierta = any(horario.estado_mercado(t)["abierto"] for t in ("SAN.MC", "AAPL"))
    except Exception:  # noqa: BLE001
        abierta = True
    return SEGUNDOS_REFRESCO if abierta else SEGUNDOS_REFRESCO_CERRADO


def fragmento_vivo(funcion):
    """Como @st.fragment(run_every=...), pero el intervalo se decide cada vez que se pinta la página: cada minuto
    con mercado abierto y cada 10 minutos con todo cerrado (menos trabajo para el móvil y el servidor)."""
    from functools import wraps

    @wraps(funcion)
    def envoltura(*args, **kwargs):
        return st.fragment(funcion, run_every=segundos_refresco())(*args, **kwargs)
    return envoltura

# --------------------------------------------------------------------------- datos «siempre al día» sin esperas
# Precios y noticias se piden de nuevo en segundo plano: la pantalla enseña al momento lo último que hay y, cuando
# llega lo nuevo, el siguiente refresco lo muestra. Así la app nunca se queda congelada esperando a Yahoo.
_VIVOS: dict[tuple, dict] = {}
_CERROJO_VIVOS = threading.Lock()
_ULTIMA_HORA: dict[str, str] = {}


def _renovar(clave: tuple, funcion) -> None:
    try:
        valor = funcion()
    except Exception:  # noqa: BLE001 - se queda el último dato bueno
        valor = None
    with _CERROJO_VIVOS:
        e = _VIVOS.get(clave)
        if e is not None:
            e["renovando"] = False
            # Una descarga vacía (Yahoo limita, un canal caído) no borra lo bueno que ya había.
            if valor and not (isinstance(valor, tuple) and not valor[0]):
                if isinstance(valor, dict) and isinstance(e.get("valor"), dict):
                    valor = {**e["valor"], **valor}       # si falta algún valor, se queda su último precio
                e.update(valor=valor, t=time.time(), hora=_hora_ahora())


def _hora_ahora() -> str:
    from datetime import datetime

    return datetime.now(MADRID_TZ).strftime("%H:%M:%S")


def _hacer_sitio() -> None:
    """Muchos grupos distintos guardados: se olvidan los más viejos (nunca los que se están descargando)."""
    if len(_VIVOS) > 300:
        viejos = sorted((k for k in _VIVOS if not _VIVOS[k]["renovando"]), key=lambda k: _VIVOS[k]["t"])
        for k in viejos[:100]:
            _VIVOS.pop(k, None)


def al_dia(clave: tuple, funcion, segundos: int, esperar: bool = True):
    """(valor, hora): lo último descargado al instante; si tiene más de `segundos`, se renueva en segundo plano.
    La primera vez (nada guardado) se espera a la descarga, salvo con `esperar=False`: entonces devuelve
    (None, None) y la descarga sigue por detrás (la página enseña mientras tanto lo que ya tenga)."""
    with _CERROJO_VIVOS:
        e = _VIVOS.get(clave)
        if e is None and not esperar:
            _hacer_sitio()
            _VIVOS[clave] = {"valor": None, "t": 0.0, "hora": None, "renovando": True}
            threading.Thread(target=_renovar, args=(clave, funcion), daemon=True).start()
            return None, None
        if e is not None and time.time() - e["t"] >= segundos and not e["renovando"]:
            e["renovando"] = True
            threading.Thread(target=_renovar, args=(clave, funcion), daemon=True).start()
    if e is None:
        valor = funcion()
        with _CERROJO_VIVOS:
            _hacer_sitio()
            e = _VIVOS[clave] = {"valor": valor, "t": time.time(), "hora": _hora_ahora(), "renovando": False}
    if e["hora"]:
        _ULTIMA_HORA[clave[0]] = e["hora"]
    return e["valor"], e["hora"]


@contextmanager
def descargas_en_paralelo(*funciones):
    """Lanza ya, a la vez, descargas que la página necesitará más abajo (cada una guarda su resultado en la caché)
    mientras se hace lo de dentro del bloque; al salir, se esperan. Si alguna falla, se repite luego sin hilos."""
    from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx

    ctx = get_script_run_ctx()

    def lanzar(f):
        add_script_run_ctx(threading.current_thread(), ctx)
        try:
            f()
        except BaseException:  # noqa: BLE001 - (también si la página se recarga): se repite luego sin hilos
            pass

    pool = ThreadPoolExecutor(max_workers=max(len(funciones), 1))
    for f in funciones:
        pool.submit(lanzar, f)
    try:
        yield
    except BaseException:            # p. ej. st.rerun(): no se espera a las descargas
        pool.shutdown(wait=False, cancel_futures=True)
        raise
    pool.shutdown(wait=True)


def precalentar(*funciones) -> None:
    """Una vez por sesión, en segundo plano: descarga ya lo que suelen necesitar las demás páginas (mercados, la
    historia larga de tu cartera, los fondos...), para que al ir a ellas no haya que esperar."""
    if st.session_state.get("_precalentado") or os.environ.get("PYTEST_CURRENT_TEST"):
        return
    st.session_state["_precalentado"] = True
    from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx

    ctx = get_script_run_ctx()

    def correr():
        add_script_run_ctx(threading.current_thread(), ctx)
        for f in funciones:
            try:
                f()
            except BaseException:  # noqa: BLE001 - si algo falla (o la página se recarga), se descargará al ir a ella
                pass

    threading.Thread(target=correr, daemon=True).start()


def olvidar_datos_al_dia() -> None:
    """Para «Actualizar todo ahora» (y las pruebas): la próxima vez se descarga todo de nuevo."""
    with _CERROJO_VIVOS:
        _VIVOS.clear()
    with _CERROJO_FUND:
        _FUNDAMENTALES.clear()


def linea_actualizado() -> str:
    hora = _ULTIMA_HORA.get("precios") or _hora_ahora()
    return f"🔄 Precios de las {hora} · se actualizan solos (cada minuto con la bolsa abierta)"


def _precios_recientes(tickers: tuple[str, ...], esperar: bool = True) -> dict[str, dict]:
    # Un poco antes del minuto: así cada refresco automático encuentra ya los precios nuevos.
    return al_dia(("precios", tickers), lambda: datos.precios_recientes(list(tickers)), SEGUNDOS_PRECIOS - 15,
                  esperar)[0] or {}


MAX_FINNHUB_TABLA = 20      # el plan gratuito permite unas 60 consultas por minuto


def cotizaciones_ahora(tickers, esperar: bool = True) -> dict[str, dict]:
    """Precio de ahora para una lista de valores: en directo si su bolsa está abierta (Yahoo, ~15 min de retraso;
    tiempo real para EEUU con Finnhub) y, si está cerrada, el cierre de la última sesión.
    Cada valor: precio, anterior, variacion_pct, fecha, estado ('tiempo_real' | 'directo' | 'cierre').
    `esperar=False`: si aún no hay nada descargado, devuelve {} al momento (las tablas grandes no se quedan en
    blanco esperando; el siguiente refresco ya trae los precios)."""
    from bolsa import horario

    tickers = tuple(sorted(set(tickers)))
    if not tickers:
        return {}
    recientes = _precios_recientes(tickers, esperar)
    hoy = pd.Timestamp.now(tz=MADRID_TZ).date()
    salida = {}
    for t in tickers:
        q = dict(recientes[t]) if t in recientes else None
        if not q:
            continue
        abierto = horario.estado_mercado(t)["abierto"]
        q["estado"] = "directo" if abierto and q["fecha"] >= hoy else "cierre"
        salida[t] = q
    eeuu = [t for t in tickers if finnhub.es_eeuu(t) and salida.get(t, {}).get("estado") == "directo"]
    if clave_finnhub() and 0 < len(eeuu) <= MAX_FINNHUB_TABLA:
        with ThreadPoolExecutor(max_workers=8) as pool:
            for t, f in zip(eeuu, pool.map(cotizacion_al_instante, eeuu)):
                if f:
                    salida[t].update(precio=f["precio"], variacion_pct=f.get("variacion_pct"), estado="tiempo_real")
    return salida


def texto_estado_precio(q: dict) -> str:
    """«🟢 ahora», «⚡ tiempo real» o «cierre 15/10»."""
    if q["estado"] == "tiempo_real":
        return "⚡ tiempo real"
    if q["estado"] == "directo":
        return "🟢 ahora (~15 min)"
    return f"cierre {q['fecha']:%d/%m}"


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


# Datos de empresa, guardados valor a valor (cambian poco: 6 horas). Así lo descargado para Mi cartera sirve
# también para Hoy, Analizar o la cartera virtual aunque cada una pida una lista distinta.
_FUNDAMENTALES: dict[str, tuple[float, dict]] = {}
_CERROJO_FUND = threading.Lock()
SEGUNDOS_FUNDAMENTALES = 6 * 3600


def cargar_fundamentales_varios(tickers) -> dict[str, dict]:
    ahora = time.time()
    with _CERROJO_FUND:
        faltan = [t for t in dict.fromkeys(tickers)
                  if t not in _FUNDAMENTALES or ahora - _FUNDAMENTALES[t][0] > SEGUNDOS_FUNDAMENTALES]
    if faltan:
        with ThreadPoolExecutor(max_workers=min(8, len(faltan))) as pool:
            nuevos = list(pool.map(datos.fundamentales, faltan))
        with _CERROJO_FUND:
            for t, f in zip(faltan, nuevos):
                if f or t not in _FUNDAMENTALES:      # un fallo de Yahoo no borra lo bueno que ya había
                    _FUNDAMENTALES[t] = (ahora, f)
    with _CERROJO_FUND:
        return {t: dict(_FUNDAMENTALES[t][1]) for t in tickers if t in _FUNDAMENTALES}


def cargar_fundamentales(ticker: str) -> dict:
    return cargar_fundamentales_varios((ticker,)).get(ticker, {})


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def cargar_analistas(tickers: tuple[str, ...]) -> dict[str, dict]:
    """Datos de analistas de varias empresas (cambian poco: se piden cada 6 horas)."""
    with ThreadPoolExecutor(max_workers=3) as pool:      # pocas a la vez: Yahoo limita las peticiones
        return dict(zip(tickers, pool.map(datos.analistas, tickers)))


@st.cache_data(ttl=86_400, show_spinner=False)
def cargar_composiciones(tickers: tuple[str, ...]) -> dict[str, dict]:
    """Qué hay dentro de cada fondo o ETF (cambia poco: se pide una vez al día)."""
    with ThreadPoolExecutor(max_workers=3) as pool:
        return dict(zip(tickers, pool.map(datos.composicion_fondo, tickers)))


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


def privado() -> bool:
    """Modo privado (barra lateral): se ocultan tus importes; precios y porcentajes se siguen viendo."""
    try:
        return bool(st.session_state.get("_privado"))
    except Exception:  # noqa: BLE001 - fuera de la app
        return False


def eur(x: float | None, moneda: str = "€") -> str:
    """Un importe de dinero (tu cartera, una ganancia...). En modo privado sale «•••»."""
    if x is None or pd.isna(x):
        return "—"
    return f"••• {moneda}" if privado() else f"{num(x, 2)} {moneda}"


_IMPORTE = re.compile(r"[−+-]?\d[\d.]*(?:,\d+)?\s?€")


def ocultar(texto: str) -> str:
    """En modo privado, tapa los importes en euros de un texto ya escrito («perderías unos 1.234 €» → «••• €»)."""
    return _IMPORTE.sub("••• €", texto) if privado() and texto else texto


def tabla_privada(tabla: pd.DataFrame) -> pd.DataFrame:
    """En modo privado, sin las columnas en euros ni la de títulos (precios y porcentajes sí)."""
    if not privado():
        return tabla
    return tabla.drop(columns=[c for c in tabla.columns if "(€)" in str(c) or str(c) == "Títulos"])


def entrada_importe(donde, etiqueta: str, minimo: float, maximo: float, valor: float, paso: float, **kw) -> float:
    """Un campo con tu dinero (ahorros, aportación...): en modo privado no se enseña y se queda lo guardado."""
    if privado():
        donde.caption(f"{etiqueta}: ••• (oculto en modo privado)")
        return valor
    return donde.number_input(etiqueta, minimo, maximo, valor, paso, **kw)


def precio(x: float | None, moneda: str = "€") -> str:
    """El precio de un valor, o un importe de ejemplo (calculadoras, lecciones): no es tu dinero, así que se ve
    también en modo privado."""
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
def _tipos_cambio_completos() -> dict[str, float]:
    pares = {div: t for div, t in costes.TICKER_CAMBIO.items() if div != "GBp"}
    hist = datos.varios(sorted(set(pares.values())), "1mo")   # una sola descarga para todas las divisas
    salida = {div: float(hist[t]["Close"].iloc[-1]) for div, t in pares.items()
              if hist.get(t) is not None and not hist[t].empty}
    if len(salida) < len(pares):     # incompleto: no se guarda una hora (se reintenta en la próxima pantalla)
        raise ValueError("faltan tipos de cambio")
    return salida


def tipos_cambio() -> dict[str, float]:
    """Unidades de cada divisa por 1 euro (último cierre). Si falta alguna, se usan las que haya, sin guardarlas."""
    try:
        return _tipos_cambio_completos()
    except Exception:  # noqa: BLE001
        pares = {div: t for div, t in costes.TICKER_CAMBIO.items() if div != "GBp"}
        hist = cargar_varios(tuple(sorted(set(pares.values()))), "1mo")
        return {div: float(hist[t]["Close"].iloc[-1]) for div, t in pares.items()
                if hist.get(t) is not None and not hist[t].empty}


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
            try:
                d, version = _almacen().cargar_con_version()
            except Exception:  # noqa: BLE001 - un fallo pasajero de GitHub: se reintenta una vez
                d, version = _almacen().cargar_con_version()
            st.session_state["_datos"], st.session_state["_version_datos"] = d, version
            st.session_state["_cuentas_conocidas"] = sorted((d or {}).get("cuentas", {}) or
                                                            ([cuentas.PRINCIPAL] if d else []))
            st.session_state.pop("_carga_fallida", None)
            _GUARDADOS.pop(_id_sesion(), None)       # datos recién cargados: versión y cuentas de ahora
            cargar_nombres_buscados()
        except Exception as e:  # noqa: BLE001
            # Sin tus datos NO se guarda nada: guardar ahora borraría lo que tienes en la nube.
            st.session_state["_datos"] = {}
            st.session_state["_carga_fallida"] = str(e)
    d = st.session_state["_datos"]
    cuentas.asegurar(d)              # `cartera_real` apunta siempre a la cuenta activa
    _sincronizar_guardado(d)
    return d


def aviso_carga_fallida() -> None:
    """Arriba de todas las páginas, mientras tus datos no hayan podido cargarse."""
    datos_usuario()
    if st.session_state.get("_carga_fallida"):
        st.error("⚠️ No se han podido cargar tus datos guardados (GitHub no responde). Para no borrarlos, **la app no "
                 "guardará nada** hasta que vuelvan a cargarse.")
        if st.button("🔄 Reintentar cargar mis datos"):
            st.session_state.pop("_datos", None)
            st.rerun()


CAMPOS_DE_POSICION = ("stop_", "pv_", "pq_", "nv_", "ss_", "alarma_", "perfil_diag", "co_")


def olvidar_campos_de_cuenta() -> None:
    """Al cambiar de cuenta, los campos de cada posición (stop, venta, vigilar...) se rellenan con los de la cuenta
    nueva: si tu madre también tiene Santander, no se le pone tu stop-loss."""
    for k in [k for k in st.session_state if isinstance(k, str) and k.startswith(CAMPOS_DE_POSICION)]:
        del st.session_state[k]
    st.session_state.pop("_ss_resincronizar", None)
    st.session_state.pop("cta_seguro", None)


def cuenta_activa() -> dict:
    """La cuenta que estás mirando (la tuya, la de tu madre...): sus posiciones y sus ajustes (perfil, ahorros,
    avisos, diario, aportación, bróker). Nunca se suman cuentas."""
    return cuentas.activa(datos_usuario())


# Guardado en la nube en segundo plano: el botón responde al momento y GitHub se actualiza por detrás (dos
# llamadas de ~0,5 s cada una). Un trabajador por sesión; si pulsas varias cosas seguidas, se guarda solo lo último.
_GUARDADOS: dict[str, dict] = {}
_CERROJO_GUARDAR = threading.Lock()


def _id_sesion() -> str:
    from streamlit.runtime.scriptrunner import get_script_run_ctx

    ctx = get_script_run_ctx()
    return ctx.session_id if ctx else "sin_sesion"


def _hora() -> str:
    from datetime import datetime

    return datetime.now(MADRID_TZ).strftime("%H:%M")


def _trabajador_guardar(alm: almacen.Almacen, reg: dict) -> None:
    while True:
        with _CERROJO_GUARDAR:
            item = reg.pop("pendiente", None)
            if item is None:
                reg["hilo"] = None
                return
            cambiadas, reg["cambiadas"] = reg.get("cambiadas", set()), set()
            forzar = reg.pop("forzar", False)
        a_guardar, activa = item
        try:
            # Si otro dispositivo ha guardado desde que abriste la app, se junta con lo suyo en vez de pisarlo.
            remotos, version = alm.cargar_con_version()
            if version and version != reg.get("version") and not forzar:
                a_guardar = cuentas.combinar(a_guardar, remotos, cambiadas | {activa}, reg.get("conocidas"))
                otras = {n: c for n, c in a_guardar.get("cuentas", {}).items() if n not in cambiadas | {activa}}
                with _CERROJO_GUARDAR:
                    reg["otras_cuentas"] = otras
            nueva = alm.guardar(a_guardar)
            with _CERROJO_GUARDAR:
                reg["version"] = nueva
                reg["conocidas"] = set(a_guardar.get("cuentas", {}))
                reg["estado"] = (True, _hora(), "")
                reg.pop("fallos", None)
        except Exception as e:  # noqa: BLE001 - se reintenta solo (ver _sincronizar_guardado)
            with _CERROJO_GUARDAR:
                reg.setdefault("pendiente", item)
                reg["cambiadas"] = reg.get("cambiadas", set()) | cambiadas
                if forzar:
                    reg["forzar"] = True
                reg["estado"] = (False, _hora(), str(e))
                reg["fallos"] = reg.get("fallos", 0) + 1
                reg["ultimo_fallo"] = time.time()
                reg["hilo"] = None
            return


def _lanzar_guardado(reg: dict) -> None:
    """Arranca el trabajador si hay algo pendiente y no hay ninguno trabajando (llamar con el cerrojo cogido)."""
    if reg.get("pendiente") and not reg.get("hilo"):
        reg["hilo"] = threading.Thread(target=_trabajador_guardar, args=(_almacen(), reg), daemon=True)
        reg["hilo"].start()


def _sincronizar_guardado(d: dict) -> None:
    """Trae a la sesión lo que ha hecho el guardado en segundo plano (estado, versión, cambios de otras cuentas) y,
    si falló, lo reintenta solo (esperando cada vez un poco más)."""
    reg = _GUARDADOS.get(_id_sesion())
    if not reg:
        return
    with _CERROJO_GUARDAR:
        if reg.get("pendiente") and not reg.get("hilo") and \
                time.time() - reg.get("ultimo_fallo", 0) > min(10 * 2 ** reg.get("fallos", 0), 300):
            _lanzar_guardado(reg)
        estado = reg.get("estado")
        otras = reg.pop("otras_cuentas", None)
        version = reg.get("version")
    if estado:
        st.session_state["_guardado"] = estado
        if estado[0] is False and reg.get("avisado") != estado:
            reg["avisado"] = estado
            st.toast(f"⚠️ No se han podido guardar tus últimos cambios ({estado[2][:80]}). Se reintenta solo; si "
                     "sigue fallando, descarga una copia de seguridad.")
    if version:
        st.session_state["_version_datos"] = version
    if otras and d.get("cuentas"):
        for nombre, c in otras.items():
            if nombre != d.get("cuenta_activa") and nombre not in reg.get("cambiadas", set()):
                d["cuentas"][nombre] = c


def _registro_guardado() -> dict:
    """El registro de guardado de esta sesión (versión y cuentas conocidas al cargar los datos)."""
    reg = _GUARDADOS.get(_id_sesion())
    if reg is None:
        reg = _GUARDADOS[_id_sesion()] = {"version": st.session_state.get("_version_datos"),
                                          "conocidas": set(st.session_state.get("_cuentas_conocidas", ())),
                                          "cambiadas": set()}
    return reg


def guardar_datos(forzar: bool = False) -> None:
    """Guarda tus datos. `forzar`: sustituir lo de la nube sin juntarlo con lo de otros dispositivos (al restaurar
    una copia de seguridad)."""
    d = datos_usuario()
    if st.session_state.get("_carga_fallida"):
        st.session_state["_guardado"] = (False, _hora(), "tus datos no se cargaron; no se guarda para no borrarlos")
        return
    alm = _almacen()
    if not alm.en_la_nube:          # archivo local: es instantáneo
        try:
            st.session_state["_version_datos"] = alm.guardar(cuentas.para_guardar(d))
            st.session_state["_guardado"] = (True, _hora(), "")
        except Exception as e:  # noqa: BLE001
            st.session_state["_guardado"] = (False, _hora(), str(e))
            st.error(f"No se han podido guardar los datos: {e}. Descarga una copia de seguridad por si acaso.")
        return
    copia = json.loads(json.dumps(cuentas.para_guardar(d), ensure_ascii=False, default=str))
    with _CERROJO_GUARDAR:
        reg = _registro_guardado()
        reg["pendiente"] = (copia, d.get("cuenta_activa"))
        reg["cambiadas"] = reg.get("cambiadas", set()) | {d.get("cuenta_activa")}
        if forzar:
            reg["forzar"] = True
        reg["estado"] = (None, _hora(), "")
        reg.pop("fallos", None)
        reg.pop("ultimo_fallo", None)
        _lanzar_guardado(reg)
    st.session_state["_guardado"] = (None, _hora(), "")


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


_CALENTADO = {"cuando": 0.0}
_CERROJO_CALENTAR = threading.Lock()
SEGUNDOS_ENTRE_CALENTADOS = 1200


def calentar_en_segundo_plano() -> None:
    """Descarga ya, por detrás, lo que necesitará Hoy para tus cuentas (como mucho cada 20 min). Solo deja datos
    públicos de mercado en la caché del servidor: no enseña nada antes de la contraseña."""
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return
    with _CERROJO_CALENTAR:
        if time.time() - _CALENTADO["cuando"] < SEGUNDOS_ENTRE_CALENTADOS:
            return
        _CALENTADO["cuando"] = time.time()
    alm = _almacen()

    # Sin atarlo a esta ejecución de la página: la pantalla de la contraseña termina enseguida (st.stop) y
    # Streamlit pararía también las descargas.
    def correr():
        try:
            d, _ = alm.cargar_con_version()
            if d:
                from paginas_extra import calentar_cuentas
                calentar_cuentas(d)
            cargar_informe()
        except BaseException as e:  # noqa: BLE001 - si algo falla, se descargará al abrir la página
            import logging
            logging.getLogger(__name__).warning("No se ha podido calentar la caché: %r", e)

    threading.Thread(target=correr, daemon=True).start()


def control_acceso() -> None:
    """Pide la contraseña de la app (Secrets: [app] password = "...") antes de mostrar nada. Sin contraseña
    configurada, la app se abre (y la barra lateral avisa de que conviene ponerla)."""
    import hmac
    import time

    clave = _clave_app()
    if not clave or st.session_state.get("_acceso_ok"):
        return
    calentar_en_segundo_plano()          # mientras escribes la contraseña, se van descargando los datos de Hoy
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
    ok, hora, error = st.session_state.get("_guardado", ("", "", ""))
    if ok is None:
        return "⏳ Guardando en la nube…", "Tus últimos cambios se están guardando en tu Gist privado de GitHub."
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


def pestanas(nombres: list[str], clave: str):
    """Pestañas que solo calculan la que tienes abierta (las demás, al tocarlas). Así una página con varias
    pestañas pesadas (diagnóstico, dividendos, rentabilidad...) abre mucho más rápido."""
    return st.tabs(nombres, key=clave, on_change="rerun")


def mostrar_plotly(fig, alto: int | None = None, margen: dict | None = None):
    """Gráfico fluido: sin barra de herramientas y, en el móvil, sin capturar el deslizamiento ni el zoom (así la
    página se desplaza bien con el dedo). `margen`: para gráficos con etiquetas fuera (p. ej. el de araña)."""
    fig.update_layout(dragmode=False, margin=margen or dict(l=0, r=0, t=30, b=0), **({"height": alto} if alto else {}))
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


def _categorias_selector(solo_invertibles: bool) -> dict[str, list[str]]:
    from bolsa.tickers import CATALOGO, CATEGORIAS, NO_INVERTIBLES

    def vale(g: str) -> bool:
        return not solo_invertibles or any(t not in NO_INVERTIBLES for t in CATALOGO[g])

    categorias = {c: [g for g in gs if vale(g)] for c, gs in CATEGORIAS.items()}
    return {c: gs for c, gs in categorias.items() if gs}


def _opciones_grupo(grupo: str, solo_invertibles: bool) -> list[str]:
    from bolsa.tickers import CATALOGO, NO_INVERTIBLES

    return [t for t in CATALOGO[grupo] if not solo_invertibles or t not in NO_INVERTIBLES]


def selector_valor(clave: str, solo_invertibles: bool = False, defecto: str | None = None,
                   etiqueta: str = "Valor", buscar: bool = True) -> str:
    """Elige tipo (acciones de España, de EEUU, fondos, cripto...), mercado o sector y valor. Devuelve el ticker.
    Con `buscar`, debajo se puede buscar cualquier otro valor de Yahoo por nombre, ticker o ISIN.
    En tres pasos para que cada lista sea corta (el catálogo tiene unos 2.500 valores). Cambiar el tipo o el
    mercado solo recarga los desplegables (al momento); la página se recalcula cuando eliges el valor."""
    from bolsa.tickers import categoria_de, grupo_de

    categorias = _categorias_selector(solo_invertibles)
    # `defecto` llega una sola vez (quien llama lo saca de la sesión al usarlo): se aplica siempre, también si ya
    # habías abierto ese mismo valor antes (al volver a la página, Streamlit olvida lo que estaba elegido).
    if defecto and categoria_de(grupo_de(defecto)) in categorias:
        st.session_state[f"{clave}_cat"] = categoria_de(grupo_de(defecto))
        st.session_state[f"{clave}_grupo"] = grupo_de(defecto)
        st.session_state[f"{clave}_valor"] = st.session_state[f"{clave}_usado"] = defecto
        st.session_state[f"{clave}_buscar"] = ""
    elif defecto and buscar:        # algo de fuera del catálogo (encontrado antes con el buscador)
        st.session_state[f"{clave}_buscar"] = defecto
    if not st.session_state.get(f"{clave}_usado"):       # la primera vez: el primero de la lista
        primera = next(iter(categorias))
        st.session_state[f"{clave}_usado"] = st.session_state.get(f"{clave}_valor") or \
            _opciones_grupo(categorias[primera][0], solo_invertibles)[0]
    _desplegables_valor(clave, solo_invertibles, etiqueta)
    elegido = st.session_state[f"{clave}_usado"]
    if not buscar:
        return elegido
    hallado = buscador_valores(clave, solo_invertibles)
    return hallado or elegido


@st.fragment
def _desplegables_valor(clave: str, solo_invertibles: bool, etiqueta: str) -> None:
    """Los tres desplegables. Es un fragmento: al cambiar el tipo o el mercado solo se recargan ellos (la página
    no recalcula el análisis de un valor que no has elegido); al elegir el valor, se recarga la página entera."""
    from bolsa.tickers import categoria_de, grupo_de
    from streamlit.runtime.scriptrunner import get_script_run_ctx

    categorias = _categorias_selector(solo_invertibles)
    usado = st.session_state[f"{clave}_usado"]
    if st.session_state.get(f"{clave}_cat") not in categorias:          # lo primero: donde está lo que ves
        st.session_state[f"{clave}_cat"] = categoria_de(grupo_de(usado)) if categoria_de(grupo_de(usado)) in \
            categorias else next(iter(categorias))
    c = st.columns([1, 1, 2])
    categoria = c[0].selectbox("Tipo", list(categorias), key=f"{clave}_cat")
    grupos = categorias[categoria]
    if st.session_state.get(f"{clave}_grupo") not in grupos:
        st.session_state[f"{clave}_grupo"] = grupo_de(usado) if grupo_de(usado) in grupos else grupos[0]
    grupo = c[1].selectbox("Mercado o sector", grupos, key=f"{clave}_grupo", disabled=len(grupos) == 1)
    opciones = _opciones_grupo(grupo, solo_invertibles)
    if st.session_state.get(f"{clave}_valor") not in opciones:
        st.session_state[f"{clave}_valor"] = usado if usado in opciones else None
    valor = c[2].selectbox(etiqueta, opciones, key=f"{clave}_valor", format_func=nombre_de, index=None,
                           placeholder=f"Elige uno de {len(opciones)}...")
    if valor and valor != usado:
        st.session_state[f"{clave}_usado"] = valor
        ctx = get_script_run_ctx()
        if ctx is not None and ctx.fragment_ids_this_run:      # cambio dentro del fragmento: página entera
            st.rerun()


@st.cache_data(ttl=86_400, show_spinner=False)
def _buscar_en_yahoo(consulta: str) -> list[dict]:
    return datos.buscar_simbolos(consulta)


def buscador_valores(clave: str, solo_invertibles: bool = False) -> str | None:
    """«¿No está en la lista?»: busca en Yahoo por nombre, ticker o ISIN. Devuelve el ticker elegido o None."""
    from bolsa import tickers

    texto = st.text_input("🔎 ¿No está en la lista? Búscalo por nombre, ticker o ISIN", key=f"{clave}_buscar",
                          placeholder="Ej.: Ferrari, PLTR, IE00B4L5Y983, Cobas...").strip()
    if not texto:
        return None
    with st.spinner("Buscando..."):
        resultados = [r for r in _buscar_en_yahoo(texto)
                      if not solo_invertibles or r["type"] not in ("INDEX",)]
    if not resultados:
        st.caption("No encuentro nada con ese texto. Prueba con el nombre en inglés, el ticker o el ISIN (lo tienes "
                   "en la ficha del valor en tu banco).")
        return None
    por_simbolo = {r["symbol"]: r for r in resultados}
    simbolo = st.selectbox(
        "Resultados", list(por_simbolo), key=f"{clave}_hallado",
        format_func=lambda s: f"{por_simbolo[s]['name']} · {s} · "
                              f"{datos.TIPOS_BUSCABLES.get(por_simbolo[s]['type'], '')} {por_simbolo[s]['exchange']}")
    st.session_state[f"{clave}_tipo_hallado"] = por_simbolo[simbolo]["type"]
    if simbolo not in tickers.TODOS_LOS_VALORES:
        registrar_nombre(simbolo, por_simbolo[simbolo]["name"])
    if re.search(r"\b(\d(\.\d)?x|bull|bear|short|leveraged|inverse|ultra|daily)\b", por_simbolo[simbolo]["name"], re.I):
        st.warning("⚠️ Esto parece un producto **apalancado o inverso** (multiplica las subidas y las bajadas, y "
                   "pierde valor con el tiempo). No es para mantener: mejor la acción o un ETF normal.")
    st.caption("Estás usando el resultado de la búsqueda: borra el texto para volver a la lista.")
    return simbolo


_NOMBRES = {"cargados": False, "cerrojo": threading.Lock()}
NOMBRES_EXTRA = "nombres_buscados.json"


def cargar_nombres_buscados() -> None:
    """Una vez por proceso, en segundo plano: los nombres de lo que se encontró con el buscador (para que tu
    cartera virtual o tu lista no enseñen solo el código)."""
    from bolsa import tickers

    if _NOMBRES["cargados"] or os.environ.get("PYTEST_CURRENT_TEST"):
        return
    _NOMBRES["cargados"] = True
    alm = _almacen()

    def leer():
        try:
            tickers.NOMBRES_BUSCADOS.update({**alm.leer_extra(NOMBRES_EXTRA), **tickers.NOMBRES_BUSCADOS})
        except Exception:  # noqa: BLE001 - sin nombres se ve el código, nada más
            _NOMBRES["cargados"] = False

    threading.Thread(target=leer, daemon=True).start()


def registrar_nombre(ticker: str, nombre: str) -> None:
    """Apunta el nombre de un valor encontrado con el buscador y lo guarda en la nube (sin esperar)."""
    from bolsa import tickers

    if not nombre or tickers.NOMBRES_BUSCADOS.get(ticker) == nombre:
        return
    tickers.NOMBRES_BUSCADOS[ticker] = nombre
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return
    alm = _almacen()

    def guardar():
        with _NOMBRES["cerrojo"]:
            try:
                guardados = alm.leer_extra(NOMBRES_EXTRA)
                if guardados.get(ticker) != nombre:
                    alm.guardar_extra(NOMBRES_EXTRA, {**guardados, ticker: nombre})
            except Exception:  # noqa: BLE001
                pass

    threading.Thread(target=guardar, daemon=True).start()


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


# --------------------------------------------------------------------------- estilo
ESTILOS = """
<style>
/* Orden de compra/venta de la cartera virtual, con el aspecto de la de Bankinter (sirve en tema claro y oscuro). */
.st-key-orden_ticket, .st-key-orden_confirmar { background: rgba(128,128,128,.07); }
.orden-titulo { letter-spacing: .04em; opacity: .75; font-size: .95rem; border-bottom: 3px solid currentColor;
  display: inline-block; padding-bottom: .2rem; margin-bottom: .6rem; }
.orden-valor { font-size: 1.25rem; font-weight: 600; }
.orden-precio { font-size: 1.35rem; font-weight: 700; }
.orden-hora { opacity: .7; font-size: .9rem; }
.orden-caja { background: rgba(128,128,128,.14); border-radius: 6px; padding: .4rem .7rem; font-size: .85rem; }
.orden-caja-cab, .orden-caja-val { display: flex; justify-content: space-between; }
.orden-caja-cab { opacity: .8; letter-spacing: .03em; }
.orden-caja-val { font-weight: 600; font-size: 1rem; }
.orden-caja-pie { opacity: .7; font-size: .8rem; }
.st-key-orden_ticket [data-testid="stWidgetLabel"] p, .st-key-orden_confirmar [data-testid="stWidgetLabel"] p {
  font-size: .8rem; letter-spacing: .03em; opacity: .8; }
.st-key-orden_ticket button[kind="primary"], .st-key-orden_confirmar button[kind="primary"] {
  background: #f7941d; border-color: #f7941d; border-radius: 999px; letter-spacing: .06em; }
/* Cifras un poco más pequeñas: caben más sin hacer scroll. */
[data-testid="stMetricValue"] { font-size: clamp(1.3rem, 2.4vw, 1.9rem); }
@media (max-width: 640px) {
  [data-testid="stMainBlockContainer"] { padding: 2.75rem 0.85rem 3rem 0.85rem; }
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
}
</style>
"""


# En el móvil, la ayuda «?» se abre al tocarla (recibe el foco) y en el iPhone no se cerraba al tocar en otro sitio,
# porque tocar una zona vacía no quita el foco. Este código (nuestro, sin nada externo) la cierra al tocar fuera,
# al desplazar la página o al volver a tocar la misma «?».
AYUDAS_TACTILES = """
<script>
(() => {
  if (window.__ayudasTactiles) return;
  window.__ayudasTactiles = true;
  const AYUDA = '[data-testid="stTooltipHoverTarget"]';
  const enFoco = () => {
    const a = document.activeElement;
    return a && a.closest && a.closest(AYUDA) ? a : null;
  };
  const cerrar = () => { const a = enFoco(); if (a) a.blur(); };
  let abiertaAlTocar = null;
  document.addEventListener('touchstart', (e) => {
    const ayuda = e.target.closest && e.target.closest(AYUDA);
    const a = enFoco();
    abiertaAlTocar = ayuda && a && ayuda.contains(a) ? a : null;
    if (!ayuda) cerrar();
  }, {capture: true, passive: true});
  // Segundo toque en la misma «?»: el clic del toque le devuelve el foco, así que se cierra justo después.
  const cerrarLaTocada = () => {
    if (!abiertaAlTocar) return;
    const a = abiertaAlTocar; abiertaAlTocar = null;
    setTimeout(() => a.blur(), 50);
  };
  document.addEventListener('click', cerrarLaTocada, {capture: true});
  document.addEventListener('touchend', () => setTimeout(cerrarLaTocada, 400), {capture: true, passive: true});
  window.addEventListener('scroll', cerrar, {capture: true, passive: true});
})();
</script>
"""


def estilos() -> None:
    st.html(ESTILOS)
    st.html(AYUDAS_TACTILES, unsafe_allow_javascript=True)

