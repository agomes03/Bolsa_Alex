"""Errores encontrados en la revisión herramienta por herramienta (para que no vuelvan)."""

from datetime import datetime, timezone

from bolsa import cuentas, horario, renta


def _h(fecha, tipo, n, resultado=None, motivo="x"):
    return {"fecha": fecha, "tipo": tipo, "ticker": "X.MC", "acciones": n, "precio": 10.0, "gastos": 0.0,
            "resultado": resultado, "motivo": motivo, "fx": 1.0}


def test_regla_dos_meses_no_cuenta_las_acciones_que_vendes():
    # Compras 10 y vendes las 10 con pérdida un mes después: la pérdida SÍ se puede restar.
    hist = [_h("2026-03-01", "Compra", 10), _h("2026-04-01", "Venta", 10, -200)]
    assert renta.ventas_del_ano(hist, 2026)[0]["aplazada"] is False
    # Si te quedan acciones compradas en esos dos meses, no.
    hist = [_h("2026-03-01", "Compra", 10), _h("2026-03-20", "Compra", 10), _h("2026-04-01", "Venta", 10, -200)]
    assert renta.ventas_del_ano(hist, 2026)[0]["aplazada"] is True
    # Recompra el mismo día o en los dos meses siguientes: tampoco.
    hist = [_h("2025-01-01", "Compra", 10), _h("2026-04-01", "Venta", 10, -200), _h("2026-04-01", "Compra", 10)]
    assert renta.ventas_del_ano(hist, 2026)[0]["aplazada"] is True
    # Lo importado lleva la fecha de la importación, no la de la compra: no cuenta.
    hist = [_h("2026-03-25", "Compra", 20, motivo="Importada (archivo)"), _h("2026-04-01", "Venta", 10, -200)]
    assert renta.ventas_del_ano(hist, 2026)[0]["aplazada"] is False


def test_los_indices_usan_el_horario_de_su_bolsa():
    viernes_20h = datetime(2026, 10, 16, 18, 0, tzinfo=timezone.utc)
    assert horario.estado_mercado("^GSPC", viernes_20h)["abierto"] is True
    assert horario.estado_mercado("^IBEX", viernes_20h)["abierto"] is False


def test_guardar_desde_dos_dispositivos_no_pisa_otras_cuentas():
    mio = {"cuentas": {"Mi cuenta": {"posiciones": {"SAN.MC": {}}}, "Mamá": {"posiciones": {}}},
           "cuenta_activa": "Mi cuenta"}
    remoto = {"cuentas": {"Mi cuenta": {"posiciones": {}}, "Mamá": {"posiciones": {"ITX.MC": {}}}},
              "cuenta_activa": "Mamá"}
    junto = cuentas.combinar(mio, remoto, "Mi cuenta")
    assert "SAN.MC" in junto["cuentas"]["Mi cuenta"]["posiciones"]          # lo mío se queda
    assert "ITX.MC" in junto["cuentas"]["Mamá"]["posiciones"]               # lo que apuntó tu madre, también


def test_telegram_avisa_cada_cruce_una_sola_vez_aunque_el_aviso_vaya_con_retraso():
    import pandas as pd

    from bolsa import alertas

    idx = pd.date_range("2026-10-15 09:00", periods=8, freq="h")
    df = pd.DataFrame({"Low": [14.2, 14.1, 13.9, 13.8, 13.9, 14.3, 14.2, 13.4],
                       "High": [14.4, 14.3, 14.1, 14.0, 14.2, 14.5, 14.3, 13.9],
                       "Close": [14.3, 14.2, 13.95, 13.9, 14.1, 14.4, 14.2, 13.5]}, index=idx)
    aviso = [{"id": 1, "ticker": "SAN.MC", "nombre": "Santander", "tipo": "baja", "precio": 14.0,
              "creada": "2026-10-15", "disparada": None}]
    enviados = {}
    ahora = pd.Timestamp("2026-10-15 13:30").to_pydatetime()
    assert len(alertas.cruces_nuevos(aviso, {"SAN.MC": df.iloc[:4]}, enviados, "Mi cuenta", ahora)) == 1
    # La siguiente vuelta (aunque llegue tarde) no repite el mismo cruce...
    assert alertas.cruces_nuevos(aviso, {"SAN.MC": df.iloc[:6]}, enviados, "Mi cuenta", ahora) == []
    # ...pero si vuelve a subir y cruza otra vez, sí avisa.
    assert len(alertas.cruces_nuevos(aviso, {"SAN.MC": df}, enviados, "Mi cuenta", ahora)) == 1
