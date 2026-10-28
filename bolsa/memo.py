"""Recordar cálculos pesados (indicadores, evaluaciones, gráficos) mientras sus datos no cambien.

Cada refresco de la app vuelve a pedir lo mismo con los mismos datos: en vez de recalcularlo, se reutiliza. La
«huella» de un histórico (tamaño, primera y última fecha, último cierre y suma de cierres) cambia en cuanto llega
un precio nuevo, así que nunca se enseña nada viejo.
"""

from __future__ import annotations

import copy
import threading
from collections import OrderedDict
from functools import wraps

import pandas as pd


def huella(x):
    """Algo pequeño y comparable que cambia si cambian los datos."""
    if isinstance(x, pd.DataFrame):
        if x.empty:
            return ("df", 0)
        cierre = x["Close"] if "Close" in x else x.iloc[:, 0]
        return ("df", x.shape, str(x.index[0]), str(x.index[-1]), float(cierre.iloc[-1]),
                float(cierre.sum()), tuple(x.columns))
    if isinstance(x, pd.Series):
        return ("s", len(x), str(x.index[0]) if len(x) else None, float(x.sum()) if len(x) else 0.0)
    if isinstance(x, dict):
        return tuple(sorted((str(k), huella(v)) for k, v in x.items()))
    if isinstance(x, (list, tuple)):
        return tuple(huella(v) for v in x)
    if x is None or isinstance(x, (str, int, float, bool)):
        return x
    return repr(x)


def memorizar(maximo: int = 64, copiar: bool = True):
    """Decorador: guarda los últimos `maximo` resultados. Devuelve una copia (quien llama puede modificarla)."""
    def decorador(funcion):
        guardados: OrderedDict = OrderedDict()
        cerrojo = threading.Lock()

        @wraps(funcion)
        def envoltura(*args, **kwargs):
            try:
                clave = (huella(args), huella(kwargs))
                hash(clave)
            except Exception:  # noqa: BLE001 - algo raro en los argumentos: se calcula sin recordar
                return funcion(*args, **kwargs)
            with cerrojo:
                if clave in guardados:
                    guardados.move_to_end(clave)
                    valor = guardados[clave]
                    return _copia(valor) if copiar else valor
            valor = funcion(*args, **kwargs)
            with cerrojo:
                guardados[clave] = valor
                while len(guardados) > maximo:
                    guardados.popitem(last=False)
            return _copia(valor) if copiar else valor

        envoltura.olvidar = guardados.clear
        return envoltura
    return decorador


def _copia(valor):
    if isinstance(valor, (pd.DataFrame, pd.Series)):
        return valor.copy()
    return copy.deepcopy(valor)
