"""Genera `bolsa/catalogo_mundial.json`: todas las acciones de la bolsa española y las de los índices
principales de cada país (con el buscador de acciones de Yahoo y la lista oficial del S&P 500).

Uso:
    python scripts/generar_catalogo.py

Se repite solo cada sábado en GitHub Actions (.github/workflows/actualizar.yml). Se puede repetir a mano (las empresas que entran o salen de bolsa cambian poco). Lo que no esté en el
catálogo se encuentra igualmente con el buscador de la app (nombre, ticker o ISIN).
"""

from __future__ import annotations

import csv
import io
import json
import re
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

SALIDA = RAIZ / "bolsa" / "catalogo_mundial.json"
SP500_CSV = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"

# grupo -> [(bolsa en Yahoo, país, cuántas como máximo, de mayor a menor tamaño)]
# (Muchas bolsas cotizan también empresas de fuera, p. ej. Nvidia en Fráncfort: se quitan, ver `main`.)
ROTACION_MINIMA = 0.01
MERCADOS = {
    "Alemania": [("GER", "de", 160)],
    "Francia": [("PAR", "fr", 130)],
    "Italia": [("MIL", "it", 90)],
    "Países Bajos y Bélgica": [("AMS", "nl", 60), ("BRU", "be", 40)],
    "Portugal, Irlanda, Austria y Finlandia": [("LIS", "pt", 15), ("ISE", "ie", 10), ("VIE", "at", 25),
                                               ("HEL", "fi", 40)],
    "Reino Unido": [("LSE", "gb", 150)],
    "Suiza": [("EBS", "ch", 80)],
    "Suecia": [("STO", "se", 80)],
    "Dinamarca y Noruega": [("CPH", "dk", 40), ("OSL", "no", 40)],
    "Japón": [("JPX", "jp", 100)],
    "China y Hong Kong": [("HKG", "hk", 80)],
    "Corea del Sur y Taiwán": [("KSC", "kr", 40), ("TAI", "tw", 40)],
    "India": [("NSI", "in", 60)],
    "Australia": [("ASX", "au", 60)],
    "Canadá": [("TOR", "ca", 70)],
    "Brasil y México": [("SAO", "br", 40), ("MEX", "mx", 30)],
}

SECTORES_SP = {
    "Information Technology": "Tecnología", "Health Care": "Salud", "Financials": "Financiero",
    "Consumer Discretionary": "Consumo discrecional", "Consumer Staples": "Consumo básico",
    "Communication Services": "Comunicaciones", "Industrials": "Industria", "Energy": "Energía",
    "Utilities": "Eléctricas y agua", "Real Estate": "Inmobiliario", "Materials": "Materiales",
}

_FORMAS = re.compile(r"(,?\s+(S\.?A\.?U?\.?|S\.?p\.?A\.?|N\.?V\.?|SE|AG|plc|p\.l\.c|PLC|Inc\.?|Corp\.?|Corporation|"
                     r"Incorporated|Limited|Ltd\.?|ASA|AB|A/S|Oyj|SA/NV|S\.?A\.?B\.? de C\.?V\.?|Co\.,? Ltd\.?|"
                     r"Holdings?|Group|Company|\(publ\)|S\.?G\.?P\.?S|KGaA|GmbH|& Co\.?|and|S\.E|Aktiengesellschaft( in \w+)?|"
                     r"Soci[ée]t[ée] (anonyme|Europ[ée]enne|en commandite par actions)|société anonyme)\.?,?)+$",
                     re.I)
_RUIDO = {"the", "inc", "co", "corp", "corporation", "incorporated", "group", "holdings", "holding", "plc", "sa",
          "ag", "se", "nv", "and", "company", "class", "ltd", "limited"}


def limpiar(nombre: str) -> str:
    """«Industria de Diseño Textil, S.A.» -> «Industria de Diseño Textil»."""
    nombre = re.sub(r"\s+", " ", (nombre or "").strip())
    limpio = re.sub(r"^The\s+", "", _FORMAS.sub("", nombre).strip(" ,."))
    return limpio or nombre


def pantalla(bolsa: str, pais: str, maximo: int) -> list[dict]:
    import yfinance as yf
    from yfinance import EquityQuery as Q

    consulta = Q("and", [Q("eq", ["exchange", bolsa]), Q("eq", ["region", pais])])
    salida, desde = [], 0
    while len(salida) < maximo:
        for intento in range(4):
            try:
                r = yf.screen(consulta, offset=desde, size=min(250, maximo - len(salida) + 50),
                              sortField="intradaymarketcap", sortAsc=False)
                break
            except Exception:  # noqa: BLE001 - Yahoo limita a ratos: se espera y se repite
                time.sleep(3 * (intento + 1))
        else:
            break
        filas = r.get("quotes") or []
        if not filas:
            break
        for f in filas:
            nombre = f.get("longName") or f.get("shortName") or ""
            # Fuera preferentes, derechos y valores sin capitalización (suelen ser duplicados o warrants).
            if f.get("quoteType") != "EQUITY" or not f.get("marketCap") or "%" in nombre:
                continue
            precio = (f.get("regularMarketPrice") or 0) / (100 if f.get("currency") in ("GBp", "ZAc", "ILA") else 1)
            # Rotación: % del valor de la empresa que se negocia al día EN ESA BOLSA. Las de casa, >0,05 %; las
            # extranjeras que también cotizan allí (Nvidia en Fráncfort), <0,005 %.
            rotacion = (f.get("averageDailyVolume3Month") or 0) * precio / f["marketCap"] * 100
            salida.append({"t": f["symbol"], "n": limpiar(nombre), "cap": f["marketCap"], "rot": rotacion})
        desde += len(filas)
        if desde >= (r.get("total") or 0):
            break
    return salida[:maximo]


def espana() -> dict[str, dict]:
    """Toda la bolsa española: Mercado Continuo, BME Growth (empresas pequeñas y SOCIMIs) y Latibex."""
    from bolsa.tickers import IBEX35

    continuo, growth, latibex = {}, {}, {}
    for f in pantalla("MCE", "es", 400):
        t = f["t"]
        if t in IBEX35 or t.endswith("-D.MC") or "-D." in t:
            continue
        if t.startswith("X"):
            latibex[t] = [f["n"], "Latibex"]
        elif t.startswith("Y"):
            growth[t] = [f["n"], "BME Growth"]
        else:
            continuo[t] = [f["n"], "Mercado Continuo"]
    return {"España (Mercado Continuo)": continuo, "España (BME Growth y SOCIMIs pequeñas)": growth,
            "Latibex (Latinoamérica en euros)": latibex}


def eeuu() -> dict[str, dict]:
    """El S&P 500 entero por sectores, y las demás grandes de EEUU (Nasdaq y empresas extranjeras)."""
    import requests

    texto = requests.get(SP500_CSV, timeout=30).text
    grupos: dict[str, dict] = {}
    sp = set()
    for fila in csv.DictReader(io.StringIO(texto)):
        t = fila["Symbol"].strip().replace(".", "-")          # BRK.B -> BRK-B (como en Yahoo)
        sector = SECTORES_SP.get(fila["GICS Sector"], fila["GICS Sector"])
        grupos.setdefault(f"EEUU · {sector}", {})[t] = [limpiar(fila["Security"]), sector]
        sp.add(t)
    otras = {}
    for bolsa in ("NMS", "NYQ"):
        for f in pantalla(bolsa, "us", 250):
            if f["t"] not in sp and f["cap"] > 20e9:
                otras[f["t"]] = [f["n"], "EEUU (otras grandes)"]
    grupos["EEUU · Otras grandes (Nasdaq, ADR...)"] = otras
    return dict(sorted(grupos.items()))


def clave_nombre(nombre: str) -> str:
    """Para reconocer la misma empresa en dos bolsas: «Apple Inc.» y «Apple» -> «apple»."""
    sin_parentesis = re.sub(r"\(.*?\)", " ", nombre or "")
    palabras = [w for w in re.findall(r"[a-z0-9]+", limpiar(sin_parentesis).lower().replace("-", ""))
                if w not in _RUIDO]
    return "".join(palabras[:2])


def main():
    from bolsa.tickers import IBEX35

    catalogo = espana()
    catalogo.update(eeuu())
    # Empresas que ya tienen su sitio (el S&P 500 y la bolsa española): en otras bolsas no se repiten.
    ya_estan = {clave_nombre(v[0]) for g, vs in catalogo.items()
                if g.startswith("EEUU ·") and "Otras" not in g or g == "España (Mercado Continuo)" for v in vs.values()}
    ya_estan |= {clave_nombre(v[0]) for v in IBEX35.values()}
    for g, fuentes in MERCADOS.items():
        valores, vistas = {}, set()
        for b, p, maximo in fuentes:
            n = 0
            # En Brasil y México las primeras por tamaño son casi todas recibos de empresas de EEUU (BDR).
            for f in pantalla(b, p, 1200 if b in ("SAO", "MEX") else maximo * 6):
                k = clave_nombre(f["n"])
                if f["rot"] < ROTACION_MINIMA or k in ya_estan or k in vistas:
                    continue        # extranjera que también cotiza aquí, o la misma empresa con otra clase de acción
                vistas.add(k)
                valores[f["t"]] = [f["n"], g]
                n += 1
                if n >= maximo:
                    break
        catalogo[g] = valores
        print(f"{g}: {len(valores)}", flush=True)
    catalogo = {g: v for g, v in catalogo.items() if v}
    total = sum(len(v) for v in catalogo.values())
    if total < 1500 or len(catalogo) < 25:      # Yahoo ha fallado a medias: mejor quedarse con el anterior
        print(f"Solo {total} valores en {len(catalogo)} grupos: no se guarda")
        sys.exit(1)
    SALIDA.write_text(json.dumps(catalogo, ensure_ascii=False, indent=0, sort_keys=False), encoding="utf-8")
    print(f"Guardado {SALIDA} con {sum(len(v) for v in catalogo.values())} valores en {len(catalogo)} grupos")


if __name__ == "__main__":
    main()
