"""Carteras: la virtual (dinero ficticio para practicar) y la real (lo que tienes en Bankinter).

Se guardan como diccionarios sencillos (JSON). Los precios se guardan en la divisa del valor (como los ves
en Bankinter) y los importes de dinero, en euros: `fx` es cuántos euros vale 1 unidad de esa divisa
(1 para valores en euros).
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
            stop: float | None = None, objetivo: float | None = None, nota: str = "", fx: float = 1.0,
            orden: str | None = None) -> str | None:
    """`fecha` puede llevar hora ('2026-10-15T12:35'): así los stop solo miran precios posteriores."""
    """Registra una compra. Devuelve un mensaje de error o None si ha ido bien."""
    if acciones <= 0 or precio <= 0:
        return "El número de acciones y el precio deben ser mayores que cero."
    importe = acciones * precio * fx
    gastos = coste_compra(importe, ticker, tarifa)["total"]
    if c.get("efectivo") is not None:
        if importe + gastos > c["efectivo"] + 1e-9:
            return (f"No tienes suficiente dinero virtual: necesitas {importe + gastos:,.2f} € "
                    f"y tienes {c['efectivo']:,.2f} €.").replace(",", "X").replace(".", ",").replace("X", ".")
        c["efectivo"] -= importe + gastos
    pos = c["posiciones"].get(ticker)
    if pos:
        total = pos["acciones"] + acciones
        local_previo = pos["precio_medio"] * pos["acciones"]
        pos["fx_medio"] = (pos.get("fx_medio", 1.0) * local_previo + fx * acciones * precio) / (local_previo + acciones * precio)
        pos["precio_medio"] = (local_previo + acciones * precio) / total
        pos["acciones"] = total
        pos["gastos"] = pos.get("gastos", 0.0) + gastos
        pos["stop"] = stop if stop is not None else pos.get("stop")
        pos["objetivo"] = objetivo if objetivo is not None else pos.get("objetivo")
    else:
        c["posiciones"][ticker] = {"acciones": acciones, "precio_medio": precio, "fx_medio": fx,
                                   "fecha": (fecha or hoy())[:10], "desde": fecha or hoy(), "stop": stop,
                                   "objetivo": objetivo, "gastos": gastos, "nota": nota}
    c["historial"].append({"fecha": fecha or hoy(), "tipo": "Compra", "ticker": ticker, "acciones": acciones,
                           "precio": precio, "gastos": gastos, "resultado": None, "motivo": nota, "fx": fx,
                           **({"orden": orden} if orden else {})})
    return None


def vender(c: dict, ticker: str, acciones: int, precio: float, tarifa: Tarifa, fecha: str | None = None,
           motivo: str = "Venta manual", fx: float = 1.0, orden: str | None = None) -> str | None:
    pos = c["posiciones"].get(ticker)
    if not pos:
        return "No tienes esa acción."
    acciones = min(acciones, pos["acciones"])
    if acciones <= 0 or precio <= 0:
        return "Datos de venta no válidos."
    importe = acciones * precio * fx
    gastos = tarifa.coste(importe, ticker)
    parte_gastos_compra = pos.get("gastos", 0.0) * acciones / pos["acciones"]
    invertido = acciones * pos["precio_medio"] * pos.get("fx_medio", 1.0)
    resultado = importe - gastos - invertido - parte_gastos_compra
    if c.get("efectivo") is not None:
        c["efectivo"] += importe - gastos
    c["historial"].append({"fecha": fecha or hoy(), "tipo": "Venta", "ticker": ticker, "acciones": acciones,
                           "precio": precio, "gastos": gastos, "resultado": resultado, "motivo": motivo, "fx": fx,
                           **({"orden": orden} if orden else {})})
    pos["acciones"] -= acciones
    pos["gastos"] = pos.get("gastos", 0.0) - parte_gastos_compra
    if pos["acciones"] <= 0:
        del c["posiciones"][ticker]
    return None


def revisar_ordenes(c: dict, historicos: dict[str, pd.DataFrame], tarifa: Tarifa,
                    fx: dict[str, float] | None = None) -> list[str]:
    """Ejecuta los stop-loss y objetivos que se hayan tocado desde la compra (como haría el broker).
    Solo para la cartera virtual."""
    fx = fx or {}
    eventos = []
    for ticker in list(c["posiciones"]):
        pos = c["posiciones"][ticker]
        df = historicos.get(ticker)
        if df is None or df.empty or (pos.get("stop") is None and pos.get("objetivo") is None):
            continue
        desde = pd.Timestamp(pos.get("revisado") or pos.get("desde") or pos["fecha"])
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
                vender(c, ticker, pos["acciones"], float(precio), tarifa, _iso(fecha), motivo,
                       fx=fx.get(ticker, pos.get("fx_medio", 1.0)), orden="stop" if motivo.startswith("Stop") else
                       "limitada")
                eventos.append(f"{motivo}: vendidas las acciones de {ticker} a {_num(float(precio))} "
                               f"({_cuando(_iso(fecha))}).")
                break
        else:
            if len(posteriores):
                pos["revisado"] = _iso(posteriores.index[-1])
    return eventos


def _iso(ts) -> str:
    """Fecha (y hora si no es medianoche) en ISO: '2026-10-15' o '2026-10-15T12:35'."""
    ts = pd.Timestamp(ts)
    return f"{ts:%Y-%m-%d}" if (ts.hour, ts.minute) == (0, 0) else f"{ts:%Y-%m-%dT%H:%M}"


# --------------------------------------------------------------------------- órdenes (cartera virtual)
# Funcionan como en el bróker: una orden queda pendiente hasta que el precio la permite o caduca.
# - Limitada de compra: se ejecuta si el precio baja hasta el límite (al límite o mejor).
# - Limitada de venta: si el precio sube hasta el límite.
# - A mercado: al precio de ese momento (o en la apertura de la siguiente sesión si el mercado está cerrado).
# - Stop de venta (como en Bankinter, con activación y límite): al tocar la activación se lanza una venta
#   limitada; si el precio ya está por debajo del límite, queda pendiente como limitada.
MARGEN_MERCADO = 0.03   # para reservar dinero en una compra a mercado (el precio puede moverse)


def _estimado_compra(o: dict, tarifa: Tarifa) -> float:
    precio = o["limite"] if o["tipo"] == "limitada" else o["precio_ref"] * (1 + MARGEN_MERCADO)
    importe = o["acciones"] * precio * o.get("fx", 1.0)
    return importe + coste_compra(importe, o["ticker"], tarifa)["total"]


def comprometido(c: dict, tarifa: Tarifa) -> float:
    """Dinero reservado por las órdenes de compra pendientes (como el «saldo comprometido» del bróker)."""
    return sum(_estimado_compra(o, tarifa) for o in c.get("ordenes", []) if o["sentido"] == "compra")


def disponible(c: dict, tarifa: Tarifa) -> float:
    return (c.get("efectivo") or 0.0) - comprometido(c, tarifa)


def acciones_libres(c: dict, ticker: str) -> int:
    """Acciones que se pueden vender: las que tienes menos las que ya están en órdenes de venta."""
    pos = c["posiciones"].get(ticker)
    en_venta = sum(o["acciones"] for o in c.get("ordenes", []) if o["ticker"] == ticker and o["sentido"] == "venta")
    return max(0, (pos["acciones"] if pos else 0) - en_venta)


def nueva_orden(c: dict, ticker: str, sentido: str, tipo: str, acciones: int, tarifa: Tarifa, *, precio_ref: float,
                ahora: str, validez: str, limite: float | None = None, activacion: float | None = None,
                fx: float = 1.0, stop: float | None = None, objetivo: float | None = None) -> str | None:
    """Registra una orden pendiente. Devuelve un mensaje de error o None. `ahora` y `validez` en ISO."""
    if acciones <= 0:
        return "El número de títulos debe ser mayor que cero."
    if tipo not in ("limitada", "mercado", "stop") or sentido not in ("compra", "venta"):
        return "Tipo de orden no válido."
    if tipo == "limitada" and not (limite and limite > 0):
        return "Indica el precio límite."
    if tipo == "stop":
        if sentido != "venta":
            return "Las órdenes stop de esta cartera son de venta (para limitar pérdidas)."
        if not (activacion and limite and 0 < limite <= activacion):
            return "En una orden stop, el precio límite debe ser igual o menor que el de activación."
        if activacion >= precio_ref:
            return "La activación de un stop de venta debe estar por debajo del precio actual."
    if validez < ahora[:10]:
        return "La fecha de validez ya ha pasado."
    o = {"id": c.get("siguiente_id", 1), "ticker": ticker, "sentido": sentido, "tipo": tipo, "acciones": int(acciones),
         "limite": limite, "activacion": activacion, "precio_ref": precio_ref, "fx": fx, "creada": ahora,
         "validez": validez, "stop": stop, "objetivo": objetivo}
    if sentido == "compra":
        if stop is not None and stop >= (limite or precio_ref):
            return "El stop-loss debe estar por debajo del precio de compra."
        necesario = _estimado_compra(o, tarifa)
        if necesario > disponible(c, tarifa) + 1e-9:
            return (f"No tienes suficiente dinero disponible: la orden necesita unos {_eur(necesario)} y tienes "
                    f"{_eur(disponible(c, tarifa))} (descontadas otras órdenes de compra pendientes).")
    elif acciones > acciones_libres(c, ticker):
        return f"Solo puedes vender {acciones_libres(c, ticker)} títulos de este valor (el resto ya está en otras órdenes)."
    c.setdefault("ordenes", []).append(o)
    c["siguiente_id"] = o["id"] + 1
    return None


def cancelar_orden(c: dict, id_orden: int, motivo: str = "Orden cancelada", fecha: str | None = None) -> bool:
    for o in c.get("ordenes", []):
        if o["id"] == id_orden:
            c["ordenes"].remove(o)
            c["historial"].append({"fecha": fecha or hoy(), "tipo": motivo, "ticker": o["ticker"],
                                   "acciones": o["acciones"], "precio": o.get("limite"), "gastos": 0.0,
                                   "resultado": None, "motivo": f"{o['sentido']} {o['tipo']}", "orden": o["tipo"]})
            return True
    return False


def _precio_ejecucion(o: dict, fila) -> float | None:
    """Precio al que se ejecutaría la orden en esta vela, o None si no se ejecuta."""
    if o["tipo"] == "mercado":
        return float(fila["Open"])
    if o["tipo"] == "limitada":
        if o["sentido"] == "compra" and fila["Low"] <= o["limite"]:
            return float(min(fila["Open"], o["limite"]))
        if o["sentido"] == "venta" and fila["High"] >= o["limite"]:
            return float(max(fila["Open"], o["limite"]))
    return None


def _titulos(n: int) -> str:
    return f"{n} título" if n == 1 else f"{n} títulos"


def _ejecutar(c: dict, o: dict, precio: float, cuando: str, tarifa: Tarifa) -> str:
    from .tickers import nombre_de

    nombre = nombre_de(o["ticker"])
    if o["sentido"] == "compra":
        err = comprar(c, o["ticker"], o["acciones"], precio, tarifa, cuando, o.get("stop"), o.get("objetivo"),
                      nota=f"Orden {o['tipo']} nº {o['id']}", fx=o.get("fx", 1.0), orden=o["tipo"])
        if err:
            return f"❌ No se pudo ejecutar la compra de {nombre}: {err}"
        return f"✅ Compra ejecutada: {_titulos(o['acciones'])} de {nombre} a {_num(precio)} ({_cuando(cuando)})."
    err = vender(c, o["ticker"], o["acciones"], precio, tarifa, cuando, f"Orden {o['tipo']} nº {o['id']}",
                 fx=o.get("fx", 1.0), orden=o["tipo"])
    if err:
        return f"❌ No se pudo ejecutar la venta de {nombre}: {err}"
    return f"✅ Venta ejecutada: {_titulos(o['acciones'])} de {nombre} a {_num(precio)} ({_cuando(cuando)})."


def ejecutar_ordenes(c: dict, barras: dict[str, pd.DataFrame], tarifa: Tarifa, ahora: str,
                     cotizaciones: dict[str, tuple[float, bool]] | None = None) -> list[str]:
    """Revisa las órdenes pendientes con las velas posteriores a su creación (diarias o intradía, en hora de
    Madrid) y con la cotización actual si el mercado está abierto: {ticker: (precio, abierto)}."""
    cotizaciones = cotizaciones or {}
    eventos = _anular_ventas_sin_acciones(c, ahora)
    for o in sorted(list(c.get("ordenes", [])), key=lambda x: x["creada"]):
        if o not in c.get("ordenes", []):
            continue
        df = barras.get(o["ticker"])
        hecho = False
        if df is not None and not df.empty:
            fin_validez = pd.Timestamp(o["validez"]) + pd.Timedelta(days=1)
            velas = df[(df.index > pd.Timestamp(o["creada"])) & (df.index < fin_validez)]
            for ts, fila in velas.iterrows():
                if o["tipo"] == "stop":
                    if fila["Low"] <= o["activacion"]:
                        precio = float(min(fila["Open"], o["activacion"]))
                        if precio >= o["limite"]:
                            c["ordenes"].remove(o)
                            eventos.append("🛑 Stop activado. " + _ejecutar(c, o, precio, _iso(ts), tarifa))
                            hecho = True
                            break
                        o["tipo"] = "limitada"   # cayó por debajo del límite: queda como venta limitada
                        eventos.append(f"⚠️ El stop de {o['ticker']} se activó pero el precio cayó por debajo del "
                                       f"límite ({_num(o['limite'])}): queda como orden limitada de venta.")
                    continue
                precio = _precio_ejecucion(o, fila)
                if precio is not None:
                    c["ordenes"].remove(o)
                    eventos.append(_ejecutar(c, o, precio, _iso(ts), tarifa))
                    hecho = True
                    break
        if hecho:
            continue
        precio, abierto = cotizaciones.get(o["ticker"], (None, False))
        if abierto and precio and ahora[:10] <= o["validez"]:
            ok = (o["tipo"] == "mercado"
                  or (o["tipo"] == "limitada" and o["sentido"] == "compra" and precio <= o["limite"])
                  or (o["tipo"] == "limitada" and o["sentido"] == "venta" and precio >= o["limite"])
                  or (o["tipo"] == "stop" and o["limite"] <= precio <= o["activacion"]))
            if ok:
                c["ordenes"].remove(o)
                eventos.append(_ejecutar(c, o, precio, ahora, tarifa))
                continue
        if ahora[:10] > o["validez"]:
            cancelar_orden(c, o["id"], "Orden caducada", ahora)
            eventos.append(f"⌛ Ha caducado la orden {o['sentido']} {o['tipo']} de {o['ticker']} sin ejecutarse.")
    return eventos


def _anular_ventas_sin_acciones(c: dict, ahora: str) -> list[str]:
    """Si un stop-loss de la posición ya vendió las acciones, sus órdenes de venta pendientes sobran."""
    eventos = []
    for o in list(c.get("ordenes", [])):
        if o["sentido"] == "venta" and o["ticker"] not in c["posiciones"]:
            cancelar_orden(c, o["id"], "Orden anulada", ahora)
            eventos.append(f"Anulada la orden de venta nº {o['id']} de {o['ticker']}: ya no tienes esas acciones.")
    return eventos


def _num(x: float) -> str:
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _eur(x: float) -> str:
    return _num(x) + " €"


def _cuando(iso: str) -> str:
    ts = pd.Timestamp(iso)
    return f"{ts:%d/%m/%Y}" if (ts.hour, ts.minute) == (0, 0) else f"{ts:%d/%m/%Y %H:%M}"


def valorar(c: dict, precios: dict[str, float], fx: dict[str, float] | None = None) -> tuple[pd.DataFrame, dict]:
    """Valor en euros de cada posición. `precios` en la divisa del valor; `fx`: euros por unidad."""
    fx = fx or {}
    filas = []
    for t, pos in c["posiciones"].items():
        precio = precios.get(t)
        f = fx.get(t, 1.0)
        valor = pos["acciones"] * precio * f if precio else None
        invertido = pos["acciones"] * pos["precio_medio"] * pos.get("fx_medio", 1.0) + pos.get("gastos", 0.0)
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


def evolucion(c: dict, cierres_eur: dict[str, pd.Series], hasta: str | None = None) -> pd.Series:
    """Valor de la cartera virtual cada día desde que se creó, rehaciendo sus operaciones con los cierres
    (en euros) de cada valor."""
    if not c.get("capital_inicial"):
        return pd.Series(dtype=float)
    inicio = pd.Timestamp(c["creada"])
    fin = pd.Timestamp(hasta or hoy())
    dias = pd.bdate_range(inicio, fin)
    if len(dias) == 0:
        return pd.Series(dtype=float)
    precios = pd.DataFrame({t: s for t, s in cierres_eur.items() if s is not None and len(s)}).sort_index()
    precios = precios.reindex(precios.index.union(dias)).ffill().reindex(dias) if len(precios.columns) else \
        pd.DataFrame(index=dias)
    movimientos = sorted((h for h in c["historial"] if h["tipo"] in ("Compra", "Venta")), key=lambda h: h["fecha"])
    efectivo, acciones, ultimo = c["capital_inicial"], {}, {}
    valores, i = [], 0
    for dia in dias:
        while i < len(movimientos) and pd.Timestamp(movimientos[i]["fecha"][:10]) <= dia:
            h = movimientos[i]
            importe = h["acciones"] * h["precio"] * h.get("fx", 1.0)
            signo = 1 if h["tipo"] == "Compra" else -1
            efectivo -= signo * importe + h.get("gastos", 0.0)
            acciones[h["ticker"]] = acciones.get(h["ticker"], 0) + signo * h["acciones"]
            ultimo[h["ticker"]] = h["precio"] * h.get("fx", 1.0)
            i += 1
        valor = efectivo
        for t, n in acciones.items():
            if n:
                p = precios.at[dia, t] if t in precios.columns and pd.notna(precios.at[dia, t]) else ultimo[t]
                valor += n * p
        valores.append(valor)
    return pd.Series(valores, index=dias)


def dias_desde(fecha_iso: str) -> int:
    return (date.today() - datetime.fromisoformat(fecha_iso).date()).days
