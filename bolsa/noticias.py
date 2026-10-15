"""Noticias de última hora: descarga de fuentes RSS, puntuación de impacto y explicación sencilla.

No usa inteligencia artificial: aplica reglas transparentes (palabras clave) para que
siempre puedas ver *por qué* una noticia se considera importante.
"""

from __future__ import annotations

import calendar
import html
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import quote_plus

from .tickers import TODAS_LAS_ACCIONES

FUENTES_RSS = {
    "Expansión - Mercados": "https://e00-expansion.uecdn.es/rss/mercados.xml",
    "elEconomista - Mercados": "https://www.eleconomista.es/rss/rss-mercados.php",
    "Cinco Días - Mercados": "https://cincodias.elpais.com/rss/cincodias/mercados/",
    "Investing.com España": "https://es.investing.com/rss/news_25.rss",
    "Google News - Bolsa": "https://news.google.com/rss/search?q=bolsa+OR+ibex+OR+%22wall+street%22+when:1d&hl=es&gl=ES&ceid=ES:es",
}


def url_google_news(consulta: str) -> str:
    """Feed de Google News para una empresa concreta (últimos 7 días)."""
    return f"https://news.google.com/rss/search?q={quote_plus(consulta)}+when:7d&hl=es&gl=ES&ceid=ES:es"


# Temas que mueven a TODO el mercado. (expresión regular, peso, explicación para principiantes)
TEMAS_MACRO = [
    (r"\bbce\b|banco central europeo|lagarde", 3,
     "El BCE decide los tipos de interés en Europa. Bajadas de tipos suelen animar la bolsa; "
     "subidas la frenan (aunque a los bancos les ayudan los tipos altos)."),
    (r"\bfed\b|reserva federal|powell|\bfomc\b", 3,
     "La Reserva Federal fija los tipos en EEUU. Lo que hace la Fed mueve a todas las bolsas del mundo."),
    (r"tipos de inter[eé]s|subida de tipos|bajada de tipos|recorte de tipos|euribor", 3,
     "Los tipos de interés son el 'precio del dinero'. Tipos más bajos = empresas y familias "
     "se endeudan más barato = suele ser bueno para la bolsa."),
    (r"inflaci[oó]n|\bipc\b|\bpce\b", 2,
     "Si la inflación sube más de lo esperado, los bancos centrales pueden subir tipos, y eso suele hacer caer la bolsa."),
    (r"empleo|paro|n[oó]minas|payrolls|desempleo", 2,
     "El dato de empleo indica la salud de la economía. Se publica en EEUU el primer viernes de cada mes."),
    (r"\bpib\b|recesi[oó]n|crecimiento econ[oó]mico", 2,
     "El PIB mide cuánto crece la economía. Una recesión (PIB cayendo) suele traer caídas en bolsa."),
    (r"aranceles?|guerra comercial|proteccionismo", 3,
     "Los aranceles encarecen el comercio entre países. Suelen provocar caídas, sobre todo en exportadoras."),
    (r"guerra|conflicto|ataque|geopol[ií]tic|invasi[oó]n|misil", 2,
     "Los conflictos generan incertidumbre: suelen bajar las bolsas y subir el petróleo y el oro."),
    (r"petr[oó]leo|brent|\bopep\b", 2,
     "El precio del petróleo afecta a petroleras (Repsol), aerolíneas (IAG) y a la inflación."),
    (r"desplome|hundimiento|p[aá]nico|crash|batacazo|sell-?off", 2,
     "Indica caídas fuertes. Para el inversor a largo plazo, los desplomes pueden ser oportunidades, "
     "pero nunca compres todo de golpe en plena caída."),
    (r"r[eé]cord|m[aá]ximos hist[oó]ricos|m[aá]ximos anuales", 1,
     "El mercado está en máximos: buen momento para el que ya estaba dentro; para entrar, mejor ir poco a poco."),
    (r"prima de riesgo|bono a 10 a[nñ]os|rentabilidad del bono", 1,
     "La prima de riesgo mide la desconfianza en la deuda de un país. Si sube, suele afectar a la banca española."),
    (r"china|yuan", 1, "China es la segunda economía mundial; sus problemas afectan a materias primas y lujo."),
    (r"inteligencia artificial|\bia\b|chips?|semiconductor", 1,
     "La IA es el gran motor de las tecnológicas de EEUU (Nvidia, Microsoft...)."),
]

# Eventos de empresa (cuando la noticia nombra una empresa concreta).
TEMAS_EMPRESA = [
    (r"resultados|beneficio|ganancias|facturaci[oó]n|ventas|trimestre", 2,
     "Resultados trimestrales: lo que importa es si son mejores o peores *de lo que esperaba el mercado*."),
    (r"\bopa\b|oferta p[uú]blica|fusi[oó]n|adquisici[oó]n|compra de", 3,
     "OPA/fusión: una empresa quiere comprar otra. La comprada suele subir; la compradora a veces baja."),
    (r"dividendo", 2,
     "El dividendo es el dinero que la empresa reparte a sus accionistas. El día que se paga, la acción baja ese importe."),
    (r"recompra de acciones|recompra", 1,
     "La empresa compra sus propias acciones: reduce el número de acciones y suele apoyar la cotización."),
    (r"rebaja.*(recomendaci[oó]n|precio objetivo|rating)|recorta.*precio objetivo|vender", 2,
     "Un analista rebaja su opinión. Puede presionar el precio a corto plazo."),
    (r"eleva.*(recomendaci[oó]n|precio objetivo)|mejora.*recomendaci[oó]n|sube.*precio objetivo|comprar", 2,
     "Un analista mejora su opinión. Suele impulsar la acción a corto plazo."),
    (r"ampliaci[oó]n de capital", 2,
     "La empresa emite acciones nuevas para captar dinero: diluye a los accionistas y suele bajar el precio."),
    (r"profit warning|rebaja.*previsiones|recorta.*previsiones", 3,
     "La empresa avisa de que ganará menos de lo previsto: suele provocar caídas fuertes."),
    (r"eleva.*previsiones|mejora.*previsiones", 2, "La empresa espera ganar más de lo previsto: buena señal."),
]

PALABRAS_POSITIVAS = [
    "sube", "suben", "subida", "alza", "alzas", "dispara", "disparan", "gana", "ganan", "récord", "record",
    "máximos", "maximos", "rebote", "rebota", "mejora", "mejoran", "supera", "superan", "optimismo",
    "repunte", "repunta", "avanza", "avanzan", "impulsa", "impulso", "crece", "crecen", "beneficio",
    "bajada de tipos", "recorte de tipos", "eleva", "verde", "euforia", "fuerte demanda",
]
PALABRAS_NEGATIVAS = [
    "cae", "caen", "caída", "caida", "baja", "bajan", "desplome", "desploma", "hunde", "hunden",
    "pierde", "pierden", "pérdidas", "perdidas", "mínimos", "minimos", "temor", "temores", "miedo",
    "recorta", "rebaja", "incertidumbre", "crisis", "recesión", "recesion", "aranceles", "guerra",
    "pánico", "panico", "retrocede", "retroceden", "rojo", "decepciona", "advierte", "subida de tipos",
    "profit warning", "sanción", "multa", "investigación", "investigacion", "huelga",
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

    if re.search(r"ibex|wall street|s&p|nasdaq|dow jones|euro stoxx|dax|bolsas?", texto):
        puntos += 1
        noticia.temas.append("Índices")

    pos = _contar(texto, PALABRAS_POSITIVAS)
    neg = _contar(texto, PALABRAS_NEGATIVAS)
    noticia.sentimiento = 1 if pos > neg else -1 if neg > pos else 0
    if abs(pos - neg) >= 2:
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
    # Quitar explicaciones duplicadas conservando el orden.
    noticia.explicaciones = list(dict.fromkeys(noticia.explicaciones))
    return noticia


def _fecha(entrada) -> datetime | None:
    for clave in ("published_parsed", "updated_parsed"):
        t = entrada.get(clave)
        if t:
            return datetime.fromtimestamp(calendar.timegm(t), tz=timezone.utc)
    return None


def descargar(fuentes: dict[str, str] | None = None, max_por_fuente: int = 30) -> tuple[list[Noticia], list[str]]:
    """Descarga y analiza noticias. Devuelve (noticias ordenadas por impacto, fuentes que fallaron)."""
    import feedparser

    fuentes = fuentes or FUENTES_RSS
    noticias, fallos, vistos = [], [], set()
    for nombre, url in fuentes.items():
        try:
            feed = feedparser.parse(url, agent="Mozilla/5.0 (asistente-bolsa)")
        except Exception:  # noqa: BLE001 - una fuente caída no debe tumbar la app
            fallos.append(nombre)
            continue
        if not feed.entries:
            fallos.append(nombre)
            continue
        for e in feed.entries[:max_por_fuente]:
            titulo = _limpiar(e.get("title", ""))
            clave = re.sub(r"\W+", "", titulo.lower())[:80]
            if not titulo or clave in vistos:
                continue
            vistos.add(clave)
            n = Noticia(titulo=titulo, enlace=e.get("link", ""), fuente=nombre,
                        fecha=_fecha(e), resumen=_limpiar(e.get("summary", ""))[:400])
            noticias.append(analizar(n))
    noticias.sort(key=lambda n: (n.impacto, n.fecha or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
    return noticias, fallos


def sentimiento_medio(noticias: list[Noticia]) -> float:
    """Media ponderada por impacto del sentimiento (-1 a +1)."""
    peso = sum(max(n.impacto, 1) for n in noticias)
    if not peso:
        return 0.0
    return sum(n.sentimiento * max(n.impacto, 1) for n in noticias) / peso


def hace_cuanto(n: Noticia) -> str:
    h = n.horas
    if h is None:
        return "fecha desconocida"
    if h < 1:
        return f"hace {max(1, int(h * 60))} min"
    if h < 48:
        return f"hace {int(h)} h"
    return f"hace {int(h / 24)} días"


__all__ = ["Noticia", "FUENTES_RSS", "analizar", "descargar", "detectar_empresas",
           "sentimiento_medio", "hace_cuanto", "url_google_news"]
