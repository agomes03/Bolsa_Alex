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

# --------------------------------------------------------------------------- catálogo ampliado
# Todo lo que se puede consultar y practicar en la app (Analizar, Mercados, cartera virtual). No entra en el
# informe diario ni en las carteras modelo, que siguen con el universo de arriba (validado en el laboratorio).
# Todos los códigos están comprobados con datos reales de Yahoo Finance.
REINO_UNIDO_SUIZA = {
    "HSBA.L": ("HSBC", "Banca", ["hsbc"]), "SHEL.L": ("Shell", "Petróleo", ["shell"]),
    "AZN.L": ("AstraZeneca", "Salud", ["astrazeneca"]), "ULVR.L": ("Unilever", "Consumo", ["unilever"]),
    "BP.L": ("BP", "Petróleo", ["bp"]), "RIO.L": ("Rio Tinto", "Materiales", ["rio tinto"]),
    "GSK.L": ("GSK", "Salud", ["gsk", "glaxo"]), "BARC.L": ("Barclays", "Banca", ["barclays"]),
    "LSEG.L": ("London Stock Exchange Group", "Financiero", ["london stock exchange"]),
    "NESN.SW": ("Nestlé", "Consumo", ["nestlé", "nestle"]), "NOVN.SW": ("Novartis", "Salud", ["novartis"]),
    "RO.SW": ("Roche", "Salud", ["roche"]), "UBSG.SW": ("UBS", "Banca", ["ubs"]),
    "ZURN.SW": ("Zurich Insurance", "Seguros", ["zurich insurance"]),
    "NOVO-B.CO": ("Novo Nordisk", "Salud", ["novo nordisk", "ozempic", "wegovy"]),
}
ASIA = {
    "7203.T": ("Toyota", "Automoción", ["toyota"]), "6758.T": ("Sony", "Tecnología", ["sony"]),
    "9984.T": ("SoftBank Group", "Tecnología", ["softbank"]), "7974.T": ("Nintendo", "Consumo", ["nintendo"]),
    "8306.T": ("Mitsubishi UFJ", "Banca", ["mitsubishi ufj", "mufg"]),
    "0700.HK": ("Tencent", "Tecnología", ["tencent"]), "9988.HK": ("Alibaba (Hong Kong)", "Consumo", ["alibaba"]),
    "1299.HK": ("AIA Group", "Seguros", ["aia group"]), "1810.HK": ("Xiaomi", "Tecnología", ["xiaomi"]),
    "005930.KS": ("Samsung Electronics", "Tecnología", ["samsung"]),
    "2330.TW": ("TSMC (Taiwán)", "Tecnología", ["tsmc"]), "RELIANCE.NS": ("Reliance Industries", "Energía", ["reliance"]),
}
OTROS_MERCADOS = {
    "TSM": ("TSMC (ADR en EEUU)", "Tecnología", []), "BABA": ("Alibaba (ADR en EEUU)", "Consumo", []),
    "INFY": ("Infosys (ADR en EEUU)", "Tecnología", ["infosys"]), "VALE": ("Vale (ADR en EEUU)", "Materiales", ["vale"]),
    "SHOP.TO": ("Shopify", "Tecnología", ["shopify"]), "RY.TO": ("Royal Bank of Canada", "Banca", ["royal bank of canada"]),
    "PLTR": ("Palantir", "Tecnología", ["palantir"]), "UBER": ("Uber", "Transporte", ["uber"]),
    "PYPL": ("PayPal", "Financiero", ["paypal"]), "SPOT": ("Spotify", "Medios", ["spotify"]),
}
FONDOS_INDEXADOS = {
    "0P00000WLG.F": ("Vanguard Global Stock Index (MSCI World) € Acc", "Fondo mundial", []),
    "0P0001CLDK.F": ("Fidelity MSCI World Index EUR P Acc", "Fondo mundial", []),
    "0P00012PP6.F": ("Amundi Index MSCI World AE-C", "Fondo mundial", []),
    "0P0001AINF.F": ("iShares Developed World Index (IE) D Acc EUR", "Fondo mundial", []),
    "0P00000SUJ.F": ("Vanguard U.S. 500 Stock Index € Acc", "Fondo EEUU", []),
    "0P00012SJB.F": ("Amundi S&P 500 Screened Index AE Acc", "Fondo EEUU", []),
    "0P00000RQ8.F": ("Vanguard European Stock Index € Acc", "Fondo Europa", []),
    "0P00012I6A.F": ("Vanguard Emerging Markets Stock Index € Acc", "Fondo emergentes", []),
    "0P0000XR9M.F": ("Vanguard Global Small-Cap Index € Acc", "Fondo pequeñas empresas", []),
    "0P00012I69.F": ("Vanguard Global Bond Index € Hedged Acc", "Renta fija", []),
}
MAS_ETFS = {
    "EUNL.DE": ("iShares Core MSCI World (Xetra, €)", "ETF Mundial", []),
    "XDWD.DE": ("Xtrackers MSCI World (€)", "ETF Mundial", []),
    "VGWL.DE": ("Vanguard FTSE All-World (distribución, €)", "ETF Mundial", []),
    "IS3N.DE": ("iShares Core MSCI Emerging Markets IMI (€)", "ETF Emergentes", []),
    "EMIM.AS": ("iShares Core MSCI EM IMI (Ámsterdam, €)", "ETF Emergentes", []),
    "VUSA.AS": ("Vanguard S&P 500 (distribución, €)", "ETF EEUU", []),
    "SXRV.DE": ("iShares Nasdaq 100 (€)", "ETF EEUU", []),
    "EXS1.DE": ("iShares Core DAX (€)", "ETF Alemania", []),
    "EUNA.DE": ("iShares Core Global Aggregate Bond (€)", "Renta fija", []),
    "4GLD.DE": ("Xetra-Gold (oro físico, €)", "Oro", []),
    "SGLD.L": ("Invesco Physical Gold", "Oro", []),
}
CRIPTOMONEDAS = {f"{c}-EUR": (n, "Criptomoneda", [n.lower()]) for c, n in
                 [("BTC", "Bitcoin"), ("ETH", "Ethereum"), ("SOL", "Solana"), ("XRP", "XRP"), ("ADA", "Cardano"),
                  ("BNB", "BNB"), ("DOGE", "Dogecoin"), ("DOT", "Polkadot"), ("LTC", "Litecoin")]}
DIVISAS = {
    "USDEUR=X": ("Dólar estadounidense (USD/EUR)", "Divisa", []), "GBPEUR=X": ("Libra esterlina (GBP/EUR)", "Divisa", []),
    "CHFEUR=X": ("Franco suizo (CHF/EUR)", "Divisa", []), "JPYEUR=X": ("Yen japonés (JPY/EUR)", "Divisa", []),
    "CADEUR=X": ("Dólar canadiense (CAD/EUR)", "Divisa", []), "AUDEUR=X": ("Dólar australiano (AUD/EUR)", "Divisa", []),
    "CNYEUR=X": ("Yuan chino (CNY/EUR)", "Divisa", []), "MXNEUR=X": ("Peso mexicano (MXN/EUR)", "Divisa", []),
}
MATERIAS_PRIMAS = {
    "GC=F": ("Oro (futuro, $/onza)", "Metales", ["oro"]), "SI=F": ("Plata (futuro, $/onza)", "Metales", ["plata"]),
    "PL=F": ("Platino (futuro, $/onza)", "Metales", ["platino"]), "HG=F": ("Cobre (futuro, $/libra)", "Metales", ["cobre"]),
    "BZ=F": ("Petróleo Brent (futuro, $/barril)", "Energía", ["brent"]),
    "CL=F": ("Petróleo WTI (futuro, $/barril)", "Energía", ["wti"]),
    "NG=F": ("Gas natural (futuro, $)", "Energía", ["gas natural"]),
    "ZW=F": ("Trigo (futuro, $)", "Agrícolas", ["trigo"]), "ZC=F": ("Maíz (futuro, $)", "Agrícolas", ["maíz"]),
    "KC=F": ("Café (futuro, $)", "Agrícolas", ["café"]), "CC=F": ("Cacao (futuro, $)", "Agrícolas", ["cacao"]),
    "SB=F": ("Azúcar (futuro, $)", "Agrícolas", ["azúcar"]),
}
INDICES_TODOS = {
    "^IBEX": ("IBEX 35 (España)", "Índice", []), "^STOXX50E": ("Euro Stoxx 50 (zona euro)", "Índice", []),
    "^GDAXI": ("DAX (Alemania)", "Índice", []), "^FCHI": ("CAC 40 (Francia)", "Índice", []),
    "FTSEMIB.MI": ("FTSE MIB (Italia)", "Índice", []), "^AEX": ("AEX (Países Bajos)", "Índice", []),
    "^FTSE": ("FTSE 100 (Reino Unido)", "Índice", []), "^SSMI": ("SMI (Suiza)", "Índice", []),
    "^GSPC": ("S&P 500 (EEUU)", "Índice", []), "^NDX": ("Nasdaq 100 (EEUU)", "Índice", []),
    "^IXIC": ("Nasdaq Composite (EEUU)", "Índice", []), "^DJI": ("Dow Jones (EEUU)", "Índice", []),
    "^RUT": ("Russell 2000 (pequeñas EEUU)", "Índice", []), "^GSPTSE": ("S&P/TSX (Canadá)", "Índice", []),
    "^BVSP": ("Bovespa (Brasil)", "Índice", []), "^N225": ("Nikkei 225 (Japón)", "Índice", []),
    "^HSI": ("Hang Seng (Hong Kong)", "Índice", []), "000001.SS": ("Shanghái Composite (China)", "Índice", []),
    "^KS11": ("KOSPI (Corea del Sur)", "Índice", []), "^NSEI": ("Nifty 50 (India)", "Índice", []),
    "^AXJO": ("ASX 200 (Australia)", "Índice", []),
}
INDICADORES_MACRO = {
    "^IRX": ("Letra del Tesoro EEUU 13 semanas (rentabilidad %)", "Tipos de interés", []),
    "^FVX": ("Bono EEUU 5 años (rentabilidad %)", "Tipos de interés", []),
    "^TNX": ("Bono EEUU 10 años (rentabilidad %)", "Tipos de interés", []),
    "^TYX": ("Bono EEUU 30 años (rentabilidad %)", "Tipos de interés", []),
    "^VIX": ("VIX (índice del miedo)", "Volatilidad", []),
    "DX-Y.NYB": ("Índice dólar (DXY)", "Divisas", []),
    "EURUSD=X": ("Euro / dólar (EUR/USD)", "Divisas", []),
}

CATALOGO = {
    "España (IBEX 35)": IBEX35, "España (Mercado Continuo)": CONTINUO, "Europa": EUROPA, "EEUU": EEUU,
    "Reino Unido, Suiza y Nórdicos": REINO_UNIDO_SUIZA, "Asia": ASIA, "Otros mercados": OTROS_MERCADOS,
    "Fondos indexados": FONDOS_INDEXADOS, "ETF y oro": {**ETFS, **MAS_ETFS}, "Criptomonedas": CRIPTOMONEDAS,
    "Divisas": DIVISAS, "Materias primas": MATERIAS_PRIMAS, "Índices": INDICES_TODOS,
    "Tipos de interés y macro": INDICADORES_MACRO,
}
TODOS_LOS_VALORES = {t: v for grupo in CATALOGO.values() for t, v in grupo.items()}
# Lo que no se puede comprar directamente (son referencias): índices y tipos/indicadores.
NO_INVERTIBLES = set(INDICES_TODOS) | set(INDICADORES_MACRO)


def nombre_de(ticker: str) -> str:
    if ticker in INDICES:
        return INDICES[ticker]["nombre"]
    if ticker in TERMOMETROS:
        return TERMOMETROS[ticker]["nombre"]
    if ticker in INDICES_MUNDIALES:
        return INDICES_MUNDIALES[ticker]
    if ticker in TODAS_LAS_ACCIONES:
        return TODAS_LAS_ACCIONES[ticker][0]
    if ticker in TODOS_LOS_VALORES:
        return TODOS_LOS_VALORES[ticker][0]
    from .activos import ACTIVOS, CRIPTO, ORO, es_cripto

    if ticker in ORO:
        return ORO[ticker]
    if ticker in ACTIVOS:
        return ACTIVOS[ticker]["nombre"]
    if es_cripto(ticker):
        return CRIPTO[ticker.split("-")[0].upper()]
    return ticker


def sector_de(ticker: str) -> str:
    return TODOS_LOS_VALORES.get(ticker, ("", "—", []))[1]


def grupo_de(ticker: str) -> str | None:
    """Grupo del catálogo (p. ej. 'Asia', 'Divisas')."""
    return next((g for g, d in CATALOGO.items() if ticker in d), None)


def es_invertible(ticker: str) -> bool:
    return ticker not in NO_INVERTIBLES and not ticker.startswith("^")


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
