"""Motor de decisiones: convierte indicadores y noticias en una puntuación de 0 a 100,
un veredicto y una explicación en lenguaje llano.

Importante: es un sistema de reglas sencillas y transparentes. Ayuda a no comprar
en mal momento y a tener un plan (precio de entrada, stop-loss y objetivo), pero no
adivina el futuro. Ningún sistema lo hace.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from .indicadores import calcular_todo, variacion, volatilidad_anual


@dataclass
class Motivo:
    puntos: int
    titulo: str
    explicacion: str

    @property
    def icono(self) -> str:
        return "🟢" if self.puntos > 0 else "🔴" if self.puntos < 0 else "⚪"


@dataclass
class Plan:
    entrada: float
    stop: float
    objetivo: float
    riesgo_pct: float          # % que perderías si salta el stop
    beneficio_pct: float       # % que ganarías si llega al objetivo


@dataclass
class Evaluacion:
    ticker: str
    precio: float
    puntuacion: int
    veredicto: str
    color: str
    resumen: str
    motivos: list[Motivo] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    plan: Plan | None = None
    datos: dict = field(default_factory=dict)


VEREDICTOS = [
    (70, "Zona de compra", "green",
     "Las señales acompañan. Si te gusta la empresa, puedes comprar con un plan: "
     "pon una orden limitada y un stop-loss."),
    (55, "Interesante: compra escalonada", "orange",
     "Hay más señales a favor que en contra, pero no todas. Si quieres entrar, hazlo poco a poco "
     "(por ejemplo, un tercio ahora y el resto en las próximas semanas)."),
    (40, "Esperar", "gray",
     "Las señales están mezcladas. No hay prisa: espera a que la tendencia se aclare."),
    (0, "Evitar por ahora", "red",
     "La acción está en tendencia bajista o con señales negativas. Comprar ahora es intentar "
     "'coger un cuchillo que cae'. Mejor esperar."),
]


def _veredicto(puntos: int) -> tuple[str, str, str]:
    for minimo, texto, color, resumen in VEREDICTOS:
        if puntos >= minimo:
            return texto, color, resumen
    return VEREDICTOS[-1][1:]


def _ok(x) -> bool:
    return x is not None and not (isinstance(x, float) and math.isnan(x))


def evaluar(ticker: str, historico: pd.DataFrame, sentimiento_noticias: float | None = None,
            n_noticias: int = 0, mercado_alcista: bool | None = None,
            fundamentales: dict | None = None, prediccion=None) -> Evaluacion:
    """Evalúa una acción.

    historico: DataFrame diario con Open/High/Low/Close/Volume (ideal: 1-2 años).
    sentimiento_noticias: -1..+1, media de las noticias recientes sobre la empresa.
    mercado_alcista: True si el índice de referencia está por encima de su media de 200 sesiones.
    """
    df = calcular_todo(historico.dropna(subset=["Close"]))
    u = df.iloc[-1]
    precio = float(u["Close"])
    puntos = 50
    motivos: list[Motivo] = []
    avisos: list[str] = []

    def add(p: int, titulo: str, explicacion: str):
        nonlocal puntos
        puntos += p
        motivos.append(Motivo(p, titulo, explicacion))

    sma50, sma200, rsi_v = u["SMA50"], u["SMA200"], u["RSI"]
    alcista_largo = _ok(sma200) and precio > sma200

    # 1) Tendencia de fondo (lo más importante).
    if _ok(sma200):
        dist = (precio / sma200 - 1) * 100
        if alcista_largo:
            add(15, "Tendencia de fondo alcista",
                f"El precio ({precio:.2f}) está un {dist:.1f}% por encima de su media de 200 sesiones "
                f"({sma200:.2f}). La media de 200 resume el último año: estar por encima indica que, "
                "en el largo plazo, la acción va hacia arriba.")
        else:
            add(-15, "Tendencia de fondo bajista",
                f"El precio está un {abs(dist):.1f}% por debajo de su media de 200 sesiones ({sma200:.2f}). "
                "Comprar acciones en tendencia bajista es arriesgado: lo barato puede abaratarse más.")
    else:
        avisos.append("Hay menos de 200 sesiones de historial: la tendencia de fondo no se puede valorar bien.")

    # 2) Cruce de medias.
    if _ok(sma50) and _ok(sma200):
        if sma50 > sma200:
            add(8, "Media de 50 por encima de la de 200",
                "Se conoce como 'cruce dorado' (golden cross): la tendencia de los últimos meses es más "
                "fuerte que la del último año. Señal positiva clásica.")
        else:
            add(-8, "Media de 50 por debajo de la de 200",
                "Se conoce como 'cruce de la muerte' (death cross): los últimos meses van peor que el último año.")

    # 3) Tendencia a medio plazo.
    if _ok(sma50):
        if precio > sma50:
            add(5, "Por encima de la media de 50 sesiones",
                "En los últimos 2-3 meses el precio también va bien.")
        else:
            add(-5, "Por debajo de la media de 50 sesiones",
                "En los últimos 2-3 meses el precio ha perdido fuerza.")

    # 4) RSI: ¿está cara o barata a corto plazo?
    if _ok(rsi_v):
        if rsi_v < 30:
            if alcista_largo:
                add(12, f"RSI en {rsi_v:.0f}: sobrevendida dentro de una tendencia alcista",
                    "El RSI mide si una acción ha subido o bajado 'demasiado rápido' (escala de 0 a 100). "
                    "Por debajo de 30 ha caído mucho en poco tiempo. Si la tendencia de fondo es buena, "
                    "suele ser una buena oportunidad de compra (comprar 'en la caída').")
            else:
                add(3, f"RSI en {rsi_v:.0f}: sobrevendida, pero en tendencia bajista",
                    "Ha caído mucho y podría rebotar, pero como la tendencia de fondo es mala, "
                    "el rebote puede ser solo temporal.")
        elif rsi_v < 45:
            add(6 if alcista_largo else 0, f"RSI en {rsi_v:.0f}: precio relajado",
                "La acción no está 'recalentada'. Si la tendencia es buena, es un punto de entrada razonable.")
        elif rsi_v <= 65:
            add(2, f"RSI en {rsi_v:.0f}: zona neutral", "Ni cara ni barata a corto plazo.")
        elif rsi_v <= 70:
            add(-3, f"RSI en {rsi_v:.0f}: empieza a calentarse",
                "Ha subido bastante en poco tiempo. Puede seguir, pero el margen es menor.")
        else:
            add(-10, f"RSI en {rsi_v:.0f}: sobrecomprada",
                "Ha subido muy deprisa. Es habitual que corrija (baje un poco) antes de seguir. "
                "Mejor no perseguir el precio: espera un recorte.")

    # 5) MACD: impulso.
    hist = df["histograma"].dropna()
    if len(hist) >= 2:
        if hist.iloc[-1] > 0 and hist.iloc[-2] <= 0:
            add(8, "El impulso acaba de girar al alza (cruce MACD)",
                "El MACD compara una media rápida y una lenta. Acaba de cruzar hacia arriba: "
                "el precio empieza a acelerar al alza.")
        elif hist.iloc[-1] < 0 and hist.iloc[-2] >= 0:
            add(-8, "El impulso acaba de girar a la baja (cruce MACD)",
                "El MACD acaba de cruzar hacia abajo: el precio pierde fuerza.")
        elif hist.iloc[-1] > 0:
            add(4, "Impulso positivo (MACD)", "El precio mantiene aceleración al alza.")
        else:
            add(-4, "Impulso negativo (MACD)", "El precio mantiene aceleración a la baja.")

    # 6) Distancia a máximos y mínimos del año.
    max52, min52 = u["Max52"], u["Min52"]
    if _ok(max52) and _ok(min52) and max52 > min52:
        desde_max = (precio / max52 - 1) * 100
        if desde_max > -3 and _ok(rsi_v) and rsi_v > 65:
            avisos.append(f"Está muy cerca de sus máximos del año ({max52:.2f}) y recalentada: "
                          "no hay descuento. Si compras, hazlo en varias veces.")
        elif desde_max < -35:
            avisos.append(f"Cotiza un {abs(desde_max):.0f}% por debajo de su máximo del año. "
                          "Antes de comprar, busca en las noticias POR QUÉ ha caído tanto.")

    # 7) Noticias.
    if sentimiento_noticias is not None and n_noticias > 0:
        if sentimiento_noticias > 0.25:
            add(6, f"Noticias recientes positivas ({n_noticias})",
                "La mayoría de titulares recientes sobre la empresa son favorables.")
        elif sentimiento_noticias < -0.25:
            add(-6, f"Noticias recientes negativas ({n_noticias})",
                "La mayoría de titulares recientes son desfavorables. Léelos antes de decidir.")
        else:
            add(0, f"Noticias recientes mixtas ({n_noticias})", "No hay un tono claro en los titulares.")

    # 8) Ambiente general del mercado.
    if mercado_alcista is True:
        add(4, "El mercado en general acompaña",
            "El índice de referencia está en tendencia alcista: 'la marea sube todos los barcos'.")
    elif mercado_alcista is False:
        add(-6, "El mercado en general está débil",
            "El índice de referencia está por debajo de su media de 200 sesiones. En mercados bajistas "
            "incluso las buenas empresas suelen caer.")

    # 9) Fundamentales y analistas.
    if fundamentales:
        for p, titulo, explicacion in _motivos_fundamentales(fundamentales, precio):
            add(p, titulo, explicacion)
        avisos.extend(_avisos_fundamentales(fundamentales))

    # 10) Modelo estadístico (solo puntúa si ha demostrado acertar más que el azar).
    if prediccion is not None:
        prob = prediccion.prob_subida * 100
        if prediccion.fiabilidad in ("Alta", "Media"):
            peso = 1.0 if prediccion.fiabilidad == "Alta" else 0.6
            p = int(round(max(-10, min(10, (prob - 50) * 0.5)) * peso))
            add(p, f"Modelo estadístico: {prob:.0f}% de probabilidad de subir en {prediccion.horizonte.lower()}",
                f"En situaciones pasadas parecidas, subió en el {prob:.0f}% de los casos. Su fiabilidad para esta "
                f"acción es {prediccion.fiabilidad.lower()}: acertó el {prediccion.acierto * 100:.0f}% de las veces "
                f"en {prediccion.pruebas} pruebas con datos pasados.")
        else:
            add(0, f"Modelo estadístico: {prob:.0f}% (no fiable para esta acción)",
                "En las pruebas con datos pasados el modelo no acertó más que el azar con esta acción, "
                "así que no se tiene en cuenta en la puntuación.")

    # Volatilidad: no puntúa, pero avisa.
    vol = volatilidad_anual(df["Close"])
    if _ok(vol) and vol > 40:
        avisos.append(f"Acción muy volátil (≈{vol:.0f}% anual): puede moverse mucho en pocos días. "
                      "Invierte una cantidad menor.")

    puntos = int(max(0, min(100, round(puntos))))
    veredicto, color, resumen = _veredicto(puntos)

    plan = None
    atr_v = u["ATR"]
    if _ok(atr_v) and atr_v > 0:
        stop = precio - 2 * atr_v
        if _ok(sma200) and alcista_largo and sma200 < precio and sma200 > stop - atr_v:
            stop = min(stop, sma200 * 0.99)  # dejar margen bajo la media de 200 si está cerca
        stop = max(stop, precio * 0.80)      # nunca arriesgar más de un 20%
        objetivo = precio + 2 * (precio - stop)
        plan = Plan(entrada=precio, stop=stop, objetivo=objetivo,
                    riesgo_pct=(1 - stop / precio) * 100,
                    beneficio_pct=(objetivo / precio - 1) * 100)

    datos = {
        "rsi": float(rsi_v) if _ok(rsi_v) else None,
        "sma50": float(sma50) if _ok(sma50) else None,
        "sma200": float(sma200) if _ok(sma200) else None,
        "volatilidad": vol if _ok(vol) else None,
        "var_1d": variacion(df["Close"], 1),
        "var_1m": variacion(df["Close"], 21),
        "var_1a": variacion(df["Close"], 252),
        "max52": float(max52) if _ok(max52) else None,
        "min52": float(min52) if _ok(min52) else None,
    }
    return Evaluacion(ticker, precio, puntos, veredicto, color, resumen, motivos, avisos, plan, datos)


RECOMENDACIONES = {
    "strong_buy": "Compra fuerte", "buy": "Comprar", "hold": "Mantener",
    "underperform": "Peor que el mercado", "sell": "Vender", "strong_sell": "Venta fuerte",
}


def _motivos_fundamentales(f: dict, precio: float) -> list[tuple[int, str, str]]:
    out = []
    objetivo, n = f.get("targetMeanPrice"), f.get("numberOfAnalystOpinions") or 0
    if objetivo and n >= 3 and precio > 0:
        pot = (objetivo / precio - 1) * 100
        rec = RECOMENDACIONES.get(f.get("recommendationKey", ""), "—")
        texto = (f"{n} analistas profesionales siguen la empresa. Su precio objetivo medio es {objetivo:.2f} "
                 f"({pot:+.0f}% desde el precio actual) y su recomendación media es '{rec}'. "
                 "Los analistas se equivocan a menudo, pero su consenso es una referencia útil.")
        if pot > 15:
            out.append((6, f"Los analistas ven un {pot:.0f}% de recorrido", texto))
        elif pot > 5:
            out.append((3, f"Los analistas ven un {pot:.0f}% de recorrido", texto))
        elif pot < -5:
            out.append((-6, f"Cotiza por encima del objetivo de los analistas ({pot:.0f}%)", texto))
        else:
            out.append((0, "Cotiza cerca del objetivo de los analistas", texto))
    per = f.get("forwardPE") or f.get("trailingPE")
    if per is not None:
        if per <= 0:
            out.append((-4, "La empresa no gana dinero (PER negativo)",
                        "El PER compara el precio con los beneficios. Si es negativo, la empresa está en pérdidas."))
        elif per < 12:
            out.append((3, f"PER {per:.1f}: barata respecto a lo que gana",
                        "El PER indica cuántos años de beneficios pagas al comprar la acción. Por debajo de 12 "
                        "se considera barato (aunque a veces es barato por algo)."))
        elif per > 40:
            out.append((-3, f"PER {per:.0f}: cara respecto a lo que gana",
                        "Pagas más de 40 años de beneficios: el mercado espera mucho crecimiento. "
                        "Si decepciona, puede caer con fuerza."))
    div = f.get("trailingAnnualDividendYield")
    if div and div > 0.04:
        out.append((2, f"Buen dividendo ({div * 100:.1f}% anual)",
                    "Reparte una parte importante de sus beneficios cada año: te pagan por esperar."))
    return out


def _avisos_fundamentales(f: dict) -> list[str]:
    avisos = []
    ts = f.get("earningsTimestampStart") or f.get("earningsTimestamp")
    if ts:
        dias = (ts - time.time()) / 86400
        if 0 <= dias <= 10:
            avisos.append(f"📅 Presenta resultados el {datetime.fromtimestamp(ts):%d/%m}. Ese día la acción puede "
                          "moverse mucho (±5-10%). Muchos prefieren esperar a ver los resultados antes de comprar.")
    return avisos


def estado_indice(historico: pd.DataFrame) -> dict:
    """Resumen sencillo del estado de un índice."""
    c = historico["Close"].dropna()
    sma200 = c.rolling(200, min_periods=200).mean().iloc[-1] if len(c) >= 200 else float("nan")
    sma50 = c.rolling(50, min_periods=50).mean().iloc[-1] if len(c) >= 50 else float("nan")
    precio = float(c.iloc[-1])
    alcista = bool(_ok(sma200) and precio > sma200)
    if not _ok(sma200):
        texto = "Sin historial suficiente."
    elif alcista and _ok(sma50) and precio > sma50:
        texto = "Tendencia alcista sana: por encima de sus medias de 50 y 200 sesiones."
    elif alcista:
        texto = "Tendencia de fondo alcista, pero en corrección a corto plazo (puede ser oportunidad)."
    elif _ok(sma50) and precio > sma50:
        texto = "Intentando recuperarse, pero aún por debajo de la media de 200: precaución."
    else:
        texto = "Tendencia bajista: el mercado está débil. Paciencia."
    return {"precio": precio, "alcista": alcista, "texto": texto,
            "var_1d": variacion(c, 1), "var_1m": variacion(c, 21), "var_1a": variacion(c, 252)}


def backtest_media200(historico: pd.DataFrame, comision_pct: float = 0.2) -> dict:
    """Compara 'comprar y mantener' con la regla sencilla 'estar dentro solo si el precio
    cierra por encima de su media de 200 sesiones'. Sirve para aprender, no para predecir."""
    c = historico["Close"].dropna()
    sma = c.rolling(200, min_periods=200).mean()
    validos = sma.notna()
    if validos.sum() < 50:
        return {}
    c, sma = c[validos], sma[validos]
    dentro = (c > sma).astype(int).shift(1).fillna(0)  # decide con el cierre de ayer
    rent = c.pct_change().fillna(0)
    cambios = dentro.diff().abs().fillna(dentro.iloc[0])
    estrategia = (1 + rent * dentro - cambios * comision_pct / 100).cumprod()
    mantener = c / c.iloc[0]

    def max_caida(curva: pd.Series) -> float:
        return float((curva / curva.cummax() - 1).min() * 100)

    return {
        "curva_estrategia": estrategia, "curva_mantener": mantener,
        "rent_estrategia": float((estrategia.iloc[-1] - 1) * 100),
        "rent_mantener": float((mantener.iloc[-1] - 1) * 100),
        "caida_estrategia": max_caida(estrategia), "caida_mantener": max_caida(mantener),
        "operaciones": int(cambios.sum()),
    }
