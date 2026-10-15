from datetime import date

import pytest

from bolsa import reequilibrio
from bolsa.costes import impuesto_ganancia

ITX = {"ticker": "ITX.MC", "nombre": "Inditex", "acciones": 351, "importe": 19_459, "coste": 9, "ganancia": -465}
IDR = {"ticker": "IDR.MC", "nombre": "Indra", "acciones": 930, "importe": 58_683, "coste": 9, "ganancia": 2_130}


def test_ganancia_pequena_vende_todo_ahora_y_perdidas_primero():
    p = reequilibrio.planificar([IDR, ITX], 78_000, {"Fondo indexado mundial": 78_000}, date(2026, 10, 15))
    assert p["ahorro"] == 0 and len(p["pasos"]) == 1
    assert [v["ticker"] for v in p["pasos"][0]["ventas"]] == ["ITX.MC", "IDR.MC"]
    assert p["irpf_plan"] == pytest.approx(impuesto_ganancia(2_130 - 465))
    assert [a["fecha"] for a in p["aportaciones"]] == [date(2026, 10, 15), date(2026, 11, 15), date(2026, 12, 15)]


def test_ganancia_grande_se_reparte_entre_dos_anos():
    grande = {"ticker": "IDR.MC", "nombre": "Indra", "acciones": 1000, "importe": 100_000, "coste": 9,
              "ganancia": 40_000}
    p = reequilibrio.planificar([grande], 100_000, {}, date(2026, 11, 20))
    assert p["irpf_todo_ahora"] == pytest.approx(impuesto_ganancia(40_000))
    assert p["irpf_plan"] == pytest.approx(2 * impuesto_ganancia(20_000))
    assert p["ahorro"] == pytest.approx(120) and len(p["pasos"]) == 2
    assert p["pasos"][1]["fecha"] == date(2027, 1, 4)         # el 2 de enero de 2027 es sábado
    assert sum(v["acciones"] for paso in p["pasos"] for v in paso["ventas"]) == 1000


def test_ganancias_ya_realizadas_y_perdidas_que_compensan():
    p = reequilibrio.planificar([IDR], 0, {}, date(2026, 10, 15), otras_ganancias_ano=-3_000)
    assert p["irpf_plan"] == 0
    assert reequilibrio.ahorro_por_perdidas([{"ganancia": -1_000}], 2_000) == pytest.approx(190)
    assert reequilibrio.planificar([], 0, {})["pasos"] == []
