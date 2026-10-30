"""Datos que cambian poco (empresa, analistas, dividendos), guardados valor a valor en memoria y en disco.

Así lo descargado para una página sirve para las demás aunque pidan listas distintas, y tras un reinicio de la
app (Streamlit Cloud la duerme a ratos) se enseña al momento lo guardado: si ya es viejo, se renueva por detrás
y la siguiente visita trae lo nuevo. Solo se espera a la descarga cuando de un valor no hay nada.
"""

from __future__ import annotations

import logging
import pickle
import threading
import time
from pathlib import Path
from typing import Callable

log = logging.getLogger(__name__)


class Guardados:
    def __init__(self, nombre: str, segundos: float, descargar: Callable[[list[str]], dict],
                 vale: Callable[[object], bool] = bool, segundos_vacio: float = 600,
                 carpeta: Callable[[], Path] | None = None):
        """`descargar(tickers)` -> {ticker: dato}. Lo que falte o no `vale` (un fallo de Yahoo) se vuelve a pedir a
        los `segundos_vacio`; lo bueno vale `segundos` y, pasado ese tiempo, se sigue enseñando mientras se renueva."""
        self.nombre, self.segundos, self.segundos_vacio = nombre, segundos, segundos_vacio
        self._descargar, self._vale, self._carpeta = descargar, vale, carpeta
        self.datos: dict[str, tuple[float, object]] = {}
        self._cerrojo = threading.Lock()
        self._leido = carpeta is None
        self._renovando: set[str] = set()
        self._escribiendo = False
        self._sucio = False

    # --- disco -------------------------------------------------------------------------------------------------
    def _ruta(self) -> Path:
        return Path(self._carpeta()) / f"guardados_{self.nombre}.pkl"

    def _leer_disco(self) -> None:          # (con el cerrojo cogido)
        self._leido = True
        try:
            with open(self._ruta(), "rb") as f:
                guardado = pickle.load(f)
            for t, (cuando, v) in guardado.items():
                if t not in self.datos:
                    self.datos[t] = (cuando, v)
        except FileNotFoundError:
            pass
        except Exception as e:  # noqa: BLE001 - archivo roto o de otra versión: se empieza de cero
            log.warning("No se pudo leer %s: %s", self.nombre, e)

    def _guardar_disco(self) -> None:
        if self._carpeta is None:
            return
        with self._cerrojo:
            self._sucio = True
            if self._escribiendo:
                return
            self._escribiendo = True
        threading.Thread(target=self._escribir, daemon=True).start()

    def _escribir(self) -> None:
        while True:
            with self._cerrojo:
                if not self._sucio:
                    self._escribiendo = False
                    return
                self._sucio = False
                copia = {t: x for t, x in self.datos.items() if self._vale(x[1])}
            try:
                ruta = self._ruta()
                ruta.parent.mkdir(parents=True, exist_ok=True)
                temporal = ruta.with_suffix(".tmp")
                with open(temporal, "wb") as f:
                    pickle.dump(copia, f)
                temporal.replace(ruta)
            except Exception as e:  # noqa: BLE001 - sin disco se sigue con lo de memoria
                log.warning("No se pudo guardar %s: %s", self.nombre, e)

    # --- uso ---------------------------------------------------------------------------------------------------
    def _bajar_y_guardar(self, tickers: list[str]) -> None:
        nuevos = self._descargar(tickers) or {}
        ahora = time.time()
        with self._cerrojo:
            for t in tickers:
                v = nuevos.get(t)
                if self._vale(v) or t not in self.datos or not self._vale(self.datos[t][1]):
                    self.datos[t] = (ahora, v)      # un fallo de Yahoo no borra lo bueno que ya había
                else:
                    self.datos[t] = (ahora - self.segundos + self.segundos_vacio, self.datos[t][1])
        self._guardar_disco()

    def _renovar(self, tickers: list[str]) -> None:
        try:
            self._bajar_y_guardar(tickers)
        except BaseException as e:  # noqa: BLE001
            log.warning("No se pudo renovar %s: %s", self.nombre, e)
        finally:
            with self._cerrojo:
                self._renovando.difference_update(tickers)

    def varios(self, tickers) -> dict:
        tickers = list(dict.fromkeys(tickers))
        ahora = time.time()
        faltan, viejos = [], []
        with self._cerrojo:
            if not self._leido:
                self._leer_disco()
            for t in tickers:
                if t not in self.datos:
                    faltan.append(t)
                    continue
                cuando, v = self.datos[t]
                if not self._vale(v):
                    if ahora - cuando > self.segundos_vacio:
                        faltan.append(t)
                elif ahora - cuando > self.segundos and t not in self._renovando:
                    viejos.append(t)
            self._renovando.update(viejos)
        if viejos:
            threading.Thread(target=self._renovar, args=(viejos,), daemon=True).start()
        if faltan:
            self._bajar_y_guardar(faltan)
        with self._cerrojo:
            return {t: self.datos[t][1] for t in tickers if t in self.datos and self._vale(self.datos[t][1])}

    def olvidar(self) -> None:
        """Lo siguiente se descarga de nuevo (ni la memoria ni el disco se usan)."""
        with self._cerrojo:
            self.datos.clear()
            self._leido = True
