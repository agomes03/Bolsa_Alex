"""Conclusión sencilla de cada noticia: dónde repercute, qué suele pasar y qué oportunidad o riesgo genera.

Reglas transparentes basadas en cómo suele reaccionar la bolsa a cada tipo de noticia (sin inteligencia
artificial, gratis). Si la noticia nombra una empresa, se añade lo que la app ve de ella hoy (veredicto, nota,
riesgo) y si la tienes en tu cartera.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .tickers import IBEX35, nombre_de, sector_de


@dataclass(frozen=True)
class Regla:
    patron: str
    tipo: str            # "oportunidad", "riesgo", "vigilar"
    efecto: str          # qué suele pasar
    oportunidad: str     # qué hacer / dónde está la ocasión
    bajan: tuple[str, ...] = ()          # sectores que suelen sufrir
    activos: str = ""                    # otros activos afectados (oro, petróleo, bonos...)
    de_empresa: bool = False             # solo si la noticia nombra una empresa
    suben: tuple[str, ...] = ()          # sectores que suelen ganar o aguantar mejor
    condicional: bool = False            # el efecto depende del dato (inflación, reunión del BCE...)


# En orden de prioridad: se usa la primera que encaja.
REGLAS = [
    Regla(r"profit warning|rebaja.{0,30}previsiones|recorta.{0,30}previsiones|cuts? (its )?(guidance|outlook|forecast)",
          "riesgo", "La empresa avisa de que ganará menos: suele caer con fuerza el mismo día y le cuesta semanas "
          "recuperarse.",
          "No la compres solo porque «ha bajado mucho»: espera a que deje de caer. Si la tienes, revisa tu stop-loss.",
          de_empresa=True),
    Regla(r"\bopa\b|oferta p[uú]blica de (adquisici|compra)|takeover|tender offer|fusi[oó]n|merger|adquisici[oó]n de|"
          r"acquire|acquisition",
          "vigilar", "La empresa que van a comprar suele subir hasta cerca del precio ofrecido; la compradora a veces "
          "baja porque paga mucho.",
          "Comprar después del anuncio deja poco margen y, si la operación fracasa, el precio cae. Si ya la tienes, "
          "valora vender en bolsa o acudir a la oferta.", de_empresa=True),
    Regla(r"ampliaci[oó]n de capital|share offering|equity raise|dilut",
          "riesgo", "Emite acciones nuevas: cada acción vale una parte menor de la empresa y el precio suele bajar.",
          "No hay prisa por comprar: suele haber precios más bajos durante la ampliación.", de_empresa=True),
    Regla(r"(presentar[aá]|publicar[aá]|dar[aá] a conocer|antes de|previa de|esta semana|ma[nñ]ana|will report|"
          r"ahead of|to report|preview).{0,40}(resultados|earnings|cuentas)|(resultados|earnings).{0,25}"
          r"(ma[nñ]ana|esta semana|next week|this week)",
          "vigilar", "El día de resultados la acción puede moverse con fuerza (un 5-10 % no es raro) hacia arriba o "
          "hacia abajo.",
          "Evita comprar justo antes. La ocasión suele venir después: si cae mucho por unos resultados solo algo "
          "peores de lo esperado y la empresa sigue sana, se puede entrar poco a poco.", de_empresa=True),
    Regla(r"resultados|beneficio|ganancias|facturaci[oó]n|ventas|trimestre|earnings|revenue|quarterly|profit",
          "vigilar", "Los resultados mueven la acción según sean mejores o peores de lo que el mercado esperaba "
          "(no según si son buenos o malos en sí).",
          "Si cae con fuerza y la empresa sigue sana, puede ser una oportunidad de entrar poco a poco tras unos días; "
          "si sube mucho, no la persigas el mismo día.", de_empresa=True),
    Regla(r"rebaja.{0,40}(recomendaci[oó]n|precio objetivo|rating|consejo)|recorta.{0,30}precio objetivo|downgrade",
          "riesgo", "Un analista empeora su opinión: suele presionar el precio unos días.",
          "Una rebaja sola no es motivo para vender si tu plan sigue en pie; vigila el stop-loss.", de_empresa=True),
    Regla(r"(eleva|mejora|sube).{0,40}(recomendaci[oó]n|precio objetivo|rating)|upgrade",
          "oportunidad", "Un analista mejora su opinión: suele dar un empujón de pocos días.",
          "No basta para comprar: mira primero su veredicto en 🔍 Analizar.", de_empresa=True),
    Regla(r"recompra de acciones|recompra|buyback|share repurchase",
          "oportunidad", "La empresa compra sus propias acciones: suele apoyar el precio.",
          "Es una señal de confianza de la empresa, pero no garantiza subidas.", de_empresa=True),
    Regla(r"dividendo|dividend",
          "vigilar", "El día del pago (fecha ex-dividendo) la acción baja más o menos lo que reparte.",
          "No es dinero gratis: comprar justo antes para cobrarlo no da ganancia (y el dividendo tributa).",
          de_empresa=True),
    # ------------------------------------------------------------------ macro
    Regla(r"bajada de tipos|recorte de tipos|baja (los )?tipos|recorta (los )?tipos|rate cuts?|cuts? rates|dovish|relajaci[oó]n monetaria|monetary easing",
          "oportunidad", "Tipos más bajos abaratan los préstamos: suelen subir la bolsa en general, sobre todo "
          "inmobiliarias, eléctricas y tecnológicas. Los bancos ganan algo menos.",
          "Buen viento para el fondo indexado y las empresas endeudadas; si tienes mucho en bancos, no es su mejor "
          "noticia.", ("Banca",), "bonos (suben de precio)", suben=("Inmobiliaria", "Eléctricas", "Tecnología")),
    Regla(r"subida de tipos|sube (los )?tipos|eleva (los )?tipos|rate hikes?|hikes? rates|hawkish|endurecimiento|tightening",
          "riesgo", "Tipos más altos frenan la economía: la bolsa suele bajar, sobre todo inmobiliarias, eléctricas y "
          "tecnológicas. Los bancos y aseguradoras suelen aguantar mejor.",
          "Los bancos se benefician; para comprar el resto, mejor poco a poco.",
          ("Inmobiliaria", "Eléctricas", "Tecnología"), "bonos (bajan de precio)", suben=("Banca", "Seguros")),
    Regla(r"inflaci[oó]n|\bipc\b|\bcpi\b|\bpce\b|inflation",
          "vigilar", "Si la inflación sale más alta de lo esperado, se teme que suban los tipos: las bolsas suelen "
          "bajar y los bancos aguantan mejor. Si sale más baja, al revés.",
          "Los días de dato de inflación hay más movimiento: evita operar justo en la publicación.",
          ("Tecnología", "Inmobiliaria", "Banca"), "bonos y euro/dólar", condicional=True),
    Regla(r"\bbce\b|banco central europeo|lagarde|\bfed\b|reserva federal|powell|\bfomc\b|\becb\b",
          "vigilar", "Lo que digan los bancos centrales mueve todas las bolsas y los bonos.",
          "No hagas cambios grandes justo antes de la reunión; después, el mercado suele calmarse.",
          ("Inmobiliaria", "Banca"), "bonos y euro/dólar", condicional=True),
    Regla(r"aranceles?|guerra comercial|proteccionismo|tariffs?|trade war",
          "riesgo", "Encarecen el comercio: suelen bajar las exportadoras (automóvil, lujo, materiales) y la bolsa en "
          "general.",
          "Las caídas por aranceles a veces se recuperan cuando hay acuerdos: si quieres aprovecharlas, entra poco a "
          "poco y solo en empresas con buen veredicto.", ("Automoción", "Lujo", "Materiales")),
    Regla(r"(petr[oó]leo|brent|crudo|\bopep\b|\bopec\b|crude|\boil\b).{0,40}(sube|dispara|alza|r[eé]cord|rise|surge|jump)|"
          r"(sube|dispara).{0,20}(petr[oó]leo|crudo)",
          "vigilar", "Petróleo más caro: ganan las petroleras (Repsol) y pierden aerolíneas (IAG) y transporte; "
          "también puede subir la inflación.",
          "Oportunidad para petroleras a corto plazo; riesgo para aerolíneas.", ("Transporte",),
          suben=("Petróleo",)),
    Regla(r"(petr[oó]leo|brent|crudo|\bopep\b|\bopec\b|crude|\boil\b).{0,40}(cae|baja|desploma|hunde|fall|drop|slump)|"
          r"(cae|baja|desploma).{0,20}(petr[oó]leo|crudo)",
          "vigilar", "Petróleo más barato: pierden las petroleras y ganan aerolíneas, transporte y consumo.",
          "Buen momento relativo para aerolíneas; malo para petroleras.", ("Petróleo",),
          suben=("Transporte",)),
    Regla(r"guerra|conflicto|ataque|invasi[oó]n|misil|\bwar\b|military|missile|geopol",
          "riesgo", "Más incertidumbre: suelen bajar las bolsas, las aerolíneas y el turismo; suben el petróleo, el oro "
          "y las empresas de defensa.",
          "No vendas por pánico: en la historia, las caídas por conflictos han sido casi siempre temporales.",
          ("Transporte", "Turismo"), "oro y petróleo (suelen subir)", suben=("Tecnología y Defensa", "Petróleo")),
    Regla(r"recesi[oó]n|recession|contracci[oó]n econ[oó]mica|\bpib\b.{0,20}(cae|baja|contrae)|\bgdp\b.{0,20}"
          r"(shrink|contract|fall)",
          "riesgo", "Si la economía se frena, sufren los bancos y las empresas cíclicas; aguantan mejor eléctricas, "
          "alimentación y salud.",
          "Las empresas defensivas y la renta fija protegen; no es momento de concentrarse en cíclicas.",
          ("Banca", "Automoción", "Construcción"), suben=("Eléctricas", "Salud")),
    Regla(r"desplome|hundimiento|p[aá]nico|crash|batacazo|sell-?off|plunge|rout|n[uú]meros rojos|se hunde",
          "oportunidad", "Caída fuerte del mercado: suele arrastrar a casi todo, también a empresas sanas.",
          "Para el largo plazo, las caídas fuertes han sido oportunidades: sigue con tu aportación al fondo indexado y, "
          "si compras acciones, hazlo poco a poco. No vendas por miedo."),
    Regla(r"r[eé]cord|m[aá]ximos hist[oó]ricos|m[aá]ximos anuales|all-time high|record high",
          "vigilar", "El mercado está en máximos: la tendencia acompaña, pero hay menos margen si llega una corrección.",
          "No hay prisa: si vas a invertir una cantidad grande, mejor en varias veces."),
    Regla(r"inteligencia artificial|\bia\b|\bai\b|chips?|semiconductor|nvidia",
          "vigilar", "La IA mueve sobre todo a las tecnológicas de EEUU, que pesan mucho en los fondos mundiales.",
          "Si tienes un fondo indexado mundial ya tienes estas empresas; no hace falta concentrarse más en ellas.",
          ("Tecnología",)),
    Regla(r"china|yuan|beijing|pek[ií]n",
          "vigilar", "China influye en las materias primas, el lujo y los fabricantes de coches europeos.",
          "Vigila a las empresas muy expuestas a China; para el resto, efecto limitado.", ("Materiales", "Lujo", "Automoción")),
]

ICONO = {"oportunidad": "🟢", "riesgo": "🔴", "vigilar": "🟡"}
TITULO = {"oportunidad": "Posible oportunidad", "riesgo": "Riesgo", "vigilar": "Vigilar"}


def _ejemplos(sector: str) -> str:
    nombres = [v[0] for v in IBEX35.values() if v[1] == sector][:3]
    return f"{sector.lower()} ({', '.join(nombres)})" if nombres else sector.lower()


def concluir(titulo: str, resumen: str = "", empresas: list[str] | None = None, sentimiento: int = 0,
             filas_informe: dict[str, dict] | None = None, mis_tickers: set[str] | None = None) -> dict | None:
    """{'tipo', 'icono', 'titulo', 'donde', 'efecto', 'oportunidad', 'te_afecta'} o None si no hay conclusión clara."""
    texto = f"{titulo} {resumen}".lower()
    empresas = empresas or []
    filas_informe = filas_informe or {}
    mis_tickers = mis_tickers or set()
    regla = next((r for r in REGLAS if (empresas or not r.de_empresa) and re.search(r.patron, texto)), None)
    if not regla:
        return None
    efecto = regla.efecto
    tipo = regla.tipo
    # Resultados ya publicados: el tono del titular orienta el efecto probable.
    if regla.de_empresa and "resultados" in regla.patron and "presentar" not in regla.patron:
        if sentimiento > 0:
            efecto = "El titular apunta a unos buenos resultados: suele subir si superan lo esperado. " + efecto
        elif sentimiento < 0:
            efecto = "El titular apunta a unos resultados flojos: suele bajar. " + efecto
            tipo = "oportunidad"   # la caída puede abrir una ocasión si la empresa sigue sana

    if empresas:
        donde = ", ".join(nombre_de(t) for t in empresas[:3])
        sectores = {sector_de(t) for t in empresas if sector_de(t) != "—"}
        if sectores:
            donde += f" y, en menor medida, su sector ({', '.join(s.lower() for s in sorted(sectores))})"
    elif regla.bajan or regla.suben:
        partes = []
        if regla.condicional:
            partes.append("📊 los más sensibles: " + "; ".join(_ejemplos(x) for x in regla.bajan + regla.suben))
        elif regla.bajan:
            partes.append("📉 suelen sufrir " + "; ".join(_ejemplos(x) for x in regla.bajan))
        if regla.suben and not regla.condicional:
            partes.append("📈 suelen ganar o aguantar mejor " + "; ".join(_ejemplos(x) for x in regla.suben))
        donde = "Bolsa en general. " + " · ".join(partes)
    else:
        donde = "Bolsa en general (índices y fondos indexados)"
    if regla.activos:
        donde += f". También: {regla.activos}"

    oportunidad = regla.oportunidad
    for t in empresas[:2]:
        f = filas_informe.get(t)
        if f:
            from .asesor import veredicto

            etiqueta = veredicto(f)[0]
            nota = f", nota {f['nota']}/100" if f.get("nota") is not None else ""
            riesgo = f", riesgo de caída {f['riesgo_nivel']}" if f.get("riesgo_nivel") else ""
            oportunidad += f" Hoy la app ve {nombre_de(t)} así: «{etiqueta}»{nota}{riesgo}."

    if empresas:
        mias = [t for t in sorted(mis_tickers) if t in empresas]
        te_afecta = ("Te afecta: tienes " + ", ".join(nombre_de(t) for t in mias) + ".") if mias else ""
    elif regla.condicional:
        sensibles = [nombre_de(t) for t in sorted(mis_tickers) if sector_de(t) in regla.bajan + regla.suben]
        te_afecta = ("Puede afectar a lo que tienes: " + ", ".join(sensibles) + " (según cómo salga el dato).") \
            if sensibles else ""
    else:
        contra = [nombre_de(t) for t in sorted(mis_tickers) if sector_de(t) in regla.bajan]
        favor = [nombre_de(t) for t in sorted(mis_tickers) if sector_de(t) in regla.suben]
        trozos = ([f"en contra para {', '.join(contra)}"] if contra else []) + \
                 ([f"a favor de {', '.join(favor)}"] if favor else [])
        te_afecta = ("Te afecta: " + "; ".join(trozos) + ".") if trozos else ""
    return {"tipo": tipo, "icono": ICONO[tipo], "titulo": TITULO[tipo], "donde": donde, "efecto": efecto,
            "oportunidad": oportunidad, "te_afecta": te_afecta}


def resumen_corto(c: dict) -> str:
    """Una línea para listas (página Hoy)."""
    return f"{c['icono']} {c['titulo']} · {c['donde'].split('. También')[0]}"


__all__ = ["concluir", "resumen_corto", "REGLAS"]
