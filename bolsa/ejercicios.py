"""Ejercicios guiados para la cartera virtual: se marcan solos cuando haces lo que piden."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .tickers import sector_de


@dataclass(frozen=True)
class Ejercicio:
    titulo: str
    como: str
    aprendes: str
    hecho: Callable[[dict], bool]


def _hist(c: dict) -> list[dict]:
    return c.get("historial", [])


def _diversificada(c: dict) -> bool:
    pos = c.get("posiciones", {})
    return len(pos) >= 5 and len({sector_de(t) for t in pos} - {"—"}) >= 3


def _sin_concentracion(c: dict) -> bool:
    pos = c.get("posiciones", {})
    if len(pos) < 5:
        return False
    valores = {t: p["acciones"] * p["precio_medio"] * p.get("fx_medio", 1.0) for t, p in pos.items()}
    total = sum(valores.values()) + (c.get("efectivo") or 0.0)
    return total > 0 and max(valores.values()) / total <= 0.20


EJERCICIOS: list[Ejercicio] = [
    Ejercicio("Compra con una orden limitada",
              "Elige una empresa, pon «Limitada» y un precio límite igual o un poco por debajo del actual.",
              "Con una limitada nunca pagas más de lo que decides.",
              lambda c: any(h["tipo"] == "Compra" and h.get("orden") == "limitada" for h in _hist(c))),
    Ejercicio("Protege una posición con stop-loss",
              "Al comprar, rellena el stop-loss (la app te propone uno) o añádelo después en «Cambiar stop».",
              "Decidir de antemano cuánto aceptas perder.",
              lambda c: any(p.get("stop") for p in c.get("posiciones", {}).values())
              or any(h["tipo"] == "Venta" and str(h.get("motivo", "")).startswith("Stop") for h in _hist(c))),
    Ejercicio("Cancela una orden que ya no quieres",
              "Crea una orden limitada lejos del precio actual y cancélala en «Órdenes pendientes».",
              "Una orden pendiente sigue viva hasta que se ejecuta, caduca o la cancelas.",
              lambda c: any(h["tipo"] == "Orden cancelada" for h in _hist(c))),
    Ejercicio("Vende con beneficio con una orden limitada",
              "Cuando una posición esté en positivo, véndela con una orden limitada a un precio que te deje ganancia "
              "después de comisiones.",
              "Las comisiones de compra y venta cuentan: hay que subir algo más que 0 % para ganar.",
              lambda c: any(h["tipo"] == "Venta" and h.get("orden") == "limitada" and (h.get("resultado") or 0) > 0
                            for h in _hist(c))),
    Ejercicio("Deja que el stop-loss haga su trabajo",
              "No muevas el stop hacia abajo. Si el precio cae hasta él, se venderá solo.",
              "Una pérdida pequeña a tiempo evita una grande. Es parte normal de invertir.",
              lambda c: any(h["tipo"] == "Venta" and (str(h.get("motivo", "")).startswith("Stop")
                                                      or h.get("orden") == "stop") for h in _hist(c))),
    Ejercicio("Diversifica: 5 empresas de 3 sectores distintos",
              "Ten a la vez al menos 5 posiciones de 3 sectores diferentes (bancos, eléctricas, consumo...).",
              "Si un sector cae, no arrastra todo tu dinero.",
              _diversificada),
    Ejercicio("Ninguna empresa por encima del 20 %",
              "Con 5 o más posiciones, que ninguna pese más del 20 % del total (posiciones más efectivo).",
              "La regla de concentración que usa el diagnóstico de 🏦 Mi cartera.",
              _sin_concentracion),
]


def progreso(c: dict) -> list[tuple[Ejercicio, bool]]:
    return [(e, bool(e.hecho(c))) for e in EJERCICIOS]


__all__ = ["EJERCICIOS", "Ejercicio", "progreso"]
