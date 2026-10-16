"""Importa tu cartera desde cualquier banco o bróker: el archivo que descargas (CSV o Excel) o la tabla copiada
de su web. Reconoce columnas con nombres distintos según el banco, códigos ISIN, fondos, oro y criptomonedas.

Ningún banco español ofrece a particulares una forma oficial de que otra app lea sus inversiones, así que la
app nunca te pide usuario ni contraseña: tú descargas o copias tus posiciones y la app las analiza.
"""

from __future__ import annotations

import io
import re
from typing import Callable

import pandas as pd

from .activos import CRIPTO, clase_de
from .bankinter import _norm, buscar_ticker, numero

COLUMNAS = {
    "nombre": ["valor", "nombre", "instrumento", "descripcion", "titulo", "producto", "emisora", "activo", "empresa",
               "denominacion", "name", "security", "fondo", "nombre del valor"],
    "isin": ["isin", "codigo isin"],
    "ticker": ["ticker", "simbolo", "symbol", "codigo"],
    "mercado": ["mercado", "bolsa", "exchange", "market", "plaza"],
    "acciones": ["titulos", "n titulos", "no titulos", "no de titulos", "nº titulos", "num titulos", "numero de titulos", "cantidad", "acciones", "unidades",
                 "participaciones", "n acciones", "nominal", "quantity", "shares", "posicion", "títulos depositados",
                 "titulos depositados", "units"],
    "precio_medio": ["precio medio", "pr medio", "p medio", "precio compra", "precio de compra", "coste medio",
                     "precio adquisicion", "cambio medio", "precio medio compra", "average price", "avg price",
                     "precio medio de compra", "coste unitario", "pmc", "precio"],
    "coste_total": ["importe invertido", "coste total", "coste de adquisicion", "valor de adquisicion",
                    "precio de coste", "inversion", "importe de compra", "cost basis", "total cost"],
    "valor_mercado": ["valoracion", "valor de mercado", "valor mercado", "importe valorado", "market value",
                      "valor actual", "saldo"],
    "divisa": ["divisa", "moneda", "currency"],
}

# Mercado que escriben los bancos -> sufijo de Yahoo.
SUFIJO_MERCADO = {"continuo": ".MC", "mercado continuo": ".MC", "bme": ".MC", "madrid": ".MC", "mc": ".MC",
                  "xetra": ".DE", "frankfurt": ".DE", "paris": ".PA", "euronext paris": ".PA", "amsterdam": ".AS",
                  "milan": ".MI", "lisboa": ".LS", "bruselas": ".BR", "londres": ".L", "london": ".L",
                  "nasdaq": "", "nyse": "", "eeuu": "", "usa": ""}

# ISIN de ETF habituales -> su cotización en euros (Yahoo a veces solo devuelve la de Londres, en dólares).
ISIN_CONOCIDOS = {"IE00B4L5Y983": "IWDA.AS", "IE00BK5BQT80": "VWCE.DE", "IE00B5BMR087": "SXR8.DE",
                  "DE0002635307": "EXSA.DE", "IE00B14X4Q57": "IBGS.AS", "LU0290358497": "XEON.DE",
                  "DE000A0S9GB0": "4GLD.DE"}

PATRON_ISIN = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}\d$")


def _columna(columnas, campo: str, usadas: set) -> str | None:
    normal = {c: _norm(str(c)) for c in columnas}
    sinonimos = [_norm(s) for s in COLUMNAS[campo]]
    for c, n in normal.items():   # primero coincidencia exacta
        if c not in usadas and n in sinonimos:
            return c
    for c, n in normal.items():
        if c not in usadas and any(n.startswith(s) for s in sinonimos):
            return c
    clave = PALABRA_CLAVE.get(campo)   # p. ej. «Títulos disponibles hoy»
    for c, n in normal.items():
        if clave and c not in usadas and re.search(rf"\b{clave}\b", n):
            return c
    return None


PALABRA_CLAVE = {"acciones": "(titulos|participaciones|cantidad|acciones)", "isin": "isin",
                 "precio_medio": "(precio medio|coste medio)"}


def detectar(columnas) -> dict[str, str]:
    salida, usadas = {}, set()
    for campo in ["isin", "ticker", "mercado", "acciones", "precio_medio", "coste_total", "valor_mercado", "divisa",
                  "nombre"]:
        c = _columna(columnas, campo, usadas)
        if c is not None:
            salida[campo] = c
            usadas.add(c)
    return salida


def _buscar_cabecera(df: pd.DataFrame) -> pd.DataFrame:
    """Muchas exportaciones tienen filas de resumen antes de la cabecera: la busca en las primeras filas."""
    if "acciones" in detectar(df.columns):
        return df
    for i in range(min(20, len(df))):
        fila = [str(x) for x in df.iloc[i].tolist()]
        if "acciones" in detectar(fila):
            nuevo = df.iloc[i + 1:].copy()
            nuevo.columns = fila
            return nuevo
    return df


def es_isin(texto: str) -> bool:
    return bool(PATRON_ISIN.match(str(texto).strip().upper()))


def ticker_cripto(texto: str) -> str | None:
    t = _norm(texto)
    for simbolo, nombre in CRIPTO.items():
        if t in (simbolo.lower(), _norm(nombre)) or t.startswith(_norm(nombre)):
            return f"{simbolo}-EUR"
    return None


def leer_tabla(df: pd.DataFrame, resolver: Callable[[str], dict | None] | None = None) -> pd.DataFrame:
    """Convierte la tabla de cualquier banco en filas: ticker, nombre, isin, acciones, precio_medio, clase.
    `resolver(isin_o_nombre)` -> {'symbol', 'name', 'type'} busca en Internet lo que no se reconoce."""
    df = _buscar_cabecera(df)
    cols = detectar(df.columns)
    filas = []
    for _, r in df.iterrows():
        def campo(nombre):
            return r.get(cols[nombre]) if nombre in cols else None

        nombre = str(campo("nombre") or "").strip()
        nombre = "" if nombre.lower() == "nan" else nombre
        isin = str(campo("isin") or "").strip().upper()
        isin = isin if es_isin(isin) else ""
        ticker_txt = str(campo("ticker") or "").strip().upper()
        ticker_txt = "" if ticker_txt in ("NAN", "NONE") else ticker_txt
        if not isin and es_isin(ticker_txt):
            isin, ticker_txt = ticker_txt, ""
        if not isin and es_isin(nombre):
            isin = nombre.upper()
        cantidad = numero(campo("acciones"))
        if not cantidad or cantidad <= 0 or not (nombre or ticker_txt or isin):
            continue
        precio = numero(campo("precio_medio"))
        if not precio and numero(campo("coste_total")):
            precio = numero(campo("coste_total")) / cantidad
        ticker, tipo = "", None
        if ticker_txt:
            mercado = _norm(str(campo("mercado") or ""))
            sufijo = SUFIJO_MERCADO.get(mercado)
            if sufijo is not None and "." not in ticker_txt and "-" not in ticker_txt:
                ticker = ticker_txt + sufijo
            else:
                ticker = buscar_ticker(ticker_txt) or ticker_txt
        # «Santander Acciones Españolas FI» es un fondo, no la acción de Santander: en los fondos manda el ISIN.
        es_fondo = bool(re.search(r"\b(fi|fim|fondo|fund|etf|ucits|sicav|plan de pensiones|pp)\b", _norm(nombre or "")))
        ticker = ticker or ISIN_CONOCIDOS.get(isin) or ""
        if not ticker and es_fondo and resolver and isin:
            hallado = resolver(isin)
            if hallado:
                ticker, tipo = hallado["symbol"], hallado.get("type")
        ticker = ticker or ticker_cripto(nombre) or ticker_cripto(ticker_txt) \
            or ("" if es_fondo else buscar_ticker(nombre)) or ""
        if not ticker and resolver:
            hallado = resolver(isin) if isin else None
            hallado = hallado or (resolver(nombre) if nombre else None)
            if hallado:
                ticker, tipo = hallado["symbol"], hallado.get("type")
                nombre = nombre or hallado.get("name", "")
        filas.append({"ticker": ticker, "nombre": nombre or ticker_txt or isin, "isin": isin,
                      "acciones": int(cantidad) if float(cantidad).is_integer() else round(float(cantidad), 8),
                      "precio_medio": precio, "clase": clase_de(ticker, tipo, nombre) if ticker else "—"})
    return pd.DataFrame(filas, columns=["ticker", "nombre", "isin", "acciones", "precio_medio", "clase"])


def leer_archivo(archivo, nombre_archivo: str, resolver=None) -> pd.DataFrame:
    if nombre_archivo.lower().endswith((".xlsx", ".xls")):
        bruto = pd.read_excel(archivo, header=None)
        bruto.columns = [str(c) for c in bruto.iloc[0]]
        bruto = bruto.iloc[1:]
    else:
        contenido = archivo.read()
        texto = None
        for codificacion in ("utf-8-sig", "latin-1"):
            try:
                texto = contenido.decode(codificacion) if isinstance(contenido, bytes) else contenido
                break
            except UnicodeDecodeError:
                continue
        bruto = _csv(texto or "")
    return leer_tabla(bruto, resolver)


def _csv(texto: str) -> pd.DataFrame:
    """Lee texto separado por ';', ',', tabuladores o '|', aunque las filas tengan distinto número de campos."""
    lineas = [x for x in texto.splitlines() if x.strip()]
    if not lineas:
        return pd.DataFrame()
    muestra = "\n".join(lineas[:30])
    sep = max([";", "\t", ",", "|"], key=lambda s: muestra.count(s))
    ancho = max(len(x.split(sep)) for x in lineas[:50])
    return pd.read_csv(io.StringIO("\n".join(lineas)), sep=sep, header=None, names=range(ancho), dtype=str,
                       engine="python", quotechar='"').pipe(_primera_fila_cabecera)


def _primera_fila_cabecera(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [str(c) for c in df.iloc[0]]
    return df.iloc[1:]


def leer_texto(texto: str, resolver=None) -> pd.DataFrame:
    """La tabla copiada de la web o la app del banco (pegada tal cual)."""
    return leer_tabla(_csv(texto), resolver)


__all__ = ["leer_tabla", "leer_archivo", "leer_texto", "detectar", "es_isin", "ticker_cripto"]
