"""Varias cuentas: la misma empresa a precios distintos en dos cuentas, y la vista «Todas»."""

import pandas as pd
import pytest

from bolsa import cartera, costes, cuentas, renta


def _dos_cuentas():
    d = {"cartera_real": cartera.nueva(None)}
    cartera.comprar(d["cartera_real"], "SAN.MC", 1000, 10.0, costes.Tarifa(), "2025-01-10")
    cuentas.asegurar(d)
    assert cuentas.nueva_cuenta(d, "Bankinter 2") is None
    b2 = d["cuentas"]["Bankinter 2"]
    cartera.comprar(b2, "SAN.MC", 500, 13.0, costes.Tarifa(), "2025-06-10", stop=11.0)
    cartera.comprar(b2, "ITX.MC", 10, 50.0, costes.Tarifa(), "2025-06-10")
    cuentas.consolidar(d)
    return d


def test_los_datos_antiguos_pasan_a_una_cuenta():
    d = {"cartera_real": cartera.nueva(None)}
    cartera.comprar(d["cartera_real"], "SAN.MC", 100, 10.0, costes.Tarifa(), "2025-01-10")
    cuentas.asegurar(d)
    assert list(d["cuentas"]) == [cuentas.PRINCIPAL]
    assert d["cartera_real"]["posiciones"]["SAN.MC"]["acciones"] == 100
    vacio = {}
    assert list(cuentas.asegurar(vacio)) == [cuentas.PRINCIPAL] and vacio["cartera_real"]["posiciones"] == {}


def test_todas_suma_y_pondera_el_precio_medio():
    d = _dos_cuentas()
    san = d["cartera_real"]["posiciones"]["SAN.MC"]
    assert san["acciones"] == 1500
    assert san["precio_medio"] == pytest.approx((1000 * 10 + 500 * 13) / 1500)
    assert san["cuentas"] == [cuentas.PRINCIPAL, "Bankinter 2"]
    assert san["stop"] is None                      # la cuenta principal no tiene stop
    assert d["cartera_real"]["posiciones"]["ITX.MC"]["acciones"] == 10
    assert [x["cuenta"] for x in cuentas.desglose(d, "SAN.MC")] == [cuentas.PRINCIPAL, "Bankinter 2"]
    assert [x["precio_medio"] for x in cuentas.desglose(d, "SAN.MC")] == [10.0, 13.0]


def test_vender_en_una_cuenta_usa_su_precio_medio():
    d = _dos_cuentas()
    cartera.vender(d["cuentas"]["Bankinter 2"], "SAN.MC", 500, 14.0, costes.Tarifa(), "2026-03-01")
    cuentas.consolidar(d)
    assert d["cartera_real"]["posiciones"]["SAN.MC"]["acciones"] == 1000
    v = renta.ventas_del_ano(d["cartera_real"]["historial"], 2026)
    # Ganancia con el precio de ESA cuenta (13 €), no con la media de todas (11 €): 500 × 1 € menos comisiones.
    assert len(v) == 1 and 400 < v[0]["resultado"] < 500
    assert renta.acciones_en(d["cartera_real"]["historial"], "SAN.MC", pd.Timestamp("2025-12-01")) \
        == 1500


def test_vigilancia_y_stop_en_todas():
    d = _dos_cuentas()
    d["cuentas"][cuentas.PRINCIPAL]["posiciones"]["SAN.MC"]["stop"] = 9.0
    d["cuentas"]["Bankinter 2"]["posiciones"]["ITX.MC"].update(sin_stop=True, alarma=45.0)
    cuentas.consolidar(d)
    assert d["cartera_real"]["posiciones"]["SAN.MC"]["stop"] == 11.0     # ambas con stop: el más alto
    itx = d["cartera_real"]["posiciones"]["ITX.MC"]
    assert itx["sin_stop"] and itx["alarma"] == 45.0


def test_crear_renombrar_y_borrar_cuentas():
    d = _dos_cuentas()
    assert "Ya hay" in cuentas.nueva_cuenta(d, "Bankinter 2")
    assert cuentas.nueva_cuenta(d, " ") is not None
    assert cuentas.renombrar(d, "Bankinter 2", "Cuenta de ahorro") is None
    assert list(d["cuentas"]) == [cuentas.PRINCIPAL, "Cuenta de ahorro"]
    assert d["cartera_real"]["posiciones"]["SAN.MC"]["cuentas"] == [cuentas.PRINCIPAL, "Cuenta de ahorro"]
    assert cuentas.borrar(d, "Cuenta de ahorro") is None
    assert d["cartera_real"]["posiciones"]["SAN.MC"]["acciones"] == 1000
    assert "al menos una" in cuentas.borrar(d, cuentas.PRINCIPAL)
