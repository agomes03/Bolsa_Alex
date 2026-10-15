"""💬 Pregunta a Claude: chat de dudas bursátiles con el contexto de tu cartera y del mercado."""

from __future__ import annotations

import os
from datetime import date

import streamlit as st

from bolsa import activos, bankinter, chat, diagnostico
from bolsa.indicadores import rsi
from bolsa.tickers import nombre_de
from ui_comun import (cargar_activos, cargar_fundamentales, cargar_historico, cargar_informe, datos_usuario, num,
                      perfil)

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
    clave = f"_contexto_chat_{date.today()}"
    if clave in st.session_state:
        return st.session_state[clave]
    from paginas_extra import _perfil_guardado, revisar_cartera_real

    d = datos_usuario()
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
            d.get("otros_ahorros", 0.0), _perfil_guardado(), perfil().tarifa,
            {r["ticker"]: r for r in inf.get("ranking", [])})
        lista_activos = cargar_activos()
    except Exception:  # noqa: BLE001 - sin datos de mercado el chat sigue funcionando
        lista_activos = []
    texto = chat.contexto_usuario(date.today().strftime("%d/%m/%Y"), bankinter.BROKER, _perfil_guardado(), cartera,
                                  dg, inf.get("mercado"), lista_activos)
    st.session_state[clave] = texto
    return texto


def pagina_chat():
    st.title("💬 Pregunta a Claude")
    st.caption("Dudas técnicas de bolsa respondidas por Claude con el contexto de tu cartera y del mercado de hoy. "
               "Puede consultar al momento los datos de cualquier valor.")
    st.session_state.setdefault("chat_historia", [])
    st.session_state.setdefault("chat_gasto", 0.0)
    clave = clave_api()

    with st.expander("⚙️ Ajustes y coste" + ("" if clave else " · sin conectar"), expanded=not clave):
        st.radio("Modelo", list(chat.MODELOS), format_func=lambda m: chat.MODELOS[m]["nombre"],
                          key="chat_modelo", horizontal=True)
        st.caption("Coste orientativo por pregunta: Opus 5.5, unos 2-5 céntimos de dólar; Haiku 5.5, menos de "
                   "medio céntimo. Lo ves debajo de cada respuesta.")
        if not clave:
            st.markdown(
                "**Para conectar Claude** necesitas una clave de la API de Anthropic. **Es aparte de tu suscripción "
                "de claude.ai** (que no incluye la API, ni en el plan gratuito ni en los de pago):\n"
                "1. Entra en **console.anthropic.com**, ve a **Billing** y recarga un saldo pequeño (por ejemplo, "
                "5 $). Pon un **límite de gasto** mensual en *Limits* para no llevarte sorpresas.\n"
                "2. En **API keys**, crea una clave.\n"
                "3. En Streamlit → tu app → **Settings → Secrets**, añade debajo de lo que ya tienes:\n"
                "   ```\n   [anthropic]\n   api_key = \"sk-ant-...\"\n   ```\n"
                "Sin clave (o si se acaba el saldo), el chat sigue funcionando en **modo sin conexión**: responde "
                "con el diccionario y las guías de la app y te prepara la pregunta para pegarla en claude.ai, "
                "que sí tiene plan gratuito.")
            tecleada = st.text_input("O pega aquí la clave solo para esta sesión (no se guarda)", type="password")
            if tecleada.strip():
                st.session_state["_clave_api"] = tecleada.strip()
                st.rerun()
        else:
            st.caption(f"Conectado a la API de Anthropic. Gasto en esta sesión: ≈ {num(st.session_state['chat_gasto'], 3)} $.")
        if st.session_state["chat_historia"] and st.button("🗑️ Borrar la conversación"):
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
            _sin_conexion(pregunta, ctx, "Modo sin conexión (no hay clave de la API).")
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


def _sin_conexion(pregunta: str, ctx: str, motivo: str):
    texto = chat.respuesta_sin_conexion(pregunta)
    st.info(motivo)
    st.markdown(texto)
    para = chat.pregunta_para_claude_ai(pregunta, ctx)
    _bloque_claude_ai(para)
    st.session_state["chat_vista"].append({"role": "assistant", "content": f"ℹ️ {motivo}\n\n{texto}",
                                           "para_claude_ai": para})


def _bloque_claude_ai(texto: str):
    with st.expander("📋 Pregunta preparada para claude.ai (gratis): cópiala y pégala allí"):
        st.code(texto, language=None, wrap_lines=True)
        st.link_button("Abrir claude.ai", "https://claude.ai/new")
