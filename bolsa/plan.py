"""🎯 Mi plan: qué hacer con un dinero concreto según para qué lo quieres, leyendo el mercado del día.

Cuatro objetivos, cada uno con su forma de invertir:
- crecer: reparto a largo plazo (fondo indexado, renta fija, acciones del día y, si te interesan, oro o cripto con
  límites prudentes);
- operacion: unas pocas ideas del día (acciones, divisas, oro, cripto, ETF) con precio de entrada, stop-loss,
  objetivo y cuánto comprar para no perder más de lo que eliges;
- rentas: empresas con buen dividendo y renta fija / letras, con los euros que cobrarías al año;
- proteger: monetario, letras y renta fija a corto, con un poco de oro.

Las ideas salen del informe diario (nota global, tendencia, riesgo de caída, stop y objetivo de cada acción) y de la
tendencia de hoy de divisas, oro, cripto y fondos. No hay magia: la app ha comprobado con datos reales que adivinar si
algo sube o baja a corto plazo funciona poco mejor que el azar; lo que sí ayuda es seguir la tendencia, evitar lo que
tiene mucho riesgo de caída y cortar las pérdidas con un stop-loss.
"""

from __future__ import annotations

import math

import pandas as pd

OBJETIVOS = {
    "crecer": "Hacer crecer mis ahorros a largo plazo (3 años o más)",
    "operacion": "Una operación: comprar ahora y vender en semanas o meses",
    "rentas": "Cobrar rentas cada año (dividendos o intereses)",
    "proteger": "Proteger mi dinero: poco riesgo, que no pierda valor",
}
PLAZOS = {"1-4 semanas": 20, "1-3 meses": 63, "3-12 meses": 189}
INTERESES = ["Acciones españolas", "Acciones de Europa y EEUU", "Divisas", "Oro", "Criptomonedas",
             "Fondos indexados y ETF"]
INTERESES_POR_DEFECTO = {"crecer": ["Fondos indexados y ETF", "Acciones españolas"],
                         "operacion": ["Acciones españolas", "Acciones de Europa y EEUU"],
                         "rentas": ["Acciones españolas"], "proteger": []}

DIVISAS = {"EURUSD=X": ("dólar estadounidense", "USD"), "EURGBP=X": ("libra esterlina", "GBP"),
           "EURCHF=X": ("franco suizo", "CHF"), "EURJPY=X": ("yen japonés", "JPY")}
FEMENINAS = {"GBP"}


def frente_a(codigo: str) -> str:
    """«al dólar estadounidense», «a la libra esterlina»..."""
    nombre = next(n for n, c in DIVISAS.values() if c == codigo)
    return f"a la {nombre}" if codigo in FEMENINAS else f"al {nombre}"
ALTERNATIVOS = {
    "Oro": [("4GLD.DE", "Oro físico (ETC en euros)",
             "ETC de oro físico en Xetra (código 4GLD). En Bankinter: Bróker → ETF/ETC → busca «Xetra-Gold».")],
    "Criptomonedas": [("BTC-EUR", "Bitcoin",
                       "En Bankinter no se compran criptomonedas directamente: o un ETP de bitcoin cotizado en bolsa "
                       "(busca «Bitcoin ETP» en el bróker) o una plataforma regulada (MiCA)."),
                      ("ETH-EUR", "Ethereum", "Igual que bitcoin: ETP cotizado en bolsa o plataforma regulada (MiCA).")],
    "Fondos indexados y ETF": [
        ("IWDA.AS", "Fondo indexado mundial (MSCI World)",
         "Fondo indexado MSCI World (sin comisión de compra en Bankinter) o el ETF IWDA en Ámsterdam."),
        ("SXR8.DE", "Bolsa de EEUU (S&P 500)", "Fondo indexado S&P 500 o el ETF SXR8 en Xetra."),
        ("EXSA.DE", "Bolsa europea (Stoxx Europe 600)", "Fondo indexado europeo o el ETF EXSA en Xetra.")],
}
TIPO_INTERES = {"Oro": "Oro", "Criptomonedas": "Cripto", "Fondos indexados y ETF": "Fondo/ETF"}
MINIMO_OPERACION = 500.0          # menos que esto por idea: las comisiones pesan demasiado
STOP_RANGOS, OBJETIVO_RANGOS = 3, 6   # stop a 3 rangos diarios medios y objetivo a 6 (gana el doble de lo que arriesga)
MAX_IDEAS_OPERACION = 4


# --------------------------------------------------------------------------- utilidades
def atr(df: pd.DataFrame, n: int = 14) -> float | None:
    """Rango medio diario (máximo − mínimo), para poner stops que no salten por el ruido normal."""
    if df is None or len(df) < n + 1:
        return None
    rango = (df["High"] - df["Low"]).iloc[-n:]
    valor = float(rango.mean())
    if not math.isfinite(valor) or valor <= 0:   # algunas divisas no traen máximos y mínimos
        valor = float(df["Close"].diff().abs().iloc[-n:].mean()) * 1.5
    return valor if math.isfinite(valor) and valor > 0 else None


def tendencia(df: pd.DataFrame) -> dict | None:
    """Precio, tendencia (media de 200 sesiones y de 50), variación de 1 y 12 meses."""
    if df is None or len(df) < 60:
        return None
    c = df["Close"].dropna()
    precio = float(c.iloc[-1])
    m200 = float(c.iloc[-200:].mean()) if len(c) >= 200 else None
    m50 = float(c.iloc[-50:].mean())
    return {"precio": precio, "alcista": (precio > m200 and m50 > m200) if m200 else precio > m50,
            "bajista": (precio < m200 and m50 < m200) if m200 else precio < m50,
            "var_1m": precio / float(c.iloc[-22]) - 1 if len(c) > 22 else None,
            "var_1a": precio / float(c.iloc[-253]) - 1 if len(c) > 253 else None}


def _pct(x: float | None) -> str:
    return "—" if x is None else f"{x * 100:+.1f} %".replace(".", ",")


def _idea(tipo, ticker, nombre, precio, stop, objetivo, por_que, como, nota=None, moneda="€", **extra) -> dict:
    return {"tipo": tipo, "ticker": ticker, "nombre": nombre, "precio": precio, "entrada": precio, "stop": stop,
            "objetivo": objetivo, "riesgo_pct": abs(precio - stop) / precio if precio and stop else None,
            "beneficio_pct": abs(objetivo - precio) / precio if precio and objetivo else None,
            "por_que": por_que, "como": como, "nota": nota, "moneda": moneda, **extra}


# --------------------------------------------------------------------------- ideas del día
def ideas_acciones(ranking: list[dict], nacionales: bool, n: int = 3, con_resultados: bool = False) -> list[dict]:
    """Acciones con buena nota, tendencia al alza y sin riesgo alto de caída, de sectores distintos."""
    candidatas = [r for r in ranking if not r.get("etf") and r.get("precio") and r.get("stop")
                  and str(r["ticker"]).endswith(".MC") == nacionales and (r.get("nota") or 0) >= 70
                  and r.get("riesgo_nivel") != "alto" and r.get("mercado_alcista") is not False
                  and (con_resultados or not r.get("resultados_pronto"))]
    candidatas.sort(key=lambda r: -(r.get("nota") or 0))
    salida, sectores = [], set()
    for r in candidatas:
        if r.get("sector") in sectores:
            continue
        sectores.add(r.get("sector"))
        objetivo = r.get("objetivo") or r["precio"] + 2 * (r["precio"] - r["stop"])
        rango = ""
        if r.get("p10_1m") is not None and r.get("p90_1m") is not None:
            rango = (f" En situaciones parecidas del pasado, en un mes lo normal fue entre {_pct(r['p10_1m'])} y "
                     f"{_pct(r['p90_1m'])}.")
        por_que = (f"Nota {r['nota']}/100 entre {r.get('de', 'todas las')} acciones: ha subido {_pct(r.get('momentum'))} "
                   f"en un año, su tendencia es alcista y su riesgo de caída es {r.get('riesgo_nivel', '—')}.{rango}")
        moneda = "€" if nacionales or r.get("divisa") in (None, "EUR") else r.get("divisa")
        salida.append(_idea("Acción", r["ticker"], r["nombre"], r["precio"], r["stop"], objetivo, por_que,
                            "Orden limitada en tu bróker con el stop-loss puesto en cuanto se ejecute.",
                            r.get("nota"), moneda, sector=r.get("sector"), dividendo=r.get("dividendo"),
                            precio_eur=r.get("precio_eur"), riesgo_nivel=r.get("riesgo_nivel")))
        if len(salida) >= n:
            break
    return salida


def ideas_dividendo(ranking: list[dict], n: int = 5, minimo: float = 0.035) -> list[dict]:
    """Empresas españolas con buen dividendo y sin riesgo alto de caída, de sectores distintos."""
    candidatas = [r for r in ranking if str(r["ticker"]).endswith(".MC") and not r.get("etf")
                  and (r.get("dividendo") or 0) >= minimo and r.get("riesgo_nivel") != "alto"
                  and (r.get("nota") or 0) >= 40 and r.get("precio")]
    candidatas.sort(key=lambda r: (-(r.get("dividendo") or 0)))
    salida, sectores = [], set()
    for r in candidatas:
        if r.get("sector") in sectores:
            continue
        sectores.add(r.get("sector"))
        por_que = (f"Paga alrededor de un {r['dividendo'] * 100:.1f} % al año en dividendos".replace(".", ",")
                   + f", con riesgo de caída {r.get('riesgo_nivel', '—')} y nota {r.get('nota')}/100.")
        stop = r.get("stop") or r["precio"] * 0.85
        salida.append(_idea("Acción (dividendo)", r["ticker"], r["nombre"], r["precio"], stop,
                            r.get("objetivo") or r["precio"] * 1.15, por_que,
                            "Compra con orden limitada y mantenla: el dividendo se cobra solo en tu cuenta.",
                            r.get("nota"), dividendo=r["dividendo"], sector=r.get("sector"),
                            riesgo_nivel=r.get("riesgo_nivel")))
        if len(salida) >= n:
            break
    return salida


def idea_alternativo(clave: str, ticker: str, nombre: str, como: str, df: pd.DataFrame) -> dict | None:
    """Oro, cripto o fondo: solo si hoy está en tendencia alcista, con stop y objetivo según su rango diario."""
    t, rango = tendencia(df), atr(df)
    if not t or not rango or not t["alcista"]:
        return None
    precio = t["precio"]
    stop, objetivo = precio - STOP_RANGOS * rango, precio + OBJETIVO_RANGOS * rango
    por_que = (f"En tendencia alcista: {_pct(t['var_1m'])} en un mes y {_pct(t['var_1a'])} en un año, por encima de "
               "sus medias de 50 y 200 sesiones.")
    return _idea(TIPO_INTERES[clave], ticker, nombre, precio, stop, objetivo, por_que, como)


def idea_divisa(par: str, df: pd.DataFrame) -> dict | None:
    """Comprar la otra divisa cuando el euro se debilita frente a ella (el par EUR/XXX en tendencia bajista)."""
    if par not in DIVISAS:
        return None
    t, rango = tendencia(df), atr(df)
    if not t or not rango or not t["bajista"]:
        return None
    nombre, codigo = DIVISAS[par]
    precio = t["precio"]
    # Si el euro vuelve a subir (el par sube), la idea se ha roto: ese es el stop.
    stop, objetivo = precio + STOP_RANGOS * rango, precio - OBJETIVO_RANGOS * rango
    articulo = "La" if codigo in FEMENINAS else "El"
    por_que = (f"{articulo} {nombre} se está fortaleciendo frente al euro: el EUR/{codigo} va a la baja "
               f"({_pct(t['var_1m'])} en un mes, {_pct(t['var_1a'])} en un año).")
    como = (f"Cambia euros a {codigo} en una cuenta en divisa de tu banco o compra un fondo/ETF que cotice en {codigo}. "
            f"Sal si el EUR/{codigo} sube por encima del stop. Los CFD y el forex con apalancamiento no son para "
            "empezar: puedes perder más de lo que pones.")
    return _idea("Divisa", par, f"Comprar {nombre} ({codigo})", precio, stop, objetivo, por_que, como,
                 moneda=f"EUR/{codigo}", divisa=True)


def ideas_del_dia(intereses: list[str], ranking: list[dict], historicos: dict[str, pd.DataFrame],
                  con_resultados: bool = False) -> tuple[list[dict], list[str]]:
    """Ideas de hoy para los intereses elegidos y, para los que no tienen idea hoy, por qué."""
    ideas, sin_idea = [], []
    if "Acciones españolas" in intereses:
        x = ideas_acciones(ranking, True, con_resultados=con_resultados)
        ideas += x
        if not x:
            sin_idea.append("Acciones españolas: hoy ninguna cumple a la vez buena nota, tendencia al alza y riesgo "
                            "de caída bajo o normal.")
    if "Acciones de Europa y EEUU" in intereses:
        x = ideas_acciones(ranking, False, n=2, con_resultados=con_resultados)
        ideas += x
        if not x:
            sin_idea.append("Acciones de Europa y EEUU: hoy ninguna cumple todas las condiciones.")
    for clave in ("Oro", "Criptomonedas", "Fondos indexados y ETF"):
        if clave not in intereses:
            continue
        x = [i for i in (idea_alternativo(clave, t, n, c, historicos.get(t)) for t, n, c in ALTERNATIVOS[clave]) if i]
        ideas += x
        if not x:
            sin_idea.append(f"{clave}: hoy no está en tendencia alcista. Mejor esperar a que la recupere que intentar "
                            "adivinar el suelo.")
    if "Divisas" in intereses:
        x = [i for i in (idea_divisa(p, historicos.get(p)) for p in DIVISAS) if i]
        ideas += x
        if not x:
            sin_idea.append("Divisas: hoy ninguna se está fortaleciendo con claridad frente al euro. Para un "
                            "inversor en euros, no hay motivo para cambiar de moneda.")
    return ideas, sin_idea


# --------------------------------------------------------------------------- planes por objetivo
def _variadas(ideas: list[dict]) -> list[dict]:
    """Primero la mejor de cada tipo (acción, divisa, oro, cripto, fondo) y luego el resto por nota: así una
    operación no acaba siendo solo acciones si también te interesan otras cosas."""
    grupos: dict[str, list[dict]] = {}
    for i in sorted(ideas, key=lambda x: -(x.get("nota") or 60)):
        grupos.setdefault(i["tipo"].split(" (")[0], []).append(i)
    salida = []
    while any(grupos.values()):
        for g in list(grupos):
            if grupos[g]:
                salida.append(grupos[g].pop(0))
    return salida


def plan_operacion(importe: float, perdida_max: float, ideas: list[dict], maximo: int = MAX_IDEAS_OPERACION) -> dict:
    """Reparte `importe` entre las mejores ideas de modo que, si saltan todos los stops, no pierdas más de
    `perdida_max` (fracción del importe). Lo que no se invierte queda en liquidez."""
    ideas = _variadas([i for i in ideas if i.get("riesgo_pct")])
    n = min(maximo, len(ideas), max(int(importe // MINIMO_OPERACION), 1))
    elegidas, avisos = ideas[:n], []
    if not elegidas:
        return {"posiciones": [], "liquidez": importe, "riesgo_total": 0.0, "avisos": avisos}
    riesgo_cada = importe * perdida_max / len(elegidas)
    tope_cada = importe / len(elegidas)
    posiciones = []
    for i in elegidas:
        euros = min(riesgo_cada / i["riesgo_pct"], tope_cada)
        posiciones.append({**i, "euros": euros, "perdida_si_stop": euros * i["riesgo_pct"],
                           "ganancia_si_objetivo": euros * (i.get("beneficio_pct") or 0)})
    invertido = sum(p["euros"] for p in posiciones)
    if len(ideas) > n and n < maximo:
        avisos.append(f"Con {importe:,.0f} € caben {n} idea(s) sin que las comisiones pesen demasiado "
                      f"(unos {MINIMO_OPERACION:,.0f} € por idea como mínimo).".replace(",", "."))
    return {"posiciones": posiciones, "liquidez": importe - invertido,
            "riesgo_total": sum(p["perdida_si_stop"] for p in posiciones),
            "ganancia_objetivo": sum(p["ganancia_si_objetivo"] for p in posiciones), "avisos": avisos}


REPARTO_RENTAS = {"Conservador": 0.30, "Moderado": 0.50, "Dinámico": 0.70}   # parte en acciones con dividendo


def plan_rentas(importe: float, perfil: str, ideas: list[dict], interes_liquidez: float,
                minimo_por_empresa: float = 1000.0) -> dict:
    """Acciones con dividendo + renta fija / letras, con los euros que cobrarías al año (brutos)."""
    parte_acciones = importe * REPARTO_RENTAS.get(perfil, 0.5)
    n = min(len(ideas), int(parte_acciones // minimo_por_empresa))
    acciones = [{**i, "euros": parte_acciones / n} for i in ideas[:n]] if n else []
    resto = importe - sum(a["euros"] for a in acciones)
    renta_acciones = sum(a["euros"] * (a.get("dividendo") or 0) for a in acciones)
    renta_fija = resto * max(interes_liquidez, 0.0)
    return {"acciones": acciones, "renta_fija": resto, "renta_anual": renta_acciones + renta_fija,
            "renta_acciones": renta_acciones, "renta_liquidez": renta_fija,
            "rentabilidad": (renta_acciones + renta_fija) / importe if importe else 0.0}


def plan_proteger(importe: float, oro: bool = True) -> list[dict]:
    """Poco riesgo: monetario y letras, renta fija a corto y, si quieres, un poco de oro."""
    partes = [("Monetario / Letras del Tesoro", 0.60 if oro else 0.65, "XEON.DE"),
              ("Renta fija a corto plazo", 0.35, "IBGS.AS")]
    if oro:
        partes.append(("Oro", 0.05, "4GLD.DE"))
    return [{"parte": p, "pct": round(w * 100), "euros": importe * w, "ticker": t} for p, w, t in partes]


def satelites(perfil: str, intereses: list[str], limites: dict[str, dict[str, float]]) -> dict[str, float]:
    """Para el largo plazo: un poco de oro o cripto si te interesan, sin pasar de los límites prudentes del perfil."""
    lim = limites.get(perfil, {})
    salida = {}
    if "Oro" in intereses and lim.get("Oro y materias primas"):
        salida["Oro"] = lim["Oro y materias primas"]
    if "Criptomonedas" in intereses and lim.get("Criptomonedas"):
        salida["Criptomonedas"] = lim["Criptomonedas"]
    return salida


__all__ = ["OBJETIVOS", "PLAZOS", "INTERESES", "INTERESES_POR_DEFECTO", "DIVISAS", "ALTERNATIVOS", "atr", "frente_a",
           "tendencia", "ideas_acciones", "ideas_dividendo", "idea_alternativo", "idea_divisa", "ideas_del_dia",
           "plan_operacion", "plan_rentas", "plan_proteger", "satelites", "REPARTO_RENTAS"]
