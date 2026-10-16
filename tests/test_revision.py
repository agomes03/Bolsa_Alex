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


def test_guardar_en_la_nube_no_hace_esperar_y_guarda_lo_ultimo(monkeypatch):
    import time

    import streamlit as st

    import ui_comun

    class GistLento:
        en_la_nube = True

        def __init__(self):
            self.guardados, self.version = [], "v0"

        def cargar_con_version(self):
            time.sleep(0.3)
            return ({"cuentas": {}}, self.version)

        def guardar(self, datos):
            time.sleep(0.3)
            self.guardados.append(datos)
            self.version = f"v{len(self.guardados)}"
            return self.version

    gist = GistLento()
    monkeypatch.setattr(ui_comun, "_almacen", lambda: gist)
    ui_comun._GUARDADOS.clear()
    st.session_state["_datos"] = {"cartera_real": {"posiciones": {}, "historial": []}}
    st.session_state["_version_datos"] = "v0"
    t0 = time.time()
    for n in range(3):                                   # tres botones seguidos
        st.session_state["_datos"]["cartera_real"]["posiciones"] = {"SAN.MC": {"acciones": n}}
        ui_comun.guardar_datos()
    assert time.time() - t0 < 0.2                         # no espera a GitHub
    for _ in range(50):
        if not ui_comun._GUARDADOS["sin_sesion"].get("hilo"):
            break
        time.sleep(0.1)
    ultimo = gist.guardados[-1]["cuentas"]["Mi cuenta"]["posiciones"]
    assert ultimo == {"SAN.MC": {"acciones": 2}} and len(gist.guardados) <= 2   # lo último, sin repetir de más
    ui_comun.datos_usuario()
    assert st.session_state["_guardado"][0] is True and st.session_state["_version_datos"] == gist.version
    st.session_state.clear()


def test_juntar_con_otro_dispositivo_respeta_borrados_renombrados_y_cuentas_nuevas():
    remoto = {"cuentas": {"Yo": {"posiciones": {}}, "Mamá": {"posiciones": {"ITX.MC": {}}},
                          "Hermano": {"posiciones": {"BBVA.MC": {}}}}}
    conocidas = {"Yo", "Mamá"}                       # Hermano lo creó otro dispositivo después
    # Borro Mamá y renombro Yo -> Nuevo en este dispositivo.
    mio = {"cuentas": {"Nuevo": {"posiciones": {"SAN.MC": {}}}}, "cuenta_activa": "Nuevo"}
    junto = cuentas.combinar(mio, remoto, {"Nuevo"}, conocidas)
    assert set(junto["cuentas"]) == {"Nuevo", "Hermano"}                   # ni Mamá ni Yo vuelven
    # Cambio Yo y luego paso a Mamá antes de guardar: lo de Yo no se pierde.
    mio = {"cuentas": {"Yo": {"posiciones": {"SAN.MC": {}}}, "Mamá": {"posiciones": {}}}, "cuenta_activa": "Mamá"}
    junto = cuentas.combinar(mio, remoto, {"Yo", "Mamá"}, conocidas)
    assert "SAN.MC" in junto["cuentas"]["Yo"]["posiciones"] and junto["cuentas"]["Mamá"]["posiciones"] == {}


def test_si_falla_el_guardado_queda_pendiente_y_se_reintenta(monkeypatch):
    import time

    import streamlit as st

    import ui_comun

    class GistQueFallaUnaVez:
        en_la_nube = True

        def __init__(self):
            self.intentos, self.guardados = 0, []

        def cargar_con_version(self):
            return ({}, "v0")

        def guardar(self, datos):
            self.intentos += 1
            if self.intentos == 1:
                raise RuntimeError("GitHub no responde")
            self.guardados.append(datos)
            return "v1"

    gist = GistQueFallaUnaVez()
    monkeypatch.setattr(ui_comun, "_almacen", lambda: gist)
    ui_comun._GUARDADOS.clear()
    st.session_state["_datos"] = {"cartera_real": {"posiciones": {"SAN.MC": {"acciones": 1}}, "historial": []}}
    st.session_state["_version_datos"] = "v0"
    ui_comun.guardar_datos()
    reg = ui_comun._GUARDADOS["sin_sesion"]
    for _ in range(50):
        if not reg.get("hilo"):
            break
        time.sleep(0.05)
    assert reg.get("pendiente") and reg["estado"][0] is False            # no se ha perdido: sigue pendiente
    reg["ultimo_fallo"] = 0                                              # (sin esperar al reintento)
    ui_comun.datos_usuario()                                             # cualquier pantalla lo reintenta
    for _ in range(50):
        if not reg.get("hilo"):
            break
        time.sleep(0.05)
    assert gist.guardados and not reg.get("pendiente") and reg["estado"][0] is True
    st.session_state.clear()


def test_validez_hasta_fin_de_semana_y_tasa_tobin_de_empresas_pequenas(monkeypatch):
    from datetime import date, datetime

    import paginas_virtual
    from bolsa import costes, horario

    for hoy, viernes in ((date(2026, 10, 14), date(2026, 10, 16)), (date(2026, 10, 17), date(2026, 10, 23)),
                         (date(2026, 10, 18), date(2026, 10, 23))):
        monkeypatch.setattr(horario, "ahora_madrid", lambda h=hoy: datetime(h.year, h.month, h.day, 12))
        assert paginas_virtual._fecha_validez("Hasta fin de semana", None) == viernes
    assert costes.coste_compra(1000, "ECR.MC", costes.Tarifa(), 400e6)["itf"] == 0          # pequeña: no paga
    assert costes.coste_compra(1000, "SAN.MC", costes.Tarifa(), 80e9)["itf"] == 2.0


def test_el_stop_mira_otra_vez_la_vela_que_aun_se_esta_formando():
    import pandas as pd

    from bolsa import cartera, costes

    cv = cartera.nueva(10_000.0)
    cartera.comprar(cv, "SAN.MC", 100, 12.0, costes.Tarifa(), "2026-10-14", 11.0, nota="x", fx=1.0)
    dias = pd.to_datetime(["2026-10-15", "2026-10-16"])
    velas = pd.DataFrame({"Open": [12.0, 12.0], "High": [12.2, 12.1], "Low": [11.8, 11.5], "Close": [12.0, 11.9]},
                         index=dias)
    assert cartera.revisar_ordenes(cv, {"SAN.MC": velas}, costes.Tarifa()) == []
    velas.loc[dias[-1], "Low"] = 10.9                     # la vela de hoy acaba tocando el stop
    assert cartera.revisar_ordenes(cv, {"SAN.MC": velas}, costes.Tarifa())


def test_ronda2_calculos():
    from datetime import datetime

    import pandas as pd

    from bolsa import alertas, ficha, fondos, importador, libertad

    # Importador: «Precio actual» o «de mercado» nunca es el precio de compra.
    assert importador.detectar(["Valor", "Títulos", "Precio actual", "Precio medio de adquisición (EUR)"])[
        "precio_medio"] == "Precio medio de adquisición (EUR)"
    assert "precio_medio" not in importador.detectar(["Nombre", "Cantidad", "Precio de mercado", "Coste total"])
    # Aviso creado a las 15:00: lo que bajó a las 09:00 no cuenta.
    a = {"id": 1, "ticker": "X", "tipo": "baja", "precio": 200.0, "creada": "2026-10-15",
         "creada_hora": "2026-10-15T15:00"}
    idx = pd.to_datetime(["2026-10-15 09:00", "2026-10-15 15:30"])
    df = pd.DataFrame({"Low": [199.0, 204.0], "High": [206.0, 207.0], "Close": [205.0, 206.0]}, index=idx)
    assert alertas.ultimo_cruce(a, df) is None
    # Fondos: Sanofi (SAN.PA) no es Santander (SAN.MC); los % sobre todo tu dinero.
    comp = {"F": {"top": [{"simbolo": "SAN.PA", "nombre": "Sanofi", "peso": 0.05}]}}
    r = fondos.exposicion({"SAN.MC": 1000}, {"F": 1000}, comp, {"SAN.MC": "Banco Santander"}, total=4000)
    assert r["solapes"] == [] and abs(r["empresas"][0]["peso"] - 0.25) < 1e-9
    # Ficha: una variación de 1 año que no existe (NaN) no cuenta como suspenso.
    f = ficha.ficha({"returnOnEquity": 0.2, "profitMargins": 0.2}, 10.0, float("nan"))
    assert f["Pasado"]["puntos"] == 6.0
    # FIRE mes a mes: 2.000 €/mes, de 0 con 1.000 €/mes al 4 % → 28 años (no 29).
    assert libertad.calcular(2000, 0, 1000, 0.04)["anos"] == 28
    assert datetime  # noqa: B018


def test_renta_por_fechas_aunque_se_apunte_tarde():
    from bolsa import renta

    venta = {"fecha": "2026-03-01", "tipo": "Venta", "ticker": "X.MC", "acciones": 10, "precio": 9.0, "gastos": 0.0,
             "resultado": -100.0, "motivo": "x", "fx": 1.0}
    compras = [{"fecha": f, "tipo": "Compra", "ticker": "X.MC", "acciones": 10, "precio": 10.0, "gastos": 0.0,
                "resultado": None, "motivo": "x", "fx": 1.0} for f in ("2025-01-01", "2026-02-15")]
    hist = [compras[0], venta, compras[1]]        # la compra del 15/02 se apuntó DESPUÉS de la venta del 01/03
    assert renta.ventas_del_ano(hist, 2026)[0]["aplazada"] is True
