"""Asistente de Bolsa para principiantes (pensado para operar con el broker de Bankinter).

Ejecutar:  streamlit run app.py

Este archivo solo arranca la app: cada página vive en su propio módulo (paginas_*.py) y la barra lateral en
barra_lateral.py.
"""

from __future__ import annotations

import streamlit as st

from ui_comun import aviso_datos_antiguos, control_acceso, estilos

st.set_page_config(page_title="Asistente de Bolsa", page_icon="📈", layout="wide",
                   initial_sidebar_state="collapsed")
estilos()
control_acceso()

from barra_lateral import barra_lateral  # noqa: E402  (después de la contraseña: no se carga nada sin acceso)
from paginas_acierto import pagina_acierto  # noqa: E402
from paginas_analizar import pagina_analizar, pagina_radar  # noqa: E402
from paginas_aprende import pagina_aprende  # noqa: E402
from paginas_calculadoras import pagina_calculadoras  # noqa: E402
from paginas_chat import pagina_chat  # noqa: E402
from paginas_extra import pagina_bankinter, pagina_cartera_virtual, pagina_simulador  # noqa: E402
from paginas_hoy import pagina_carteras, pagina_hoy  # noqa: E402
from paginas_mercados import pagina_resumen  # noqa: E402
from paginas_noticias import pagina_noticias  # noqa: E402
from paginas_plan import pagina_plan  # noqa: E402
from paginas_seguimiento import pagina_seguimiento  # noqa: E402

st.session_state["_perfil"] = barra_lateral()

PAGINAS = {
    "hoy": st.Page(pagina_hoy, title="Hoy", icon="🧭", default=True),
    "plan": st.Page(pagina_plan, title="Mi plan", icon="🎯"),
    "analizar": st.Page(pagina_analizar, title="Analizar", icon="🔍"),
    "radar": st.Page(pagina_radar, title="Radar", icon="📡"),
    "carteras": st.Page(pagina_carteras, title="Carteras modelo", icon="📦"),
    "noticias": st.Page(pagina_noticias, title="Noticias", icon="📰"),
    "mercados": st.Page(pagina_resumen, title="Mercados", icon="🌍"),
    "bankinter": st.Page(pagina_bankinter, title="Mi cartera", icon="🏦"),
    "virtual": st.Page(pagina_cartera_virtual, title="Cartera virtual", icon="🎮"),
    "seguimiento": st.Page(pagina_seguimiento, title="Seguimiento", icon="📒"),
    "simulador": st.Page(pagina_simulador, title="Simulador y modelos", icon="🧪"),
    "calculadoras": st.Page(pagina_calculadoras, title="Calculadoras", icon="🧮"),
    "aprende": st.Page(pagina_aprende, title="Aprende", icon="🎓"),
    "chat": st.Page(pagina_chat, title="Pregunta", icon="💬"),
    "acierto": st.Page(pagina_acierto, title="¿Acierta la app?", icon="✅"),
}
st.session_state["_paginas"] = PAGINAS
GRUPOS = {
    "Inicio": [PAGINAS["hoy"], PAGINAS["plan"], PAGINAS["chat"]],
    "Invertir": [PAGINAS["analizar"], PAGINAS["radar"], PAGINAS["carteras"], PAGINAS["noticias"],
                 PAGINAS["mercados"]],
    "Mis carteras": [PAGINAS["bankinter"], PAGINAS["seguimiento"], PAGINAS["virtual"]],
    "Aprender y probar": [PAGINAS["acierto"], PAGINAS["simulador"], PAGINAS["calculadoras"], PAGINAS["aprende"]],
}
nav = st.navigation(GRUPOS, position="top")
_hueco_aviso = st.empty()
nav.run()
aviso_datos_antiguos(_hueco_aviso)
