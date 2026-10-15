"""Plan de reequilibrio por pasos con calendario fiscal.

Parte de las ventas que propone el diagnóstico (para que ninguna empresa pese demasiado) y decide:
- qué vender este año y qué en enero, para pagar el menor IRPF posible (la base del ahorro es progresiva:
  19 % hasta 6.000 €, 21 % hasta 50.000 €...), con las pérdidas compensando ganancias;
- si el ahorro compensa esperar (mientras esperas, sigues con el riesgo de tener mucho en pocas empresas);
- cómo llevar el dinero liberado al fondo en varios tramos mensuales.
"""

from __future__ import annotations

import itertools
import math
from datetime import date, timedelta

from .costes import impuesto_ganancia

FRACCIONES = (0.0, 0.5, 1.0)        # parte de cada venta que se hace este año
AHORRO_MINIMO = 100.0               # por debajo de esto, no merece la pena esperar
MAX_VENTAS_COMBINATORIA = 8


def _impuestos(g1: float, g2: float) -> tuple[float, float]:
    """IRPF de este año y del siguiente; una pérdida neta de este año compensa ganancias del siguiente."""
    arrastre = min(g1, 0.0)
    return impuesto_ganancia(max(g1, 0.0)), impuesto_ganancia(max(g2 + arrastre, 0.0))


def primer_dia_habil(anio: int) -> date:
    d = date(anio, 1, 2)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def planificar(ventas: list[dict], liberado: float, destino: dict[str, float], hoy: date | None = None,
               otras_ganancias_ano: float = 0.0, tramos: int = 3) -> dict:
    """`ventas`: las del diagnóstico (ticker, nombre, acciones, importe, coste, ganancia).
    `otras_ganancias_ano`: ganancias (o pérdidas, en negativo) que ya has realizado este año."""
    hoy = hoy or date.today()
    if not ventas:
        return {"pasos": [], "aportaciones": [], "ahorro": 0.0}
    ventas = sorted(ventas, key=lambda v: v["ganancia"])          # pérdidas primero
    todo_ahora = sum(_impuestos(otras_ganancias_ano + sum(v["ganancia"] for v in ventas), 0.0))

    mejor = (todo_ahora, tuple(1.0 for _ in ventas))
    opciones = FRACCIONES if len(ventas) <= MAX_VENTAS_COMBINATORIA else (0.0, 1.0)
    for reparto in itertools.product(opciones, repeat=len(ventas)):
        g1 = otras_ganancias_ano + sum(v["ganancia"] * f for v, f in zip(ventas, reparto))
        g2 = sum(v["ganancia"] * (1 - f) for v, f in zip(ventas, reparto))
        total = sum(_impuestos(g1, g2))
        if total < mejor[0] - 0.01:
            mejor = (total, reparto)
    impuesto_plan, reparto = mejor
    ahorro = todo_ahora - impuesto_plan
    meses_espera = (12 - hoy.month) + 1
    if ahorro < AHORRO_MINIMO or all(f == 1.0 for f in reparto):
        reparto = tuple(1.0 for _ in ventas)
        impuesto_plan = todo_ahora
        motivo = ("Vende todo ahora: repartirlo entre dos años " + (f"solo ahorraría {resumen_euros(ahorro)} de IRPF"
                  if ahorro > 0 else "no ahorraría IRPF") + ", y no compensa seguir con tanto riesgo en pocas empresas "
                  "mientras esperas.")
        ahorro = 0.0
    else:
        motivo = (f"Repartiendo las ventas entre este año y enero ahorras unos {resumen_euros(ahorro)} de IRPF, porque cada "
                  "año empiezas de nuevo por el tramo más bajo (19 % hasta 6.000 €)."
                  + (f" Ojo: hasta enero quedan {meses_espera} meses con más riesgo del recomendable." if
                     meses_espera > 4 else ""))

    def lote(fraccion_este_ano: bool) -> list[dict]:
        salida = []
        for v, f in zip(ventas, reparto):
            parte = f if fraccion_este_ano else 1 - f
            n = round(v["acciones"] * parte) if 0 < parte < 1 else (v["acciones"] if parte == 1 else 0)
            if n <= 0:
                continue
            k = n / v["acciones"]
            salida.append({"ticker": v["ticker"], "nombre": v["nombre"], "acciones": n, "importe": v["importe"] * k,
                           "ganancia": v["ganancia"] * k, "precio": v.get("precio")})
        return salida

    este, siguiente = lote(True), lote(False)
    g1 = otras_ganancias_ano + sum(x["ganancia"] for x in este)
    g2 = sum(x["ganancia"] for x in siguiente)
    i1, i2 = _impuestos(g1, g2)
    pasos = []
    if este:
        pasos.append({"cuando": "Ahora (antes del 31/12/" + str(hoy.year) + ")", "fecha": hoy, "ventas": este,
                      "irpf": i1, "nota": "Vende primero las posiciones en pérdidas: compensan las ganancias del mismo "
                                          "año. No recompres esas mismas acciones en 2 meses."})
    if siguiente:
        inicio = primer_dia_habil(hoy.year + 1)
        pasos.append({"cuando": f"Desde el {inicio:%d/%m/%Y}", "fecha": inicio, "ventas": siguiente, "irpf": i2,
                      "nota": "Cuenta para la declaración del año siguiente."})

    aportaciones = []
    if liberado > 0 and destino:
        inicio = hoy
        for i in range(tramos):
            fecha = date(inicio.year + (inicio.month - 1 + i) // 12, (inicio.month - 1 + i) % 12 + 1,
                         min(inicio.day, 28))
            aportaciones.append({"fecha": fecha, "productos": {k: v / tramos for k, v in destino.items()}})
    return {"pasos": pasos, "aportaciones": aportaciones, "irpf_todo_ahora": todo_ahora,
            "irpf_plan": impuesto_plan, "ahorro": ahorro, "motivo": motivo, "tramos": tramos}


def ahorro_por_perdidas(posiciones_en_perdidas: list[dict], ganancia_prevista: float) -> float:
    """Cuánto IRPF ahorrarías vendiendo además posiciones en pérdidas (útil solo si de todos modos quieres
    reducirlas). `posiciones_en_perdidas`: dicts con 'ganancia' negativa."""
    perdidas = sum(min(p["ganancia"], 0.0) for p in posiciones_en_perdidas)
    return impuesto_ganancia(max(ganancia_prevista, 0.0)) - impuesto_ganancia(max(ganancia_prevista + perdidas, 0.0))


def resumen_euros(x: float) -> str:
    return f"{x:,.0f} €".replace(",", ".") if math.isfinite(x) else "—"


__all__ = ["planificar", "ahorro_por_perdidas", "primer_dia_habil"]
