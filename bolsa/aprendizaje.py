"""Contenido de 🎓 Aprende: diccionario bursátil, guías paso a paso y preguntas para ponerte a prueba.

Todo en lenguaje sencillo, con ejemplos en euros y, cuando aplica, cómo se hace en Bankinter. Las tarifas e
impuestos son los vigentes en octubre de 2026 (compruébalos antes de operar).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

CATEGORIAS = ["Órdenes", "Mercado", "Costes e impuestos", "Empresa y dividendos", "Análisis técnico",
              "Análisis fundamental", "Riesgo y cartera", "Fondos y otros productos", "Economía",
              "Productos peligrosos", "En esta app"]


@dataclass(frozen=True)
class Termino:
    termino: str
    categoria: str
    definicion: str
    ejemplo: str = ""
    ver: tuple[str, ...] = ()


GLOSARIO: list[Termino] = [
    # ------------------------------------------------------------------ Órdenes
    Termino("Orden limitada", "Órdenes",
            "Compras o vendes solo a un precio igual o mejor que el que pones. Si el mercado no llega a ese precio, "
            "la orden espera (hasta que caduque). Es la orden recomendada para principiantes.",
            "Pones comprar Santander limitada a 12,00 €: si cotiza a 12,05 € no se compra; si baja a 11,98 € "
            "compras a 11,98 €.", ("Orden a mercado", "Validez de la orden")),
    Termino("Orden a mercado", "Órdenes",
            "Compra o vende ya, al precio que haya en ese momento, cruzando con todas las órdenes contrarias que "
            "haga falta. Es rápida pero no controlas el precio: en valores poco negociados o en momentos de nervios "
            "puede salir bastante peor de lo esperado.", "", ("Orden limitada", "Horquilla")),
    Termino("Orden por lo mejor", "Órdenes",
            "Se ejecuta al mejor precio contrario disponible en ese momento; si no se completa, el resto queda como "
            "orden limitada a ese mismo precio. Más segura que «a mercado», menos que «limitada».", "",
            ("Orden limitada",)),
    Termino("Stop-loss", "Órdenes",
            "Precio al que decides vender si la acción cae, para que una pérdida pequeña no se convierta en una "
            "grande. Se pone con una orden stop. Una vez puesto, se sube si la acción sube, pero nunca se baja.",
            "Compras a 20 € y pones el stop-loss en 18 €: si cae hasta 18 € se vende y pierdes un 10 %, no un 40 %.",
            ("Orden stop", "Stop dinámica", "Riesgo por operación")),
    Termino("Orden stop", "Órdenes",
            "Orden que se queda «dormida» hasta que el precio toca el nivel de activación; entonces se lanza al "
            "mercado. En Bankinter la de venta se pone con la condición «menor o igual que» y un precio límite "
            "obligatorio.", "Activación 18,00 € y límite 17,64 € (un 2 % por debajo) para que se ejecute aunque caiga "
            "deprisa.", ("Stop-loss", "Stop limitada")),
    Termino("Stop limitada", "Órdenes",
            "Orden stop que, al activarse, se convierte en una orden limitada (no vende por debajo del límite). Es la "
            "que exige Bankinter. Si la caída es muy brusca y salta por debajo del límite, puede quedarse sin "
            "ejecutar: por eso conviene dejar un margen (la app propone un 2 %).", "", ("Orden stop",)),
    Termino("Stop relacionadas", "Órdenes",
            "En Bankinter, dos órdenes de venta enlazadas: una de protección (stop-loss) y otra de objetivo "
            "(vender con beneficio). Cuando se ejecuta una, Bankinter cancela la otra. En otros brókers se llama OCO.",
            "Compraste a 20 €: stop a 18 € y objetivo a 24 €. Si llega antes a 24 €, vendes con ganancia y el stop "
            "desaparece.", ("Stop-loss", "Objetivo de precio")),
    Termino("Stop dinámica", "Órdenes",
            "Stop que sube solo cuando la acción sube, manteniendo la distancia que elijas, y que nunca baja. En "
            "inglés, «trailing stop». Útil para dejar correr las ganancias sin vigilar cada día.",
            "Stop dinámica al 8 %: la acción sube de 20 € a 25 € y el stop pasa de 18,40 € a 23 €.", ("Stop-loss",)),
    Termino("Objetivo de precio", "Órdenes",
            "Precio al que piensas vender con beneficio. Ponerlo de antemano evita la avaricia. La app lo sitúa al "
            "doble de distancia que el stop-loss (ganar 2 por cada 1 que arriesgas).", "",
            ("Ratio beneficio/riesgo", "Stop relacionadas")),
    Termino("Validez de la orden", "Órdenes",
            "Hasta cuándo sigue viva una orden que no se ha ejecutado: solo hoy o hasta una fecha. Pasada la fecha, "
            "se cancela sola. Revisa las órdenes caducadas: un stop-loss caducado ya no te protege.", "",
            ("Orden limitada",)),
    Termino("Ejecución parcial", "Órdenes",
            "Cuando solo se compra o vende una parte de las acciones porque no había bastantes al otro lado a tu "
            "precio. El resto sigue pendiente. Cada parte ejecutada en días distintos puede cobrar comisión aparte.",
            "", ()),
    Termino("Comprar / Vender (largo)", "Órdenes",
            "Estar «largo» es tener acciones: ganas si suben. Es lo normal para un inversor particular.", "",
            ("Venta en corto",)),
    # ------------------------------------------------------------------ Mercado
    Termino("Acción", "Mercado",
            "Una parte pequeña de una empresa. Si la empresa gana dinero y crece, la acción suele valer más y puede "
            "pagar dividendos; si le va mal, puede valer mucho menos (incluso cero).", "", ("Dividendo",)),
    Termino("Cotización", "Mercado", "Precio al que se ha hecho la última compraventa de una acción.", "", ()),
    Termino("Índice bursátil", "Mercado",
            "Número que resume cómo van varias empresas a la vez. Sirve de termómetro del mercado y de referencia "
            "para los fondos indexados.", "", ("IBEX 35", "S&P 500", "MSCI World")),
    Termino("IBEX 35", "Mercado",
            "Índice de las 35 empresas españolas más negociadas. Se revisa en junio y diciembre. Pesan mucho los "
            "bancos, las eléctricas e Inditex.", "", ("Índice bursátil", "Mercado Continuo")),
    Termino("Mercado Continuo", "Mercado",
            "Sistema electrónico donde cotizan las acciones españolas (unas 130), incluidas las del IBEX 35. En "
            "Bankinter aparece como «CONTINUO».", "", ("IBEX 35", "Horario de la bolsa")),
    Termino("S&P 500", "Mercado",
            "Índice de las 500 mayores empresas de EEUU. Es la referencia de la bolsa mundial.", "", ("Nasdaq",)),
    Termino("Nasdaq", "Mercado",
            "Bolsa de EEUU donde cotizan muchas tecnológicas. El «Nasdaq 100» son sus 100 mayores empresas no "
            "financieras.", "", ("S&P 500",)),
    Termino("Euro Stoxx 50", "Mercado", "Índice de 50 grandes empresas de la zona euro.", "", ()),
    Termino("MSCI World", "Mercado",
            "Índice de unas 1.400 grandes y medianas empresas de 23 países desarrollados. Es lo que copian muchos "
            "fondos indexados mundiales.", "", ("Fondo indexado",)),
    Termino("Horario de la bolsa", "Mercado",
            "Bolsa española: subasta de apertura de 8:30 a 9:00, mercado abierto de 9:00 a 17:30 y subasta de cierre "
            "de 17:30 a 17:35. Wall Street: de 15:30 a 22:00 hora peninsular (una hora antes unas semanas de marzo y "
            "de octubre-noviembre, por el cambio de hora).", "", ("Subasta",)),
    Termino("Subasta", "Mercado",
            "Periodo en el que se acumulan órdenes sin ejecutarse y al final se cruzan todas a un único precio. Hay "
            "subasta de apertura, de cierre y de volatilidad (5 minutos cuando el precio se mueve demasiado de golpe).",
            "", ("Horario de la bolsa",)),
    Termino("Horquilla", "Mercado",
            "Diferencia entre el mejor precio al que alguien compra y el mejor al que alguien vende. En empresas "
            "grandes es de céntimos; en pequeñas puede ser grande, y comprar «a mercado» te cuesta esa diferencia.",
            "Compra 10,00 € / venta 10,04 €: la horquilla es de 4 céntimos (0,4 %).", ("Liquidez", "Orden limitada")),
    Termino("Libro de órdenes", "Mercado",
            "Lista de órdenes pendientes de compra y de venta a cada precio. En Bankinter lo ves como «posiciones» o "
            "profundidad de mercado.", "", ("Horquilla",)),
    Termino("Volumen", "Mercado",
            "Cuántas acciones se han negociado. Un movimiento fuerte con mucho volumen es más significativo que con "
            "poco.", "", ("Liquidez",)),
    Termino("Liquidez", "Mercado",
            "Facilidad para comprar o vender sin mover el precio. Las acciones del IBEX son muy líquidas; muchas "
            "pequeñas no.", "", ("Horquilla", "Volumen")),
    Termino("Capitalización", "Mercado",
            "Lo que vale en bolsa toda la empresa: precio por número de acciones.",
            "1.000 millones de acciones × 12 € = 12.000 millones de euros.", ("Blue chip", "Small caps")),
    Termino("Blue chip", "Mercado", "Empresa muy grande, conocida y estable (Santander, Iberdrola, Inditex...).", "",
            ("Capitalización",)),
    Termino("Small caps", "Mercado",
            "Empresas pequeñas en bolsa. Pueden crecer más, pero se mueven más y son menos líquidas.", "",
            ("Capitalización", "Liquidez")),
    Termino("Mercado alcista", "Mercado",
            "Periodo largo en el que la bolsa sube. Suele durar varios años.", "", ("Mercado bajista",)),
    Termino("Mercado bajista", "Mercado",
            "Caída de un 20 % o más desde máximos. Suelen durar meses; en la historia, la bolsa mundial siempre "
            "acabó recuperándose, aunque a veces tardó años.", "", ("Corrección", "Caída máxima")),
    Termino("Corrección", "Mercado",
            "Caída de entre un 10 % y un 20 % desde máximos. Ocurre de media casi una vez al año y es normal.", "",
            ("Mercado bajista",)),
    Termino("Volatilidad", "Riesgo y cartera",
            "Cuánto se mueve el precio. Se suele medir en % anual: una acción con volatilidad del 30 % se mueve mucho "
            "más que una del 15 %.", "", ("Riesgo", "Baja volatilidad", "VIX")),
    Termino("OPA", "Empresa y dividendos",
            "Oferta Pública de Adquisición: alguien ofrece comprar las acciones de una empresa a un precio, "
            "normalmente por encima del de bolsa. Puedes aceptarla o no.", "", ("Exclusión de bolsa",)),
    Termino("Exclusión de bolsa", "Empresa y dividendos",
            "La empresa deja de cotizar (suele ir tras una OPA). Si no vendes, tus acciones serán muy difíciles de "
            "vender.", "", ("OPA",)),
    # ------------------------------------------------------------------ Costes e impuestos
    Termino("Comisión", "Costes e impuestos",
            "Lo que cobra el bróker por cada compra o venta. En Bankinter: acciones españolas 3,95 € hasta 2.000 € y "
            "8 € hasta 60.000 € (0 € con Bróker Cero); extranjeras 20 € por operación.",
            "Comprar 1.500 € de Inditex: 3,95 €. Comprar 1.500 € de Apple: 20 € + un 1 % de cambio de divisa (15 €).",
            ("Canon de bolsa", "Cambio de divisa", "Custodia")),
    Termino("Canon de bolsa", "Costes e impuestos",
            "Pequeño cargo de la propia bolsa (BME) en cada operación española, aparte de la comisión del bróker. "
            "Ronda 1 € en importes normales.", "", ("Comisión",)),
    Termino("Tasa Tobin", "Costes e impuestos",
            "Impuesto sobre transacciones financieras al COMPRAR acciones de empresas grandes (más de 1.000 millones "
            "de capitalización): 0,2 % en España, 0,4 % en Francia y 0,1 % en Italia. Al vender no se paga.",
            "Comprar 5.000 € de Iberdrola: 10 € de tasa Tobin.", ("Comisión",)),
    Termino("Cambio de divisa", "Costes e impuestos",
            "Al comprar acciones en dólares u otra moneda, el banco cambia tus euros con un margen (en Bankinter, en "
            "torno al 1 % en cada sentido). Además, tu resultado depende de cómo se mueva esa moneda frente al euro.",
            "", ("Comisión",)),
    Termino("Custodia", "Costes e impuestos",
            "Comisión por guardar tus valores. En Bankinter, las acciones españolas no la pagan; las extranjeras, un "
            "0,05 % al trimestre con un mínimo de 6 € por valor (24 € al año).", "", ("Comisión",)),
    Termino("Ganancia patrimonial", "Costes e impuestos",
            "Lo que ganas (o pierdes) al vender: precio de venta menos precio de compra, restando comisiones. Tributa "
            "en la base del ahorro del IRPF solo cuando vendes.",
            "Compras por 5.000 € y vendes por 6.000 €: ganancia de 1.000 €, unos 190 € de IRPF.",
            ("Base del ahorro", "Compensación de pérdidas", "Regla de los 2 meses")),
    Termino("Base del ahorro", "Costes e impuestos",
            "Parte del IRPF donde tributan ganancias, dividendos e intereses: 19 % hasta 6.000 €, 21 % hasta 50.000 €, "
            "23 % hasta 200.000 €, 27 % hasta 300.000 € y 30 % a partir de ahí.", "", ("Ganancia patrimonial",)),
    Termino("Compensación de pérdidas", "Costes e impuestos",
            "Las pérdidas de un año se restan de las ganancias del mismo año. Si sobran, se pueden restar hasta un 25 % "
            "de dividendos e intereses y el resto, de las ganancias de los 4 años siguientes.",
            "Ganas 2.000 € con Indra y pierdes 500 € con Inditex: tributas por 1.500 €.", ("Regla de los 2 meses",)),
    Termino("Regla de los 2 meses", "Costes e impuestos",
            "Si vendes acciones con pérdidas y compras las mismas acciones en los 2 meses anteriores o posteriores, "
            "Hacienda no te deja usar esa pérdida hasta que vendas las recompradas.", "",
            ("Compensación de pérdidas",)),
    Termino("Retención", "Costes e impuestos",
            "Parte de un dividendo que se queda Hacienda por adelantado: el 19 % en España. Luego se ajusta en la "
            "declaración de la renta.", "", ("Dividendo", "Doble imposición")),
    Termino("Doble imposición", "Costes e impuestos",
            "Los dividendos extranjeros pagan impuesto en su país y en España. Puedes recuperar en la renta la parte "
            "extranjera hasta el límite español. Con acciones de EEUU, firmar el formulario W-8BEN (Bankinter lo "
            "gestiona) deja la retención de EEUU en el 15 %.", "", ("Retención",)),
    Termino("Informe fiscal", "Costes e impuestos",
            "Documento que Bankinter te envía cada año con tus ventas, ganancias, pérdidas y dividendos para hacer la "
            "declaración de la renta. Revísalo con los datos fiscales de Hacienda.", "", ("Ganancia patrimonial",)),
    # ------------------------------------------------------------------ Empresa y dividendos
    Termino("Dividendo", "Empresa y dividendos",
            "Parte del beneficio que la empresa reparte entre sus accionistas, normalmente en efectivo. No es dinero "
            "«gratis»: el día que se paga, la acción baja más o menos lo mismo.",
            "Una acción de 20 € paga 0,50 €: cobras 0,50 € (menos un 19 % de retención) y la acción abre a ~19,50 €.",
            ("Fecha ex-dividendo", "Rentabilidad por dividendo", "Retención")),
    Termino("Fecha ex-dividendo", "Empresa y dividendos",
            "Primer día en que la acción cotiza sin derecho al próximo dividendo. Para cobrarlo, debes tener las "
            "acciones al cierre del día anterior.", "", ("Dividendo",)),
    Termino("Rentabilidad por dividendo", "Empresa y dividendos",
            "Dividendos de un año divididos por el precio de la acción.", "0,60 € al año / 15 € = 4 %.",
            ("Dividendo",)),
    Termino("Dividendo flexible (scrip)", "Empresa y dividendos",
            "En lugar de dinero, la empresa te da derechos que puedes cambiar por acciones nuevas, vender en bolsa o "
            "vender a la propia empresa a un precio fijo. Cada opción tributa distinto.", "",
            ("Derechos de suscripción",)),
    Termino("Ampliación de capital", "Empresa y dividendos",
            "La empresa emite acciones nuevas para conseguir dinero. Si no acudes, tu parte de la empresa se reduce. "
            "Suele hacer bajar la cotización.", "", ("Derechos de suscripción",)),
    Termino("Derechos de suscripción", "Empresa y dividendos",
            "En una ampliación, te dan preferencia para comprar las acciones nuevas. Si no los quieres, puedes "
            "venderlos (su venta tributa como ganancia).", "", ("Ampliación de capital",)),
    Termino("Split", "Empresa y dividendos",
            "La empresa divide cada acción en varias más baratas. No cambia lo que vale tu inversión.",
            "Split 1×4: tus 10 acciones de 400 € pasan a ser 40 de 100 €.", ("Contrasplit",)),
    Termino("Contrasplit", "Empresa y dividendos",
            "Al revés que el split: junta varias acciones en una. Suele hacerse en empresas cuya acción vale muy poco.",
            "", ("Split",)),
    Termino("Resultados", "Empresa y dividendos",
            "Cuentas que las empresas publican cada trimestre (o semestre). Ese día el precio puede moverse mucho en "
            "cualquier dirección. La app te avisa cuando se acercan.", "", ("BPA",)),
    # ------------------------------------------------------------------ Análisis fundamental
    Termino("BPA", "Análisis fundamental",
            "Beneficio por acción: beneficio de la empresa dividido por el número de acciones.", "", ("PER",)),
    Termino("PER", "Análisis fundamental",
            "Precio de la acción dividido por su beneficio por acción: cuántos años de beneficios pagas. Un PER alto "
            "indica que el mercado espera mucho crecimiento (o que está cara); uno bajo, lo contrario o que hay "
            "problemas. Compáralo con empresas del mismo sector.", "Precio 20 €, BPA 2 €: PER 10.",
            ("BPA", "Precio / valor contable")),
    Termino("Precio / valor contable", "Análisis fundamental",
            "Precio de la acción dividido por lo que vale la empresa en sus libros (activos menos deudas) por acción. "
            "Muy usado con bancos y aseguradoras.", "", ("PER",)),
    Termino("ROE", "Análisis fundamental",
            "Rentabilidad sobre fondos propios: cuánto beneficio genera la empresa con el dinero de sus accionistas.",
            "", ()),
    Termino("Deuda neta / EBITDA", "Análisis fundamental",
            "Cuántos años tardaría la empresa en pagar su deuda con su beneficio de explotación. Por encima de 3 se "
            "suele considerar alta (depende del sector).", "", ()),
    Termino("Precio objetivo de los analistas", "Análisis fundamental",
            "Precio al que los analistas creen que llegará la acción en 12 meses. Es orientativo: se equivocan a "
            "menudo y suelen ser optimistas.", "", ()),
    Termino("Valor (value) y crecimiento (growth)", "Análisis fundamental",
            "«Value»: empresas baratas respecto a sus beneficios. «Growth»: empresas que crecen deprisa y suelen "
            "estar caras. Cada estilo tiene épocas buenas y malas.", "", ("PER",)),
    Termino("Defensivo y cíclico", "Análisis fundamental",
            "Defensivas: venden igual en las crisis (eléctricas, alimentación, salud). Cíclicas: dependen de la "
            "economía (bancos, construcción, automóvil, materias primas).", "", ("Sector",)),
    Termino("Sector", "Análisis fundamental",
            "Grupo de empresas del mismo negocio (banca, eléctricas, consumo...). Las de un mismo sector suelen moverse "
            "juntas.", "", ("Diversificación",)),
    # ------------------------------------------------------------------ Análisis técnico
    Termino("Tendencia", "Análisis técnico",
            "Dirección general del precio en semanas o meses: alcista, bajista o lateral. La app la mide con las "
            "medias móviles.", "", ("Media móvil",)),
    Termino("Media móvil", "Análisis técnico",
            "Media del precio de los últimos N días, que suaviza el ruido diario. Si el precio está por encima de su "
            "media, la tendencia es alcista.", "", ("Media de 200 sesiones", "Cruce dorado")),
    Termino("Media de 200 sesiones", "Análisis técnico",
            "Precio medio del último año de bolsa (~200 días). La regla de protección de la app sale de un índice "
            "cuando cae un 2 % por debajo de ella.", "", ("Regla de protección",)),
    Termino("Cruce dorado", "Análisis técnico",
            "Cuando la media de 50 sesiones cruza por encima de la de 200 (señal alcista). El contrario se llama "
            "«cruce de la muerte».", "", ("Media móvil",)),
    Termino("Soporte", "Análisis técnico",
            "Nivel de precio donde antes dejó de caer (aparecieron compradores). Si lo rompe, suele caer más.", "",
            ("Resistencia",)),
    Termino("Resistencia", "Análisis técnico",
            "Nivel de precio donde antes dejó de subir. Si lo supera con fuerza, suele seguir subiendo.", "",
            ("Soporte",)),
    Termino("RSI", "Análisis técnico",
            "Indicador de 0 a 100 que mide la fuerza de las subidas y bajadas recientes. Más de 70: ha subido muy "
            "deprisa (sobrecompra); menos de 30: ha caído muy deprisa (sobreventa).", "", ()),
    Termino("MACD", "Análisis técnico",
            "Indicador que compara dos medias móviles para detectar cambios de tendencia.", "", ("Media móvil",)),
    Termino("ATR", "Análisis técnico",
            "Lo que se mueve una acción en un día normal (rango medio verdadero). La app pone el stop-loss a 2 veces "
            "el ATR para que el ruido diario no lo active.", "", ("Stop-loss",)),
    Termino("Velas japonesas", "Análisis técnico",
            "Forma de dibujar el precio de cada día: el cuerpo va de la apertura al cierre (verde si sube, rojo si "
            "baja) y las mechas marcan el máximo y el mínimo.", "", ()),
    Termino("Momentum", "Análisis técnico",
            "Las acciones que más han subido en el último año tienden a seguir haciéndolo algo mejor unos meses. Es "
            "uno de los patrones más estudiados; la cartera Dinámica de la app se basa en él.", "",
            ("Cartera modelo",)),
    # ------------------------------------------------------------------ Riesgo y cartera
    Termino("Riesgo", "Riesgo y cartera",
            "Posibilidad de perder dinero o de que el resultado sea muy distinto del esperado. A más rentabilidad "
            "esperada, más riesgo: no existe lo uno sin lo otro.", "", ("Volatilidad", "Diversificación")),
    Termino("Diversificación", "Riesgo y cartera",
            "Repartir el dinero entre muchas empresas, sectores y países para que un problema en una no te hunda. Es "
            "lo único que reduce el riesgo sin reducir la rentabilidad esperada.",
            "Con 3 empresas, si una cae un 50 %, pierdes ~17 %. Con un fondo de 1.400 empresas, casi no lo notas.",
            ("Concentración", "Fondo indexado")),
    Termino("Concentración", "Riesgo y cartera",
            "Tener mucho dinero en pocas empresas o en un solo sector o país. Lo prudente: ninguna empresa por encima "
            "del 20 % y ningún sector por encima del 40 %.", "", ("Diversificación",)),
    Termino("Correlación", "Riesgo y cartera",
            "Cuánto se mueven dos inversiones a la vez. Dos bancos están muy correlacionados; un banco y una "
            "eléctrica, menos. Combinar cosas poco correlacionadas reduce las caídas.", "", ("Diversificación",)),
    Termino("Caída máxima", "Riesgo y cartera",
            "La mayor caída desde un máximo hasta el mínimo siguiente (en inglés, «drawdown»). Ojo: recuperar cuesta "
            "más que caer.", "Si caes un 50 %, necesitas subir un 100 % para volver a donde estabas.",
            ("Riesgo",)),
    Termino("Beta", "Riesgo y cartera",
            "Cuánto se mueve una acción respecto al mercado. Beta 1: igual; 1,5: un 50 % más; 0,5: la mitad.", "",
            ("Volatilidad",)),
    Termino("Riesgo por operación", "Riesgo y cartera",
            "Lo máximo que aceptas perder en una operación si salta el stop-loss, como % de tu dinero. La regla "
            "prudente es el 1-2 %. Con eso, la app calcula cuántas acciones comprar.",
            "Tienes 10.000 € y arriesgas el 1 % (100 €). Compras a 20 € con stop a 18 €: pierdes 2 € por acción, así "
            "que compras 50 acciones (1.000 €).", ("Stop-loss",)),
    Termino("Ratio beneficio/riesgo", "Riesgo y cartera",
            "Lo que esperas ganar si sale bien dividido por lo que pierdes si salta el stop. Con 2 a 1, aunque "
            "aciertes solo 4 de cada 10 veces, ganas dinero.", "", ("Objetivo de precio", "Stop-loss")),
    Termino("Rebalanceo", "Riesgo y cartera",
            "Volver a poner cada parte de tu cartera en el peso que planeaste, vendiendo lo que ha crecido de más y "
            "comprando lo que se ha quedado atrás. Una o dos veces al año basta.", "", ("Diversificación",)),
    Termino("Interés compuesto", "Riesgo y cartera",
            "Ganar rentabilidad también sobre lo que ya has ganado. Con el tiempo es lo que más hace crecer el dinero.",
            "10.000 € al 7 % anual son unos 19.700 € en 10 años y 38.700 € en 20.", ("Regla del 72",)),
    Termino("Regla del 72", "Riesgo y cartera",
            "Divide 72 entre la rentabilidad anual para saber en cuántos años se dobla tu dinero.",
            "Al 6 %: 72 / 6 = 12 años.", ("Interés compuesto",)),
    Termino("Rentabilidad anualizada", "Riesgo y cartera",
            "Lo que ganarías de media cada año para llegar al mismo resultado. Permite comparar inversiones de "
            "duración distinta.", "Doblar en 10 años es un 7,2 % anualizado, no un 10 %.", ()),
    Termino("Baja volatilidad", "Riesgo y cartera",
            "Estrategia de elegir las acciones que menos se mueven. Históricamente han dado casi lo mismo que la "
            "media con menos sustos. La cartera Tranquila de la app se basa en ella.", "", ("Volatilidad",)),
    Termino("Sesgo de supervivencia", "Riesgo y cartera",
            "Error de mirar solo las empresas que siguen existiendo. Las simulaciones con las empresas de hoy parecen "
            "mejores de lo que fueron en realidad, porque las que quebraron no aparecen.", "", ("Backtest",)),
    Termino("Backtest", "Riesgo y cartera",
            "Probar una estrategia con datos del pasado. Útil, pero lo que funcionó no tiene por qué repetirse.", "",
            ("Sesgo de supervivencia", "Sobreajuste")),
    Termino("Sobreajuste", "Riesgo y cartera",
            "Cuando una estrategia se ajusta tanto al pasado que solo funciona en él. La app lo evita probando cada "
            "año con reglas elegidas solo con los años anteriores (walk-forward).", "", ("Backtest",)),
    Termino("FOMO", "Riesgo y cartera",
            "Miedo a quedarse fuera: comprar algo solo porque ha subido mucho y todo el mundo habla de ello. Suele "
            "acabar comprando caro.", "", ("Venta por pánico",)),
    Termino("Venta por pánico", "Riesgo y cartera",
            "Vender todo en plena caída por miedo. Es el error que más dinero ha costado a los inversores "
            "particulares: convierte una caída temporal en una pérdida definitiva.", "", ("FOMO",)),
    # ------------------------------------------------------------------ Fondos y otros productos
    Termino("Fondo de inversión", "Fondos y otros productos",
            "Dinero de muchos inversores que gestiona una gestora. Compras participaciones a su valor liquidativo "
            "(una vez al día). En España puedes pasar de un fondo a otro sin pagar impuestos (traspaso).", "",
            ("Fondo indexado", "Traspaso", "Valor liquidativo")),
    Termino("Fondo indexado", "Fondos y otros productos",
            "Fondo que copia un índice (por ejemplo, el MSCI World) en lugar de intentar elegir empresas. Es barato y, a "
            "largo plazo, gana a la mayoría de fondos que eligen empresas. La base recomendada para casi todo el mundo.",
            "", ("MSCI World", "TER", "Aportación periódica")),
    Termino("ETF", "Fondos y otros productos",
            "Fondo que cotiza en bolsa como una acción. Barato, pero en España no admite traspasos (tributa al vender) "
            "y en Bankinter cada compra de un ETF extranjero cuesta 20 €. Para aportar cada mes, mejor un fondo "
            "indexado.", "", ("Fondo indexado",)),
    Termino("TER", "Fondos y otros productos",
            "Gastos anuales de un fondo, en %. Se cobran solos, restando del valor del fondo. En un indexado debería "
            "ser menor del 0,3 %; en muchos fondos de gestión activa pasa del 1,5 %.", "", ("Fondo indexado",)),
    Termino("Valor liquidativo", "Fondos y otros productos",
            "Precio de una participación de un fondo, calculado una vez al día con el cierre de mercado.", "", ()),
    Termino("Traspaso", "Fondos y otros productos",
            "Mover dinero de un fondo a otro sin vender a efectos fiscales: no pagas impuestos hasta que retires el "
            "dinero. No vale para ETF ni acciones.", "", ("Fondo de inversión",)),
    Termino("Aportación periódica", "Fondos y otros productos",
            "Invertir la misma cantidad cada mes, pase lo que pase. Evita intentar adivinar el mejor momento y "
            "compra más participaciones cuando está barato.", "", ("Fondo indexado",)),
    Termino("Fondo monetario", "Fondos y otros productos",
            "Fondo que invierte en deuda a muy corto plazo. Casi sin riesgo; renta más o menos lo que marcan los "
            "tipos del BCE. Sirve para dinero que necesitarás pronto.", "", ("Letras del Tesoro",)),
    Termino("Bono", "Fondos y otros productos",
            "Préstamo que haces a un Estado o empresa a cambio de intereses. Si los tipos suben, el precio de los "
            "bonos que ya existen baja (y al revés).", "", ("Letras del Tesoro", "Tipos de interés")),
    Termino("Letras del Tesoro", "Fondos y otros productos",
            "Deuda del Estado español a 3, 6, 9 o 12 meses. Se compran en tesoro.es (Banco de España) o en el banco. "
            "Muy seguras.", "", ("Bono", "Fondo monetario")),
    # ------------------------------------------------------------------ Economía
    Termino("Tipos de interés", "Economía",
            "Precio del dinero que fijan los bancos centrales. Si suben, los préstamos encarecen y la bolsa suele "
            "sufrir (aunque los bancos ganan más); si bajan, al revés.", "", ("BCE", "Fed")),
    Termino("BCE", "Economía",
            "Banco Central Europeo: fija los tipos de interés del euro. Se reúne cada ~6 semanas (jueves).", "",
            ("Tipos de interés",)),
    Termino("Fed", "Economía",
            "Reserva Federal de EEUU. Sus decisiones (8 al año, miércoles por la tarde en España) mueven todas las "
            "bolsas del mundo.", "", ("Tipos de interés",)),
    Termino("IPC", "Economía",
            "Índice de precios al consumo: mide la inflación. Una inflación alta hace temer subidas de tipos.", "",
            ("Inflación",)),
    Termino("Inflación", "Economía",
            "Subida general de precios. Hace perder poder de compra al dinero parado; por eso a largo plazo hay que "
            "invertirlo.", "Con un 3 % de inflación, 10.000 € compran en 10 años lo que hoy 7.400 €.", ("IPC",)),
    Termino("Prima de riesgo", "Economía",
            "Diferencia entre lo que paga el bono a 10 años de España y el de Alemania. Si sube, los inversores ven "
            "más riesgo en España.", "", ("Bono",)),
    Termino("VIX", "Economía",
            "El «índice del miedo»: mide cuánto movimiento esperan los inversores en el S&P 500. Por encima de 30 "
            "suele haber nervios fuertes.", "", ("Volatilidad",)),
    Termino("Recesión", "Economía",
            "Caída de la economía (se suele hablar de recesión con dos trimestres seguidos de caída del PIB). La "
            "bolsa suele adelantarse: cae antes y se recupera antes.", "", ()),
    # ------------------------------------------------------------------ Productos peligrosos
    Termino("Apalancamiento", "Productos peligrosos",
            "Invertir con dinero prestado o con productos que multiplican el movimiento. Multiplica ganancias y "
            "pérdidas: con 5 veces de apalancamiento, una caída del 20 % te hace perderlo todo.", "",
            ("CFD", "Margin call")),
    Termino("CFD", "Productos peligrosos",
            "Contrato por diferencias: apuestas al precio con apalancamiento. Los brókers están obligados a decir qué "
            "porcentaje de clientes pierde dinero, y suele estar entre el 70 % y el 80 %. No son para principiantes.",
            "", ("Apalancamiento",)),
    Termino("Warrants y turbos", "Productos peligrosos",
            "Productos apalancados con fecha de vencimiento: puedes perder todo lo invertido en días.", "",
            ("Apalancamiento",)),
    Termino("Venta en corto", "Productos peligrosos",
            "Vender acciones prestadas para recomprarlas más baratas. Si la acción sube, la pérdida no tiene límite.",
            "", ("Comprar / Vender (largo)",)),
    Termino("Margin call", "Productos peligrosos",
            "Aviso del bróker para que pongas más dinero cuando una inversión apalancada va mal. Si no lo pones, "
            "cierra tu posición con pérdidas.", "", ("Apalancamiento",)),
    Termino("Opciones y futuros", "Productos peligrosos",
            "Contratos para comprar o vender en el futuro a un precio fijado. Útiles para profesionales; para "
            "principiantes, una forma rápida de perder dinero.", "", ("Apalancamiento",)),
    # ------------------------------------------------------------------ En esta app
    Termino("Veredicto", "En esta app",
            "La conclusión para cada acción: Candidata a comprar, Tendencia favorable, Neutral, Floja, Arriesgada "
            "ahora, Evitar por ahora o Esperar. Es la misma en toda la app y en «🧠 Por qué» ves los motivos.", "",
            ("Nota global",)),
    Termino("Nota global", "En esta app",
            "De 0 a 100: su puesto frente a las demás acciones hoy (100 = la mejor). Combina momentum (50 %), "
            "análisis técnico (30 %) y menor riesgo de caída (20 %).", "", ("Veredicto", "Riesgo de caída")),
    Termino("Riesgo de caída", "En esta app",
            "Probabilidad de que la acción caiga más de un 10 % en algún momento del próximo mes, calculada con un "
            "modelo comprobado con datos reales. Es lo único que se ha podido anticipar mejor que al azar.", "",
            ("Nota global",)),
    Termino("Cartera modelo", "En esta app",
            "Lista de 8 acciones que se revisa una vez al mes con una regla fija (momentum o baja volatilidad), como "
            "máximo 2 por sector. Está en 📦 Carteras modelo.", "", ("Momentum", "Baja volatilidad")),
    Termino("Regla de protección", "En esta app",
            "Estar invertido en un índice mientras esté por encima de su media de 200 sesiones y salir si cae un 2 % "
            "por debajo. En la historia del IBEX, recortó la peor caída de −63 % a −37 %.", "",
            ("Media de 200 sesiones",)),
    Termino("Semáforo", "En esta app",
            "Resumen del estado del mercado en 🧭 Hoy: verde (tendencia alcista), ámbar (dudas) o rojo (tendencia "
            "bajista: entra poco a poco o espera).", "", ()),
]


# Otras formas de llamar a un término (en inglés, siglas o como se dice en la calle).
ALIAS: dict[str, tuple[str, ...]] = {
    "Acción": ("título", "títulos", "valor", "share", "stock"),
    "Horquilla": ("spread", "bid", "ask", "precio de compra y venta", "diferencial"),
    "Caída máxima": ("drawdown", "máxima caída"),
    "Stop dinámica": ("trailing stop", "stop móvil", "stop dinámico"),
    "Stop relacionadas": ("OCO", "órdenes relacionadas", "one cancels other"),
    "Stop-loss": ("stop loss", "stoploss", "parar pérdidas", "limitar pérdidas"),
    "Objetivo de precio": ("take profit", "recoger beneficios"),
    "Ganancia patrimonial": ("plusvalía", "minusvalía", "plusvalías", "beneficio al vender"),
    "Tasa Tobin": ("ITF", "impuesto sobre transacciones financieras"),
    "Fondo indexado": ("indexado", "gestión pasiva", "index fund", "fondo índice"),
    "Comprar / Vender (largo)": ("long", "posición larga", "estar largo"),
    "Venta en corto": ("short", "corto", "ponerse corto"),
    "Rentabilidad anualizada": ("CAGR", "TAE", "rentabilidad anual"),
    "Comisión": ("corretaje", "gastos del bróker"),
    "Media móvil": ("SMA", "EMA", "media"),
    "Riesgo por operación": ("position sizing", "tamaño de la posición", "cuántas acciones comprar"),
    "Mercado alcista": ("bull market", "toro"),
    "Mercado bajista": ("bear market", "oso", "crash"),
    "Precio / valor contable": ("P/VC", "PVC", "price to book"),
    "BPA": ("EPS", "beneficio por acción"),
    "Fed": ("Reserva Federal", "FOMC"),
    "BCE": ("Banco Central Europeo",),
    "Capitalización": ("market cap", "valor en bolsa"),
    "Dividendo flexible (scrip)": ("scrip dividend", "dividendo en acciones"),
    "Fecha ex-dividendo": ("ex-date", "ex dividendo", "fecha de corte"),
    "Libro de órdenes": ("profundidad de mercado", "posiciones del mercado"),
    "Rebalanceo": ("reequilibrio", "rebalancear"),
    "Concentración": ("demasiado en una empresa",),
    "ETF": ("fondo cotizado", "exchange traded fund"),
    "TER": ("gastos corrientes", "comisión de gestión"),
    "Small caps": ("empresas pequeñas", "pequeñas compañías"),
    "Blue chip": ("valores grandes", "grandes empresas"),
    "Volatilidad": ("cuánto se mueve",),
    "Apalancamiento": ("leverage", "apalancado"),
    "Interés compuesto": ("interés sobre interés",),
}


def _norm(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")


def _contiene(q: str, texto: str) -> bool:
    """`q` aparece en `texto` empezando en el inicio de una palabra (así «oco» no encuentra «poco»)."""
    return re.search(r"(?<![a-z0-9])" + re.escape(q), texto) is not None


def _nombres(t: Termino) -> list[str]:
    return [_norm(t.termino)] + [_norm(a) for a in ALIAS.get(t.termino, ())]


def buscar(texto: str = "", categoria: str | None = None) -> list[Termino]:
    """Términos que contienen `texto` (sin distinguir tildes ni mayúsculas, también por sus alias). Primero los
    que lo tienen en el nombre o un alias, y en orden alfabético."""
    q = _norm(texto.strip())
    salida = [t for t in GLOSARIO if (not categoria or t.categoria == categoria)
              and (not q or any(_contiene(q, n) for n in _nombres(t)) or _contiene(q, _norm(t.definicion))
                   or _contiene(q, _norm(t.ejemplo)))]
    return sorted(salida, key=lambda t: (bool(q) and not any(_contiene(q, n) for n in _nombres(t)), _norm(t.termino)))


def parecidos(texto: str, n: int = 5) -> list[Termino]:
    """Términos con un nombre parecido (para errores al escribir: «stoploss», «dividedno»...)."""
    import difflib

    q = _norm(texto.strip())
    if not q:
        return []
    por_nombre = {n_: t for t in GLOSARIO for n_ in _nombres(t)}
    encontrados = difflib.get_close_matches(q, list(por_nombre), n=n * 2, cutoff=0.6)
    salida = []
    for nombre in encontrados:
        t = por_nombre[nombre]
        if t not in salida:
            salida.append(t)
    return salida[:n]


def definicion(termino: str) -> str:
    """Definición corta para usar como ayuda (tooltip) en otras páginas."""
    t = next((x for x in GLOSARIO if _norm(x.termino) == _norm(termino)), None)
    return t.definicion if t else ""


# ---------------------------------------------------------------------------------------------- guías
@dataclass(frozen=True)
class Guia:
    titulo: str
    para_que: str
    pasos: list[str]
    errores: list[str] = field(default_factory=list)
    en_la_app: str = ""


GUIAS: list[Guia] = [
    Guia("Antes de empezar: ¿estoy listo para invertir?",
         "Evitar tener que vender en mal momento porque necesitas el dinero.",
         ["Ten un **colchón de emergencia** de 3 a 6 meses de gastos en una cuenta o un fondo monetario, fuera de la "
          "bolsa.",
          "**Paga primero las deudas caras** (tarjetas, préstamos al consumo): ninguna inversión rinde de forma segura "
          "más de lo que te cuestan.",
          "Separa el dinero que vayas a necesitar en **menos de 3-5 años**: ese no va a bolsa.",
          "Responde las 5 preguntas de 🎯 Mi plan para saber tu **perfil** (conservador, moderado o dinámico).",
          "Decide cuánto vas a aportar **cada mes** y apúntalo. La constancia gana a la puntería."],
         ["Invertir el dinero de la entrada del piso o del coche.", "Empezar con todo de golpe por miedo a perderse "
          "una subida."],
         "🎯 Mi plan te da el reparto en euros según tu perfil."),
    Guia("Comprar una acción española en Bankinter",
         "Comprar al precio que tú decides, sin sorpresas.",
         ["En la app, abre 🔍 Analizar, elige la empresa y mira el **veredicto**. Si no es «Candidata a comprar», "
          "piénsatelo dos veces.",
          "Copia la **orden de compra** que te prepara la app (número de acciones y precio límite).",
          "En Bankinter: **Bróker → busca la empresa → Comprar**.",
          "Tipo de orden: **Limitada**. Escribe el número de títulos y el precio límite.",
          "Validez: unos días (por ejemplo, una semana). Revisa el **coste estimado** que muestra Bankinter y "
          "confirma con tu firma.",
          "Cuando se ejecute, **pon el stop-loss enseguida** (siguiente guía) y apunta la compra en 🏦 Mi cartera."],
         ["Usar orden «a mercado» en acciones poco negociadas.", "Comprar más del 20 % de tu dinero en una sola "
          "empresa.", "Olvidarte del stop-loss."],
         "En 🔍 Analizar → «Si decides comprar» tienes las órdenes listas para copiar."),
    Guia("Poner un stop-loss",
         "Limitar la pérdida si la compra sale mal.",
         ["Mira el **precio de stop** que propone la app (2 veces lo que se mueve en un día normal por debajo del "
          "precio).",
          "En Bankinter: **Bróker → busca la empresa → Vender** y elige orden **Stop**.",
          "Condición: **«menor o igual que»** el precio de stop (precio de activación).",
          "**Precio límite**: un 2 % por debajo del de activación, para que se venda aunque caiga deprisa.",
          "Títulos: todos los que tienes. Validez: la máxima que permita.",
          "Apunta el stop en 🏦 Mi cartera para que la app lo vigile y te avise si conviene subirlo."],
         ["Ponerlo tan cerca que salte con el movimiento normal de un día.", "Bajarlo cuando el precio se acerca: "
          "anula su sentido.", "Dejar que caduque sin renovarlo."],
         "Las fichas de órdenes de la app incluyen activación y límite calculados."),
    Guia("Protección y objetivo a la vez (stop relacionadas)",
         "Dejar puesta la venta con pérdidas pequeñas y la venta con beneficio, sin vigilar a diario.",
         ["En Bankinter: **Bróker → Vender → Stop relacionadas** (o «órdenes relacionadas»).",
          "Orden 1, **protección**: activación en tu stop-loss y límite un 2 % por debajo.",
          "Orden 2, **objetivo**: venta limitada al precio objetivo que propone la app.",
          "Cuando se ejecute una, Bankinter cancela la otra automáticamente."],
         ["Poner el objetivo tan cerca que ganes menos de lo que arriesgas."],
         "La ficha «PROTECCIÓN + OBJETIVO» de la app trae los dos precios."),
    Guia("Subir el stop cuando la acción sube",
         "Asegurar parte de la ganancia.",
         ["Cuando la app te avise («🟢⬆️ subir stop»), mira el nuevo nivel propuesto.",
          "En Bankinter las órdenes stop **no se pueden modificar**: ve a **Órdenes → anula** el stop actual.",
          "Crea uno nuevo con el precio nuevo (activación y límite un 2 % por debajo).",
          "Alternativa: usa una **stop dinámica**, que sube sola y nunca baja.",
          "Actualiza el stop en 🏦 Mi cartera."],
         ["Bajar el stop.", "Quedarte sin stop entre anular el viejo y crear el nuevo: hazlo seguido."]),
    Guia("Vender",
         "Salir de una posición de forma ordenada.",
         ["Motivos razonables para vender: salta el stop, llega al objetivo, la cartera modelo la saca este mes, o "
          "necesitas reducir una empresa que pesa demasiado. «Está en pérdidas» o «ha bajado hoy» no son motivos "
          "por sí solos.",
          "Antes de vender, **anula el stop-loss** pendiente de esas acciones (si no, Bankinter puede rechazar la "
          "venta por títulos no disponibles).",
          "En Bankinter: **Bróker → Vender → Limitada**, con un precio cercano al de compra del momento.",
          "Apunta la venta en la app. Si vendes con pérdidas, **no recompres la misma acción en 2 meses** si quieres "
          "usar esa pérdida en la renta."],
         ["Vender todo en plena caída por miedo.", "Vender las ganadoras demasiado pronto y aguantar las perdedoras "
          "para no «reconocer» la pérdida."],
         "🏦 Mi cartera te dice qué hacer con cada posición y te deja la orden de venta escrita."),
    Guia("Aportar cada mes a un fondo indexado",
         "La forma más sencilla y eficaz de invertir a largo plazo.",
         ["En Bankinter, ve a **Fondos** y busca un fondo indexado al **MSCI World** o al **FTSE All-World** "
          "(comisión anual por debajo del 0,3 %).",
          "Lee el documento de datos fundamentales (DFI): qué índice copia, gastos y riesgo.",
          "Haz la primera aportación y programa una **aportación periódica** mensual.",
          "No mires el saldo cada día. Revisa una vez al año.",
          "Si algún día quieres cambiar de fondo, hazlo con un **traspaso** (no paga impuestos)."],
         ["Parar las aportaciones cuando la bolsa cae: es justo cuando compras más barato.", "Elegir un fondo caro "
          "de gestión activa pensando que lo hará mejor."],
         "🎯 Mi plan te dice cuánto poner cada mes en el fondo."),
    Guia("Seguir una cartera modelo una vez al mes",
         "Aplicar una estrategia probada sin decidir por impulso.",
         ["Entra en 📦 Carteras modelo a principios de mes y abre la de tu perfil.",
          "Compara la lista de este mes con lo que tienes: **vende** las que han salido y **compra** las que han "
          "entrado, con el mismo dinero en cada una.",
          "Usa órdenes limitadas y pon el stop-loss en las nuevas.",
          "No toques nada el resto del mes salvo que salte un stop."],
         ["Saltarte meses o elegir solo las que te gustan: la estrategia funciona como conjunto.", "Usar muy poco "
          "dinero por empresa: las comisiones se comen la rentabilidad (mínimo ~1.000 € por empresa en España)."]),
    Guia("Revisar tu cartera con la app",
         "Saber si tu dinero está bien repartido y qué hacer.",
         ["En tu banco, descarga tu posición (CSV o Excel) o copia la tabla de tu cartera. En Bankinter: **Bróker → "
          "Posición global → descargar** («Posición global.csv»).",
          "En la app: 🏦 Mi cartera → **Archivo de tu banco** (o **Pegar tabla**) y súbelo tal cual.",
          "Indica tu perfil y, si quieres, tus otros ahorros: el **diagnóstico** te dirá si alguna empresa, sector "
          "o país pesa demasiado y te propondrá cambios con su coste e impuestos.",
          "Apunta el stop-loss de cada posición (el archivo no lo incluye).",
          "Repite la importación cuando compres o vendas."]),
    Guia("Cobrar dividendos",
         "Entender qué pasa cuando una empresa reparte beneficios.",
         ["Para cobrarlo, debes tener las acciones al cierre del día **anterior a la fecha ex-dividendo**.",
          "Bankinter te ingresa el dividendo en la cuenta, ya con la **retención del 19 %**.",
          "Ese día la acción baja más o menos lo que ha pagado: no es dinero gratis.",
          "En los dividendos «flexibles» (scrip) Bankinter te pregunta si quieres acciones nuevas o vender los "
          "derechos; si no contestas, aplica la opción por defecto."],
         ["Comprar justo antes del dividendo pensando que es una ganancia segura."]),
    Guia("La declaración de la renta",
         "No pagar de más ni equivocarte.",
         ["Bankinter te envía el **informe fiscal** del año a principios de la campaña.",
          "Comprueba que las ventas y dividendos de los **datos fiscales** de Hacienda coinciden con ese informe.",
          "Las **ganancias** al vender y los **dividendos** tributan en la base del ahorro (19 % a 30 %).",
          "Las **pérdidas** compensan ganancias del mismo año y, si sobran, se arrastran 4 años.",
          "Si vas a vender con mucha ganancia a final de año, valora vender también alguna posición en pérdidas que "
          "ya no quieras (sin recomprarla en 2 meses) o repartir las ventas entre dos años."],
         ["Olvidar declarar las ventas de acciones extranjeras.", "No aplicar la deducción por doble imposición de "
          "los dividendos extranjeros."],
         "🧮 Calculadoras → Impuestos te da el IRPF aproximado de una venta."),
    Guia("Qué hacer cuando la bolsa cae fuerte",
         "No convertir una caída temporal en una pérdida definitiva.",
         ["Respira: las caídas del 10 % ocurren casi cada año y las del 30 % varias veces por década.",
          "Comprueba que tus stop-loss de acciones sueltas están puestos y respétalos.",
          "**No toques el fondo indexado**: sigue con las aportaciones mensuales (compras más barato).",
          "Mira la **regla de protección** en 🧭 Hoy: si el índice cae un 2 % bajo su media de 200 sesiones, la app "
          "te lo dice.",
          "Si no duermes tranquilo, quizás tu perfil es más conservador de lo que pensabas: ajústalo cuando pase la "
          "tormenta, no en mitad de ella."],
         ["Vender todo por pánico.", "Intentar «comprar el suelo» con todo tu dinero."]),
]


def buscar_guias(texto: str) -> list[Guia]:
    q = _norm(texto.strip())
    if not q:
        return []
    return [g for g in GUIAS if _contiene(q, _norm(" ".join([g.titulo, g.para_que, g.en_la_app, *g.pasos, *g.errores])))]


# ---------------------------------------------------------------------------------------------- test
@dataclass(frozen=True)
class Pregunta:
    pregunta: str
    opciones: list[str]
    correcta: int
    explicacion: str


PREGUNTAS: list[Pregunta] = [
    Pregunta("Quieres comprar Iberdrola sin pagar más de 15 €. ¿Qué orden usas?",
             ["A mercado", "Limitada a 15 €", "Stop a 15 €"], 1,
             "La orden limitada garantiza que no pagas más de tu precio. «A mercado» compra al precio que haya."),
    Pregunta("Compraste a 20 € con el stop-loss en 18 €. La acción sube a 26 €. ¿Qué haces con el stop?",
             ["Lo bajo a 16 € para darle margen", "Lo dejo en 18 €", "Lo subo (por ejemplo, a 23 €)"], 2,
             "El stop se sube para asegurar parte de la ganancia y nunca se baja. En Bankinter: anular y crear uno nuevo."),
    Pregunta("Tienes 10.000 € y aceptas perder como mucho el 1 % por operación. Compras a 50 € con stop a 45 €. "
             "¿Cuántas acciones compras?", ["20", "200", "50"], 0,
             "Arriesgas 100 € (1 % de 10.000) y pierdes 5 € por acción si salta el stop: 100 / 5 = 20 acciones."),
    Pregunta("Una acción cae un 50 %. ¿Cuánto tiene que subir para volver al precio inicial?",
             ["Un 50 %", "Un 100 %", "Un 75 %"], 1,
             "De 100 € a 50 € es −50 %, pero de 50 € a 100 € es +100 %. Por eso limitar las pérdidas es clave."),
    Pregunta("¿Qué reduce el riesgo sin reducir la rentabilidad esperada?",
             ["Diversificar", "Operar más a menudo", "Seguir las noticias al minuto"], 0,
             "Repartir entre muchas empresas, sectores y países evita que un problema concreto te hunda."),
    Pregunta("Para aportar 200 € cada mes en Bankinter, ¿qué sale más barato?",
             ["Un ETF extranjero", "Un fondo indexado", "Acciones de EEUU"], 1,
             "Las aportaciones a fondos no pagan comisión de compra; cada compra de un ETF extranjero cuesta 20 €."),
    Pregunta("Vendes Santander con pérdidas el 1 de marzo y lo recompras el 15 de marzo. ¿Puedes usar esa pérdida "
             "en la renta de este año?", ["Sí", "No, por la regla de los 2 meses"], 1,
             "Si recompras en los 2 meses siguientes, la pérdida queda aplazada hasta que vendas las recompradas."),
    Pregunta("La bolsa cae un 25 % en dos meses. Llevas años aportando a un fondo indexado. ¿Qué es lo más sensato?",
             ["Vender todo y esperar", "Seguir aportando como siempre", "Pedir un préstamo para comprar más"], 1,
             "Seguir con el plan: las aportaciones compran más barato y la historia muestra que las caídas se "
             "recuperan. Vender en pánico convierte la caída en pérdida."),
    Pregunta("Una acción paga 1 € de dividendo y cotiza a 25 €. ¿Qué pasa el día que lo paga?",
             ["Ganas 1 € gratis", "La acción baja más o menos 1 € y cobras 1 € menos la retención", "Nada"], 1,
             "El dividendo sale del valor de la empresa: tu patrimonio no cambia y además tributa."),
    Pregunta("¿Qué significa un PER de 10?",
             ["Que la acción ha subido un 10 %", "Que pagas 10 años de beneficios", "Que tiene 10 analistas"], 1,
             "PER = precio / beneficio por acción. Compáralo siempre con empresas del mismo sector."),
]


def buscar_preguntas(texto: str) -> list[Pregunta]:
    q = _norm(texto.strip())
    if not q:
        return []
    return [p for p in PREGUNTAS if _contiene(q, _norm(" ".join([p.pregunta, p.explicacion, *p.opciones])))]


__all__ = ["ALIAS", "CATEGORIAS", "GLOSARIO", "GUIAS", "PREGUNTAS", "Termino", "Guia", "Pregunta", "buscar",
           "buscar_guias", "buscar_preguntas", "definicion", "parecidos"]
