"""Letras del Tesoro: cuánto pagas, cuánto cobras al vencer y qué queda después de impuestos.

Las Letras se compran «al descuento»: pagas menos de 1.000 € por cada una y al vencer cobras 1.000 €. La
diferencia es el interés. El Tesoro calcula el precio con los días reales del plazo sobre una base de 360.
"""

from __future__ import annotations

import math

from .costes import impuesto_ganancia

NOMINAL = 1000.0
# Días habituales de cada plazo en las subastas.
PLAZOS = {"3 meses": 91, "6 meses": 182, "9 meses": 273, "12 meses": 364}


def precio(tipo_pct: float, dias: int) -> float:
    """Precio de una Letra de 1.000 € con un tipo de interés (el «tipo medio» de la subasta)."""
    return NOMINAL / (1 + tipo_pct / 100 * dias / 360)


def calcular(importe: float, tipo_pct: float, dias: int) -> dict:
    """Con el dinero que quieres poner: cuántas Letras, lo que pagas, lo que cobras y lo neto tras el IRPF."""
    p = precio(tipo_pct, dias)
    letras = math.floor(importe / p) if p > 0 else 0
    pagas = letras * p
    cobras = letras * NOMINAL
    intereses = cobras - pagas
    impuesto = impuesto_ganancia(intereses)
    return {"precio": p, "letras": letras, "pagas": pagas, "cobras": cobras, "intereses": intereses,
            "impuesto": impuesto, "neto": intereses - impuesto, "sobra": importe - pagas,
            "tae": ((NOMINAL / p) ** (365 / dias) - 1) * 100 if p else 0.0}
