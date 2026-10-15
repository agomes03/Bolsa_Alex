"""Tus pendientes: lo que TÚ te has propuesto (avisos de precio, aportación mensual, diario, Renta), en una lista.

Se muestra arriba en 🧭 Hoy y se añade al aviso diario de Telegram, para que la app sea el único sitio que mirar.
"""

from __future__ import annotations

from datetime import date

from . import alertas, aportaciones, diario, renta


def _item(prioridad: int, icono: str, titulo: str, texto: str, pagina: str = "seguimiento") -> dict:
    return {"prioridad": prioridad, "icono": icono, "titulo": titulo, "texto": texto, "pagina": pagina}


def _eur(x: float) -> str:
    return f"{x:,.0f} €".replace(",", ".")


def pendientes(d: dict, hoy: date | None = None) -> list[dict]:
    """`d`: los datos guardados del usuario."""
    hoy = hoy or date.today()
    salida = []
    for a in d.get("alertas", []):
        if a.get("disparada") and not a.get("vista"):
            salida.append(_item(1, "🔔", alertas.texto(a, a.get("precio_disparo")),
                                f"Saltó el {date.fromisoformat(a['disparada']).strftime('%d/%m')}. Decide con calma "
                                "si haces algo; luego márcalo como visto."))
    cfg = d.get("aportacion") or {}
    if aportaciones.pendiente(cfg, hoy):
        salida.append(_item(2, "💶", f"Toca tu aportación mensual de {_eur(cfg['importe'])}",
                            "Mira a dónde llevarla para acercarte a tu reparto ideal y apúntala cuando la hagas."))
    revisar = diario.pendientes(d.get("diario", []), hoy)
    if revisar:
        nombres = ", ".join(sorted({e["nombre"] for e in revisar})[:3])
        salida.append(_item(3, "📓", f"Revisa {len(revisar)} apunte{'s' if len(revisar) > 1 else ''} de tu diario",
                            f"Ha pasado el tiempo que te diste ({nombres}). ¿Se cumplió tu motivo?"))
    if renta.en_campana(hoy):
        salida.append(_item(3, "🧾", f"Campaña de la Renta {hoy.year - 1}",
                            "Tienes tus ventas y dividendos del año resumidos para comparar con el borrador."))
    elif hoy.month == 12 or (hoy.month == 11 and hoy.day >= 15):
        salida.append(_item(3, "🧾", "Antes del 31 de diciembre",
                            "Si has vendido con ganancias este año, mira si te conviene compensarlas con pérdidas "
                            "(plan fiscal en 🏦 Mi cartera).", "bankinter"))
    return sorted(salida, key=lambda x: x["prioridad"])


def texto_telegram(d: dict, hoy: date | None = None) -> str:
    items = [x for x in pendientes(d, hoy) if x["icono"] != "🔔"]   # los avisos de precio ya llegan al momento
    return ("📌 Tus pendientes\n" + "\n".join(f"• {x['titulo']}" for x in items)) if items else ""


__all__ = ["pendientes", "texto_telegram"]
