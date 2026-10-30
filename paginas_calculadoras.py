"""Página Calculadoras: cuánto comprar, costes e interés compuesto."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from bolsa import costes, letras, libertad
from ui_comun import lineas, alto_grafico, cuenta_activa, perfil, pestanas, privado, reducir
from ui_comun import (cargar_fundamentales, cargar_historico, cotizaciones_ahora, datos_usuario, fx, moneda_de,
                      mostrar_plotly, num, pct, selector_valor)
from ui_comun import precio as eur  # importes de ejemplo: se ven también en modo privado


def pagina_calculadoras():
    pf = perfil()
    movil, tarifa = pf.movil, pf.tarifa
    st.title("🧮 Calculadoras")
    t0, t1, t2, t3, t4, t5 = pestanas(["🎯 Orden limitada", "💶 Coste", "🏛️ Impuestos", "🌱 Cada mes",
                                       "🏖️ Libertad financiera", "📜 Letras del Tesoro"], "calc_pestana")
    with t0:
        if t0.open:
            calculadora_orden("orden")
    with t5:
        calculadora_letras(movil)
    with t4:
        if t4.open:          # la única que descarga datos (tu cartera)
            calculadora_libertad()
    with t1:
        st.caption("Cuánto te cuesta en Bankinter comprar, mantener un año y vender, según dónde cotice el valor.")
        importe = st.number_input("Importe que vas a invertir (€)", 50.0, 1_000_000.0, 1000.0, 50.0)
        tipos_valor = {"Acción española (IBEX, Mercado Continuo)": "SAN.MC",
                       "Acción europea en euros (Alemania, Países Bajos...)": "SAP.DE",
                       "Acción francesa (paga tasa Tobin del 0,4 %)": "MC.PA",
                       "Acción de EEUU (en dólares)": "AAPL"}
        tipo = st.radio("¿Qué vas a comprar?", list(tipos_valor))
        ref = tipos_valor[tipo]
        cc = costes.coste_compra(importe, ref, tarifa)
        iv = costes.coste_ida_y_vuelta(importe, ref, tarifa)
        c = st.columns(2 if movil else 3)
        c[0].metric("Al comprar", eur(cc["total"]), f"{cc['pct']:.2f} %".replace(".", ","), delta_color="off", delta_arrow="off")
        c[1 % len(c)].metric("Al vender", eur(iv["venta"]))
        c[2 % len(c)].metric("Custodia (1 año)", eur(iv["custodia"]))
        detalle = [f"comisión {eur(cc['comision'])}"]
        if cc["cambio"]:
            detalle.append(f"cambio de divisa {eur(cc['cambio'])}")
        if cc["itf"]:
            detalle.append(f"tasa Tobin {eur(cc['itf'])}")
        st.caption("Compra: " + " + ".join(detalle) + ".")
        pct_total = f"{iv['pct']:.2f}".replace(".", ",")
        st.markdown(f"**En total, comprar, mantener un año y vender cuesta {eur(iv['total'])} ({pct_total} %)**: "
                    "la inversión tiene que subir al menos eso para que empieces a ganar.")
        if iv["pct"] > 2:
            st.warning("Es un coste alto para este importe. Con poco dinero, las acciones españolas o un fondo "
                       "indexado (sin comisión por aportación) salen mucho más baratos.")
    with t2:
        compra = st.number_input("Precio total de compra (€)", 0.0, 10_000_000.0, 1000.0, 50.0)
        venta = st.number_input("Precio total de venta (€)", 0.0, 10_000_000.0, 1300.0, 50.0)
        g = venta - compra
        imp = costes.impuesto_ganancia(g)
        c = st.columns(2 if movil else 3)
        c[0].metric("Ganancia", eur(g))
        c[1 % len(c)].metric("IRPF aproximado", eur(imp))
        c[2 % len(c)].metric("Te queda limpio", eur(g - imp))
        st.caption("Tramos del ahorro: 19% hasta 6.000 €, 21% hasta 50.000 €, 23% hasta 200.000 €, "
                   "27% hasta 300.000 €, 30% a partir de ahí. Las pérdidas se pueden compensar con ganancias "
                   "(durante 4 años). Ojo con la 'regla de los 2 meses': si vendes con pérdidas y compras la "
                   "misma acción en los 2 meses anteriores o posteriores (y la conservas), no puedes aplicar esa "
                   "pérdida todavía. "
                   "Bankinter te envía el informe fiscal para la declaración.")
    with t3:
        st.write("Para la mayoría de personas, la forma más eficaz de hacer crecer el dinero es **aportar una "
                 "cantidad fija cada mes a un fondo indexado** mundial, sin intentar adivinar el mejor momento.")
        c = st.columns(2 if movil else 4)
        inicial = c[0].number_input("Dinero inicial (€)", 0.0, 1_000_000.0, 1000.0, 100.0)
        mensual = c[1].number_input("Aportación mensual (€)", 0.0, 10_000.0, 150.0, 10.0)
        anos = c[2 % len(c)].slider("Años", 1, 40, 15)
        rent = c[3 % len(c)].slider("Rentabilidad anual supuesta (%)", 0.0, 12.0, 7.0, 0.5,
                                    help="La bolsa mundial ha dado históricamente ~7% anual de media "
                                         "(con años de -40% y años de +30%). No está garantizado.")
        filas = costes.simular_aportaciones(mensual, anos, rent, inicial)
        tabla = pd.DataFrame(filas).set_index("Año")
        lineas(apiladas=True, datos=reducir(tabla[["Aportado", "Ganancia"]]), height=alto_grafico() - 150)
        f = filas[-1]
        st.success(f"Aportando {eur(mensual)} al mes durante {anos} años habrías puesto **{eur(f['Aportado'])}** "
                   f"y tendrías unos **{eur(f['Valor'])}**. El interés compuesto hace el resto.")


def calculadora_letras(movil: bool):
    st.caption("Las Letras del Tesoro son préstamos al Estado español a 3, 6, 9 o 12 meses. Pagas menos de 1.000 € "
               "por cada Letra y al vencer cobras 1.000 €: la diferencia es tu interés. Riesgo muy bajo.")
    c = st.columns(1 if movil else 3)
    importe = c[0].number_input("Dinero que quieres poner (€)", 1000.0, 10_000_000.0, 10_000.0, 1000.0,
                                key="letras_importe")
    plazo = c[1 % len(c)].selectbox("Plazo", list(letras.PLAZOS), index=3, key="letras_plazo")
    tipo = c[2 % len(c)].number_input(
        "Tipo de interés de la última subasta (%)", 0.0, 15.0, 2.0, 0.05, format="%.3f", key="letras_tipo",
        help="El «tipo medio» de la última subasta de ese plazo. Lo publica el Tesoro en tesoro.es → Subastas → "
             "Resultados (y sale en las noticias el día de la subasta).")
    r = letras.calcular(importe, tipo, letras.PLAZOS[plazo])
    if r["letras"] == 0:
        st.warning("Con ese importe no llega para una Letra (cada una cuesta casi 1.000 €).")
        return
    m = st.columns(2 if movil else 4)
    m[0].metric("Letras que compras", f"{r['letras']}", help=f"Cada una cuesta {eur(r['precio'])} hoy.")
    m[1].metric("Pagas hoy", eur(r["pagas"]))
    m[2 % len(m)].metric(f"Cobras dentro de {plazo}", eur(r["cobras"]))
    m[3 % len(m)].metric("Intereses (antes de impuestos)", eur(r["intereses"]),
                         f"{r['tae']:.2f} % TAE".replace(".", ","), delta_color="off")
    st.markdown(f"Después de Hacienda (19 % en la base del ahorro hasta 6.000 €) te quedan **{eur(r['neto'])}** "
                f"limpios. Las Letras no tienen retención: el interés se declara en la Renta del año en que vencen.")
    st.info("**Cómo se compran:** en la web del Tesoro (tesoro.es, con certificado digital o Cl@ve; sin comisiones, "
            "el dinero va a tu cuenta) o desde tu banco (Bankinter las vende en su sección de renta fija; pregunta "
            "su comisión). Se pide en las subastas, que son cada dos semanas aprox. Si no quieres esperar a una "
            "subasta, hay fondos que invierten en Letras (🌍 Mercados → Renta fija).")


def calculadora_libertad():
    """¿Cuándo podrías vivir de tus inversiones? Con tu cartera y tu aportación (como el «FIRE» de Ghostfolio)."""
    from paginas_extra import _perfil_guardado, revisar_cartera_real

    pf = perfil()
    st.write("Cuánto dinero necesitas para vivir de tus inversiones y cuántos años te faltan con lo que tienes y lo "
             "que aportas cada mes. Todo en **euros de hoy** (las rentabilidades ya descuentan la inflación).")
    cta = cuenta_activa()
    try:
        filas = revisar_cartera_real()
        tu_capital = sum(f["pos"]["acciones"] * f["precio"] * f["fx"] for f in filas if f["precio"])
    except Exception:  # noqa: BLE001
        tu_capital = 0.0
    tu_capital += max(cta.get("otros_ahorros", 0.0), 0.0)
    if privado():
        tu_capital = 0.0
        st.caption("🙈 Modo privado: no se rellena con tu cartera; pon la cifra que quieras.")
    perfil_nombre = _perfil_guardado() or "Moderado"
    c = st.columns(2 if pf.movil else 4)
    gasto = c[0].number_input("Gasto que quieres cubrir (€ al mes)", 100.0, 50_000.0, 2_000.0, 100.0,
                              help="Lo que necesitarías al mes para vivir (o la parte que quieres que paguen tus "
                                   "inversiones).")
    capital = c[1].number_input("Lo que tienes invertido hoy (€)", 0.0, 100_000_000.0, float(round(tu_capital, -2)),
                                1_000.0, help="Relleno con tu cartera y tus ahorros apuntados de esta cuenta.")
    aporte = c[2 % len(c)].number_input("Lo que aportas al mes (€)", 0.0, 100_000.0,
                                        float((cta.get("aportacion") or {}).get("importe", 300.0) or 0.0), 50.0)
    rent = c[3 % len(c)].slider("Rentabilidad real al año (%)", 0.0, 8.0,
                                libertad.RENTABILIDAD_REAL.get(perfil_nombre, 0.04) * 100, 0.5,
                                help=f"Propuesta para un perfil {perfil_nombre.lower()}, ya descontada la inflación. "
                                     "Bolsa mundial: ~5 % real a largo plazo; mixta: ~4 %; conservadora: ~2,5 %.")
    tasa = st.select_slider("Cuánto sacarías cada año", [0.03, 0.035, 0.04], 0.04,
                            format_func=lambda x: f"{x * 100:.1f} %".replace(".", ","),
                            help="La «regla del 4 %»: sacando un 4 % al año (subiéndolo con la inflación), una "
                                 "cartera diversificada ha durado históricamente 30 años o más. Para más años o más "
                                 "prudencia, 3-3,5 %.")
    r = libertad.calcular(gasto, capital, aporte, rent / 100, tasa)
    m = st.columns(3)
    m[0].metric("Necesitas", eur(r["objetivo"]), help="Gasto anual dividido entre lo que sacas cada año.")
    m[1].metric("Llevas", f"{min(r['avance'], 9.99) * 100:.0f} %".replace(".", ","))
    m[2].metric("Te faltan", "¡ya lo tienes!" if r["anos"] == 0 else f"{r['anos']} años" if r["anos"]
                else "más de 60 años")
    if r["anos"] == 0:
        st.success(f"Con lo que tienes ya podrías sacar unos {eur(r['renta_hoy'])} al mes.")
    elif r["anos"]:
        peor = r["escenarios"]["Pesimista"]["anos"] or "más de 60"
        mejor = r["escenarios"]["Optimista"]["anos"] or "más de 60"
        st.info(f"Hoy tu dinero podría pagarte unos **{eur(r['renta_hoy'])} al mes**. Aportando {eur(aporte)} al mes "
                f"llegarías en **{r['anos']} años** ({peor} si va peor y {mejor} si va mejor).")
    else:
        st.warning("Con esa aportación no llegas en 60 años: sube la aportación, baja el gasto o acepta sacar menos.")
    anos_max = max((e["anos"] or 40) for e in r["escenarios"].values()) + 3
    tabla = pd.DataFrame({n: e["valores"][:anos_max + 1] for n, e in r["escenarios"].items()})
    tabla["Objetivo"] = r["objetivo"]
    tabla.index.name = "Años"
    lineas(tabla, height=alto_grafico() - 150)
    st.caption("Escenarios con 2 puntos menos y 2 más de rentabilidad al año. La bolsa no sube en línea recta: habrá "
               "años de -30 % por el camino. Es una guía para planificar, no una promesa.")


def calculadora_orden(clave: str, ticker: str | None = None, precio_hoy: float | None = None):
    """¿Cuánto gano o pierdo si pongo la orden limitada a X? Con las comisiones de tu bróker y lo que se lleva
    Hacienda, el precio a partir del cual empiezas a ganar y, si pones stop-loss, lo que arriesgas."""
    import plotly.graph_objects as go

    pf = perfil()
    movil, tarifa = pf.movil, pf.tarifa
    if ticker is None:
        st.caption("Pon a qué precio compras (o compraste) y a qué precio pondrías la orden de venta: te dice cuánto "
                   "ganas o pierdes de verdad, ya con comisiones e impuestos.")
        ticker = selector_valor(f"{clave}_v", solo_invertibles=True)
    fund = cargar_fundamentales(ticker)
    m, f_eur = moneda_de(ticker, fund), fx(ticker, fund)
    if f_eur is None:
        st.warning("No se ha podido leer el tipo de cambio de su divisa: prueba de nuevo en un momento.")
        return
    if precio_hoy is None:
        q = cotizaciones_ahora([ticker]).get(ticker)
        if q:
            precio_hoy = q["precio"]
        else:
            df = cargar_historico(ticker, "1mo")
            precio_hoy = float(df["Close"].iloc[-1]) if not df.empty else None
    if not precio_hoy:
        st.warning("No hay precio de este valor ahora mismo.")
        return
    pos = ((datos_usuario().get("cartera_real") or {}).get("posiciones") or {}).get(ticker)
    paso = 0.01 if precio_hoy < 50 else 0.05 if precio_hoy < 500 else 0.5
    redondo = lambda x: round(round(x / paso) * paso, 2)  # noqa: E731

    modos = ["Voy a comprar", "Ya las tengo"]
    modo = st.segmented_control("¿Qué vas a hacer?", modos, key=f"{clave}_modo_{ticker}",
                                default=modos[1] if pos else modos[0]) or modos[0]
    ya = modo == modos[1]
    c = st.columns(2)
    defecto_compra = float(pos["precio_medio"]) if ya and pos else float(redondo(precio_hoy))
    compra = c[0].number_input(f"{'Precio medio de compra' if ya else 'Precio de compra'} ({m})", 0.0001, 1e7,
                               defecto_compra, paso, format="%.2f", key=f"{clave}_compra_{ticker}_{ya}",
                               help="El que te sale en Bankinter en la posición." if ya else
                                    "El precio límite de tu orden de compra (o el de ahora si compras ya).")
    defecto_acciones = float(pos["acciones"]) if ya and pos else float(max(1, int(1000 / (precio_hoy * f_eur))))
    acciones = c[1].number_input("Acciones" if not ya else "Acciones que tienes", 0.0, 1e9, defecto_acciones, 1.0,
                                 format="%.0f" if defecto_acciones == int(defecto_acciones) else "%.4f",
                                 key=f"{clave}_acciones_{ticker}_{ya}")
    c = st.columns(2)
    venta = c[0].number_input(f"Vender a ({m}) · orden limitada", 0.0001, 1e7, float(redondo(compra * 1.05)), paso,
                              format="%.2f", key=f"{clave}_venta_{ticker}_{ya}",
                              help="El precio al que pones la orden limitada de venta: se vende a ese precio o más.")
    stop = c[1].number_input(f"Stop-loss ({m}) · 0 = sin stop", 0.0, 1e7, float(redondo(compra * 0.95)), paso,
                             format="%.2f", key=f"{clave}_stop_{ticker}_{ya}",
                             help="Si baja hasta aquí, se vende para cortar la pérdida. Pon 0 si no quieres stop.")
    if acciones <= 0:
        st.info("Pon cuántas acciones para calcularlo.")
        return
    cap = fund.get("marketCap")
    r = costes.resultado_orden(acciones, compra, venta, ticker, tarifa, f_eur, ya, cap)
    equilibrio = costes.precio_sin_perder(acciones, compra, ticker, tarifa, f_eur, ya, cap)
    from ui_comun import eur as dinero      # tu dinero: en modo privado sale «•••»
    signo = lambda x: ("+" if x > 0 else "") + dinero(x)  # noqa: E731
    color = "green" if r["neto"] > 0 else "red"
    cambio = (venta / compra - 1) * 100
    st.markdown(f"#### Si se vende a {eur(venta, m)} ({pct(cambio)}): :{color}[{'ganas' if r['neto'] > 0 else 'pierdes'}"
                f" {dinero(abs(r['neto']))}]")
    k = st.columns(2 if movil else 4)
    k[0].metric("Resultado (con comisiones)", signo(r["neto"]), pct(r["pct"]))
    k[1].metric("Hacienda (IRPF)", dinero(r["irpf"]))
    k[2 % len(k)].metric("Te queda limpio", signo(r["limpio"]))
    k[3 % len(k)].metric("Precio para no perder", eur(equilibrio, m),
                         help="Hay que vender por encima de este precio para ganar algo: por debajo, las "
                              "comisiones se comen la subida.")
    detalle = [f"subida del precio {signo(r['bruto'])}"]
    if r["gasto_compra"]:
        detalle.append(f"gastos de compra {dinero(-r['gasto_compra'])}")
    detalle.append(f"gastos de venta {dinero(-r['gasto_venta'])}")
    st.caption(" · ".join(detalle) + (f" · en euros al cambio de hoy ({num(1 / f_eur, 4)} {m} por €)"
                                      if m != "€" else ""))

    perdida = None
    if 0 < stop < compra:
        rs = costes.resultado_orden(acciones, compra, stop, ticker, tarifa, f_eur, ya, cap)
        perdida = -rs["neto"]
        st.markdown(f"Si salta el stop a {eur(stop, m)} ({pct((stop / compra - 1) * 100)}): "
                    f":red[pierdes {dinero(perdida)}]")
        if r["neto"] > 0 and perdida > 0:
            ratio = r["neto"] / perdida
            veredicto = ("✅ buena proporción" if ratio >= 2 else "🟡 justa: lo habitual es buscar al menos 2 a 1"
                         if ratio >= 1 else "🔴 arriesgas más de lo que puedes ganar")
            st.markdown(f"**Arriesgas {dinero(perdida)} para ganar {dinero(r['neto'])}: {num(ratio, 1)} a 1** · {veredicto}")
    elif stop >= compra and stop > 0:
        st.caption("El stop está por encima del precio de compra: así asegura ganancia (stop de beneficios).")

    # Lo que ganas o pierdes según a qué precio se venda: de un poco por debajo del stop a un poco por encima
    # del objetivo.
    bajo = min(x for x in (stop or compra * 0.9, compra * 0.9, precio_hoy) if x > 0) * 0.97
    alto = max(venta, compra * 1.1, precio_hoy) * 1.03
    precios = [bajo + (alto - bajo) * i / 80 for i in range(81)]
    netos = [costes.resultado_orden(acciones, compra, p, ticker, tarifa, f_eur, ya, cap)["neto"] for p in precios]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=precios, y=[max(n, 0) for n in netos], fill="tozeroy", mode="none",
                             fillcolor="rgba(22,163,74,.25)", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=precios, y=[min(n, 0) for n in netos], fill="tozeroy", mode="none",
                             fillcolor="rgba(220,38,38,.25)", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=precios, y=netos, mode="lines", line=dict(color="#475569", width=2),
                             hovertemplate=f"Vender a %{{x:,.2f}} {m}<br>%{{y:+,.0f}} €<extra></extra>"))
    marcas = [(precio_hoy, "Ahora", "#2563eb"), (venta, "Venta", "#16a34a")]
    if 0 < stop:
        marcas.append((stop, "Stop", "#dc2626"))
    for x, txt, col in marcas:
        fig.add_vline(x=x, line=dict(color=col, width=1.5, dash="dot"))
        fig.add_annotation(x=x, y=1, yref="paper", text=txt, showarrow=False, yanchor="bottom",
                           font=dict(color=col, size=12))
    fig.add_hline(y=0, line=dict(color="#94a3b8", width=1))
    fig.update_layout(showlegend=False, xaxis_title=f"Precio de venta ({m})", yaxis_title="Ganas o pierdes (€)",
                      yaxis=dict(tickformat="+,.0f"))
    if privado():
        fig.update_yaxes(showticklabels=False)
    mostrar_plotly(fig, alto=260 if movil else 320, margen=dict(l=10, r=10, t=30, b=10))

    with st.expander("📋 Tabla de precios (cuánto ganas o pierdes en cada uno)"):
        filas = []
        for d in (-10, -7.5, -5, -3, -2, -1, 1, 2, 3, 5, 7.5, 10, 15):
            p = compra * (1 + d / 100)
            x = costes.resultado_orden(acciones, compra, p, ticker, tarifa, f_eur, ya, cap)
            filas.append({"Vender a": eur(p, m), "Cambio": pct(d, 1), "Resultado": signo(x["neto"]),
                          "Limpio (tras IRPF)": signo(x["limpio"])})
        st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch")
    st.caption("Cálculo con tu tarifa de comisiones (⚙️ Mi plan) y el IRPF de la base del ahorro, como si fuera tu "
               "única venta del año. Una orden limitada se ejecuta a tu precio o mejor, pero solo si el mercado llega.")
