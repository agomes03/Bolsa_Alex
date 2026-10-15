# 📈 Asistente de Bolsa para principiantes

Una app sencilla (en español) que te ayuda a invertir en bolsa con el **broker de Bankinter**:

| Sección | Qué hace |
|---|---|
| 🧭 **Hoy** | Pantalla de inicio: semáforo del mercado, resumen en pocas palabras, **ideas del día** (diversificadas por sector), **qué puede pasar** según la historia de los índices, noticias clave y avisos de tu cartera. Abre al instante porque usa el informe diario. |
| 🎯 **Mi plan** | Asesor: 6 preguntas → tu perfil (conservador, moderado o dinámico) y un **reparto concreto en euros** (monetario/Letras, bonos, ETF mundial y unas pocas acciones), con órdenes para Bankinter, escenarios a 1 año y pruebas de estrés en crisis reales. |
| 🔍 **Analizar** | Puntuación de 0 a 100 explicada, modelo conjunto, predicción por situaciones parecidas, plan con stop-loss y tamaño de posición, qué le puede pasar a tu dinero, datos de la empresa, analistas y noticias. |
| 📡 **Radar** | Todas las empresas (IBEX, Continuo, Europa, EEUU, ETF) ordenadas por puntuación, con filtros. Toca una fila para analizarla. |
| 📰 **Noticias** | 19 fuentes en español e inglés, ordenadas por impacto y explicadas. |
| 🌍 **Mercados** | Índices, termómetros (VIX, euro/dólar, petróleo), fase de cada mercado con estadísticas desde los años 90 y peores caídas de la historia. |
| 🏦 **Mi Bankinter** | Copiloto de tu broker: importa o registra tus posiciones, la app las vigila, te avisa y te prepara las órdenes; además, qué le puede pasar a tu cartera. |
| 🎮 **Cartera virtual** | Practica con dinero ficticio y crea un robot que opera solo desde hoy. |
| 🧪 **Simulador y modelos** | Resultados diarios con todas las empresas, acierto real de las ideas pasadas, laboratorio de experimentos, y simulación/entrenamiento propios. |
| 🧮 **Calculadoras** · 🎓 **Aprende** | Costes, impuestos, interés compuesto y lo básico explicado fácil. |

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

## Lo que hemos aprendido con datos reales (laboratorio, octubre 2026)
Probado con ~130 empresas (2016-2026) e índices con toda su historia, siempre en años que los modelos no
habían visto y con comisiones incluidas:

| Pregunta | ¿Se puede predecir? |
|---|---|
| ¿Subirá una acción en 1 o 3 meses? | No (AUC 0,50-0,52: igual que lanzar una moneda) |
| ¿Lo hará mejor que las demás? | Prácticamente no (AUC 0,51) |
| **¿Sufrirá una caída de más del 10% el próximo mes?** | **Sí (AUC 0,61)**: con riesgo "muy bajo" ocurrió el 7% de las veces; con "muy alto", el 21% |

| Estrategia (2020-2026, años no vistos) | Rentabilidad/año | Peor caída |
|---|---|---|
| Momentum 12-1, 10 acciones, rotación mensual | 27,9% | -37% |
| Momentum 12-1, 20 acciones, con filtro de mercado | 14,4% | -28% |
| Baja volatilidad, 20 acciones, con filtro de mercado | 7,9% | **-14%** |
| Todas las acciones a partes iguales | 7,5% | -28% |
| Reglas de compra/venta diarias con stop-loss (entrenadas) | 4,2% | -19% |

| Regla de protección (media 200 ± 2%) | Sin regla | Con regla |
|---|---|---|
| IBEX 35 (1994-2026) | 5,3%/año, peor caída -63% | 6,7%/año, peor caída -37% |
| S&P 500 (1928-2026) | 6,2%/año, peor caída -86% | 7,0%/año, peor caída -53% |

Por eso la app se apoya en el **riesgo de caída** (para evitar sustos), en **carteras modelo de rotación mensual**
y en la **regla de protección** para los fondos indexados, y no presume de adivinar si una acción subirá.
Cuidado: el universo son las grandes empresas de hoy (sesgo de supervivencia), lo que favorece al momentum.

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

Puedes lanzarla a mano en GitHub → *Actions* → *Actualización diaria* → *Run workflow*. Consume unos pocos
minutos al día del cupo gratuito de GitHub Actions.

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
