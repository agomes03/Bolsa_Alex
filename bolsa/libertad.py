"""Calculadora de libertad financiera («FIRE»): cuánto dinero necesitas para vivir de tus inversiones y cuántos
años te faltan con lo que tienes y lo que aportas cada mes.

Regla del 4 %: si cada año sacas un 4 % de una cartera diversificada (subiéndolo con la inflación), históricamente
ha durado unos 30 años o más. Para retiros más largos o más prudencia, un 3-3,5 %. Las rentabilidades son REALES
(ya descontada la inflación), así que todo sale en euros de hoy.
"""

from __future__ import annotations

RENTABILIDAD_REAL = {"Conservador": 0.025, "Moderado": 0.04, "Dinámico": 0.05}


def calcular(gasto_mensual: float, capital: float, aportacion_mensual: float, rentabilidad_real: float,
             tasa_retiro: float = 0.04, max_anos: int = 60) -> dict:
    """objetivo (€), años hasta llegar (None si no se llega en `max_anos`), renta mensual que ya darías hoy y la
    evolución año a año en tres escenarios (2 puntos peor, el elegido y 2 puntos mejor)."""
    objetivo = gasto_mensual * 12 / tasa_retiro if tasa_retiro > 0 else float("inf")
    escenarios = {}
    for nombre, r in (("Pesimista", rentabilidad_real - 0.02), ("Esperado", rentabilidad_real),
                      ("Optimista", rentabilidad_real + 0.02)):
        valores, anos = [capital], None
        for ano in range(1, max_anos + 1):
            valores.append(valores[-1] * (1 + r) + aportacion_mensual * 12)
            if anos is None and valores[-1] >= objetivo:
                anos = ano
        if capital >= objetivo:
            anos = 0
        escenarios[nombre] = {"rentabilidad": r, "anos": anos, "valores": valores}
    return {"objetivo": objetivo, "renta_hoy": capital * tasa_retiro / 12,
            "avance": capital / objetivo if objetivo else 0, "anos": escenarios["Esperado"]["anos"], "escenarios": escenarios}


__all__ = ["RENTABILIDAD_REAL", "calcular"]
