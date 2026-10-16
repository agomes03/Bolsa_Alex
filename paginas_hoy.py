"""Páginas basadas en el informe diario: Hoy, Mi plan, Radar, Carteras modelo y bloques de "qué puede pasar"."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from bolsa import asesor, bankinter, costes, estrategias, noticias, patrones
from bolsa.costes import simular_aportaciones
from bolsa.tickers import nombre_de
from paginas_extra import asesor_hoy, limite_empresa, pesos_cartera_real
from paginas_seguimiento import bloque_pendientes
from ui_comun import (cargar_informe, cargar_noticias, cargar_varios, conclusion_noticia, cotizaciones_ahora,
                      cuenta_activa, dias_informe, eur, fecha, guardar_datos, hora_espana, ir_a, linea_actualizado,
                      linea_frescura, moneda_de, num, palabras_de_la_pagina, pct, perfil, pestanas, precio, reducir,
                      SEGUNDOS_REFRESCO, texto_estado_precio)

COLOR_SEMAFORO = {"verde": ("success", "🟢 Mercado favorable"),
                  "ambar": ("warning", "🟡 Mercado mixto"),
                  "rojo": ("error", "🔴 Mercado débil o nervioso")}
TEXTO_SEMAFORO = {
    "verde": "La mayoría de bolsas suben con calma. Buen momento para seguir tu plan con normalidad.",
    "ambar": "Unas bolsas van bien y otras no. Sigue tu plan, entra poco a poco y usa siempre stop-loss.",
    "rojo": "La mayoría de bolsas están en tendencia bajista o hay mucho miedo. Sin prisa: sigue solo con tus "
            "aportaciones periódicas al fondo indexado y no compres acciones sueltas.",
}
ICONO_RIESGO = {"bajo": "🟢 bajo", "normal": "🟡 normal", "alto": "🔴 alto", None: "—"}


def sin_informe():
    st.info("📭 Todavía no hay **informe diario**. Se genera solo cada día laborable al cierre de Wall Street "
            "(GitHub → Actions → «Actualización diaria»). Mientras tanto, puedes usar 🔍 Analizar, 📰 Noticias y "
            "🌍 Mercados, que descargan los datos en directo.")


def aviso_antiguedad(inf: dict):
    dias = dias_informe(inf)
    st.caption(f"📅 Datos hasta el **{fecha(inf['datos_hasta'])}** (calculado el {hora_espana(inf.get('generado'))}). "
               "Se actualiza solo cada día laborable al cierre de Wall Street.")
    if dias > 4:
        st.warning(f"El informe tiene {dias} días. Revisa que la actualización diaria de GitHub esté funcionando.")


def texto_fase(nombre: str, f: dict) -> str:
    h = f.get("horizontes", {}).get("1 mes", {})
    if not h.get("prob_sube"):
        return f"**{nombre}**: fase «{f.get('fase', '—')}»."
    return (f"**{nombre}** está en fase **«{f['fase']}»** desde el {fecha(f['desde'])}. En las {h['casos']} ocasiones "
            f"parecidas desde {f['historia_desde'][:4]}, un mes después **subió el {num(h['prob_sube'] * 100, 0)} %** de "
            f"las veces; lo normal fue entre {pct(h['p10'] * 100)} y {pct(h['p90'] * 100)}, y la peor vez "
            f"{pct(h['peor'] * 100)}.")


def texto_proteccion(t: str, p: dict) -> str:
    if p.get("estado") == "dentro":
        return (f"🟢 **{nombre_de(t)}**: seguir invertido (desde el {fecha(p['desde'])}). Se saldría si baja de "
                f"{num(p['salir_si_baja_de'], 0)} ({pct((p['salir_si_baja_de'] / p['precio'] - 1) * 100)}).")
    if p.get("estado") == "fuera":
        return (f"🔴 **{nombre_de(t)}**: la regla dice estar fuera (desde el {fecha(p['desde'])}). Se volvería a entrar "
                f"si supera {num(p['entrar_si_sube_de'], 0)} ({pct((p['entrar_si_sube_de'] / p['precio'] - 1) * 100)}).")
    return f"⚪ **{nombre_de(t)}**: sin datos suficientes."


def precio_eur(r: dict) -> float | None:
    """Precio en euros de una fila del informe (los antiguos no lo traen: solo valen los de euros)."""
    if r.get("precio_eur") is not None:
        return r["precio_eur"]
    return r["precio"] if costes.divisa(r["ticker"]) == "EUR" else None


def tarjeta_idea(r: dict, clave: str, peso: float = 0.0):
    """`peso`: parte de tu dinero que ya está en este valor (0 si no lo tienes)."""
    m = moneda_de(r["ticker"])
    etiqueta, color, _ = asesor.veredicto(r)
    with st.container(border=True):
        st.markdown(f"**{r['nombre']}** · {r['sector']}")
        if peso > limite_empresa():
            st.markdown(f":orange[**Ya tienes demasiada**] · pesa el {peso * 100:.0f} % de tu dinero: no compres "
                        "más aunque tenga buena nota.")
        else:
            st.markdown(f":{color}[**{etiqueta}**] · nota **{r.get('nota', '—')}**/100"
                        + (f" · ya la tienes ({peso * 100:.0f} %)" if peso > 0 else ""))
        partes = [f"{precio(r['precio'], m)}", f"último año {pct((r.get('momentum') or 0) * 100, 0)}"]
        if r.get("riesgo_nivel"):
            partes.append(f"riesgo de caída {ICONO_RIESGO[r['riesgo_nivel']]}")
        st.caption(" · ".join(partes))
        if st.button("Ver análisis y orden", key=f"idea_{clave}_{r['ticker']}", width="stretch"):
            ir_a("analizar", analizar_ticker=r["ticker"])


def cartera_del_perfil(inf: dict) -> tuple[str, dict] | None:
    """Cartera modelo (España) que encaja con el perfil guardado en 🎯 Mi plan."""
    p = cuenta_activa().get("perfil_inversor")
    if not p or not inf.get("carteras"):
        return None
    nombre = asesor.perfil_inversor(p["horizonte"], p["reaccion"], p["experiencia"], p["colchon"]).nombre
    for k, c in inf["carteras"].items():
        if c.get("universo", "global") == "espana" and nombre in c.get("perfiles", []):
            return k, c
    return None


# --------------------------------------------------------------------------- 🧭 Hoy
def pagina_hoy():
    pf = perfil()
    st.title("🧭 Hoy")
    inf = cargar_informe()
    cta = cuenta_activa()
    solo_mia = False
    if cta.get("posiciones"):
        solo_mia = st.toggle("🎯 Solo lo de mi cartera", value=cta.get("solo_mi_cartera", True),
                             help="Encendido: Hoy se centra en las acciones que ya tienes (esperar, diversificar o poner "
                                  "stop-loss) y oculta las ideas de compra nuevas. Apágalo para ver también ideas.")
        if solo_mia != cta.get("solo_mi_cartera", True):
            cta["solo_mi_cartera"] = solo_mia
            guardar_datos()
    bloque_pendientes()
    asesor_hoy(inf)
    if not inf:
        sin_informe()
        return
    aviso_antiguedad(inf)
    mer = inf["mercado"]
    tipo, titulo = COLOR_SEMAFORO[mer["semaforo"]]
    getattr(st, tipo)(f"**{titulo}.** {TEXTO_SEMAFORO[mer['semaforo']]}")
    fuera = [nombre_de(t) for t, p in inf.get("proteccion", {}).items() if p.get("estado") == "fuera"]
    if fuera:
        st.warning("🛡️ La regla de protección dice **estar fuera** de: " + ", ".join(fuera) + ". Si tienes un fondo "
                   "indexado de ese mercado y sigues esta regla, revisa 📦 Carteras modelo.")

    por_ticker = {r["ticker"]: r for r in inf["ranking"]}
    if solo_mia:
        mostrar_contexto(inf, mer)
        return
    st.subheader("💡 Ideas del día en España")
    st.caption("Las acciones españolas con mejor nota, de sectores distintos, con su mercado al alza, sin riesgo alto "
               "de caída y sin resultados inminentes. En Bankinter cuestan de 0 a 8 € por operación.")
    ideas = [por_ticker[t] for t in inf.get("ideas_es", []) if t in por_ticker]
    pesos = pesos_cartera_real()
    # Las que ya tienes de sobra, al final: no son ideas para ti hoy.
    tope = limite_empresa()
    ideas.sort(key=lambda r: pesos.get(r["ticker"], 0.0) > tope)
    if ideas:
        visibles = ideas[:3] if pf.movil else ideas
        cols = st.columns(1 if pf.movil else min(len(ideas), 3))
        for i, r in enumerate(visibles):
            with cols[i % len(cols)]:
                tarjeta_idea(r, "es", pesos.get(r["ticker"], 0.0))
        if len(ideas) > len(visibles):
            with st.expander(f"Ver {len(ideas) - len(visibles)} ideas más"):
                for r in ideas[len(visibles):]:
                    tarjeta_idea(r, "es", pesos.get(r["ticker"], 0.0))
    else:
        st.info("Hoy ninguna acción española cumple todas las condiciones. No pasa nada: sigue con tu aportación "
                "mensual al fondo indexado (🎯 Mi plan).")
    internacionales = [por_ticker[t] for t in inf.get("ideas", []) if t in por_ticker and not t.endswith(".MC")]
    if internacionales:
        with st.expander("🌍 Ideas internacionales (solo para importes grandes)"):
            st.caption("En Bankinter cada operación en el extranjero cuesta 20 €, más un 1 % si se cambia de divisa y "
                       "una custodia mínima de 24 € al año por valor: solo compensan con unos 5.000 € o más.")
            cols = st.columns(1 if pf.movil else min(len(internacionales), 3))
            for i, r in enumerate(internacionales):
                with cols[i % len(cols)]:
                    tarjeta_idea(r, "int")

    propia = cartera_del_perfil(inf)
    if propia:
        clave, c = propia
        nombres = [por_ticker.get(x["ticker"], {}).get("nombre", x["ticker"]) for x in c["composicion"]]
        st.subheader(f"📦 Tu cartera modelo: {c['nombre']}")
        st.markdown(("Este mes: " + ", ".join(nombres) + ".") if nombres else
                    "Este mes está **en liquidez** (el IBEX está en tendencia bajista).")
        st.caption("Se revisa una vez al mes. Detalle, órdenes y resultados en 📦 Carteras modelo.")
        if st.button("Ver mi cartera modelo", width="stretch"):
            ir_a("carteras")

    mostrar_contexto(inf, mer)


def mostrar_contexto(inf: dict, mer: dict) -> None:
    """Lo que se ve en Hoy en los dos modos: qué pasó otras veces, palabras de la página y noticias."""
    with st.expander("🔮 Qué ha pasado otras veces en una situación como la de hoy"):
        for t, nombre in (("^IBEX", "El IBEX 35"), ("^STOXX50E", "El Euro Stoxx 50"), ("^GSPC", "El S&P 500")):
            f = mer.get("fases", {}).get(t)
            if f:
                st.markdown("- " + texto_fase(nombre, f))
        st.caption("Estadísticas de lo que pasó en situaciones parecidas del pasado, no una garantía.")

    palabras_de_la_pagina(["Semáforo", "Regla de protección", "Veredicto", "Nota global", "Riesgo de caída",
                           "Cartera modelo", "Momentum", "Diversificación"])
    noticias_importantes(inf)


@st.fragment(run_every=SEGUNDOS_REFRESCO)
def noticias_importantes(inf: dict):
    """Las 3 noticias de más impacto ahora mismo (si no se pueden leer, las del informe de la noche)."""
    st.subheader("📰 Lo más importante")
    try:
        lista, _ = cargar_noticias()
    except Exception:  # noqa: BLE001
        lista = []
    if lista:
        recientes = [n for n in lista if n.horas is None or n.horas <= 24] or lista
        top = [{"titulo": n.titulo, "enlace": n.enlace, "sentimiento": n.sentimiento, "resumen": n.resumen,
                "empresas": n.empresas, "explicaciones": n.explicaciones,
                "cuando": f"{n.fuente.split(' · ')[0]} · {noticias.hace_cuanto(n)}"} for n in recientes[:3]]
        st.caption(linea_frescura(lista) + ". Todas en 📰 Noticias.")
    else:
        top = (inf.get("noticias") or {}).get("top", [])[:3]
        st.caption("Ahora no se pueden leer las fuentes: estas son las del informe de esta noche.")
    vistas = set()
    for n in top:
        icono = {1: "🟢", -1: "🔴", 0: "⚪"}[n["sentimiento"]]
        st.markdown(f"{icono} [{n['titulo']}]({n['enlace']})" + (f"  \n<small>{n['cuando']}</small>"
                                                                 if n.get("cuando") else ""),
                    unsafe_allow_html=True)
        c = conclusion_noticia(n["titulo"], n.get("resumen", ""), n.get("empresas", []), n["sentimiento"])
        if c and (c["titulo"], c["oportunidad"]) in vistas:
            st.caption("↑ Misma lectura que la noticia anterior.")
        elif c:
            vistas.add((c["titulo"], c["oportunidad"]))
            donde = c["donde"].split(". ")[0].split(" · ")[0]
            st.markdown(f"<small>{c['icono']} **{c['titulo']}** · {donde}: {c['oportunidad']}"
                        + (f" 📌 **{c['te_afecta']}**" if c["te_afecta"] else "") + "</small>",
                        unsafe_allow_html=True)
        elif n.get("explicaciones"):
            st.caption("💡 " + n["explicaciones"][0])


# --------------------------------------------------------------------------- escenarios
def bloque_que_puede_pasar(pesos: dict[str, float], importe: float, mensual: float = 0.0, anos: int = 10):
    """Escenarios a 1 año (con la historia real de esos productos) y pruebas de estrés en crisis reales."""
    pf = perfil()
    if not pesos or importe <= 0:
        st.caption("Introduce un importe para ver escenarios.")
        return
    with st.spinner("Calculando escenarios con 10 años de historia real..."):
        hist = cargar_varios(tuple(sorted(pesos)), "10y")
        rets = patrones.rentabilidades_cartera(hist, pesos)
        esc = patrones.escenarios(rets)
        estres = patrones.prueba_estres(hist, pesos)
    if not esc:
        st.caption("No hay historia suficiente para calcular escenarios.")
        return
    c = st.columns(2 if pf.movil else 3)
    c[0].metric("Año malo (1 de cada 20)", eur(importe * (1 + esc["p5"])), pct(esc["p5"] * 100, 1))
    c[1 % len(c)].metric("Año normal", eur(importe * (1 + esc["p50"])), pct(esc["p50"] * 100, 1))
    c[2 % len(c)].metric("Año bueno (1 de cada 20)", eur(importe * (1 + esc["p95"])), pct(esc["p95"] * 100, 1))
    st.caption(f"Probabilidad de acabar un año en pérdidas: **{esc['prob_perdida'] * 100:.0f}%**. "
               f"Durante el año, lo normal es ver en algún momento una caída de {pct(esc['caida_tipica'] * 100, 0)}, "
               f"y en un año malo de {pct(esc['caida_mala'] * 100, 0)}. "
               f"(Calculado remuestreando {esc['anos_historia']} años de historia real de estos productos.)")
    if estres:
        st.markdown("**Si se repitiera una crisis real:**")
        st.dataframe(pd.DataFrame([{"Crisis": e["crisis"], "Cambio": pct(e["cambio"] * 100, 1),
                                    "Tus euros": eur(importe * e["cambio"])} for e in estres]),
                     hide_index=True, width="stretch")
        st.caption("Todas estas crisis se recuperaron con el tiempo, pero solo quien no vendió con pánico lo vivió.")
    if mensual or anos:
        rent = max(min(esc["p50"] * 100, 9.0), 0.0)
        filas = simular_aportaciones(mensual, anos, rent, importe)
        f = filas[-1]
        st.caption(f"Proyección a {anos} años con un rendimiento anual de {rent:.1f}% (el escenario normal): "
                   f"aportarías {eur(f['Aportado'])} y tendrías unos **{eur(f['Valor'])}**. No está garantizado.")


# --------------------------------------------------------------------------- 📡 Radar
@st.fragment(run_every=SEGUNDOS_REFRESCO)
def tabla_radar(f: pd.DataFrame, ideas: set[str]):
    """La tabla del radar con los precios de ahora. Se refresca sola cada minuto."""
    pf = perfil()
    precios = cotizaciones_ahora(f["ticker"].tolist(), esperar=False)
    del_informe = dict(zip(f["ticker"], f["precio"])) if "precio" in f else {}

    def precio_txt(t: str, divisa) -> str:
        q = precios.get(t)
        p = q["precio"] if q else del_informe.get(t)
        if p is None or pd.isna(p):
            return "—"
        return f"{num(p, 2)} {'€' if divisa in (None, 'EUR') or t.endswith('.MC') else divisa}"

    tabla = pd.DataFrame({
        "": ["⭐" if t in ideas else "" for t in f["ticker"]],
        "Empresa": f["nombre"],
        "Precio": [precio_txt(t, d) for t, d in zip(f["ticker"], f.get("divisa", [None] * len(f)))],
        "Hoy (%)": [round(precios[t]["variacion_pct"], 2) if precios.get(t, {}).get("variacion_pct") is not None
                    else None for t in f["ticker"]],
        "Cotización": [texto_estado_precio(precios[t]) if t in precios else "cierre (cargando…)" for t in f["ticker"]],
        "Veredicto": f["veredicto_txt"], "Nota": f["nota"],
        "Riesgo de caída": f["riesgo_nivel"].map(ICONO_RIESGO),
        "Último año (%)": (f["momentum"] * 100).round(0),
        "Mercado": f["mercado"], "Ticker": f["ticker"],
    })
    if pf.movil:
        tabla = tabla[["", "Empresa", "Precio", "Hoy (%)", "Nota", "Ticker"]]
    st.caption(f"{len(tabla)} valores ordenados por **nota global** (100 = la mejor hoy). ⭐ = idea del día. "
               "**Toca una fila** para ver su análisis y la orden para Bankinter.")
    st.caption("💶 **Precio**: con la bolsa abierta, el de ahora (Yahoo, unos 15 minutos de retraso; en tiempo real "
               "para EEUU si tienes Finnhub); con la bolsa cerrada, el cierre de la última sesión. Se actualiza cada "
               "minuto.")
    sel = st.dataframe(tabla, hide_index=True, width="stretch", height=min(38 * len(tabla) + 40, 900),
                       on_select="rerun", selection_mode="single-row",
                       column_config={"Nota": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d"),
                                      "Hoy (%)": st.column_config.NumberColumn(format="%+.2f %%"),
                                      "Ticker": None})
    filas = sel.selection.rows if sel and sel.selection else []
    if filas:
        ir_a("analizar", analizar_ticker=tabla.iloc[filas[0]]["Ticker"])
    st.caption(linea_actualizado())


def pagina_radar_global() -> bool:
    """Radar con todas las empresas del informe. Devuelve False si no hay informe."""
    pf = perfil()
    inf = cargar_informe()
    if not inf:
        return False
    st.title("📡 Radar")
    aviso_antiguedad(inf)
    df = pd.DataFrame(inf["ranking"])
    df = df[~df["etf"]]
    ideas = set(inf.get("ideas_es", [])) | set(inf.get("ideas", []))
    c = st.columns(1 if pf.movil else 3)
    ambito = c[0].segmented_control("Acciones", ["España", "Todas"], default="España",
                                    help="España: comisión de 0 a 8 € en Bankinter. Todas: incluye Europa y EEUU "
                                         "(20 € por operación + divisa).") or "España"
    sectores = sorted(df["sector"].dropna().unique())
    sector = c[1 % len(c)].selectbox("Sector", ["Todos"] + sectores)
    solo = c[2 % len(c)].toggle("Solo candidatas a comprar", value=False)
    buscar = st.text_input("Buscar empresa", "").strip().lower()
    f = df if ambito == "Todas" else df[df["ticker"].str.endswith(".MC")]
    if sector != "Todos":
        f = f[f["sector"] == sector]
    veredictos = [asesor.veredicto(r) for r in f.to_dict("records")]
    f = f.assign(veredicto_txt=[v[0] for v in veredictos])
    if solo:
        f = f[f["veredicto_txt"] == "Candidata a comprar"]
    if buscar:
        f = f[f["nombre"].str.lower().str.contains(buscar) | f["ticker"].str.lower().str.contains(buscar)]
    tabla_radar(f, ideas)
    with st.expander("¿Qué significa cada columna?"):
        st.markdown("- **Veredicto**: la conclusión de la app (la misma que verás al analizarla).\n"
                    "- **Nota**: puesto frente a todas las demás combinando subida del último año (50 %), tendencia "
                    "(30 %) y menor riesgo de caída (20 %), lo que ha funcionado con datos reales.\n"
                    "- **Riesgo de caída**: probabilidad de caer más de un 10 % en el próximo mes frente a lo normal.")
    return True


# --------------------------------------------------------------------------- bloques para Analizar
def bloque_que_puede_pasar_accion(ticker: str, df: pd.DataFrame, importe: float):
    """Escenarios a 1 año y crisis reales para una sola acción."""
    pf = perfil()
    rets = df["Close"].pct_change().dropna()
    esc = patrones.escenarios(rets)
    estres = patrones.prueba_estres({ticker: df}, {ticker: 1.0})
    if not esc:
        return
    st.caption(f"Con {eur(importe)} invertidos durante 1 año, según {esc['anos_historia']} años de su historia:")
    c = st.columns(2 if pf.movil else 3)
    c[0].metric("Año malo (1 de cada 20)", pct(esc["p5"] * 100, 0), eur(importe * esc["p5"]), delta_color="off", delta_arrow="off")
    c[1 % len(c)].metric("Año normal", pct(esc["p50"] * 100, 0), eur(importe * esc["p50"]), delta_color="off", delta_arrow="off")
    c[2 % len(c)].metric("Año bueno (1 de cada 20)", pct(esc["p95"] * 100, 0), eur(importe * esc["p95"]),
                         delta_color="off", delta_arrow="off")
    if estres:
        st.caption("En crisis reales: " + " · ".join(f"{e['crisis']}: {pct(e['cambio'] * 100, 0)}" for e in estres))


def bloque_fases(inf: dict | None):
    if not inf:
        return
    mer = inf["mercado"]
    st.subheader("🧭 Fase de cada mercado y qué pasó después en el pasado")
    for t in ("^IBEX", "^STOXX50E", "^GSPC"):
        f = mer.get("fases", {}).get(t)
        if not f:
            continue
        with st.container(border=True):
            st.markdown(texto_fase(nombre_de(t), f))
            st.caption(f["explicacion"])
            filas = []
            for h, s in f["horizontes"].items():
                if s.get("prob_sube") is None:
                    continue
                g = f["todas"][h]
                filas.append({"Plazo": h, "Subió (esta fase)": f"{s['prob_sube'] * 100:.0f}%",
                              "Subió (siempre)": f"{g['prob_sube'] * 100:.0f}%",
                              "Lo normal": f"{pct(s['p10'] * 100, 0)} a {pct(s['p90'] * 100, 0)}",
                              "Peor caso": pct(s["peor"] * 100, 0), "Casos": s["casos"]})
            if filas:
                tabla = pd.DataFrame(filas)
                if perfil().movil:
                    tabla = tabla[["Plazo", "Subió (esta fase)", "Peor caso"]]
                st.dataframe(tabla, hide_index=True, width="stretch")
    with st.expander("📉 Las peores caídas de la historia y cuánto tardaron en recuperarse"):
        for t in ("^IBEX", "^GSPC"):
            caidas = mer.get("peores_caidas", {}).get(t, [])
            if caidas:
                st.markdown(f"**{nombre_de(t)}**")
                st.dataframe(pd.DataFrame([{
                    "Empezó": c["inicio"], "Fondo": c["fondo"], "Caída": pct(c["caida"] * 100, 0),
                    "Recuperado": c["recuperado"] or "aún no",
                    "Años en recuperar": f"{c['dias_recuperar'] / 365:.1f}" if c["dias_recuperar"] else "—"}
                    for c in caidas]), hide_index=True, width="stretch")
        st.caption("Lección: las caídas fuertes ocurren cada pocos años. Quien invierte a largo plazo y no vende "
                   "con pánico ha acabado recuperándose; quien necesitaba el dinero en mal momento, no.")


# --------------------------------------------------------------------------- resultados del entrenamiento diario
def bloque_entrenamiento_diario():
    inf = cargar_informe()
    if not inf:
        sin_informe()
        return
    pf = perfil()
    e = inf["estrategia"]
    m = inf["modelo"]
    st.markdown(f"Cada noche el modelo conjunto se reentrena con **{m['metricas']['casos']:,}".replace(",", ".")
                + f" situaciones de {m['metricas']['acciones']} valores**, y cada semana la estrategia prueba "
                f"**{e.get('iteraciones', '—')} combinaciones de reglas** con {e.get('acciones', '—')} acciones "
                f"(último entrenamiento: {e.get('fecha', '—')}).")
    if inf.get("modelo_riesgo"):
        bloque_un_modelo(inf["modelo_riesgo"], "🛡️ Modelo de riesgo de caída fuerte (el que sí funciona)", riesgo=True)
    bloque_un_modelo(m, "🎲 Modelo de dirección: ¿subirá en 1 mes? (se publica por transparencia)")

    if e.get("fuera_de_muestra"):
        st.subheader("🏋️ Estrategia completa: años no vistos")
        from paginas_extra import tarjetas_metricas, veredicto_simulacion
        cols = st.columns(1 if pf.movil else 3)
        tarjetas_metricas(e["fuera_de_muestra"], "Estrategia entrenada", 10_000, cols[0])
        tarjetas_metricas(e["por_defecto"], "Reglas por defecto", 10_000, cols[1 % len(cols)])
        tarjetas_metricas(e["comprar_y_mantener"], "Comprar y mantener", 10_000, cols[2 % len(cols)])
        curvas = pd.DataFrame({k: pd.Series(v["valores"], index=pd.to_datetime(v["fechas"]))
                               for k, v in e.get("curvas", {}).items()})
        if not curvas.empty:
            st.line_chart(reducir(curvas), height=300 if pf.movil else 380)
        veredicto_simulacion(e["fuera_de_muestra"], e["comprar_y_mantener"])
        from bolsa.simulador import Parametros
        with st.expander("Reglas vigentes"):
            for linea in Parametros.desde_dict(e["parametros"]).describir():
                st.markdown(f"- {linea}")


def bloque_un_modelo(mod: dict, titulo: str, riesgo: bool = False):
    pf = perfil()
    mm = mod["metricas"]
    st.subheader(titulo)
    c = st.columns(2 if pf.movil else 3)
    c[0].metric("AUC (0,5 = azar)", f"{mm['auc']:.3f}", nivel_auc(mm["auc"]), delta_color="off", delta_arrow="off")
    if riesgo:
        cal = pd.DataFrame(mod["calibracion"])
        c[1 % len(c)].metric("Caídas con riesgo 'muy bajo'", f"{cal['sube'].iloc[0] * 100:.0f}%")
        c[2 % len(c)].metric("Caídas con riesgo 'muy alto'", f"{cal['sube'].iloc[-1] * 100:.0f}%",
                             f"media {mm['tasa_subidas'] * 100:.0f}%", delta_color="off", delta_arrow="off")
        st.caption("Frecuencia real con la que la acción llegó a caer más de un 10% en el mes siguiente, según el "
                   "riesgo que había estimado el modelo, en años que no había visto.")
    else:
        c[1 % len(c)].metric("Acierto de dirección a 1 mes", f"{mm['acierto'] * 100:.1f}%",
                             f"azar {mm['referencia'] * 100:.1f}%", delta_color="off", delta_arrow="off")
        c[2 % len(c)].metric("20% mejor valoradas (al mes)", pct(mm["mejores_mes"] * 100, 2),
                             f"todas {pct(mm['todos_mes'] * 100, 2)}", delta_color="off", delta_arrow="off")
    st.caption(f"{mm['casos']:,} casos de {mm['acciones']} valores ({mm['desde']} → {mm['hasta']}). ".replace(",", ".")
               + f"Fiabilidad: **{mod['fiabilidad']}**.")
    cal = pd.DataFrame(mod["calibracion"])
    if not cal.empty:
        with st.expander("📏 Calibración: lo que dijo el modelo y lo que pasó de verdad"):
            st.dataframe(pd.DataFrame({
                "El modelo decía": [f"{a * 100:.0f}-{b * 100:.0f}%" for a, b in zip(cal["p_min"], cal["p_max"])],
                "Ocurrió de verdad": (cal["sube"] * 100).round(0).astype(int).astype(str) + "%",
                "Rentabilidad media": [pct(x * 100, 1) for x in cal["rent_media"]],
                "Casos": cal["casos"]}), hide_index=True, width="stretch")
            st.caption("Si 'Ocurrió de verdad' cambia claramente de arriba abajo, el modelo distingue algo real. "
                       "La app siempre te enseña lo que ocurrió de verdad, no la cifra bruta del modelo.")
    if mod.get("importancia"):
        with st.expander("🔎 Qué patrones pesan más"):
            st.bar_chart(pd.DataFrame(mod["importancia"]).set_index("dato")["peso"], horizontal=True)
    if mod.get("por_ano"):
        with st.expander("📆 Año a año"):
            pa = pd.DataFrame(mod["por_ano"])
            st.dataframe(pd.DataFrame({"Año": pa["ano"], "AUC": pa["auc"].round(3),
                                       "Acierto": (pa["acierto"] * 100).round(1),
                                       "Frecuencia real %": (pa["tasa_subidas"] * 100).round(1), "Casos": pa["casos"]}),
                         hide_index=True, width="stretch")


# --------------------------------------------------------------------------- 📦 Carteras modelo
def mostrar_cartera(k: str, c: dict, por_ticker: dict, sugerida: bool):
    pf = perfil()
    if sugerida:
        st.success("👉 Es la que encaja con tu perfil (🎯 Mi plan).")
    st.caption(estrategias.CARTERAS[k].descripcion if k in estrategias.CARTERAS else c["descripcion"])
    m, ref = c["metricas"], c["referencia"]
    cols = st.columns(2 if pf.movil else 3)
    cols[0].metric("Rentabilidad al año (simulada)", pct(m["cagr_pct"]), f"todas: {pct(ref['cagr_pct'])}",
                   delta_color="off", delta_arrow="off")
    cols[1 % len(cols)].metric("Peor caída", pct(m["max_caida_pct"], 0), f"todas: {pct(ref['max_caida_pct'], 0)}",
                               delta_color="off", delta_arrow="off")
    cols[2 % len(cols)].metric("Comisiones pagadas", eur(m["gastos"]), f"{m['operaciones']} operaciones",
                               delta_color="off", delta_arrow="off")
    curvas = pd.DataFrame({"Esta cartera": pd.Series(c["curva"]["valores"], index=pd.to_datetime(c["curva"]["fechas"])),
                           "Todas a partes iguales": pd.Series(c["curva_referencia"]["valores"],
                                                               index=pd.to_datetime(c["curva_referencia"]["fechas"]))})
    st.line_chart(reducir(curvas), height=240 if pf.movil else 320)
    st.caption(f"Qué habría pasado con {eur(c.get('capital_simulado', 10_000), '€').replace(',00', '')} invertidos desde "
               f"el {fecha(m['desde'])} siguiendo la regla, en euros y con las comisiones reales de Bankinter "
               "(gráfico escalado a 10.000 €; sin IRPF). «Todas a partes iguales» es la referencia: comprar todas las "
               "acciones de su grupo.")
    with st.expander("📆 Año a año"):
        st.dataframe(pd.DataFrame([{"Año": a["ano"], "Esta cartera": pct(a["cartera"]),
                                    "Todas a partes iguales": pct(a["todas"])} for a in c["por_ano"]]),
                     hide_index=True, width="stretch")
    st.markdown("**Composición de este mes**")
    if not c["composicion"]:
        st.info("Este mes la cartera está en **liquidez**: su mercado está en tendencia bajista. La regla vuelve a "
                "comprar cuando se recupere.")
        return
    minimo = c["n"] * (asesor.MINIMO_POR_ACCION if c.get("universo") == "espana" else asesor.MINIMO_INTERNACIONAL)
    importe = st.number_input("¿Cuánto quieres dedicar a esta cartera? (€)", 1_000.0, 10_000_000.0,
                              float(minimo), 500.0, key=f"imp_{k}")
    por_valor = importe / c["n"]
    filas, ordenes = [], []
    for x in c["composicion"]:
        r = por_ticker.get(x["ticker"], {})
        n = int(por_valor // x["precio_eur"]) if x.get("precio_eur") else 0
        local = r.get("precio")
        filas.append({"Empresa": r.get("nombre", x["ticker"]), "Sector": r.get("sector", "—"), "Títulos": n,
                      "Importe": eur(n * x["precio_eur"]) if x.get("precio_eur") else "—",
                      "Riesgo de caída": ICONO_RIESGO.get(r.get("riesgo_nivel"))})
        if n and local:
            ordenes.append(bankinter.ticket_compra(x["ticker"], n, local, dias_validez=3, tarifa=pf.tarifa,
                                                   importe_eur=n * x["precio_eur"]))
    st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch")
    if por_valor < (asesor.MINIMO_POR_ACCION if c.get("universo") == "espana" else asesor.MINIMO_INTERNACIONAL):
        st.warning(f"Con {eur(por_valor)} por empresa, las comisiones se comerían buena parte de la ganancia. "
                   "Dedica más dinero o usa un fondo indexado.")
    st.caption("Cómo seguirla: el primer día hábil de cada mes, vende las que ya no estén en la lista, compra las "
               "nuevas y reparte a partes iguales. Esta cartera no usa stop-loss: su protección es la revisión mensual"
               + (" y salir a liquidez si el mercado entra en tendencia bajista." if c.get("filtro_mercado") else "."))
    with st.expander("📋 Órdenes para copiar en Bankinter"):
        for o in ordenes:
            st.code(o, language=None)


def pagina_carteras():
    st.title("📦 Carteras modelo")
    inf = cargar_informe()
    if not inf or not inf.get("carteras"):
        sin_informe()
        return
    aviso_antiguedad(inf)
    st.markdown("Formas sencillas de invertir en acciones que **han funcionado con datos reales**. Se revisan **una vez "
                "al mes**: lo contrario de estar comprando y vendiendo cada día.")
    st.warning("⚠️ Las simulaciones usan las empresas que cotizan **hoy**; las que fracasaron por el camino no están, "
               "y eso hace los resultados algo optimistas. Rentabilidades pasadas no garantizan las futuras. Úsalas "
               "solo para la parte de acciones de tu plan (🎯 Mi plan).")
    por_ticker = {r["ticker"]: r for r in inf["ranking"]}
    propia = cartera_del_perfil(inf)
    espana = {k: c for k, c in inf["carteras"].items() if c.get("universo") == "espana"}
    internacional = {k: c for k, c in inf["carteras"].items() if c.get("universo", "global") == "global"}
    if espana:
        st.subheader("🇪🇸 Con acciones españolas (recomendado en Bankinter)")
        tabs = pestanas([c["nombre"] for c in espana.values()], "cm_es")
        for tab, (k, c) in zip(tabs, espana.items()):
            with tab:
                if tab.open:
                    mostrar_cartera(k, c, por_ticker, bool(propia and propia[0] == k))
    if internacional:
        with st.expander("🌍 Internacionales (España, Europa y EEUU) · solo para importes grandes"):
            st.caption("Cada operación en el extranjero cuesta 20 € en Bankinter, más un 1 % de cambio de divisa en "
                       "acciones en dólares y una custodia mínima de 24 € al año por valor. Por eso estas carteras se "
                       "simulan con unos 5.000 € por empresa.")
            tabs = pestanas([c["nombre"] for c in internacional.values()], "cm_int")
            for tab, (k, c) in zip(tabs, internacional.items()):
                with tab:
                    if tab.open:
                        mostrar_cartera(k, c, por_ticker, False)

    st.header("🛡️ Regla de protección para tus fondos indexados")
    st.markdown("Para la parte de tu dinero en fondos indexados: **seguir invertido mientras el índice esté por encima "
                "de su media de 200 sesiones, y pasar a un fondo monetario solo si cae más de un 2 % por debajo**. "
                "Volver a entrar cuando supere la media en un 2 %.")
    filas = []
    for t, p in inf.get("proteccion", {}).items():
        st.markdown("- " + texto_proteccion(t, p))
        h = p.get("historia", {})
        if h:
            filas.append({"Índice": nombre_de(t), "Desde": h["mantener"]["desde"][:4],
                          "Sin la regla": f"{pct(h['mantener']['cagr_pct'])} al año · peor caída "
                                          f"{pct(h['mantener']['max_caida_pct'], 0)}",
                          "Con la regla": f"{pct(h['filtro']['cagr_pct'])} al año · peor caída "
                                          f"{pct(h['filtro']['max_caida_pct'], 0)}",
                          "Cambios al año": num(h["cambios_por_ano"], 1)})
    if filas:
        st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch")
        st.caption("Índices sin dividendos; con la regla, el tiempo fuera se remunera al 2 % anual. La regla no evita "
                   "las caídas muy rápidas (como marzo de 2020), pero sí las largas (2000-2003, 2008).")
    st.info("💡 **Fiscalidad en España**: entre **fondos de inversión** puedes hacer *traspasos* sin pagar impuestos. "
            "Si vas a aplicar esta regla, hazlo con un fondo indexado y un fondo monetario, no con ETF: vender un ETF "
            "tributa y en Bankinter cada operación con un ETF extranjero cuesta 20 €.")


def bloque_historial_ideas():
    inf = cargar_informe()
    if not inf:
        return
    h = inf.get("historial_ideas", {})
    st.subheader("📅 Acierto real de las ideas del día (en tiempo real)")
    st.caption("Cada idea del día se guarda en el momento y, un mes después, se comprueba qué pasó. Es la prueba "
               "más honesta: nadie conocía el futuro cuando se dio la idea.")
    if not h.get("evaluadas"):
        st.info(f"Aún no hay ideas con un mes de antigüedad ({h.get('pendientes', 0)} pendientes de evaluar). "
                "Este historial irá creciendo cada día.")
        return
    c = st.columns(3)
    c[0].metric("Ideas evaluadas", h["evaluadas"])
    c[1].metric("Subieron en 1 mes", f"{h['suben'] * 100:.0f}%", pct(h["rent_media"] * 100, 2))
    if h.get("baten_indice") is not None:
        c[2].metric("Batieron a su índice", f"{h['baten_indice'] * 100:.0f}%", pct(h["exceso_medio"] * 100, 2))
    ult = pd.DataFrame(h.get("ultimas", []))
    if not ult.empty:
        ult["Empresa"] = ult["ticker"].map(nombre_de)
        st.dataframe(pd.DataFrame({"Fecha": ult["fecha"], "Empresa": ult["Empresa"],
                                   "1 mes después": [pct(x * 100, 1) for x in ult["ret"]],
                                   "Su índice": [pct(x * 100, 1) if pd.notna(x) else "—" for x in ult["ret_indice"]]}),
                     hide_index=True, width="stretch")
    pn = inf.get("patron_noticias", {})
    if pn.get("dias", 0) >= 30 and pn.get("correlacion") is not None:
        st.subheader("📰 ¿Anticipan algo las noticias?")
        st.markdown(f"Con {pn['dias']} días archivados: la semana siguiente a días de noticias muy positivas el IBEX "
                    f"se movió de media {pct((pn['semana_tras_positivas'] or 0) * 100, 2)}, y tras días muy negativos "
                    f"{pct((pn['semana_tras_negativas'] or 0) * 100, 2)} (media de todas las semanas: "
                    f"{pct(pn['semana_media'] * 100, 2)}).")
    elif pn:
        st.caption(f"📰 Archivo de noticias: {pn.get('dias', 0)} días. Con al menos 30 se empezará a medir si el tono "
                   "de las noticias anticipa los movimientos del mercado.")


# --------------------------------------------------------------------------- laboratorio
RUTA_LAB = Path(__file__).resolve().parent / "informe" / "experimentos.json"


@st.cache_data(ttl=3600, show_spinner=False)
def _leer_lab(mtime: float) -> dict | None:
    try:
        return json.loads(RUTA_LAB.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def cargar_laboratorio() -> dict | None:
    return _leer_lab(RUTA_LAB.stat().st_mtime) if RUTA_LAB.exists() else None


def nivel_auc(auc: float | None) -> str:
    if auc is None:
        return "—"
    if auc >= 0.65:
        return "🟢 Bastante predecible"
    if auc >= 0.58:
        return "🟡 Algo predecible"
    if auc >= 0.53:
        return "🟠 Muy poco"
    return "🔴 Azar"


def bloque_laboratorio():
    lab = cargar_laboratorio()
    if not lab:
        return
    pf = perfil()
    st.subheader("🔬 Laboratorio: qué funciona de verdad (datos reales, años no vistos)")
    st.caption(f"Última revisión: {lab.get('fecha', '—')}. Se repite automáticamente cada mes con datos nuevos.")
    filas = []
    for nombre, m in lab.get("modelos", {}).items():
        filas.append({"Pregunta": m.get("pregunta", nombre), "¿Se puede predecir?": nivel_auc(m.get("auc")),
                      "AUC": round(m["auc"], 3) if m.get("auc") is not None else None,
                      "Ocurre si el modelo dice 'poco probable'": f"{m['tramo_bajo'] * 100:.0f}%",
                      "Ocurre si dice 'muy probable'": f"{m['tramo_alto'] * 100:.0f}%"})
    if filas:
        st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch")
        st.caption("AUC: 0,50 = lanzar una moneda; 0,55-0,60 ya es útil en bolsa; más de 0,65 es una señal fuerte. "
                   "Las columnas de la derecha dicen con qué frecuencia ocurrió de verdad lo que el modelo predecía.")
    rot = pd.DataFrame(lab.get("rotacion", []))
    if not rot.empty:
        st.markdown("**Carteras mensuales: quedarse cada mes con las N mejores según cada criterio**")
        rot = rot.sort_values("sharpe", ascending=False)
        tabla = pd.DataFrame({
            "Criterio": rot["senal"], "N": rot["n"], "Filtro mercado": rot["filtro_mercado"].map({True: "sí", False: "no"}),
            "Rentab. anual %": rot["cagr_pct"].round(1), "Peor caída %": rot["max_caida_pct"].round(1),
            "Rentab./riesgo": rot["sharpe"].round(2), "Comisiones €": rot["gastos"].round(0)})
        if pf.movil:
            tabla = tabla[["Criterio", "N", "Rentab. anual %", "Peor caída %"]]
        st.dataframe(tabla, hide_index=True, width="stretch", height=380)
        ref = rot[rot["senal"] == "Todas a partes iguales"]
        if len(ref):
            r = ref.iloc[0]
            st.caption(f"Referencia (todas las acciones a partes iguales): {r['cagr_pct']:.1f}% al año con una peor "
                       f"caída de {r['max_caida_pct']:.0f}%. Periodo {r['desde']} → {r['hasta']}. Rentab./riesgo = "
                       "rentabilidad dividida por la volatilidad (más alto = mejor relación ganancia/sustos).")
    idx = lab.get("indices", {})
    if idx:
        st.markdown("**Índices: ¿protege salir cuando el índice cae por debajo de su media?** (historia completa)")
        filas = []
        for t, variantes in idx.items():
            for v in variantes:
                filas.append({"Índice": nombre_de(t), "Regla": f"media {v['media']}" + (f" ±{v['banda']:.0%}" if v["banda"] else ""),
                              "Mantener %/año": round(v["mantener"]["cagr_pct"], 1),
                              "Mantener peor caída": f"{v['mantener']['max_caida_pct']:.0f}%",
                              "Con filtro %/año": round(v["filtro"]["cagr_pct"], 1),
                              "Con filtro peor caída": f"{v['filtro']['max_caida_pct']:.0f}%",
                              "Tiempo invertido": f"{v['tiempo_invertido']:.0%}",
                              "Desde": v["mantener"]["desde"][:4]})
        st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch")
