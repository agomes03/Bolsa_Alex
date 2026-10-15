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


def mercado_de(ticker: str) -> str:
    if ticker.endswith(".MC"):
        return "Mercado Continuo (Bolsa de Madrid)"
    if ticker.endswith((".AS", ".PA", ".DE", ".MI", ".L")):
        return "Bolsa europea"
    return "NYSE / Nasdaq (EEUU)"


def _num(x: float, moneda: str) -> str:
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + f" {moneda}"


def ticket(ticker: str, operacion: str, acciones: int, precio: float, stop: float | None = None,
           objetivo: float | None = None, dias_validez: int = 7) -> str:
    """Texto con los campos exactos del formulario de órdenes de Bankinter."""
    moneda = "€" if ticker.endswith((".MC", ".AS", ".PA", ".DE", ".MI")) else "$"
    validez = date.today() + timedelta(days=dias_validez)
    lineas = [
        f"ORDEN PARA BANKINTER — {operacion.upper()}",
        f"Valor ........... {nombre_de(ticker)} ({ticker.split('.')[0]})",
        f"Mercado ......... {mercado_de(ticker)}",
        f"Operación ....... {operacion}",
    ]
    if operacion.lower().startswith("venta stop") or operacion.lower().startswith("stop"):
        lineas += ["Tipo de orden ... Stop (de pérdidas)",
                   f"Precio disparo .. {_num(precio, moneda)}"]
    else:
        lineas += ["Tipo de orden ... Limitada",
                   f"Precio límite ... {_num(precio, moneda)}"]
    lineas += [f"Títulos ......... {acciones}",
               f"Validez ......... hasta el {validez:%d/%m/%Y}"]
    if stop:
        lineas.append(f"Después ......... orden STOP de venta a {_num(stop, moneda)} (protege tu dinero)")
    if objetivo:
        lineas.append(f"Opcional ........ venta limitada a {_num(objetivo, moneda)} (objetivo)")
    return "\n".join(lineas)


def consejo_posicion(precio: float, precio_medio: float, stop: float | None, stop_sugerido: float | None,
                     puntuacion: int | None, umbral_venta: int = 40, resultados_pronto: bool = False) -> tuple[str, str]:
    """(nivel, texto). nivel: 'vender', 'vigilar', 'subir_stop', 'mantener', 'poner_stop'."""
    if stop and precio <= stop:
        return "vender", "Ha tocado tu stop-loss: según tu plan, toca vender (si tenías la orden puesta, ya se habrá vendido)."
    if puntuacion is not None and puntuacion < umbral_venta:
        return "vigilar", (f"La puntuación ha bajado a {puntuacion}: la tendencia se ha estropeado. "
                           "Plantéate vender o, como mínimo, ajusta el stop-loss.")
    if not stop:
        return "poner_stop", (f"No tienes stop-loss registrado. Ponlo en Bankinter a {stop_sugerido:.2f} para "
                              "limitar pérdidas." if stop_sugerido else "No tienes stop-loss registrado.")
    if stop_sugerido and stop_sugerido > stop * 1.01 and precio > precio_medio:
        return "subir_stop", (f"Vas ganando: sube el stop-loss de {stop:.2f} a {stop_sugerido:.2f} para asegurar "
                              "parte de la ganancia (en Bankinter: modifica la orden stop).")
    texto = "Todo en orden: mantener."
    if resultados_pronto:
        texto += " Ojo: presenta resultados en los próximos días."
    return "mantener", texto
