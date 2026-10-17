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

import ui_comun

from bolsa import cartera, costes, datos, noticias
from bolsa import plan as plan_mod

APP = str(Path(__file__).resolve().parent.parent / "app.py")
SESIONES = {"10y": 2500, "5y": 1260, "max": 5000, "1y": 250, "6mo": 126, "1mo": 21, "5d": 5}

PAGINAS = ["pagina_hoy", "pagina_plan", "pagina_chat", "pagina_analizar", "pagina_radar", "pagina_carteras",
           "pagina_noticias", "pagina_resumen", "pagina_bankinter", "pagina_seguimiento", "pagina_cartera_virtual",
           "pagina_acierto",
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
    en_5_dias = (datetime.now(timezone.utc) + pd.Timedelta(days=5)).timestamp()
    monkeypatch.setattr(datos, "fundamentales", lambda t: {"targetMeanPrice": 150.0, "numberOfAnalystOpinions": 12,
                                                          "recommendationKey": "buy", "currency": "EUR",
                                                          "trailingPE": 14.0, "forwardPE": 12.0, "priceToBook": 1.2,
                                                          "returnOnEquity": 0.14, "profitMargins": 0.2,
                                                          "earningsGrowth": 0.08, "revenueGrowth": 0.06,
                                                          "dividendYield": 3.5, "payoutRatio": 0.5,
                                                          "earningsTimestamp": en_5_dias})
    monkeypatch.setattr(datos, "composicion_fondo", lambda t: {
        "top": [{"simbolo": "SAN.MC", "nombre": "Banco Santander", "peso": 0.02},
                {"simbolo": "AAPL", "nombre": "Apple Inc", "peso": 0.05}],
        "sectores": {"technology": 0.25, "financial_services": 0.15}} if t == "IWDA.AS" else {})
    monkeypatch.setattr(datos, "noticias_yahoo", lambda t: [])
    monkeypatch.setattr(datos, "analistas", lambda t: {
        "recuento": {"strongBuy": 5, "buy": 10, "hold": 3, "sell": 1, "strongSell": 0},
        "recuento_antes": {"strongBuy": 5, "buy": 9, "hold": 4, "sell": 1, "strongSell": 0},
        "objetivos": {"mean": 160.0, "median": 158.0, "low": 120.0, "high": 190.0}, "revision_beneficios": 0.02})
    monkeypatch.setattr(datos, "dividendos", lambda t: pd.Series(dtype=float))
    monkeypatch.setattr(datos, "dividendos_varios", lambda ts, periodo="5y": {})
    monkeypatch.setattr(datos, "buscar_simbolo", lambda q: None)
    monkeypatch.setattr(datos, "precios_recientes",
                        lambda ts: {t: datos.ultimo_precio(historico_falso(t, "5d")) for t in ts})
    titular = noticias.Noticia("El BCE baja los tipos de interés", "x", "Prueba", datetime.now(timezone.utc))
    monkeypatch.setattr(noticias, "descargar",
                        lambda *a, extra=None, **k: (noticias.combinar([titular] + list(extra or []), 72), []))
    monkeypatch.setattr(st, "Page", lambda fn, **kw: fn)
    monkeypatch.setattr(st, "switch_page", lambda p: None)
    st.cache_data.clear()
    ui_comun.olvidar_datos_al_dia()
    yield


def abrir(pagina: str, movil: bool = False, datos_usuario: dict | None = None, secretos: dict | None = None,
          estado: dict | None = None):
    def navegacion(paginas, **_k):
        todas = [p for grupo in paginas.values() for p in grupo]
        return SimpleNamespace(run=next(p for p in todas if p.__name__ == pagina))

    st.navigation = navegacion
    at = AppTest.from_file(APP, default_timeout=120)
    if datos_usuario is not None:
        at.session_state["_datos"] = datos_usuario
    for k, v in (secretos or {}).items():
        at.secrets[k] = v
    for k, v in (estado or {}).items():
        at.session_state[k] = v
    at.run()
    if movil and at.sidebar.toggle:
        at.sidebar.toggle[0].set_value(True).run()
    return at


def abrir_pestana(at, clave: str, nombre: str):
    """Las pestañas solo calculan la abierta: abre otra (como al tocarla)."""
    at.session_state[clave] = nombre
    return at.run()


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


@pytest.mark.parametrize("pagina", ["pagina_hoy", "pagina_resumen", "pagina_bankinter", "pagina_seguimiento",
                                    "pagina_cartera_virtual",
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


def _datos_seguimiento() -> dict:
    cr = cartera_de_prueba()
    cartera.vender(cr, "SAN.MC", 1000, 14.0, costes.Tarifa(), "2026-03-02")
    return {"cartera_real": cr,
            "alertas": [{"id": 1, "ticker": "IDR.MC", "nombre": "Indra", "tipo": "baja", "precio": 1e6, "nota": "",
                         "creada": "2026-01-02", "disparada": None, "precio_disparo": None}],
            "aportacion": {"importe": 300.0, "dia": 1, "hechas": []},
            "diario": [{"id": 1, "fecha": "2026-01-02", "ticker": "IDR.MC", "nombre": "Indra", "accion": "Compra",
                        "precio": 100.0, "motivo": "Defensa", "revisar": "2026-02-02", "revisada": None,
                        "leccion": ""}]}


def test_seguimiento_con_datos_y_pendientes_en_hoy():
    at = abrir("pagina_hoy", datos_usuario=_datos_seguimiento())
    sin_fallos(at)
    textos = " ".join(m.value for m in at.markdown)
    assert "Tus pendientes" in textos and "Toca tu aportación mensual" in textos
    assert "ha bajado de" in textos               # el aviso a 1.000.000 € salta con cualquier precio
    assert at.session_state["_datos"]["cartera_real"]["alertas"][0]["disparada"]


def test_seguimiento_crear_aviso_aportacion_y_apunte():
    at = abrir("pagina_seguimiento", datos_usuario=_datos_seguimiento())
    sin_fallos(at)
    # Aviso nuevo de subida muy por encima del precio: se crea y queda vigilando.
    abrir_pestana(at, "seg_pestana", "🔔 Avisos de precio")
    at.radio(key="alerta_origen").set_value("De mi cartera").run()
    formulario = [r for r in at.radio if r.label == "Avísame si…"][0]
    formulario.set_value("sube")
    [n for n in at.number_input if n.label == "Precio"][0].set_value(99_999.0)
    [b for b in at.button if "Crear aviso" in b.label][0].click().run()
    sin_fallos(at)
    assert len(at.session_state["_datos"]["cartera_real"]["alertas"]) == 2
    # Aportación del mes: reparto y marcarla como hecha.
    abrir_pestana(at, "seg_pestana", "💶 Aportación mensual")
    assert any("A dónde llevarla" in s.value for s in at.subheader)
    [b for b in at.button if "Ya he hecho la aportación" in b.label][0].click().run()
    assert len(at.session_state["_datos"]["cartera_real"]["aportacion"]["hechas"]) == 1
    # Diario: el apunte vencido se puede revisar.
    abrir_pestana(at, "seg_pestana", "📓 Diario")
    [b for b in at.button if b.label == "Marcar como revisado"][0].click().run()
    assert at.session_state["_datos"]["cartera_real"]["diario"][0]["revisada"]
    # Renta: la venta de Santander aparece con su resultado y se puede descargar.
    abrir_pestana(at, "seg_pestana", "🧾 Renta")
    assert any("Ganancias y pérdidas patrimoniales" in s.value for s in at.subheader)
    sin_fallos(at)


def test_variaciones_negativas_salen_en_rojo():
    """st.metric decide rojo/flecha abajo por el «-» inicial: un «−» tipográfico saldría en verde."""
    from ui_comun import pct

    assert pct(-0.28).startswith("-") and pct(1.08).startswith("+")


def test_finnhub_conectado(monkeypatch):
    from bolsa import finnhub

    monkeypatch.setattr(finnhub, "comprobar", lambda clave: (True, "Finnhub conectado: prueba."))
    monkeypatch.setattr(finnhub, "cotizacion", lambda t, clave: {
        "precio": 231.5, "variacion": 2.5, "variacion_pct": 1.09, "maximo": 232.0, "minimo": 228.0,
        "apertura": 229.0, "anterior": 229.0, "hora": datetime(2026, 10, 15, 20, 0), "tiempo_real": True})
    monkeypatch.setattr(finnhub, "noticias_mercado", lambda clave: [{
        "titulo": "Fed holds rates steady", "enlace": "https://x", "fuente": "Finnhub · Reuters",
        "fecha": datetime.now(timezone.utc), "resumen": ""}])
    monkeypatch.setattr(finnhub, "noticias_empresa", lambda t, clave: [])
    secretos = {"finnhub": {"api_key": "clave-de-prueba"}}
    at = abrir("pagina_noticias", secretos=secretos)
    sin_fallos(at)
    assert any("Finnhub conectado" in c.value for c in at.sidebar.caption)
    assert any("Fed holds rates" in e.label for e in at.expander)
    from bolsa import horario

    # Con la bolsa de EEUU abierta (y la vela de hoy), el precio de AAPL llega en tiempo real por Finnhub.
    monkeypatch.setattr(horario, "estado_mercado", lambda t, ahora=None: {"abierto": True, "texto": "", "apertura": None})
    hoy = pd.Timestamp.now(tz="Europe/Madrid").date()
    monkeypatch.setattr(datos, "precios_recientes", lambda ts: {
        t: {"precio": 230.0, "anterior": 229.0, "fecha": hoy, "variacion_pct": 0.44} for t in ts})
    at = abrir("pagina_analizar", secretos=secretos, estado={"analizar_ticker": "AAPL"})
    sin_fallos(at)
    assert any("Ahora mismo (tiempo real)" in m.value and "231,50" in m.value for m in at.markdown)


def test_vigilar_sin_stop_desde_mi_cartera():
    at = abrir("pagina_bankinter", datos_usuario={"cartera_real": cartera_de_prueba()})
    sin_fallos(at)
    boton = [b for b in at.button if "Vigilarlas sin stop-loss" in b.label]
    assert boton, "con acciones sin stop-loss debe ofrecer vigilarlas"
    boton[0].click().run()
    sin_fallos(at)
    d = at.session_state["_datos"]
    acciones = [t for t in ("SAN.MC", "IDR.MC") if t in d["cartera_real"]["posiciones"]]
    assert all(d["cartera_real"]["posiciones"][t]["sin_stop"] for t in acciones)
    assert all(d["cartera_real"]["posiciones"][t]["alarma"] for t in acciones)
    avisos = {a["ticker"] for a in d["cartera_real"]["alertas"]}
    assert set(acciones) <= avisos
    assert not [b for b in at.button if "Vigilarlas sin stop-loss" in b.label]   # ya no lo vuelve a pedir
    # Desmarcar una: deja de vigilarla y borra su aviso.
    at.toggle(key="ss_SAN.MC").set_value(False).run()
    d = at.session_state["_datos"]
    assert not d["cartera_real"]["posiciones"]["SAN.MC"].get("sin_stop")
    assert "SAN.MC" not in {a["ticker"] for a in d["cartera_real"]["alertas"]}


def test_cambiar_el_nivel_de_alarma_de_una_posicion():
    at = abrir("pagina_bankinter", datos_usuario={"cartera_real": cartera_de_prueba()})
    at.toggle(key="ss_SAN.MC").set_value(True).run()
    sin_fallos(at)
    at.number_input(key="alarma_SAN.MC").set_value(1.0).run()
    at.button(key="gss_SAN.MC").click().run()
    sin_fallos(at)
    pos = at.session_state["_datos"]["cartera_real"]["posiciones"]["SAN.MC"]
    assert pos["sin_stop"] and pos["alarma"] == 1.0
    assert [a["precio"] for a in at.session_state["_datos"]["cartera_real"]["alertas"] if a["ticker"] == "SAN.MC"] == [1.0]


def _familia() -> dict:
    """Mi cuenta y la de mi madre: el mismo Santander a precios distintos, y perfiles distintos."""
    mia = cartera.nueva(None)
    cartera.comprar(mia, "SAN.MC", 2500, 12.46, costes.Tarifa(), "2025-06-02")
    mia["otros_ahorros"] = 1000.0
    madre = cartera.nueva(None)
    cartera.comprar(madre, "SAN.MC", 1000, 14.20, costes.Tarifa(), "2026-02-10")
    cartera.comprar(madre, "ITX.MC", 100, 50.0, costes.Tarifa(), "2026-02-10")
    madre["aportacion"] = {"importe": 200.0, "dia": 1, "hechas": []}
    return {"cuentas": {"Yo": mia, "Mamá": madre}, "cuenta_activa": "Yo"}


def test_cada_cuenta_se_asesora_por_separado():
    at = abrir("pagina_bankinter", datos_usuario=_familia())
    sin_fallos(at)
    tabla = at.dataframe[0].value
    assert tabla["Títulos"].tolist() == [2500]                 # solo la mía, sin sumar la de mi madre
    assert any(m.label == "Valor de «Yo»" for m in at.metric)
    [s for s in at.sidebar.selectbox if s.label == "👤 Cuenta"][0].set_value("Mamá").run()
    sin_fallos(at)
    tabla = at.dataframe[0].value
    san = tabla[tabla["Activo"].str.contains("Santander")].iloc[0]
    assert san["Títulos"] == 1000 and san["Precio compra"] == 14.2
    assert at.session_state["_datos"]["cuenta_activa"] == "Mamá"


def test_hoy_y_seguimiento_son_de_la_cuenta_activa():
    datos = _familia()
    at = abrir("pagina_hoy", datos_usuario=datos)
    sin_fallos(at)
    assert not any("aportación mensual" in m.value for m in at.markdown)       # la aportación es de mi madre
    [s for s in at.sidebar.selectbox if s.label == "👤 Cuenta"][0].set_value("Mamá").run()
    sin_fallos(at)
    assert any("Toca tu aportación mensual de 200" in m.value for m in at.markdown)


def test_crear_una_cuenta_nueva():
    at = abrir("pagina_bankinter", datos_usuario={"cartera_real": cartera_de_prueba()})
    sin_fallos(at)
    at.text_input(key="cta_nueva").set_value("Mamá").run()
    at.button(key="cta_anadir").click().run()
    sin_fallos(at)
    d = at.session_state["_datos"]
    assert list(d["cuentas"]) == ["Mi cuenta", "Mamá"]
    assert d["cuenta_activa"] == "Mamá" and d["cartera_real"]["posiciones"] == {}     # la nueva empieza vacía
    assert d["cuentas"]["Mi cuenta"]["posiciones"]["SAN.MC"]["acciones"] == 2500   # la mía sigue igual


def test_renombrar_y_borrar_cuenta_desde_la_pantalla():
    at = abrir("pagina_bankinter", datos_usuario=_familia())
    at.selectbox(key="cta_cual").set_value("Mamá").run()
    at.text_input(key="cta_nombre").set_value("Cuenta ahorro").run()
    at.button(key="cta_renombrar").click().run()
    sin_fallos(at)
    assert list(at.session_state["_datos"]["cuentas"]) == ["Yo", "Cuenta ahorro"]
    at.selectbox(key="cta_cual").set_value("Cuenta ahorro").run()
    at.checkbox(key="cta_seguro").check().run()
    at.button(key="cta_borrar").click().run()
    sin_fallos(at)
    d = at.session_state["_datos"]
    assert list(d["cuentas"]) == ["Yo"] and d["cartera_real"]["posiciones"]["SAN.MC"]["acciones"] == 2500


@pytest.mark.parametrize("objetivo, intereses, titulo", [
    ("operacion", ["Acciones españolas", "Divisas", "Oro", "Criptomonedas"], "Tu operación"),
    ("rentas", [], "Tu plan de rentas"),
    ("proteger", [], "Tu plan para proteger"),
    ("crecer", ["Fondos indexados y ETF", "Acciones españolas", "Oro"], "Reparto propuesto"),
])
def test_mi_plan_segun_el_objetivo(objetivo, intereses, titulo):
    at = abrir("pagina_plan")
    sin_fallos(at)
    [r for r in at.radio if r.label.startswith("1️⃣")][0].set_value(objetivo)
    if intereses:
        [m for m in at.multiselect if m.label.startswith("3️⃣")][0].set_value(intereses)
    [b for b in at.button if b.label == "Ver mi plan para hoy"][0].click().run()
    sin_fallos(at)
    assert any(titulo in s.value for s in at.subheader)
    assert any("El mercado hoy" in m.value for m in at.markdown)
    guardado = at.session_state["_datos"]["cartera_real"]["perfil_inversor"]
    assert guardado["objetivo"] == objetivo
    assert guardado["intereses"] == (intereses or plan_mod.INTERESES_POR_DEFECTO[objetivo])


def test_mi_plan_es_de_cada_cuenta():
    datos = _familia()
    datos["cuentas"]["Mamá"]["perfil_inversor"] = {
        "objetivo": "rentas", "importe": 20_000.0, "mensual": 0.0, "intereses": ["Acciones españolas"],
        "plazo": "1-3 meses", "perdida_max": 5, "horizonte": 10, "reaccion": "Me preocuparía, pero esperaría",
        "experiencia": "Ninguna", "colchon": True, "deudas": False}
    at = abrir("pagina_plan", datos_usuario=datos)
    assert not any("Tu plan de rentas" in s.value for s in at.subheader)     # yo aún no he hecho el test
    [s for s in at.sidebar.selectbox if s.label == "👤 Cuenta"][0].set_value("Mamá").run()
    sin_fallos(at)
    assert any("Tu plan de rentas" in s.value for s in at.subheader)


def test_radar_con_precio_de_ahora_o_de_cierre():
    at = abrir("pagina_radar")
    sin_fallos(at)
    tabla = at.dataframe[0].value
    assert {"Precio", "Hoy (%)", "Cotización"} <= set(tabla.columns)
    assert tabla["Precio"].str.endswith("€").all()
    assert tabla["Cotización"].str.contains("ahora|cierre|tiempo real").all()


def test_noticias_dicen_cuando_se_leyeron_y_hoy_usa_las_de_ahora():
    at = abrir("pagina_noticias")
    sin_fallos(at)
    assert any("Fuentes leídas a las" in m.value for m in at.markdown)
    at = abrir("pagina_hoy")
    sin_fallos(at)
    assert any("El BCE baja los tipos" in m.value for m in at.markdown)     # la noticia de ahora, no la del informe


def test_diagnostico_cambia_con_el_perfil():
    at = abrir("pagina_bankinter", datos_usuario={"cartera_real": cartera_de_prueba()},
               estado={"mc_pestana": "🩺 Diagnóstico"})
    sin_fallos(at)
    perfil_sel = [s for s in at.selectbox if s.label == "Tu perfil"][0]

    def lectura():
        limites = [c.value for c in at.caption if c.value.startswith("📏")]
        rojos = [e.label for e in at.expander if e.label.startswith("🔴")]
        return limites, rojos

    perfil_sel.set_value("Conservador").run()
    sin_fallos(at)
    lim_c, rojos_c = lectura()
    [s for s in at.selectbox if s.label == "Tu perfil"][0].set_value("Dinámico").run()
    sin_fallos(at)
    lim_d, rojos_d = lectura()
    assert "conservador" in lim_c[0] and "máximo 5 % por empresa" in lim_c[0]
    assert "dinámico" in lim_d[0] and "máximo 20 % por empresa" in lim_d[0]
    assert len(rojos_c) > len(rojos_d)


def test_tabla_de_mi_cartera_con_todas_las_columnas():
    at = abrir("pagina_bankinter", datos_usuario={"cartera_real": cartera_de_prueba()})
    sin_fallos(at)
    tabla = at.dataframe[0].value
    for col in ("Precio actual", "Hoy (%)", "Precio compra", "Títulos", "Invertido (€)", "Valor (€)", "Ganancia (€)",
                "Ganancia (%)", "Peso (%)", "Protección"):
        assert col in tabla.columns, col
    assert abs(tabla["Peso (%)"].sum() - 100) < 0.5
    san = tabla[tabla["Activo"].str.contains("Santander")].iloc[0]
    assert san["Precio compra"] == 12.46 and san["Títulos"] == 2500
    assert abs(san["Ganancia (€)"] - (san["Valor (€)"] - san["Invertido (€)"])) < 0.05
    assert any(m.label == "Hoy" for m in at.metric)
    # En el móvil también se ven precio actual y de compra (la tabla se desliza de lado).
    at = abrir("pagina_bankinter", movil=True, datos_usuario={"cartera_real": cartera_de_prueba()})
    assert {"Precio actual", "Precio compra", "Hoy (%)", "Ganancia (€)"} <= set(at.dataframe[0].value.columns)


def test_hoy_dice_que_hacer_con_cada_accion_y_puede_centrarse_en_mi_cartera():
    at = abrir("pagina_hoy", datos_usuario={"cartera_real": cartera_de_prueba()})
    sin_fallos(at)
    textos = " ".join(m.value for m in at.markdown)
    assert "Qué hacer con cada acción tuya" in textos
    assert "Te recomiendo:" in textos and "Tienes 2.500 acciones compradas a 12,46" in textos
    assert any("analistas" in c.value for c in at.caption)                    # el consenso de los brókers
    assert any("Fiabilidad del consenso" in m.value for m in at.markdown)
    assert any("se actualizan solos cada minuto" in c.value for c in at.caption)
    assert not any("Ideas del día" in s.value for s in at.subheader)        # «solo mi cartera», encendido
    [x for x in at.toggle if x.label == "🎯 Solo lo de mi cartera"][0].set_value(False).run()
    sin_fallos(at)
    assert any("Ideas del día" in s.value for s in at.subheader)
    assert at.session_state["_datos"]["cartera_real"]["solo_mi_cartera"] is False


def test_el_stop_de_una_cuenta_no_aparece_en_otra_con_la_misma_accion():
    mia, mama = cartera_de_prueba(), cartera_de_prueba()
    mia["posiciones"]["SAN.MC"]["stop"] = 11.0
    d = {"cuentas": {"Mi cuenta": mia, "Mamá": mama}, "cuenta_activa": "Mi cuenta"}
    at = abrir("pagina_bankinter", datos_usuario=d)
    sin_fallos(at)
    assert at.number_input(key="stop_SAN.MC").value == 11.0
    [s for s in at.sidebar.selectbox if s.label == "👤 Cuenta"][0].set_value("Mamá").run()
    sin_fallos(at)
    assert at.number_input(key="stop_SAN.MC").value == 0.0            # el de tu madre, no el tuyo


def test_diagnostico_con_solo_fondos_no_se_rompe():
    cr = cartera.nueva(None)
    cartera.comprar(cr, "IWDA.AS", 300, 90.0, costes.Tarifa(), "2026-09-01", None, nota="prueba", fx=1.0)
    at = abrir("pagina_bankinter", datos_usuario={"cartera_real": cr})
    sin_fallos(at)


def test_si_no_cargan_tus_datos_no_se_guarda_nada(monkeypatch):
    from bolsa import almacen

    guardados = []
    monkeypatch.setattr(almacen.Almacen, "cargar_con_version",
                        lambda self: (_ for _ in ()).throw(RuntimeError("GitHub caído")))
    monkeypatch.setattr(almacen.Almacen, "guardar", lambda self, d: guardados.append(d) or "v")
    at = abrir("pagina_seguimiento")
    sin_fallos(at)
    assert any("no se han podido cargar tus datos" in e.value.lower() for e in at.error)
    assert [b for b in at.button if "Reintentar" in b.label]               # se puede reintentar
    assert guardados == []                     # guardar ahora borraría lo que tienes en la nube


def test_venta_parcial():
    at = abrir("pagina_bankinter", datos_usuario={"cartera_real": cartera_de_prueba()})
    sin_fallos(at)
    at.number_input(key="nv_SAN.MC").set_value(1000).run()
    at.button(key="vend_SAN.MC").click().run()
    sin_fallos(at)
    assert at.session_state["_datos"]["cartera_real"]["posiciones"]["SAN.MC"]["acciones"] == 1500


def test_cartera_virtual_con_la_misma_tabla_que_mi_cartera():
    cv = cartera.nueva(10_000.0)
    cartera.comprar(cv, "SAN.MC", 300, 12.0, costes.Tarifa(), "2026-09-01", 11.0, nota="prueba", fx=1.0)
    cartera.comprar(cv, "IDR.MC", 20, 60.0, costes.Tarifa(), "2026-09-01", None, nota="prueba", fx=1.0)
    at = abrir("pagina_cartera_virtual", datos_usuario={"cartera_virtual": cv})
    sin_fallos(at)
    tabla = at.dataframe[0].value
    for col in ("Precio actual", "Hoy (%)", "Precio compra", "Títulos", "Invertido (€)", "Valor (€)", "Ganancia (€)",
                "Ganancia (%)", "Peso (%)", "Protección", "Precio de"):
        assert col in tabla.columns, col
    assert abs(tabla["Peso (%)"].sum() - 100) < 0.5
    assert "stop 11,00" in tabla["Protección"].tolist()
    assert any(m.label == "Hoy" for m in at.metric)
    assert any("Qué haría el asesor" in e.label for e in at.expander)


def test_rentabilidad_por_periodos_en_mi_cartera():
    at = abrir("pagina_bankinter", datos_usuario={"cartera_real": cartera_de_prueba()},
               estado={"mc_pestana": "📈 Rentabilidad"})
    sin_fallos(at)
    assert any(t.label == "📈 Rentabilidad" for t in at.tabs)
    tablas = [df.value for df in at.dataframe if "Periodo" in df.value.columns]
    assert tablas and {"Tu cartera", "IBEX 35", "Fondo mundial"} <= set(tablas[0].columns)
    assert {"Hoy", "1 mes", "1 año"} <= set(tablas[0]["Periodo"])


def test_dentro_de_los_fondos_avisa_si_tienes_la_misma_empresa_dos_veces():
    at = abrir("pagina_bankinter", datos_usuario={"cartera_real": cartera_de_prueba()},
               estado={"mc_pestana": "🩺 Diagnóstico"})
    sin_fallos(at)
    assert any("Qué hay dentro de tus fondos" in e.label for e in at.expander)
    assert any("Banco Santander" in w.value and "también dentro de" in w.value for w in at.warning)


def test_calendario_en_hoy_y_en_seguimiento():
    at = abrir("pagina_hoy", datos_usuario={"cartera_real": cartera_de_prueba()})
    sin_fallos(at)
    assert any("Próximos 14 días" in m.value for m in at.markdown)
    assert any("presenta resultados en 5 días" in m.value for m in at.markdown)
    at = abrir("pagina_seguimiento", datos_usuario={"cartera_real": cartera_de_prueba()},
               estado={"seg_pestana": "📅 Calendario"})
    sin_fallos(at)
    assert any("Presenta resultados" in str(df.value.values) for df in at.dataframe)


def test_lista_de_seguimiento():
    at = abrir("pagina_seguimiento")
    sin_fallos(at)
    at.button(key="lista_anadir").click().run()
    sin_fallos(at)
    lista = at.session_state["_datos"]["cartera_real"]["lista_seguimiento"]
    assert len(lista) == 1 and lista[0]["precio_inicial"]
    tabla = [df.value for df in at.dataframe if "Desde que la añadiste (%)" in df.value.columns][0]
    assert tabla["Precio"].iloc[0] > 0
    at.button(key="lista_aviso").click().run()
    sin_fallos(at)
    assert at.session_state["_datos"]["cartera_real"]["alertas"][0]["tipo"] == "baja"


def test_ficha_de_cinco_ejes_en_analizar():
    at = abrir("pagina_analizar")
    sin_fallos(at)
    assert any("Ficha de la empresa" in h.value for h in at.subheader)
    assert any(e.label.startswith("Valoración:") for e in at.expander)


def test_calculadora_de_libertad_financiera():
    at = abrir("pagina_calculadoras", datos_usuario={"cartera_real": cartera_de_prueba()},
               estado={"calc_pestana": "🏖️ Libertad financiera"})
    sin_fallos(at)
    assert any(m.label == "Te faltan" for m in at.metric)
    assert any(m.label == "Necesitas" and m.value == "600.000,00 €" for m in at.metric)    # 2.000 € x 12 / 4 %


def test_modo_privado_oculta_tus_importes():
    at = abrir("pagina_bankinter", datos_usuario={"cartera_real": cartera_de_prueba()}, estado={"_privado": True})
    sin_fallos(at)
    valor = [m for m in at.metric if m.label.startswith("Valor de")][0]
    assert "•••" in valor.value
    tabla = at.dataframe[0].value
    assert "Valor (€)" not in tabla.columns and "Precio actual" in tabla.columns


class _Enviar:
    """Como en el bróker: «Continuar» enseña el resumen con los costes y «Confirmar orden» la envía."""

    def __init__(self, at):
        self.at = at

    def click(self):
        [b for b in self.at.button if b.label == "CONTINUAR"][0].click().run()
        return [b for b in self.at.button if b.label == "CONFIRMAR ORDEN"][0].click()


def _boton_enviar(at):
    return _Enviar(at)


def test_virtual_compra_totalenergies_con_limite_por_debajo_del_stop_propuesto():
    at = abrir("pagina_cartera_virtual", estado={"v_defecto": "TTE.PA"})
    sin_fallos(at)
    assert [s.value for s in at.selectbox if s.label == "Valor"][0] == "TTE.PA"
    stop = at.number_input(key="v_slc_TTE.PA").value
    at.number_input(key="v_lim_TTE.PA_compra").set_value(round(stop * 0.95, 3)).run()   # compra por debajo del stop
    sin_fallos(at)
    assert any("lo bajo a" in i.value for i in at.info)
    _boton_enviar(at).click().run()
    sin_fallos(at)
    assert not at.error
    cv = at.session_state["_datos"]["cartera_virtual"]
    compras = [h for h in cv["historial"] if h["tipo"] == "Compra" and h["ticker"] == "TTE.PA"]
    assert cv.get("ordenes") or compras                     # la orden se ha aceptado (y, si toca, ejecutado)
    for o in cv.get("ordenes", []):
        assert o["stop"] < o["limite"]


def test_virtual_opera_aunque_falle_la_cotizacion_intradia(monkeypatch):
    # Como en la realidad cuando Yahoo limita: las descargas devuelven tablas vacías.
    monkeypatch.setattr(datos, "intradia", lambda *_a, **_k: pd.DataFrame())
    monkeypatch.setattr(datos, "diario_sin_ajustar", lambda *_a, **_k: pd.DataFrame())
    at = abrir("pagina_cartera_virtual", estado={"v_defecto": "TTE.PA"})
    sin_fallos(at)
    assert not [e for e in at.error if "cotización" in e.value]
    _boton_enviar(at).click().run()
    sin_fallos(at)
    cv = at.session_state["_datos"]["cartera_virtual"]
    assert "TTE.PA" in cv["posiciones"] or cv.get("ordenes")


def test_las_pestanas_solo_calculan_la_abierta():
    at = abrir("pagina_bankinter", datos_usuario={"cartera_real": cartera_de_prueba()})
    sin_fallos(at)
    assert not any("Diagnóstico de tu cartera" in h.value for h in at.subheader)      # cerrada: no se calcula
    abrir_pestana(at, "mc_pestana", "🩺 Diagnóstico")
    sin_fallos(at)
    assert any("Diagnóstico de tu cartera" in h.value for h in at.subheader)


def test_ayuda_tactil_en_la_pagina():
    from ui_comun import AYUDAS_TACTILES

    assert "blur()" in AYUDAS_TACTILES and "touchstart" in AYUDAS_TACTILES and "http" not in AYUDAS_TACTILES


def test_ver_solo_un_activo_en_mi_cartera():
    at = abrir("pagina_bankinter", datos_usuario={"cartera_real": cartera_de_prueba()})
    sin_fallos(at)
    at.selectbox(key="mc_activo").set_value("IDR.MC").run()
    sin_fallos(at)
    etiquetas = {m.label: m.value for m in at.metric}
    assert "Valor de Indra" in etiquetas or any(k.startswith("Valor de Indra") for k in etiquetas)
    assert {"Ganancia o pérdida (sin vender)", "Precio de compra", "Precio actual", "Títulos"} <= set(etiquetas)
    assert etiquetas["Precio de compra"].startswith("60,80")
    assert any("Cómo ha ido el precio" in m.value for m in at.markdown)
    at.selectbox(key="mc_activo").set_value("Toda la cartera").run()
    sin_fallos(at)
    assert any(m.label == "Valor de tu cartera" for m in at.metric)


def test_ver_solo_un_activo_en_la_cartera_virtual():
    cv = cartera.nueva(10_000.0)
    cartera.comprar(cv, "IDR.MC", 20, 60.0, costes.Tarifa(), "2026-09-01", None, nota="prueba", fx=1.0)
    cartera.comprar(cv, "SAN.MC", 300, 12.0, costes.Tarifa(), "2026-09-01", 11.0, nota="prueba", fx=1.0)
    at = abrir("pagina_cartera_virtual", datos_usuario={"cartera_virtual": cv})
    sin_fallos(at)
    at.selectbox(key="cv_activo").set_value("IDR.MC").run()
    sin_fallos(at)
    etiquetas = {m.label: m.value for m in at.metric}
    assert any(k.startswith("Valor de Indra") for k in etiquetas)
    assert etiquetas["Precio de compra"].startswith("60,00") and etiquetas["Títulos"] == "20"
    assert any("Cómo ha ido el precio" in m.value for m in at.markdown)


def test_orden_virtual_como_en_el_broker_continuar_modificar_y_vender():
    cv = cartera.nueva(10_000.0)
    cartera.comprar(cv, "SAN.MC", 300, 12.0, costes.Tarifa(), "2026-09-01", None, nota="prueba", fx=1.0)
    at = abrir("pagina_cartera_virtual", datos_usuario={"cartera_virtual": cv}, estado={"v_defecto": "SAN.MC"})
    sin_fallos(at)
    assert any("ORDEN DE COMPRA" in m.value for m in at.markdown)
    assert {"TIPO DE ORDEN", "PRECIO", "VALIDEZ"} <= {s.label for s in at.selectbox}
    [b for b in at.button if b.label == "CONTINUAR"][0].click().run()
    assert any("CONFIRMA TU ORDEN DE COMPRA" in m.value for m in at.markdown)
    assert any("Total aproximado" in m.value for m in at.markdown)
    [b for b in at.button if b.label == "← MODIFICAR"][0].click().run()            # vuelve al formulario
    assert any(b.label == "CONTINUAR" for b in at.button)
    # Venta de 100 a mercado.
    at.segmented_control(key="v_sentido").set_value("Vender").run()
    sin_fallos(at)
    assert any("ORDEN DE VENTA" in m.value for m in at.markdown)
    at.selectbox(key="v_precio_SAN.MC_venta").set_value("A mercado").run()
    at.number_input(key="v_n_SAN.MC_v").set_value(100).run()
    [b for b in at.button if b.label == "CONTINUAR"][0].click().run()
    assert any("Recibirías unos" in m.value for m in at.markdown)
    [b for b in at.button if b.label == "CONFIRMAR ORDEN"][0].click().run()
    sin_fallos(at)
    cv = at.session_state["_datos"]["cartera_virtual"]
    vendido = sum(h["acciones"] for h in cv["historial"] if h["tipo"] == "Venta")
    assert vendido == 100 or any(o["sentido"] == "venta" for o in cv.get("ordenes", []))


def test_si_cambias_la_orden_con_el_resumen_abierto_se_vuelve_al_formulario():
    cv = cartera.nueva(10_000.0)
    at = abrir("pagina_cartera_virtual", datos_usuario={"cartera_virtual": cv}, estado={"v_defecto": "SAN.MC"})
    [b for b in at.button if b.label == "CONTINUAR"][0].click().run()
    assert any(b.label == "CONFIRMAR ORDEN" for b in at.button)
    at.number_input(key="v_n_SAN.MC_c").set_value(3).run()                     # cambio los títulos
    assert not any(b.label == "CONFIRMAR ORDEN" for b in at.button)            # el resumen viejo ya no vale
    [b for b in at.button if b.label == "CONTINUAR"][0].click().run()
    assert any("3 títulos" in m.value for m in at.markdown)


def test_modo_privado_tapa_los_importes_de_los_textos():
    import ui_comun

    assert ui_comun.ocultar("perderías unos 100.528 € y ahorras 1.120,50 €") == \
        "perderías unos 100.528 € y ahorras 1.120,50 €"                 # sin modo privado, igual
    st.session_state["_privado"] = True
    try:
        assert ui_comun.ocultar("perderías unos 100.528 € y −1.380 € hoy") == "perderías unos ••• € y ••• € hoy"
    finally:
        st.session_state.pop("_privado", None)
    at = abrir("pagina_bankinter", datos_usuario={"cartera_real": cartera_de_prueba()},
               estado={"_privado": True, "mc_pestana": "🩺 Diagnóstico"})
    sin_fallos(at)
    import re
    textos = [e.label for e in at.expander] + [m.value for m in at.markdown]
    # (las definiciones y ejemplos del diccionario, «**Palabra**: ...», no son tu dinero)
    tuyos = [t for t in textos if "💡" not in t and not re.match(r"\*\*[^*]+\*\*: ", t)]
    assert not [t for t in tuyos if re.search(r"\d{1,3}(\.\d{3})+ €", t)]          # ningún importe a la vista


def test_volver_a_abrir_el_mismo_valor_en_analizar():
    at = abrir("pagina_analizar", estado={"analizar_ticker": "IDR.MC"})
    assert at.selectbox(key="an_valor").value == "IDR.MC"
    at.session_state["an_valor"] = "ACS.MC"
    at.session_state["analizar_ticker"] = "IDR.MC"                    # vuelves a Analizar desde otra página
    at.run()
    assert at.selectbox(key="an_valor").value == "IDR.MC"


def test_buscar_cualquier_valor_fuera_del_catalogo(monkeypatch):
    from bolsa import tickers

    monkeypatch.setattr(datos, "buscar_simbolos", lambda q, maximo=8: [
        {"symbol": "ZZZ.MI", "name": "Empresa Buscada SpA", "type": "EQUITY", "exchange": "Milan"}] if q else [])
    at = abrir("pagina_analizar")
    at.text_input(key="an_buscar").set_value("empresa buscada").run()
    sin_fallos(at)
    assert at.selectbox(key="an_hallado").value == "ZZZ.MI"
    assert tickers.nombre_de("ZZZ.MI") == "Empresa Buscada SpA"
    assert any("Empresa Buscada SpA" in t.value for t in [*at.title, *at.header, *at.subheader, *at.markdown])
    tickers.NOMBRES_BUSCADOS.pop("ZZZ.MI", None)


def test_comprar_en_virtual_algo_encontrado_con_el_buscador(monkeypatch):
    from bolsa import tickers

    monkeypatch.setattr(datos, "buscar_simbolos", lambda q, maximo=8: [
        {"symbol": "ZZZ.MC", "name": "Pyme Española SA", "type": "EQUITY", "exchange": "Madrid"}])
    at = abrir("pagina_cartera_virtual")
    at.text_input(key="v_compra_buscar").set_value("pyme").run()
    sin_fallos(at)
    assert any("PYME ESPAÑOLA SA" in m.value for m in at.markdown)          # en el ticket de la orden
    tickers.NOMBRES_BUSCADOS.pop("ZZZ.MC", None)


def test_calculadora_de_letras_del_tesoro():
    at = abrir_pestana(abrir("pagina_calculadoras"), "calc_pestana", "📜 Letras del Tesoro")
    sin_fallos(at)
    assert any(m.label == "Letras que compras" and m.value == "10" for m in at.metric)


@pytest.mark.parametrize("pestana", ["Renta fija", "Fondos de gestión activa", "ETF temáticos y sectoriales"])
def test_mercados_pestanas_nuevas(pestana):
    at = abrir_pestana(abrir("pagina_resumen"), "mk_pestana", pestana)
    sin_fallos(at)
    assert at.dataframe


def test_mercados_acciones_mas_empresas():
    at = abrir("pagina_resumen", estado={"mk_pestana": "Acciones", "mk_acciones": "SOCIMIs e inmobiliarias"})
    sin_fallos(at)
    assert at.dataframe
