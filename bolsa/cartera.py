"""Carteras: la virtual (dinero ficticio para practicar) y la real (lo que tienes en Bankinter).

Se guardan como diccionarios sencillos (JSON) para poder almacenarlos en un archivo o en la nube.
"""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd

from .costes import Tarifa, coste_compra


def hoy() -> str:
    return date.today().isoformat()


def nueva(capital: float | None = 10_000.0) -> dict:
    """capital=None para la cartera real (no llevamos la cuenta del efectivo)."""
    return {"capital_inicial": capital, "efectivo": capital, "posiciones": {}, "historial": [],
            "creada": hoy()}


def comprar(c: dict, ticker: str, acciones: int, precio: float, tarifa: Tarifa, fecha: str | None = None,
            stop: float | None = None, objetivo: float | None = None, nota: str = "") -> str | None:
    """Registra una compra. Devuelve un mensaje de error o None si ha ido bien."""
    if acciones <= 0 or precio <= 0:
        return "El número de acciones y el precio deben ser mayores que cero."
    importe = acciones * precio
    gastos = coste_compra(importe, ticker, tarifa)["total"]
    if c.get("efectivo") is not None:
        if importe + gastos > c["efectivo"] + 1e-9:
            return (f"No tienes suficiente dinero virtual: necesitas {importe + gastos:,.2f} € "
                    f"y tienes {c['efectivo']:,.2f} €.")
        c["efectivo"] -= importe + gastos
    pos = c["posiciones"].get(ticker)
    if pos:
        total = pos["acciones"] + acciones
        pos["precio_medio"] = (pos["precio_medio"] * pos["acciones"] + importe) / total
        pos["acciones"] = total
        pos["gastos"] = pos.get("gastos", 0.0) + gastos
        pos["stop"] = stop if stop is not None else pos.get("stop")
        pos["objetivo"] = objetivo if objetivo is not None else pos.get("objetivo")
    else:
        c["posiciones"][ticker] = {"acciones": acciones, "precio_medio": precio, "fecha": fecha or hoy(),
                                   "stop": stop, "objetivo": objetivo, "gastos": gastos, "nota": nota}
    c["historial"].append({"fecha": fecha or hoy(), "tipo": "Compra", "ticker": ticker, "acciones": acciones,
                           "precio": precio, "gastos": gastos, "resultado": None, "motivo": nota})
    return None


def vender(c: dict, ticker: str, acciones: int, precio: float, tarifa: Tarifa, fecha: str | None = None,
           motivo: str = "Venta manual") -> str | None:
    pos = c["posiciones"].get(ticker)
    if not pos:
        return "No tienes esa acción."
    acciones = min(acciones, pos["acciones"])
    if acciones <= 0 or precio <= 0:
        return "Datos de venta no válidos."
    importe = acciones * precio
    gastos = tarifa.coste(importe)
    parte_gastos_compra = pos.get("gastos", 0.0) * acciones / pos["acciones"]
    resultado = importe - gastos - acciones * pos["precio_medio"] - parte_gastos_compra
    if c.get("efectivo") is not None:
        c["efectivo"] += importe - gastos
    c["historial"].append({"fecha": fecha or hoy(), "tipo": "Venta", "ticker": ticker, "acciones": acciones,
                           "precio": precio, "gastos": gastos, "resultado": resultado, "motivo": motivo})
    pos["acciones"] -= acciones
    pos["gastos"] = pos.get("gastos", 0.0) - parte_gastos_compra
    if pos["acciones"] <= 0:
        del c["posiciones"][ticker]
    return None


def revisar_ordenes(c: dict, historicos: dict[str, pd.DataFrame], tarifa: Tarifa) -> list[str]:
    """Ejecuta los stop-loss y objetivos que se hayan tocado desde la compra (como haría el broker).
    Solo para la cartera virtual."""
    eventos = []
    for ticker in list(c["posiciones"]):
        pos = c["posiciones"][ticker]
        df = historicos.get(ticker)
        if df is None or df.empty or (pos.get("stop") is None and pos.get("objetivo") is None):
            continue
        desde = pd.Timestamp(pos.get("revisado") or pos["fecha"])
        posteriores = df[df.index > desde]
        for fecha, fila in posteriores.iterrows():
            stop, obj = pos.get("stop"), pos.get("objetivo")
            precio = motivo = None
            if stop is not None and fila["Open"] <= stop:
                precio, motivo = fila["Open"], "Stop-loss (abrió por debajo)"
            elif stop is not None and fila["Low"] <= stop:
                precio, motivo = stop, "Stop-loss"
            elif obj is not None and fila["Open"] >= obj:
                precio, motivo = fila["Open"], "Objetivo alcanzado"
            elif obj is not None and fila["High"] >= obj:
                precio, motivo = obj, "Objetivo alcanzado"
            if precio is not None:
                vender(c, ticker, pos["acciones"], float(precio), tarifa, f"{fecha:%Y-%m-%d}", motivo)
                eventos.append(f"{motivo}: vendidas las acciones de {ticker} a {precio:.2f} el {fecha:%d/%m/%Y}.")
                break
        else:
            if len(posteriores):
                pos["revisado"] = f"{posteriores.index[-1]:%Y-%m-%d}"
    return eventos


def valorar(c: dict, precios: dict[str, float]) -> tuple[pd.DataFrame, dict]:
    filas = []
    for t, pos in c["posiciones"].items():
        precio = precios.get(t)
        valor = pos["acciones"] * precio if precio else None
        invertido = pos["acciones"] * pos["precio_medio"] + pos.get("gastos", 0.0)
        filas.append({"ticker": t, "acciones": pos["acciones"], "precio_medio": pos["precio_medio"],
                      "precio": precio, "valor": valor, "invertido": invertido,
                      "resultado": valor - invertido if valor is not None else None,
                      "resultado_pct": (valor / invertido - 1) * 100 if valor else None,
                      "stop": pos.get("stop"), "objetivo": pos.get("objetivo"), "fecha": pos["fecha"]})
    tabla = pd.DataFrame(filas)
    valor_pos = float(tabla["valor"].fillna(0).sum()) if len(tabla) else 0.0
    cerradas = [h["resultado"] for h in c["historial"] if h["resultado"] is not None]
    resumen = {"valor_posiciones": valor_pos, "efectivo": c.get("efectivo"),
               "realizado": float(sum(cerradas)), "operaciones_cerradas": len(cerradas),
               "ganadoras": sum(1 for r in cerradas if r > 0)}
    if c.get("capital_inicial"):
        total = valor_pos + c["efectivo"]
        resumen.update(total=total, ganancia=total - c["capital_inicial"],
                       ganancia_pct=(total / c["capital_inicial"] - 1) * 100)
    else:
        latente = float(tabla["resultado"].fillna(0).sum()) if len(tabla) else 0.0
        resumen.update(total=valor_pos, ganancia=latente,
                       ganancia_pct=latente / tabla["invertido"].sum() * 100 if len(tabla) else 0.0)
    return tabla, resumen


def dias_desde(fecha_iso: str) -> int:
    return (date.today() - datetime.fromisoformat(fecha_iso).date()).days
