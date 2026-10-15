import json

import numpy as np
import pandas as pd
import pytest

from bolsa import almacen, bankinter, cartera, senales, simulador
from bolsa.costes import Tarifa
from bolsa.indicadores import calcular_todo
from bolsa.simulador import Parametros, Universo
from test_bolsa import serie

TARIFA = Tarifa(pct=0.2, minimo=6, canon_fijo=1)


# ----------------------------------------------------------------- puntuación coherente con la app
@pytest.mark.parametrize("tendencia,semilla", [(0.0015, 1), (-0.0015, 2), (0.0, 3), (0.0008, 4)])
@pytest.mark.parametrize("mercado", [None, True, False])
def test_puntuacion_vectorizada_igual_que_evaluar(tendencia, semilla, mercado):
    df = serie(tendencia, n=400, semilla=semilla)
    serie_mercado = None if mercado is None else pd.Series(float(mercado), index=df.index)
    vector = simulador.puntuacion_tecnica(calcular_todo(df), serie_mercado)
    for corte in (150, 260, 400):  # sin y con media de 200
        ev = senales.evaluar("X", df.iloc[:corte], mercado_alcista=mercado)
        assert vector.iloc[corte - 1] == ev.puntuacion


# ----------------------------------------------------------------- universo sintético a mano
def universo_manual(precios: list[float], base: float = 80.0, atr: float = 2.0) -> Universo:
    n = len(precios)
    p = np.array(precios, dtype=float).reshape(-1, 1)
    return Universo(fechas=pd.bdate_range("2024-01-01", periods=n), tickers=["X.MC"],
                    O=p.copy(), H=p * 1.0, L=p * 1.0, C=p.copy(), ATR=np.full((n, 1), atr),
                    BASE=np.full((n, 1), base), PROB=np.full((n, 1), np.nan), inicio=1)


def test_stop_loss_en_hueco_bajista():
    u = universo_manual([100.0] * 10 + [80.0] * 5)
    r = simulador.simular(u, Parametros(peso_modelo=0), TARIFA, 10_000)
    op = r.operaciones.iloc[0]
    assert op["Precio compra"] == 100 and op["Precio venta"] == 80
    assert op["Motivo"].startswith("Stop-loss")
    assert op["Resultado €"] < 0


def test_objetivo_alcanzado():
    u = universo_manual([100.0] * 5 + [101, 103, 105, 109, 109])
    r = simulador.simular(u, Parametros(peso_modelo=0, stop_atr=2, ratio_objetivo=2), TARIFA, 10_000)
    op = r.operaciones.iloc[0]
    assert op["Motivo"] == "Objetivo alcanzado"
    assert op["Precio venta"] == pytest.approx(109)  # abrió por encima del objetivo (108)


def test_riesgo_por_operacion_respetado():
    u = universo_manual([100.0] * 10 + [80.0] * 5)
    p = Parametros(peso_modelo=0, riesgo_pct=1.0, max_posiciones=1)
    r = simulador.simular(u, p, TARIFA, 10_000)
    # Riesgo previsto: 1% de 10.000 = 100 €. El hueco bajista (de 100 a 80 con stop en 96) lo multiplica
    # por 5, pero el tamaño se calculó correctamente: 25 acciones (100 € / 4 € de riesgo por acción).
    assert r.operaciones.iloc[0]["Acciones"] == 25


def test_contabilidad_cuadra():
    hist = {t: serie(0.0008, n=900, semilla=i) for i, t in enumerate(["A.MC", "B.MC", "C.MC", "D"])}
    u = simulador.preparar_universo(hist, con_modelo=False)
    r = simulador.simular(u, Parametros(umbral_compra=60), TARIFA, 10_000)
    assert len(r.operaciones) > 0
    assert r.curva.iloc[-1] == pytest.approx(10_000 + r.operaciones["Resultado €"].sum(), abs=0.01)
    assert r.metricas["gastos"] > 0


def test_no_mira_el_futuro():
    """Si cambiamos los precios a partir de un día, todo lo anterior debe quedar idéntico."""
    hist = {t: serie(0.0006, n=900, semilla=i) for i, t in enumerate(["A.MC", "B.MC", "C.MC"])}
    corte = hist["A.MC"].index[700]
    alterado = {}
    for t, df in hist.items():
        d = df.copy()
        d.loc[d.index >= corte, ["Open", "High", "Low", "Close"]] *= 0.5
        alterado[t] = d
    u1 = simulador.preparar_universo(hist)
    u2 = simulador.preparar_universo(alterado)
    p = Parametros(umbral_compra=60)
    r1 = simulador.simular(u1, p, TARIFA, 10_000, liquidar=False)
    r2 = simulador.simular(u2, p, TARIFA, 10_000, liquidar=False)
    antes = r1.curva.index < corte
    pd.testing.assert_series_equal(r1.curva[antes], r2.curva[antes])
    np.testing.assert_array_equal(u1.PROB[:700], u2.PROB[:700])


def test_walk_forward():
    hist = {t: serie(0.0005, n=1500, semilla=i, ruido=0.012) for i, t in enumerate(["A.MC", "B.MC", "C.MC", "D.MC"])}
    u = simulador.preparar_universo(hist, con_modelo=False)
    wf = simulador.walk_forward(u, TARIFA, 10_000, iteraciones=8, anos_entreno=2)
    assert len(wf["tramos"]) >= 2
    assert isinstance(wf["parametros_finales"], Parametros)
    assert wf["curva_entrenada"].index.is_monotonic_increasing
    assert set(wf) >= {"metricas_entrenada", "metricas_defecto", "metricas_mantener"}


def test_parametros_roundtrip():
    p = Parametros(umbral_compra=75, ratio_objetivo=0.0)
    assert Parametros.desde_dict(json.loads(json.dumps(p.a_dict()))) == p
    assert Parametros.desde_dict({"umbral_compra": 65, "desconocido": 1}).umbral_compra == 65
    assert any("sin objetivo fijo" in linea for linea in p.describir())


# ----------------------------------------------------------------- carteras
def test_cartera_virtual_compra_venta():
    c = cartera.nueva(1_000.0)
    assert cartera.comprar(c, "SAN.MC", 100, 5.0, TARIFA) is None
    assert c["efectivo"] == pytest.approx(1_000 - 500 - 7 - 1)  # comisión 7 + ITF 1
    assert "No tienes suficiente" in cartera.comprar(c, "SAN.MC", 1000, 5.0, TARIFA)
    assert cartera.vender(c, "SAN.MC", 100, 6.0, TARIFA) is None
    venta = c["historial"][-1]
    assert venta["resultado"] == pytest.approx(600 - 7 - 500 - 8)
    assert not c["posiciones"]


def test_cartera_ejecuta_stop():
    c = cartera.nueva(10_000.0)
    cartera.comprar(c, "X", 10, 100.0, TARIFA, fecha="2024-01-01", stop=95.0, objetivo=120.0)
    df = pd.DataFrame({"Open": [100, 99, 97], "High": [101, 100, 98], "Low": [99, 96, 94],
                       "Close": [100, 97, 95], "Volume": 1}, index=pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]))
    eventos = cartera.revisar_ordenes(c, {"X": df}, TARIFA)
    assert len(eventos) == 1 and "Stop-loss" in eventos[0]
    assert c["historial"][-1]["precio"] == 95.0
    assert not c["posiciones"]


def test_cartera_real_sin_efectivo():
    c = cartera.nueva(None)
    assert cartera.comprar(c, "ITX.MC", 10, 50.0, TARIFA) is None
    tabla, res = cartera.valorar(c, {"ITX.MC": 55.0})
    assert res["efectivo"] is None
    assert tabla.iloc[0]["resultado"] == pytest.approx(10 * 55 - 10 * 50 - (7 + 1))


# ----------------------------------------------------------------- Bankinter
def test_numeros_formato_espanol():
    assert bankinter.numero("1.234,56 €") == pytest.approx(1234.56)
    assert bankinter.numero("1,234.56") == pytest.approx(1234.56)
    assert bankinter.numero("8,5") == pytest.approx(8.5)
    assert bankinter.numero(12) == 12.0
    assert bankinter.numero("") is None


def test_importar_posiciones_con_cabecera_desplazada():
    bruto = pd.DataFrame([
        ["Posición a 15/10/2026", None, None],
        ["Valor", "Títulos", "Precio medio"],
        ["BANCO SANTANDER, S.A.", "1.200", "4,85"],
        ["INDITEX", "30", "45,10"],
        ["EMPRESA DESCONOCIDA", "10", "3"],
        ["Total", None, None],
    ])
    pos = bankinter.leer_posiciones(bruto)
    assert list(pos["ticker"]) == ["SAN.MC", "ITX.MC", ""]
    assert list(pos["acciones"]) == [1200, 30, 10]
    assert pos.iloc[0]["precio_medio"] == pytest.approx(4.85)


def test_ticket_bankinter():
    texto = bankinter.ticket("SAN.MC", "Compra", 100, 8.45, stop=7.9, objetivo=9.6)
    for parte in ("Banco Santander", "Mercado Continuo", "Limitada", "8,45 €", "100", "STOP", "7,90"):
        assert parte in texto
    assert "Stop (de pérdidas)" in bankinter.ticket("SAN.MC", "Venta stop", 100, 7.9)


def test_consejos():
    assert bankinter.consejo_posicion(9, 10, 9.5, 9.0, 60)[0] == "vender"
    assert bankinter.consejo_posicion(11, 10, 9.5, 10.4, 30)[0] == "vigilar"
    assert bankinter.consejo_posicion(11, 10, None, 10.4, 70)[0] == "poner_stop"
    assert bankinter.consejo_posicion(12, 10, 9.5, 11.0, 70)[0] == "subir_stop"
    assert bankinter.consejo_posicion(10.2, 10, 9.5, 9.4, 70)[0] == "mantener"


# ----------------------------------------------------------------- almacenamiento
def test_almacen_local(tmp_path):
    a = almacen.Almacen(tmp_path / "d" / "datos.json")
    assert a.cargar() == {}
    a.guardar({"robot": {"capital": 1000}})
    assert a.cargar() == {"robot": {"capital": 1000}}


def test_almacen_gist(monkeypatch):
    import requests

    guardado = {}

    class Resp:
        def __init__(self, data=None):
            self._data = data or {}

        def raise_for_status(self):
            pass

        def json(self):
            return self._data

    def fake_patch(url, headers, json, timeout):
        assert url.endswith("/gists/abc") and headers["Authorization"] == "Bearer tok"
        guardado.update(json["files"])
        return Resp()

    def fake_get(url, headers, timeout):
        return Resp({"files": guardado})

    monkeypatch.setattr(requests, "patch", fake_patch)
    monkeypatch.setattr(requests, "get", fake_get)
    a = almacen.Almacen(gist_token="tok", gist_id="abc")
    assert a.en_la_nube
    a.guardar({"x": 1})
    assert a.cargar() == {"x": 1}
    assert almacen.desde_secrets({"gist": {"token": "t", "id": "i"}}).en_la_nube
    assert not almacen.desde_secrets({}).en_la_nube
