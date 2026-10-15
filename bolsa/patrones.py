"""Patrones históricos y escenarios: "¿qué puede ocurrir?".

- Fase del mercado: clasifica cada día de la historia de un índice (desde los años 90 en el IBEX,
  desde 1927 en el S&P 500) y mide qué pasó después en todas las ocasiones parecidas a la actual.
- Peores caídas: las grandes crisis de cada índice, cuánto cayeron y cuánto tardaron en recuperarse.
- Escenarios de una cartera: remuestreo de su historia (bootstrap por bloques) para estimar el rango
  de resultados a 1 año, y pruebas de estrés: cuánto habría perdido en crisis reales.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

FASES = {
    "Alcista tranquilo": "El mercado sube por encima de sus medias y sin sobresaltos. Históricamente es la fase "
                         "más favorable, aunque las subidas suelen ser más lentas.",
    "Alcista con nervios": "La tendencia de fondo es buena, pero hay más movimiento de lo normal. Conviene entrar "
                           "poco a poco y respetar los stop-loss.",
    "Corrección en tendencia alcista": "Ha bajado en las últimas semanas, pero la tendencia de fondo sigue siendo "
                                       "alcista. Muchas veces son oportunidades, otras el inicio de algo peor.",
    "Intentando recuperarse": "Viene de caer, sigue por debajo de su media de 200 sesiones, pero rebota. "
                              "Puede ser el fin de la caída o un rebote pasajero.",
    "Bajista": "El mercado está por debajo de sus medias: tendencia bajista. Paciencia: invierte solo con "
               "aportaciones pequeñas y periódicas, nunca todo de golpe.",
}

CRISIS = {
    "Brexit (junio 2016)": ("2016-06-08", "2016-06-27"),
    "Final de 2018": ("2018-10-01", "2018-12-24"),
    "COVID (febrero-marzo 2020)": ("2020-02-19", "2020-03-23"),
    "Subida de tipos e inflación (2022)": ("2022-01-03", "2022-10-12"),
    "Crisis bancaria SVB (marzo 2023)": ("2023-03-08", "2023-03-17"),
    "Aranceles de EEUU (abril 2025)": ("2025-04-02", "2025-04-08"),
}


# --------------------------------------------------------------------------- fases del mercado
def fase_mercado(c: pd.Series) -> pd.Series:
    c = c.dropna()
    sma200 = c.rolling(200, min_periods=200).mean()
    sma50 = c.rolling(50, min_periods=50).mean()
    vol = c.pct_change().rolling(20).std()
    vol_normal = vol.rolling(756, min_periods=252).median()
    nervioso = vol > 1.3 * vol_normal
    encima = c > sma200
    fase = np.select(
        [encima & (c <= sma50), encima & nervioso, encima, ~encima & (c > sma50)],
        ["Corrección en tendencia alcista", "Alcista con nervios", "Alcista tranquilo", "Intentando recuperarse"],
        default="Bajista")
    return pd.Series(fase, index=c.index).where(sma200.notna())


def _stats(r: pd.Series) -> dict:
    r = r.dropna()
    if len(r) < 10:
        return {"casos": int(len(r))}
    return {"casos": int(len(r)), "prob_sube": float((r > 0).mean()), "mediana": float(r.median()),
            "p10": float(np.percentile(r, 10)), "p90": float(np.percentile(r, 90)), "peor": float(r.min()),
            "mejor": float(r.max())}


def estadisticas_fase(c: pd.Series, horizontes: dict[str, int] | None = None, paso: int = 5) -> dict:
    """Qué pasó después en todas las ocasiones en que el índice estuvo en la misma fase que hoy."""
    horizontes = horizontes or {"1 mes": 21, "3 meses": 63, "1 año": 252}
    c = c.dropna()
    fases = fase_mercado(c)
    actual = fases.iloc[-1]
    if pd.isna(actual):
        return {}
    cambios = fases.ne(fases.shift())
    inicio_racha = fases.index[cambios][-1] if cambios.any() else fases.index[0]
    muestra = fases.iloc[::paso]
    salida = {"fase": actual, "explicacion": FASES[actual], "desde": str(inicio_racha.date()),
              "historia_desde": str(c.index[0].date()), "horizontes": {}, "todas": {}}
    for nombre, h in horizontes.items():
        fwd = (c.shift(-h) / c - 1).reindex(muestra.index)
        salida["horizontes"][nombre] = _stats(fwd[muestra == actual])
        salida["todas"][nombre] = _stats(fwd)
    reparto = fases.dropna().value_counts(normalize=True)
    salida["frecuencia_fase"] = float(reparto.get(actual, 0.0))
    return salida


def peores_caidas(c: pd.Series, n: int = 5, minimo: float = -0.15) -> list[dict]:
    """Las n mayores caídas desde máximos, cuándo tocaron fondo y cuánto tardaron en recuperarse."""
    c = c.dropna()
    maximo = c.cummax()
    dd = c / maximo - 1
    episodios, i = [], 0
    valores, fechas = dd.to_numpy(), dd.index
    while i < len(valores):
        if valores[i] < 0:
            j = i
            while j < len(valores) and valores[j] < 0:
                j += 1
            tramo = valores[i:j]
            k = i + int(np.argmin(tramo))
            if tramo.min() <= minimo:
                episodios.append({
                    "inicio": str(fechas[i - 1].date()) if i > 0 else str(fechas[i].date()),
                    "fondo": str(fechas[k].date()), "caida": float(tramo.min()),
                    "recuperado": str(fechas[j].date()) if j < len(valores) else None,
                    "dias_caida": int((fechas[k] - fechas[max(i - 1, 0)]).days),
                    "dias_recuperar": int((fechas[j] - fechas[k]).days) if j < len(valores) else None,
                })
            i = j
        else:
            i += 1
    return sorted(episodios, key=lambda e: e["caida"])[:n]


# --------------------------------------------------------------------------- carteras
def rentabilidades_cartera(historicos: dict[str, pd.DataFrame], pesos: dict[str, float]) -> pd.Series:
    """Rentabilidad diaria de una cartera con pesos fijos (si un valor no existía aún, se reparte su peso
    entre los demás ese día)."""
    rets = pd.DataFrame({t: historicos[t]["Close"].pct_change() for t in pesos
                         if t in historicos and not historicos[t].empty})
    if rets.empty:
        return pd.Series(dtype=float)
    rets = rets.sort_index()
    w = pd.Series({t: pesos[t] for t in rets.columns}, dtype=float)
    disponibles = rets.notna()
    pesos_dia = disponibles.mul(w, axis=1)
    pesos_dia = pesos_dia.div(pesos_dia.sum(axis=1).replace(0, np.nan), axis=0)
    return (rets.fillna(0) * pesos_dia).sum(axis=1)[disponibles.any(axis=1)].iloc[1:]


def escenarios(rets: pd.Series, dias: int = 252, n: int = 3000, bloque: int = 21, semilla: int = 0) -> dict:
    """Remuestrea bloques de un mes de la historia real para simular muchos 'años posibles'."""
    r = rets.dropna().to_numpy()
    if len(r) < bloque * 6:
        return {}
    rng = np.random.default_rng(semilla)
    bloques = int(np.ceil(dias / bloque))
    inicios = rng.integers(0, len(r) - bloque, size=(n, bloques))
    caminos = np.stack([r[s:s + bloque] for s in inicios.ravel()]).reshape(n, bloques * bloque)[:, :dias]
    curvas = np.cumprod(1 + caminos, axis=1)
    final = curvas[:, -1] - 1
    caida = (curvas / np.maximum.accumulate(curvas, axis=1) - 1).min(axis=1)
    return {"p5": float(np.percentile(final, 5)), "p25": float(np.percentile(final, 25)),
            "p50": float(np.percentile(final, 50)), "p75": float(np.percentile(final, 75)),
            "p95": float(np.percentile(final, 95)), "prob_perdida": float((final < 0).mean()),
            "caida_tipica": float(np.median(caida)), "caida_mala": float(np.percentile(caida, 10)),
            "anos_historia": round(len(r) / 252, 1)}


def prueba_estres(historicos: dict[str, pd.DataFrame], pesos: dict[str, float],
                  crisis: dict[str, tuple[str, str]] | None = None) -> list[dict]:
    """Cuánto habría cambiado la cartera en cada crisis (solo con los valores que ya cotizaban)."""
    crisis = crisis or CRISIS
    salida = []
    total = sum(pesos.values()) or 1
    for nombre, (ini, fin) in crisis.items():
        ini, fin = pd.Timestamp(ini), pd.Timestamp(fin)
        cambio, cubierto = 0.0, 0.0
        for t, w in pesos.items():
            df = historicos.get(t)
            if df is None or df.empty:
                continue
            c = df["Close"].dropna()
            antes, despues = c[c.index <= ini], c[c.index <= fin]
            if antes.empty or despues.empty or antes.index[-1] < ini - pd.Timedelta(days=7):
                continue
            cambio += w * (despues.iloc[-1] / antes.iloc[-1] - 1)
            cubierto += w
        if cubierto > 0:
            salida.append({"crisis": nombre, "desde": str(ini.date()), "hasta": str(fin.date()),
                           "cambio": cambio / cubierto, "cobertura": cubierto / total})
    return salida
