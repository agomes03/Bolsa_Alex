# 📈 Asistente de Bolsa para principiantes

Una app sencilla (en español) que te ayuda a invertir en bolsa con el **broker de Bankinter**:

| Sección | Qué hace |
|---|---|
| 🏠 **Resumen del día** | IBEX 35, Euro Stoxx 50, DAX, S&P 500 y Nasdaq, VIX, euro/dólar y petróleo, más un **semáforo** (verde / ámbar / rojo) que dice si es buen momento para invertir. |
| 📰 **Noticias** | Junta las últimas noticias de Expansión, elEconomista, Cinco Días, Investing y Google News. Las ordena por **impacto** (tipos de interés, BCE/Fed, inflación, aranceles, resultados, OPAs...), dice si son **positivas o negativas** y te explica **por qué importan**. |
| 🔍 **Analizar una acción** | Da una puntuación de 0 a 100 y un veredicto (*Zona de compra*, *Compra escalonada*, *Esperar*, *Evitar*), explicando cada motivo. Te propone un **plan**: precio de compra, **stop-loss**, objetivo y **cuántas acciones comprar** según el dinero que quieras arriesgar. Incluye los pasos para hacerlo en la app de Bankinter. |
| 📡 **Radar del IBEX 35** | Analiza las 35 empresas a la vez y las ordena por puntuación. |
| 🧮 **Calculadoras** | Comisiones + Impuesto de Transacciones Financieras, IRPF al vender, e interés compuesto invirtiendo cada mes. |
| 🎓 **Aprende** | Lo básico explicado fácil: diccionario, reglas de oro y calendario de eventos. **Empieza por aquí.** |

> ⚠️ **Es una herramienta educativa, no asesoramiento financiero.** Ningún programa puede garantizar
> beneficios ni adivinar el futuro. Lo que sí hace es ayudarte a no comprar en mal momento, a tener
> siempre un plan con stop-loss, y a entender lo que haces.

## Cómo instalarla (una sola vez)

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

### Usarla desde el móvil (gratis)
Puedes publicarla en **Streamlit Community Cloud** (<https://share.streamlit.io>): inicia sesión con
GitHub, pulsa *New app*, elige este repositorio y el archivo `app.py`. Te dará un enlace que puedes
abrir desde el móvil, al lado de la app de Bankinter.

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
- El **stop-loss** se coloca a 2 × ATR (movimiento diario típico) y el objetivo al doble de distancia
  (ganas 2 € por cada 1 € que arriesgas).

Todo el código de las reglas está en `bolsa/senales.py` y `bolsa/noticias.py`.

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
