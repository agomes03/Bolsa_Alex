"""Abre la app como lo haría el navegador del móvil, para que esté despierta y con los datos ya descargados cuando
la abras tú. Streamlit Cloud duerme las apps que nadie usa durante horas (despertarlas tarda medio minuto o más).

Uso: APP_URL=https://tu-app.streamlit.app python scripts/despertar.py

No necesita la contraseña de la app: con solo abrir la pantalla de la contraseña, la app empieza a descargar en
segundo plano lo que necesitará Hoy.
"""

from __future__ import annotations

import os
import sys
import time

TEXTOS_APP = ("Asistente de Bolsa", "Contraseña", "Hoy", "Mi cartera")
BOTON_DESPERTAR = "get this app back up"      # el botón de Streamlit Cloud cuando la app está dormida


def _texto(pagina) -> str:
    partes = []
    for marco in pagina.frames:
        try:
            partes.append(marco.inner_text("body", timeout=2000))
        except Exception:  # noqa: BLE001 - un marco que aún no ha cargado
            pass
    return "\n".join(partes)


def main() -> int:
    url = os.environ.get("APP_URL", "").strip()
    if not url:
        print("Sin APP_URL (secreto del repositorio): no hay nada que despertar.")
        return 0
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        ruta = os.environ.get("CHROMIUM_PATH")         # (opcional: un Chromium ya instalado)
        navegador = p.chromium.launch(**({"executable_path": ruta} if ruta else {}))
        pagina = navegador.new_page(viewport={"width": 412, "height": 915}, is_mobile=True, has_touch=True)
        pagina.goto(url, wait_until="domcontentloaded", timeout=120_000)
        inicio = time.time()
        while time.time() - inicio < 300:
            for marco in pagina.frames:
                boton = marco.get_by_role("button", name=BOTON_DESPERTAR)
                try:
                    if boton.count():
                        print("La app estaba dormida: despertándola...")
                        boton.first.click()
                except Exception:  # noqa: BLE001
                    pass
            if any(t in _texto(pagina) for t in TEXTOS_APP):
                print(f"App despierta en {time.time() - inicio:.0f} s. Dejando que descargue los datos...")
                pagina.wait_for_timeout(int(os.environ.get("ESPERA_MS", 60_000)))   # lo que tarda en calentar la caché
                navegador.close()
                return 0
            pagina.wait_for_timeout(5_000)
        print("La app no ha respondido en 5 minutos.")
        navegador.close()
        return 1


if __name__ == "__main__":
    sys.exit(main())
