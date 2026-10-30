"""Barra lateral: perfil (móvil, dinero, riesgo), bróker y comisiones, estado del guardado."""

from __future__ import annotations

import streamlit as st

from bolsa import asesor, costes, cuentas, noticias
from ui_comun import (Perfil, cuenta_activa, datos_usuario, es_movil, estado_finnhub, estado_guardado, guardar_datos,
                      hay_contrasena, olvidar_campos_de_cuenta, olvidar_datos_al_dia, privado)


def _capital_por_defecto() -> float:
    """La parte para acciones sueltas según el plan guardado en 🎯 Mi plan (3.000 € si no hay plan)."""
    plan = cuenta_activa().get("perfil_inversor") or {}
    if not plan:
        return 3000.0
    p = asesor.perfil_inversor(plan["horizonte"], plan["reaccion"], plan["experiencia"], plan["colchon"])
    return max(100.0, plan["importe"] * asesor.REPARTOS[p.nombre]["Acciones individuales"] / 100)


def _tarifa_bankinter() -> costes.Tarifa:
    broker_cero = st.toggle("Tengo el servicio Bróker Cero", value=False,
                            help="Con Bróker Cero, comprar y vender acciones españolas por Internet cuesta 0 € "
                                 "(solo pagas los cánones de la bolsa).")
    canon = st.number_input("Cánones de bolsa en España por operación (€, aprox.)", 0.0, 10.0, 1.0, 0.5)
    st.caption("Tarifa pública de Bankinter (oct. 2026): acciones españolas 3,95 € hasta 2.000 € y 8 € hasta "
               "60.000 € por operación; extranjeras 20 € por operación, +1 % si se cambia de divisa, y una "
               "custodia mínima de 24 € al año por valor. Compruébala en Bankinter → Bróker → Tarifas.")
    return costes.Tarifa(broker_cero=broker_cero, canon_nacional=canon)


def _tarifa_otro(broker: str, d: dict) -> costes.TarifaPersonal:
    base = costes.TARIFAS_PRECARGADAS.get(broker, costes.TarifaPersonal(broker))
    guardada = d.get("tarifas", {}).get(broker, {})
    antes = {k: float(guardada.get(k, getattr(base, k))) for k in
             ("nacional_fija", "internacional_fija", "divisa_pct", "custodia_anual_valor", "canon_nacional")}
    st.caption("Pon las comisiones de tu tarifa (están en la web de tu banco, apartado «tarifas» o "
               "«comisiones» del bróker)." + (" Precargada la de Trade Republic: 1 € por operación."
                                              if broker in costes.TARIFAS_PRECARGADAS else ""))
    v = dict(antes)
    v["nacional_fija"] = st.number_input("Por operación en España (€)", 0.0, 100.0, v["nacional_fija"], 0.5)
    v["internacional_fija"] = st.number_input("Por operación en el extranjero (€)", 0.0, 200.0,
                                              v["internacional_fija"], 0.5)
    v["divisa_pct"] = st.number_input("Cambio de divisa (%)", 0.0, 5.0, v["divisa_pct"], 0.05)
    v["custodia_anual_valor"] = st.number_input("Custodia por valor extranjero y año (€)", 0.0, 200.0,
                                                v["custodia_anual_valor"], 1.0)
    v["canon_nacional"] = st.number_input("Cánones de bolsa en España (€)", 0.0, 10.0, v["canon_nacional"], 0.5)
    if v != antes:
        d.setdefault("tarifas", {})[broker] = v
        guardar_datos()
    return costes.TarifaPersonal(broker, **v)


def _pie():
    st.divider()
    st.caption(f"Cotizaciones de Yahoo Finance (retraso ~15 min). Noticias de {len(noticias.FUENTES_RSS)} "
               "fuentes RSS en español e inglés. Se actualizan solas cada 5-10 minutos.")
    texto, ayuda = estado_guardado()
    st.caption(texto, help=ayuda)
    fh = estado_finnhub()
    if fh:
        st.caption(("⚡ " if fh[0] else "⚠️ ") + fh[1])
    if not hay_contrasena():
        st.caption("🔓 App sin contraseña", help="Si la app es pública, cualquiera con el enlace ve tu cartera. Ponla "
                   "privada en Streamlit → Settings → Sharing y añade en Secrets:\n\n[app]\npassword = \"...\"")
    elif st.button("🔒 Salir", width="stretch"):
        st.session_state.pop("_acceso_ok", None)
        st.rerun()
    st.caption("Los precios y las noticias se actualizan solos cada minuto.")
    if st.button("🔄 Actualizar todo ahora", width="stretch",
                 help="Vuelve a descargarlo todo (también el histórico y los datos de las empresas)."):
        st.cache_data.clear()
        olvidar_datos_al_dia()
        st.rerun()


def selector_de_cuenta() -> None:
    """Qué cuenta asesora la app (la tuya, la de tu madre...). Solo aparece si hay más de una."""
    d = datos_usuario()
    nombres = list(cuentas.asegurar(d))
    if len(nombres) < 2:
        return
    elegida = st.selectbox("👤 Cuenta", nombres, index=nombres.index(d["cuenta_activa"]),
                           help="Toda la app (Hoy, Mi cartera, Seguimiento, Mi plan) asesora solo a esta cuenta. "
                                "Las cuentas no se suman. Créalas en 🏦 Mi cartera → 🗂️ Cuentas.")
    if elegida != d["cuenta_activa"]:
        cuentas.activar(d, elegida)
        olvidar_campos_de_cuenta()
        guardar_datos()
    st.divider()


# Streamlit guarda el tema elegido en el navegador (localStorage, una clave por dirección de la página) y lo lee al
# cargar. Desde Python no se puede cambiar: se escribe esa clave para esta página, la de inicio y las del menú, y se
# recarga. Así se queda puesto también al volver a abrir la app en el móvil.
_CAMBIAR_TEMA = """
<script>
(() => {
  const valor = JSON.stringify("%s");
  const base = location.pathname.replace(/[^/]*$/, "");
  const rutas = new Set([location.pathname, base, base.replace(/\\/$/, "") || "/"]);
  document.querySelectorAll("a[href]").forEach(a => {
    try { const u = new URL(a.href, location.href);
          if (u.origin === location.origin && u.pathname.startsWith(base)) rutas.add(u.pathname); } catch (e) {}
  });
  try {
    Object.keys(localStorage).filter(k => k.startsWith("stActiveTheme-")).forEach(k => localStorage.setItem(k, valor));
    rutas.forEach(r => localStorage.setItem("stActiveTheme-" + r + "-v2", valor));
  } catch (e) {}
  location.reload();
})();
</script>
"""


def _tema_actual_oscuro() -> bool:
    try:
        return st.context.theme.type == "dark"
    except Exception:  # noqa: BLE001
        return False


def _al_cambiar_tema() -> None:
    st.session_state["_tema_pendiente"] = "Dark" if st.session_state.get("_oscuro") else "Light"


def modo_oscuro() -> None:
    """Interruptor de modo oscuro (fondo negro, mejor de noche y gasta menos batería en pantallas OLED)."""
    if "_oscuro" not in st.session_state:
        st.session_state["_oscuro"] = _tema_actual_oscuro()
    st.toggle("🌙 Modo oscuro", key="_oscuro", on_change=_al_cambiar_tema,
              help="Fondo oscuro, más cómodo de noche. Se queda guardado en este móvil o navegador.")
    pendiente = st.session_state.pop("_tema_pendiente", None)
    if pendiente:
        st.html(_CAMBIAR_TEMA % pendiente, unsafe_allow_javascript=True)


def barra_lateral() -> Perfil:
    """Pinta la barra lateral y devuelve el perfil elegido."""
    with st.sidebar:
        selector_de_cuenta()
        st.title("⚙️ Tu perfil")
        movil = st.toggle("📱 Vista para móvil", value=es_movil(),
                          help="Gráficos más bajos y tablas con menos columnas. Se activa sola en el móvil.")
        st.toggle("🙈 Ocultar importes", key="_privado",
                  help="Modo privado: tus euros salen como «•••» y las tablas solo enseñan precios y porcentajes. "
                       "Para enseñar la app sin que se vea cuánto tienes.")
        modo_oscuro()
        if privado():                # sin enseñar tu dinero: se usa el de tu plan
            capital = float(st.session_state.get("_capital_sueltas") or round(_capital_por_defecto(), -1))
            st.caption("💶 Dinero para acciones sueltas: ••• € (oculto)")
        else:
            capital = st.number_input("Dinero para acciones sueltas (€)", min_value=100.0,
                                      value=float(round(_capital_por_defecto(), -1)), step=100.0,
                                      help="La parte de tu dinero para comprar acciones concretas (en 🎯 Mi plan se "
                                           "calcula según tu perfil). Se usa para decirte cuántas comprar.")
            st.session_state["_capital_sueltas"] = capital
        riesgo = st.slider("Máximo que aceptas perder por operación (% de ese dinero)", 0.5, 5.0, 1.0, 0.5,
                           help="Regla de oro de los profesionales: no arriesgar más de un 1-2% del capital "
                                "en una sola operación. Así, aunque falles varias veces seguidas, sigues en el juego.")
        d = cuenta_activa()
        broker = st.selectbox("Tu banco o bróker", costes.BROKERS,
                              index=costes.BROKERS.index(d["broker"]) if d.get("broker") in costes.BROKERS else 0,
                              help="Se usa para las comisiones y para escribir las órdenes con los pasos de tu bróker.")
        if broker != d.get("broker", "Bankinter"):
            d["broker"] = broker
            guardar_datos()
        st.session_state["_broker"] = broker
        with st.expander(f"Tus comisiones en {broker if broker != 'Otro' else 'tu bróker'}"):
            tarifa = _tarifa_bankinter() if broker == "Bankinter" else _tarifa_otro(broker, d)
        _pie()
    return Perfil(movil=movil, capital=capital, riesgo=riesgo, tarifa=tarifa)
