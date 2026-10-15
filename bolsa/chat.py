"""Chat bursátil con Claude (API de Anthropic) y un modo sin conexión que siempre responde.

- Con clave de API: Claude responde con el contexto de tu cartera y del mercado, y puede consultar datos al
  momento de cualquier valor (precio, tendencia, RSI, PER, veredicto de la app...).
- Sin clave o sin saldo: responde con el diccionario y las guías de la app, y te prepara la pregunta (con tu
  contexto) para pegarla en claude.ai, que tiene un plan gratuito.

La API se paga aparte de la suscripción de claude.ai: se recarga saldo en console.anthropic.com y se paga por
uso (unos céntimos por pregunta).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Callable

from . import aprendizaje

# Modelos que puede elegir el usuario. Precios en $ por millón de tokens (entrada, salida).
MODELOS = {
    "claude-opus-5-5": {"nombre": "Claude Opus 5.5 (el más preciso)", "precio": (4.00, 20.00)},
    "claude-haiku-5-5": {"nombre": "Claude Haiku 5.5 (rápido y muy barato)", "precio": (0.10, 0.50)},
}
MODELO_POR_DEFECTO = "claude-opus-5-5"
# Los reintentos automáticos en otro modelo si el principal declina responder (solo Opus 5.5 aquí).
CON_FALLBACK = {"claude-opus-5-5"}
MAX_TURNOS_HISTORIA = 20

SISTEMA = """Eres el asistente de una app educativa de bolsa para un inversor particular en España con \
conocimientos básicos. Respondes preguntas técnicas bursátiles: análisis técnico y fundamental, órdenes, \
fiscalidad española, fondos, ETF, renta fija, oro, criptomonedas, gestión del riesgo y de la cartera.

Cómo responder:
- En español de España, claro y directo. Explica cada término técnico la primera vez que salga, con un \
ejemplo en euros cuando ayude.
- Ve al grano: primero la respuesta, luego el porqué. Usa listas cortas y negritas solo para lo importante.
- Sé preciso. Si la pregunta depende de datos actuales de un valor (precio, tendencia, RSI, PER...), usa la \
herramienta `datos_valor` en lugar de suponer; si no sabes el código, usa `buscar_valor`. Si un dato no está \
disponible, dilo. Nunca inventes cifras.
- Ten en cuenta el contexto del usuario que se adjunta (su cartera, su perfil, su bróker y el estado del \
mercado) cuando sea relevante, y relaciónalo con la pregunta.
- Sé honesto con la incertidumbre: nadie puede predecir la bolsa. Da escenarios y riesgos, no certezas ni \
recomendaciones de "compra ya". Si la pregunta es de alto riesgo (apalancamiento, CFD, todo el dinero en un \
valor), explica el riesgo con números.
- Fiscalidad: España, base del ahorro (19 % hasta 6.000 €, 21 % hasta 50.000 €, 23 % hasta 200.000 €, 27 % \
hasta 300.000 €, 30 % más). Recuerda la regla de los 2 meses y la compensación de pérdidas cuando aplique.
- Eres una herramienta educativa, no un asesor financiero registrado en la CNMV. No lo repitas en cada \
respuesta; menciónalo solo si te piden una recomendación personal concreta."""

HERRAMIENTAS = [
    {
        "name": "datos_valor",
        "description": "Datos actuales de un valor cotizado (acción, ETF, fondo, índice, oro, criptomoneda) a "
                       "partir de su código de Yahoo Finance (p. ej. SAN.MC, ITX.MC, AAPL, IWDA.AS, BTC-EUR, "
                       "^IBEX, GC=F): precio, variaciones, tendencia frente a la media de 200 sesiones, RSI, "
                       "volatilidad, distancia al máximo, PER, dividendo, opinión de analistas y el veredicto y "
                       "la nota de la app si los tiene.",
        "eager_input_streaming": True,
        "input_schema": {
            "type": "object",
            "properties": {"ticker": {"type": "string", "description": "Código de Yahoo Finance"}},
            "required": ["ticker"],
            "additionalProperties": False,
        },
    },
    {
        "name": "buscar_valor",
        "description": "Busca el código de Yahoo Finance de una empresa, fondo o ETF por su nombre o su ISIN.",
        "eager_input_streaming": True,
        "input_schema": {
            "type": "object",
            "properties": {"consulta": {"type": "string", "description": "Nombre o ISIN"}},
            "required": ["consulta"],
            "additionalProperties": False,
        },
    },
]

PATRON_TICKER = re.compile(r"^[\^A-Za-z0-9.\-=]{1,20}$")


@dataclass
class Uso:
    entrada: int = 0
    salida: int = 0
    cache: int = 0
    modelo: str = MODELO_POR_DEFECTO

    def coste_usd(self) -> float:
        p_in, p_out = MODELOS.get(self.modelo, MODELOS[MODELO_POR_DEFECTO])["precio"]
        return (self.entrada * p_in + self.cache * p_in * 0.1 + self.salida * p_out) / 1e6


@dataclass
class Resultado:
    texto: str = ""
    uso: Uso = field(default_factory=Uso)
    herramientas: list[str] = field(default_factory=list)
    rechazada: bool = False


def contexto_usuario(fecha: str, broker: str, perfil: str | None, cartera: list[dict] | None,
                     diagnostico: dict | None, mercado: dict | None, activos: list[dict] | None) -> str:
    """Resumen corto (y sin datos personales identificativos) que se envía a Claude junto a la pregunta."""
    lineas = [f"Fecha: {fecha}. Bróker del usuario: {broker}. Perfil inversor: {perfil or 'sin calcular'}."]
    if cartera:
        total = sum(p["valor"] for p in cartera) or 1
        lineas.append("Su cartera (peso · ganancia desde la compra):")
        for p in sorted(cartera, key=lambda x: -x["valor"]):
            lineas.append(f"- {p['nombre']} ({p['ticker']}, {p['clase']}): {p['valor'] / total * 100:.0f} % · "
                          + f"{p['ganancia_pct']:+.1f} %".replace(".", ",")
                          + (f" · stop {_n(p['stop'])}" if p.get("stop") else " · sin stop"))
        lineas.append(f"Valor total aproximado: {total:,.0f} €.".replace(",", "."))
    else:
        lineas.append("No ha importado su cartera.")
    if diagnostico and diagnostico.get("hallazgos"):
        graves = [h["titulo"] for h in diagnostico["hallazgos"] if h["gravedad"] in ("alta", "media")][:5]
        if graves:
            lineas.append("Diagnóstico de la app: " + "; ".join(graves) + ".")
    if mercado:
        lineas.append(f"Mercado: semáforo {mercado.get('semaforo', '?')}"
                      + (f", VIX {mercado['vix']:.1f}" if mercado.get("vix") else "") + ".")
    if activos:
        lineas.append("Lectura de activos: " + " ".join(a["lectura"] for a in activos[:11]))
    return "\n".join(lineas)


def ejecutar_herramienta(nombre: str, entrada, datos_valor: Callable[[str], dict],
                         buscar_valor: Callable[[str], dict | None]) -> tuple[str, bool]:
    """Devuelve (contenido, es_error). Valida la entrada del modelo antes de usarla."""
    if not isinstance(entrada, dict):
        return json.dumps({"INVALID_JSON": str(entrada)}), True
    if nombre == "datos_valor":
        ticker = entrada.get("ticker")
        if not isinstance(ticker, str) or not PATRON_TICKER.match(ticker.strip()):
            return "Código no válido. Usa un código de Yahoo Finance como SAN.MC o AAPL.", True
        try:
            datos = datos_valor(ticker.strip().upper() if not ticker.startswith("^") else ticker.strip())
        except Exception as e:  # noqa: BLE001 - un fallo de datos se devuelve al modelo, no rompe el chat
            return f"No se pudieron obtener datos: {e}", True
        if not datos:
            return f"No hay datos para {ticker}. Comprueba el código (puedes usar buscar_valor).", True
        return json.dumps(datos, ensure_ascii=False, default=str), False
    if nombre == "buscar_valor":
        consulta = entrada.get("consulta")
        if not isinstance(consulta, str) or not consulta.strip() or len(consulta) > 100:
            return "Consulta no válida.", True
        try:
            hallado = buscar_valor(consulta.strip())
        except Exception as e:  # noqa: BLE001
            return f"No se pudo buscar: {e}", True
        return (json.dumps(hallado, ensure_ascii=False) if hallado else
                f"No se ha encontrado «{consulta}»."), not hallado
    return f"Herramienta desconocida: {nombre}", True


def conversar(cliente, modelo: str, historia: list[dict], pregunta: str, contexto: str,
              datos_valor: Callable[[str], dict], buscar_valor: Callable[[str], dict | None],
              al_escribir: Callable[[str], None] | None = None, max_vueltas: int = 6) -> Resultado:
    """Hace la pregunta a Claude (en streaming) y resuelve las consultas de datos que pida.
    `historia`: turnos anteriores [{'role', 'content': texto}]. No se modifica."""
    import anthropic

    res = Resultado(uso=Uso(modelo=modelo))
    sistema = [{"type": "text", "text": SISTEMA, "cache_control": {"type": "ephemeral"}},
               {"type": "text", "text": "Contexto del usuario (datos de la app, actualizados hoy):\n" + contexto}]
    mensajes = [*historia[-MAX_TURNOS_HISTORIA * 2:], {"role": "user", "content": pregunta}]
    extra = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"} if modelo in CON_FALLBACK else {}
    reintentos_json = 0
    for _ in range(max_vueltas):
        try:
            with cliente.beta.messages.stream(model=modelo, max_tokens=16000, system=sistema, messages=mensajes,
                                              tools=HERRAMIENTAS, thinking={"type": "adaptive"},
                                              output_config={"effort": "medium"}, **extra) as stream:
                for evento in stream:
                    if evento.type == "text" and al_escribir:
                        al_escribir(evento.text)
                respuesta = stream.get_final_message()
            reintentos_json = 0
        except ValueError:
            # JSON de una herramienta imposible de interpretar: se repite el turno (como mucho dos veces).
            reintentos_json += 1
            if reintentos_json > 2:
                raise
            continue
        except anthropic.APIError:
            raise
        u = respuesta.usage
        res.uso.entrada += u.input_tokens or 0
        res.uso.salida += u.output_tokens or 0
        res.uso.cache += getattr(u, "cache_read_input_tokens", 0) or 0
        texto = "".join(b.text for b in respuesta.content if b.type == "text")
        if texto:
            res.texto += ("\n\n" if res.texto else "") + texto
        if respuesta.stop_reason == "refusal":
            res.rechazada = True
            return res
        if respuesta.stop_reason == "pause_turn":
            mensajes.append({"role": "assistant", "content": respuesta.content})
            continue
        llamadas = [b for b in respuesta.content if b.type == "tool_use"]
        if not llamadas:
            return res
        if respuesta.stop_reason == "max_tokens":
            res.texto += "\n\n(La respuesta se ha cortado por ser demasiado larga.)"
            return res
        resultados = []
        for b in llamadas:
            contenido, error = ejecutar_herramienta(b.name, b.input, datos_valor, buscar_valor)
            res.herramientas.append(f"{b.name}({json.dumps(b.input, ensure_ascii=False)})")
            resultados.append({"type": "tool_result", "tool_use_id": b.id, "content": contenido,
                               **({"is_error": True} if error else {})})
        mensajes.append({"role": "assistant", "content": respuesta.content})
        mensajes.append({"role": "user", "content": resultados})
    res.texto += "\n\n(He parado tras varias consultas de datos seguidas.)"
    return res


def explicar_error(error: Exception) -> tuple[str, bool]:
    """(mensaje para el usuario, ¿pasar al modo sin conexión?)."""
    import anthropic

    texto = str(getattr(error, "message", error))
    if isinstance(error, anthropic.AuthenticationError):
        return "La clave de la API no es válida o se ha revocado. Revísala en console.anthropic.com.", True
    if isinstance(error, anthropic.PermissionDeniedError):
        return "La clave no tiene permiso para usar este modelo.", True
    if isinstance(error, anthropic.BadRequestError) and "credit" in texto.lower():
        return ("Se ha acabado el saldo de la API. Puedes recargarlo en console.anthropic.com → Billing; mientras "
                "tanto, respondo con el diccionario y te preparo la pregunta para claude.ai."), True
    if isinstance(error, anthropic.RateLimitError):
        return "Demasiadas preguntas seguidas. Espera un minuto y vuelve a intentarlo.", False
    if isinstance(error, anthropic.APIConnectionError):
        return "No hay conexión con Claude ahora mismo.", True
    if isinstance(error, anthropic.APIStatusError) and error.status_code >= 500:
        return "El servicio de Claude está saturado o caído. Inténtalo en unos minutos.", True
    return f"Error de la API: {texto}", True


# --------------------------------------------------------------------------- modo sin conexión
VACIAS = {"como", "cómo", "para", "pero", "porque", "cuál", "cual", "cuando", "cuándo", "donde", "dónde", "esta",
          "este", "esto", "estos", "estas", "tengo", "tiene", "hacer", "hago", "puedo", "debo", "quiero", "sobre",
          "entre", "desde", "hasta", "bien", "más", "menos", "muy", "algo", "cosa", "pongo", "poner", "significa",
          "quiere", "decir", "explica", "explícame", "dime", "funciona", "conviene", "mejor", "peor", "cuánto",
          "cuanto", "ahora", "hoy", "mucho", "poco", "todo", "todos", "nada", "también", "empresa", "empresas", "acción",
          "acciones", "bolsa", "dinero", "invertir", "inversión", "precio", "comprar", "vender", "compro", "vendo",
          "españa", "español", "española", "cartera", "meter", "sentido", "tiene", "diferencia", "algo", "orden", "está", "están", "estoy", "sería", "debería"}


def respuesta_sin_conexion(pregunta: str) -> str:
    """Respuesta con el contenido de la app (diccionario y guías) para cuando no hay API."""
    palabras = [w for w in re.findall(r"[\wáéíóúñü\-/&]+", pregunta.lower()) if len(w) > 3 and w not in VACIAS]
    vistos, terminos = set(), []
    # Primero términos cuyo nombre o alias aparece en la pregunta; si no hay, por palabras sueltas.
    for t in aprendizaje.GLOSARIO:
        nombres = [t.termino.lower(), *[a.lower() for a in aprendizaje.ALIAS.get(t.termino, ())]]
        if any(re.search(rf"(?<![\w]){re.escape(n)}(?![\w])", pregunta.lower()) for n in nombres):
            terminos.append(t)
            vistos.add(t.termino)
    if not terminos:
        for w in palabras:
            en_nombre = [x for x in aprendizaje.buscar(w) if re.search(rf"\b{re.escape(w)}\b", x.termino.lower())]
            for t in en_nombre[:2] + aprendizaje.parecidos(w, 1, corte=0.85):
                if t.termino not in vistos and len(terminos) < 3:
                    terminos.append(t)
                    vistos.add(t.termino)
    guias = []
    for w in palabras:
        for g in aprendizaje.buscar_guias(w):
            if w in g.titulo.lower() and g not in guias and len(guias) < 2:
                guias.append(g)
    if not terminos and not guias:
        return ("No tengo esa respuesta en el diccionario de la app. Copia la pregunta preparada de abajo y pégala "
                "en claude.ai (tiene plan gratuito).")
    partes = ["**Esto dice la app sobre tu pregunta** (respuesta sin conexión a Claude):"]
    for t in terminos[:4]:
        partes.append(f"**{t.termino}**: {t.definicion}" + (f"\n> 💡 {t.ejemplo}" if t.ejemplo else ""))
    for g in guias:
        partes.append(f"**Guía: {g.titulo}**\n" + "\n".join(f"{i}. {p}" for i, p in enumerate(g.pasos, 1)))
    return "\n\n".join(partes)


# Activos que se reconocen por su nombre en la pregunta (además de las empresas de la app).
ACTIVOS_POR_NOMBRE = {"oro": "GC=F", "gold": "GC=F", "plata": "SI=F", "bitcoin": "BTC-EUR", "btc": "BTC-EUR",
                      "ethereum": "ETH-EUR", "ibex": "^IBEX", "ibex 35": "^IBEX", "s&p": "^GSPC", "s&p 500": "^GSPC",
                      "sp500": "^GSPC", "nasdaq": "^IXIC", "euro stoxx": "^STOXX50E", "dax": "^GDAXI",
                      "petróleo": "BZ=F", "petroleo": "BZ=F", "brent": "BZ=F", "msci world": "IWDA.AS",
                      "fondo indexado mundial": "IWDA.AS"}
PATRON_MI_CARTERA = re.compile(r"\b(mi|mis)\s+(cartera|acciones|dinero|inversi\w*|posici\w*|valores|ahorros)\b")


def valores_en_pregunta(pregunta: str, maximo: int = 3) -> list[str]:
    from .noticias import detectar_empresas

    p = pregunta.lower()
    tickers = list(detectar_empresas(p))
    for nombre, t in ACTIVOS_POR_NOMBRE.items():
        if re.search(rf"(?<![\w]){re.escape(nombre)}(?![\w])", p) and t not in tickers:
            tickers.append(t)
    for codigo in re.findall(r"\b[A-Z]{2,5}(?:\.[A-Z]{1,2})\b", pregunta):   # códigos como IDR.MC
        if codigo not in tickers:
            tickers.append(codigo)
    return tickers[:maximo]


def _n(x, dec=2) -> str:
    return f"{x:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


OPINIONES = {"strong_buy": "compra fuerte", "buy": "comprar", "outperform": "mejor que el mercado", "hold": "mantener",
             "underperform": "peor que el mercado", "sell": "vender", "strong_sell": "venta fuerte", "none": "sin opinión"}


def describir_valor(d: dict) -> str:
    """Los datos de `datos_valor` explicados en lenguaje sencillo."""
    from .costes import simbolo

    moneda = simbolo(d["ticker"])
    precio = f"{_n(d['ultimo_cierre'])} {moneda}" if moneda not in ("—", "") else _n(d["ultimo_cierre"])
    variaciones = [f"{etiqueta} {d[k]:+.1f} %".replace(".", ",") for k, etiqueta in
                   (("variacion_1d_pct", "último día"), ("variacion_1m_pct", "un mes"), ("variacion_1a_pct", "un año"))
                   if d.get(k) is not None]
    lineas = [f"**{d['nombre'].split(' (')[0]}** ({d['ticker']}): último cierre {precio} ({'/'.join(reversed(d['fecha'].split('-')))})"
              + (f" · {', '.join(variaciones)}." if variaciones else ".")]
    if d.get("tendencia"):
        lineas.append(f"- **Tendencia**: {d['tendencia']}.")
    if d.get("rsi_14") is not None:
        r = d["rsi_14"]
        zona = ("sobrecompra: ha subido muy deprisa y a veces se toma un respiro" if r >= 70 else
                "sobreventa: ha caído muy deprisa y a veces rebota" if r <= 30 else "zona neutral")
        lineas.append(f"- **RSI**: {_n(r, 0)} → {zona} (más de 70 = sobrecompra, menos de 30 = sobreventa).")
    if d.get("distancia_al_maximo_1a_pct") is not None:
        dm = d["distancia_al_maximo_1a_pct"]
        lineas.append("- **Máximo del año**: " + ("está en máximos." if dm > -2 else f"está un {_n(-dm, 0)} % por debajo."))
    if d.get("volatilidad_anual_pct"):
        v = d["volatilidad_anual_pct"]
        lineas.append(f"- **Volatilidad**: {_n(v, 0)} % al año ("
                      + ("se mueve más que la bolsa en general, ~15 %" if v > 20 else "parecida o menor que la bolsa")
                      + ").")
    f = d.get("fundamentales") or {}
    partes = []
    if f.get("PER"):
        partes.append(f"PER {_n(f['PER'], 1)}")
    if f.get("rentabilidad por dividendo"):
        partes.append(f"dividendo {_n(f['rentabilidad por dividendo'] * 100, 1)} %")
    if f.get("opinión de analistas"):
        n = f.get("número de analistas")
        opinion = OPINIONES.get(str(f["opinión de analistas"]).lower(), f["opinión de analistas"])
        partes.append(f"analistas: {opinion}" + (f" ({n} analistas)" if n else ""))
    if partes:
        lineas.append("- **Empresa**: " + ", ".join(partes) + ".")
    a = d.get("app")
    if a:
        lineas.append(f"- **Veredicto de la app**: {a['veredicto']}"
                      + (f" · nota {a['nota_0_100']}/100" if a.get("nota_0_100") is not None else "")
                      + (f" · riesgo de caída {a['riesgo_de_caida']}" if a.get("riesgo_de_caida") else "")
                      + f". {a['explicacion']}")
    return "\n".join(lineas)


def _limites_alternativos(pregunta: str, contexto: str) -> list[str]:
    """Si preguntas por oro o cripto en tu cartera: cuánto es prudente según tu perfil."""
    from .activos import LIMITES_ALTERNATIVOS

    p = pregunta.lower()
    if not any(w in p for w in ("oro", "bitcoin", "cripto", "ethereum", "gold", "btc")):
        return []
    perfil = next((x for x in LIMITES_ALTERNATIVOS if f"Perfil inversor: {x}" in contexto), None)
    limites = LIMITES_ALTERNATIVOS[perfil or "Moderado"]
    quien = f"tu perfil {perfil.lower()}" if perfil else "un perfil moderado (calcula el tuyo en 🎯 Mi plan)"
    return [f"**Cuánto es prudente**: para {quien}, como mucho un "
            f"{limites['Oro y materias primas'] * 100:.0f} % de tu dinero en oro y un "
            f"{limites['Criptomonedas'] * 100:.0f} % en criptomonedas. Son complementos para diversificar, no el "
            "núcleo de la cartera (ese papel lo hace un fondo indexado mundial)."]


def respuesta_gratis(pregunta: str, contexto: str, datos_valor: Callable[[str], dict] | None = None) -> str:
    """Asistente gratuito: datos reales de los valores que nombras, tu cartera y el diccionario de la app."""
    partes = []
    for t in valores_en_pregunta(pregunta):
        try:
            d = datos_valor(t) if datos_valor else None
        except Exception:  # noqa: BLE001 - sin datos de un valor, se sigue con el resto
            d = None
        if d:
            partes.append(describir_valor(d))
    if PATRON_MI_CARTERA.search(pregunta.lower()) and contexto:
        utiles = [x for x in contexto.splitlines() if x.startswith(("- ", "Valor total", "Diagnóstico", "Su cartera",
                                                                    "No ha importado"))]
        if utiles:
            partes.append("**Tu cartera según la app**\n" + "\n".join(utiles).replace("Su cartera", "Tu cartera"))
        partes += _limites_alternativos(pregunta, contexto)
    teoria = respuesta_sin_conexion(pregunta)
    if not teoria.startswith("No tengo"):
        partes.append(teoria.split("\n\n", 1)[1] if "\n\n" in teoria else teoria)
    if not partes:
        return teoria
    return "\n\n".join(partes)


def pregunta_para_claude_ai(pregunta: str, contexto: str) -> str:
    """Texto listo para pegar en claude.ai (plan gratuito) con el mismo enfoque y contexto que el chat."""
    return (f"{SISTEMA}\n\n(No tienes herramientas de datos: si necesitas un precio o un indicador actual, "
            f"dime qué dato buscar.)\n\nMi contexto:\n{contexto}\n\nMi pregunta: {pregunta}")


__all__ = ["respuesta_gratis", "describir_valor", "valores_en_pregunta", "MODELOS", "MODELO_POR_DEFECTO", "SISTEMA", "HERRAMIENTAS", "Uso", "Resultado", "contexto_usuario",
           "ejecutar_herramienta", "conversar", "explicar_error", "respuesta_sin_conexion",
           "pregunta_para_claude_ai"]
