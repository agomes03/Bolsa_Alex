"""Simulador con dinero virtual y entrenamiento de la estrategia.

Cómo funciona, explicado fácil:

1. Se toma el histórico de muchas acciones (10 años) y, **día a día**, se calcula la puntuación que la
   app habría dado ese día usando solo la información disponible hasta entonces (nunca el futuro).
2. Un "operador virtual" sigue las reglas: compra en la apertura del día siguiente las acciones con
   puntuación alta, pone su stop-loss y su objetivo, vende si saltan o si la puntuación se estropea,
   paga comisiones e impuestos, y nunca arriesga más de lo indicado por operación.
3. **Entrenamiento (walk-forward)**: se prueban muchas combinaciones de reglas en un periodo de
   entrenamiento (p. ej. 3 años), se elige la que menos error de inversión tiene, y se comprueba
   en el año siguiente, que el entrenamiento NO ha visto. Se repite avanzando año a año. Lo que
   cuenta es el resultado en esos años "no vistos": es lo más parecido a operar de verdad.

Limitaciones honestas: no hay histórico gratuito de noticias ni de opiniones de analistas, así que la
simulación usa la parte técnica y el modelo estadístico; se usa la composición ACTUAL del IBEX
(sesgo de supervivencia: las empresas que salieron del índice por ir mal no aparecen).
"""

from __future__ import annotations

import itertools
import math
import random
from dataclasses import asdict, dataclass, fields
from typing import Callable

import numpy as np
import pandas as pd

from .costes import ITF_PCT, Tarifa
from .indicadores import calcular_todo
from .prediccion import serie_probabilidad


# --------------------------------------------------------------------------- parámetros
@dataclass(frozen=True)
class Parametros:
    umbral_compra: int = 70        # puntuación mínima para comprar
    umbral_venta: int = 40         # si la puntuación baja de aquí, se vende
    stop_atr: float = 2.0          # stop-loss a N veces el movimiento diario típico (ATR)
    ratio_objetivo: float = 2.0    # objetivo = N veces lo arriesgado (0 = sin objetivo, stop que sube)
    peso_modelo: float = 1.0       # cuánto cuenta el modelo estadístico (0 = nada)
    max_posiciones: int = 6        # nº máximo de acciones distintas a la vez
    riesgo_pct: float = 1.0        # % del dinero que se arriesga por operación

    def describir(self) -> list[str]:
        obj = ("sin objetivo fijo: el stop-loss va subiendo con el precio para dejar correr las ganancias"
               if self.ratio_objetivo == 0 else
               f"vende con beneficio cuando gana {self.ratio_objetivo:g} veces lo que arriesga")
        return [
            f"Compra cuando la puntuación llega a **{self.umbral_compra}** o más.",
            f"Vende si la puntuación cae por debajo de **{self.umbral_venta}**.",
            f"Stop-loss a **{self.stop_atr:g} veces** el movimiento diario típico (ATR).",
            f"Objetivo: {obj}.",
            "Modelo estadístico: " + ("**no se usa**." if self.peso_modelo == 0 else
                                      f"cuenta al **{self.peso_modelo * 100:.0f}%**."),
            f"Como mucho **{self.max_posiciones}** empresas a la vez, arriesgando un **{self.riesgo_pct:g}%** "
            "del dinero en cada una.",
        ]

    def a_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def desde_dict(cls, d: dict | None) -> "Parametros":
        validos = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in (d or {}).items() if k in validos})


ESPACIO = {
    "umbral_compra": [60, 65, 70, 75, 80],
    "umbral_venta": [30, 40, 50],
    "stop_atr": [1.5, 2.0, 2.5, 3.0],
    "ratio_objetivo": [0.0, 1.5, 2.0, 3.0],
    "peso_modelo": [0.0, 0.5, 1.0],
    "max_posiciones": [4, 6, 8],
}

OBJETIVOS: dict[str, Callable[[dict], float]] = {
    # Rentabilidad anual menos la mitad de la peor caída: premia ganar, castiga los sustos.
    "Equilibrado (recomendado)": lambda m: m["cagr_pct"] + 0.5 * m["max_caida_pct"],
    # Lo mínimo posible de caída, siempre que gane dinero.
    "Menos pérdidas": lambda m: m["max_caida_pct"] if m["cagr_pct"] > 0 else -100 + m["cagr_pct"],
    "Máxima rentabilidad": lambda m: m["cagr_pct"],
}


# --------------------------------------------------------------------------- puntuación vectorizada
def puntuacion_tecnica(d: pd.DataFrame, mercado: pd.Series | None = None) -> pd.Series:
    """Misma puntuación técnica que `senales.evaluar` (sin noticias, analistas ni modelo),
    calculada para TODOS los días a la vez. `d` debe venir de `calcular_todo`."""
    c, sma50, sma200, rsi = d["Close"], d["SMA50"], d["SMA200"], d["RSI"]
    v200, v50 = sma200.notna(), sma50.notna()
    alc = v200 & (c > sma200)
    p = np.full(len(d), 50.0)
    p += np.where(v200, np.where(c > sma200, 15, -15), 0)
    p += np.where(v50 & v200, np.where(sma50 > sma200, 8, -8), 0)
    p += np.where(v50, np.where(c > sma50, 5, -5), 0)
    p += np.select([rsi < 30, rsi < 45, rsi <= 65, rsi <= 70, rsi > 70],
                   [np.where(alc, 12, 3), np.where(alc, 6, 0), 2, -3, -10], default=0)
    h, hp = d["histograma"], d["histograma"].shift(1)
    m = np.select([(h > 0) & (hp <= 0), (h < 0) & (hp >= 0), h > 0], [8, -8, 4], default=-4)
    p += np.where(h.notna() & hp.notna(), m, 0)
    if mercado is not None:
        mk = mercado.reindex(d.index, method="ffill").astype(float).to_numpy()
        p += np.where(mk == 1, 4, np.where(mk == 0, -6, 0))
    return pd.Series(np.clip(p, 0, 100), index=d.index)


def mercado_alcista(indice: pd.DataFrame) -> pd.Series:
    """1 si el índice está por encima de su media de 200 sesiones, 0 si no, NaN si no se sabe."""
    c = indice["Close"]
    sma = c.rolling(200, min_periods=200).mean()
    return (c > sma).astype(float).where(sma.notna())


def aporte_modelo(prob: np.ndarray, peso: float) -> np.ndarray:
    a = np.round(np.clip((prob * 100 - 50) * 0.5, -10, 10) * peso)
    return np.nan_to_num(a)


# --------------------------------------------------------------------------- universo de datos
@dataclass
class Universo:
    fechas: pd.DatetimeIndex
    tickers: list[str]
    O: np.ndarray
    H: np.ndarray
    L: np.ndarray
    C: np.ndarray          # cierre (relleno hacia delante, para valorar)
    ATR: np.ndarray
    BASE: np.ndarray       # puntuación técnica (NaN si ese día no cotizó)
    PROB: np.ndarray       # probabilidad del modelo (NaN si aún no hay)
    inicio: int            # primer día operable (con medias de 200 calculadas)

    def indice_de(self, fecha) -> int:
        return int(self.fechas.searchsorted(pd.Timestamp(fecha), side="left"))


def preparar_universo(historicos: dict[str, pd.DataFrame], indice: pd.DataFrame | None = None,
                      con_modelo: bool = True, progreso: Callable[[float, str], None] | None = None) -> Universo:
    historicos = {t: df for t, df in historicos.items() if len(df) >= 300}
    if not historicos:
        raise ValueError("No hay datos suficientes para simular.")
    mercado = mercado_alcista(indice) if indice is not None and not indice.empty else None
    fechas = pd.DatetimeIndex(sorted(set().union(*[df.index for df in historicos.values()])))
    tickers = list(historicos)
    T, N = len(fechas), len(tickers)
    O, H, L, C, A, B, P = (np.full((T, N), np.nan) for _ in range(7))
    for j, t in enumerate(tickers):
        if progreso:
            progreso(j / N, f"Preparando {t}...")
        d = calcular_todo(historicos[t])
        base = puntuacion_tecnica(d, mercado)
        prob = serie_probabilidad(historicos[t]) if con_modelo else pd.Series(np.nan, index=d.index)
        r = d.reindex(fechas)
        O[:, j], H[:, j], L[:, j] = r["Open"], r["High"], r["Low"]
        C[:, j] = r["Close"].ffill()
        A[:, j] = r["ATR"].ffill()
        B[:, j] = base.reindex(fechas)
        P[:, j] = prob.reindex(fechas).ffill(limit=5)
    # Primer día en el que al menos la mitad de las acciones tienen su media de 200 calculada.
    sma_ok = np.array([pd.Series(C[:, j]).rolling(200).mean().notna().to_numpy() for j in range(N)]).T
    listo = np.nonzero((sma_ok & ~np.isnan(B) & ~np.isnan(A)).sum(axis=1) >= max(1, N // 2))[0]
    inicio = int(listo[0]) if len(listo) else 200
    if progreso:
        progreso(1.0, "Datos listos")
    return Universo(fechas, tickers, O, H, L, C, A, B, P, max(inicio, 1))


# --------------------------------------------------------------------------- motor de simulación
@dataclass
class Resultado:
    curva: pd.Series
    operaciones: pd.DataFrame
    metricas: dict
    abiertas: pd.DataFrame


def puntuaciones(u: Universo, p: Parametros) -> np.ndarray:
    return np.where(np.isnan(u.BASE), np.nan, np.clip(u.BASE + aporte_modelo(u.PROB, p.peso_modelo), 0, 100))


def simular(u: Universo, p: Parametros, tarifa: Tarifa, capital: float = 10_000.0,
            inicio: int | None = None, fin: int | None = None, liquidar: bool = True,
            score: np.ndarray | None = None) -> Resultado:
    """Opera con dinero virtual entre los días `inicio` y `fin` (índices de u.fechas).
    Decide con el cierre del día anterior y ejecuta en la apertura: nunca usa información futura."""
    T, N = u.C.shape
    inicio = max(inicio if inicio is not None else u.inicio, 1)
    fin = min(fin if fin is not None else T, T)
    S = puntuaciones(u, p) if score is None else score
    es_es = np.array([t.endswith(".MC") for t in u.tickers])
    Cv = np.nan_to_num(u.C)

    efectivo = float(capital)
    gastos_total = 0.0
    acc = np.zeros(N)
    entrada, stop, coste_ent = np.zeros(N), np.zeros(N), np.zeros(N)
    obj = np.full(N, np.inf)
    f_ent = np.zeros(N, dtype=int)
    curva = np.empty(max(fin - inicio, 0))
    ops: list[dict] = []

    def vender(j: int, precio: float, t: int, motivo: str):
        nonlocal efectivo, gastos_total
        importe = acc[j] * precio
        coste = tarifa.coste(importe)
        efectivo += importe - coste
        gastos_total += coste
        invertido = acc[j] * entrada[j] + coste_ent[j]
        resultado = importe - coste - invertido
        ops.append({"Empresa": u.tickers[j], "Compra": u.fechas[f_ent[j]], "Precio compra": entrada[j],
                    "Venta": u.fechas[t], "Precio venta": precio, "Acciones": int(acc[j]),
                    "Resultado €": resultado, "Resultado %": resultado / invertido * 100,
                    "Días": int(t - f_ent[j]), "Motivo": motivo})
        acc[j] = 0

    for t in range(inicio, fin):
        s_ant = S[t - 1]
        o_hoy = u.O[t]
        # 1) Ventas por señal (decididas ayer al cierre), en la apertura de hoy.
        for j in np.nonzero(acc > 0)[0]:
            if not np.isnan(o_hoy[j]) and not np.isnan(s_ant[j]) and s_ant[j] < p.umbral_venta:
                vender(j, o_hoy[j], t, "La puntuación bajó")
        # 2) Compras de las mejores candidatas.
        libres = p.max_posiciones - int((acc > 0).sum())
        if libres > 0:
            ok = (~np.isnan(s_ant)) & (s_ant >= p.umbral_compra) & (acc == 0) & ~np.isnan(o_hoy) \
                 & ~np.isnan(u.ATR[t - 1])
            cand = np.nonzero(ok)[0]
            cand = cand[np.argsort(-s_ant[cand], kind="stable")][:libres]
            patrimonio = efectivo + float((acc * Cv[t - 1]).sum())
            for j in cand:
                precio = float(o_hoy[j])
                st_ = max(precio - p.stop_atr * u.ATR[t - 1, j], precio * 0.80)
                riesgo_acc = precio - st_
                if riesgo_acc <= 0:
                    continue
                itf = ITF_PCT / 100 if es_es[j] else 0.0
                n = math.floor(min(patrimonio * p.riesgo_pct / 100 / riesgo_acc,
                                   patrimonio / p.max_posiciones / precio,
                                   max(efectivo - tarifa.minimo - tarifa.canon_fijo, 0)
                                   / (precio * (1 + itf + tarifa.pct / 100))))
                if n < 1:
                    continue
                importe = n * precio
                coste = tarifa.coste(importe) + importe * itf
                if importe + coste > efectivo:
                    continue
                efectivo -= importe + coste
                gastos_total += coste
                acc[j], entrada[j], stop[j], coste_ent[j], f_ent[j] = n, precio, st_, coste, t
                obj[j] = precio + p.ratio_objetivo * riesgo_acc if p.ratio_objetivo > 0 else np.inf
        # 3) Stop-loss y objetivos durante la sesión (si toca ambos, se asume lo peor: el stop).
        for j in np.nonzero(acc > 0)[0]:
            o, h, l = u.O[t, j], u.H[t, j], u.L[t, j]
            if np.isnan(o):
                continue
            if o <= stop[j]:
                vender(j, o, t, "Stop-loss (abrió por debajo)")
            elif l <= stop[j]:
                vender(j, stop[j], t, "Stop-loss")
            elif o >= obj[j]:
                vender(j, o, t, "Objetivo alcanzado")
            elif h >= obj[j]:
                vender(j, obj[j], t, "Objetivo alcanzado")
            elif p.ratio_objetivo == 0 and not np.isnan(u.ATR[t, j]):
                stop[j] = max(stop[j], u.C[t, j] - p.stop_atr * u.ATR[t, j])
        curva[t - inicio] = efectivo + float((acc * Cv[t]).sum())

    abiertas = [{"Empresa": u.tickers[j], "Compra": u.fechas[f_ent[j]], "Precio compra": entrada[j],
                 "Precio actual": Cv[fin - 1, j], "Acciones": int(acc[j]), "Stop-loss": stop[j],
                 "Objetivo": obj[j] if np.isfinite(obj[j]) else None,
                 "Resultado %": (Cv[fin - 1, j] / entrada[j] - 1) * 100}
                for j in np.nonzero(acc > 0)[0]] if fin > inicio else []
    if liquidar and fin > inicio:
        for j in np.nonzero(acc > 0)[0]:
            vender(j, Cv[fin - 1, j], fin - 1, "Fin de la simulación")
        curva[-1] = efectivo
    serie = pd.Series(curva, index=u.fechas[inicio:fin])
    tabla = pd.DataFrame(ops)
    return Resultado(serie, tabla, metricas(serie, tabla, capital, gastos_total), pd.DataFrame(abiertas))


def metricas(curva: pd.Series, ops: pd.DataFrame, capital: float, gastos: float | None = None) -> dict:
    if curva.empty:
        return {"capital_final": capital, "rentabilidad_pct": 0.0, "cagr_pct": 0.0, "max_caida_pct": 0.0,
                "operaciones": 0, "acierto_pct": None, "ganancia_media_pct": None, "perdida_media_pct": None,
                "factor_beneficio": None, "anos": 0.0, "gastos": gastos}
    final = float(curva.iloc[-1])
    anos = max(len(curva) / 252, 1 / 252)
    cagr = ((final / capital) ** (1 / anos) - 1) * 100 if final > 0 else -100.0
    caida = float((curva / curva.cummax() - 1).min() * 100)
    m = {"capital_final": final, "rentabilidad_pct": (final / capital - 1) * 100, "cagr_pct": cagr,
         "max_caida_pct": caida, "operaciones": int(len(ops)), "anos": anos, "gastos": gastos,
         "acierto_pct": None, "ganancia_media_pct": None, "perdida_media_pct": None, "factor_beneficio": None}
    if len(ops):
        r = ops["Resultado €"]
        ganan, pierden = ops[r > 0], ops[r <= 0]
        m["acierto_pct"] = len(ganan) / len(ops) * 100
        m["ganancia_media_pct"] = float(ganan["Resultado %"].mean()) if len(ganan) else None
        m["perdida_media_pct"] = float(pierden["Resultado %"].mean()) if len(pierden) else None
        perdidas = -pierden["Resultado €"].sum()
        m["factor_beneficio"] = float(ganan["Resultado €"].sum() / perdidas) if perdidas > 0 else None
    return m


def comprar_y_mantener(u: Universo, tarifa: Tarifa, capital: float, inicio: int, fin: int) -> pd.Series:
    """Referencia: repartir el dinero a partes iguales entre todas las acciones el primer día y no tocarlo."""
    precios = u.O[inicio]
    ok = ~np.isnan(precios)
    if not ok.any():
        return pd.Series(capital, index=u.fechas[inicio:fin])
    parte = capital / ok.sum()
    acc = np.zeros(len(precios))
    efectivo = capital
    for j in np.nonzero(ok)[0]:
        coste = tarifa.coste(parte) + (parte * ITF_PCT / 100 if u.tickers[j].endswith(".MC") else 0)
        acc[j] = (parte - coste) / precios[j]
        efectivo -= parte
    valores = efectivo + (np.nan_to_num(u.C[inicio:fin]) * acc).sum(axis=1)
    return pd.Series(valores, index=u.fechas[inicio:fin])


# --------------------------------------------------------------------------- entrenamiento
def candidatos(n: int, base: Parametros | None = None, semilla: int = 7) -> list[Parametros]:
    base = base or Parametros()
    todos = [dict(zip(ESPACIO, valores)) for valores in itertools.product(*ESPACIO.values())]
    elegidos = random.Random(semilla).sample(todos, min(max(n - 1, 0), len(todos)))
    lista = [base] + [Parametros(**c, riesgo_pct=base.riesgo_pct) for c in elegidos]
    return list(dict.fromkeys(lista))


def optimizar(u: Universo, tarifa: Tarifa, capital: float, inicio: int, fin: int,
              lista: list[Parametros], objetivo: str = "Equilibrado (recomendado)",
              progreso: Callable[[float, str], None] | None = None, cache: dict | None = None):
    """Prueba cada combinación en el periodo [inicio, fin) y las ordena de mejor a peor."""
    f = OBJETIVOS[objetivo]
    cache = {} if cache is None else cache
    salida = []
    for i, p in enumerate(lista):
        clave = p.peso_modelo
        if clave not in cache:
            cache[clave] = puntuaciones(u, p)
        r = simular(u, p, tarifa, capital, inicio, fin, score=cache[clave])
        salida.append((f(r.metricas), p, r.metricas))
        if progreso:
            progreso((i + 1) / len(lista), "")
    salida.sort(key=lambda x: x[0], reverse=True)
    return salida


def walk_forward(u: Universo, tarifa: Tarifa, capital: float = 10_000.0, iteraciones: int = 40,
                 objetivo: str = "Equilibrado (recomendado)", anos_entreno: int = 3,
                 base: Parametros | None = None,
                 progreso: Callable[[float, str], None] | None = None) -> dict:
    """Entrena en una ventana, prueba en el año siguiente (no visto) y avanza. Devuelve las curvas
    'fuera de muestra' de la estrategia entrenada, de las reglas por defecto y de comprar y mantener."""
    base = base or Parametros()
    T = len(u.fechas)
    entreno, prueba = 252 * anos_entreno, 252
    lista = candidatos(iteraciones, base)
    cache: dict = {}
    ventanas = []
    a = u.inicio
    while a + entreno + 20 < T:
        ventanas.append((a, a + entreno, min(a + entreno + prueba, T)))
        a += prueba
    total = len(ventanas) + 1
    cap_e = cap_d = cap_m = capital
    curvas_e, curvas_d, curvas_m, tramos, ops = [], [], [], [], []
    gastos_e = 0.0
    for i, (a, b, c) in enumerate(ventanas):
        def prog(x, _m="", i=i, a=a, b=b):
            if progreso:
                progreso((i + x) / total, f"Entrenando con {u.fechas[a]:%Y}-{u.fechas[b - 1]:%Y} "
                                          f"({i + 1}/{len(ventanas)})")
        ranking = optimizar(u, tarifa, capital, a, b, lista, objetivo, prog, cache)
        mejor = ranking[0][1]
        r_e = simular(u, mejor, tarifa, cap_e, b, c, score=cache[mejor.peso_modelo])
        r_d = simular(u, base, tarifa, cap_d, b, c, score=cache.setdefault(base.peso_modelo, puntuaciones(u, base)))
        r_m = comprar_y_mantener(u, tarifa, cap_m, b, c)
        cap_e, cap_d, cap_m = float(r_e.curva.iloc[-1]), float(r_d.curva.iloc[-1]), float(r_m.iloc[-1])
        curvas_e.append(r_e.curva)
        curvas_d.append(r_d.curva)
        curvas_m.append(r_m)
        gastos_e += r_e.metricas["gastos"] or 0.0
        if len(r_e.operaciones):
            ops.append(r_e.operaciones)
        tramos.append({"Entrenado con": f"{u.fechas[a]:%Y-%m} → {u.fechas[b - 1]:%Y-%m}",
                       "Probado en (no visto)": f"{u.fechas[b]:%Y-%m} → {u.fechas[c - 1]:%Y-%m}",
                       "Reglas elegidas": mejor, "Resultado entreno %": ranking[0][2]["rentabilidad_pct"],
                       "Resultado prueba %": r_e.metricas["rentabilidad_pct"],
                       "Reglas por defecto %": r_d.metricas["rentabilidad_pct"],
                       "Comprar y mantener %": (r_m.iloc[-1] / r_m.iloc[0] - 1) * 100 if len(r_m) else 0.0})
    if not ventanas:
        raise ValueError("Se necesitan al menos unos 4-5 años de datos para entrenar con walk-forward.")
    # Reglas finales: entrenadas con los años más recientes, para usarlas a partir de hoy.
    ranking_final = optimizar(u, tarifa, capital, max(u.inicio, T - entreno), T, lista, objetivo,
                              (lambda x, _m="": progreso((len(ventanas) + x) / total, "Ajuste final con los "
                                                         "últimos años")) if progreso else None, cache)
    curva_e, curva_d, curva_m = (pd.concat(cs) for cs in (curvas_e, curvas_d, curvas_m))
    operaciones = pd.concat(ops, ignore_index=True) if ops else pd.DataFrame()
    return {
        "curva_entrenada": curva_e, "curva_defecto": curva_d, "curva_mantener": curva_m,
        "metricas_entrenada": metricas(curva_e, operaciones, capital, gastos_e),
        "metricas_defecto": metricas(curva_d, pd.DataFrame(), capital),
        "metricas_mantener": metricas(curva_m, pd.DataFrame(), capital),
        "operaciones": operaciones, "tramos": tramos,
        "parametros_finales": ranking_final[0][1], "metricas_finales_entreno": ranking_final[0][2],
        "top_final": ranking_final[:5], "objetivo": objetivo, "iteraciones": len(lista),
    }


def senales_hoy(u: Universo, p: Parametros, excluir: set[str] | None = None) -> pd.DataFrame:
    """Lo que la estrategia compraría en la próxima apertura según el último cierre."""
    S = puntuaciones(u, p)[-1]
    filas = [{"Empresa": t, "Puntuación": float(S[j]), "Precio": float(u.C[-1, j]),
              "Stop-loss": float(max(u.C[-1, j] - p.stop_atr * u.ATR[-1, j], u.C[-1, j] * 0.8))}
             for j, t in enumerate(u.tickers)
             if not np.isnan(S[j]) and S[j] >= p.umbral_compra and t not in (excluir or set())]
    return pd.DataFrame(filas).sort_values("Puntuación", ascending=False) if filas else pd.DataFrame()
