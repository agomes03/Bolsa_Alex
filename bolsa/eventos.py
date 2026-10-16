"""Calendario de lo que viene para tus valores: presentación de resultados, fecha ex-dividendo (el último día para
cobrarlo es el anterior) y pago del dividendo. Datos de Yahoo Finance; las fechas de resultados son a veces
estimadas y pueden moverse unos días."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

TIPOS = {
    "resultados": ("📊", "Presenta resultados",
                   "Suele moverse mucho ese día. Evita comprar justo antes; si tienes stop-loss, revísalo."),
    "ex_dividendo": ("✂️", "Fecha ex-dividendo",
                     "Para cobrar el dividendo tienes que tener las acciones el día ANTERIOR. Ese día el precio baja "
                     "más o menos lo que paga."),
    "pago_dividendo": ("💶", "Pago del dividendo", "Te llega el dinero a la cuenta (menos la retención)."),
}
CAMPOS = {"resultados": ("earningsTimestampStart", "earningsTimestamp"), "ex_dividendo": ("exDividendDate",),
          "pago_dividendo": ("dividendDate",)}


def _a_fecha(x) -> date | None:
    if x is None:
        return None
    if isinstance(x, (int, float)):
        if x <= 0:
            return None
        return datetime.fromtimestamp(float(x), tz=timezone.utc).date()
    if isinstance(x, datetime):
        return x.date()
    if isinstance(x, date):
        return x
    try:
        return date.fromisoformat(str(x)[:10])
    except ValueError:
        return None


def proximos(nombres: dict[str, str], fundamentales: dict[str, dict], hoy: date | None = None,
             dias: int = 30) -> list[dict]:
    """Eventos de los próximos `dias` días para esos valores, ordenados por fecha."""
    hoy = hoy or date.today()
    hasta = hoy + timedelta(days=dias)
    salida = []
    for t, nombre in nombres.items():
        info = fundamentales.get(t) or {}
        for tipo, campos in CAMPOS.items():
            f = next((d for d in (_a_fecha(info.get(c)) for c in campos) if d), None)
            if f and hoy <= f <= hasta:
                icono, titulo, consejo = TIPOS[tipo]
                salida.append({"fecha": f, "ticker": t, "nombre": nombre, "tipo": tipo, "icono": icono,
                               "titulo": titulo, "consejo": consejo, "dias": (f - hoy).days})
    return sorted(salida, key=lambda e: (e["fecha"], e["nombre"]))


def cuando(e: dict) -> str:
    return "hoy" if e["dias"] == 0 else "mañana" if e["dias"] == 1 else f"en {e['dias']} días ({e['fecha']:%d/%m})"


def texto_telegram(eventos: list[dict]) -> str:
    """Lo de hoy y mañana, para el mensaje diario."""
    cerca = [e for e in eventos if e["dias"] <= 1]
    if not cerca:
        return ""
    return "📅 Atento:\n" + "\n".join(f"• {e['icono']} {e['nombre']}: {e['titulo'].lower()} {cuando(e)}"
                                     for e in cerca)


__all__ = ["TIPOS", "proximos", "cuando", "texto_telegram"]
