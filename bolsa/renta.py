"""Ayuda para la declaración de la Renta: tus ventas y tus dividendos del año, ya resumidos.

Lo que hay que poner en Renta Web (base del ahorro):
- «Ganancias y pérdidas patrimoniales derivadas de la transmisión de acciones admitidas a negociación»: cada venta
  (fecha, importe de venta y de compra, con sus gastos).
- «Rendimientos del capital mobiliario → dividendos»: lo cobrado en bruto y la retención.

Es una estimación con lo que has apuntado en la app. Hacienda ya suele tener estos datos (tu banco se los envía):
compáralos con el borrador y, si no coinciden, manda el certificado fiscal de tu banco.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from .costes import impuesto_ganancia

RETENCION = 0.19
RETENCION_ORIGEN = 0.15     # lo que suele retener el país de la empresa con convenio (EEUU, Alemania con papeles...)
DIAS_REGLA_DOS_MESES = 61
LIMITE_CRUZADO = 0.25       # las pérdidas de un tipo compensan como mucho el 25 % del saldo del otro


def _fecha(s: str) -> date:
    return date.fromisoformat(s[:10])


def _es_compra_real(h: dict) -> bool:
    """Las compras «Importadas» llevan la fecha del día en que importaste el extracto, no la de la compra: no
    sirven para la regla de los dos meses."""
    return h.get("tipo") == "Compra" and not str(h.get("motivo") or "").startswith("Importada")


def _recompra_en_dos_meses(historial: list[dict], i: int) -> bool:
    """Regla de los dos meses (art. 33.5 de la Ley del IRPF): la pérdida no se puede restar si compraste el mismo
    valor en los dos meses anteriores o posteriores a la venta. Las compras de antes solo cuentan si siguen en tu
    poder después de vender (si vendiste todo, son las mismas acciones que vendes)."""
    venta = historial[i]
    fv = _fecha(venta["fecha"])
    t = venta["ticker"]
    quedan = sum(h["acciones"] if h.get("tipo") == "Compra" else -h["acciones"] if h.get("tipo") == "Venta" else 0
                 for h in historial[:i + 1] if h.get("ticker") == t)
    for j, c in enumerate(historial):
        if j == i or c.get("ticker") != t or not _es_compra_real(c):
            continue
        dias = (_fecha(c["fecha"]) - fv).days
        if j > i and 0 <= dias <= DIAS_REGLA_DOS_MESES:
            return True
        if j < i and 0 <= -dias <= DIAS_REGLA_DOS_MESES and quedan > 1e-9:
            return True
    return False


def ventas_del_ano(historial: list[dict], anio: int, nombres: dict[str, str] | None = None) -> list[dict]:
    """Ventas de ese año con su resultado (ya descontados los gastos de compra y venta) y si la pérdida queda
    aplazada por la regla de los dos meses (recompra del mismo valor dos meses antes o después)."""
    nombres = nombres or {}
    # Por fecha (y, el mismo día, en el orden en que se apuntaron): las operaciones pueden apuntarse tarde.
    historial = sorted(historial, key=lambda h: str(h.get("fecha", ""))[:10])
    salida = []
    for i, h in enumerate(historial):
        if h.get("tipo") != "Venta" or _fecha(h["fecha"]).year != anio or h.get("resultado") is None:
            continue
        fv = _fecha(h["fecha"])
        aplazada = h["resultado"] < 0 and _recompra_en_dos_meses(historial, i)
        fx = h.get("fx", 1.0)
        venta = h["acciones"] * h["precio"] * fx - h.get("gastos", 0.0)
        salida.append({"fecha": fv.isoformat(), "ticker": h["ticker"], "nombre": nombres.get(h["ticker"], h["ticker"]),
                       "acciones": h["acciones"], "importe_venta": venta, "importe_compra": venta - h["resultado"],
                       "resultado": h["resultado"], "aplazada": aplazada})
    return sorted(salida, key=lambda v: v["fecha"])


def acciones_en(historial: list[dict], ticker: str, dia: pd.Timestamp) -> float:
    """Títulos que tenías antes de ese día (para cobrar un dividendo hay que tenerlos antes de la fecha ex)."""
    n = 0.0
    for h in historial:
        if h.get("ticker") != ticker or pd.Timestamp(h["fecha"][:10]) >= dia:
            continue
        n += h["acciones"] if h.get("tipo") == "Compra" else -h["acciones"] if h.get("tipo") == "Venta" else 0
    return max(n, 0.0)


def dividendos_del_ano(historial: list[dict], dividendos: dict[str, pd.Series], fx: dict[str, float], anio: int,
                       nombres: dict[str, str] | None = None) -> list[dict]:
    """Dividendos cobrados ese año (estimados con tus títulos en cada fecha ex-dividendo)."""
    nombres = nombres or {}
    salida = []
    for t, serie in dividendos.items():
        if serie is None or len(serie) == 0:
            continue
        idx = pd.to_datetime(serie.index)
        if idx.tz is not None:
            idx = idx.tz_localize(None)
        for dia, importe in zip(idx, serie.values):
            if dia.year != anio:
                continue
            n = acciones_en(historial, t, dia.normalize())
            if n <= 0:
                continue
            bruto = n * float(importe) * fx.get(t, 1.0)
            extranjero = not t.endswith(".MC")
            # En España se retiene el 19 % de lo que llega DESPUÉS de la retención del otro país (≈15 % con
            # convenio; recuperable en parte con la deducción por doble imposición).
            base_es = bruto * (1 - RETENCION_ORIGEN) if extranjero else bruto
            salida.append({"fecha": dia.date().isoformat(), "ticker": t, "nombre": nombres.get(t, t), "acciones": n,
                           "bruto": bruto, "retencion": base_es * RETENCION, "extranjero": extranjero,
                           "retencion_origen": bruto - base_es})
    return sorted(salida, key=lambda d: d["fecha"])


def resumen(ventas: list[dict], dividendos: list[dict], perdidas_anteriores: float = 0.0) -> dict:
    """Base del ahorro y cuota aproximada, con las compensaciones de la ley del IRPF:
    1) las pérdidas de años anteriores (últimos 4) compensan primero ganancias;
    2) un saldo negativo de ventas compensa hasta el 25 % de los dividendos (y al revés);
    3) lo que no se compensa se arrastra 4 años."""
    computables = [v for v in ventas if not v["aplazada"]]
    ganancias = sum(v["resultado"] for v in computables if v["resultado"] > 0)
    perdidas = -sum(v["resultado"] for v in computables if v["resultado"] < 0)
    gp = ganancias - perdidas
    rcm = sum(d["bruto"] for d in dividendos)
    anteriores = max(perdidas_anteriores, 0.0)

    usado_anteriores = min(anteriores, max(gp, 0.0))
    gp -= usado_anteriores
    anteriores -= usado_anteriores
    cruzado = 0.0
    if gp < 0 and rcm > 0:
        cruzado = min(-gp, LIMITE_CRUZADO * rcm)
        gp += cruzado
        rcm -= cruzado
    margen = max(LIMITE_CRUZADO * sum(d["bruto"] for d in dividendos) - cruzado, 0.0)
    usado_rcm = min(anteriores, margen, rcm)
    rcm -= usado_rcm
    anteriores -= usado_rcm
    usado_anteriores += usado_rcm

    base = max(gp, 0.0) + max(rcm, 0.0)
    cuota = impuesto_ganancia(base)
    retenciones = sum(d["retencion"] for d in dividendos)
    return {"ganancias": ganancias, "perdidas": perdidas, "saldo_ventas": ganancias - perdidas,
            "dividendos_brutos": sum(d["bruto"] for d in dividendos), "retenciones": retenciones,
            "perdidas_anteriores_usadas": usado_anteriores, "compensacion_cruzada": cruzado,
            "base_ahorro": base, "cuota": cuota, "a_pagar": cuota - retenciones,
            "perdidas_para_futuro": max(-gp, 0.0) + anteriores,
            "aplazadas": [v for v in ventas if v["aplazada"]],
            "hay_extranjeros": any(d["extranjero"] for d in dividendos)}


def tabla_csv(ventas: list[dict], dividendos: list[dict]) -> str:
    """Todo en un CSV (separador «;» y coma decimal, para abrirlo bien con Excel en español)."""
    filas = [{"Tipo": "Venta", "Fecha": v["fecha"], "Valor": v["nombre"], "Ticker": v["ticker"],
              "Títulos": v["acciones"], "Importe venta (€)": v["importe_venta"],
              "Importe compra (€)": v["importe_compra"], "Resultado (€)": v["resultado"],
              "Retención (€)": None, "Nota": "Pérdida aplazada (regla de los 2 meses)" if v["aplazada"] else ""}
             for v in ventas]
    filas += [{"Tipo": "Dividendo", "Fecha": d["fecha"], "Valor": d["nombre"], "Ticker": d["ticker"],
               "Títulos": d["acciones"], "Importe venta (€)": None, "Importe compra (€)": None,
               "Resultado (€)": d["bruto"], "Retención (€)": d["retencion"],
               "Nota": "Extranjero: mira la retención en origen" if d["extranjero"] else ""} for d in dividendos]
    df = pd.DataFrame(filas, columns=["Tipo", "Fecha", "Valor", "Ticker", "Títulos", "Importe venta (€)",
                                      "Importe compra (€)", "Resultado (€)", "Retención (€)", "Nota"])
    return df.to_csv(index=False, sep=";", decimal=",", float_format="%.2f")


def en_campana(hoy: date | None = None) -> bool:
    """De abril a junio se presenta la Renta del año anterior."""
    hoy = hoy or date.today()
    return 4 <= hoy.month <= 6


__all__ = ["ventas_del_ano", "dividendos_del_ano", "acciones_en", "resumen", "tabla_csv", "en_campana",
           "RETENCION"]
