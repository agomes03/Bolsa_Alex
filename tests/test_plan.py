"""🎯 Mi plan: ideas del día según el objetivo (operación, rentas, proteger, crecer)."""

import numpy as np
import pandas as pd
import pytest

from bolsa import plan
from bolsa.activos import LIMITES_ALTERNATIVOS


def serie(tendencia_diaria: float, n: int = 300, inicio: float = 100.0) -> pd.DataFrame:
    c = inicio * np.cumprod(np.full(n, 1 + tendencia_diaria))
    return pd.DataFrame({"Open": c, "High": c * 1.005, "Low": c * 0.995, "Close": c, "Volume": 1.0},
                        index=pd.bdate_range(end="2026-10-16", periods=n))


def fila(t, nota, sector, riesgo="bajo", dividendo=0.02, resultados=False, alcista=True):
    return {"ticker": t, "nombre": t, "nota": nota, "sector": sector, "riesgo_nivel": riesgo, "precio": 10.0,
            "stop": 9.0, "objetivo": 12.0, "momentum": 0.3, "dividendo": dividendo, "resultados_pronto": resultados,
            "mercado_alcista": alcista, "p10_1m": -0.08, "p90_1m": 0.1, "de": 130}


RANKING = [fila("ELE.MC", 99, "Eléctricas", dividendo=0.05), fila("IBE.MC", 95, "Eléctricas", dividendo=0.045),
           fila("SAN.MC", 90, "Banca", riesgo="alto"), fila("ITX.MC", 85, "Textil", resultados=True),
           fila("LOG.MC", 80, "Distribución", dividendo=0.06), fila("TEF.MC", 50, "Telecom", dividendo=0.07),
           fila("TTE.PA", 100, "Petróleo"), fila("AAPL", 75, "Tecnología")]


def test_ideas_de_acciones_buenas_y_de_sectores_distintos():
    ideas = plan.ideas_acciones(RANKING, nacionales=True)
    assert [i["ticker"] for i in ideas] == ["ELE.MC", "LOG.MC"]      # sin repetir sector, sin riesgo alto ni resultados
    assert ideas[0]["riesgo_pct"] == pytest.approx(0.1) and ideas[0]["beneficio_pct"] == pytest.approx(0.2)
    assert "entre −8,0 %" not in ideas[0]["por_que"] and "-8,0 %" in ideas[0]["por_que"]
    assert [i["ticker"] for i in plan.ideas_acciones(RANKING, nacionales=False)] == ["TTE.PA", "AAPL"]


def test_dividendos():
    ideas = plan.ideas_dividendo(RANKING)
    assert [i["ticker"] for i in ideas][:3] == ["TEF.MC", "LOG.MC", "ELE.MC"]   # el más alto primero, un sector cada uno
    assert ideas[0]["riesgo_nivel"] == "bajo"


def test_oro_y_divisas_segun_la_tendencia_de_hoy():
    sube, baja = serie(0.002), serie(-0.001)
    oro = plan.idea_alternativo("Oro", "4GLD.DE", "Oro", "...", sube)
    assert oro and oro["tipo"] == "Oro" and oro["stop"] < oro["precio"] < oro["objetivo"]
    assert plan.idea_alternativo("Oro", "4GLD.DE", "Oro", "...", baja) is None
    usd = plan.idea_divisa("EURUSD=X", baja)                 # el euro baja frente al dólar: comprar dólares
    assert usd and "dólar" in usd["nombre"] and usd["stop"] > usd["precio"] > usd["objetivo"]
    assert plan.idea_divisa("EURUSD=X", sube) is None


def test_ideas_del_dia_dice_por_que_no_hay_idea():
    hist = {"4GLD.DE": serie(-0.001), "EURUSD=X": serie(0.001)}
    ideas, sin = plan.ideas_del_dia(["Acciones españolas", "Oro", "Divisas"], RANKING, hist)
    assert {i["tipo"] for i in ideas} == {"Acción"}
    assert any(s.startswith("Oro") for s in sin) and any(s.startswith("Divisas") for s in sin)


def test_operacion_no_pierde_mas_de_lo_elegido():
    ideas = plan.ideas_acciones(RANKING, nacionales=True) + plan.ideas_acciones(RANKING, nacionales=False)
    r = plan.plan_operacion(10_000, 0.03, ideas)
    assert len(r["posiciones"]) == 4
    assert r["riesgo_total"] == pytest.approx(300)            # 3 % de 10.000 € si saltan todos los stops
    assert sum(p["euros"] for p in r["posiciones"]) + r["liquidez"] == pytest.approx(10_000)
    assert all(p["euros"] <= 2_500 + 1e-6 for p in r["posiciones"])
    pequeno = plan.plan_operacion(800, 0.05, ideas)
    assert len(pequeno["posiciones"]) == 1 and pequeno["avisos"]


def test_rentas_y_proteger():
    ideas = plan.ideas_dividendo(RANKING)
    r = plan.plan_rentas(10_000, "Moderado", ideas, interes_liquidez=0.02)
    assert sum(a["euros"] for a in r["acciones"]) == pytest.approx(5_000) and r["renta_fija"] == pytest.approx(5_000)
    assert r["renta_anual"] > 100 + 200       # liquidez al 2 % (100 €) más dividendos de más del 4 %
    p = plan.plan_proteger(10_000)
    assert sum(x["pct"] for x in p) == 100 and [x["parte"] for x in p][-1] == "Oro"


def test_satelites_respetan_el_perfil():
    assert plan.satelites("Conservador", ["Oro", "Criptomonedas"], LIMITES_ALTERNATIVOS) == {"Oro": 0.05}
    assert plan.satelites("Dinámico", ["Criptomonedas"], LIMITES_ALTERNATIVOS) == {"Criptomonedas": 0.05}


def test_la_operacion_mezcla_tipos_si_te_interesan_varios():
    acciones = plan.ideas_acciones(RANKING, nacionales=True) + plan.ideas_acciones(RANKING, nacionales=False)
    oro = plan.idea_alternativo("Oro", "4GLD.DE", "Oro", "...", serie(0.002))
    usd = plan.idea_divisa("EURUSD=X", serie(-0.001))
    r = plan.plan_operacion(10_000, 0.05, acciones + [oro, usd])
    assert {p["tipo"] for p in r["posiciones"]} == {"Acción", "Oro", "Divisa"}
    assert plan.frente_a("GBP") == "a la libra esterlina" and plan.frente_a("USD") == "al dólar estadounidense"
