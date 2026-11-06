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
- Binance Public Data (documentación oficial del archivo): https://github.com/binance/binance-public-data
- Binance USDⓈ-M Futures, estadísticas históricas de open interest: https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Open-Interest-Statistics
- Binance USDⓈ-M Futures, historial de funding: https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Get-Funding-Rate-History

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
- [x] Contrastar OHLCV diario de Binance y Kraken para el periodo de contexto.
- [ ] Recuperar velas intradía de Binance y el archivo histórico intradía de Kraken.
- [ ] Obtener series verificables de derivados, ETF y mercados macro.
- [ ] Construir cronología de eventos con timestamps originales.
- [ ] Calcular métricas del episodio y contrastar hipótesis.
- [ ] Publicar un informe de resultados con evidencia y nivel de confianza.

**Conclusión provisional:** las fuentes públicas apuntan a un episodio multifactorial: aversión al riesgo en mercados globales, debilitamiento de la demanda institucional y desapalancamiento. La información disponible no permite todavía determinar qué factor inició el movimiento, cuál tuvo mayor contribución ni si las liquidaciones fueron causa inicial o amplificador. Esa respuesta queda condicionada a la reconstrucción temporal con datos de mercado y derivados.

## 8. Restricciones de publicación

Este caso es parte de investigación privada. El repositorio GitHub es público, por lo que no se deben añadir payloads, series descargadas, datos licenciados ni derivados cuya publicación no esté autorizada. El repositorio puede contener metodología, hashes, metadatos técnicos no sensibles y conclusiones cuya publicación esté permitida. Los artefactos de análisis deberán permanecer en almacenamiento privado conforme a las condiciones de cada proveedor.

## 9. Primera comprobación empírica con el artefacto Run #13

Se inspeccionó el artefacto histórico de la PoC, que contiene OHLCV diario BTC de Binance Spot (BTCUSDT) y Kraken Spot (XBT/USD). La ventana diaria cubre el episodio de febrero; la ventana horaria de ese artefacto comienza el 7 de octubre de 2026, por lo que **no contiene velas horarias del episodio de febrero**.

La primera lectura confirma que ambos venues registran el mismo patrón general: deterioro antes del episodio, una sesión UTC de venta extrema y una sesión UTC posterior de rebote violento. El volumen diario del día de caída es varias veces superior a la mediana de las sesiones de contexto anteriores en ambos venues. Esto confirma que el episodio fue excepcional en actividad y volatilidad, pero no identifica por sí solo el catalizador.

### Precaución crítica de zona horaria

La cobertura de velas está alineada a días UTC. Los titulares periodísticos etiquetados como 5 de febrero en Estados Unidos describen también movimientos ocurridos durante la tarde/noche de Nueva York, que pueden caer ya en la vela del **6 de febrero UTC**. Por tanto, no se debe comparar la fecha del titular con la fecha de la vela sin normalizar ambos timestamps a UTC.

Esta diferencia explica por qué un artículo puede reportar el mínimo cercano a 60.000 USD en el episodio del 5 de febrero local, mientras que la vela diaria UTC que contiene ese mínimo corresponde al 6 de febrero. Para el análisis causal se conservarán por separado:
- timestamp original y zona horaria del artículo;
- hora de publicación y, si es distinta, hora del acontecimiento;
- apertura/cierre UTC de la vela;
- venue y par de negociación.

### Resultado de esta fase

- [x] Contrastar la forma general del episodio en Binance y Kraken con datos OHLCV diarios.
- [x] Confirmar que la actividad y el rango del episodio fueron extraordinarios respecto a las sesiones de contexto.
- [x] Detectar la desalineación potencial entre fechas locales de los titulares y días UTC de las velas.
- [ ] Recuperar granularidad de 1m/5m/1h para 2026-02-04 a 2026-02-07 en ambos venues.
- [ ] Construir cronología intradía con liquidaciones, open interest, flujos y acontecimientos macro.

**Conclusión empírica limitada:** la caída no es un artefacto de un único exchange: Binance y Kraken reflejan un episodio concordante. El OHLCV diario no permite determinar el orden intradía entre noticias, presión spot y liquidaciones. Hasta obtener esa resolución, no se asignará causalidad ni se jerarquizarán H1–H4.

### Restricción de datos

Los valores OHLCV y las métricas calculadas a partir de ellos no se reproducen en este documento público. El artefacto histórico se utilizó para análisis interno; la política de publicación del proyecto exige mantener fuera del repositorio público los valores de mercado cuya redistribución no esté autorizada.

## 10. Auditoría de disponibilidad histórica de datos intradía y derivados

Se revisó la documentación oficial disponible de Binance para evitar depender de endpoints que ya no conservan el periodo investigado.

### Binance Spot: OHLCV histórico

Binance documenta un archivo público de klines por símbolo, intervalo y mes. Para BTCUSDT, las rutas mensuales oficiales siguen el patrón:

- `https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1m/BTCUSDT-1m-2026-02.zip`
- `https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/5m/BTCUSDT-5m-2026-02.zip`
- `https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1h/BTCUSDT-1h-2026-02.zip`

La documentación oficial confirma que el archivo ofrece klines Spot en múltiples intervalos y archivos ZIP con checksum acompañante. Desde 2025-01-01, los timestamps de Spot están expresados en microsegundos, detalle que debe manejar el parser. La existencia del mecanismo oficial está documentada; **la descarga de estos ZIP no se completó en este entorno**, cuyo runtime no pudo resolver el dominio externo. No se declarará que los archivos fueron recuperados hasta validar su descarga y checksum.

### Binance USDⓈ-M Futures: límite crítico de open interest

La documentación oficial del endpoint `/futures/data/openInterestHist` indica que solo conserva estadísticas del último mes, aunque permite periodos de 5m a 1d y un máximo de 500 registros por consulta. A fecha de esta auditoría (2026-11-06), ese endpoint no puede devolver febrero de 2026. Por tanto:

- No usaremos una consulta actual de ese endpoint para inferir el open interest del episodio de febrero.
- La serie histórica de OI deberá proceder de un archivo histórico independiente o proveedor que demuestre cobertura de esa fecha.
- Si no aparece una fuente con cobertura verificable, H3 quedará parcialmente no identificada; no se sustituirá OI histórico por estimaciones retrospectivas sin metodología.

### Funding y liquidaciones

El historial de funding tiene un endpoint separado (`/fapi/v1/fundingRate`), pero antes de usarlo se comprobarán cobertura efectiva, paginación y disponibilidad del intervalo de febrero. No se inferirá que funding y open interest comparten la misma retención.

El endpoint de liquidaciones/force orders no se considerará un archivo histórico completo. Se necesitará documentar su alcance temporal, autenticación, límites y sesgo de cobertura antes de tratar sus resultados como el total de liquidaciones del mercado.

### Resultado de la auditoría de fuentes

- [x] Identificar el archivo oficial de Binance Spot para reconstrucción 1m/5m/1h.
- [x] Identificar el cambio de unidad temporal de milisegundos a microsegundos para Spot desde 2025.
- [x] Confirmar que el endpoint oficial de estadísticas de OI de USDⓈ-M Futures solo ofrece el último mes.
- [ ] Descargar y verificar los ZIP Spot de febrero de 2026.
- [ ] Descargar y validar el archivo OHLCVT histórico de Kraken para Q1 2026.
- [ ] Validar cobertura histórica real de funding y liquidaciones.
- [ ] Encontrar una fuente histórica independiente de OI para febrero de 2026, o declarar explícitamente que no está disponible.

**Implicación metodológica:** el precio y el volumen spot se pueden reconstruir con archivos históricos oficiales; el OI intradía de febrero no se puede recuperar mediante el endpoint público actual de estadísticas de Binance. Esta asimetría debe reflejarse en el nivel de confianza de cualquier conclusión sobre liquidaciones y desapalancamiento.


## 11. Cronología preliminar de catalizadores y flujos (revisión 2026-11-06)

Esta sección corrige una simplificación de la hipótesis macro y separa timestamps de publicación, fechas de negociación y ventanas de mercado.

### 11.1 Kevin Warsh: catalizador anterior, no noticia del 5 de febrero

La elección de Kevin Warsh como candidato de Trump a presidir la Reserva Federal se anunció el **30 de enero de 2026**, no el 5 de febrero. Reuters informó ese día de fortalecimiento del dólar, caídas de bolsas y una lectura de inflación mayorista superior a lo esperado. Bloomberg describió una reacción de alivio relativo en dólar y Treasuries ante la percepción de que Warsh sería menos proclive a una flexibilización monetaria agresiva que otros candidatos considerados.

Por tanto, la nominación puede formar parte del contexto de repricing iniciado el 30 de enero, pero no debe etiquetarse como un titular nuevo que desencadenó por sí solo la caída del 5 de febrero. La hipótesis que debe probarse es si el cambio de expectativas del 30 de enero tuvo efectos persistentes y cómo interactuó con otros shocks posteriores.

### 11.2 Flujos diarios de ETF spot BTC

Una serie diaria pública que atribuye sus datos a Farside Investors informa estos flujos netos agregados de ETF spot estadounidenses:

| Fecha de negociación | Flujo neto agregado |
|---|---:|
| 2026-02-02 | +561,8 millones USD |
| 2026-02-03 | −272,0 millones USD |
| 2026-02-04 | −544,9 millones USD |
| 2026-02-05 | −434,1 millones USD |
| 2026-02-06 | +371,1 millones USD |

La suma de los días 3 a 5 de febrero es −1.251,0 millones USD; el 2 de febrero había registrado una entrada de +561,8 millones USD. La secuencia muestra un cambio brusco desde entradas a salidas durante tres sesiones consecutivas, seguido de una entrada el 6 de febrero.

**Límite de inferencia:** estos son flujos diarios asociados a fechas de negociación estadounidenses, no observaciones intradía. No permiten establecer si las órdenes de reembolso precedieron al tramo de caída del 5 de febrero, ni si los flujos fueron causa, respuesta o ambas cosas. Las páginas de terceros consultadas reproducen una serie atribuida a Farside; no se contarán como verificaciones independientes entre sí. Antes de elevar estos valores a evidencia primaria se archivará y comprobará la tabla original de Farside, su zona horaria y sus revisiones.

### 11.3 Secuencia intradía publicada el 5 de febrero

La prensa financiera permite fijar algunos hitos provisionales en hora de Nueva York (ET):

| Hora ET / fecha | Hito publicado | Qué permite afirmar |
|---|---|---|
| 5 feb., 06:36 | CoinDesk informa que BTC había caído por debajo de 70.000 USD antes de la apertura de la bolsa estadounidense | La debilidad de BTC ya estaba presente antes de la sesión regular de acciones |
| 5 feb., mañana | Se publican datos laborales estadounidenses: solicitudes iniciales de desempleo mayores de lo esperado y vacantes JOLTS en mínimo de más de cinco años | Hubo información macro durante la mañana; falta medir su impacto incremental en BTC |
| 5 feb., 15:00 | CoinDesk publica BTC cerca de 63.000 USD y pérdidas simultáneas en metales y activos tecnológicos | La venta continuaba durante la sesión estadounidense |
| 5 feb., 19:20 | The Block informa un mínimo aproximado de 60.000 USD | La fase extrema se produjo después del cierre regular de la bolsa estadounidense |
| 5 feb., 21:07 | The Block publica liquidaciones cripto de 2.670 millones USD en 24 horas, de las cuales 2.310 millones correspondían a posiciones largas según CoinGlass | Confirma desapalancamiento masivo en la ventana reportada, pero el agregado de 24h no demuestra que las liquidaciones precedieran al primer tramo bajista |

Los tiempos de los artículos son timestamps de publicación o tiempos del acontecimiento citados por los periodistas; no equivalen a una cinta consolidada de operaciones. Se deben convertir a UTC y contrastar con las velas 1m/5m cuando estén disponibles.

### 11.4 Lectura causal provisional

La evidencia disponible obliga a separar tres fases:

1. **Reprecio previo (30 de enero–4 de febrero):** nominación de Warsh, inflación mayorista, debilidad de metales y salidas de ETF durante el 3 y 4 de febrero. Es contexto potencialmente predisponente, no explicación suficiente.
2. **Deterioro previo a la apertura estadounidense (madrugada–mañana del 5 de febrero ET):** BTC ya estaba por debajo de 70.000 USD antes de la apertura bursátil. Esto impide explicar el inicio de la jornada únicamente por la caída de las acciones estadounidenses durante esa sesión.
3. **Aceleración y liquidaciones (tarde/noche del 5 de febrero ET):** BTC cayó hacia 60.000 USD y las liquidaciones largas dominaron el agregado reportado. Esto es consistente con liquidaciones como amplificador; no prueba que fueran el detonante inicial.

La caída de acciones tecnológicas, el deterioro de metales y los datos laborales contribuyen al contexto de aversión al riesgo. Sin embargo, para establecer qué variable lideró cada tramo se necesitan series intradía sincronizadas, no solo cierres diarios ni titulares.

### Fuentes consultadas para esta cronología

- Reuters, 30-01-2026, nominación de Warsh y reacción de mercados: https://www.reuters.com/world/china/global-markets-global-markets-2026-01-30/
- Bloomberg, 30-01-2026, reacción de dólar y Treasuries: https://www.bloomberg.com/news/articles/2026-01-30/treasury-yields-rise-on-expectations-warsh-will-be-fed-chair
- CoinDesk, 05-02-2026, BTC por debajo de 70.000 USD antes de la apertura estadounidense: https://www.coindesk.com/markets/2026/02/05/bitcoin-drops-below-usd70-000-as-crypto-selloff-deepens-before-u-s-equity-market-opens
- Reuters, 05-02-2026, solicitudes de desempleo y vacantes laborales: https://www.investing.com/news/economic-indicators/us-weekly-jobless-claims-increase-more-than-expected-4487844
- New York Fed, calendario de indicadores de febrero de 2026: https://www.newyorkfed.org/research/calendars/i-feb26.html
- CoinDesk, 05-02-2026, BTC cerca de 63.000 USD y venta cross-asset: https://www.coindesk.com/markets/2026/02/05/bitcoin-drops-below-usd65-000-heading-to-worst-one-day-drawdown-since-ftx-blowup
- The Block, 05-02-2026, mínimo cercano a 60.000 USD y liquidaciones: https://www.theblock.co/news/markets/2026-02-05-bitcoin-sees-flash-crash-60000-388759
- ETF flows (serie pública que atribuye los datos a Farside Investors): https://newhedge.dev/bitcoin/spot-bitcoin-etf-flows

### Estado de hipótesis tras esta revisión

- **H1, repricing macro / risk-off:** gana plausibilidad como condición de contexto desde el 30 de enero y durante el 5 de febrero; todavía no se identifica el impulso marginal que inicia la caída intradía.
- **H2, retirada de demanda institucional:** gana apoyo descriptivo por los flujos negativos del 3 al 5 de febrero; causalidad y orden temporal intradía siguen sin identificarse.
- **H3, desapalancamiento:** existe evidencia pública de liquidaciones largas muy elevadas en la fase extrema; sigue sin demostrarse si las liquidaciones precedieron al inicio del descenso o amplificaron una caída ya en marcha.
- **H4, debilidad estructural previa:** sigue siendo consistente con la caída acumulada desde finales de enero, pero requiere métricas de mercado/on-chain adicionales.

**Conclusión:** el episodio no se explica adecuadamente con la frase «la nominación de Warsh provocó la caída del 5 de febrero». La lectura más defendible hoy es un mercado ya debilitado y sometido a repricing y salidas de ETF, seguido por una venta que se aceleró y desencadenó liquidaciones largas masivas. La identificación del detonante inmediato permanece abierta.


## 12. Especificación de microestructura para medir presión spot (revisión 2026-11-06)

La documentación oficial del repositorio `binance-public-data` permite precisar qué variable puede extraerse del archivo histórico Spot, sin confundir volumen bruto con presión vendedora.

### 12.1 Campos utilizables en klines Spot

Las velas Spot de Binance contienen, además de OHLCV y número de operaciones:

- `taker buy base asset volume`: volumen BTC de operaciones cuyo comprador fue el taker/agresor.
- `taker buy quote asset volume`: valor cotizado de esas compras agresoras, en USDT para BTCUSDT.

A partir de esos campos se pueden construir, por intervalo:

```text
taker_sell_base = total_base_volume - taker_buy_base_volume
taker_delta_base = taker_buy_base_volume - taker_sell_base
taker_imbalance = taker_delta_base / total_base_volume
```

Se calcularán también las versiones en quote volume para evitar interpretar cantidades BTC como valor monetario. Los resultados se agregarán a 1m, 5m y 1h, conservando el dato original de 1m.

**Interpretación:** un `taker_imbalance` negativo indica que el volumen ejecutado por vendedores agresores superó al ejecutado por compradores agresores en ese intervalo. Es una aproximación observable a la presión de órdenes de mercado, no una medida completa de flujo de órdenes: no revela órdenes limitadas no ejecutadas, cancelaciones, profundidad ni la identidad económica de los participantes. Tampoco demuestra por sí sola que esa presión haya causado el movimiento.

### 12.2 Comprobación alternativa con aggTrades

El archivo Spot `aggTrades` contiene timestamp, precio, cantidad y el indicador `was the buyer the maker`. Con esa bandera se puede clasificar la agresión de cada operación agregada:

- buyer maker = true: el comprador aportó liquidez; el vendedor fue el agresor.
- buyer maker = false: el comprador fue el agresor.

Se calculará el volumen comprador/vendedor agresor a partir de aggTrades y se contrastará con el residual de taker-buy en klines. Las diferencias se investigarán antes de aceptar la serie: agregación de operaciones, límites temporales, precisión, tratamiento de timestamps y cobertura del archivo.

### 12.3 Protocolo temporal y controles

1. Descargar los archivos oficiales mensuales de BTCUSDT para febrero de 2026, tanto klines 1m como aggTrades, y sus archivos de checksum.
2. Verificar SHA-256 antes de parsear; conservar URL, fecha de descarga, checksum, tamaño, esquema y versión del parser en un manifiesto privado.
3. Convertir los timestamps Spot de microsegundos a UTC; no aplicar la conversión de milisegundos usada por otros conjuntos de Binance.
4. Recortar exactamente 2026-02-04T00:00:00Z a 2026-02-07T00:00:00Z y comprobar continuidad, duplicados, huecos y límites del día.
5. Calcular volumen comprador/vendedor agresor, delta, imbalance, volumen cotizado y número de operaciones por minuto.
6. Identificar si el imbalance vendedor aparece antes del primer tramo de caída, coincide con él o aumenta después de la aceleración.
7. Repetir el cálculo con aggTrades como control de consistencia y comparar precio/volumen con Kraken.

### 12.4 Qué no permite concluir este conjunto

- No identifica al participante ni distingue ventas discrecionales, cobertura, arbitraje o liquidaciones.
- No reconstruye el libro de órdenes histórico ni la liquidez disponible antes de cada operación.
- No prueba causalidad solo porque el imbalance vendedor anteceda a un retorno negativo; se debe contrastar con futuros, mercados macro y eventos fechados.
- Un resultado de Binance no se generalizará automáticamente a todo el mercado. Kraken servirá como contraste independiente de precio y volumen, pero su OHLCVT no debe tratarse como equivalente a la clasificación de agresor de Binance.

### Estado de adquisición

- [x] Verificar en documentación oficial la disponibilidad de klines Spot con campos taker-buy.
- [x] Verificar en documentación oficial el esquema Spot aggTrades y su bandera buyer-maker.
- [x] Definir métricas de presión compradora/vendedora y controles de consistencia.
- [ ] Descargar los archivos de febrero de 2026 y validar checksum.
- [ ] Calcular y revisar las series de imbalance de 1m/5m/1h.

**Estado de evidencia:** esta revisión mejora la especificación de medición, pero todavía no aporta observaciones intradía calculadas. El runtime de esta sesión no pudo resolver el host `data.binance.vision`; por tanto, no se afirma que los ZIP hayan sido descargados ni que la presión vendedora inicial haya quedado medida.

### Referencia técnica primaria

- Binance Public Data, esquema y semántica de Spot klines, Spot aggTrades y timestamps desde 2025: https://github.com/binance/binance-public-data
