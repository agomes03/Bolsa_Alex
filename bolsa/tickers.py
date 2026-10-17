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


# --------------------------------------------------------------------------- catálogo grande (octubre 2026)
# Más empresas y productos, todos comprobados con datos de Yahoo. Lo que no esté aquí se encuentra con el
# buscador (nombre, ticker o ISIN) en Analizar, la cartera virtual y la lista de seguimiento.
def _g(sector: str, pares: str) -> dict:
    """«TICKER=Nombre; TICKER=Nombre» -> {ticker: (nombre, sector, [palabras de noticias])}."""
    salida = {}
    for par in pares.split(";"):
        t, n = (x.strip() for x in par.split("=", 1))
        salida[t] = (n, sector, [n.split(" (")[0].lower()])
    return salida


MAS_CONTINUO = {
    **_g("Transporte", "TLGO.MC=Talgo; EDR.MC=eDreams ODIGEO; HBX.MC=HBX Group (Hotelbeds)"),
    **_g("Inmobiliaria", "HOME.MC=Neinor Homes; AEDAS.MC=Aedas Homes; MVC.MC=Metrovacesa; RLIA.MC=Realia; "
                         "ISUR.MC=Inmobiliaria del Sur; MTB.MC=Montebalito; NYE.MC=Nyesa; LIB.MC=Libertas 7"),
    **_g("Seguros", "LDA.MC=Línea Directa Aseguradora"),
    **_g("Financiero", "R4.MC=Renta 4 Banco; ALNT.MC=Alantra"),
    **_g("Salud", "ATRY.MC=Atrys Health; CBAV.MC=Clínica Baviera; RJF.MC=Reig Jofre; ORY.MC=Oryzon Genomics; "
                  "GRF-P.MC=Grifols (acciones B); PRM.MC=Prim"),
    **_g("Materiales", "MCM.MC=Miquel y Costas; CMO.MC=Cementos Molins; IBG.MC=Iberpapel; LGT.MC=Lingotes Especiales"),
    **_g("Tecnología", "DOM.MC=Global Dominion; IZER.MC=Izertis; AMP.MC=Amper; AI.MC=Airtificial; EZE.MC=Ezentis"),
    **_g("Energía", "ADX.MC=Audax Renovables; SOL.MC=Soltec; ENER.MC=Ecoener; BKY.MC=Berkeley Energia"),
    **_g("Industria", "MDF.MC=Duro Felguera; TRE.MC=Técnicas Reunidas; NEA.MC=Nicolás Correa; AZK.MC=Azkoyen; "
                      "ART.MC=Arteche"),
    **_g("Construcción", "OHLA.MC=OHLA; FCC.MC=FCC; GSJ.MC=Grupo San José"),
    **_g("Consumo", "NTH.MC=Naturhouse; RIO.MC=Bodegas Riojanas; PVA.MC=Pescanova; OLE.MC=Deoleo; "
                    "CCEP.MC=Coca-Cola Europacific Partners; ADZ.MC=Adolfo Domínguez; DIA.MC=DIA; "
                    "EAT.MC=AmRest; NXT.MC=Nextil; CIRSA.MC=Cirsa"),
    **_g("Medios", "SQRL.MC=Squirrel Media; VOC.MC=Vocento; PRS.MC=Prisa"),
    **_g("Servicios", "CASH.MC=Prosegur Cash"),
}

MAS_EEUU = {
    **_g("Banca", "WFC=Wells Fargo; MS=Morgan Stanley; C=Citigroup; SCHW=Charles Schwab"),
    **_g("Financiero", "BLK=BlackRock; AXP=American Express; SPGI=S&P Global; COIN=Coinbase; HOOD=Robinhood; "
                       "MSTR=Strategy (MicroStrategy)"),
    **_g("Consumo", "LOW=Lowe's; TGT=Target; SBUX=Starbucks; PM=Philip Morris; MO=Altria; MDLZ=Mondelez; "
                    "CL=Colgate-Palmolive; KHC=Kraft Heinz; F=Ford; GM=General Motors"),
    **_g("Turismo", "BKNG=Booking; ABNB=Airbnb"),
    **_g("Tecnología", "TXN=Texas Instruments; QCOM=Qualcomm; AMAT=Applied Materials; MU=Micron; LRCX=Lam Research; "
                       "KLAC=KLA; ADI=Analog Devices; MRVL=Marvell; ARM=Arm Holdings; INTU=Intuit; NOW=ServiceNow; "
                       "IBM=IBM; ACN=Accenture; CRWD=CrowdStrike; PANW=Palo Alto Networks; SNOW=Snowflake; "
                       "ANET=Arista Networks; DELL=Dell; SMCI=Super Micro Computer; APP=AppLovin"),
    **_g("Telecomunicaciones", "T=AT&T; VZ=Verizon; TMUS=T-Mobile US; CMCSA=Comcast; ASTS=AST SpaceMobile"),
    **_g("Salud", "ABT=Abbott; TMO=Thermo Fisher; DHR=Danaher; AMGN=Amgen; GILD=Gilead; BMY=Bristol-Myers Squibb; "
                  "CVS=CVS Health; MDT=Medtronic; ISRG=Intuitive Surgical; VRTX=Vertex; REGN=Regeneron; MRNA=Moderna"),
    **_g("Defensa", "LMT=Lockheed Martin; RTX=RTX (Raytheon); NOC=Northrop Grumman; GD=General Dynamics"),
    **_g("Industria", "GE=GE Aerospace; HON=Honeywell; UPS=UPS; FDX=FedEx; DE=John Deere; MMM=3M; UNP=Union Pacific; "
                      "LIN=Linde"),
    **_g("Eléctricas", "NEE=NextEra Energy; DUK=Duke Energy; SO=Southern Company"),
    **_g("Petróleo", "COP=ConocoPhillips"),
}

MAS_EUROPA = {
    **_g("Automoción", "RACE.MI=Ferrari; STLAM.MI=Stellantis; P911.DE=Porsche; RNO.PA=Renault; CON.DE=Continental; "
                       "ML.PA=Michelin"),
    **_g("Defensa", "RHM.DE=Rheinmetall; HO.PA=Thales; LDO.MI=Leonardo; HAG.DE=Hensoldt; R3NK.DE=Renk; "
                    "SAAB-B.ST=Saab; BA.L=BAE Systems; RR.L=Rolls-Royce"),
    **_g("Tecnología", "IFX.DE=Infineon; CAP.PA=Capgemini; DSY.PA=Dassault Systèmes; PRX.AS=Prosus; ADYEN.AS=Adyen; "
                       "ASM.AS=ASM International; ERIC-B.ST=Ericsson; PHIA.AS=Philips"),
    **_g("Banca", "DBK.DE=Deutsche Bank; CBK.DE=Commerzbank; GLE.PA=Société Générale; KBC.BR=KBC"),
    **_g("Seguros", "G.MI=Generali; HNR1.DE=Hannover Re"),
    **_g("Consumo", "BN.PA=Danone; RI.PA=Pernod Ricard; CA.PA=Carrefour; HEIA.AS=Heineken; AD.AS=Ahold Delhaize; "
                    "ZAL.DE=Zalando; PUM.DE=Puma; HEN3.DE=Henkel; JMT.LS=Jerónimo Martins"),
    **_g("Lujo", "KER.PA=Kering; MONC.MI=Moncler"),
    **_g("Salud", "UCB.BR=UCB; MRK.DE=Merck KGaA; FRE.DE=Fresenius"),
    **_g("Industria", "PRY.MI=Prysmian; VOLV-B.ST=Volvo; ATCO-A.ST=Atlas Copco; DSV.CO=DSV; MAERSK-B.CO=Maersk; "
                      "DHL.DE=DHL Group; SGO.PA=Saint-Gobain; BFSA.DE=Befesa"),
    **_g("Energía", "EQNR.OL=Equinor; VWS.CO=Vestas; ENR.DE=Siemens Energy; GALP.LS=Galp"),
    **_g("Eléctricas", "EOAN.DE=E.ON; RWE.DE=RWE; ENGI.PA=Engie; VIE.PA=Veolia; EDP.LS=EDP"),
    **_g("Telecomunicaciones", "ORA.PA=Orange"),
}

SOCIMIS_INMOBILIARIAS = {
    **_g("SOCIMI", "MRL.MC=Merlin Properties; COL.MC=Inmobiliaria Colonial"),
    **_g("Inmobiliaria Europa", "VNA.DE=Vonovia; URW.PA=Unibail-Rodamco-Westfield; SGRO.L=Segro"),
    **_g("REIT EEUU", "O=Realty Income; PLD=Prologis; AMT=American Tower; SPG=Simon Property; EQIX=Equinix"),
    **_g("ETF inmobiliario", "IPRP.AS=iShares European Property Yield (€); "
                             "IWDP.AS=iShares Developed Markets Property Yield"),
}

FONDOS_GESTION_ACTIVA = {
    **_g("Fondo de autor", "0P00019W2R.F=Cobas Internacional FI; 0P00019W2Q.F=Cobas Iberia FI; "
                           "0P0001572X.F=Magallanes European Equity M FI; 0P0001572U.F=Magallanes Iberian Equity M FI; "
                           "0P00016YQ5.F=azValor Internacional FI; 0P00016YQ4.F=azValor Iberia FI; "
                           "0P00000P2M.F=Bestinver Internacional FI; 0P00000P2N.F=Bestinver Bolsa FI; "
                           "0P0001DFE8.F=Horos Value Internacional FI; 0P00011MD7.F=True Value FI; "
                           "0P0001JGVI.F=True Value Small Caps A FI; 0P000125T9.F=Valentum FI; 0P0001HVBJ.F=Muza FI; "
                           "0P00000J48.F=Metavalor FI; 0P0001NMUD.F=MyInvestor Value A FI; "
                           "0P0001CTGR.F=Baelo Patrimonio FI; 0P00000TJ8.F=Cartesio X FI"),
    **_g("Fondo internacional", "0P0000RU81.L=Fundsmith Equity I Acc (£)"),
    **_g("Fondo mixto", "0P0001H7WN.F=Indexa RV Mixta Internacional 75 FI"),
    **_g("Fondo Bankinter", "0P00000PIG.F=Bankinter Índice IBEX R FI; "
                            "0P00000PI7.F=Bankinter Renta Fija Largo Plazo R FI"),
}

RENTA_FIJA = {
    **_g("Bonos España", "IS0P.DE=iShares Bonos del Estado español (distribución, €); "
                         "SPGA.MI=iShares Bonos del Estado español (acumulación, €)"),
    **_g("Monetario y Letras", "0P00000DNX.F=Renta 4 Fondtesoro Corto Plazo FI (Letras y deuda corta); "
                               "0P00000PI2.F=Bankinter Ahorro Activos Euro R FI (monetario); "
                               "0P00000CNF.F=Sabadell Fondtesoro Largo Plazo FI; "
                               "XEON.DE=Xtrackers EUR Overnight Rate (monetario, €); "
                               "ERNE.AS=iShares € Ultrashort Bond (muy corto plazo, €)"),
    **_g("Bonos zona euro", "EUNH.DE=iShares Core € Govt Bond (€); XGLE.DE=Xtrackers Eurozone Government Bond (€); "
                            "VGEA.DE=Vanguard Eurozone Government Bond (€); IBGS.AS=iShares € Govt Bond 1-3 años; "
                            "IBGM.AS=iShares € Govt Bond 7-10 años; "
                            "IBCI.AS=iShares € Inflation Linked Govt Bond (ligados a la inflación)"),
    **_g("Bonos de empresa", "IEAC.AS=iShares Core € Corp Bond (empresas, €); 0P00000M9H.F=Evli Short Corporate Bond B; "
                             "EUNA.DE=iShares Core Global Aggregate Bond (€)"),
}

ETF_TEMATICOS = {
    **_g("ETF sector", "QDVE.DE=iShares S&P 500 Tecnología; QDVG.DE=iShares S&P 500 Salud; "
                       "QDVF.DE=iShares S&P 500 Energía; QDVH.DE=iShares S&P 500 Financiero; "
                       "XDWT.DE=Xtrackers MSCI World Tecnología; XDWH.DE=Xtrackers MSCI World Salud; "
                       "EXV1.DE=iShares STOXX Europe 600 Bancos; EXH1.DE=iShares STOXX Europe 600 Petróleo y gas; "
                       "EXV6.DE=iShares STOXX Europe 600 Materias primas"),
    **_g("ETF temático", "VVSM.DE=VanEck Semiconductores; XAIX.DE=Xtrackers Inteligencia Artificial y Big Data; "
                         "DFEN.DE=VanEck Defensa; USPY.DE=L&G Ciberseguridad; 2B76.DE=iShares Automatización y Robótica; "
                         "IQQH.DE=iShares Energía Limpia; IQQQ.DE=iShares Agua"),
    **_g("ETF dividendos", "VHYL.AS=Vanguard FTSE All-World High Dividend Yield; "
                           "ZPRG.DE=SPDR S&P Global Dividend Aristocrats; ISPA.DE=iShares STOXX Global Select Dividend 100; "
                           "SPYD.DE=SPDR S&P US Dividend Aristocrats; TDIV.AS=VanEck Dividend Leaders"),
    **_g("ETF región y estilo", "SXRT.DE=iShares Core EURO STOXX 50 (€); MEUD.PA=Amundi STOXX Europe 600 (€); "
                                "CW8.PA=Amundi MSCI World (€); CSPX.AS=iShares Core S&P 500 (Ámsterdam); "
                                "IJPA.AS=iShares Core MSCI Japan; XCS6.DE=Xtrackers MSCI China; "
                                "IUSN.DE=iShares MSCI World Small Cap; ZPRV.DE=SPDR USA Small Cap Value; "
                                "ZPRX.DE=SPDR Europe Small Cap Value; IS3R.DE=iShares MSCI World Momentum"),
    **_g("Metales y cripto", "PHAG.AS=WisdomTree Plata física; BTCE.DE=Bitwise Bitcoin físico (ETC, €); "
                             "G2X.DE=VanEck Mineras de oro; URNU.DE=Global X Uranio"),
    **_g("ETF temático", "WTI2.DE=WisdomTree Inteligencia Artificial; CBUX.DE=iShares Infraestructuras globales"),
    **_g("ETF dividendos", "VGWE.DE=Vanguard FTSE All-World High Dividend (acumulación); "
                           "IQQA.DE=iShares Euro Dividend"),
    **_g("ETF región y estilo", "XDEQ.DE=Xtrackers MSCI World Calidad; XDEM.DE=Xtrackers MSCI World Momentum; "
                                "SXR0.DE=iShares MSCI World Mínima volatilidad; IWVE.AS=iShares MSCI World Value; "
                                "QDV5.DE=iShares MSCI India; IUSD.DE=iShares MSCI World Islamic"),
}

# Los ETF más usados para el núcleo de la cartera (además de los de arriba).
ETF_NUCLEO = {
    **_g("ETF Mundial", "SPYL.DE=SPDR S&P 500 (acumulación); VGVF.DE=Vanguard FTSE Developed World; "
                        "F50A.DE=Amundi Prime Global; V3AA.DE=Vanguard ESG Global All Cap"),
    **_g("ETF EEUU", "D5BM.DE=Xtrackers S&P 500 Swap; XD9U.DE=Xtrackers MSCI USA; EQQQ.DE=Invesco Nasdaq-100"),
    **_g("ETF Europa", "EUNK.DE=iShares Core MSCI Europe; SXRW.DE=iShares Core FTSE 100"),
    **_g("ETF España", "LYXIB.MC=Amundi IBEX 35"),
    **_g("ETF Emergentes", "VFEA.DE=Vanguard FTSE Emerging Markets; XMME.DE=Xtrackers MSCI Emerging Markets; "
                           "AMEM.DE=Amundi MSCI Emerging Markets"),
    **_g("Renta fija", "DBZB.DE=Xtrackers Global Government Bond (€ cubierto)"),
}

def _cargar_mundial() -> dict[str, dict]:
    """Catálogo generado con `scripts/generar_catalogo.py`: toda la bolsa española y los índices principales de
    cada país, S&P 500 entero por sectores."""
    import json
    from pathlib import Path

    ruta = Path(__file__).with_name("catalogo_mundial.json")
    try:
        bruto = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {g: {t: (v[0], v[1], []) for t, v in vs.items()} for g, vs in bruto.items()}


MUNDIAL = _cargar_mundial()
# Los nombres escritos a mano (más cortos y conocidos) mandan sobre los generados.
_A_MANO = {**IBEX35, **CONTINUO, **MAS_CONTINUO, **EUROPA, **MAS_EUROPA, **EEUU, **MAS_EEUU, **REINO_UNIDO_SUIZA,
           **ASIA, **OTROS_MERCADOS}


def _grupo(*fuentes: dict) -> dict:
    salida = {}
    for f in fuentes:
        for t, v in f.items():
            salida.setdefault(t, _A_MANO.get(t, v))
    return salida


# Bolsa de cada sufijo, para colocar lo escrito a mano que el catálogo generado no tenga.
_SUFIJO_GRUPO = {".MC": "España (Mercado Continuo)", ".DE": "Alemania", ".PA": "Francia", ".MI": "Italia",
                 ".AS": "Países Bajos y Bélgica", ".BR": "Países Bajos y Bélgica",
                 ".LS": "Portugal, Irlanda, Austria y Finlandia", ".IR": "Portugal, Irlanda, Austria y Finlandia",
                 ".VI": "Portugal, Irlanda, Austria y Finlandia", ".HE": "Portugal, Irlanda, Austria y Finlandia",
                 ".L": "Reino Unido", ".SW": "Suiza", ".ST": "Suecia", ".CO": "Dinamarca y Noruega",
                 ".OL": "Dinamarca y Noruega", ".T": "Japón", ".HK": "China y Hong Kong",
                 ".KS": "Corea del Sur y Taiwán", ".TW": "Corea del Sur y Taiwán", ".NS": "India", ".AX": "Australia",
                 ".TO": "Canadá", ".SA": "Brasil y México", ".MX": "Brasil y México"}

ACCIONES_ESPANA = {"España (IBEX 35)": IBEX35,
                   "España (Mercado Continuo)": _grupo(CONTINUO, MAS_CONTINUO,
                                                       MUNDIAL.get("España (Mercado Continuo)", {})),
                   "España (BME Growth y SOCIMIs pequeñas)": MUNDIAL.get("España (BME Growth y SOCIMIs pequeñas)", {}),
                   "Latibex (Latinoamérica en euros)": MUNDIAL.get("Latibex (Latinoamérica en euros)", {})}
ACCIONES_EUROPA = {"Europa (las 50 más grandes)": EUROPA,
                   **{g: _grupo(MUNDIAL.get(g, {})) for g in (
                       "Alemania", "Francia", "Italia", "Países Bajos y Bélgica",
                       "Portugal, Irlanda, Austria y Finlandia", "Reino Unido", "Suiza", "Suecia",
                       "Dinamarca y Noruega")}}
ACCIONES_EEUU = {"EEUU (las 40 más grandes)": EEUU,
                 **{g: _grupo(v) for g, v in MUNDIAL.items() if g.startswith("EEUU ·")}}
ACCIONES_MUNDO = {g: _grupo(MUNDIAL.get(g, {})) for g in (
    "Japón", "China y Hong Kong", "Corea del Sur y Taiwán", "India", "Australia", "Canadá", "Brasil y México")}

# Lo escrito a mano que no esté en el catálogo generado se coloca en el grupo de su bolsa (no se pierde nada).
_TODOS_GRUPOS_ACCIONES = {**ACCIONES_ESPANA, **ACCIONES_EUROPA, **ACCIONES_EEUU, **ACCIONES_MUNDO}
_ya = {t for d in _TODOS_GRUPOS_ACCIONES.values() for t in d}
for _t, _v in {**MAS_EUROPA, **MAS_EEUU, **REINO_UNIDO_SUIZA, **ASIA, **OTROS_MERCADOS, **MAS_CONTINUO}.items():
    if _t not in _ya:
        _destino = next((g for suf, g in _SUFIJO_GRUPO.items() if _t.endswith(suf)), "EEUU · Otras grandes (Nasdaq, ADR...)")
        _TODOS_GRUPOS_ACCIONES.setdefault(_destino, {})[_t] = _v
        _ya.add(_t)
for _g, _d in _TODOS_GRUPOS_ACCIONES.items():
    for _bloque in (ACCIONES_ESPANA, ACCIONES_EUROPA, ACCIONES_EEUU, ACCIONES_MUNDO):
        if _g in _bloque:
            _bloque[_g] = _d

# Primer nivel del selector (tipo de activo) -> grupos del segundo nivel.
CATEGORIAS = {
    "Acciones de España": list(ACCIONES_ESPANA), "Acciones de Europa": list(ACCIONES_EUROPA),
    "Acciones de EEUU": list(ACCIONES_EEUU), "Acciones del resto del mundo": list(ACCIONES_MUNDO),
    "SOCIMIs e inmobiliarias": ["SOCIMIs e inmobiliarias"], "Fondos indexados": ["Fondos indexados"],
    "Fondos de gestión activa": ["Fondos de gestión activa"], "ETF y oro": ["ETF y oro"],
    "ETF temáticos y sectoriales": ["ETF temáticos y sectoriales"], "Renta fija": ["Renta fija"],
    "Criptomonedas": ["Criptomonedas"], "Divisas": ["Divisas"], "Materias primas": ["Materias primas"],
    "Índices": ["Índices"], "Tipos de interés y macro": ["Tipos de interés y macro"],
}

CATALOGO = {
    **ACCIONES_ESPANA, **ACCIONES_EUROPA, **ACCIONES_EEUU, **ACCIONES_MUNDO,
    "SOCIMIs e inmobiliarias": SOCIMIS_INMOBILIARIAS,
    "Fondos indexados": FONDOS_INDEXADOS, "Fondos de gestión activa": FONDOS_GESTION_ACTIVA,
    "ETF y oro": {**ETFS, **MAS_ETFS, **ETF_NUCLEO}, "ETF temáticos y sectoriales": ETF_TEMATICOS,
    "Renta fija": RENTA_FIJA, "Criptomonedas": CRIPTOMONEDAS, "Divisas": DIVISAS, "Materias primas": MATERIAS_PRIMAS, "Índices": INDICES_TODOS,
    "Tipos de interés y macro": INDICADORES_MACRO,
}
TODOS_LOS_VALORES = {t: v for grupo in CATALOGO.values() for t, v in grupo.items()}
# Lo que no se puede comprar directamente (son referencias): índices y tipos/indicadores.
NO_INVERTIBLES = set(INDICES_TODOS) | set(INDICADORES_MACRO)
# Nombres de lo que se ha encontrado con el buscador (fuera del catálogo): ticker -> nombre.
NOMBRES_BUSCADOS: dict[str, str] = {}


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
    return NOMBRES_BUSCADOS.get(ticker, ticker)


def sector_de(ticker: str) -> str:
    return TODOS_LOS_VALORES.get(ticker, ("", "—", []))[1]


_GRUPO_DE = {}
for _g, _d in CATALOGO.items():
    for _t in _d:
        _GRUPO_DE.setdefault(_t, _g)
_CATEGORIA_DE = {g: c for c, gs in CATEGORIAS.items() for g in gs}


def grupo_de(ticker: str) -> str | None:
    """Grupo del catálogo (p. ej. 'Japón', 'Divisas')."""
    return _GRUPO_DE.get(ticker)


def categoria_de(grupo: str | None) -> str | None:
    """Primer nivel del selector para un grupo (p. ej. 'Japón' -> 'Acciones del resto del mundo')."""
    return _CATEGORIA_DE.get(grupo)


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
