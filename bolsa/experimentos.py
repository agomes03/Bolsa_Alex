"""Laboratorio: compara con datos reales qué se puede predecir y qué estrategias funcionan.

Todo se evalúa sin mirar el futuro: las señales de cada fecha usan solo datos anteriores y las
predicciones del modelo son las "fuera de muestra" del walk-forward anual.
"""

from __future__ import annotations

import math
from typing import Callable

import numpy as np
import pandas as pd

from . import modelo_ml, simulador
from .costes import Tarifa, acciones_asequibles, itf_pct
from .tickers import ETFS, indice_de_referencia


# --------------------------------------------------------------------------- métricas
def resumen_curva(curva: pd.Series, capital: float, gastos: float = 0.0, operaciones: int = 0) -> dict:
    curva = curva.dropna()
    if len(curva) < 2:
        return {}
    anos = len(curva) / 252
    final = float(curva.iloc[-1])
    rets = curva.pct_change().dropna()
    return {"cagr_pct": ((final / capital) ** (1 / anos) - 1) * 100 if final > 0 else -100.0,
            "max_caida_pct": float((curva / curva.cummax() - 1).min() * 100),
            "volatilidad_pct": float(rets.std() * math.sqrt(252) * 100),
            "sharpe": float(rets.mean() / rets.std() * math.sqrt(252)) if rets.std() > 0 else 0.0,
            "capital_final": final, "anos": round(anos, 1), "gastos": gastos, "operaciones": operaciones,
            "desde": str(curva.index[0].date()), "hasta": str(curva.index[-1].date())}


# --------------------------------------------------------------------------- cartera mensual por ranking
def simular_rotacion(cierres: pd.DataFrame, senal: pd.DataFrame, n: int, tarifa: Tarifa,
                     capital: float = 10_000.0, permitido: pd.DataFrame | None = None, cada: int = 21,
                     inicio: pd.Timestamp | None = None, tolerancia: float = 0.25) -> tuple[pd.Series, dict]:
    """Cada `cada` sesiones se queda con las `n` acciones de mayor señal (decidido con el cierre anterior),
    a partes iguales. Los huecos que no se pueden llenar (p. ej. mercado bajista) quedan en liquidez.
    Paga comisión por operación e impuesto de transacciones en las compras."""
    fechas = cierres.index
    i0 = int(fechas.searchsorted(inicio)) if inicio is not None else 1
    i0 = max(i0, 1)
    tickers = list(cierres.columns)
    precios = cierres.to_numpy()
    s = senal.reindex(index=fechas, columns=tickers).to_numpy()
    ok_perm = permitido.reindex(index=fechas, columns=tickers).fillna(False).to_numpy().astype(bool) \
        if permitido is not None else None
    itf = np.array([itf_pct(t) / 100 for t in tickers])
    acc = np.zeros(len(tickers))
    efectivo, gastos, ops = float(capital), 0.0, 0
    curva = np.empty(len(fechas) - i0)
    for k, t in enumerate(range(i0, len(fechas))):
        p = precios[t]
        if (t - i0) % cada == 0:
            sig = s[t - 1].copy()
            elegible = ~np.isnan(sig) & ~np.isnan(p)
            if ok_perm is not None:
                elegible &= ok_perm[t - 1]
            sig[~elegible] = -np.inf
            top = [j for j in np.argsort(-sig)[:n] if np.isfinite(sig[j])]
            valor = efectivo + float(np.nansum(acc * p))
            objetivo_euros = valor / n
            # Ventas: lo que sale del top y lo que sobra de lo que se queda
            for j in np.nonzero(acc > 0)[0]:
                if np.isnan(p[j]):
                    continue
                deseadas = math.floor(objetivo_euros / p[j]) if j in top else 0
                if deseadas < acc[j] and (j not in top or (acc[j] - deseadas) * p[j] > tolerancia * objetivo_euros):
                    importe = (acc[j] - deseadas) * p[j]
                    coste = tarifa.coste(importe, tickers[j])
                    efectivo += importe - coste
                    gastos += coste
                    ops += 1
                    acc[j] = deseadas
            # Compras
            for j in top:
                deseadas = math.floor(objetivo_euros / p[j])
                faltan = deseadas - acc[j]
                if faltan <= 0 or faltan * p[j] < tolerancia * objetivo_euros:
                    continue
                importe = faltan * p[j]
                coste = tarifa.coste(importe, tickers[j]) + importe * itf[j]
                if importe + coste > efectivo:
                    faltan = acciones_asequibles(efectivo, p[j], tickers[j], tarifa, itf[j] * 100)
                    if faltan <= 0:
                        continue
                    importe = faltan * p[j]
                    coste = tarifa.coste(importe, tickers[j]) + importe * itf[j]
                efectivo -= importe + coste
                gastos += coste
                ops += 1
                acc[j] += faltan
        curva[k] = efectivo + float(np.nansum(acc * np.nan_to_num(p)))
    serie = pd.Series(curva, index=fechas[i0:])
    resumen = resumen_curva(serie, capital, gastos, ops)
    resumen["cartera_final"] = {tickers[j]: int(acc[j]) for j in np.nonzero(acc > 0)[0]}
    resumen["efectivo_final"] = efectivo
    return serie, resumen


def senales_basicas(cierres: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Señales clásicas calculadas solo con precios pasados."""
    r252 = cierres.pct_change(252, fill_method=None)
    r21 = cierres.pct_change(21, fill_method=None)
    vol = cierres.pct_change(fill_method=None).rolling(126, min_periods=60).std()
    mom = r252 - r21  # momentum "12-1": el último año sin el último mes
    rank = lambda x: x.rank(axis=1, pct=True)  # noqa: E731
    return {
        "Momentum 12-1": mom,
        "Baja volatilidad": -vol,
        "Momentum + baja volatilidad": rank(mom) + rank(-vol),
        "Tendencia (sobre media 200)": cierres / cierres.rolling(200, min_periods=200).mean() - 1,
    }


def permitido_por_indice(cierres: pd.DataFrame, indices: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """True si el índice de referencia de cada acción está por encima de su media de 200 sesiones."""
    estados = {k: simulador.mercado_alcista(v).reindex(cierres.index, method="ffill") for k, v in indices.items()}
    return pd.DataFrame({t: estados.get(indice_de_referencia(t), pd.Series(1.0, index=cierres.index)) == 1
                         for t in cierres.columns}, index=cierres.index)


# --------------------------------------------------------------------------- índices con filtro de tendencia
def filtro_tendencia_indice(c: pd.Series, media: int = 200, banda: float = 0.0, interes_anual: float = 0.02,
                            coste_cambio: float = 0.001) -> dict:
    """Comprar y mantener frente a 'estar invertido solo si el índice está por encima de su media'."""
    c = c.dropna()
    sma = c.rolling(media, min_periods=media).mean()
    r = c.pct_change().fillna(0)
    dentro = np.full(len(c), np.nan)
    estado = 1.0
    for i in range(len(c)):
        if np.isnan(sma.iloc[i]):
            continue
        if c.iloc[i] > sma.iloc[i] * (1 + banda):
            estado = 1.0
        elif c.iloc[i] < sma.iloc[i] * (1 - banda):
            estado = 0.0
        dentro[i] = estado
    pos = pd.Series(dentro, index=c.index).shift(1)  # decide con el cierre de ayer
    validos = pos.notna()
    pos, r = pos[validos], r[validos]
    cambios = pos.diff().abs().fillna(0)
    estrategia = (1 + pos * r + (1 - pos) * interes_anual / 252 - cambios * coste_cambio).cumprod() * 10_000
    mantener = (1 + r).cumprod() * 10_000
    return {"mantener": resumen_curva(mantener, 10_000), "filtro": resumen_curva(estrategia, 10_000),
            "tiempo_invertido": float(pos.mean()), "cambios_por_ano": float(cambios.sum() / (len(pos) / 252))}


# --------------------------------------------------------------------------- experimento completo
def ejecutar(acciones: dict[str, pd.DataFrame], indices: dict[str, pd.DataFrame], largos: dict[str, pd.DataFrame],
             tarifa: Tarifa | None = None, log: Callable[[str], None] = print) -> dict:
    tarifa = tarifa or Tarifa()
    refs = {k: indices[k] for k in ("^IBEX", "^STOXX50E", "^GSPC") if k in indices}
    resultado: dict = {"modelos": {}, "rotacion": [], "indices": {}}

    log("1) Qué se puede predecir (modelo conjunto, años no vistos)")
    panel = modelo_ml.construir_panel(acciones, refs, indices.get("^VIX"))
    oos = {}
    for nombre in modelo_ml.OBJETIVOS:
        wf = modelo_ml.walk_forward(panel, objetivo=nombre)
        m = wf["metricas"]
        cal = wf["calibracion"]
        m["tramo_bajo"] = float(cal["sube"].iloc[0])
        m["tramo_alto"] = float(cal["sube"].iloc[-1])
        resultado["modelos"][nombre] = m
        oos[nombre] = wf["oos"].unstack("ticker")
        log(f"   {nombre:10} AUC {m['auc']:.3f} | acierto {m['acierto']:.3f} (ref {m['referencia']:.3f}) | "
            f"tramo más bajo {m['tramo_bajo']:.2f} → más alto {m['tramo_alto']:.2f} | "
            f"20% mejor {m['mejores_mes'] * 100:+.2f}% vs 20% peor {m['peores_mes'] * 100:+.2f}%")

    log("2) Carteras mensuales por ranking (en euros, comisiones reales de Bankinter)")
    hist = {t: df for t, df in acciones.items() if t not in ETFS}
    cierres_g = pd.DataFrame({t: df["Close"] for t, df in hist.items()}).sort_index().ffill(limit=5)
    permitido = permitido_por_indice(cierres_g, refs)
    inicio_oos = min(v.index.min() for v in oos.values())
    for universo in ("espana", "global"):
        cierres = cierres_g if universo == "global" else cierres_g[[t for t in cierres_g.columns if t.endswith(".MC")]]
        senales = senales_basicas(cierres)
        if universo == "global":
            for nombre, clave in (("Modelo: lo hará mejor (3 meses)", "supera_3m"), ("Modelo: subirá (1 mes)", "sube_1m"),
                                  ("Modelo: menor riesgo de caída", "caida_3m")):
                sig = oos[clave].reindex(index=cierres.index, columns=cierres.columns)
                senales[nombre] = -sig if clave.startswith("caida") else sig
        senales["Todas a partes iguales"] = pd.DataFrame(1.0, index=cierres.index, columns=cierres.columns)
        for nombre, sig in senales.items():
            todas = nombre == "Todas a partes iguales"
            n_opciones = [len(cierres.columns)] if todas else ([5, 8, 12] if universo == "espana" else [5, 10, 20])
            for n in n_opciones:
                for filtro in (False, True):
                    if todas and filtro:
                        continue
                    # Capital realista para cada universo; la referencia, con mucho capital (como un fondo).
                    cap = 1_000_000.0 if todas else (10_000.0 if universo == "espana" else n * 5_000.0)
                    _, met = simular_rotacion(cierres, sig, n, tarifa, cap, permitido if filtro else None,
                                              inicio=inicio_oos)
                    met.pop("cartera_final", None)
                    fila = {"universo": universo, "senal": nombre, "n": n, "filtro_mercado": filtro, "capital": cap,
                            **met}
                    resultado["rotacion"].append(fila)
                    log(f"   [{universo:6}] {nombre[:30]:30} n={n:3} filtro={'sí' if filtro else 'no'} | "
                        f"{met['cagr_pct']:6.1f}%/año caída {met['max_caida_pct']:6.1f}% sharpe {met['sharpe']:.2f} "
                        f"gastos {met['gastos'] * 10_000 / cap:7.0f} (por cada 10.000 €)")

    log("3) Índices: comprar y mantener frente a filtro de tendencia (historia completa)")
    for t, df in largos.items():
        if df is None or df.empty:
            continue
        for media, banda in ((200, 0.0), (200, 0.02), (150, 0.0)):
            r = filtro_tendencia_indice(df["Close"], media, banda)
            resultado["indices"].setdefault(t, []).append({"media": media, "banda": banda, **r})
            log(f"   {t:10} media {media} banda {banda:.0%} | mantener {r['mantener']['cagr_pct']:.1f}%/año "
                f"caída {r['mantener']['max_caida_pct']:.0f}% | filtro {r['filtro']['cagr_pct']:.1f}%/año caída "
                f"{r['filtro']['max_caida_pct']:.0f}% | invertido {r['tiempo_invertido']:.0%} "
                f"cambios/año {r['cambios_por_ano']:.1f}")
    return resultado
