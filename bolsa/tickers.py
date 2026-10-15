"""Catálogo de índices y acciones, con los nombres con los que aparecen en las noticias.

Los símbolos son los de Yahoo Finance (el sufijo .MC significa Bolsa de Madrid).
En la app de Bankinter busca la empresa por su nombre: allí no hace falta el sufijo.
La composición del IBEX 35 cambia en las revisiones trimestrales; revisa la lista si falta alguna.
"""

INDICES = {
    "^IBEX": {"nombre": "IBEX 35", "zona": "España",
              "que_es": "Las 35 empresas más negociadas de la Bolsa española."},
    "^STOXX50E": {"nombre": "Euro Stoxx 50", "zona": "Europa",
                  "que_es": "Las 50 mayores empresas de la zona euro."},
    "^GDAXI": {"nombre": "DAX", "zona": "Alemania",
               "que_es": "Las 40 mayores empresas alemanas."},
    "^GSPC": {"nombre": "S&P 500", "zona": "EEUU",
              "que_es": "Las 500 mayores empresas de EEUU. El índice que más mueve el mundo."},
    "^IXIC": {"nombre": "Nasdaq", "zona": "EEUU",
              "que_es": "Bolsa tecnológica de EEUU (Apple, Nvidia, Microsoft...)."},
}

# Termómetros del mercado (no se invierte en ellos directamente, pero avisan del ambiente).
TERMOMETROS = {
    "^VIX": {"nombre": "VIX (índice del miedo)",
             "que_es": "Mide el nerviosismo en Wall Street. Por debajo de 15: calma. Por encima de 25: miedo."},
    "EURUSD=X": {"nombre": "Euro / Dólar",
                 "que_es": "Cuántos dólares vale un euro. Afecta a lo que ganas si compras acciones de EEUU."},
    "BZ=F": {"nombre": "Petróleo Brent",
             "que_es": "Precio del barril. Si sube, suelen ganar Repsol y perder aerolíneas como IAG."},
}

# ticker -> (nombre, sector, palabras con las que aparece en las noticias)
IBEX35 = {
    "ACS.MC": ("ACS", "Construcción", ["acs", "florentino"]),
    "ACX.MC": ("Acerinox", "Materiales", ["acerinox"]),
    "AENA.MC": ("Aena", "Transporte", ["aena", "aeropuerto"]),
    "AMS.MC": ("Amadeus", "Tecnología", ["amadeus"]),
    "ANA.MC": ("Acciona", "Construcción", ["acciona"]),
    "ANE.MC": ("Acciona Energía", "Energía", ["acciona energía", "acciona energia"]),
    "BBVA.MC": ("BBVA", "Banca", ["bbva"]),
    "BKT.MC": ("Bankinter", "Banca", ["bankinter"]),
    "CABK.MC": ("CaixaBank", "Banca", ["caixabank"]),
    "CLNX.MC": ("Cellnex", "Telecomunicaciones", ["cellnex"]),
    "COL.MC": ("Inmobiliaria Colonial", "Inmobiliaria", ["colonial"]),
    "ELE.MC": ("Endesa", "Eléctricas", ["endesa"]),
    "ENG.MC": ("Enagás", "Energía", ["enagás", "enagas"]),
    "FDR.MC": ("Fluidra", "Industria", ["fluidra"]),
    "FER.MC": ("Ferrovial", "Construcción", ["ferrovial"]),
    "GRF.MC": ("Grifols", "Salud", ["grifols"]),
    "IAG.MC": ("IAG (Iberia, British Airways)", "Transporte", ["iag", "iberia", "british airways"]),
    "IBE.MC": ("Iberdrola", "Eléctricas", ["iberdrola"]),
    "IDR.MC": ("Indra", "Tecnología y Defensa", ["indra"]),
    "ITX.MC": ("Inditex", "Consumo", ["inditex", "zara"]),
    "LOG.MC": ("Logista", "Distribución", ["logista"]),
    "MAP.MC": ("Mapfre", "Seguros", ["mapfre"]),
    "MRL.MC": ("Merlin Properties", "Inmobiliaria", ["merlin"]),
    "MTS.MC": ("ArcelorMittal", "Materiales", ["arcelormittal", "arcelor"]),
    "NTGY.MC": ("Naturgy", "Energía", ["naturgy"]),
    "PUIG.MC": ("Puig", "Consumo", ["puig"]),
    "RED.MC": ("Redeia (Red Eléctrica)", "Eléctricas", ["redeia", "red eléctrica", "red electrica"]),
    "REP.MC": ("Repsol", "Petróleo", ["repsol"]),
    "ROVI.MC": ("Laboratorios Rovi", "Salud", ["rovi"]),
    "SAB.MC": ("Banco Sabadell", "Banca", ["sabadell"]),
    "SAN.MC": ("Banco Santander", "Banca", ["santander"]),
    "SCYR.MC": ("Sacyr", "Construcción", ["sacyr"]),
    "SLR.MC": ("Solaria", "Energía", ["solaria"]),
    "TEF.MC": ("Telefónica", "Telecomunicaciones", ["telefónica", "telefonica"]),
    "UNI.MC": ("Unicaja", "Banca", ["unicaja"]),
}

# Grandes empresas de EEUU muy seguidas (Bankinter permite operar en el mercado americano).
EEUU = {
    "AAPL": ("Apple", "Tecnología", ["apple", "iphone"]),
    "MSFT": ("Microsoft", "Tecnología", ["microsoft"]),
    "NVDA": ("Nvidia", "Tecnología", ["nvidia"]),
    "AMZN": ("Amazon", "Consumo", ["amazon"]),
    "GOOGL": ("Alphabet (Google)", "Tecnología", ["google", "alphabet"]),
    "META": ("Meta (Facebook)", "Tecnología", ["meta platforms", "facebook", "zuckerberg"]),
    "TSLA": ("Tesla", "Automoción", ["tesla", "musk"]),
}

# Fondos cotizados (ETF): una sola compra = cientos de empresas. Lo más recomendable para empezar.
ETFS = {
    "CSPX.L": ("iShares Core S&P 500 (acumulación)", "ETF EEUU", []),
    "IWDA.AS": ("iShares Core MSCI World (acumulación)", "ETF Mundial", []),
    "BBVAI.MC": ("BBVA Accion IBEX 35 ETF", "ETF España", []),
}

TODAS_LAS_ACCIONES = {**IBEX35, **EEUU, **ETFS}


def nombre_de(ticker: str) -> str:
    if ticker in INDICES:
        return INDICES[ticker]["nombre"]
    if ticker in TERMOMETROS:
        return TERMOMETROS[ticker]["nombre"]
    if ticker in TODAS_LAS_ACCIONES:
        return TODAS_LAS_ACCIONES[ticker][0]
    return ticker


def sector_de(ticker: str) -> str:
    return TODAS_LAS_ACCIONES.get(ticker, ("", "—", []))[1]
