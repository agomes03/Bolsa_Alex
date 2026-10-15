import pandas as pd
import pytest

from bolsa import datos


@pytest.fixture
def respaldo(tmp_path, monkeypatch):
    monkeypatch.setattr(datos, "CARPETA_RESPALDO", tmp_path)
    datos.RESPALDOS_USADOS.clear()
    yield tmp_path
    datos.RESPALDOS_USADOS.clear()


class FalsoTicker:
    def __init__(self, df):
        self.df = df

    def history(self, **kw):
        if isinstance(self.df, Exception):
            raise self.df
        return self.df


def _df():
    return pd.DataFrame({"Open": [1.0, 2.0], "High": [1.0, 2.0], "Low": [1.0, 2.0], "Close": [1.0, 2.0],
                         "Volume": [1, 1]}, index=pd.to_datetime(["2026-10-14", "2026-10-15"]))


def test_si_yahoo_falla_usa_los_ultimos_datos_buenos(respaldo, monkeypatch):
    import yfinance as yf

    monkeypatch.setattr(yf, "Ticker", lambda t: FalsoTicker(_df()))
    assert len(datos.historico("SAN.MC", "2y")) == 2 and datos.respaldo_mas_antiguo() is None
    monkeypatch.setattr(yf, "Ticker", lambda t: FalsoTicker(ConnectionError("sin red")))
    df = datos.historico("SAN.MC", "2y")
    assert df["Close"].tolist() == [1.0, 2.0] and datos.respaldo_mas_antiguo() is not None
    assert datos.historico("NADA.MC", "2y").empty           # sin respaldo: vacío, sin romper


def test_varios_completa_con_respaldo_lo_que_falta(respaldo, monkeypatch):
    import yfinance as yf

    columnas = pd.MultiIndex.from_product([["SAN.MC", "ITX.MC"], ["Open", "High", "Low", "Close", "Volume"]])
    bueno = pd.DataFrame([[1, 1, 1, 1, 1] * 2, [2, 2, 2, 2, 2] * 2], columns=columnas,
                         index=pd.to_datetime(["2026-10-14", "2026-10-15"]), dtype=float)
    monkeypatch.setattr(yf, "download", lambda *a, **k: bueno)
    assert set(datos.varios(["SAN.MC", "ITX.MC"], "1y")) == {"SAN.MC", "ITX.MC"}
    monkeypatch.setattr(yf, "download", lambda *a, **k: (_ for _ in ()).throw(TimeoutError()))
    salida = datos.varios(["SAN.MC", "ITX.MC"], "1y")
    assert set(salida) == {"SAN.MC", "ITX.MC"} and set(datos.RESPALDOS_USADOS) == {"SAN.MC", "ITX.MC"}
