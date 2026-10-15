# 📈 Asistente de Bolsa para principiantes

Una app sencilla (en español) que te ayuda a invertir en bolsa con el **broker de Bankinter**:

| Sección | Qué hace |
|---|---|
| 🧭 **Hoy** | **🧑‍💼 Tu asesor hoy** (con avisos de dividendos y **📅 tu semana en palabras**, también por Telegram los viernes): cuánto vale tu dinero y qué hacer hoy, en orden de importancia (protección de índices, stops, concentración, movimientos fuertes de bitcoin u oro...). Pantalla de inicio: semáforo del mercado, resumen en pocas palabras, **ideas del día** (diversificadas por sector), **qué puede pasar** según la historia de los índices, noticias clave y avisos de tu cartera. Abre al instante porque usa el informe diario. |
| 🎯 **Mi plan** | Asesor: 6 preguntas → tu perfil (conservador, moderado o dinámico) y un **reparto concreto en euros** (Letras/monetario, renta fija, **fondo indexado mundial** y unas pocas acciones españolas), con órdenes para Bankinter, escenarios a 1 año y pruebas de estrés en crisis reales. |
| 🔍 **Analizar** | **Veredicto** claro (Candidata a comprar, Neutral, Esperar…), nota global, riesgo de caída, por qué, plan en euros con stop-loss, costes reales de Bankinter y las **órdenes exactas** (limitada + stop relacionadas), qué le puede pasar a tu dinero, datos de la empresa y noticias. |
| 📡 **Radar** | Acciones españolas (o todas) ordenadas por nota global con su veredicto. Toca una fila para analizarla. |
| 📰 **Noticias** | 19 fuentes en español e inglés, ordenadas por impacto. Cada noticia con su **conclusión sencilla**: dónde repercute (empresa, sector o mercado; qué suele subir y qué suele bajar), qué suele pasar, la oportunidad o el riesgo que genera, lo que la app ve hoy de esa empresa y si te afecta por lo que tienes en cartera. |
| 🌍 **Mercados** | Como la pantalla de mercados del bróker: tarjetas de los índices mundiales y pestañas de **divisas, materias primas, criptomonedas, tipos de interés y macro, fondos indexados, ETF y oro, y acciones de todos los mercados** (España, Europa, EEUU, Reino Unido, Suiza, Nórdicos, Asia y otros). Toca una fila para **comprar o vender en la cartera virtual** o analizarla. Cada pestaña descarga solo lo suyo y en un único lote. |
| 🏦 **Mi cartera** | Para **cualquier banco o bróker** (Bankinter, CaixaBank, BBVA, Santander, ING, Kutxabank, Trade Republic, MyInvestor, Degiro...): importa el CSV/Excel de tu banco o **pega la tabla** de su web; reconoce ISIN, fondos, ETF, oro y criptomonedas. Diagnóstico como el de un asesor (concentración, sectores, países, **reparto por tipo de activo frente a tu perfil**, límites prudentes para cripto y oro), propuesta de reequilibrio con comisiones de tu bróker e IRPF, y órdenes escritas para tu bróker. La app nunca pide usuario ni contraseña del banco. |
| 🏦 Mi cartera (además) | **Plan por pasos con calendario fiscal** (qué vender este año y qué en enero para pagar menos IRPF, pérdidas primero y entrada al fondo en tramos), **dividendos** (cuánto cobras al año, neto tras el 19 %, próxima fecha ex-dividendo), **tu cartera frente a un fondo indexado y el IBEX** (1, 3 y 5 años: rentabilidad, volatilidad y peor caída), guía y prueba de **avisos de Telegram** y palabras de la página explicadas. |
| ✅ **¿Acierta la app?** | Todas las pruebas de lo que dice la app con datos que no conocía: lo que no funciona (adivinar subidas), lo que sí (riesgo de caída), las carteras modelo con comisiones y, en tiempo real, las ideas y los **veredictos de cada día** comprobados un mes después. |
| 💬 **Pregunta** | **Gratis**: el asistente de la app responde con datos reales de cualquier valor que nombres (precio, tendencia, RSI explicado, PER, analistas, veredicto), de oro, bitcoin e índices, de tu cartera (con límites prudentes según tu perfil) y del diccionario y las guías. Para preguntas abiertas, prepara la pregunta con tu contexto para pegarla en claude.ai (plan gratuito). Opcional y de pago: conectar la API de Claude en Secrets (`[anthropic]` `api_key`) para que responda dentro de la app. |
| 🎮 **Cartera virtual** | Un bróker de práctica con dinero ficticio: ficha de cotización (último, variación, apertura, máximo, mínimo, volumen, gráfico del día; ~15 min de retraso), órdenes **limitadas, a mercado y stop con límite** que se ejecutan cuando el precio llega de verdad (velas de 5 minutos), órdenes pendientes con dinero reservado, validez, comisiones de tu tarifa, posición al estilo Bankinter, evolución frente al IBEX y ejercicios guiados. También un robot que opera solo. |
| 🧪 **Simulador y modelos** | Resultados diarios con todas las empresas, acierto real de las ideas pasadas, laboratorio de experimentos, y simulación/entrenamiento propios. |
| 🧮 **Calculadoras** · 🎓 **Aprende** | Costes, impuestos, interés compuesto. Aprende: lo esencial, **diccionario bursátil** con buscador (más de 100 términos con ejemplos), **guías paso a paso** de cómo se hace cada cosa en Bankinter y un test para comprobar lo aprendido. |

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

## Rutina recomendada
**Una vez:** rellena 🎯 **Mi plan** (tu perfil y cuánto invertir) y crea un **robot** en 🎮 Cartera virtual para
ver durante unas semanas cómo se comporta la estrategia antes de arriesgar dinero real.

**Cada día o cada semana (5 minutos):**
1. 🧭 **Hoy** → semáforo, regla de protección, ideas del día, qué puede pasar y avisos de tu cartera.
2. 🔍 **Analizar** → antes de comprar algo, lee los motivos, el riesgo de caída y el plan con stop-loss.
3. **Bankinter** → copia la orden que te prepara la app (orden limitada + stop-loss) y regístrala en 🏦 Mi Bankinter.

**Una vez al mes:** revisa 📦 **Carteras modelo** (qué entra y qué sale). La aportación al fondo indexado,
mejor programarla en Bankinter como aportación periódica.

## Cómo decide (sin cajas negras)
La **nota global** (0-100) es el puesto de cada acción frente a las demás, combinando lo que ha funcionado con
datos reales: momentum del último año (50%), puntuación técnica (30%) y menor riesgo de caída (20%).

La **puntuación técnica** empieza en 50 y suma o resta puntos según reglas clásicas y transparentes:

- **Tendencia de fondo**: precio por encima/debajo de su media de 200 sesiones (±15).
- **Cruce de medias** 50/200, "cruce dorado" o "de la muerte" (±8).
- **Tendencia a medio plazo**: precio frente a la media de 50 (±5).
- **RSI**: premia comprar caídas dentro de tendencias alcistas y penaliza perseguir subidas (+12 a −10).
- **Impulso MACD** (±8).
- **Noticias** de la empresa (±6) y **ambiente del mercado** (+4 / −6).
- **Analistas** (precio objetivo, ±6), **PER** (±3/−4) y **dividendo** (+2).
- **Riesgo de caída fuerte** del modelo conjunto (+4 / −8), porque sí ha demostrado funcionar.
- El **stop-loss** se coloca a 2 × ATR (movimiento diario típico) y el objetivo al doble de distancia
  (ganas 2 € por cada 1 € que arriesgas).

Todo el código de las reglas está en `bolsa/senales.py` y `bolsa/noticias.py`.

## Lo que hemos aprendido con datos reales (laboratorio, octubre 2026)
Probado con ~130 empresas (2016-2026) e índices con toda su historia, siempre en años que los modelos no
habían visto, **en euros y con las comisiones reales de Bankinter**:

| Pregunta | ¿Se puede predecir? |
|---|---|
| ¿Subirá una acción en 1 o 3 meses? | No (AUC 0,50-0,52: igual que lanzar una moneda) |
| ¿Lo hará mejor que las demás? | Prácticamente no (AUC 0,51) |
| **¿Sufrirá una caída de más del 10 % el próximo mes?** | **Sí (AUC 0,61)**: con riesgo "muy bajo" ocurrió el 7 % de las veces; con "muy alto", el 21 % |

| Cartera mensual (2020-2026, comisiones de Bankinter) | Rentabilidad/año | Peor caída |
|---|---|---|
| **España**: 8 acciones con más momentum (cartera *Dinámica España*) | 20,7 % | -35 % |
| España: las mismas con filtro de mercado | 11,3 % | -35 % |
| **España**: 8 más estables con filtro (cartera *Tranquila España*) | 5,1 % | **-16 %** |
| España: todas a partes iguales (referencia) | 13,1 % | -35 % |
| Internacional: 10 con más momentum (≈5.000 € por empresa) | 28,2 % | -35 % |
| Internacional: 20 con más momentum y filtro | 14,7 % | -25 % |
| Internacional: todas a partes iguales (referencia) | 15,3 % | -34 % |

| Regla de protección (media 200 ± 2 %) | Sin regla | Con regla |
|---|---|---|
| IBEX 35 (1994-2026) | 5,3 %/año, peor caída -63 % | 6,7 %/año, peor caída -37 % |
| S&P 500 (1928-2026) | 6,2 %/año, peor caída -86 % | 7,0 %/año, peor caída -53 % |

Conclusiones que aplica la app: no presume de adivinar subidas; usa el **riesgo de caída** para evitar sustos;
propone **carteras modelo españolas** (en Bankinter, las extranjeras pagan 20 € por operación, un 1 % de divisa y
custodia) y un **fondo indexado** para el grueso del dinero. Cuidado: el universo son las grandes empresas de hoy
(sesgo de supervivencia) y 2020-2026 es un único periodo; ninguna opción gana a la vez más y con menos riesgo
siempre.

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

## Actualización diaria automática (GitHub Actions)
`.github/workflows/actualizar.yml` se ejecuta solo de lunes a viernes a las 22:15 UTC (tras el cierre de Wall
Street) y los sábados (reentrenamiento semanal de la estrategia). Ejecuta `scripts/actualizar.py`, que:

1. Descarga 10 años de unas 130 empresas, los índices (IBEX desde 1993, S&P 500 desde 1927) y las noticias.
2. Reentrena el **modelo conjunto** con todas las empresas y lo valida año a año sin mirar el futuro.
3. Puntúa cada valor, elige las **ideas del día** y calcula fases de mercado y escenarios.
4. Guarda `informe/informe.json` en el repositorio (la app lo lee al instante) y archiva las ideas y el tono de
   las noticias para medir su **acierto real** con el paso del tiempo.

Puedes lanzarla a mano en GitHub → *Actions* → *Actualización diaria* → *Run workflow*. Cada ejecución tarda
unos 2-3 minutos (≈60 minutos al mes, muy por debajo de los 2.000 gratuitos de un repositorio privado). Si un día
falla (por ejemplo, Yahoo no responde), la app sigue mostrando el último informe y avisa de su antigüedad, y
GitHub te envía un correo.

**Avisos al móvil por Telegram (opcional):** crea un bot con @BotFather y añade en GitHub → *Settings →
Secrets and variables → Actions* los secretos `TELEGRAM_TOKEN` y `TELEGRAM_CHAT_ID`. Si además añades
`GIST_TOKEN` y `GIST_ID` (los mismos del guardado en la nube), el mensaje diario incluirá avisos de tu cartera
de Bankinter (stop tocado, subir stop, tendencia rota...).

**Laboratorio** (`.github/workflows/experimentos.yml`, mensual o a mano): compara con datos reales qué se puede
predecir (subidas, hacerlo mejor que las demás, caídas fuertes) y qué carteras funcionan; los resultados se ven
en la app (🧪 Simulador y modelos).

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

- **Órdenes listas para copiar**, con los tipos de orden de Bankinter: compra **limitada**; protección con orden
  **Stop** (condición «menor o igual que» + **precio límite**, que Bankinter exige), **stop relacionadas**
  (stop-loss y objetivo a la vez; al ejecutarse una se cancela la otra) o **stop dinámica**. Recuerda que en
  Bankinter las órdenes stop no se modifican: para cambiarlas, cancela y crea otra.
- **Costes reales** (tarifa pública, oct. 2026; ajustable en la barra lateral): España 3,95 € (≤2.000 €) u 8 €
  (≤60.000 €) por operación, 0 € con Bróker Cero, más cánones de bolsa (~1 €, aproximado) y tasa Tobin del 0,2 %;
  extranjeras 20 € por operación, ±1 % de cambio de divisa y custodia de 0,05 % trimestral (mínimo 6 € por valor).
- **Importes en euros**: los precios se muestran en la divisa del valor (como en Bankinter) y los importes, en euros
  con el tipo de cambio del día.
- **Tu cartera**: la registras a mano o la importas de una hoja de cálculo; la app la vigila cada día y te avisa
  (también por Telegram si lo activas).

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
