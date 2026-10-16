"""Avisos de precio por Telegram: cada hora en horario de mercado (GitHub Actions, .github/workflows/alertas.yml).

Lee tus avisos del Gist (los que creas en la app, 📒 Seguimiento) y te escribe solo si el precio ha CRUZADO tu
nivel en la última hora completa. No modifica tus datos: el aviso queda marcado como «saltado» la próxima vez que
abras la app.

Variables de entorno: TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, GIST_TOKEN y GIST_ID (las mismas del aviso diario).
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bolsa import alertas, almacen, avisos, cuentas, datos  # noqa: E402


def ventana(ahora: datetime) -> tuple[datetime, datetime]:
    """La última hora completa en hora de Madrid, sin zona (como las velas de datos.intradia)."""
    hasta = ahora.astimezone(ZoneInfo("Europe/Madrid")).replace(minute=0, second=0, microsecond=0, tzinfo=None)
    return hasta - timedelta(hours=1), hasta


def main() -> int:
    faltan = [v for v in ("TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID", "GIST_TOKEN", "GIST_ID") if not os.environ.get(v)]
    if faltan:
        print("Faltan secretos:", ", ".join(faltan), "- no se comprueban avisos.")
        return 0
    d = almacen.Almacen(gist_token=os.environ["GIST_TOKEN"], gist_id=os.environ["GIST_ID"]).cargar()
    lista = cuentas.asegurar(d)                 # los avisos son de cada cuenta (tuya, de tu madre...)
    activas = {n: [a for a in c.get("alertas", []) if not a.get("disparada")] for n, c in lista.items()}
    if not any(activas.values()):
        print("No hay avisos activos.")
        return 0
    desde, hasta = ventana(datetime.now(ZoneInfo("UTC")))
    tickers = sorted({a["ticker"] for lst in activas.values() for a in lst})
    intradia = {t: datos.intradia(t, "5d", "5m") for t in tickers}
    lineas = []
    for nombre, lst in activas.items():
        for a in alertas.cruces_en_ventana(lst, intradia, desde, hasta):
            lineas.append(f"• {(nombre + ': ') if len(lista) > 1 else ''}{alertas.texto(a, a['precio_ahora'])}")
    print(f"Ventana {desde:%d/%m %H:%M}-{hasta:%H:%M}: {sum(map(len, activas.values()))} avisos, "
          f"{len(lineas)} cruzados.")
    if lineas:
        texto = "🔔 Aviso de precio\n" + "\n".join(lineas)
        texto += "\n\nDecide con calma. Herramienta educativa, no es asesoramiento financiero."
        ok = avisos.enviar_telegram(os.environ["TELEGRAM_TOKEN"], os.environ["TELEGRAM_CHAT_ID"], texto)
        print("Telegram enviado" if ok else "Fallo al enviar a Telegram")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
