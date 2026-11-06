# Caso causal BTC — caída del 5 de febrero de 2026

**Estado:** investigación iniciada; hipótesis preliminares, no conclusión causal.  
**Activo:** Bitcoin (BTC).  
**Ventana del episodio:** 2026-02-03 a 2026-02-08 (UTC), con contexto ampliado desde 2026-01-20.  
**Mercados primarios previstos:** Binance Spot BTCUSDT y Kraken Spot XBT/USD.  
**Fecha de diseño:** 2026-11-06.

## 1. Pregunta de investigación

¿Qué combinación de factores explica la aceleración bajista de BTC observada el 5 de febrero de 2026, y qué parte del movimiento fue amplificada por liquidaciones de posiciones apalancadas?

No se buscará una única noticia que coincida con la caída. Se separarán:

1. **Catalizadores externos:** noticias macroeconómicas, decisiones y expectativas de política monetaria, movimientos de otros mercados y acontecimientos geopolíticos.
2. **Flujos de demanda spot:** flujos de ETF, demanda institucional, ventas de tesorerías corporativas y actividad de compradores/vendedores spot.
3. **Mecanismos de amplificación:** liquidaciones forzosas, caída de open interest, profundidad y desequilibrio del libro de órdenes.
4. **Condiciones previas:** tendencia bajista, liquidez, posicionamiento, volatilidad y niveles técnicos ya debilitados.

## 2. Justificación de selección

El episodio cae dentro de la ventana diaria ya cubierta por la PoC del proyecto (2025-11-21 a 2026-11-06). Fuentes contemporáneas describieron el 5 de febrero como una caída excepcional:

- Reuters informó de una caída diaria del 12,6 % hasta aproximadamente 63.525 USD en una de sus referencias de mercado, además de liquidaciones y debilidad simultánea en tecnología y metales preciosos.
- Bitwise describió un movimiento desde un máximo de sesión cercano a 73.000 USD hasta un mínimo aproximado de 60.200 USD, con un descenso diario de alrededor del 14 % según su serie.
- The Block informó de liquidaciones superiores a 1.000 millones USD en el mercado cripto, con predominio de posiciones largas, y de debilidad de la demanda spot.

Las diferencias de precio y porcentaje entre publicaciones no se tratarán como contradicciones automáticamente: pueden proceder de venue, zona horaria, ventana de cálculo, máximo/mínimo intradía o metodología distintos. La serie de Binance y la de Kraken deberán cuantificar el episodio por separado.

## 3. Hipótesis competidoras

| ID | Hipótesis | Mecanismo propuesto | Evidencia necesaria para evaluarla |
|---|---|---|---|
| H1 | Reprecio macroeconómico y aversión al riesgo | Expectativas sobre la futura dirección de la Reserva Federal, debilidad de tecnología y volatilidad en otros activos reducen exposición a riesgo | Cronología exacta de noticias; retornos de Nasdaq/S&P, dólar, rendimientos y metales; sincronía de BTC con activos de riesgo |
| H2 | Retirada de demanda institucional | Salidas de ETF y menor absorción spot dejan el mercado sin compradores suficientes | Flujos diarios por ETF, volumen spot, delta comprador/vendedor y comportamiento previo al episodio |
| H3 | Desapalancamiento como amplificador | La ruptura de niveles activa liquidaciones de posiciones largas, que generan ventas forzosas y aceleran la caída | Liquidaciones por hora y dirección, open interest, funding, basis y secuencia temporal respecto al precio |
| H4 | Distribución y debilidad estructural previas | Ventas persistentes y pérdidas realizadas debilitan la estructura antes del día extremo | Flujos on-chain con metodología identificada, métricas de holders, volumen spot y tendencia de varias semanas |

**Regla de interpretación:** H3 describe un mecanismo de amplificación y no demuestra por sí sola el origen del movimiento. H1 y H2 pueden coexistir. Ninguna hipótesis será aceptada solo porque un artículo o analista la haya propuesto.

## 4. Evidencia pública localizada inicialmente

| Evidencia | Observación publicada | Uso en la investigación | Limitación |
|---|---|---|---|
| Reuters, 2026-02-05 | Caída de BTC, liquidaciones, debilidad tecnológica y volatilidad en metales; se mencionan expectativas sobre el candidato a presidir la Fed y salidas de ETF | Construir la cronología de catalizadores y contexto cross-asset | Artículo periodístico; no sustituye las series primarias ni prueba causalidad |
| The Block, 2026-02-05 | Más de 1.000 millones USD en liquidaciones cripto; presión en posiciones largas, debilidad spot y salidas institucionales | Evaluar desapalancamiento y demanda | Las liquidaciones agregadas dependen de cobertura y metodología del proveedor |
| Bitwise, 2026-02-06 | BTC desde aproximadamente 73.000 USD hasta 60.200 USD; caída cercana al 14 % | Delimitar magnitud aproximada y contrastar con OHLCV | Serie y metodología de Bitwise/Glassnode; no equiparar sin más a Binance o Kraken |
| The Block, 2026-02-05 | Se informa de salidas de ETF en sesiones previas, incluida una salida de 544,9 millones USD el 4 de febrero según sus datos | Contrastar el papel de flujos institucionales | Requiere validar el dato diario con una segunda fuente y distinguir fecha de negociación/fecha de publicación |

### Referencias

- Reuters: https://www.reuters.com/business/bitcoin-slumps-with-key-70000-level-sight-2026-02-05/
- Reuters, versión sindicada con más detalle: https://finance.yahoo.com/news/bitcoin-drops-driving-2-trillion-180917395.html
- The Block, demanda spot, liquidaciones y flujos: https://www.theblock.co/news/markets/2026-02-05-bears-in-control-bitcoin-erases-gains-since-2021-all-time-high-as-price-drops-back-toward-69k
- The Block, episodio intradía y liquidaciones: https://www.theblock.co/news/markets/2026-02-05-bitcoin-sees-flash-crash-60000-388759
- Bitwise, análisis del flash crash: https://bitwiseinvestments.eu/blog/crypto-research/2026-02-06-Flash-Crash-Market-Update/
- Bloomberg, contexto de ventas cross-asset: https://www.bloomberg.com/news/articles/2026-02-05/wall-street-s-favorite-trades-collapse-as-market-selloff-deepens

## 5. Diseño de datos para la reconstrucción

### 5.1 Mercado spot

| Fuente | Instrumento | Granularidad | Uso |
|---|---|---|---|
| Binance Spot | BTCUSDT | 1m, 5m y 1h; 1d para contexto | OHLCV, volumen cotizado USDT, número de operaciones y taker-buy |
| Kraken Spot | XBT/USD | 1m/5m/1h si el archivo histórico lo permite; 1d | Contraste independiente de precio y actividad del venue |

- Ventana de alta resolución: 2026-02-04T00:00:00Z a 2026-02-07T00:00:00Z.
- Contexto diario: 2026-01-20T00:00:00Z a 2026-02-09T00:00:00Z.
- Los retornos se calcularán por venue; no se compararán directamente precios BTCUSDT y XBT/USD como si USDT fuera USD.
- Se alinearán timestamps UTC y se documentará la semántica de apertura/cierre de cada vela.
- Kraken REST OHLC está limitado a 720 observaciones; no se utilizará como si permitiera paginar libremente el episodio intradía. Se evaluará el archivo histórico OHLCVT oficial y se documentará su granularidad real.

### 5.2 Variables externas y de derivados

| Variable | Fuente candidata | Resolución mínima | Motivo |
|---|---|---|---|
| Nasdaq 100 / S&P 500 | Fuente histórica financiera con licencia adecuada | 5m/1h | Medir si BTC se movió junto con activos de riesgo |
| DXY y rendimientos del Tesoro | Fuente macroeconómica documentada | 5m/1h o diaria, según disponibilidad | Contrastar el canal de liquidez y dólar |
| Flujos de ETF spot BTC | Publicaciones de emisores y agregador con metodología explícita | Diaria | Medir demanda institucional; no confundir flujos de ETF con compras spot instantáneas |
| Open interest y funding BTC | Exchange de derivados o proveedor histórico | 5m/1h | Detectar reducción de apalancamiento y cambios de posicionamiento |
| Liquidaciones largas/cortas | Fuente de derivados con cobertura documentada | 1m/5m/1h | Cuantificar ventas forzosas y su sincronía con la caída |
| Noticias y comunicados | Fuentes oficiales, medios con hora de publicación y archivos verificables | Timestamp original | Identificar catalizadores y evitar asignar al mercado noticias publicadas después del movimiento |

No se incorporará una variable solo porque esté disponible. Se registrarán proveedor, definición, unidad, zona horaria, hora de publicación, hora de captura, revisiones y licencia.

## 6. Método de análisis

1. Reconstruir retornos y volumen por venue, con ventanas móviles de 5m, 1h y 1d.
2. Identificar el inicio de la aceleración, máximos/mínimos locales y cambios de volatilidad sin fijarlos a partir de los titulares.
3. Construir una cronología de noticias con published_at, event_at cuando sea distinto, captured_at y URL de fuente.
4. Alinear BTC con índices tecnológicos, dólar, rendimientos, metales y ETH.
5. Medir si liquidaciones y caída de open interest preceden, coinciden o siguen a los tramos más intensos de caída.
6. Contrastar flujos ETF de los días previos y posteriores; respetar que los datos de ETF suelen ser diarios y no explican por sí solos el minuto exacto del movimiento.
7. Comparar las hipótesis y registrar evidencia a favor, en contra, ausente y explicaciones alternativas.
8. Ejecutar pruebas de robustez: diferentes venues, ventanas temporales, frecuencia y exclusión de observaciones anómalas.

### Criterio mínimo para hablar de causalidad

- La causa propuesta debe preceder al movimiento en la resolución temporal relevante.
- Debe existir un mecanismo económico plausible y evidencia independiente.
- La relación debe persistir al controlar, en la medida posible, factores comunes y variables concurrentes.
- Deben documentarse hipótesis alternativas y datos faltantes.
- Si solo existe coincidencia temporal o interpretación periodística, el resultado será **asociación/hipótesis**, no causalidad demostrada.

## 7. Estado actual y límites

- [x] Seleccionar un episodio dentro de la ventana histórica diaria del proyecto.
- [x] Localizar fuentes públicas iniciales y formular hipótesis competidoras.
- [x] Definir ventanas de reconstrucción y variables a contrastar.
- [ ] Recuperar y analizar OHLCV diario de Binance y Kraken para el periodo de contexto.
- [ ] Recuperar velas intradía de Binance y el archivo histórico intradía de Kraken.
- [ ] Obtener series verificables de derivados, ETF y mercados macro.
- [ ] Construir cronología de eventos con timestamps originales.
- [ ] Calcular métricas del episodio y contrastar hipótesis.
- [ ] Publicar un informe de resultados con evidencia y nivel de confianza.

**Conclusión provisional:** las fuentes públicas apuntan a un episodio multifactorial: aversión al riesgo en mercados globales, debilitamiento de la demanda institucional y desapalancamiento. La información disponible no permite todavía determinar qué factor inició el movimiento, cuál tuvo mayor contribución ni si las liquidaciones fueron causa inicial o amplificador. Esa respuesta queda condicionada a la reconstrucción temporal con datos de mercado y derivados.

## 8. Restricciones de publicación

Este caso es parte de investigación privada. El repositorio GitHub es público, por lo que no se deben añadir payloads, series descargadas, datos licenciados ni derivados cuya publicación no esté autorizada. El repositorio puede contener metodología, hashes, metadatos técnicos no sensibles y conclusiones cuya publicación esté permitida. Los artefactos de análisis deberán permanecer en almacenamiento privado conforme a las condiciones de cada proveedor.
