from datetime import datetime, timezone

import pandas as pd
import pytest

from bolsa import cartera, datos, ejercicios, horario
from bolsa.costes import Tarifa

T = Tarifa()


def velas(filas, inicio="2026-10-15 09:00", freq="5min"):
    idx = pd.date_range(inicio, periods=len(filas), freq=freq)
    return pd.DataFrame(filas, columns=["Open", "High", "Low", "Close"], index=idx).assign(Volume=1000)


def test_horario_bolsa_espanola_y_eeuu():
    miercoles_12h = datetime(2026, 10, 14, 10, 0, tzinfo=timezone.utc)      # 12:00 en Madrid
    assert horario.estado_mercado("SAN.MC", miercoles_12h)["abierto"]
    assert not horario.estado_mercado("AAPL", miercoles_12h)["abierto"]    # Wall Street abre a las 15:30
    assert "15:30" in horario.estado_mercado("AAPL", miercoles_12h)["texto"]
    sabado = datetime(2026, 10, 17, 10, 0, tzinfo=timezone.utc)
    e = horario.estado_mercado("SAN.MC", sabado)
    assert not e["abierto"] and "lunes" in e["texto"] and "09:00" in e["texto"]


def test_limitada_de_compra_espera_al_precio_y_mejora_si_abre_por_debajo():
    c = cartera.nueva(10_000)
    assert cartera.nueva_orden(c, "SAN.MC", "compra", "limitada", 100, T, precio_ref=10.2, limite=10.0,
                               ahora="2026-10-15T09:00", validez="2026-10-20", stop=9.5) is None
    assert cartera.disponible(c, T) < 10_000 - 1000          # el dinero queda reservado
    barras = {"SAN.MC": velas([(10.2, 10.3, 10.1, 10.2), (10.1, 10.15, 10.05, 10.1)])}
    assert cartera.ejecutar_ordenes(c, barras, T, "2026-10-15T09:10") == []
    assert len(c["ordenes"]) == 1 and not c["posiciones"]
    barras = {"SAN.MC": velas([(10.2, 10.3, 10.1, 10.2), (9.9, 10.0, 9.8, 9.95)])}   # abre por debajo del límite
    ev = cartera.ejecutar_ordenes(c, barras, T, "2026-10-15T09:10")
    assert len(ev) == 1 and c["posiciones"]["SAN.MC"]["precio_medio"] == pytest.approx(9.9)
    assert c["posiciones"]["SAN.MC"]["stop"] == 9.5 and c["ordenes"] == []
    assert c["historial"][-1]["orden"] == "limitada"


def test_solo_cuentan_las_velas_posteriores_a_la_orden():
    c = cartera.nueva(10_000)
    cartera.nueva_orden(c, "SAN.MC", "compra", "limitada", 10, T, precio_ref=10.2, limite=10.0,
                        ahora="2026-10-15T09:30", validez="2026-10-15")
    barras = {"SAN.MC": velas([(9.9, 9.9, 9.8, 9.9), (10.2, 10.3, 10.1, 10.2)])}   # 9:00 y 9:05: antes de la orden
    assert cartera.ejecutar_ordenes(c, barras, T, "2026-10-15T09:35") == []


def test_mercado_cerrado_se_ejecuta_en_la_apertura_y_abierto_al_precio_actual():
    c = cartera.nueva(10_000)
    cartera.nueva_orden(c, "ITX.MC", "compra", "mercado", 10, T, precio_ref=50, ahora="2026-10-14T20:00",
                        validez="2026-10-15")
    cartera.ejecutar_ordenes(c, {"ITX.MC": velas([(51, 52, 50.5, 51.5)])}, T, "2026-10-15T09:10")
    assert c["posiciones"]["ITX.MC"]["precio_medio"] == 51
    cartera.nueva_orden(c, "ITX.MC", "venta", "mercado", 10, T, precio_ref=51.5, ahora="2026-10-15T12:00",
                        validez="2026-10-15")
    cartera.ejecutar_ordenes(c, {}, T, "2026-10-15T12:00", {"ITX.MC": (51.7, True)})
    assert "ITX.MC" not in c["posiciones"] and c["historial"][-1]["precio"] == 51.7


def test_stop_con_limite_como_en_bankinter():
    c = cartera.nueva(10_000)
    cartera.comprar(c, "SAN.MC", 100, 10.0, T, "2026-10-14")
    assert cartera.nueva_orden(c, "SAN.MC", "venta", "stop", 100, T, precio_ref=10, activacion=9.0, limite=8.9,
                               ahora="2026-10-14T18:00", validez="2026-10-30") is None
    assert cartera.acciones_libres(c, "SAN.MC") == 0
    # Hueco a la baja por debajo del límite: se activa pero queda como limitada a 8,90
    ev = cartera.ejecutar_ordenes(c, {"SAN.MC": velas([(8.5, 8.6, 8.4, 8.5)])}, T, "2026-10-15T09:05")
    assert "queda como orden limitada" in ev[0] and c["ordenes"][0]["tipo"] == "limitada"
    ev = cartera.ejecutar_ordenes(c, {"SAN.MC": velas([(8.5, 8.6, 8.4, 8.5), (8.7, 8.95, 8.7, 8.9)])}, T,
                                  "2026-10-15T09:10")
    assert "SAN.MC" not in c["posiciones"] and c["historial"][-1]["precio"] == pytest.approx(8.9)


def test_validaciones_y_caducidad():
    c = cartera.nueva(1_000)
    assert "dinero" in cartera.nueva_orden(c, "SAN.MC", "compra", "limitada", 1000, T, precio_ref=10, limite=10,
                                           ahora="2026-10-15T10:00", validez="2026-10-15")
    assert "vender" in cartera.nueva_orden(c, "SAN.MC", "venta", "limitada", 5, T, precio_ref=10, limite=10,
                                           ahora="2026-10-15T10:00", validez="2026-10-15")
    assert "límite" in cartera.nueva_orden(c, "SAN.MC", "compra", "limitada", 5, T, precio_ref=10,
                                           ahora="2026-10-15T10:00", validez="2026-10-15")
    cartera.nueva_orden(c, "SAN.MC", "compra", "limitada", 5, T, precio_ref=10, limite=5,
                        ahora="2026-10-15T10:00", validez="2026-10-15")
    ev = cartera.ejecutar_ordenes(c, {}, T, "2026-10-16T09:00")
    assert "caducado" in ev[0] and c["ordenes"] == [] and c["historial"][-1]["tipo"] == "Orden caducada"
    assert cartera.disponible(c, T) == pytest.approx(1_000)


def test_cancelar_libera_el_dinero_y_cuenta_como_ejercicio():
    c = cartera.nueva(10_000)
    cartera.nueva_orden(c, "SAN.MC", "compra", "limitada", 100, T, precio_ref=10, limite=8,
                        ahora="2026-10-15T10:00", validez="2026-10-20")
    assert cartera.cancelar_orden(c, c["ordenes"][0]["id"])
    assert cartera.disponible(c, T) == pytest.approx(10_000)
    hechos = dict((e.titulo, h) for e, h in ejercicios.progreso(c))
    assert hechos["Cancela una orden que ya no quieres"]
    assert not hechos["Compra con una orden limitada"]


def test_evolucion_rehace_la_cartera_dia_a_dia():
    c = cartera.nueva(10_000)
    c["creada"] = "2026-10-12"
    cartera.comprar(c, "SAN.MC", 100, 10.0, Tarifa(broker_cero=True, canon_nacional=0), "2026-10-13T10:00")
    cierres = {"SAN.MC": pd.Series([10.0, 11.0, 12.0], index=pd.to_datetime(["2026-10-13", "2026-10-14",
                                                                              "2026-10-15"]))}
    e = cartera.evolucion(c, cierres, hasta="2026-10-15")
    gastos = c["historial"][0]["gastos"]   # tasa Tobin
    assert e.iloc[0] == pytest.approx(10_000)
    assert e.loc["2026-10-15"] == pytest.approx(10_000 - 1000 - gastos + 1200)


def test_cotizacion_y_velas_de_ejecucion():
    diario = pd.DataFrame({"Open": [9, 10], "High": [10, 11], "Low": [8, 9], "Close": [9.5, 10], "Volume": [1, 1]},
                          index=pd.to_datetime(["2026-10-13", "2026-10-14"]))
    intra = velas([(10.1, 10.4, 10.0, 10.3), (10.3, 10.5, 10.2, 10.4)])
    q = datos.cotizacion(diario, intra)
    assert q["precio"] == 10.4 and q["anterior"] == 10 and q["variacion_pct"] == pytest.approx(4.0)
    assert q["apertura"] == 10.1 and q["maximo"] == 10.5 and q["minimo"] == 10.0
    b = datos.barras_ejecucion(diario, intra)
    assert len(b) == 4 and b.index.is_monotonic_increasing
