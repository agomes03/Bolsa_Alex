"""Finnhub con respuestas simuladas (sin conexión): precios de EEUU, noticias y comprobación de la clave."""

from datetime import date, datetime

import pytest
import requests

from bolsa import finnhub


class Respuesta:
    def __init__(self, datos, codigo=200):
        self._datos, self.status_code, self.text = datos, codigo, str(datos)

    def json(self):
        return self._datos


@pytest.fixture
def peticiones(monkeypatch):
    hechas = []

    def falso_get(url, params=None, timeout=None):
        hechas.append((url, params))
        if params["token"] == "mala":
            return Respuesta({"error": "Invalid API key"}, 401)
        if url.endswith("/quote"):
            return Respuesta({"c": 231.5, "d": 2.5, "dp": 1.09, "h": 232.0, "l": 228.1, "o": 229.0, "pc": 229.0,
                              "t": 1760551200})
        if url.endswith("/news"):
            return Respuesta([{"headline": "Fed holds rates", "url": "https://x", "source": "Reuters",
                               "datetime": 1760551200, "summary": "..."}, {"headline": "", "datetime": 1}])
        if url.endswith("/company-news"):
            return Respuesta([{"headline": "Apple beats estimates", "url": "https://y", "source": "CNBC",
                               "datetime": 1760551200, "summary": "Strong iPhone sales"}])
        return Respuesta(None, 404)

    monkeypatch.setattr(requests, "get", falso_get)
    return hechas


def test_solo_acciones_de_eeuu():
    assert finnhub.es_eeuu("AAPL") and finnhub.es_eeuu("SPY")
    assert not any(finnhub.es_eeuu(t) for t in ("SAN.MC", "^IBEX", "EURUSD=X", "BTC-EUR", ""))


def test_cotizacion_en_tiempo_real(peticiones):
    q = finnhub.cotizacion("AAPL", "buena")
    assert q["precio"] == 231.5 and q["variacion_pct"] == 1.09 and q["anterior"] == 229.0 and q["tiempo_real"]
    assert q["hora"] == datetime(2025, 10, 15, 20, 0)          # 18:00 UTC = 20:00 en Madrid
    assert finnhub.cotizacion("SAN.MC", "buena") is None
    assert len(peticiones) == 1                                 # a Finnhub solo se le pregunta por EEUU


def test_noticias(peticiones):
    n = finnhub.noticias_mercado("buena")
    assert [x["titulo"] for x in n] == ["Fed holds rates"] and n[0]["fuente"] == "Finnhub · Reuters"
    e = finnhub.noticias_empresa("AAPL", "buena", dias=7, hoy=date(2026, 10, 15))
    assert e[0]["titulo"] == "Apple beats estimates"
    assert peticiones[-1][1]["from"] == "2026-10-08" and peticiones[-1][1]["to"] == "2026-10-15"
    assert finnhub.noticias_empresa("SAN.MC", "buena") == []


def test_comprobar_la_clave(peticiones):
    assert finnhub.comprobar("buena")[0]
    ok, mensaje = finnhub.comprobar("mala")
    assert not ok and "no es válida" in mensaje
