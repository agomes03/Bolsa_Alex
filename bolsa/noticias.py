"""Noticias de última hora: descarga de muchas fuentes RSS (España e internacionales, en español
e inglés), puntuación de impacto y explicación sencilla.

No usa inteligencia artificial: aplica reglas transparentes (palabras clave) para que
siempre puedas ver *por qué* una noticia se considera importante.
"""

from __future__ import annotations

import calendar
import html
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import quote_plus

from .tickers import TODAS_LAS_ACCIONES


def url_google_news(consulta: str, dias: int = 7, ingles: bool = False) -> str:
    q = quote_plus(f"{consulta} when:{dias}d")
    if ingles:
        return f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
    return f"https://news.google.com/rss/search?q={q}&hl=es&gl=ES&ceid=ES:es"


def url_yahoo(ticker: str) -> str:
    return f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={quote_plus(ticker)}&region=US&lang=en-US"


FUENTES_RSS = {
    # Prensa económica española
    "Expansión - Mercados": "https://e00-expansion.uecdn.es/rss/mercados.xml",
    "Expansión - Economía": "https://e00-expansion.uecdn.es/rss/economia.xml",
    "elEconomista - Mercados": "https://www.eleconomista.es/rss/rss-mercados.php",
    "elEconomista - Economía": "https://www.eleconomista.es/rss/rss-economia.php",
    "Cinco Días - Mercados": "https://cincodias.elpais.com/rss/cincodias/mercados/",
    "El País - Economía": "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/economia/portada",
    "El Confidencial - Mercados": "https://rss.elconfidencial.com/mercados/",
    "Europa Press - Economía": "https://www.europapress.es/rss/rss.aspx?ch=00136",
    "La Vanguardia - Economía": "https://www.lavanguardia.com/rss/economia.xml",
    "Investing.com España": "https://es.investing.com/rss/news_25.rss",
    # Agregadores (decenas de medios cada uno)
    "Google News - IBEX": url_google_news("IBEX 35", 1),
    "Google News - Bolsa": url_google_news('bolsa OR "Wall Street" OR "mercados"', 1),
    "Google News - BCE/Fed": url_google_news('BCE OR "Reserva Federal" OR "tipos de interés"', 2),
    "Google News - Markets (EN)": url_google_news('"stock market" OR "Wall Street" OR stocks', 1, ingles=True),
    # Prensa financiera internacional (inglés)
    "CNBC - Top News": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
    "CNBC - Economy": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258",
    "MarketWatch - Top Stories": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
    "MarketWatch - Market Pulse": "https://feeds.content.dowjones.io/public/rss/mw_marketpulse",
    "Yahoo Finance": "https://finance.yahoo.com/news/rssindex",
}


# Temas que mueven a TODO el mercado. (expresión regular, peso, explicación para principiantes)
TEMAS_MACRO = [
    (r"\bbce\b|banco central europeo|lagarde|\becb\b", 3,
     "El BCE decide los tipos de interés en Europa. Bajadas de tipos suelen animar la bolsa; "
     "subidas la frenan (aunque a los bancos les ayudan los tipos altos)."),
    (r"\bfed\b|reserva federal|federal reserve|powell|\bfomc\b", 3,
     "La Reserva Federal fija los tipos en EEUU. Lo que hace la Fed mueve a todas las bolsas del mundo."),
    (r"tipos de inter[eé]s|subida de tipos|bajada de tipos|recorte de tipos|euribor|interest rates?|rate cut|rate hike", 3,
     "Los tipos de interés son el 'precio del dinero'. Tipos más bajos = empresas y familias "
     "se endeudan más barato = suele ser bueno para la bolsa."),
    (r"inflaci[oó]n|\bipc\b|\bpce\b|inflation|\bcpi\b", 2,
     "Si la inflación sube más de lo esperado, los bancos centrales pueden subir tipos, y eso suele hacer caer la bolsa."),
    (r"empleo|paro|n[oó]minas|payrolls|desempleo|jobs report|unemployment|jobless", 2,
     "El dato de empleo indica la salud de la economía. Se publica en EEUU el primer viernes de cada mes."),
    (r"\bpib\b|recesi[oó]n|crecimiento econ[oó]mico|\bgdp\b|recession", 2,
     "El PIB mide cuánto crece la economía. Una recesión (PIB cayendo) suele traer caídas en bolsa."),
    (r"aranceles?|guerra comercial|proteccionismo|tariffs?|trade war", 3,
     "Los aranceles encarecen el comercio entre países. Suelen provocar caídas, sobre todo en exportadoras."),
    (r"guerra|conflicto|ataque|geopol[ií]tic|invasi[oó]n|misil|\bwar\b|military|missile", 2,
     "Los conflictos generan incertidumbre: suelen bajar las bolsas y subir el petróleo y el oro."),
    (r"petr[oó]leo|brent|\bopep\b|\bopec\b|crude|\boil prices?", 2,
     "El precio del petróleo afecta a petroleras (Repsol), aerolíneas (IAG) y a la inflación."),
    (r"desplome|hundimiento|p[aá]nico|crash|batacazo|sell-?off|plunge|tumble|rout", 2,
     "Indica caídas fuertes. Para el inversor a largo plazo, los desplomes pueden ser oportunidades, "
     "pero nunca compres todo de golpe en plena caída."),
    (r"r[eé]cord|m[aá]ximos hist[oó]ricos|m[aá]ximos anuales|all-time high|record high", 1,
     "El mercado está en máximos: buen momento para el que ya estaba dentro; para entrar, mejor ir poco a poco."),
    (r"prima de riesgo|bono a 10 a[nñ]os|rentabilidad del bono|treasury yields?|bond yields?", 1,
     "La rentabilidad de los bonos compite con la bolsa: si sube mucho, las acciones suelen sufrir."),
    (r"china|yuan|beijing|pek[ií]n", 1,
     "China es la segunda economía mundial; sus problemas afectan a materias primas y lujo."),
    (r"inteligencia artificial|\bia\b|\bai\b|chips?|semiconductor", 1,
     "La IA es el gran motor de las tecnológicas de EEUU (Nvidia, Microsoft...)."),
    (r"shutdown|techo de deuda|debt ceiling|cierre del gobierno", 2,
     "Bloqueos políticos en EEUU que pueden retrasar datos y generar nerviosismo."),
]

# Eventos de empresa (cuando la noticia nombra una empresa concreta).
TEMAS_EMPRESA = [
    (r"resultados|beneficio|ganancias|facturaci[oó]n|ventas|trimestre|earnings|revenue|quarterly|profit", 2,
     "Resultados trimestrales: lo que importa es si son mejores o peores *de lo que esperaba el mercado*."),
    (r"\bopa\b|oferta p[uú]blica|fusi[oó]n|adquisici[oó]n|compra de|takeover|merger|acquisition|\bbid\b", 3,
     "OPA/fusión: una empresa quiere comprar otra. La comprada suele subir; la compradora a veces baja."),
    (r"dividendo|dividend", 2,
     "El dividendo es el dinero que la empresa reparte a sus accionistas. El día que se paga, la acción baja ese importe."),
    (r"recompra|buyback", 1,
     "La empresa compra sus propias acciones: reduce el número de acciones y suele apoyar la cotización."),
    (r"rebaja.*(recomendaci[oó]n|precio objetivo|rating)|recorta.*precio objetivo|downgrade", 2,
     "Un analista rebaja su opinión. Puede presionar el precio a corto plazo."),
    (r"eleva.*(recomendaci[oó]n|precio objetivo)|mejora.*recomendaci[oó]n|sube.*precio objetivo|upgrade", 2,
     "Un analista mejora su opinión. Suele impulsar la acción a corto plazo."),
    (r"ampliaci[oó]n de capital|share offering|dilut", 2,
     "La empresa emite acciones nuevas para captar dinero: diluye a los accionistas y suele bajar el precio."),
    (r"profit warning|rebaja.*previsiones|recorta.*previsiones|cuts? (guidance|outlook)", 3,
     "La empresa avisa de que ganará menos de lo previsto: suele provocar caídas fuertes."),
    (r"eleva.*previsiones|mejora.*previsiones|raises? (guidance|outlook)", 2,
     "La empresa espera ganar más de lo previsto: buena señal."),
]

PALABRAS_POSITIVAS = [
    # español
    "sube", "suben", "subida", "alza", "alzas", "dispara", "disparan", "gana", "ganan", "récord", "record",
    "máximos", "maximos", "rebote", "rebota", "mejora", "mejoran", "supera", "superan", "optimismo",
    "repunte", "repunta", "avanza", "avanzan", "impulsa", "impulso", "crece", "crecen", "beneficio",
    "bajada de tipos", "recorte de tipos", "eleva", "verde", "euforia", "fuerte demanda",
    # inglés
    "rise", "rises", "rally", "rallies", "gain", "gains", "surge", "surges", "soar", "soars", "jump",
    "jumps", "beat", "beats", "upgrade", "record high", "rebound", "climb", "climbs", "strong", "optimism",
    "rate cut", "boost", "outperform",
]
PALABRAS_NEGATIVAS = [
    # español
    "cae", "caen", "caída", "caida", "baja", "bajan", "desplome", "desploma", "hunde", "hunden",
    "pierde", "pierden", "pérdidas", "perdidas", "mínimos", "minimos", "temor", "temores", "miedo",
    "recorta", "rebaja", "incertidumbre", "crisis", "recesión", "recesion", "aranceles", "guerra",
    "pánico", "panico", "retrocede", "retroceden", "rojo", "decepciona", "advierte", "subida de tipos",
    "profit warning", "sanción", "multa", "investigación", "investigacion", "huelga",
    # inglés
    "fall", "falls", "drop", "drops", "slump", "slumps", "plunge", "plunges", "tumble", "tumbles",
    "sink", "sinks", "loss", "losses", "miss", "misses", "downgrade", "fear", "fears", "recession",
    "tariff", "tariffs", "selloff", "sell-off", "weak", "warning", "crisis", "probe", "lawsuit", "rate hike",
    "slide", "slides", "decline", "declines", "worst",
]


@dataclass
class Noticia:
    titulo: str
    enlace: str
    fuente: str
    fecha: datetime | None
    resumen: str = ""
    impacto: int = 0                       # 0-10
    sentimiento: int = 0                   # -1, 0, +1
    temas: list[str] = field(default_factory=list)
    explicaciones: list[str] = field(default_factory=list)
    empresas: list[str] = field(default_factory=list)  # tickers
    repeticiones: int = 1                  # nº de fuentes que publican la misma noticia

    @property
    def etiqueta_sentimiento(self) -> str:
        return {1: "🟢 Positiva", -1: "🔴 Negativa", 0: "⚪ Neutra"}[self.sentimiento]

    @property
    def horas(self) -> float | None:
        if not self.fecha:
            return None
        return (datetime.now(timezone.utc) - self.fecha).total_seconds() / 3600


def _limpiar(texto: str) -> str:
    texto = re.sub(r"<[^>]+>", " ", texto or "")
    return re.sub(r"\s+", " ", html.unescape(texto)).strip()


def _contar(texto: str, palabras: list[str]) -> int:
    return sum(1 for p in palabras if re.search(rf"(?<!\w){re.escape(p)}(?!\w)", texto))


def clave_titulo(titulo: str) -> str:
    """Clave para detectar la misma noticia en varias fuentes (Google News añade ' - Medio')."""
    titulo = re.sub(r"\s+[-|–]\s+[^-|–]{2,40}$", "", titulo)
    return re.sub(r"\W+", "", titulo.lower())[:70]


def detectar_empresas(texto: str) -> list[str]:
    texto = texto.lower()
    encontrados = []
    for ticker, (_, _, claves) in TODAS_LAS_ACCIONES.items():
        if any(re.search(rf"(?<!\w){re.escape(k)}(?!\w)", texto) for k in claves):
            encontrados.append(ticker)
    # "Acciona Energía" contiene "Acciona": no contar las dos.
    if "ANE.MC" in encontrados and "ANA.MC" in encontrados and "acciona energ" in texto \
            and texto.count("acciona") == texto.count("acciona energ"):
        encontrados.remove("ANA.MC")
    return encontrados


def analizar(noticia: Noticia) -> Noticia:
    """Rellena impacto, sentimiento, temas, explicaciones y empresas de una noticia."""
    texto = f"{noticia.titulo} {noticia.resumen}".lower()
    puntos = 0
    noticia.temas, noticia.explicaciones = [], []

    for patron, peso, explicacion in TEMAS_MACRO:
        if re.search(patron, texto):
            puntos += peso
            noticia.explicaciones.append(explicacion)

    noticia.empresas = detectar_empresas(texto)
    if noticia.empresas:
        puntos += 1
        for patron, peso, explicacion in TEMAS_EMPRESA:
            if re.search(patron, texto):
                puntos += peso
                noticia.explicaciones.append(explicacion)

    if re.search(r"ibex|wall street|s&p|nasdaq|dow jones|euro stoxx|dax|bolsas?|stocks?|markets?", texto):
        puntos += 1
        noticia.temas.append("Índices")

    pos = _contar(texto, PALABRAS_POSITIVAS)
    neg = _contar(texto, PALABRAS_NEGATIVAS)
    noticia.sentimiento = 1 if pos > neg else -1 if neg > pos else 0
    if abs(pos - neg) >= 2:
        puntos += 1

    # Si muchos medios publican lo mismo, es más relevante.
    if noticia.repeticiones >= 3:
        puntos += 2
    elif noticia.repeticiones == 2:
        puntos += 1

    # Las noticias recientes pesan más.
    h = noticia.horas
    if h is not None:
        if h <= 3:
            puntos += 2
        elif h <= 12:
            puntos += 1
        elif h > 48:
            puntos -= 2

    noticia.impacto = max(0, min(10, puntos))
    noticia.explicaciones = list(dict.fromkeys(noticia.explicaciones))
    return noticia


def _fecha(entrada) -> datetime | None:
    for clave in ("published_parsed", "updated_parsed"):
        t = entrada.get(clave)
        if t:
            return datetime.fromtimestamp(calendar.timegm(t), tz=timezone.utc)
    return None


def _leer_feed(url: str):
    import feedparser
    import requests

    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0 (asistente-bolsa)"})
        r.raise_for_status()
        return feedparser.parse(r.content).entries
    except Exception:  # noqa: BLE001 - una fuente caída no debe tumbar la app
        return []


def combinar(brutas: list[Noticia], max_horas: float | None = 72) -> list[Noticia]:
    """Une noticias repetidas entre fuentes (contando cuántas la publican), las analiza y ordena."""
    unicas: dict[str, Noticia] = {}
    for n in brutas:
        if max_horas is not None and n.horas is not None and n.horas > max_horas:
            continue
        clave = clave_titulo(n.titulo)
        if not clave:
            continue
        if clave in unicas:
            previa = unicas[clave]
            previa.repeticiones += 1
            if n.fecha and (not previa.fecha or n.fecha < previa.fecha):
                previa.fecha = n.fecha  # nos quedamos con la hora de publicación original
        else:
            unicas[clave] = n
    lista = [analizar(n) for n in unicas.values()]
    minimo = datetime.min.replace(tzinfo=timezone.utc)
    lista.sort(key=lambda n: (n.impacto, n.fecha or minimo), reverse=True)
    return lista


def descargar(fuentes: dict[str, str] | None = None, max_por_fuente: int = 40,
              extra: list[Noticia] | None = None, max_horas: float | None = 72) -> tuple[list[Noticia], list[str]]:
    """Descarga en paralelo todas las fuentes. Devuelve (noticias ordenadas por impacto, fuentes que fallaron)."""
    fuentes = fuentes or FUENTES_RSS
    with ThreadPoolExecutor(max_workers=12) as pool:
        resultados = dict(zip(fuentes, pool.map(_leer_feed, fuentes.values())))
    brutas, fallos = list(extra or []), []
    for nombre, entradas in resultados.items():
        if not entradas:
            fallos.append(nombre)
            continue
        for e in entradas[:max_por_fuente]:
            titulo = _limpiar(e.get("title", ""))
            if titulo:
                brutas.append(Noticia(titulo=titulo, enlace=e.get("link", ""), fuente=nombre,
                                      fecha=_fecha(e), resumen=_limpiar(e.get("summary", ""))[:400]))
    return combinar(brutas, max_horas), fallos


def fuentes_empresa(ticker: str, nombre: str) -> dict[str, str]:
    """Fuentes específicas de una empresa: Google News en español e inglés y Yahoo Finance."""
    nombre = nombre.split(" (")[0]
    fuentes = {
        "Google News": url_google_news(f'"{nombre}"', 7),
        "Google News (EN)": url_google_news(f'"{nombre}" stock', 7, ingles=True),
        "Yahoo Finance": url_yahoo(ticker),
    }
    return fuentes


def sentimiento_medio(noticias: list[Noticia]) -> float:
    """Media ponderada por impacto del sentimiento (-1 a +1)."""
    peso = sum(max(n.impacto, 1) for n in noticias)
    if not peso:
        return 0.0
    return sum(n.sentimiento * max(n.impacto, 1) for n in noticias) / peso


def frescura(lista: list[Noticia], ahora: datetime | None = None) -> dict:
    """Minutos desde la noticia más reciente, en total y por fuente (para comprobar que llegan al momento)."""
    ahora = ahora or datetime.now(timezone.utc)
    por_fuente: dict[str, float] = {}
    for n in lista:
        if not n.fecha:
            continue
        minutos = max((ahora - n.fecha).total_seconds() / 60, 0.0)
        fuente = n.fuente.split(" · ")[0]
        por_fuente[fuente] = min(por_fuente.get(fuente, minutos), minutos)
    reciente = min(por_fuente.values()) if por_fuente else None
    return {"minutos": reciente, "por_fuente": dict(sorted(por_fuente.items(), key=lambda x: x[1]))}


def hace_cuanto(n: Noticia) -> str:
    h = n.horas
    if h is None:
        return "fecha desconocida"
    if h < 1:
        return f"hace {max(1, int(h * 60))} min"
    if h < 48:
        return f"hace {int(h)} h"
    return f"hace {int(h / 24)} días"
