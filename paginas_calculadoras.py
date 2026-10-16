"""Página Calculadoras: cuánto comprar, costes e interés compuesto."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from bolsa import costes, libertad
from ui_comun import alto_grafico, cuenta_activa, perfil, privado, reducir
from ui_comun import precio as eur  # importes de ejemplo: se ven también en modo privado


def pagina_calculadoras():
    pf = perfil()
    movil, tarifa = pf.movil, pf.tarifa
    st.title("🧮 Calculadoras")
    t1, t2, t3, t4 = st.tabs(["💶 Coste", "🏛️ Impuestos", "🌱 Cada mes", "🏖️ Libertad financiera"])
    with t4:
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
        st.area_chart(reducir(tabla[["Aportado", "Ganancia"]]), height=alto_grafico() - 150)
        f = filas[-1]
        st.success(f"Aportando {eur(mensual)} al mes durante {anos} años habrías puesto **{eur(f['Aportado'])}** "
                   f"y tendrías unos **{eur(f['Valor'])}**. El interés compuesto hace el resto.")


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
    st.line_chart(tabla, height=alto_grafico() - 150)
    st.caption("Escenarios con 2 puntos menos y 2 más de rentabilidad al año. La bolsa no sube en línea recta: habrá "
               "años de -30 % por el camino. Es una guía para planificar, no una promesa.")
