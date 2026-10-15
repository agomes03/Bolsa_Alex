"""Diario de inversiones: apuntas por qué haces algo y, pasado un tiempo, la app te enseña qué pasó después.

Es la forma más sencilla de aprender de tus propias decisiones. Ojo: un buen resultado no siempre significa una
buena decisión (y al revés). Lo importante es si tu motivo se cumplió.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

ACCIONES = ["Compra", "Venta", "No hago nada", "Idea para vigilar"]
REVISAR_EN = {"1 mes": 1, "3 meses": 3, "6 meses": 6, "1 año": 12}


def nueva(lista: list[dict], ticker: str, nombre: str, accion: str, precio: float | None, motivo: str,
          meses_revision: int = 3, hoy: date | None = None) -> str | None:
    if accion not in ACCIONES:
        return "Elige qué has hecho."
    if not motivo.strip():
        return "Escribe en una frase por qué lo haces: es lo que da valor al diario."
    hoy = hoy or date.today()
    revisar = (pd.Timestamp(hoy) + pd.DateOffset(months=meses_revision)).date()
    lista.append({"id": max((e["id"] for e in lista), default=0) + 1, "fecha": hoy.isoformat(), "ticker": ticker,
                  "nombre": nombre, "accion": accion, "precio": float(precio) if precio else None,
                  "motivo": motivo.strip(), "revisar": revisar.isoformat(), "revisada": None, "leccion": ""})
    return None


def pendientes(lista: list[dict], hoy: date | None = None) -> list[dict]:
    """Apuntes cuya fecha de revisión ya ha llegado y aún no has revisado."""
    hoy = (hoy or date.today()).isoformat()
    return [e for e in lista if not e.get("revisada") and e["revisar"] <= hoy]


def evaluar(e: dict, precio_actual: float | None) -> dict:
    """Qué ha pasado desde el apunte, en una frase."""
    if not e.get("precio") or not precio_actual:
        return {"cambio": None, "frase": "Sin precio para comparar."}
    cambio = precio_actual / e["precio"] - 1
    p = f"{abs(cambio) * 100:.1f} %".replace(".", ",")
    sube = cambio >= 0
    if abs(cambio) < 0.02:
        frase = f"{e['nombre']} está prácticamente igual que cuando lo apuntaste."
    elif e["accion"] == "Compra":
        frase = (f"Desde que compraste, {e['nombre']} ha {'subido' if sube else 'bajado'} un {p}. "
                 + ("De momento va a tu favor." if sube else "De momento va en contra."))
    elif e["accion"] == "Venta":
        frase = (f"Desde que vendiste, {e['nombre']} ha {'subido' if sube else 'bajado'} un {p}. "
                 + ("Si no hubieras vendido, tendrías más; pero si vendiste para reducir riesgo, eso no cambia."
                    if sube else "Vender te ha ahorrado esa caída."))
    else:
        frase = f"Desde tu apunte, {e['nombre']} ha {'subido' if sube else 'bajado'} un {p}."
    return {"cambio": cambio, "frase": frase}


def marcar_revisada(lista: list[dict], id_: int, leccion: str, hoy: date | None = None) -> None:
    for e in lista:
        if e["id"] == id_:
            e["revisada"], e["leccion"] = (hoy or date.today()).isoformat(), leccion.strip()


__all__ = ["ACCIONES", "REVISAR_EN", "nueva", "pendientes", "evaluar", "marcar_revisada"]
