"""Cálculos de dinero: tamaño de la posición, comisiones, impuestos y aportaciones periódicas."""

from __future__ import annotations

import math
from dataclasses import dataclass

# Tramos del IRPF de la base del ahorro (España, 2025-2026). Revísalos cada año.
TRAMOS_AHORRO = [(6_000, 19.0), (50_000, 21.0), (200_000, 23.0), (300_000, 27.0), (math.inf, 30.0)]

# Impuesto sobre Transacciones Financieras: 0,2% al COMPRAR acciones españolas de empresas
# con capitalización superior a 1.000 M€ (casi todo el IBEX 35).
ITF_PCT = 0.2


@dataclass
class Tarifa:
    """Comisiones del broker. Los valores por defecto son ORIENTATIVOS:
    consulta tu tarifa real en la app de Bankinter (Broker > Tarifas)."""
    pct: float = 0.20
    minimo: float = 6.0
    canon_fijo: float = 1.0

    def coste(self, importe: float) -> float:
        if importe <= 0:
            return 0.0
        return max(importe * self.pct / 100, self.minimo) + self.canon_fijo


def es_espanola(ticker: str) -> bool:
    return ticker.endswith(".MC")


def coste_compra(importe: float, ticker: str, tarifa: Tarifa) -> dict:
    comision = tarifa.coste(importe)
    itf = importe * ITF_PCT / 100 if es_espanola(ticker) and not ticker.startswith("BBVAI") else 0.0
    total = comision + itf
    return {"comision": comision, "itf": itf, "total": total,
            "pct": total / importe * 100 if importe else 0.0}


def acciones_para(importe: float, precio: float) -> int:
    return int(importe // precio) if precio > 0 else 0


def tamano_por_riesgo(capital: float, riesgo_max_pct: float, entrada: float, stop: float) -> int:
    """Nº de acciones para que, si salta el stop-loss, pierdas como mucho riesgo_max_pct del capital."""
    perdida_por_accion = entrada - stop
    if perdida_por_accion <= 0:
        return 0
    por_riesgo = int(capital * riesgo_max_pct / 100 // perdida_por_accion)
    por_capital = int(capital // entrada)
    return max(0, min(por_riesgo, por_capital))


def impuesto_ganancia(ganancia: float) -> float:
    """IRPF aproximado sobre una ganancia patrimonial (base del ahorro)."""
    if ganancia <= 0:
        return 0.0
    impuesto, anterior = 0.0, 0.0
    for limite, tipo in TRAMOS_AHORRO:
        tramo = min(ganancia, limite) - anterior
        if tramo <= 0:
            break
        impuesto += tramo * tipo / 100
        anterior = limite
    return impuesto


def simular_aportaciones(mensual: float, anos: int, rent_anual_pct: float, inicial: float = 0.0) -> list[dict]:
    """Interés compuesto con aportación mensual. Devuelve una fila por año."""
    r = (1 + rent_anual_pct / 100) ** (1 / 12) - 1
    saldo, aportado, filas = inicial, inicial, []
    for mes in range(1, anos * 12 + 1):
        saldo = saldo * (1 + r) + mensual
        aportado += mensual
        if mes % 12 == 0:
            filas.append({"Año": mes // 12, "Aportado": aportado, "Valor": saldo, "Ganancia": saldo - aportado})
    return filas
