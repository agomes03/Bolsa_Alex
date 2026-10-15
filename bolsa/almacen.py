"""Dónde se guardan tus carteras y la estrategia entrenada.

- Por defecto, en un archivo de tu ordenador: `datos_usuario/datos.json`.
- Si publicas la app en Streamlit Cloud (para usarla en el móvil), sus archivos se borran cuando la app
  se reinicia. Para no perder nada, configura un "Gist" privado de GitHub (ver README): la app guardará
  allí los datos automáticamente.
- Además, siempre puedes descargar una copia de seguridad y volver a cargarla.
"""

from __future__ import annotations

import json
from pathlib import Path

NOMBRE_GIST = "bolsa_alex_datos.json"


class Almacen:
    def __init__(self, ruta: str | Path = "datos_usuario/datos.json", gist_token: str | None = None,
                 gist_id: str | None = None):
        self.ruta = Path(ruta)
        self.gist_token, self.gist_id = gist_token, gist_id

    @property
    def en_la_nube(self) -> bool:
        return bool(self.gist_token and self.gist_id)

    @property
    def descripcion(self) -> str:
        return "Gist privado de GitHub (nube)" if self.en_la_nube else f"archivo local ({self.ruta})"

    def _cabeceras(self) -> dict:
        return {"Authorization": f"Bearer {self.gist_token}", "Accept": "application/vnd.github+json"}

    def cargar(self) -> dict:
        if self.en_la_nube:
            import requests

            r = requests.get(f"https://api.github.com/gists/{self.gist_id}", headers=self._cabeceras(), timeout=15)
            r.raise_for_status()
            fichero = r.json().get("files", {}).get(NOMBRE_GIST)
            if not fichero:
                return {}
            contenido = fichero.get("content", "")
            if fichero.get("truncated"):
                contenido = requests.get(fichero["raw_url"], headers=self._cabeceras(), timeout=15).text
            return json.loads(contenido or "{}")
        if self.ruta.exists():
            return json.loads(self.ruta.read_text(encoding="utf-8") or "{}")
        return {}

    def guardar(self, datos: dict) -> None:
        texto = json.dumps(datos, ensure_ascii=False, indent=1, default=str)
        if self.en_la_nube:
            import requests

            r = requests.patch(f"https://api.github.com/gists/{self.gist_id}", headers=self._cabeceras(),
                               json={"files": {NOMBRE_GIST: {"content": texto}}}, timeout=15)
            r.raise_for_status()
            return
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self.ruta.write_text(texto, encoding="utf-8")


def desde_secrets(secrets) -> Almacen:
    """Crea el almacén según `.streamlit/secrets.toml` ([gist] token = "...", id = "...")."""
    try:
        gist = secrets.get("gist", {}) if secrets else {}
    except Exception:  # noqa: BLE001 - sin secrets.toml, Streamlit lanza excepción
        gist = {}
    return Almacen(gist_token=gist.get("token"), gist_id=gist.get("id"))
