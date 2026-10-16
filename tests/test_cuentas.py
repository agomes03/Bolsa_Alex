"""Cuentas independientes (tú, tu madre, tu hermano): nada se suma entre cuentas."""

import json

from bolsa import cartera, costes, cuentas


def _familia():
    d = {}
    cuentas.asegurar(d)
    cartera.comprar(d["cartera_real"], "SAN.MC", 1000, 10.0, costes.Tarifa(), "2025-01-10")
    assert cuentas.nueva_cuenta(d, "Mamá") is None
    cartera.comprar(d["cuentas"]["Mamá"], "SAN.MC", 500, 13.0, costes.Tarifa(), "2025-06-10")
    return d


def test_los_datos_antiguos_pasan_a_la_primera_cuenta_con_sus_ajustes():
    d = {"cartera_real": cartera.nueva(None), "perfil_inversor": {"importe": 1}, "otros_ahorros": 5000.0,
         "alertas": [{"id": 1}], "estrategia": {"x": 1}}
    cartera.comprar(d["cartera_real"], "SAN.MC", 100, 10.0, costes.Tarifa(), "2025-01-10")
    cuentas.asegurar(d)
    mia = d["cuentas"][cuentas.PRINCIPAL]
    assert mia["posiciones"]["SAN.MC"]["acciones"] == 100
    assert mia["perfil_inversor"] == {"importe": 1} and mia["otros_ahorros"] == 5000.0 and mia["alertas"]
    assert "perfil_inversor" not in d and "otros_ahorros" not in d
    assert d["estrategia"] == {"x": 1}                      # lo que es de toda la app se queda donde estaba
    assert d["cartera_real"] is mia                           # el atajo es la misma cuenta, no una copia


def test_cada_cuenta_va_por_separado():
    d = _familia()
    assert d["cartera_real"]["posiciones"]["SAN.MC"]["acciones"] == 1000       # la activa: la mía, sin sumar
    cuentas.activar(d, "Mamá")
    assert d["cartera_real"]["posiciones"]["SAN.MC"]["acciones"] == 500
    assert d["cartera_real"]["posiciones"]["SAN.MC"]["precio_medio"] == 13.0
    # Lo que se cambia en la activa queda en esa cuenta.
    d["cartera_real"]["otros_ahorros"] = 20_000.0
    assert d["cuentas"]["Mamá"]["otros_ahorros"] == 20_000.0
    assert "otros_ahorros" not in d["cuentas"][cuentas.PRINCIPAL]


def test_guardar_y_cargar_mantiene_la_cuenta_activa():
    d = _familia()
    cuentas.activar(d, "Mamá")
    guardado = json.loads(json.dumps(cuentas.para_guardar(d)))
    assert "cartera_real" not in guardado
    cuentas.asegurar(guardado)
    assert guardado["cuenta_activa"] == "Mamá"
    assert guardado["cartera_real"] is guardado["cuentas"]["Mamá"]


def test_crear_renombrar_y_borrar():
    d = _familia()
    assert "Ya hay" in cuentas.nueva_cuenta(d, "Mamá")
    assert cuentas.nueva_cuenta(d, " ") is not None
    cuentas.activar(d, "Mamá")
    assert cuentas.renombrar(d, "Mamá", "Mi madre") is None
    assert d["cuenta_activa"] == "Mi madre" and d["cartera_real"] is d["cuentas"]["Mi madre"]
    assert cuentas.borrar(d, "Mi madre") is None
    assert d["cuenta_activa"] == cuentas.PRINCIPAL and d["cartera_real"]["posiciones"]["SAN.MC"]["acciones"] == 1000
    assert "al menos una" in cuentas.borrar(d, cuentas.PRINCIPAL)
