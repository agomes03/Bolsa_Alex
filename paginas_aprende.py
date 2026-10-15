"""Página Aprende: lo esencial, diccionario con buscador, guías «Cómo se hace» y test."""

from __future__ import annotations

import streamlit as st
from bolsa import aprendizaje, costes
from ui_comun import eur, num, perfil


AVISO = ("⚠️ **Herramienta educativa, no es asesoramiento financiero.** Ningún sistema puede "
         "garantizar beneficios ni predecir la bolsa con certeza: invierte solo dinero que no vayas a "
         "necesitar en años y que puedas permitirte ver bajar un 30% sin vender por miedo.")


def pagina_aprende():
    st.title("🎓 Aprende")
    q = st.text_input("🔎 ¿Qué palabra no entiendes?", placeholder="stop-loss, PER, plusvalía, spread, tasa Tobin...",
                      help="Busca en el diccionario, en las guías paso a paso y en el test. Vale sin tildes, con "
                           "siglas y con términos en inglés.")
    if q.strip():
        aprende_resultados(q)
        st.divider()
    t1, t2, t3, t4 = st.tabs(["📘 Lo esencial", "📖 Diccionario", "🛠️ Cómo se hace", "✅ Ponte a prueba"])
    with t1:
        aprende_esencial()
    with t2:
        aprende_diccionario()
    with t3:
        aprende_guias()
    with t4:
        aprende_test()


def aprende_esencial():
    st.info(AVISO)
    st.markdown("""
### 1. Lo que funciona y lo que no (comprobado con datos reales)
- ❌ **Adivinar si una acción subirá el mes que viene.** Con 10 años de 130 empresas, ningún modelo lo hace mejor
  que lanzar una moneda. Desconfía de quien te lo prometa: por eso la app no te da «probabilidades de subir».
- ✅ **Estimar el riesgo de una caída fuerte.** Las acciones con riesgo «alto» cayeron más de un 10 % en un mes unas
  tres veces más a menudo que las de riesgo «bajo». La app lo usa para que evites sustos.
- ✅ **Carteras sencillas revisadas una vez al mes** (📦 Carteras modelo). En España, quedarse cada mes con las 8
  acciones que más subieron el último año ganó más que la media (2020-2026), con caídas parecidas a la bolsa.
- ✅ **Lo más rentable para casi todo el mundo**: aportar cada mes a un **fondo indexado** mundial, durante años,
  sin vender cuando la bolsa cae.

### 2. Tu plan en tres partes (🎯 Mi plan te dice cuánto en cada una)
1. **Colchón de emergencia** (3-6 meses de gastos) fuera de la bolsa.
2. **El núcleo: un fondo indexado mundial** con aportaciones mensuales.
3. **Una parte pequeña en acciones españolas** de la cartera modelo de tu perfil.

### 3. Reglas de oro
1. **No inviertas dinero que vayas a necesitar** en los próximos 3-5 años.
2. **Diversifica**: ninguna empresa por encima del 20 % de tu dinero, ningún sector por encima del 40 %.
3. **No arriesgues más del 1-2 % de tu dinero en una operación** (la app calcula cuántas acciones comprar).
4. **Pon siempre stop-loss** en acciones sueltas y no lo bajes nunca.
5. **No persigas** una acción que ha subido un 20 % en una semana.
6. **Las noticias llegan tarde**: cuando las lees, el precio ya se ha movido. Sirven para entender, no para correr.
7. **Las comisiones importan**: pocas operaciones y bien pensadas.
8. **Las emociones son tu mayor enemigo**: ten un plan y síguelo.

### 4. Calendario que mueve los mercados
- Reuniones del **BCE** (cada ~6 semanas, jueves) y de la **Fed** (8 al año, miércoles por la tarde en España).
- **IPC** de EEUU (hacia mediados de mes) y **empleo** de EEUU (primer viernes de mes, 14:30 h).
- **Resultados de las empresas**: enero-febrero, abril-mayo, julio-agosto y octubre-noviembre.
- **Horario**: Bolsa española de 9:00 a 17:30; Wall Street de 15:30 a 22:00 (hora peninsular; una hora antes
  unas semanas de marzo y de octubre-noviembre por el cambio de hora).
""")


def _termino_md(t) -> str:
    texto = f"**{t.termino}** · _{t.categoria}_\n\n{t.definicion}"
    if t.ejemplo:
        texto += f"\n\n> 💡 {t.ejemplo}"
    if t.ver:
        texto += f"\n\n<small>Ver también: {', '.join(t.ver)}</small>"
    return texto


def aprende_resultados(q: str):
    terminos = aprendizaje.buscar(q)
    guias = aprendizaje.buscar_guias(q)
    preguntas = aprendizaje.buscar_preguntas(q)
    if not (terminos or guias or preguntas):
        parecidos = aprendizaje.parecidos(q)
        if parecidos:
            st.info(f"No aparece «{q}». ¿Quizás buscabas…?")
            for t in parecidos[:3]:
                with st.container(border=True):
                    st.markdown(_termino_md(t), unsafe_allow_html=True)
        else:
            st.info(f"No aparece «{q}». Prueba con otra palabra o mira los temas del 📖 Diccionario.")
        return
    # Los que coinciden en el nombre se muestran abiertos; el resto, plegados para no llenar la pantalla.
    for i, t in enumerate(terminos[:12]):
        if i < 3:
            with st.container(border=True):
                st.markdown(_termino_md(t), unsafe_allow_html=True)
        else:
            with st.expander(f"📖 {t.termino}"):
                st.markdown(_termino_md(t), unsafe_allow_html=True)
    if len(terminos) > 12:
        st.caption(f"Y {len(terminos) - 12} términos más: escribe una palabra más concreta.")
    for g in guias:
        with st.expander(f"🛠️ Guía: {g.titulo}"):
            _guia(g)
    for p in preguntas:
        with st.expander(f"✅ Del test: {p.pregunta[:70]}"):
            st.markdown(f"**{p.pregunta}**\n\nRespuesta: **{p.opciones[p.correcta]}**. {p.explicacion}")


def aprende_diccionario():
    st.caption(f"{len(aprendizaje.GLOSARIO)} términos explicados en lenguaje sencillo, con ejemplos en euros. "
               "Para buscar una palabra, usa el buscador de arriba.")
    for nombre in aprendizaje.CATEGORIAS:
        terminos = aprendizaje.buscar(categoria=nombre)
        with st.expander(f"{nombre} ({len(terminos)})"):
            for t in terminos:
                st.markdown(_termino_md(t), unsafe_allow_html=True)


def _guia(g):
    st.markdown(f"**Para qué:** {g.para_que}")
    st.markdown("\n".join(f"{i}. {p}" for i, p in enumerate(g.pasos, 1)))
    if g.errores:
        st.markdown("**Errores típicos:**\n" + "\n".join(f"- ❌ {e}" for e in g.errores))
    if g.en_la_app:
        st.caption("📱 " + g.en_la_app)


def aprende_guias():
    pf = perfil()
    movil, tarifa = pf.movil, pf.tarifa
    st.caption("Paso a paso, con lo que tienes que pulsar en Bankinter y en esta app. Los nombres de los menús de "
               "Bankinter pueden variar un poco entre la web y la app del móvil.")
    for g in aprendizaje.GUIAS:
        with st.expander(f"🛠️ {g.titulo}"):
            _guia(g)

    with st.expander("🧮 Practica: cuántas acciones comprar y dónde poner el stop"):
        st.write("La cantidad no se elige a ojo: sale de cuánto aceptas perder si la operación sale mal.")
        k = st.columns(2 if movil else 4)
        dinero = k[0].number_input("Tu dinero para acciones (€)", 500.0, 10_000_000.0, 10_000.0, 500.0)
        riesgo_p = k[1].number_input("Riesgo por operación (%)", 0.25, 5.0, 1.0, 0.25)
        entrada = k[2 % len(k)].number_input("Precio de compra (€)", 0.1, 100_000.0, 20.0, 0.5)
        stop_p = k[3 % len(k)].number_input("Stop-loss (€)", 0.0, 100_000.0, 18.0, 0.5)
        if stop_p >= entrada:
            st.warning("El stop-loss tiene que estar por debajo del precio de compra.")
        else:
            n = costes.tamano_por_riesgo(dinero, riesgo_p, entrada, stop_p)
            arriesgado = dinero * riesgo_p / 100
            st.markdown(
                f"1. Lo máximo que aceptas perder: {num(riesgo_p, 2)} % de {eur(dinero)} = **{eur(arriesgado)}**.\n"
                f"2. Si salta el stop, pierdes {eur(entrada)} − {eur(stop_p)} = **{eur(entrada - stop_p)} por acción**.\n"
                f"3. Acciones: {eur(arriesgado)} / {eur(entrada - stop_p)} = **{n} "
                f"{'acción' if n == 1 else 'acciones'}** ({eur(n * entrada)}, el "
                f"{num(n * entrada / dinero * 100, 0)} % de tu dinero).")
            if n * entrada > dinero * 0.20:
                st.info(f"Eso supera el 20 % de tu dinero en una sola empresa: por diversificación, la app lo limita a "
                        f"unas {costes.acciones_asequibles(dinero * 0.20, entrada, 'SAN.MC', tarifa)} acciones.")

    st.markdown("#### Resumen: qué orden usar en Bankinter")
    st.markdown("""
| Para… | En Bankinter | Por qué |
|---|---|---|
| Comprar una acción | Bróker → buscar el nombre → **Comprar** → orden **Limitada** | Nunca pagas más del precio que pones. |
| Limitar pérdidas | Orden **Stop** de venta: «menor o igual que» + **precio límite** | Bankinter exige precio límite; ponlo un 2 % por debajo para que se ejecute aunque caiga deprisa. |
| Pérdidas y objetivo a la vez | **Stop relacionadas** | Al ejecutarse una, Bankinter cancela la otra. |
| Que el stop suba solo | **Stop dinámica** | Sube con la cotización y no baja nunca. |
| Subir un stop | Anular la orden stop y crear otra | En Bankinter las órdenes stop no se modifican. |
| Aportar cada mes | **Fondos** → fondo indexado → aportación periódica | Sin comisión por aportación (un ETF extranjero cuesta 20 € cada compra). |
| Revisar tu cartera | Bróker → **Posición global** → descargar | Súbelo en 🏦 Mi cartera para el diagnóstico. |

**Lo que cuesta en Bankinter** (tarifa pública, octubre 2026; compruébala en Bróker → Tarifas):
- Acciones españolas: **3,95 €** hasta 2.000 € y **8 €** hasta 60.000 € por operación (**0 €** con Bróker Cero), más
  un canon de bolsa de ~1 € y la tasa Tobin (0,2 % al comprar empresas de más de 1.000 millones).
- Acciones extranjeras: **20 €** por operación, **+1 %** si cotizan en otra divisa y una **custodia mínima de 24 € al
  año por valor**. Con poco dinero, mejor acciones españolas y fondos indexados.
""")


def aprende_test():
    st.caption(f"{len(aprendizaje.PREGUNTAS)} preguntas sobre situaciones reales. Sin nota que guardar: solo para "
               "comprobar que lo tienes claro.")
    with st.form("test_aprende"):
        respuestas = [st.radio(f"**{i}.** {p.pregunta}", p.opciones, index=None, key=f"test_{i}")
                      for i, p in enumerate(aprendizaje.PREGUNTAS, 1)]
        corregir = st.form_submit_button("Corregir", type="primary")
    if not corregir:
        return
    aciertos = 0
    for i, (p, r) in enumerate(zip(aprendizaje.PREGUNTAS, respuestas), 1):
        bien = r == p.opciones[p.correcta]
        aciertos += bien
        icono = "✅" if bien else ("⬜" if r is None else "❌")
        st.markdown(f"{icono} **{i}.** {p.opciones[p.correcta]} — {p.explicacion}")
    n = len(aprendizaje.PREGUNTAS)
    (st.success if aciertos >= n * 0.8 else st.info)(
        f"Has acertado {aciertos} de {n}." + ("" if aciertos >= n * 0.8 else
                                            " Repasa las guías de 🛠️ Cómo se hace y vuelve a intentarlo."))
