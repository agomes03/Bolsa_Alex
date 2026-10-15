"""Ejecuta el laboratorio de experimentos con datos reales y guarda `informe/experimentos.json`.

    python scripts/experimentos.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from bolsa import datos, experimentos, informe  # noqa: E402
from bolsa.tickers import INDICES, TERMOMETROS, TODAS_LAS_ACCIONES  # noqa: E402


def main() -> int:
    inicio = time.time()

    def log(msg: str):
        print(f"[{time.time() - inicio:6.0f}s] {msg}", flush=True)

    acciones = informe.frescos(informe.descargar_por_bloques(list(TODAS_LAS_ACCIONES), "10y", log=log))
    indices = informe.descargar_por_bloques(list(INDICES) + list(TERMOMETROS), "10y", log=log)
    largos = {t: datos.historico(t, "max") for t in informe.INDICES_LARGOS}
    log(f"{len(acciones)} acciones, {len(indices)} índices")
    res = experimentos.ejecutar(acciones, indices, largos, log=log)
    res["fecha"] = time.strftime("%Y-%m-%d")
    salida = RAIZ / "informe" / "experimentos.json"
    salida.write_text(json.dumps(informe.limpiar(res), ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"Guardado {salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
