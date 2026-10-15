"""Página Calculadoras: cuánto comprar, costes e interés compuesto."""

from __future__ import annotations

import pandas as pd
import streamlit as st
from bolsa import costes
from ui_comun import alto_grafico, eur, perfil, reducir


def pagina_calculadoras():
    pf = perfil()
    movil, tarifa = pf.movil, pf.tarifa
    st.title("🧮 Calculadoras")
    t1, t2, t3 = st.tabs(["💶 Coste", "🏛️ Impuestos", "🌱 Cada mes"])
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
        c = st.columns(1 if movil else 3)
        c[0].metric("Al comprar", eur(cc["total"]), f"{cc['pct']:.2f} %".replace(".", ","), delta_color="off")
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
        c = st.columns(1 if movil else 3)
        c[0].metric("Ganancia", eur(g))
        c[1 % len(c)].metric("IRPF aproximado", eur(imp))
        c[2 % len(c)].metric("Te queda limpio", eur(g - imp))
        st.caption("Tramos del ahorro: 19% hasta 6.000 €, 21% hasta 50.000 €, 23% hasta 200.000 €, "
                   "27% hasta 300.000 €, 30% a partir de ahí. Las pérdidas se pueden compensar con ganancias "
                   "(durante 4 años). Ojo con la 'regla de los 2 meses': si vendes con pérdidas y recompras la "
                   "misma acción en menos de 2 meses, no puedes aplicar esa pérdida todavía. "
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
        st.area_chart(reducir(tabla[["Aportado", "Ganancia"]]), height=alto_grafico() - 150)
        f = filas[-1]
        st.success(f"Aportando {eur(mensual)} al mes durante {anos} años habrías puesto **{eur(f['Aportado'])}** "
                   f"y tendrías unos **{eur(f['Valor'])}**. El interés compuesto hace el resto.")
