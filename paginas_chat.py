"""💬 Pregunta a Claude: chat de dudas bursátiles con el contexto de tu cartera y del mercado."""

from __future__ import annotations

import os
from datetime import date

import streamlit as st

from bolsa import activos, bankinter, chat, diagnostico
from bolsa.indicadores import rsi
from bolsa.tickers import nombre_de
from ui_comun import (cargar_activos, cargar_fundamentales, cargar_historico, cargar_informe, cuenta_activa,
                      datos_usuario, num, perfil)

EJEMPLOS = [
    "¿Qué es el RSI y cómo está ahora el de Indra?",
    "¿Cómo tributa en España vender acciones con pérdidas?",
    "¿Qué diferencia hay entre una orden limitada y una stop?",
    "¿Tiene sentido meter algo de oro o de bitcoin en mi cartera?",
]
CAMPOS_FUNDAMENTALES = {"trailingPE": "PER", "forwardPE": "PER estimado", "priceToBook": "precio/valor contable",
                        "trailingAnnualDividendYield": "rentabilidad por dividendo", "beta": "beta",
                        "recommendationKey": "opinión de analistas", "targetMeanPrice": "precio objetivo medio",
                        "numberOfAnalystOpinions": "número de analistas", "marketCap": "capitalización"}


def clave_api() -> str | None:
    try:
        clave = (st.secrets.get("anthropic", {}) or {}).get("api_key")
    except Exception:  # noqa: BLE001 - sin secrets.toml, Streamlit lanza excepción
        clave = None
    return clave or os.environ.get("ANTHROPIC_API_KEY") or st.session_state.get("_clave_api") or None


@st.cache_resource(show_spinner=False)
def _cliente(clave: str):
    import anthropic

    return anthropic.Anthropic(api_key=clave, max_retries=2)


def datos_valor(ticker: str) -> dict:
    """Lo que la herramienta `datos_valor` devuelve a Claude."""
    df = cargar_historico(ticker, "2y")
    if df is None or df.empty:
        return {}
    e = activos.estado(df) or {}
    c = df["Close"].dropna()
    salida = {"ticker": ticker, "nombre": nombre_de(ticker), "ultimo_cierre": round(float(c.iloc[-1]), 4),
              "fecha": str(c.index[-1].date()),
              "variacion_1d_pct": _r(e.get("var_1d")), "variacion_1m_pct": _r(e.get("var_1m")),
              "variacion_1a_pct": _r(e.get("var_1a")),
              "tendencia": None if e.get("alcista") is None else ("alcista (sobre su media de 200 sesiones)"
                                                                   if e["alcista"] else "bajista (bajo su media de 200)"),
              "distancia_al_maximo_1a_pct": _r(e.get("desde_maximo")), "volatilidad_anual_pct": _r(e.get("volatilidad")),
              "rsi_14": _r(float(rsi(c).iloc[-1])) if len(c) > 20 else None,
              "nota": "precios ajustados por dividendos; cierre del último día con datos"}
    if not ticker.startswith("^") and "=" not in ticker and not ticker.endswith("-EUR"):
        f = cargar_fundamentales(ticker) or {}
        salida["fundamentales"] = {v: f[k] for k, v in CAMPOS_FUNDAMENTALES.items() if f.get(k) is not None}
    fila = next((r for r in (cargar_informe() or {}).get("ranking", []) if r["ticker"] == ticker), None)
    if fila:
        from bolsa import asesor

        etiqueta, _, explicacion = asesor.veredicto(fila)
        salida["app"] = {"veredicto": etiqueta, "explicacion": explicacion, "nota_0_100": fila.get("nota"),
                         "riesgo_de_caida": fila.get("riesgo_nivel"), "stop_sugerido": fila.get("stop"),
                         "resultados_pronto": fila.get("resultados_pronto")}
    return salida


def _r(x, d=2):
    return None if x is None else round(float(x), d)


def buscar_valor(consulta: str) -> dict | None:
    from paginas_extra import buscar_simbolo

    return buscar_simbolo(consulta)


def contexto() -> str:
    """Contexto del usuario (se calcula una vez por sesión y día)."""
    clave = f"_contexto_chat_{date.today()}_{datos_usuario().get('cuenta_activa', '')}"
    if clave in st.session_state:
        return st.session_state[clave]
    from paginas_extra import _perfil_guardado, revisar_cartera_real

    inf = cargar_informe() or {}
    cartera, dg = [], None
    try:
        filas = [f for f in revisar_cartera_real() if f["precio"]]
        for f in filas:
            pos = f["pos"]
            valor = pos["acciones"] * f["precio"] * f["fx"]
            coste = pos["acciones"] * pos["precio_medio"] * pos.get("fx_medio", 1.0)
            cartera.append({"ticker": f["ticker"], "nombre": f["nombre"], "clase": f["clase"], "valor": valor,
                            "ganancia_pct": (valor / coste - 1) * 100 if coste else 0, "stop": pos.get("stop")})
        dg = diagnostico.diagnosticar(
            [{"ticker": f["ticker"], "acciones": f["pos"]["acciones"], "precio_medio": f["pos"]["precio_medio"],
              "fx_medio": f["pos"].get("fx_medio", 1.0), "precio": f["precio"], "fx": f["fx"],
              "stop": f["pos"].get("stop"), "clase": f["clase"], "nombre": f["nombre"]} for f in filas],
            cuenta_activa().get("otros_ahorros", 0.0), _perfil_guardado(), perfil().tarifa,
            {r["ticker"]: r for r in inf.get("ranking", [])})
        lista_activos = cargar_activos()
    except Exception:  # noqa: BLE001 - sin datos de mercado el chat sigue funcionando
        lista_activos = []
    texto = chat.contexto_usuario(date.today().strftime("%d/%m/%Y"), bankinter.broker(), _perfil_guardado(), cartera,
                                  dg, inf.get("mercado"), lista_activos)
    st.session_state[clave] = texto
    return texto


def pagina_chat():
    clave = clave_api()
    st.title("💬 Pregunta")
    if clave:
        st.caption("Dudas de bolsa respondidas por Claude con el contexto de tu cartera y del mercado de hoy.")
    else:
        st.caption("**Gratis.** El asistente de la app te responde con datos reales de cualquier valor que nombres "
                   "(precio, tendencia, RSI, PER, veredicto), de tu cartera y del diccionario. Para preguntas más "
                   "abiertas, te deja la pregunta preparada con tu contexto para pegarla en **claude.ai**, que tiene "
                   "plan gratuito.")
    st.session_state.setdefault("chat_historia", [])
    st.session_state.setdefault("chat_gasto", 0.0)

    with st.expander("⚙️ Opcional: conectar la API de Claude (de pago)" if not clave else "⚙️ Ajustes y coste"):
        if not clave:
            st.markdown(
                "No hace falta: la app funciona gratis sin esto. Solo si algún día quieres que Claude responda "
                "**dentro** de la app: la API se paga por uso (unos céntimos por pregunta) y va aparte de "
                "claude.ai. Se activa con una clave de console.anthropic.com en Streamlit → Settings → Secrets:\n"
                "```\n[anthropic]\napi_key = \"sk-ant-...\"\n```")
        else:
            st.radio("Modelo", list(chat.MODELOS), format_func=lambda m: chat.MODELOS[m]["nombre"],
                     key="chat_modelo", horizontal=True)
            st.caption("Coste orientativo por pregunta: Opus 5.5, unos 2-5 céntimos de dólar; Haiku 5.5, menos de "
                       f"medio céntimo. Gasto en esta sesión: ≈ {num(st.session_state['chat_gasto'], 3)} $.")
        if st.session_state.get("chat_vista") and st.button("🗑️ Borrar la conversación"):
            st.session_state["chat_historia"] = []
            st.session_state.pop("chat_vista", None)
            st.rerun()

    vista = st.session_state.setdefault("chat_vista", [])
    for m in vista:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
            if m.get("pie"):
                st.caption(m["pie"])
            if m.get("para_claude_ai"):
                _bloque_claude_ai(m["para_claude_ai"])

    pregunta = st.chat_input("Escribe tu pregunta sobre bolsa, fondos, impuestos, tu cartera...")
    if not vista and not pregunta:
        st.markdown("**Prueba con:**")
        for i, ejemplo in enumerate(EJEMPLOS):
            if st.button(ejemplo, key=f"ej_{i}", width="stretch"):
                st.session_state["_pregunta_pendiente"] = ejemplo
                st.rerun()
    pregunta = pregunta or st.session_state.pop("_pregunta_pendiente", None)
    if pregunta:
        responder(pregunta, clave, st.session_state.get("chat_modelo", chat.MODELO_POR_DEFECTO))


def responder(pregunta: str, clave: str | None, modelo: str):
    vista = st.session_state["chat_vista"]
    vista.append({"role": "user", "content": pregunta})
    with st.chat_message("user"):
        st.markdown(pregunta)
    with st.chat_message("assistant"):
        with st.spinner("Preparando tu contexto..."):
            ctx = contexto()
        if not clave:
            _sin_conexion(pregunta, ctx, None)
            return
        hueco = st.empty()
        escrito = []

        def al_escribir(t):
            escrito.append(t)
            hueco.markdown("".join(escrito) + " ▌")

        try:
            res = chat.conversar(_cliente(clave), modelo, st.session_state["chat_historia"], pregunta, ctx,
                                 datos_valor, buscar_valor, al_escribir)
        except Exception as e:  # noqa: BLE001 - cualquier fallo de la API pasa al modo sin conexión
            mensaje, sin_conexion = chat.explicar_error(e)
            hueco.empty()
            if sin_conexion:
                _sin_conexion(pregunta, ctx, mensaje)
            else:
                st.warning(mensaje)
                vista.append({"role": "assistant", "content": f"⚠️ {mensaje}"})
            return
        texto = res.texto or ("Claude ha declinado responder a esta pregunta." if res.rechazada else "")
        hueco.markdown(texto)
        coste = res.uso.coste_usd()
        st.session_state["chat_gasto"] += coste
        consultas = f" · consultó: {', '.join(res.herramientas)}" if res.herramientas else ""
        pie = f"{chat.MODELOS[modelo]['nombre'].split(' (')[0]} · ≈ {num(coste, 4)} ${consultas}"
        st.caption(pie)
        vista.append({"role": "assistant", "content": texto, "pie": pie})
        st.session_state["chat_historia"] += [{"role": "user", "content": pregunta},
                                              {"role": "assistant", "content": texto or "(sin respuesta)"}]


def _sin_conexion(pregunta: str, ctx: str, motivo: str | None):
    """Respuesta gratuita de la app y la pregunta preparada para claude.ai."""
    if motivo:
        st.info(motivo)
    with st.spinner("Buscando datos..."):
        texto = chat.respuesta_gratis(pregunta, ctx, datos_valor)
    st.markdown(texto)
    st.caption("Asistente gratuito de la app · 0 €")
    para = chat.pregunta_para_claude_ai(pregunta, ctx)
    _bloque_claude_ai(para)
    st.session_state["chat_vista"].append({"role": "assistant", "content": (f"ℹ️ {motivo}\n\n" if motivo else "")
                                           + texto, "pie": "Asistente gratuito de la app · 0 €",
                                           "para_claude_ai": para})


def _bloque_claude_ai(texto: str):
    with st.expander("🤖 ¿Quieres una explicación más completa? Pregúntaselo gratis a Claude en claude.ai"):
        st.caption("Copia este texto (botón de la esquina del recuadro), abre claude.ai y pégalo. Lleva tu pregunta y "
                   "el contexto de tu cartera y del mercado, sin nombres ni datos de tu banco.")
        st.code(texto, language=None, wrap_lines=True)
        st.link_button("Abrir claude.ai", "https://claude.ai/new")
