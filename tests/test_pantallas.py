"""Pruebas de pantallas: cada página se abre sin errores, en ordenador y en móvil, con datos simulados.

No se conecta a Internet: las descargas (Yahoo Finance, RSS) se sustituyen por datos inventados y los datos del
usuario se guardan en una carpeta temporal.
"""

from __future__ import annotations

import zlib
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from bolsa import cartera, costes, datos, noticias

APP = str(Path(__file__).resolve().parent.parent / "app.py")
SESIONES = {"10y": 2500, "5y": 1260, "max": 5000, "1y": 250, "6mo": 126, "1mo": 21, "5d": 5}

PAGINAS = ["pagina_hoy", "pagina_plan", "pagina_chat", "pagina_analizar", "pagina_radar", "pagina_carteras",
           "pagina_noticias", "pagina_resumen", "pagina_bankinter", "pagina_cartera_virtual", "pagina_acierto",
           "pagina_simulador", "pagina_calculadoras", "pagina_aprende"]


def historico_falso(ticker: str, periodo: str = "2y") -> pd.DataFrame:
    n = SESIONES.get(periodo, 500)
    rng = np.random.default_rng(zlib.crc32(ticker.encode()) % 1000)
    c = 100 * np.cumprod(1 + rng.normal(0.0004, 0.013, n))
    o = np.r_[c[0], c[:-1]]
    return pd.DataFrame({"Open": o, "High": np.maximum(o, c) * 1.004, "Low": np.minimum(o, c) * 0.996, "Close": c,
                         "Volume": 1e6}, index=pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=n))


def intradia_falso(ticker: str, periodo: str = "5d", intervalo: str = "5m") -> pd.DataFrame:
    """Como datos.intradia: velas de 5 minutos en hora de Madrid, sin zona horaria."""
    dias = historico_falso(ticker, "5d")
    filas = []
    for dia, f in dias.iterrows():
        horas = pd.date_range(dia + pd.Timedelta(hours=9), dia + pd.Timedelta(hours=17, minutes=25), freq="5min")
        precios = np.linspace(f["Open"], f["Close"], len(horas))
        filas.append(pd.DataFrame({"Open": precios, "High": precios * 1.001, "Low": precios * 0.999,
                                   "Close": precios, "Volume": 1e4}, index=horas))
    return pd.concat(filas)


def _prohibido(*_a, **_k):
    raise RuntimeError("Las pruebas no deben descargar nada de Internet")


@pytest.fixture(autouse=True)
def sin_internet(monkeypatch, tmp_path):
    """Datos simulados, carpeta temporal y un menú que abre directamente la página que se quiere probar."""
    import yfinance

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(datos, "CARPETA_RESPALDO", tmp_path / "respaldo")
    for nombre in ("download", "Ticker", "Search"):
        monkeypatch.setattr(yfinance, nombre, _prohibido)
    monkeypatch.setattr(datos, "historico", historico_falso)
    monkeypatch.setattr(datos, "varios", lambda ts, periodo="2y": {t: historico_falso(t, periodo) for t in ts})
    monkeypatch.setattr(datos, "diario_sin_ajustar", lambda t, periodo="1y": historico_falso(t, periodo))
    monkeypatch.setattr(datos, "intradia", intradia_falso)
    monkeypatch.setattr(datos, "fundamentales", lambda t: {"targetMeanPrice": 150.0, "numberOfAnalystOpinions": 12,
                                                          "recommendationKey": "buy", "currency": "EUR"})
    monkeypatch.setattr(datos, "noticias_yahoo", lambda t: [])
    monkeypatch.setattr(datos, "dividendos", lambda t: pd.Series(dtype=float))
    monkeypatch.setattr(datos, "dividendos_varios", lambda ts, periodo="5y": {})
    monkeypatch.setattr(datos, "buscar_simbolo", lambda q: None)
    titular = noticias.Noticia("El BCE baja los tipos de interés", "x", "Prueba", datetime.now(timezone.utc))
    monkeypatch.setattr(noticias, "descargar", lambda *a, **k: (noticias.combinar([titular], 72), []))
    monkeypatch.setattr(st, "Page", lambda fn, **kw: fn)
    monkeypatch.setattr(st, "switch_page", lambda p: None)
    st.cache_data.clear()
    yield


def abrir(pagina: str, movil: bool = False, datos_usuario: dict | None = None, secretos: dict | None = None):
    def navegacion(paginas, **_k):
        todas = [p for grupo in paginas.values() for p in grupo]
        return SimpleNamespace(run=next(p for p in todas if p.__name__ == pagina))

    st.navigation = navegacion
    at = AppTest.from_file(APP, default_timeout=120)
    if datos_usuario is not None:
        at.session_state["_datos"] = datos_usuario
    for k, v in (secretos or {}).items():
        at.secrets[k] = v
    at.run()
    if movil and at.sidebar.toggle:
        at.sidebar.toggle[0].set_value(True).run()
    return at


def sin_fallos(at):
    """Ningún error de programa. (Los avisos en rojo de la propia app, como «esta estrategia pierde», sí valen.)"""
    assert [e.value for e in at.exception] == []


def cartera_de_prueba() -> dict:
    cr = cartera.nueva(None)
    for t, n, p in [("SAN.MC", 2500, 12.46), ("IDR.MC", 1500, 60.80), ("IWDA.AS", 300, 90.0), ("BTC-EUR", 0.05, 5e4)]:
        cartera.comprar(cr, t, n, p, costes.Tarifa(), "2026-09-01", None, nota="prueba", fx=1.0)
    return cr


@pytest.fixture(scope="module", autouse=True)
def navegacion_original():
    original = st.navigation
    yield
    st.navigation = original


@pytest.mark.parametrize("pagina", PAGINAS)
def test_pagina_en_ordenador(pagina):
    sin_fallos(abrir(pagina))


@pytest.mark.parametrize("pagina", ["pagina_hoy", "pagina_resumen", "pagina_bankinter", "pagina_cartera_virtual",
                                    "pagina_analizar", "pagina_aprende"])
def test_pagina_en_movil(pagina):
    at = abrir(pagina, movil=True)
    sin_fallos(at)
    assert at.sidebar.toggle[0].value is True


@pytest.mark.parametrize("pagina", ["pagina_hoy", "pagina_bankinter"])
@pytest.mark.parametrize("broker", ["Bankinter", "Trade Republic"])
def test_con_cartera_real(pagina, broker):
    at = abrir(pagina, datos_usuario={"cartera_real": cartera_de_prueba(), "broker": broker})
    sin_fallos(at)
    assert at.metric, "debería mostrar el valor de la cartera"


def test_aprende_buscador_encuentra_terminos():
    at = abrir("pagina_aprende")
    at.text_input[0].set_value("stop loss").run()
    sin_fallos(at)
    assert any("Stop-loss" in m.value for m in at.markdown)


def test_cartera_virtual_muestra_el_saldo():
    at = abrir("pagina_cartera_virtual")
    sin_fallos(at)
    assert any("Valor total" in m.label for m in at.metric)


def test_contrasena_bloquea_y_deja_pasar():
    secretos = {"app": {"password": "secreta"}}
    at = abrir("pagina_hoy", secretos=secretos)
    assert "_datos" not in at.session_state
    assert not at.sidebar.toggle, "sin contraseña no se ve nada de la app"
    at.text_input[0].set_value("mala")
    at.button[0].click().run()
    assert [e.value for e in at.error] == ["Contraseña incorrecta."]
    at.text_input[0].set_value("secreta")
    at.button[0].click().run()
    at.run()
    sin_fallos(at)
    assert at.sidebar.toggle, "con la contraseña buena se abre la app"


def test_sin_contrasena_avisa_en_la_barra():
    at = abrir("pagina_hoy")
    assert any("sin contraseña" in c.value for c in at.sidebar.caption)
