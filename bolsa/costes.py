"""Costes reales de invertir con el bróker de Bankinter, divisas, impuestos y tamaño de las posiciones.

Tarifas públicas de Bankinter consultadas en octubre de 2026 (pueden cambiar: compruébalas en
bankinter.com → Bróker → Tarifas y comisiones):

- Mercado nacional (acciones españolas), por operación: hasta 2.000 € → 3,95 €; de 2.000 a 60.000 € → 8 €;
  más de 60.000 € → 0,07% (máximo 200 €). Con el servicio **Bróker Cero**: 0 € (online, Mercado Continuo).
  Aparte, la bolsa cobra unos cánones pequeños (aquí ~1 € por operación, aproximado).
- Mercados internacionales (EEUU, Alemania, Francia...): 20 € por operación hasta 40.000 €
  (incluye corretaje y gastos de mercado); por encima, en torno al 0,20%.
- Cambio de divisa (acciones en dólares, libras...): diferencial de ±1% en la compra y en la venta.
- Custodia de valores internacionales: 0,05% trimestral con un mínimo de 6 € por valor (≥ 24 €/año).
- Órdenes stop: sin coste de alta ni de cancelación.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Tramos del IRPF de la base del ahorro (España, 2025-2026). Revísalos cada año.
TRAMOS_AHORRO = [(6_000, 19.0), (50_000, 21.0), (200_000, 23.0), (300_000, 27.0), (math.inf, 30.0)]

# Impuesto sobre Transacciones Financieras ("tasa Tobin") al COMPRAR acciones de grandes empresas.
# España 0,2% (capitalización > 1.000 M€), Francia 0,4% desde abril de 2025 (> 1.000 M€),
# Italia 0,1% (> 500 M€). Los ETF y fondos no lo pagan.
TASA_TOBIN = {".MC": (0.2, 1e9), ".PA": (0.4, 1e9), ".MI": (0.1, 5e8)}

SUFIJOS_EURO = (".MC", ".AS", ".PA", ".DE", ".MI", ".BR", ".HE", ".LS", ".VI", ".IR", ".F")
SUFIJOS_DIVISA = {".L": "GBp", ".SW": "CHF", ".T": "JPY", ".TO": "CAD", ".HK": "HKD", ".ST": "SEK", ".CO": "DKK",
                  ".OL": "NOK"}
SIMBOLOS = {"EUR": "€", "USD": "$", "GBp": "p", "GBP": "£", "CHF": "CHF", "JPY": "¥", "CAD": "C$"}


def divisa(ticker: str, info: dict | None = None) -> str:
    """Divisa en la que cotiza un valor ('EUR', 'USD', 'GBp'...). Si se conoce, manda la de los datos."""
    if info and info.get("currency"):
        return info["currency"]
    if ticker.endswith("-EUR"):          # criptomonedas cotizadas en euros (BTC-EUR...)
        return "EUR"
    if ticker.endswith(SUFIJOS_EURO):
        return "EUR"
    for sufijo, d in SUFIJOS_DIVISA.items():
        if ticker.endswith(sufijo):
            return d
    if ticker.startswith("^") or "=" in ticker:
        return "—"
    return "USD"


def simbolo(ticker: str, info: dict | None = None) -> str:
    d = divisa(ticker, info)
    return SIMBOLOS.get(d, d)


def es_nacional(ticker: str) -> bool:
    """Mercado español (tarifa nacional de Bankinter)."""
    return ticker.endswith(".MC")


def tasa_tobin_pct(ticker: str, capitalizacion: float | None = None) -> float:
    from .activos import clase_de

    if clase_de(ticker) != "Acciones":
        return 0.0
    for sufijo, (pct, minimo) in TASA_TOBIN.items():
        if ticker.endswith(sufijo):
            if capitalizacion is not None and capitalizacion < minimo:
                return 0.0
            return pct
    return 0.0


itf_pct = tasa_tobin_pct  # nombre antiguo


@dataclass
class Tarifa:
    """Tarifa de Bankinter. Todos los importes en euros."""
    broker_cero: bool = False
    canon_nacional: float = 1.0          # cánones de bolsa aproximados (mercado español)
    internacional_fija: float = 20.0
    internacional_tope: float = 40_000.0
    internacional_pct: float = 0.20
    divisa_pct: float = 1.0
    custodia_int_pct_trimestral: float = 0.05
    custodia_int_minimo: float = 6.0

    def comision(self, importe: float, ticker: str) -> float:
        if importe <= 0:
            return 0.0
        if es_nacional(ticker):
            if self.broker_cero:
                base = 0.0
            elif importe <= 2_000:
                base = 3.95
            elif importe <= 60_000:
                base = 8.0
            else:
                base = min(importe * 0.07 / 100, 200.0)
            return base + self.canon_nacional
        if importe <= self.internacional_tope:
            return self.internacional_fija
        return importe * self.internacional_pct / 100

    def cambio_divisa(self, importe: float, ticker: str) -> float:
        return importe * self.divisa_pct / 100 if divisa(ticker) not in ("EUR", "—") else 0.0

    def coste(self, importe: float, ticker: str) -> float:
        """Coste de UNA operación (compra o venta) sin impuestos: comisión + cambio de divisa."""
        return self.comision(importe, ticker) + self.cambio_divisa(importe, ticker)

    def custodia_anual(self, valor: float, ticker: str) -> float:
        if es_nacional(ticker) or valor <= 0:
            return 0.0
        return 4 * max(valor * self.custodia_int_pct_trimestral / 100, self.custodia_int_minimo)

    def fijo_maximo(self, ticker: str) -> float:
        """Parte fija más alta posible de una operación (para calcular cuántas acciones caben)."""
        return (0.0 if self.broker_cero else 8.0) + self.canon_nacional if es_nacional(ticker) \
            else self.internacional_fija

    def variable_pct(self, ticker: str) -> float:
        return (0.07 if es_nacional(ticker) else self.internacional_pct) + \
            (self.divisa_pct if divisa(ticker) not in ("EUR", "—") else 0.0)


def coste_compra(importe: float, ticker: str, tarifa: Tarifa, capitalizacion: float | None = None) -> dict:
    comision = tarifa.comision(importe, ticker)
    cambio = tarifa.cambio_divisa(importe, ticker)
    itf = importe * tasa_tobin_pct(ticker, capitalizacion) / 100
    total = comision + cambio + itf
    return {"comision": comision, "cambio": cambio, "itf": itf, "total": total,
            "pct": total / importe * 100 if importe else 0.0}


def coste_ida_y_vuelta(importe: float, ticker: str, tarifa: Tarifa, anos: float = 1.0,
                       capitalizacion: float | None = None) -> dict:
    """Todo lo que cuesta comprar, mantener `anos` años y vender (sin impuestos sobre la ganancia)."""
    compra = coste_compra(importe, ticker, tarifa, capitalizacion)["total"]
    venta = tarifa.coste(importe, ticker)
    custodia = tarifa.custodia_anual(importe, ticker) * anos
    total = compra + venta + custodia
    return {"compra": compra, "venta": venta, "custodia": custodia, "total": total,
            "pct": total / importe * 100 if importe else 0.0}


def acciones_asequibles(efectivo: float, precio: float, ticker: str, tarifa: Tarifa,
                        tobin_pct: float | None = None) -> int:
    """Máximo de acciones que se pueden comprar con `efectivo` pagando todos los costes."""
    if precio <= 0 or efectivo <= 0:
        return 0
    tobin = tasa_tobin_pct(ticker) if tobin_pct is None else tobin_pct
    n = math.floor(max(efectivo - tarifa.fijo_maximo(ticker), 0) /
                   (precio * (1 + (tarifa.variable_pct(ticker) + tobin) / 100)))
    def total(k: int) -> float:
        return k * precio + tarifa.coste(k * precio, ticker) + k * precio * tobin / 100

    while n > 0 and total(n) > efectivo:
        n -= 1
    while total(n + 1) <= efectivo:  # la estimación inicial es prudente: aprovechar lo que quepa
        n += 1
    return max(n, 0)


@dataclass
class TarifaPersonal:
    """Comisiones de cualquier otro banco o bróker (las pone el usuario). Misma interfaz que `Tarifa`."""
    nombre: str = "Otro bróker"
    nacional_fija: float = 8.0
    nacional_pct: float = 0.0
    internacional_fija: float = 15.0
    internacional_pct: float = 0.0
    divisa_pct: float = 0.5
    custodia_anual_valor: float = 0.0     # por valor extranjero y año
    canon_nacional: float = 1.0
    broker_cero: bool = False             # compatibilidad con `Tarifa`

    def comision(self, importe: float, ticker: str) -> float:
        if importe <= 0:
            return 0.0
        if es_nacional(ticker):
            return self.nacional_fija + importe * self.nacional_pct / 100 + self.canon_nacional
        return self.internacional_fija + importe * self.internacional_pct / 100

    def cambio_divisa(self, importe: float, ticker: str) -> float:
        return importe * self.divisa_pct / 100 if divisa(ticker) not in ("EUR", "—") else 0.0

    def coste(self, importe: float, ticker: str) -> float:
        return self.comision(importe, ticker) + self.cambio_divisa(importe, ticker)

    def custodia_anual(self, valor: float, ticker: str) -> float:
        return 0.0 if es_nacional(ticker) or valor <= 0 else self.custodia_anual_valor

    def fijo_maximo(self, ticker: str) -> float:
        return self.nacional_fija + self.canon_nacional if es_nacional(ticker) else self.internacional_fija

    def variable_pct(self, ticker: str) -> float:
        return (self.nacional_pct if es_nacional(ticker) else self.internacional_pct) + \
            (self.divisa_pct if divisa(ticker) not in ("EUR", "—") else 0.0)


# Bancos y brókers para elegir. Solo hay tarifa precargada donde está comprobada; en el resto el usuario
# pone sus comisiones (cada banco tiene varias tarifas y cambian a menudo).
BROKERS = ["Bankinter", "Trade Republic", "CaixaBank", "BBVA", "Banco Santander", "ING", "Kutxabank", "Openbank",
           "MyInvestor", "Degiro", "Interactive Brokers", "Renta 4", "Sabadell", "Unicaja", "Otro"]
TARIFAS_PRECARGADAS = {
    # Trade Republic: 1 € de costes externos por operación, sin custodia ni cambio de divisa (opera en euros).
    "Trade Republic": TarifaPersonal("Trade Republic", 1.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0),
}


def tamano_por_riesgo(capital: float, riesgo_max_pct: float, entrada: float, stop: float) -> int:
    """Nº de acciones para que, si salta el stop-loss, pierdas como mucho riesgo_max_pct del capital.
    Capital, entrada y stop deben estar en la MISMA divisa."""
    perdida_por_accion = entrada - stop
    if perdida_por_accion <= 0:
        return 0
    por_riesgo = int(capital * riesgo_max_pct / 100 // perdida_por_accion)
    por_capital = int(capital // entrada)
    return max(0, min(por_riesgo, por_capital))


def impuesto_ganancia(ganancia: float) -> float:
    """IRPF aproximado sobre una ganancia patrimonial (base del ahorro)."""
    if ganancia <= 0:
        return 0.0
    impuesto, anterior = 0.0, 0.0
    for limite, tipo in TRAMOS_AHORRO:
        tramo = min(ganancia, limite) - anterior
        if tramo <= 0:
            break
        impuesto += tramo * tipo / 100
        anterior = limite
    return impuesto


def simular_aportaciones(mensual: float, anos: int, rent_anual_pct: float, inicial: float = 0.0) -> list[dict]:
    """Interés compuesto con aportación mensual. Devuelve una fila por año."""
    r = (1 + rent_anual_pct / 100) ** (1 / 12) - 1
    saldo, aportado, filas = inicial, inicial, []
    for mes in range(1, anos * 12 + 1):
        saldo = saldo * (1 + r) + mensual
        aportado += mensual
        if mes % 12 == 0:
            filas.append({"Año": mes // 12, "Aportado": aportado, "Valor": saldo, "Ganancia": saldo - aportado})
    return filas


# --------------------------------------------------------------------------- divisas
TICKER_CAMBIO = {"USD": "EURUSD=X", "GBp": "EURGBP=X", "GBP": "EURGBP=X", "CHF": "EURCHF=X", "JPY": "EURJPY=X",
                 "CAD": "EURCAD=X", "HKD": "EURHKD=X", "SEK": "EURSEK=X", "DKK": "EURDKK=X", "NOK": "EURNOK=X"}


def euros_por_unidad(div: str, tipos: dict[str, float]) -> float | None:
    """Cuántos euros vale 1 unidad de la divisa. `tipos`: unidades por euro (como EURUSD=X)."""
    if div in ("EUR", "—"):
        return 1.0
    clave = "GBP" if div == "GBp" else div
    t = tipos.get(clave)
    if not t:
        return None
    return (1 / t) / (100 if div == "GBp" else 1)


def a_euros(importe: float, ticker: str, tipos: dict[str, float], info: dict | None = None) -> float | None:
    f = euros_por_unidad(divisa(ticker, info), tipos)
    return importe * f if f is not None else None


def historicos_en_euros(historicos: dict, cambios: dict) -> dict:
    """Convierte OHLC de cada valor a euros con la serie diaria de su tipo de cambio.
    `cambios`: {'USD': DataFrame de EURUSD=X, ...}. Los valores sin tipo de cambio se descartan."""
    import pandas as pd

    salida = {}
    for t, df in historicos.items():
        d = divisa(t)
        if d == "EUR":
            salida[t] = df
            continue
        clave = "GBP" if d == "GBp" else d
        fx = cambios.get(clave)
        if fx is None or fx.empty:
            continue
        f = (1 / fx["Close"]).reindex(df.index, method="ffill") / (100 if d == "GBp" else 1)
        conv = df.copy()
        for col in ("Open", "High", "Low", "Close"):
            conv[col] = df[col] * f
        salida[t] = conv.dropna(subset=["Close"]) if isinstance(conv, pd.DataFrame) else conv
    return salida
