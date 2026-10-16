"""Ficha visual de una empresa en 5 ejes (inspirada en el «copo de nieve» de Simply Wall St): valoración, futuro,
pasado, salud financiera y dividendo, cada uno de 0 a 6. Cada punto sale de una comprobación sencilla que se
explica; si Yahoo no da un dato, esa comprobación no cuenta (y se dice)."""

from __future__ import annotations

EJES = ["Valoración", "Futuro", "Pasado", "Salud", "Dividendo"]
MINIMO = 3                  # comprobaciones con dato necesarias para puntuar un eje


def _chequeos(fund: dict, precio: float | None, var_1a: float | None) -> dict[str, list[tuple[str, bool | None]]]:
    f = fund or {}
    per, per_f, pvc = f.get("trailingPE"), f.get("forwardPE"), f.get("priceToBook")
    objetivo = f.get("targetMeanPrice")
    pot = (objetivo / precio - 1) if objetivo and precio else None
    rent = f.get("dividendYield")                # en %
    payout = f.get("payoutRatio")
    deuda, liquidez = f.get("debtToEquity"), f.get("currentRatio")
    roe, margen = f.get("returnOnEquity"), f.get("profitMargins")
    beneficio, ventas = f.get("earningsGrowth"), f.get("revenueGrowth")

    def si(x, cond):
        return None if x is None else bool(cond(x))

    return {
        "Valoración": [
            ("PER por debajo de 20 (no está cara frente a lo que gana)", si(per, lambda x: 0 < x < 20)),
            ("PER por debajo de 15", si(per, lambda x: 0 < x < 15)),
            ("Se espera que gane más el año que viene (PER futuro menor que el actual)",
             None if per is None or per_f is None else 0 < per_f < per),
            ("Cotiza a menos de 1,5 veces lo que vale en libros", si(pvc, lambda x: 0 < x < 1.5)),
            ("Los analistas le ven más de un 10 % de subida", si(pot, lambda x: x > 0.10)),
            ("Más de un 20 % de subida según los analistas", si(pot, lambda x: x > 0.20)),
        ],
        "Futuro": [
            ("El beneficio crece", si(beneficio, lambda x: x > 0)),
            ("El beneficio crece más de un 10 %", si(beneficio, lambda x: x > 0.10)),
            ("Las ventas crecen", si(ventas, lambda x: x > 0)),
            ("Las ventas crecen más de un 5 %", si(ventas, lambda x: x > 0.05)),
            ("Los analistas recomiendan comprar", si(f.get("recommendationKey"),
                                                     lambda x: x in ("buy", "strong_buy"))),
            ("El precio objetivo está por encima del precio de hoy", si(pot, lambda x: x > 0)),
        ],
        "Pasado": [
            ("Rentabilidad sobre sus fondos propios (ROE) de más del 10 %", si(roe, lambda x: x > 0.10)),
            ("ROE de más del 15 % (muy buen negocio)", si(roe, lambda x: x > 0.15)),
            ("Gana dinero: margen de beneficio positivo", si(margen, lambda x: x > 0)),
            ("Margen de beneficio de más del 15 %", si(margen, lambda x: x > 0.15)),
            ("La acción ha subido en el último año", si(var_1a, lambda x: x > 0)),
            ("Ha subido más de un 10 % en el último año", si(var_1a, lambda x: x > 10)),
        ],
        "Salud": [
            ("Deuda menor que sus fondos propios", si(deuda, lambda x: x < 100)),
            ("Deuda baja (menos de la mitad de sus fondos propios)", si(deuda, lambda x: x < 50)),
            ("Puede pagar lo que vence este año (liquidez mayor que 1)", si(liquidez, lambda x: x > 1)),
            ("Liquidez holgada (más de 1,5)", si(liquidez, lambda x: x > 1.5)),
            ("Se mueve menos que el mercado (beta menor que 1,2)", si(f.get("beta"), lambda x: x < 1.2)),
            ("Gana dinero (no quema caja con pérdidas)", si(margen, lambda x: x > 0)),
        ],
        "Dividendo": [
            ("Paga dividendo", si(rent, lambda x: x > 0)),
            ("Rentabilidad por dividendo de más del 2 %", si(rent, lambda x: x > 2)),
            ("Más del 4 %", si(rent, lambda x: x > 4)),
            ("Reparte menos del 80 % de lo que gana (dividendo sostenible)", si(payout, lambda x: 0 < x < 0.8)),
            ("Reparte menos del 60 % (margen de seguridad)", si(payout, lambda x: 0 < x < 0.6)),
            ("Ha pagado más del 2 % de media los últimos 5 años", si(f.get("fiveYearAvgDividendYield"),
                                                                       lambda x: x > 2)),
        ],
    }


def ficha(fund: dict, precio: float | None = None, var_1a: float | None = None) -> dict:
    """{eje: {puntos (0-6), cumple, total, chequeos: [(texto, True/False/None)]}}. Los puntos se escalan a 6 con las
    comprobaciones que tienen dato."""
    salida = {}
    for eje, lista in _chequeos(fund, precio, var_1a).items():
        con_dato = [c for c in lista if c[1] is not None]
        cumple = sum(1 for c in con_dato if c[1])
        # Con menos de 3 datos el eje no es fiable (p. ej. la salud de un banco, sin deuda ni liquidez en Yahoo).
        salida[eje] = {"puntos": round(cumple / len(con_dato) * 6, 1) if len(con_dato) >= MINIMO else None,
                       "cumple": cumple,
                       "total": len(con_dato), "chequeos": lista}
    return salida


def resumen(f: dict) -> str:
    """«Fuerte en futuro y dividendo; flojo en valoración»."""
    con = {e: v["puntos"] for e, v in f.items() if v["puntos"] is not None}
    if not con:
        return "No hay datos suficientes para la ficha."
    fuertes = [e.lower() for e, p in con.items() if p >= 4.5]
    flojos = [e.lower() for e, p in con.items() if p <= 2]
    partes = []
    if fuertes:
        partes.append("fuerte en " + _lista(fuertes))
    if flojos:
        partes.append("floja en " + _lista(flojos))
    if not partes:
        return "Equilibrada: sin puntos muy fuertes ni muy flojos."
    texto = "; ".join(partes) + "."
    return texto[0].upper() + texto[1:]


def _lista(xs: list[str]) -> str:
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " y " + xs[-1]


__all__ = ["EJES", "ficha", "resumen"]
