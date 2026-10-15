"""Utilidades para trabajar JUNTO a la app de Bankinter.

Bankinter no ofrece a los clientes particulares una API pública para que otras apps lean la cartera
o envíen órdenes, así que esta app funciona como "copiloto":
  - te prepara la orden exacta para copiarla en Bankinter (orden limitada + stop-loss),
  - importa tu cartera desde el Excel/CSV que puedes descargar en Bankinter (o la escribes a mano),
  - vigila tus posiciones y te avisa de qué orden poner o modificar.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, timedelta

import pandas as pd

from .noticias import detectar_empresas
from .tickers import TODAS_LAS_ACCIONES, nombre_de


def _norm(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9 ]", " ", texto.lower()).strip()


SINONIMOS = {
    "nombre": ["valor", "nombre", "instrumento", "descripcion", "titulo", "producto", "emisora", "activo", "empresa"],
    "acciones": ["titulos", "n titulos", "num titulos", "cantidad", "acciones", "unidades", "participaciones",
                 "n acciones", "nominal"],
    "precio_medio": ["precio medio", "pr medio", "p medio", "precio compra", "precio de compra", "coste medio",
                     "precio adquisicion", "cambio medio", "precio medio compra"],
    "ticker": ["ticker", "simbolo", "symbol", "codigo"],
}


def numero(valor) -> float | None:
    """Convierte '1.234,56 €' o '1234.56' en float."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    s = re.sub(r"[^\d,.\-]", "", str(valor))
    if not s:
        return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    elif re.fullmatch(r"-?\d{1,3}(\.\d{3})+", s):
        s = s.replace(".", "")  # "1.200" en formato español = mil doscientos
    try:
        return float(s)
    except ValueError:
        return None


def buscar_ticker(texto: str) -> str | None:
    """'BANCO SANTANDER, S.A.' -> 'SAN.MC'. Devuelve None si no lo reconoce."""
    if not texto:
        return None
    t = str(texto).strip()
    if t.upper() in TODAS_LAS_ACCIONES:
        return t.upper()
    if f"{t.upper()}.MC" in TODAS_LAS_ACCIONES:
        return f"{t.upper()}.MC"
    encontrados = detectar_empresas(t)
    if encontrados:
        return encontrados[0]
    n = _norm(t)
    for ticker, (nombre, _, _) in TODAS_LAS_ACCIONES.items():
        if _norm(nombre.split(" (")[0]) in n:
            return ticker
    return None


def detectar_columnas(columnas) -> dict[str, str]:
    salida = {}
    normalizadas = {c: _norm(c) for c in columnas}
    for campo, sinonimos in SINONIMOS.items():
        for col, n in normalizadas.items():
            if col in salida.values():
                continue
            if any(n == s or n.startswith(s) or s in n for s in sinonimos):
                salida[campo] = col
                break
    return salida


def leer_posiciones(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza un Excel/CSV de posiciones a columnas: ticker, nombre, acciones, precio_medio.
    Si la cabecera no está en la primera fila (frecuente en exportaciones bancarias), la busca."""
    cols = detectar_columnas(df.columns)
    if "acciones" not in cols:
        for i in range(min(15, len(df))):
            fila = df.iloc[i].astype(str).tolist()
            if "acciones" in detectar_columnas(fila):
                df = df.iloc[i + 1:].copy()
                df.columns = fila
                cols = detectar_columnas(fila)
                break
    filas = []
    for _, r in df.iterrows():
        nombre = str(r.get(cols.get("nombre"), "") or "").strip() if "nombre" in cols else ""
        ticker_txt = str(r.get(cols.get("ticker"), "") or "").strip() if "ticker" in cols else ""
        acciones = numero(r.get(cols["acciones"])) if "acciones" in cols else None
        precio = numero(r.get(cols["precio_medio"])) if "precio_medio" in cols else None
        if not acciones or acciones <= 0 or not (nombre or ticker_txt):
            continue
        filas.append({"ticker": buscar_ticker(ticker_txt) or buscar_ticker(nombre) or "",
                      "nombre": nombre or ticker_txt, "acciones": int(acciones), "precio_medio": precio})
    return pd.DataFrame(filas, columns=["ticker", "nombre", "acciones", "precio_medio"])


def leer_archivo(archivo, nombre_archivo: str) -> pd.DataFrame:
    if nombre_archivo.lower().endswith((".xlsx", ".xls")):
        bruto = pd.read_excel(archivo)
    else:
        bruto = pd.read_csv(archivo, sep=None, engine="python", encoding_errors="replace")
    return leer_posiciones(bruto)


MERCADOS_BANKINTER = {".MC": "Mercado Continuo (España)", ".DE": "Xetra (Alemania)", ".PA": "Euronext París",
                      ".AS": "Euronext Ámsterdam", ".MI": "Borsa Italiana (Milán)", ".BR": "Euronext Bruselas",
                      ".HE": "Nasdaq Helsinki", ".L": "Bolsa de Londres", ".SW": "SIX (Suiza)",
                      ".CO": "Nasdaq Copenhague", ".T": "Bolsa de Tokio", ".HK": "Bolsa de Hong Kong",
                      ".KS": "Bolsa de Corea", ".TW": "Bolsa de Taiwán", ".NS": "Bolsa de India (NSE)",
                      ".TO": "Bolsa de Toronto", ".LS": "Euronext Lisboa"}


def mercado_de(ticker: str) -> str:
    if ticker.startswith("^") or ticker in ("DX-Y.NYB", "000001.SS"):
        return "Índice o indicador (no se compra directamente)"
    if ticker.startswith("0P"):
        return "Fondo de inversión (sección Fondos de tu banco)"
    if ticker.endswith("=X"):
        return "Mercado de divisas"
    if ticker.endswith("=F"):
        return "Futuros de materias primas"
    if ticker.endswith("-EUR"):
        return "Criptomonedas"
    for sufijo, nombre in MERCADOS_BANKINTER.items():
        if ticker.endswith(sufijo):
            return nombre
    return "NYSE / Nasdaq (EEUU)"


def _num(x: float, decimales: int = 2) -> str:
    return f"{x:,.{decimales}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _precio(x: float, ticker: str) -> str:
    from .costes import simbolo

    return f"{_num(x)} {simbolo(ticker)}"


# Bróker del usuario (lo fija la app al arrancar). Los textos de Bankinter cambian si usa otro.
BROKER = "Bankinter"


def es_bankinter() -> bool:
    return BROKER == "Bankinter"


def _cabecera(ticker: str, titulo: str) -> list[str]:
    donde = BROKER if BROKER != "Otro" else "tu bróker"
    return [f"{titulo} · {nombre_de(ticker)}",
            f"Buscar en {donde}: «{nombre_de(ticker).split(' (')[0]}» · {mercado_de(ticker)}"]


def ticket_compra(ticker: str, acciones: int, precio_ref: float, dias_validez: int = 7,
                  tarifa=None, importe_eur: float | None = None) -> str:
    """Orden de compra limitada, con los campos del formulario de Bankinter."""
    validez = date.today() + timedelta(days=dias_validez)
    lineas = _cabecera(ticker, "COMPRA") + [
        "Operación ........ Compra",
        "Tipo de orden .... Limitada",
        f"Títulos .......... {acciones}",
        f"Precio límite .... {_precio(precio_ref, ticker)}",
        f"Validez .......... hasta el {validez:%d/%m/%Y}",
    ]
    if tarifa is not None and importe_eur:
        from .costes import coste_compra

        c = coste_compra(importe_eur, ticker, tarifa)
        partes = [f"comisión {_num(c['comision'])} €"]
        if c["cambio"]:
            partes.append(f"cambio de divisa {_num(c['cambio'])} €")
        if c["itf"]:
            partes.append(f"tasa Tobin {_num(c['itf'])} €")
        lineas.append(f"Coste estimado ... {' + '.join(partes)}")
    lineas.append(f"El precio límite es el último cierre: si en {_donde()} ves otro precio, usa ese, "
                  "pero no pagues más de un 1 % por encima.")
    return "\n".join(lineas)


def ticket_stop(ticker: str, acciones: int, activacion: float, margen: float = 0.02) -> str:
    """Orden Stop de venta para limitar pérdidas (en Bankinter exige precio límite)."""
    limite = activacion * (1 - margen)
    return "\n".join(_cabecera(ticker, "PROTECCIÓN (stop-loss)") + [
        "Operación ............. Venta",
        "Tipo de orden ......... Stop",
        f"Condición de activación  cotización menor o igual que {_precio(activacion, ticker)}",
        f"Precio límite ......... {_precio(limite, ticker)} ({margen * 100:.0f} % por debajo, para que se venda "
        "aunque caiga deprisa)",
        f"Títulos ............... {acciones}",
        "Validez ............... la más larga que permita la app",
    ] + (["En Bankinter las órdenes stop no se pueden modificar: para cambiar el nivel, cancela esta y crea otra."]
         if es_bankinter() else ["Si tu bróker no permite poner precio límite, usa una orden stop normal."]))


def ticket_stop_relacionadas(ticker: str, acciones: int, stop: float, objetivo: float,
                             margen: float = 0.02) -> str:
    """'Stop relacionadas': stop de pérdidas + stop de beneficios; al ejecutarse una, Bankinter cancela la otra."""
    nombre_orden = "órdenes «stop relacionadas»" if es_bankinter() else "orden OCO: «una cancela la otra»"
    return "\n".join(_cabecera(ticker, f"PROTECCIÓN + OBJETIVO ({nombre_orden})") + [
        f"Títulos ............... {acciones}",
        f"Stop a la baja ........ activación ≤ {_precio(stop, ticker)} · límite {_precio(stop * (1 - margen), ticker)}",
        f"Stop al alza .......... activación ≥ {_precio(objetivo, ticker)} · límite "
        f"{_precio(objetivo * 0.99, ticker)}",
        f"Cuando se ejecuta una de las dos, {_donde()} cancela la otra automáticamente"
        + ("." if es_bankinter() else " (si tu bróker no tiene este tipo de orden, pon solo el stop-loss)."),
    ])


def _donde() -> str:
    return BROKER if BROKER != "Otro" else "tu bróker"


def ticket_venta(ticker: str, acciones: int, precio_ref: float) -> str:
    return "\n".join(_cabecera(ticker, "VENTA") + [
        "Operación ........ Venta",
        "Tipo de orden .... Limitada",
        f"Títulos .......... {acciones}",
        f"Precio límite .... {_precio(precio_ref * 0.995, ticker)} (medio punto por debajo del último precio, para "
        "que se ejecute)",
        "Validez .......... hoy",
        "Si tenías una orden stop sobre estas acciones, cancélala después de vender.",
    ])


def ticket(ticker: str, operacion: str, acciones: int, precio: float, stop: float | None = None,
           objetivo: float | None = None, dias_validez: int = 7) -> str:
    """Compatibilidad: compra (con protección si se indica stop), venta o venta stop."""
    op = operacion.lower()
    if op.startswith("venta stop") or op.startswith("stop"):
        return ticket_stop(ticker, acciones, precio)
    if op.startswith("venta"):
        return ticket_venta(ticker, acciones, precio)
    partes = [ticket_compra(ticker, acciones, precio, dias_validez)]
    if stop and objetivo:
        partes.append(ticket_stop_relacionadas(ticker, acciones, stop, objetivo))
    elif stop:
        partes.append(ticket_stop(ticker, acciones, stop))
    return "\n\n".join(partes)


def consejo_posicion(precio: float, precio_medio: float, stop: float | None, stop_sugerido: float | None,
                     puntuacion: int | None, umbral_venta: int = 40, resultados_pronto: bool = False,
                     sin_stop: bool = False, alarma: float | None = None) -> tuple[str, str]:
    """(nivel, texto). nivel: 'vender', 'vigilar', 'subir_stop', 'mantener', 'poner_stop'.
    `sin_stop`: la compraste sin stop-loss y quieres solo vigilarla; `alarma`: precio que avisa pero no vende."""
    if stop and precio <= stop:
        return "vender", ("Ha tocado tu stop-loss: según tu plan, toca vender (si tenías la orden stop puesta en "
                          f"{_donde()}, ya se habrá vendido; compruébalo en tus órdenes).")
    if puntuacion is not None and puntuacion < umbral_venta:
        return "vigilar", (f"La puntuación técnica ha bajado a {puntuacion}/100: la tendencia se ha estropeado. "
                           "Plantéate vender o, al menos, acercar el stop.")
    if not stop and sin_stop:
        if alarma and precio <= alarma:
            return "vigilar", (f"Ha bajado de tu nivel de alarma ({_num(alarma)}). No tiene stop-loss, así que no se "
                               "vende sola: decide con calma si el motivo por el que la compraste sigue en pie.")
        texto = "Sin stop-loss, la vigilas tú" + (f": te aviso si baja de {_num(alarma)}." if alarma else ".")
        if resultados_pronto:
            texto += " Ojo: presenta resultados en los próximos días."
        return "mantener", texto
    if not stop:
        return "poner_stop", (f"No tienes stop-loss registrado. Crea en {_donde()} una orden Stop de venta con "
                              f"activación en {_num(stop_sugerido)} para limitar pérdidas." if stop_sugerido else
                              "No tienes stop-loss registrado.")
    if stop_sugerido and stop_sugerido > stop * 1.01 and precio > precio_medio:
        return "subir_stop", (f"Vas ganando: sube el stop de {_num(stop)} a {_num(stop_sugerido)} para asegurar "
                              "parte de la ganancia" + (" (en Bankinter: cancela la orden stop actual y crea otra)."
                                                         if es_bankinter() else "."))
    texto = "Todo en orden: mantener."
    if resultados_pronto:
        texto += " Ojo: presenta resultados en los próximos días."
    return "mantener", texto
