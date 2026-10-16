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


def test_ultimo_precio_y_cierre_anterior():
    import pandas as pd

    from bolsa import datos

    df = pd.DataFrame({"Close": [10.0, 10.5, 11.0]}, index=pd.bdate_range(end="2026-10-16", periods=3))
    q = datos.ultimo_precio(df)
    assert q["precio"] == 11.0 and q["anterior"] == 10.5 and str(q["fecha"]) == "2026-10-16"
    assert abs(q["variacion_pct"] - 4.7619) < 1e-3
    assert datos.ultimo_precio(None) is None and datos.ultimo_precio(df.iloc[:0]) is None


def test_precio_reciente_une_vela_diaria_e_intradia():
    import pandas as pd

    from bolsa import datos

    diario = pd.Series([43.0, 43.19], index=pd.to_datetime(["2026-10-13", "2026-10-14"]))
    # La vela diaria del 15/10 aún no está publicada, pero las de 15 minutos sí.
    intra = pd.Series([43.1, 42.5, 42.17], index=pd.to_datetime(
        ["2026-10-14 17:15", "2026-10-15 09:00", "2026-10-15 17:15"]).tz_localize("Europe/Madrid"))
    q = datos.combinar_precio(diario, intra)
    assert str(q["fecha"]) == "2026-10-15" and q["precio"] == 42.17 and q["anterior"] == 43.19   # cierre oficial del 14
    assert round(q["variacion_pct"], 2) == -2.36
    # Si la vela diaria existe, manda ella (incluye la subasta de cierre).
    diario2 = pd.concat([diario, pd.Series([42.20], index=pd.to_datetime(["2026-10-15"]))])
    assert datos.combinar_precio(diario2, intra)["precio"] == 42.20
    assert datos.combinar_precio(None, None) is None
