from datetime import date, datetime, timezone

import pandas as pd
import pytest

from bolsa import asesor_diario, dividendos

DIV_SAN = pd.Series([0.10, 0.11, 0.115, 0.125],
                    index=pd.to_datetime(["2024-10-30", "2025-04-29", "2025-10-30", "2026-04-30"]).tz_localize("UTC"))
HOY = date(2026, 10, 15)


def test_ingresos_anuales_y_proximo_confirmado():
    ex = datetime(2026, 10, 29, tzinfo=timezone.utc).timestamp()
    r = dividendos.resumen("SAN.MC", DIV_SAN, ex, 2500, 12.0, hoy=HOY)
    assert r["por_accion_ano"] == pytest.approx(0.24) and r["pagos_ano"] == 2
    assert r["bruto_ano"] == pytest.approx(600) and r["neto_ano"] == pytest.approx(486)
    assert r["rentabilidad"] == pytest.approx(0.02)
    assert r["proximo"] == date(2026, 10, 29) and r["proximo_confirmado"]
    assert r["proximo_importe"] == pytest.approx(2500 * 0.125)


def test_proximo_estimado_y_cobrado_desde_compra():
    r = dividendos.resumen("SAN.MC", DIV_SAN, None, 100, 12.0, hoy=HOY, fecha_compra="2025-01-01")
    assert r["proximo"] == date(2026, 10, 30) and not r["proximo_confirmado"]
    assert r["cobrado_desde_compra"] == pytest.approx(100 * (0.11 + 0.115 + 0.125))
    assert dividendos.resumen("X", None, None, 10, 5.0, hoy=HOY)["bruto_ano"] == 0


def test_calendario_y_aviso_del_asesor():
    ex = datetime(2026, 10, 20, tzinfo=timezone.utc).timestamp()
    r = {**dividendos.resumen("SAN.MC", DIV_SAN, ex, 2500, 12.0, hoy=HOY), "nombre": "Santander"}
    assert dividendos.calendario([r], dias=10, hoy=HOY) == [r]
    plan = asesor_diario.plan_del_dia({"clases": {}, "hallazgos": []}, [], {}, [], hoy=HOY, dividendos=[r])
    assert any("dividendo el 20/10" in a["titulo"] and "19/10" in a["texto"] for a in plan)
