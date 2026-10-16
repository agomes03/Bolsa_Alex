"""Qué hacer con cada acción: esperar, comprar más, vender (todo o una parte), diversificar, stop-loss o vigilar,
con el consenso completo de los analistas y su fiabilidad."""

from bolsa import decision

FUND = {"recommendationKey": "buy", "numberOfAnalystOpinions": 21, "targetMeanPrice": 13.71,
        "targetLowPrice": 11.3, "targetHighPrice": 15.3}
EXTRA = {"recuento": {"strongBuy": 6, "buy": 11, "hold": 4, "sell": 0, "strongSell": 0},
         "recuento_antes": {"strongBuy": 6, "buy": 11, "hold": 2, "sell": 0, "strongSell": 1},
         "objetivos": {"mean": 13.71, "median": 14.0, "low": 11.3, "high": 15.3}, "revision_beneficios": 0.017}


def fila(nivel="mantener", stop=None, sin_stop=False, acciones=1000, precio=12.0, medio=12.46):
    return {"pos": {"acciones": acciones, "stop": stop, "sin_stop": sin_stop, "precio_medio": medio}, "nivel": nivel,
            "consejo": "Todo en orden: mantener.", "stop_sugerido": 11.0, "precio": precio, "clase": "Acciones"}


def test_consenso_completo_y_su_fiabilidad():
    c = decision.consenso(FUND, 12.0, EXTRA)
    assert c["n"] == 21 and c["clave"] == "buy" and c["fiabilidad"] == "alta" and c["tendencia"] == "estable"
    texto = " ".join(c["lineas"])
    assert "17 comprar · 4 mantener · 0 vender" in texto and "81 %" in texto
    assert "mediana" in texto and "14,00" in texto and "+17 %" in texto           # la mediana, no la media
    assert "subido sus previsiones de beneficio un 1,7 %" in texto
    # Sin el detalle, se usa el resumen de la empresa.
    solo = decision.consenso(FUND, 12.0)
    assert solo["n"] == 21 and solo["objetivo"] == 13.71
    assert decision.consenso({}, 12.0) is None


def test_fiabilidad_baja_si_hay_pocos_y_no_coinciden():
    extra = {"recuento": {"strongBuy": 1, "buy": 1, "hold": 1, "sell": 1, "strongSell": 0},
             "objetivos": {"median": 10.0, "low": 5.0, "high": 16.0}}
    assert decision.consenso({}, 10.0, extra)["fiabilidad"] == "baja"


def test_comprar_mas_si_todo_acompana_y_pesa_poco():
    a = decision.consenso(FUND, 12.0, EXTRA)
    d = decision.decidir(fila(stop=11.0), 1_200, 20_000, 0.20, a, 12.0)
    assert d["clave"] == "comprar" and "unas 233 acciones" in d["texto"]        # (4.000 − 1.200) / 12 €
    assert d["situacion"].startswith("Tienes 1.000 acciones compradas a 12,46 · hoy 12,00")
    assert d["analistas"] and "Fiabilidad" in d["analistas"][-1]


def test_esperar_si_ya_pesa_cerca_del_limite_o_los_analistas_dudan():
    a = decision.consenso(FUND, 12.0, EXTRA)
    assert decision.decidir(fila(stop=11.0), 3_500, 20_000, 0.20, a, 12.0)["clave"] == "esperar"
    dudosos = {**EXTRA, "recuento": {"strongBuy": 1, "buy": 1, "hold": 1, "sell": 1, "strongSell": 0}}
    assert decision.decidir(fila(stop=11.0), 1_200, 20_000, 0.20, decision.consenso({}, 12.0, dudosos),
                            12.0)["clave"] == "esperar"


def test_diversificar_stop_y_vender():
    d = decision.decidir(fila(), valor=12_000, total=20_000, limite=0.20, precio_eur=12.0)
    assert d["clave"] == "diversificar" and "Vende unas 667 acciones" in d["texto"]
    assert decision.decidir(fila(), 1_000, 20_000, 0.20, precio_eur=12.0)["clave"] == "stop"
    assert decision.decidir(fila(nivel="vender", stop=11.0), 1_000, 20_000, 0.2, precio_eur=10.0)["clave"] == "vender"
    malos = decision.consenso({"recommendationKey": "sell", "numberOfAnalystOpinions": 10}, 12.0)
    assert decision.decidir(fila(nivel="vigilar", stop=11.0), 1_000, 20_000, 0.2, malos, 12.0)["clave"] == "vender"
    assert decision.decidir(fila(stop=11.0), 1_000, 20_000, 0.2, malos, 12.0)["clave"] == "vigilar"


def test_vender_una_parte_si_supera_el_objetivo_mas_optimista():
    caro = {**EXTRA, "objetivos": {"median": 13.0, "low": 11.0, "high": 14.0}}
    d = decision.decidir(fila(stop=11.0, precio=15.0), 1_500, 20_000, 0.2, decision.consenso({}, 15.0, caro), 15.0)
    assert d["clave"] == "vender_parte" and "la mitad" in d["texto"]
