"""Informe diario: todo lo que la app necesita, calculado cada noche con datos de todas las empresas.

Lo ejecuta `scripts/actualizar.py` (automáticamente en GitHub Actions al cierre de Wall Street)
y la app solo tiene que leer `informe/informe.json`: por eso abre al instante.

Archivos en la carpeta `informe/`:
- informe.json ............ el informe del día
- fundamentales.json ...... datos de empresa y analistas (se refrescan una vez por semana)
- historico_ideas.csv ..... cada idea del día que se ha dado, para medir su acierto real después
- historico_noticias.csv .. el tono de las noticias de cada día, para buscar patrones con el tiempo
"""

from __future__ import annotations

import json
import math
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Callable

import numpy as np
import pandas as pd

from . import asesor, datos, modelo_ml, noticias, patrones, senales, simulador
from .costes import Tarifa
from .tickers import (ETFS, INDICES, INDICES_MUNDIALES, TERMOMETROS, TODAS_LAS_ACCIONES, indice_de_referencia,
                      mercado_de, nombre_de, sector_de)

VERSION = 1
INDICES_LARGOS = ("^IBEX", "^GSPC", "^STOXX50E")
INDICES_REFERENCIA = ("^IBEX", "^STOXX50E", "^GSPC")


# --------------------------------------------------------------------------- utilidades
def limpiar(obj):
    """Convierte a tipos JSON (sin NaN ni tipos de numpy) y redondea decimales."""
    if isinstance(obj, dict):
        return {str(k): limpiar(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [limpiar(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        v = float(obj)
        return None if math.isnan(v) or math.isinf(v) else round(v, 5)
    if isinstance(obj, (pd.Timestamp, datetime, date)):
        return obj.isoformat()[:10]
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, simulador.Parametros):
        return obj.a_dict()
    return obj


def frescos(historicos: dict[str, pd.DataFrame], max_dias: int = 10, minimo: int = 300) -> dict[str, pd.DataFrame]:
    """Descarta valores sin datos recientes (suspendidos, excluidos de bolsa o ticker erróneo)."""
    if not historicos:
        return {}
    ultima = max(df.index.max() for df in historicos.values() if not df.empty)
    return {t: df for t, df in historicos.items()
            if not df.empty and len(df) >= minimo and (ultima - df.index.max()).days <= max_dias}


def descargar_por_bloques(tickers: list[str], periodo: str, bloque: int = 40, reintentos: int = 2,
                          log: Callable[[str], None] = print) -> dict[str, pd.DataFrame]:
    salida: dict[str, pd.DataFrame] = {}
    pendientes = list(tickers)
    for intento in range(reintentos + 1):
        for i in range(0, len(pendientes), bloque):
            salida.update(datos.varios(pendientes[i:i + bloque], periodo))
        pendientes = [t for t in tickers if t not in salida]
        if not pendientes:
            break
        if intento < reintentos:
            log(f"  reintento {intento + 1}: faltan {len(pendientes)} ({', '.join(pendientes[:8])})")
            time.sleep(3 * (intento + 1))
    if pendientes:
        log(f"  sin datos: {', '.join(pendientes)}")
    return salida


def fundamentales_todos(tickers: list[str], hilos: int = 4) -> dict[str, dict]:
    with ThreadPoolExecutor(max_workers=hilos) as pool:
        return {t: f for t, f in zip(tickers, pool.map(datos.fundamentales, tickers)) if f}


# --------------------------------------------------------------------------- pasos
def paso_modelo(acciones, indices, log) -> dict:
    log("Modelo conjunto: construyendo panel...")
    panel = modelo_ml.construir_panel(acciones, {k: indices[k] for k in INDICES_REFERENCIA if k in indices},
                                      indices.get("^VIX"))
    log(f"  {len(panel):,} situaciones de {panel.index.get_level_values('ticker').nunique()} valores")
    wf = modelo_ml.walk_forward(panel, progreso=lambda x, t: log(f"  {t}"))
    final = modelo_ml.entrenar_final(panel)
    hoy = modelo_ml.predecir_hoy(final, panel)
    m = wf["metricas"]
    ventaja = m["acierto"] - m["referencia"]
    fiabilidad = ("Alta" if m["auc"] >= 0.58 and ventaja >= 0.03 else
                  "Media" if m["auc"] >= 0.54 and ventaja >= 0.01 else "Baja")
    log(f"  acierto {m['acierto']:.3f} (ref {m['referencia']:.3f}) AUC {m['auc']:.3f} -> fiabilidad {fiabilidad}")
    try:
        imp = modelo_ml.importancia(final, panel[panel.index.get_level_values("fecha")
                                                >= panel.index.get_level_values("fecha").max() - pd.Timedelta(days=730)])
    except Exception as e:  # noqa: BLE001
        log(f"  (sin importancias: {e})")
        imp = pd.Series(dtype=float)
    return {"wf": wf, "hoy": hoy, "fiabilidad": fiabilidad, "importancia": imp}


def paso_ranking(acciones, indices, fundamentales, lista_noticias, modelo, params: simulador.Parametros) -> list[dict]:
    estados = {k: senales.estado_indice(indices[k]) for k in INDICES_REFERENCIA if k in indices}
    calib = modelo["wf"]["calibracion"]
    met = modelo["wf"]["metricas"]
    filas = []
    for t, df in acciones.items():
        rel = [n for n in lista_noticias if t in n.empresas]
        bruta = modelo["hoy"].get(t)
        cal = modelo_ml.calibrar(bruta, calib) if bruta is not None else {}
        pred = SimpleNamespace(prob_subida=cal["prob"], fiabilidad=modelo["fiabilidad"], horizonte="1 mes",
                               acierto=met["acierto"], pruebas=met["casos"]) if cal else None
        ref = indice_de_referencia(t)
        alcista = estados.get(ref, {}).get("alcista")
        f = fundamentales.get(t, {})
        ev = senales.evaluar(t, df, noticias.sentimiento_medio(rel) if rel else None, len(rel), alcista,
                             fundamentales=f, prediccion=pred, stop_atr=params.stop_atr,
                             ratio_objetivo=params.ratio_objetivo)
        objetivo = f.get("targetMeanPrice")
        filas.append({
            "ticker": t, "nombre": nombre_de(t), "mercado": mercado_de(t), "sector": sector_de(t),
            "etf": t in ETFS, "precio": ev.precio, "var_1d": ev.datos["var_1d"], "var_1m": ev.datos["var_1m"],
            "var_1a": ev.datos["var_1a"], "puntuacion": ev.puntuacion, "veredicto": ev.veredicto, "color": ev.color,
            "rsi": ev.datos["rsi"], "volatilidad": ev.datos["volatilidad"],
            "prob_modelo": cal.get("prob"), "prob_bruta": bruta, "rent_media_1m": cal.get("rent_media"),
            "p10_1m": cal.get("p10"), "p90_1m": cal.get("p90"),
            "potencial_analistas": (objetivo / ev.precio - 1) if objetivo else None,
            "analistas": f.get("numberOfAnalystOpinions"), "per": f.get("forwardPE") or f.get("trailingPE"),
            "dividendo": f.get("trailingAnnualDividendYield"),
            "recomendacion": senales.RECOMENDACIONES.get(f.get("recommendationKey", ""), None),
            "stop": ev.plan.stop if ev.plan else None, "objetivo": ev.plan.objetivo if ev.plan else None,
            "riesgo_pct": ev.plan.riesgo_pct if ev.plan else None,
            "indice": ref, "mercado_alcista": alcista,
            "resultados_pronto": any("resultados" in a for a in ev.avisos),
            "avisos": ev.avisos, "noticias": len(rel),
            "tono_noticias": noticias.sentimiento_medio(rel) if rel else None,
            "motivos": [{"p": m.puntos, "t": m.titulo} for m in sorted(ev.motivos, key=lambda x: -abs(x.puntos))[:5]],
        })
    filas.sort(key=lambda r: r["puntuacion"], reverse=True)
    return filas


def paso_estrategia(acciones, indices, modelo, tarifa, entrenar, previo, iteraciones, log) -> dict:
    """Entrena (o reutiliza) las reglas de compra/venta con todas las acciones y el modelo conjunto."""
    hist = {t: df for t, df in acciones.items() if t not in ETFS}
    probs = modelo_ml.probabilidades_por_accion(modelo["wf"]["oos"])
    refs = {k: indices[k] for k in INDICES_REFERENCIA if k in indices}
    u = simulador.preparar_universo(hist, refs, probabilidades=probs)
    if not entrenar and previo and previo.get("parametros"):
        log("Estrategia: se reutilizan las reglas de la última semana.")
        p = simulador.Parametros.desde_dict(previo["parametros"])
        salida = dict(previo)
    else:
        log(f"Estrategia: entrenando con {len(u.tickers)} acciones y {iteraciones} combinaciones...")
        wf = simulador.walk_forward(u, tarifa, 10_000.0, iteraciones, "Equilibrado (recomendado)", 3,
                                    progreso=lambda x, t: None)
        p = wf["parametros_finales"]

        def semanal(s: pd.Series) -> dict:
            s = s.resample("W").last().dropna()
            return {"fechas": [d.date().isoformat() for d in s.index], "valores": s.round(2).tolist()}

        salida = {
            "parametros": p.a_dict(), "fecha": date.today().isoformat(), "iteraciones": wf["iteraciones"],
            "acciones": len(u.tickers), "fuera_de_muestra": wf["metricas_entrenada"],
            "por_defecto": wf["metricas_defecto"], "comprar_y_mantener": wf["metricas_mantener"],
            "curvas": {"Entrenada": semanal(wf["curva_entrenada"]), "Por defecto": semanal(wf["curva_defecto"]),
                       "Comprar y mantener": semanal(wf["curva_mantener"])},
            "tramos": [{**{k: v for k, v in tr.items() if k != "Reglas elegidas"},
                        "reglas": tr["Reglas elegidas"].a_dict()} for tr in wf["tramos"]],
            "operaciones": int(len(wf["operaciones"])),
        }
        m = wf["metricas_entrenada"]
        log(f"  años no vistos: {m['cagr_pct']:.1f}%/año, caída máx {m['max_caida_pct']:.1f}% "
            f"(mantener {wf['metricas_mantener']['cagr_pct']:.1f}%/año)")
    # Señales de hoy con las reglas vigentes
    hoy = simulador.senales_hoy(u, p)
    salida["senales_hoy"] = hoy.head(15).to_dict("records") if not hoy.empty else []
    return salida


def paso_mercado(indices, largos) -> dict:
    estado = {}
    for t in list(INDICES) + list(TERMOMETROS) + list(INDICES_MUNDIALES):
        df = indices.get(t)
        if df is None or df.empty or len(df) < 30:
            continue
        e = senales.estado_indice(df)
        estado[t] = {"nombre": nombre_de(t), "precio": e["precio"], "alcista": e["alcista"], "texto": e["texto"],
                     "var_1d": e["var_1d"], "var_1m": e["var_1m"], "var_1a": e["var_1a"]}
    fases, caidas = {}, {}
    for t in INDICES_LARGOS:
        df = largos.get(t)
        if df is None or df.empty:
            df = indices.get(t)
        if df is None or df.empty:
            continue
        fases[t] = patrones.estadisticas_fase(df["Close"])
        caidas[t] = patrones.peores_caidas(df["Close"], n=6)
    alcistas = sum(1 for t in INDICES if estado.get(t, {}).get("alcista"))
    vix = estado.get("^VIX", {}).get("precio")
    if alcistas >= 4 and (vix is None or vix < 22):
        semaforo = "verde"
    elif alcistas >= 3:
        semaforo = "ambar"
    else:
        semaforo = "rojo"
    return {"indices": estado, "fases": fases, "peores_caidas": caidas, "semaforo": semaforo,
            "indices_alcistas": alcistas, "vix": vix}


def paso_noticias(lista) -> dict:
    importantes = [n for n in lista if n.impacto >= 4][:40]
    return {
        "total": len(lista), "tono": noticias.sentimiento_medio(importantes),
        "top": [{"titulo": n.titulo, "enlace": n.enlace, "fuente": n.fuente,
                 "fecha": n.fecha.isoformat() if n.fecha else None, "impacto": n.impacto,
                 "sentimiento": n.sentimiento, "explicaciones": n.explicaciones[:2], "empresas": n.empresas,
                 "repeticiones": n.repeticiones} for n in lista[:40]],
    }


def resumen_texto(mercado, noticias_inf, ideas, modelo_met, fiabilidad) -> list[str]:
    frases = []
    f_ibex = mercado["fases"].get("^IBEX", {}).get("fase")
    f_sp = mercado["fases"].get("^GSPC", {}).get("fase")
    color = {"verde": "🟢 verde", "ambar": "🟡 ámbar", "rojo": "🔴 rojo"}[mercado["semaforo"]]
    if f_ibex or f_sp:
        frases.append(f"Semáforo {color}: el IBEX está en fase «{f_ibex or '—'}» y el S&P 500 en «{f_sp or '—'}».")
    tono = noticias_inf["tono"]
    tono_txt = "positivo" if tono > 0.15 else "negativo" if tono < -0.15 else "neutro"
    if noticias_inf["top"]:
        frases.append(f"Tono de las noticias: {tono_txt}. La más influyente: «{noticias_inf['top'][0]['titulo']}».")
    if ideas:
        frases.append("Ideas del día (sectores distintos): " + ", ".join(i["nombre"] for i in ideas[:5]) + ".")
    else:
        frases.append("Hoy ninguna acción cumple todas las condiciones de compra: no pasa nada, paciencia.")
    if modelo_met:
        frases.append(f"El modelo conjunto acertó la dirección a 1 mes el {modelo_met['acierto'] * 100:.0f}% de las "
                      f"veces en años que no había visto (decir siempre lo mismo: {modelo_met['referencia'] * 100:.0f}%). "
                      f"Fiabilidad: {fiabilidad.lower()}.")
    return frases


# --------------------------------------------------------------------------- historiales
COLUMNAS_IDEAS = ["fecha", "ticker", "precio", "puntuacion", "prob_modelo", "indice", "precio_indice"]


def _leer_csv(ruta: Path, columnas: list[str]) -> pd.DataFrame:
    try:
        return pd.read_csv(ruta) if ruta.exists() and ruta.stat().st_size > 0 else pd.DataFrame(columns=columnas)
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=columnas)


def archivar_ideas(ruta: Path, hoy: str, ideas: list[dict], indices) -> pd.DataFrame:
    previo = _leer_csv(ruta, COLUMNAS_IDEAS)
    nuevas = pd.DataFrame(columns=COLUMNAS_IDEAS, data=[{"fecha": hoy, "ticker": i["ticker"], "precio": i["precio"],
                            "puntuacion": i["puntuacion"], "prob_modelo": i.get("prob_modelo"),
                            "indice": i["indice"],
                            "precio_indice": float(indices[i["indice"]]["Close"].iloc[-1])
                            if i["indice"] in indices else None} for i in ideas])
    nuevas = nuevas[COLUMNAS_IDEAS]
    if not previo.empty:
        previo = previo[previo["fecha"] != hoy]
    total = pd.concat([d for d in (previo, nuevas) if not d.empty] or [pd.DataFrame(columns=COLUMNAS_IDEAS)],
                      ignore_index=True)
    total.to_csv(ruta, index=False)
    return total


def evaluar_ideas(hist_ideas: pd.DataFrame, acciones, indices, sesiones: int = 21) -> dict:
    """Acierto REAL de las ideas pasadas: qué pasó 1 mes después de cada idea (frente a su índice)."""
    if hist_ideas is None or hist_ideas.empty:
        return {"evaluadas": 0, "pendientes": 0}
    filas, pendientes = [], 0
    for _, r in hist_ideas.iterrows():
        df, idx = acciones.get(r["ticker"]), indices.get(r["indice"])
        if df is None:
            continue
        posteriores = df["Close"][df.index > pd.Timestamp(r["fecha"])]
        if len(posteriores) < sesiones:
            pendientes += 1
            continue
        fin = posteriores.index[sesiones - 1]
        ret = posteriores.iloc[sesiones - 1] / r["precio"] - 1
        ret_idx = None
        if idx is not None and r.get("precio_indice"):
            c = idx["Close"][idx.index <= fin]
            if len(c):
                ret_idx = c.iloc[-1] / r["precio_indice"] - 1
        filas.append({"fecha": r["fecha"], "ticker": r["ticker"], "ret": ret, "ret_indice": ret_idx})
    if not filas:
        return {"evaluadas": 0, "pendientes": pendientes}
    t = pd.DataFrame(filas)
    con_idx = t.dropna(subset=["ret_indice"])
    return {"evaluadas": len(t), "pendientes": pendientes, "suben": float((t["ret"] > 0).mean()),
            "rent_media": float(t["ret"].mean()),
            "baten_indice": float((con_idx["ret"] > con_idx["ret_indice"]).mean()) if len(con_idx) else None,
            "exceso_medio": float((con_idx["ret"] - con_idx["ret_indice"]).mean()) if len(con_idx) else None,
            "ultimas": t.tail(30).iloc[::-1].to_dict("records")}


def archivar_noticias(ruta: Path, hoy: str, lista) -> pd.DataFrame:
    previo = _leer_csv(ruta, ["fecha", "ambito", "n", "sentimiento"])
    importantes = [n for n in lista if n.impacto >= 4]
    filas = [{"fecha": hoy, "ambito": "MERCADO", "n": len(importantes),
              "sentimiento": noticias.sentimiento_medio(importantes)}]
    por_empresa: dict[str, list] = {}
    for n in lista:
        for t in n.empresas:
            por_empresa.setdefault(t, []).append(n)
    filas += [{"fecha": hoy, "ambito": t, "n": len(ns), "sentimiento": noticias.sentimiento_medio(ns)}
              for t, ns in por_empresa.items()]
    if not previo.empty:
        previo = previo[previo["fecha"] != hoy]
    total = pd.concat([previo, pd.DataFrame(filas)], ignore_index=True)
    total.to_csv(ruta, index=False)
    return total


def patron_noticias(hist_noticias: pd.DataFrame, indice: pd.DataFrame | None, minimo_dias: int = 30) -> dict:
    """Con el tiempo: ¿los días de noticias muy positivas/negativas anticiparon algo en la semana siguiente?"""
    if hist_noticias is None or hist_noticias.empty or indice is None:
        return {"dias": 0}
    m = hist_noticias[hist_noticias["ambito"] == "MERCADO"].copy()
    m["fecha"] = pd.to_datetime(m["fecha"])
    c = indice["Close"]
    fwd = c.shift(-5) / c - 1
    m["fwd"] = [fwd[fwd.index >= f].iloc[0] if (fwd.index >= f).any() else np.nan for f in m["fecha"]]
    m = m.dropna(subset=["fwd"])
    salida = {"dias": int(len(m))}
    if len(m) < minimo_dias:
        return salida
    pos, neg = m[m["sentimiento"] > 0.2], m[m["sentimiento"] < -0.2]
    salida.update(correlacion=float(m["sentimiento"].corr(m["fwd"])),
                  semana_tras_positivas=float(pos["fwd"].mean()) if len(pos) else None, n_positivas=int(len(pos)),
                  semana_tras_negativas=float(neg["fwd"].mean()) if len(neg) else None, n_negativas=int(len(neg)),
                  semana_media=float(m["fwd"].mean()))
    return salida


# --------------------------------------------------------------------------- orquestación
def actualizar(carpeta: str | Path = "informe", entrenar: bool | None = None, iteraciones: int = 80,
               con_noticias: bool = True, refrescar_fundamentales: bool | None = None,
               log: Callable[[str], None] = print) -> dict:
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta_inf = carpeta / "informe.json"
    previo = json.loads(ruta_inf.read_text(encoding="utf-8")) if ruta_inf.exists() else {}
    hoy = date.today().isoformat()
    tarifa = Tarifa()

    log("Descargando cotizaciones de todas las empresas (10 años)...")
    acciones = frescos(descargar_por_bloques(list(TODAS_LAS_ACCIONES), "10y", log=log))
    log(f"  {len(acciones)}/{len(TODAS_LAS_ACCIONES)} valores con datos válidos")
    idx_tickers = list(dict.fromkeys(list(INDICES) + list(TERMOMETROS) + list(INDICES_MUNDIALES)))
    indices = descargar_por_bloques(idx_tickers, "10y", log=log)
    largos = {t: datos.historico(t, "max") for t in INDICES_LARGOS}
    if len(acciones) < 20:
        raise RuntimeError("Se han descargado muy pocas cotizaciones: se mantiene el informe anterior.")

    ruta_f = carpeta / "fundamentales.json"
    fund_prev = json.loads(ruta_f.read_text(encoding="utf-8")) if ruta_f.exists() else {}
    edad_f = (date.today() - date.fromisoformat(fund_prev["fecha"])).days if fund_prev.get("fecha") else 999
    if refrescar_fundamentales or (refrescar_fundamentales is None and edad_f >= 7):
        log("Descargando datos de empresa y analistas...")
        nuevos = fundamentales_todos([t for t in acciones if t not in ETFS])
        if len(nuevos) >= 0.5 * len(fund_prev.get("datos", {})):
            fund_prev = {"fecha": hoy, "datos": nuevos}
            ruta_f.write_text(json.dumps(limpiar(fund_prev), ensure_ascii=False), encoding="utf-8")
        log(f"  {len(nuevos)} empresas con datos")
    fundamentales = fund_prev.get("datos", {})

    lista = []
    if con_noticias:
        log("Leyendo noticias...")
        lista, fallos = noticias.descargar()
        log(f"  {len(lista)} noticias ({len(fallos)} fuentes sin respuesta)")

    modelo = paso_modelo(acciones, indices, log)

    estrategia_prev = previo.get("estrategia")
    if entrenar is None:
        ultima = estrategia_prev.get("fecha") if estrategia_prev else None
        entrenar = (ultima is None or (date.today() - date.fromisoformat(ultima)).days >= 7
                    or date.today().weekday() == 5)
    estrategia = paso_estrategia(acciones, indices, modelo, tarifa, entrenar, estrategia_prev, iteraciones, log)
    params = simulador.Parametros.desde_dict(estrategia["parametros"])

    log("Puntuando cada valor...")
    ranking = paso_ranking(acciones, indices, fundamentales, lista, modelo, params)
    candidatas = [r for r in ranking if not (params.filtro_mercado and r["mercado_alcista"] is False)]
    ideas = asesor.ideas_diversificadas(candidatas, max_ideas=5, min_puntuacion=max(65, params.umbral_compra - 5),
                                        max_por_sector=1)
    mercado = paso_mercado(indices, largos)
    noticias_inf = paso_noticias(lista)

    hist_ideas = archivar_ideas(carpeta / "historico_ideas.csv", hoy, ideas, indices)
    hist_not = archivar_noticias(carpeta / "historico_noticias.csv", hoy, lista) if con_noticias else None
    met = modelo["wf"]["metricas"]
    informe = {
        "version": VERSION, "fecha": hoy, "generado": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "datos_hasta": max(df.index.max() for df in acciones.values()).date().isoformat(),
        "resumen": resumen_texto(mercado, noticias_inf, ideas, met, modelo["fiabilidad"]),
        "mercado": mercado, "noticias": noticias_inf, "ideas": [i["ticker"] for i in ideas],
        "ranking": ranking,
        "modelo": {"metricas": met, "fiabilidad": modelo["fiabilidad"],
                   "calibracion": modelo["wf"]["calibracion"].to_dict("records"),
                   "por_ano": modelo["wf"]["por_ano"].reset_index().to_dict("records"),
                   "importancia": [{"dato": k, "peso": v} for k, v in modelo["importancia"].head(10).items()]},
        "estrategia": estrategia,
        "historial_ideas": evaluar_ideas(hist_ideas, acciones, indices),
        "patron_noticias": patron_noticias(hist_not, indices.get("^IBEX")),
        "cobertura": {"acciones": len(acciones), "indices": len(indices),
                      "fundamentales": len(fundamentales), "noticias": len(lista)},
    }
    ruta_inf.write_text(json.dumps(limpiar(informe), ensure_ascii=False), encoding="utf-8")
    log(f"Informe guardado en {ruta_inf} ({ruta_inf.stat().st_size / 1024:.0f} KB)")
    return informe
