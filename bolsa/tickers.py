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

# Mercado Continuo: empresas españolas líquidas fuera del IBEX 35.
CONTINUO = {
    "VIS.MC": ("Viscofan", "Consumo", ["viscofan"]),
    "EBRO.MC": ("Ebro Foods", "Consumo", ["ebro foods"]),
    "FAE.MC": ("Faes Farma", "Salud", ["faes"]),
    "ALM.MC": ("Almirall", "Salud", ["almirall"]),
    "PSG.MC": ("Prosegur", "Servicios", ["prosegur"]),
    "TUB.MC": ("Tubacex", "Materiales", ["tubacex"]),
    "GEST.MC": ("Gestamp", "Automoción", ["gestamp"]),
    "A3M.MC": ("Atresmedia", "Medios", ["atresmedia"]),
    "PHM.MC": ("Pharma Mar", "Salud", ["pharma mar", "pharmamar"]),
    "MEL.MC": ("Meliá Hotels", "Turismo", ["meliá", "melia"]),
    "CAF.MC": ("CAF", "Industria", ["construcciones y auxiliar de ferrocarriles"]),
    "VID.MC": ("Vidrala", "Materiales", ["vidrala"]),
    "ENO.MC": ("Elecnor", "Construcción", ["elecnor"]),
    "ENC.MC": ("Ence", "Materiales", ["ence"]),
    "CIE.MC": ("CIE Automotive", "Automoción", ["cie automotive"]),
    "GRE.MC": ("Grenergy", "Energía", ["grenergy"]),
    "ECR.MC": ("Ercros", "Materiales", ["ercros"]),
}

# Grandes empresas europeas (Euro Stoxx 50 y similares).
EUROPA = {
    "ASML.AS": ("ASML", "Tecnología", ["asml"]),
    "SAP.DE": ("SAP", "Tecnología", ["sap se"]),
    "SIE.DE": ("Siemens", "Industria", ["siemens"]),
    "MC.PA": ("LVMH", "Lujo", ["lvmh", "louis vuitton"]),
    "RMS.PA": ("Hermès", "Lujo", ["hermès", "hermes"]),
    "OR.PA": ("L'Oréal", "Consumo", ["l'oréal", "loreal", "l'oreal"]),
    "TTE.PA": ("TotalEnergies", "Petróleo", ["totalenergies"]),
    "SAN.PA": ("Sanofi", "Salud", ["sanofi"]),
    "AIR.PA": ("Airbus", "Industria", ["airbus"]),
    "SAF.PA": ("Safran", "Industria", ["safran"]),
    "SU.PA": ("Schneider Electric", "Industria", ["schneider electric"]),
    "AI.PA": ("Air Liquide", "Materiales", ["air liquide"]),
    "BNP.PA": ("BNP Paribas", "Banca", ["bnp paribas", "bnp"]),
    "CS.PA": ("AXA", "Seguros", ["axa"]),
    "DG.PA": ("Vinci", "Construcción", ["vinci"]),
    "EL.PA": ("EssilorLuxottica", "Salud", ["essilorluxottica", "essilor"]),
    "ALV.DE": ("Allianz", "Seguros", ["allianz"]),
    "MUV2.DE": ("Munich Re", "Seguros", ["munich re"]),
    "DTE.DE": ("Deutsche Telekom", "Telecomunicaciones", ["deutsche telekom"]),
    "ADS.DE": ("Adidas", "Consumo", ["adidas"]),
    "BAS.DE": ("BASF", "Materiales", ["basf"]),
    "BAYN.DE": ("Bayer", "Salud", ["bayer"]),
    "BMW.DE": ("BMW", "Automoción", ["bmw"]),
    "MBG.DE": ("Mercedes-Benz", "Automoción", ["mercedes-benz", "mercedes"]),
    "VOW3.DE": ("Volkswagen", "Automoción", ["volkswagen"]),
    "ENEL.MI": ("Enel", "Eléctricas", ["enel"]),
    "ENI.MI": ("Eni", "Petróleo", ["eni"]),
    "ISP.MI": ("Intesa Sanpaolo", "Banca", ["intesa sanpaolo", "intesa"]),
    "UCG.MI": ("UniCredit", "Banca", ["unicredit"]),
    "INGA.AS": ("ING", "Banca", ["ing group", "ing bank"]),
    "ABI.BR": ("AB InBev", "Consumo", ["ab inbev", "anheuser"]),
    "NOKIA.HE": ("Nokia", "Tecnología", ["nokia"]),
}

# Grandes empresas de EEUU (Bankinter permite operar en el mercado americano).
EEUU = {
    "AAPL": ("Apple", "Tecnología", ["apple", "iphone"]),
    "MSFT": ("Microsoft", "Tecnología", ["microsoft"]),
    "NVDA": ("Nvidia", "Tecnología", ["nvidia"]),
    "AMZN": ("Amazon", "Consumo", ["amazon"]),
    "GOOGL": ("Alphabet (Google)", "Tecnología", ["google", "alphabet"]),
    "META": ("Meta (Facebook)", "Tecnología", ["meta platforms", "facebook", "zuckerberg"]),
    "TSLA": ("Tesla", "Automoción", ["tesla", "musk"]),
    "BRK-B": ("Berkshire Hathaway", "Financiero", ["berkshire", "buffett"]),
    "JPM": ("JPMorgan", "Banca", ["jpmorgan", "jp morgan"]),
    "BAC": ("Bank of America", "Banca", ["bank of america"]),
    "GS": ("Goldman Sachs", "Banca", ["goldman sachs", "goldman"]),
    "V": ("Visa", "Financiero", []),
    "MA": ("Mastercard", "Financiero", ["mastercard"]),
    "UNH": ("UnitedHealth", "Salud", ["unitedhealth"]),
    "JNJ": ("Johnson & Johnson", "Salud", ["johnson & johnson", "johnson and johnson"]),
    "LLY": ("Eli Lilly", "Salud", ["eli lilly", "lilly"]),
    "ABBV": ("AbbVie", "Salud", ["abbvie"]),
    "MRK": ("Merck", "Salud", ["merck"]),
    "PFE": ("Pfizer", "Salud", ["pfizer"]),
    "XOM": ("ExxonMobil", "Petróleo", ["exxon", "exxonmobil"]),
    "CVX": ("Chevron", "Petróleo", ["chevron"]),
    "PG": ("Procter & Gamble", "Consumo", ["procter"]),
    "KO": ("Coca-Cola", "Consumo", ["coca-cola", "coca cola"]),
    "PEP": ("PepsiCo", "Consumo", ["pepsico", "pepsi"]),
    "WMT": ("Walmart", "Consumo", ["walmart"]),
    "COST": ("Costco", "Consumo", ["costco"]),
    "MCD": ("McDonald's", "Consumo", ["mcdonald's", "mcdonalds"]),
    "NKE": ("Nike", "Consumo", ["nike"]),
    "HD": ("Home Depot", "Consumo", ["home depot"]),
    "DIS": ("Disney", "Medios", ["disney"]),
    "NFLX": ("Netflix", "Medios", ["netflix"]),
    "AVGO": ("Broadcom", "Tecnología", ["broadcom"]),
    "AMD": ("AMD", "Tecnología", ["amd"]),
    "INTC": ("Intel", "Tecnología", ["intel"]),
    "ORCL": ("Oracle", "Tecnología", ["oracle"]),
    "CRM": ("Salesforce", "Tecnología", ["salesforce"]),
    "ADBE": ("Adobe", "Tecnología", ["adobe"]),
    "CSCO": ("Cisco", "Tecnología", ["cisco"]),
    "BA": ("Boeing", "Industria", ["boeing"]),
    "CAT": ("Caterpillar", "Industria", ["caterpillar"]),
}

# Fondos cotizados (ETF): una sola compra = cientos de empresas. Lo más recomendable para empezar.
ETFS = {
    "VWCE.DE": ("Vanguard FTSE All-World (acumulación, en €)", "ETF Mundial", []),
    "IWDA.AS": ("iShares Core MSCI World (acumulación, en €)", "ETF Mundial", []),
    "SXR8.DE": ("iShares Core S&P 500 (acumulación, en €)", "ETF EEUU", []),
    "EXSA.DE": ("iShares STOXX Europe 600 (en €)", "ETF Europa", []),
    "BBVAI.MC": ("BBVA Accion IBEX 35 ETF", "ETF España", []),
    "IBGS.AS": ("iShares Euro Government Bond 1-3 años", "Renta fija", []),
    "XEON.DE": ("Xtrackers EUR Overnight Rate (monetario)", "Monetario", []),
}

# Índices mundiales y datos macro para buscar patrones (no se compran directamente).
INDICES_MUNDIALES = {
    "^FCHI": "CAC 40 (Francia)", "^FTSE": "FTSE 100 (Reino Unido)", "^N225": "Nikkei 225 (Japón)",
    "^HSI": "Hang Seng (Hong Kong)", "^DJI": "Dow Jones (EEUU)", "^RUT": "Russell 2000 (pequeñas EEUU)",
    "^TNX": "Rentabilidad del bono de EEUU a 10 años", "GC=F": "Oro",
}

MERCADOS = {
    "IBEX 35": IBEX35,
    "Mercado Continuo": CONTINUO,
    "Europa": EUROPA,
    "EEUU": EEUU,
    "ETF": ETFS,
}

TODAS_LAS_ACCIONES = {**IBEX35, **CONTINUO, **EUROPA, **EEUU, **ETFS}


def nombre_de(ticker: str) -> str:
    if ticker in INDICES:
        return INDICES[ticker]["nombre"]
    if ticker in TERMOMETROS:
        return TERMOMETROS[ticker]["nombre"]
    if ticker in INDICES_MUNDIALES:
        return INDICES_MUNDIALES[ticker]
    if ticker in TODAS_LAS_ACCIONES:
        return TODAS_LAS_ACCIONES[ticker][0]
    from .activos import ACTIVOS, CRIPTO, ORO, es_cripto

    if ticker in ORO:
        return ORO[ticker]
    if ticker in ACTIVOS:
        return ACTIVOS[ticker]["nombre"]
    if es_cripto(ticker):
        return CRIPTO[ticker.split("-")[0].upper()]
    return ticker


def sector_de(ticker: str) -> str:
    return TODAS_LAS_ACCIONES.get(ticker, ("", "—", []))[1]


def mercado_de(ticker: str) -> str:
    for nombre, grupo in MERCADOS.items():
        if ticker in grupo:
            return nombre
    return "Otros"


def indice_de_referencia(ticker: str) -> str:
    """Índice con el que se compara una acción (para el 'ambiente del mercado')."""
    if ticker.endswith(".MC"):
        return "^IBEX"
    if ticker.endswith((".AS", ".PA", ".DE", ".MI", ".BR", ".HE")):
        return "^STOXX50E"
    return "^GSPC"


def es_etf(ticker: str) -> bool:
    return ticker in ETFS
