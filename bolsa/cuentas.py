"""Cuentas independientes: la tuya, la de tu madre, la de tu hermano...

Cada cuenta es como una persona distinta: sus posiciones, su perfil de inversor, sus ahorros, sus avisos, su diario,
su aportación mensual y su bróker. La app asesora a la cuenta activa (se elige en la barra lateral) y NUNCA suma
cuentas entre sí.

Para que el resto de la app no tenga que saber nada de cuentas, `d["cartera_real"]` es siempre la cuenta activa
(el mismo diccionario, no una copia). Al guardar se quita ese atajo: lo que vale es `d["cuentas"]`.
"""

from __future__ import annotations

import copy

PRINCIPAL = "Mi cuenta"
# Lo que es de cada persona (antes se guardaba una sola vez para toda la app).
CLAVES_CUENTA = ("perfil_inversor", "otros_ahorros", "ganancias_ano", "perdidas_anteriores", "aportacion", "alertas",
                 "diario", "broker", "tarifas")


def _vacia() -> dict:
    from .cartera import nueva

    return nueva(None)


def asegurar(d: dict) -> dict[str, dict]:
    """Pasa datos antiguos al formato de cuentas y apunta `cartera_real` a la cuenta activa. Devuelve las cuentas."""
    if not d.get("cuentas"):
        base = copy.deepcopy(d["cartera_real"]) if d.get("cartera_real") else _vacia()
        base.pop("cuentas", None)
        d["cuentas"] = {PRINCIPAL: base}
    primera = next(iter(d["cuentas"].values()))
    for clave in CLAVES_CUENTA:          # lo que había para toda la app pasa a la primera cuenta
        if clave in d:
            valor = d.pop(clave)
            primera.setdefault(clave, valor)
    if d.get("cuenta_activa") not in d["cuentas"]:
        d["cuenta_activa"] = next(iter(d["cuentas"]))
    d["cartera_real"] = d["cuentas"][d["cuenta_activa"]]
    return d["cuentas"]


def activa(d: dict) -> dict:
    asegurar(d)
    return d["cartera_real"]


def activar(d: dict, nombre: str) -> None:
    if nombre in asegurar(d):
        d["cuenta_activa"] = nombre
        d["cartera_real"] = d["cuentas"][nombre]


def para_guardar(d: dict) -> dict:
    """Los datos sin el atajo `cartera_real` (que se rehace al cargar)."""
    return {k: v for k, v in d.items() if k != "cartera_real"}


def combinar(nuestros: dict, remotos: dict, cambiadas, conocidas=None) -> dict:
    """Si otro dispositivo ha guardado mientras tanto, se juntan los dos:
    - las cuentas que has tocado en esta sesión (`cambiadas`) y lo general de la app: lo tuyo;
    - las demás cuentas: lo guardado por el otro (si tu madre apunta algo en su móvil, no se pierde);
    - una cuenta que solo está en el otro lado: si ya la conocías (`conocidas`, las cuentas al abrir la app), es que
      la has borrado o renombrado y no vuelve; si no, la ha creado el otro dispositivo y se añade."""
    cambiadas = {cambiadas} if isinstance(cambiadas, str) else set(cambiadas or ())
    salida = copy.deepcopy(para_guardar(nuestros))
    remotos = copy.deepcopy(remotos or {})
    if not remotos.get("cuentas"):
        return salida
    asegurar(remotos)
    mias = salida.setdefault("cuentas", {})
    for nombre, c in remotos["cuentas"].items():
        if nombre in mias:
            if nombre not in cambiadas:
                mias[nombre] = c
        elif conocidas is None or nombre not in conocidas:
            mias[nombre] = c
    return salida


def nueva_cuenta(d: dict, nombre: str) -> str | None:
    nombre = nombre.strip()
    cuentas = asegurar(d)
    if not nombre:
        return "Ponle un nombre a la cuenta (por ejemplo, «Mamá» o «Hermano»)."
    if nombre in cuentas:
        return f"Ya hay una cuenta llamada «{nombre}»."
    cuentas[nombre] = _vacia()
    return None


def renombrar(d: dict, viejo: str, nuevo: str) -> str | None:
    nuevo = nuevo.strip()
    cuentas = asegurar(d)
    if viejo not in cuentas:
        return "Esa cuenta no existe."
    if not nuevo or (nuevo in cuentas and nuevo != viejo):
        return "Elige otro nombre."
    d["cuentas"] = {(nuevo if n == viejo else n): c for n, c in cuentas.items()}
    if d.get("cuenta_activa") == viejo:
        d["cuenta_activa"] = nuevo
    asegurar(d)
    return None


def borrar(d: dict, nombre: str) -> str | None:
    cuentas = asegurar(d)
    if nombre not in cuentas:
        return "Esa cuenta no existe."
    if len(cuentas) == 1:
        return "Necesitas al menos una cuenta."
    del cuentas[nombre]
    asegurar(d)
    return None


__all__ = ["PRINCIPAL", "CLAVES_CUENTA", "asegurar", "activa", "activar", "para_guardar", "nueva_cuenta",
           "renombrar", "borrar"]
