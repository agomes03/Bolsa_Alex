"""Página Noticias: titulares con su conclusión sencilla."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from bolsa import noticias
from bolsa.tickers import nombre_de
from ui_comun import cargar_noticias, conclusion_noticia, mostrar_conclusion, perfil


def tarjeta_noticia(n: noticias.Noticia, expandida: bool = False):
    estrellas = "🔥" * max(1, round(n.impacto / 2)) if n.impacto >= 4 else "·"
    empresas = ", ".join(nombre_de(t) for t in n.empresas)
    with st.expander(f"{n.etiqueta_sentimiento} · {estrellas} · {n.titulo}", expanded=expandida):
        st.markdown(f"**[{n.titulo}]({n.enlace})**")
        st.caption(f"{n.fuente} · {noticias.hace_cuanto(n)} · Impacto {n.impacto}/10"
                   + (f" · Publicada en {n.repeticiones} medios" if n.repeticiones > 1 else "")
                   + (f" · Empresas: {empresas}" if empresas else ""))
        mostrar_conclusion(conclusion_noticia(n.titulo, n.resumen, n.empresas, n.sentimiento))
        if n.resumen and n.resumen.lower()[:60] not in n.titulo.lower():
            st.write(n.resumen)
        if n.explicaciones:
            st.markdown("**📚 Para entenderla:**")
            for e in n.explicaciones[:3]:
                st.markdown(f"- {e}")
        else:
            st.caption("Noticia sin un tema macro clave detectado: probablemente impacto limitado.")


def pagina_noticias():
    movil = perfil().movil
    st.title("📰 Noticias que mueven el mercado")
    st.caption(f"Se leen **{len(noticias.FUENTES_RSS)} fuentes** (prensa española, Google News, CNBC, MarketWatch, "
               "Yahoo Finance...) y se ordenan por **impacto estimado** (0-10): temas que históricamente mueven las "
               "bolsas, cuántos medios publican la misma noticia y lo reciente que es. Despliega cada una para ver "
               "**por qué importa**.")
    with st.spinner("Leyendo todas las fuentes..."):
        lista, fallos = cargar_noticias()
    st.caption(f"{len(lista)} noticias únicas de las últimas 72 h."
               + (f" Fuentes no disponibles ahora: {', '.join(fallos)}." if fallos else ""))
    if not lista:
        st.error("No se han podido descargar noticias.")
        return

    c1, c2, c3 = st.columns(3)
    minimo = c1.slider("Impacto mínimo", 0, 10, 3)
    tono = c2.selectbox("Tono", ["Todas", "🟢 Positivas", "🔴 Negativas"])
    empresas = sorted({t for n in lista for t in n.empresas}, key=nombre_de)
    filtro_emp = c3.selectbox("Empresa", ["Todas"] + empresas, format_func=lambda t: t if t == "Todas" else nombre_de(t))

    filtradas = [n for n in lista if n.impacto >= minimo
                 and (tono == "Todas" or (tono.startswith("🟢") and n.sentimiento > 0) or (tono.startswith("🔴") and n.sentimiento < 0))
                 and (filtro_emp == "Todas" or filtro_emp in n.empresas)]
    st.write(f"**{len(filtradas)}** noticias")

    menciones: dict[str, list[int]] = {}
    for n in lista:
        for t in n.empresas:
            menciones.setdefault(t, []).append(n.sentimiento)
    if menciones:
        with st.expander("🏢 Empresas más mencionadas"):
            filas = [{"Empresa": nombre_de(t), "Noticias": len(s), "Tono medio": round(sum(s) / len(s), 2)}
                     for t, s in menciones.items()]
            st.dataframe(pd.DataFrame(filas).sort_values("Noticias", ascending=False),
                         hide_index=True, width="stretch")
            st.caption("Que una empresa salga mucho en las noticias no significa que haya que comprarla. "
                       "Analízala en '🔍 Analizar'.")

    for i, n in enumerate(filtradas[:80]):
        tarjeta_noticia(n, expandida=i < 3 and not movil)
