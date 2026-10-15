# 📈 Asistente de Bolsa para principiantes

Una app sencilla (en español) que te ayuda a invertir en bolsa con el **broker de Bankinter**:

| Sección | Qué hace |
|---|---|
| 🏠 **Resumen del día** | IBEX 35, Euro Stoxx 50, DAX, S&P 500 y Nasdaq, VIX, euro/dólar y petróleo, más un **semáforo** (verde / ámbar / rojo) que dice si es buen momento para invertir. |
| 📰 **Noticias** | Junta las últimas noticias de **19 fuentes** en español e inglés (Expansión, elEconomista, Cinco Días, El País, El Confidencial, Europa Press, La Vanguardia, Investing, Google News, CNBC, MarketWatch, Yahoo Finance). Detecta cuántos medios publican la misma noticia. Las ordena por **impacto** (tipos de interés, BCE/Fed, inflación, aranceles, resultados, OPAs...), dice si son **positivas o negativas** y te explica **por qué importan**. |
| 🔍 **Analizar una acción** | Da una puntuación de 0 a 100 y un veredicto (*Zona de compra*, *Compra escalonada*, *Esperar*, *Evitar*), explicando cada motivo. Te propone un **plan**: precio de compra, **stop-loss**, objetivo y **cuántas acciones comprar** según el dinero que quieras arriesgar. Incluye datos de la empresa (PER, dividendo, márgenes), **precio objetivo de los analistas**, noticias específicas y los pasos para hacerlo en la app de Bankinter. |
| 🔮 **Predicción** | Probabilidad de subida y rango de precio probable a 1 semana, 1 mes y 3 meses, con su **porcentaje de acierto real** medido con datos pasados. |
| 📡 **Radar del IBEX 35** | Analiza las 35 empresas a la vez y las ordena por puntuación. |
| 🧪 **Simulador** | Prueba la estrategia con **dinero virtual** sobre 10 años de datos reales (operando día a día sin ver el futuro, con comisiones y stop-loss) y la **entrena**: prueba decenas de combinaciones de reglas y se queda con la de menor error de inversión, validándola en años que no ha visto (*walk-forward*). |
| 🎮 **Cartera virtual** | Practica con dinero ficticio a precios reales (los stop-loss y objetivos se ejecutan solos) y crea un **robot** que opera solo desde hoy: una prueba en tiempo real, sin trampas. |
| 🏦 **Mi Bankinter** | Copiloto de tu broker: registras o **importas** (Excel/CSV) tus posiciones de Bankinter y la app las vigila, te avisa (stop tocado, tendencia rota, subir stop, resultados próximos) y te deja escrita la **orden exacta** para copiar en Bankinter. |
| 🧮 **Calculadoras** | Comisiones + Impuesto de Transacciones Financieras, IRPF al vender, e interés compuesto invirtiendo cada mes. |
| 🎓 **Aprende** | Lo básico explicado fácil: diccionario, reglas de oro y calendario de eventos. **Empieza por aquí.** |

> ⚠️ **Es una herramienta educativa, no asesoramiento financiero.** Ningún programa puede garantizar
> beneficios ni adivinar el futuro. Lo que sí hace es ayudarte a no comprar en mal momento, a tener
> siempre un plan con stop-loss, y a entender lo que haces.

## 📱 Usarla en el móvil (recomendado, gratis, sin instalar nada en el móvil)

1. Entra en <https://share.streamlit.io> e inicia sesión con tu cuenta de **GitHub**.
2. Pulsa **Create app → Deploy a public app from GitHub**.
3. Elige el repositorio `Bolsa_Alex`, la rama donde está el código y el archivo `app.py`. Pulsa **Deploy**.
4. En 2-3 minutos tendrás un enlace (`https://....streamlit.app`). Ábrelo en el móvil y pulsa
   **"Añadir a pantalla de inicio"** (Safari: botón compartir · Chrome: menú ⋮).
   Tendrás un icono como cualquier app, al lado de la de Bankinter.

La app detecta el móvil y se adapta sola: menú arriba, gráficos más compactos y tablas con menos columnas
(también puedes activarlo a mano en ⚙️ *Tu perfil → Vista para móvil*).

### Que no se pierdan tus carteras en el móvil (guardado en la nube)
La versión publicada borra sus archivos al reiniciarse. Para guardar tus carteras y la estrategia
entrenada de forma permanente, usa un **Gist privado de GitHub** (gratis):

1. Entra en <https://gist.github.com>, crea un gist **secreto** con un archivo llamado
   `bolsa_alex_datos.json` cuyo contenido sea `{}`. Copia el código largo de la dirección
   (`https://gist.github.com/tu_usuario/ESTE_CODIGO`).
2. En GitHub → *Settings → Developer settings → Personal access tokens → Fine-grained tokens*, crea un
   token con el permiso **Gists: Read and write**. Cópialo.
3. En Streamlit Cloud → tu app → **Settings → Secrets**, pega:
   ```toml
   [gist]
   token = "github_pat_..."
   id = "ESTE_CODIGO"
   ```
En el ordenador se guardan en `datos_usuario/datos.json`. En ambos casos puedes descargar y restaurar
una copia de seguridad desde la propia app.

## Cómo instalarla en el ordenador

1. Instala **Python 3.10 o superior** desde <https://www.python.org/downloads/>
   (en Windows marca la casilla *"Add Python to PATH"*).
2. Descarga este proyecto (botón verde **Code → Download ZIP** en GitHub) y descomprímelo.
3. Abre una terminal en la carpeta del proyecto y ejecuta:

   ```bash
   pip install -r requirements.txt
   ```

## Cómo usarla

```bash
streamlit run app.py
```

Se abrirá en tu navegador (http://localhost:8501). Para cerrarla, pulsa `Ctrl + C` en la terminal.

## Rutina recomendada (10 minutos al día o a la semana)
1. **Resumen del día** → mira el semáforo.
2. **Noticias** → lee las 3-5 más influyentes y su explicación.
3. **Radar** → apunta empresas con 70 puntos o más.
4. **Analizar** → revisa los motivos y el plan.
5. **Bankinter** → compra con **orden limitada** y pon el **stop-loss** en cuanto se ejecute.

## Cómo decide (sin cajas negras)
La puntuación empieza en 50 y suma o resta puntos según reglas clásicas y transparentes:

- **Tendencia de fondo**: precio por encima/debajo de su media de 200 sesiones (±15).
- **Cruce de medias** 50/200, "cruce dorado" o "de la muerte" (±8).
- **Tendencia a medio plazo**: precio frente a la media de 50 (±5).
- **RSI**: premia comprar caídas dentro de tendencias alcistas y penaliza perseguir subidas (+12 a −10).
- **Impulso MACD** (±8).
- **Noticias** de la empresa (±6) y **ambiente del mercado** (+4 / −6).
- **Analistas** (precio objetivo, ±6), **PER** (±3/−4) y **dividendo** (+2).
- **Modelo de predicción** (±10), *solo si ha demostrado acertar más que el azar con esa acción*.
- El **stop-loss** se coloca a 2 × ATR (movimiento diario típico) y el objetivo al doble de distancia
  (ganas 2 € por cada 1 € que arriesgas).

Todo el código de las reglas está en `bolsa/senales.py` y `bolsa/noticias.py`.

## Cómo predice (y por qué no promete milagros)
`bolsa/prediccion.py` usa el método de **situaciones parecidas** (k vecinos más cercanos): describe el
momento actual de la acción con 9 números (tendencia, RSI, impulso a 1 semana / 1 mes / 3 meses,
volatilidad, MACD, distancia a máximos), busca en los últimos 10 años los días más parecidos y mira qué
pasó después.

Después **se examina a sí mismo** en ~150 fechas pasadas usando solo la información disponible en cada
fecha (validación *walk-forward*) y compara su acierto con el de decir siempre lo mismo:

- 🟢 **Alta**: acierta al menos 8 puntos más que la referencia.
- 🟡 **Media**: entre 3 y 8 puntos más.
- 🔴 **Baja**: no mejora al azar → la app lo dice y **no lo usa** en la puntuación.

Nadie puede predecir la bolsa con precisión; en bolsa, acertar de forma sostenida un 55-60% con el riesgo
controlado ya es muy bueno. Lo importante es que siempre sepas cuánto fiarte.

## Simulador y entrenamiento (`bolsa/simulador.py`)
- **Sin mirar el futuro**: cada día se decide con el cierre anterior y se ejecuta en la apertura; la
  predicción de cada día se calcula solo con datos anteriores. Hay una prueba automática que lo verifica
  (si se cambian los precios a partir de una fecha, todo lo anterior queda idéntico).
- **Realista**: comisiones de tu perfil, impuesto de transacciones, stop-loss que se ejecutan incluso si la
  acción abre por debajo (hueco), tamaño de posición según tu riesgo y número máximo de empresas.
- **Entrenamiento walk-forward**: con 3 años entrena (prueba N combinaciones de umbrales de compra/venta,
  stop, objetivo, peso del modelo y nº de posiciones) y con el año siguiente comprueba. Avanza un año y
  repite. El resultado que se muestra es el de los años **no vistos**, comparado con las reglas por
  defecto y con comprar y mantener.
- **Qué es "error de inversión"**: tú eliges qué minimizar: *Equilibrado* (rentabilidad anual menos la
  mitad de la peor caída), *Menos pérdidas* (la menor caída ganando dinero) o *Máxima rentabilidad*.
- **Limitaciones**: no hay histórico gratuito de noticias ni de analistas (no se simulan); se usa la
  composición actual del IBEX (sesgo de supervivencia); no incluye IRPF. Si el simulador dice que la
  estrategia no bate a comprar y mantener, créetelo: es lo más habitual en bolsa.

## Cómo trabaja con Bankinter
Bankinter no ofrece una API pública para que apps de terceros lean la cuenta de un particular o envíen
órdenes, así que la app **no se conecta** a tu cuenta ni toca tu dinero. Funciona como copiloto:
prepara cada orden con los campos del formulario de Bankinter (valor, mercado, tipo limitada, precio,
títulos, validez y stop-loss), importa tus posiciones desde un Excel/CSV y vigila lo que tienes.

## Datos
- Cotizaciones: Yahoo Finance (gratis, ~15 minutos de retraso). En Yahoo las acciones españolas
  llevan el sufijo `.MC` (por ejemplo `SAN.MC` = Santander); en Bankinter búscalas por el nombre.
- Noticias: RSS públicos. Si una fuente cambia su dirección, edítala en `bolsa/noticias.py` (`FUENTES_RSS`).
- Comisiones de Bankinter: los valores por defecto son orientativos. Ajústalos en la barra lateral
  con tu tarifa real (app Bankinter → Broker → Tarifas).

## Para desarrolladores
```bash
pip install pytest
python -m pytest
```
