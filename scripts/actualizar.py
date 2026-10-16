"""Actualización diaria: descarga datos, reentrena modelos y genera `informe/informe.json`.

Uso:
    python scripts/actualizar.py                 # entrena la estrategia solo si toca (1 vez por semana)
    python scripts/actualizar.py --entrenar      # fuerza el reentrenamiento de la estrategia
    python scripts/actualizar.py --iteraciones 150

Se ejecuta solo cada día laborable en GitHub Actions (.github/workflows/actualizar.yml).
Variables de entorno opcionales: TELEGRAM_TOKEN, TELEGRAM_CHAT_ID (avisos al móvil) y
GIST_TOKEN, GIST_ID (para leer tu cartera de Bankinter guardada desde la app y avisarte).
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from bolsa import agenda, almacen, avisos, cuentas, informe  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--entrenar", action="store_true", help="reentrenar la estrategia aunque no toque")
    ap.add_argument("--iteraciones", type=int, default=80, help="combinaciones de reglas a probar")
    ap.add_argument("--sin-noticias", action="store_true")
    ap.add_argument("--carpeta", default=str(RAIZ / "informe"))
    args = ap.parse_args()

    inicio = time.time()

    def log(msg: str):
        print(f"[{time.time() - inicio:6.0f}s] {msg}", flush=True)

    inf = informe.actualizar(args.carpeta, entrenar=True if args.entrenar else None,
                             iteraciones=args.iteraciones, con_noticias=not args.sin_noticias, log=log)

    token, chat = os.environ.get("TELEGRAM_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if token and chat:
        propios, semana, pendientes = [], "", ""
        if os.environ.get("GIST_TOKEN") and os.environ.get("GIST_ID"):
            try:
                datos = almacen.Almacen(gist_token=os.environ["GIST_TOKEN"], gist_id=os.environ["GIST_ID"]).cargar()
                umbral = inf["estrategia"]["parametros"].get("umbral_venta", 40)
                lista = cuentas.asegurar(datos)                  # cada cuenta (tuya, de tu madre...) por separado
                varias = len(lista) > 1
                viernes = datetime.now(timezone.utc).weekday() == 4       # viernes: resumen de la semana
                bloques_pend, bloques_semana = [], []
                for nombre, cuenta in lista.items():
                    titulo = [f"👤 {nombre}:"] if varias else []
                    av = avisos.avisos_cartera(cuenta, inf["ranking"], umbral)
                    if av:
                        propios += titulo + av
                    pend = agenda.texto_telegram(cuenta)
                    if pend:
                        bloques_pend.append((f"👤 {nombre} · " if varias else "") + pend)
                    if viernes:
                        sem = avisos.mensaje_semanal(cuenta, inf.get("noticias", {}).get("top"))
                        if sem:
                            bloques_semana.append((f"👤 {nombre} · " if varias else "") + sem)
                pendientes, semana = "\n\n".join(bloques_pend), "\n\n".join(bloques_semana)
            except Exception as e:  # noqa: BLE001
                log(f"No se pudo leer la cartera del Gist: {e}")
        mensaje = avisos.mensaje_diario(inf, propios) + (f"\n\n{pendientes}" if pendientes else "") + (
            f"\n\n{semana}" if semana else "")
        ok = avisos.enviar_telegram(token, chat, mensaje)
        log("Aviso de Telegram enviado" if ok else "Fallo al enviar el aviso de Telegram")
    log("Terminado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
