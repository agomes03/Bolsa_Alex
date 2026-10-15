import pandas as pd
import pytest

from bolsa import activos, bankinter, costes, horario
from bolsa.tickers import (CATALOGO, NO_INVERTIBLES, TODAS_LAS_ACCIONES, TODOS_LOS_VALORES, es_invertible, grupo_de,
                           nombre_de, sector_de)


def test_catalogo_amplia_sin_tocar_el_universo_del_informe():
    assert len(TODAS_LAS_ACCIONES) == 131
    assert set(TODAS_LAS_ACCIONES) <= set(TODOS_LOS_VALORES)
    for grupo in ("Asia", "Fondos indexados", "Criptomonedas", "Divisas", "Materias primas", "Índices",
                  "Tipos de interés y macro"):
        assert len(CATALOGO[grupo]) >= 7
    assert nombre_de("0700.HK") == "Tencent" and sector_de("NESN.SW") == "Consumo"
    assert grupo_de("GC=F") == "Materias primas" and not es_invertible("^IBEX") and es_invertible("USDEUR=X")
    assert "^TNX" in NO_INVERTIBLES


@pytest.mark.parametrize("ticker,divisa,clase", [
    ("0700.HK", "HKD", "Acciones"), ("005930.KS", "KRW", "Acciones"), ("2330.TW", "TWD", "Acciones"),
    ("RELIANCE.NS", "INR", "Acciones"), ("NOVO-B.CO", "DKK", "Acciones"), ("SGLD.L", "USD", "Oro y materias primas"),
    ("USDEUR=X", "EUR", "Divisas"), ("GC=F", "USD", "Oro y materias primas"), ("0P00000WLG.F", "EUR", "Fondos y ETF"),
    ("0P00012I69.F", "EUR", "Renta fija"), ("EUNA.DE", "EUR", "Renta fija"), ("^TNX", "—", "Índices y macro"),
    ("SOL-EUR", "EUR", "Criptomonedas")])
def test_divisa_y_clase_de_cada_tipo(ticker, divisa, clase):
    assert costes.divisa(ticker) == divisa and activos.clase_de(ticker) == clase


def test_costes_realistas_por_tipo_de_activo():
    t = costes.Tarifa()
    assert t.coste(2_000, "0P00000WLG.F") == 0                       # fondos: sin comisión de compra
    assert t.coste(2_000, "USDEUR=X") == pytest.approx(20.0)        # divisa: solo el margen del cambio (1 %)
    assert costes.coste_compra(2_000, "0700.HK", t)["itf"] == 0      # sin tasa Tobin fuera de ES/FR/IT
    assert costes.TARIFAS_PRECARGADAS["Trade Republic"].coste(2_000, "0P00000WLG.F") == 0


def test_horarios_y_mercados_de_cada_bolsa():
    from datetime import datetime, timezone
    madrugada = datetime(2026, 10, 14, 2, 30, tzinfo=timezone.utc)   # 11:30 en Tokio, 4:30 en Madrid
    assert horario.estado_mercado("7203.T", madrugada)["abierto"]
    assert not horario.estado_mercado("SAN.MC", madrugada)["abierto"]
    assert horario.estado_mercado("USDEUR=X", madrugada)["abierto"]
    assert bankinter.mercado_de("7203.T") == "Bolsa de Tokio" and "no se compra" in bankinter.mercado_de("^IBEX")


def test_reducir_puntos_mantiene_el_ultimo():
    from ui_comun import reducir

    s = pd.Series(range(2_500), index=pd.bdate_range("2016-01-01", periods=2_500))
    r = reducir(s, 400)
    assert len(r) <= 401 and r.index[-1] == s.index[-1] and r.iloc[-1] == 2_499
    assert reducir(s.iloc[:100], 400) is not None and len(reducir(s.iloc[:100], 400)) == 100
