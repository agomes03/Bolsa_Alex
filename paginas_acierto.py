"""✅ ¿Acierta la app? Todo lo que se puede medir de lo que dice la app, con datos que no conocía."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from paginas_hoy import bloque_historial_ideas
from ui_comun import cargar_informe, fecha, mostrar_plotly, num, pct


def pagina_acierto():
    st.title("✅ ¿Acierta la app?")
    st.caption("Lo que dice la app solo vale si se ha comprobado con datos que no conocía. Aquí tienes todas las "
               "pruebas, también las que salen mal.")
    inf = cargar_informe()
    if not inf:
        st.info("Aún no hay informe diario. Se genera cada noche de forma automática.")
        return
    mod, ries = inf.get("modelo", {}), inf.get("modelo_riesgo", {})
    cal = ries.get("calibracion") or []
    cart = {k: c for k, c in inf.get("carteras", {}).items() if c.get("universo") == "espana"}

    st.subheader("En resumen")
    lineas = []
    if mod.get("metricas"):
        m = mod["metricas"]
        lineas.append(f"❌ **Adivinar si una acción subirá el mes que viene: no funciona.** Con {num(m['casos'], 0)} "
                      f"casos reales ({m['desde'][:4]}-{m['hasta'][:4]}), el modelo acierta como lanzar una moneda "
                      f"(AUC {num(m['auc'], 2)}; 0,50 es el azar). Por eso la app no te da «probabilidad de subir».")
    if cal:
        lineas.append(f"✅ **Anticipar el riesgo de una caída fuerte: sí ayuda.** Entre las acciones con menos riesgo "
                      f"según el modelo, un {pct(cal[0]['sube'] * 100, 0, False)} cayeron más de un 10 % en el mes "
                      f"siguiente; entre las de más riesgo, un {pct(cal[-1]['sube'] * 100, 0, False)}: casi "
                      f"{num(cal[-1]['sube'] / max(cal[0]['sube'], 1e-9), 1)} veces más.")
    for c in cart.values():
        mt, ref = c["metricas"], c["referencia"]
        mejor = mt["cagr_pct"] > ref["cagr_pct"]
        lineas.append(f"{'✅' if mejor else '⚠️'} **{c['nombre']}** (simulada desde 2017 con comisiones reales): "
                      f"{pct(mt['cagr_pct'], 1)} al año frente a {pct(ref['cagr_pct'], 1)} de todas las acciones "
                      f"españolas a partes iguales; peor caída {pct(mt['max_caida_pct'], 0)} (la referencia, "
                      f"{pct(ref['max_caida_pct'], 0)}).")
    hv = inf.get("historial_veredictos") or {}
    hi = inf.get("historial_ideas") or {}
    if hv.get("evaluados"):
        mejor = hv["grupos"][0]
        lineas.append(f"📅 **En tiempo real** ({hv['evaluados']} casos con un mes de antigüedad): el grupo que más "
                      f"subió fue «{mejor['veredicto']}» ({pct(mejor['rent_media'] * 100, 1)} de media).")
    else:
        desde = date.fromisoformat(hv.get("desde") or hi.get("desde") or inf["fecha"])
        lineas.append(f"📅 **En tiempo real**: la app guarda cada día sus ideas y sus veredictos desde el "
                      f"{fecha(desde.isoformat())}. Los primeros resultados reales, con un mes de antigüedad, llegarán "
                      f"hacia el **{fecha((desde + timedelta(days=31)).isoformat())}**.")
    for x in lineas:
        st.markdown(x)
    st.caption("Ninguna prueba garantiza el futuro. Las simulaciones usan las empresas que existen hoy (las que "
               "quebraron no están), y eso las hace parecer algo mejores de lo que habrían sido.")

    if cal:
        st.subheader("🔴 Riesgo de caída: ¿se cumple?")
        st.caption("Las acciones, ordenadas de menos a más riesgo según el modelo (10 grupos iguales), y qué parte de "
                   "ellas cayó más de un 10 % en el mes siguiente. Comprobado año a año con un modelo que solo conocía "
                   "los años anteriores.")
        fig = go.Figure(go.Bar(x=[f"{i + 1}" for i in range(len(cal))], y=[c_["sube"] * 100 for c_ in cal],
                               marker_color=["#16a34a" if i < 3 else "#f59e0b" if i < 7 else "#dc2626"
                                             for i in range(len(cal))],
                               text=[f"{c_['sube'] * 100:.0f} %" for c_ in cal], textposition="outside"))
        fig.add_hline(y=ries["metricas"]["tasa_subidas"] * 100, line_dash="dot", annotation_text="media")
        fig.update_layout(xaxis_title="Grupo de riesgo (1 = el menor)", yaxis_title="% que cayó más de un 10 %",
                          showlegend=False)
        mostrar_plotly(fig, alto=300)

    if cart:
        st.subheader("📦 Carteras modelo: simulación con comisiones reales")
        st.dataframe(pd.DataFrame([{
            "Cartera": c["nombre"], "Al año": pct(c["metricas"]["cagr_pct"], 1),
            "Peor caída": pct(c["metricas"]["max_caida_pct"], 0),
            "Todas a partes iguales (al año)": pct(c["referencia"]["cagr_pct"], 1),
            "Peor caída de la referencia": pct(c["referencia"]["max_caida_pct"], 0),
            "Comisiones pagadas (con 10.000 €)": f"{num(c['metricas']['gastos'] * 10_000 / c['capital_simulado'], 0)} €"}
            for c in cart.values()]), hide_index=True, width="stretch")

    st.subheader("📅 En tiempo real (lo más honesto)")
    st.caption("Cada día se guardan las ideas y el veredicto de cada acción; un mes después se comprueba qué pasó.")
    if hv.get("evaluados"):
        st.dataframe(pd.DataFrame([{
            "Veredicto ese día": g["veredicto"], "Casos": g["casos"],
            "Un mes después (media)": pct(g["rent_media"] * 100, 2), "Subieron": pct(g["suben"] * 100, 0, False),
            "Frente a su índice": pct(g["exceso_medio"] * 100, 2) if g["exceso_medio"] is not None else "—",
            "Batieron a su índice": pct(g["baten_indice"] * 100, 0, False) if g["baten_indice"] is not None else "—"}
            for g in hv["grupos"]]), hide_index=True, width="stretch")
        st.caption("Si «Candidata a comprar» no sube más que «Evitar por ahora» durante varios meses, el veredicto "
                   "no está ayudando y conviene tomarlo con más cautela.")
    else:
        st.info(f"Veredictos guardados: {hv.get('dias', 0)} día(s), {hv.get('pendientes', 0)} pendientes de cumplir "
                "un mes.")
    bloque_historial_ideas()

    with st.expander("🔬 Cómo se mide (para que no haya trampa)"):
        st.markdown(
            "- **Fuera de muestra**: cada año se comprueba con un modelo entrenado solo con los años anteriores "
            "(*walk-forward*). Nunca se evalúa con datos que el modelo ya había visto.\n"
            "- **Sin mirar el futuro**: los datos de cada día solo usan precios hasta ese día.\n"
            "- **Con costes**: las carteras pagan las comisiones de Bankinter, la tasa Tobin y el cambio de divisa.\n"
            "- **En tiempo real**: las ideas y los veredictos se guardan el mismo día y se evalúan un mes después.\n"
            "- **Limitaciones**: sesgo de supervivencia (solo empresas que existen hoy) y un único periodo histórico "
            "(2017-2026), con una gran caída (COVID) y una fuerte subida.")
