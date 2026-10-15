"""Avisos de precio a tu medida: «avísame si Indra baja de 200 €» o «si Santander sube de 14 €».

Se comprueban de dos formas:
- en la app, cada vez que la abres (con las velas diarias desde que creaste el aviso);
- por Telegram, cada hora en horario de mercado (scripts/alertas.py), solo cuando el precio CRUZA el nivel en la
  última hora. Así no recibes el mismo aviso una y otra vez mientras el precio sigue al otro lado.
"""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd

TIPOS = {"baja": "baja de", "sube": "sube de"}


def nueva(lista: list[dict], ticker: str, nombre: str, tipo: str, precio: float, precio_actual: float | None,
          nota: str = "", hoy: date | None = None) -> str | None:
    """Añade un aviso. Devuelve un mensaje de error o None si se ha creado."""
    if tipo not in TIPOS:
        return "Tipo de aviso no válido."
    if not precio or precio <= 0:
        return "Pon un precio mayor que cero."
    if precio_actual:
        if tipo == "baja" and precio_actual <= precio:
            return (f"{nombre} ya está por debajo de ese precio ({_num(precio_actual)}). Pon un nivel más bajo o un "
                    "aviso de subida.")
        if tipo == "sube" and precio_actual >= precio:
            return (f"{nombre} ya está por encima de ese precio ({_num(precio_actual)}). Pon un nivel más alto o "
                    "un aviso de bajada.")
    lista.append({"id": max((a["id"] for a in lista), default=0) + 1, "ticker": ticker, "nombre": nombre,
                  "tipo": tipo, "precio": float(precio), "nota": nota.strip(),
                  "creada": (hoy or date.today()).isoformat(), "disparada": None, "precio_disparo": None})
    return None


def cumple(tipo: str, nivel: float, minimo: float, maximo: float) -> bool:
    return minimo <= nivel if tipo == "baja" else maximo >= nivel


def revisar(lista: list[dict], historicos: dict[str, pd.DataFrame]) -> list[dict]:
    """Marca como disparados los avisos activos cuyo nivel se ha tocado después del día en que se crearon (o al
    cierre de ese mismo día). Devuelve los que se acaban de disparar."""
    nuevos = []
    for a in lista:
        if a.get("disparada"):
            continue
        df = historicos.get(a["ticker"])
        if df is None or df.empty:
            continue
        creada = pd.Timestamp(a["creada"])
        idx = pd.to_datetime(df.index).normalize()
        despues = df[idx > creada]
        mismo_dia = df[idx == creada]
        for dia, f in despues.iterrows():
            if cumple(a["tipo"], a["precio"], float(f["Low"]), float(f["High"])):
                a["disparada"], a["precio_disparo"] = pd.Timestamp(dia).date().isoformat(), float(f["Close"])
                break
        if not a.get("disparada") and despues.empty and not mismo_dia.empty:
            cierre = float(mismo_dia["Close"].iloc[-1])
            if cumple(a["tipo"], a["precio"], cierre, cierre):
                a["disparada"], a["precio_disparo"] = a["creada"], cierre
        if a.get("disparada"):
            nuevos.append(a)
    return nuevos


def cruces_en_ventana(lista: list[dict], intradia: dict[str, pd.DataFrame], desde: datetime,
                      hasta: datetime) -> list[dict]:
    """Avisos activos cuyo nivel se ha CRUZADO entre `desde` y `hasta` (velas intradía en hora de Madrid, sin
    zona horaria): antes de `desde` el precio estaba al otro lado y dentro de la ventana lo ha tocado."""
    cruzados = []
    for a in lista:
        if a.get("disparada"):
            continue
        df = intradia.get(a["ticker"])
        if df is None or df.empty:
            continue
        antes = df[df.index < desde]
        ventana = df[(df.index >= desde) & (df.index < hasta)]
        if antes.empty or ventana.empty:
            continue
        previo = float(antes["Close"].iloc[-1])
        if cumple(a["tipo"], a["precio"], previo, previo):
            continue   # ya estaba al otro lado: no es un cruce nuevo
        if cumple(a["tipo"], a["precio"], float(ventana["Low"].min()), float(ventana["High"].max())):
            cruzados.append({**a, "precio_ahora": float(ventana["Close"].iloc[-1])})
    return cruzados


def _num(x: float) -> str:
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def texto(a: dict, precio_ahora: float | None = None) -> str:
    verbo = "ha bajado de" if a["tipo"] == "baja" else "ha subido de"
    s = f"{a['nombre']} {verbo} {_num(a['precio'])}"
    if precio_ahora:
        s += f" (ahora {_num(precio_ahora)})"
    return s + (f". Tu nota: «{a['nota']}»" if a.get("nota") else "")


def describir(a: dict) -> str:
    return f"Avísame si {a['nombre']} {TIPOS[a['tipo']]} {_num(a['precio'])}"


__all__ = ["TIPOS", "nueva", "cumple", "revisar", "cruces_en_ventana", "texto", "describir"]
