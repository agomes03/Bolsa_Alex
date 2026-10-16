"""Qué hacer con cada acción: esperar, diversificar, stop-loss, vigilar o vender (con el consenso de analistas)."""

from bolsa import decision

FUND = {"recommendationKey": "buy", "numberOfAnalystOpinions": 21, "targetMeanPrice": 13.71,
        "targetLowPrice": 11.3, "targetHighPrice": 15.3}


def fila(nivel="mantener", stop=None, sin_stop=False, acciones=1000, precio=12.0):
    return {"pos": {"acciones": acciones, "stop": stop, "sin_stop": sin_stop}, "nivel": nivel,
            "consejo": "Todo en orden: mantener.", "stop_sugerido": 11.0, "precio": precio, "clase": "Acciones"}


def test_consenso_de_analistas():
    c = decision.consenso(FUND, 12.0)
    assert c["n"] == 21 and c["recomendacion"] == "comprar"
    assert "21 analistas" in c["texto"] and "+14 %" in c["texto"] and "13,71" in c["texto"]
    assert decision.consenso({}, 12.0) is None


def test_demasiado_peso_es_diversificar_con_cuantas_vender():
    d = decision.decidir(fila(), valor=12_000, total=20_000, limite=0.20, precio_eur=12.0)
    assert d["clave"] == "diversificar" and "60 %" in d["texto"]
    assert "Vende unas 667 acciones" in d["texto"]                # (12.000 − 4.000) / 12 €
    assert d["tambien"] and "stop-loss en 11,00" in d["tambien"][0]


def test_sin_stop_es_poner_stop_y_con_stop_es_esperar():
    assert decision.decidir(fila(), 1_000, 20_000, 0.20, precio_eur=12.0)["clave"] == "stop"
    d = decision.decidir(fila(stop=11.0), 1_000, 20_000, 0.20, decision.consenso(FUND, 12.0), 12.0)
    assert d["clave"] == "esperar" and any("21 analistas" in m for m in d["motivos"])
    assert decision.decidir(fila(sin_stop=True), 1_000, 20_000, 0.20, precio_eur=12.0)["clave"] == "esperar"


def test_stop_tocado_y_analistas_negativos():
    assert decision.decidir(fila(nivel="vender", stop=11.0), 1_000, 20_000, 0.2, precio_eur=10.0)["clave"] == "vender"
    malos = {**FUND, "recommendationKey": "sell"}
    d = decision.decidir(fila(stop=11.0), 1_000, 20_000, 0.2, decision.consenso(malos, 12.0), 12.0)
    assert d["clave"] == "vigilar" and "analistas recomiendan" in d["texto"]


def test_por_encima_del_objetivo_de_los_analistas():
    caro = {**FUND, "targetMeanPrice": 10.0}
    d = decision.decidir(fila(stop=11.0, precio=12.0), 1_000, 20_000, 0.2, decision.consenso(caro, 12.0), 12.0)
    assert d["clave"] == "esperar" and any("por encima del objetivo" in m for m in d["motivos"])
