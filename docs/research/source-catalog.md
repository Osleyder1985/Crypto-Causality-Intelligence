# Catálogo inicial de fuentes históricas

> Estado: catálogo exploratorio; no constituye una selección contractual ni una integración aprobada.  
> Área: Historical Market Intelligence.  
> Fecha de consulta de referencias: 2026-11-05.

## 1. Propósito

Identificar fuentes que permitan reconstruir el comportamiento histórico del mercado cripto y relacionarlo con eventos verificables. El catálogo separa los registros originados en el mercado o la cadena, los datos agregados por terceros y el contenido contextual.

Una fuente no se considera confiable por su popularidad. Cada conjunto de datos debe evaluarse por cobertura, semántica, disponibilidad temporal, procedencia, licencia y limitaciones conocidas.

## 2. Clasificación de fuentes

| Clase | Ejemplos | Uso principal | Precaución |
|---|---|---|---|
| Primaria de mercado | API y feeds de un exchange | Trades, velas, tickers, funding y libro de órdenes de ese venue | Solo representa la actividad observada por ese exchange; los símbolos y mercados pueden cambiar |
| Archivo de feeds de mercado | Proveedor que captura WebSocket de exchanges | Reconstrucción granular de trades y order books | Es una captura de terceros; hay que revisar fechas de inicio, huecos, retrasos y licencia |
| Agregada/secundaria | Agregadores de precios y métricas | Comparación entre activos, series de referencia y cobertura amplia | La metodología de agregación puede cambiar; no equivale al registro de cada venue |
| On-chain primaria | Nodos, exploradores y datos de transacciones de la red | Bloques, transacciones, eventos de contratos y actividad observable | La interpretación de una transacción o entidad puede ser incierta |
| On-chain procesada | Indexadores y proveedores de métricas | Métricas derivadas, flujos, actividad y series históricas | Documentar metodología, revisiones y reglas de atribución |
| Oficial/contextual | Blogs, documentación, repositorios, governance y anuncios de proyectos | Fechas de anuncios, cambios de protocolo, releases y decisiones | Una publicación oficial prueba que se publicó una declaración, no que todas sus afirmaciones sean verdaderas |
| Noticias/social | Medios, RSS, X y otros canales públicos | Primera aparición conocida, difusión, reacción y contraste | Contenido editable, eliminado, duplicado, automatizado o no verificado |

## 3. Candidatos iniciales

Los candidatos se incluyen para investigación y prueba de cobertura. No se asume que todos deban integrarse ni que sus planes actuales sean adecuados.

### 3.1 Exchanges y datos primarios de mercado

| Fuente | Datos/documentación observables | Papel propuesto | Limitaciones que deben verificarse |
|---|---|---|---|
| [Binance Spot API](https://developers.binance.com/en/docs/products/spot/rest-api) | REST de mercado; endpoints de klines, trades, ticker y exchange information | Fuente primaria para actividad de Binance Spot | Límites de peso/solicitudes, cambios de símbolos, disponibilidad histórica por endpoint y diferencias Spot/Futures |
| [Coinbase Exchange API](https://docs.cdp.coinbase.com/exchange/reference/exchangerestapi_getproductcandles) | Candles por producto y granularidad | Fuente primaria para mercados Coinbase Exchange | Límites por solicitud, huecos de velas, pares disponibles y profundidad histórica real |
| [Kraken OHLC API](https://docs.kraken.com/api/docs/rest-api/get-ohlc-data) | OHLC y marca temporal de intervalos | Fuente primaria para mercados Kraken | El endpoint y sus límites de resultados deben comprobarse antes de asumir que permite reconstruir toda la historia |

**Regla:** conservar venue, market type, instrument identifier, base/quote asset, intervalo, timestamp original y timestamp de captura. No fusionar silenciosamente series de distintos exchanges.

### 3.2 Archivos históricos granulares

| Fuente | Datos/documentación observables | Papel propuesto | Limitaciones que deben verificarse |
|---|---|---|---|
| [Tardis.dev](https://docs.tardis.dev/) | Trades, incremental order book L2, snapshots, quotes, funding, open interest, liquidations y replay; cobertura por exchange | Candidato para investigación de microestructura y reconstrucción de eventos | Servicio comercial; revisar cobertura por instrumento/canal/fecha, retrasos, huecos, formato nativo vs normalizado y derechos de uso |

La documentación de Tardis indica que sus históricos se derivan de feeds WebSocket capturados y que la cobertura y fecha de inicio dependen del exchange y del canal. También documenta retrasos de publicación y particularidades de snapshots y reconexiones. Por tanto, no se debe asumir continuidad perfecta ni cobertura universal.

### 3.3 Agregadores de mercado

| Fuente | Datos/documentación observables | Papel propuesto | Limitaciones que deben verificarse |
|---|---|---|---|
| [CoinGecko API](https://www.coingecko.com/en/api) | Precios, market cap, volumen, metadatos, OHLC/OHLCV, exchanges y datos on-chain vía GeckoTerminal | Candidato para contexto agregado y cobertura amplia de activos | La profundidad histórica y granularidad dependen del endpoint y del plan; revisar metodología, límites, cobertura de activos inactivos y licencia |
| [CoinMarketCap API](https://coinmarketcap.com/api/documentation/) | Quotes históricos, listings históricos, OHLCV histórico y market pairs | Candidato alternativo para contraste de series agregadas | Acceso y granularidad dependen del plan; la documentación advierte que el volumen horario no está disponible antes de 2020-09-22 en el endpoint OHLCV histórico |

No elegir una serie agregada como única verdad de mercado. Para episodios relevantes, contrastar con uno o más venues y registrar la metodología del agregador.

### 3.4 Datos on-chain

| Fuente | Datos/documentación observables | Papel propuesto | Limitaciones que deben verificarse |
|---|---|---|---|
| [DefiLlama API](https://api-docs.defillama.com/) | Precios históricos, datos de stablecoins, protocolos y otras métricas del ecosistema | Candidato inicial para métricas DeFi y contexto cross-chain | Confirmar cobertura por métrica, metodología, granularidad, límites y condiciones de uso |
| [Glassnode API](https://docs.glassnode.com/basic-api/api) | Métricas on-chain y de mercado históricas mediante API | Candidato especializado para investigación on-chain | La documentación indica que el acceso API requiere plan Professional y complemento API; revisar costos y definición exacta de cada métrica |

Las métricas on-chain suelen ser transformaciones analíticas, no observaciones directas de una entidad económica. Registrar definición, unidad, universo, filtros, método de atribución y versión de la métrica.

### 3.5 Fuentes oficiales, noticias y redes sociales

No se selecciona todavía un proveedor único para esta categoría. El sistema debe admitir fuentes identificadas individualmente:

- Sitios oficiales, blogs, changelogs, repositorios y foros de gobernanza de proyectos.
- Comunicados regulatorios y publicaciones de autoridades.
- Feeds RSS y archivos de medios con fecha y URL originales.
- Publicaciones públicas de cuentas sociales, conservando identificador, autor, URL, hora de publicación y hora de captura cuando sea legal y técnicamente posible.

Una publicación social se registra inicialmente como **afirmación atribuida a una cuenta**, no como hecho confirmado. Para elevar su estado se requiere corroboración independiente o evidencia primaria adicional.

## 4. Matriz de evaluación

Puntuar cada dimensión de 0 a 3 y adjuntar evidencia. La puntuación es una herramienta de comparación, no una probabilidad de veracidad.

| Dimensión | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| Cobertura | No documentada | Muy limitada | Adecuada para un caso | Amplia y detallada |
| Profundidad histórica | No disponible | Muy corta/incierta | Cubre parte del periodo | Cubre el periodo requerido y sus límites están documentados |
| Granularidad | Inadecuada | Solo agregados gruesos | Adecuada para el análisis | Granularidad suficiente y semántica clara |
| Procedencia | Sin origen trazable | Origen parcial | Origen identificable | Origen, captura y transformaciones auditables |
| Calidad/continuidad | Sin controles | Controles opacos | Controles documentados | Incidentes, huecos y correcciones documentados |
| Estabilidad operativa | Sin información | Limitada | Límites y estado visibles | SLA/estado/incidentes y límites claros |
| Licencia/uso | Desconocida o incompatible | Ambigua | Uso previsto permitido con condiciones | Derechos y restricciones claros para el uso previsto |
| Costo sostenible | Desconocido/inviable | Alto o incierto | Aceptable con límites | Compatible con el presupuesto definido |

**No calcular un total si hay dimensiones críticas desconocidas.** Marcar cada campo como `confirmed`, `estimated`, `unknown` o `not_applicable`; un dato desconocido no equivale a una puntuación baja ni debe ocultarse en un promedio.

## 5. Reglas de selección

1. Definir primero la pregunta de investigación y el tipo de dato necesario.
2. Preferir la fuente primaria para hechos específicos de un venue, cadena o emisor.
3. Usar agregadores para contexto, descubrimiento y contraste, no para reemplazar procedencia primaria.
4. Exigir timestamps semánticamente definidos: event time, exchange time, published time, captured time e ingested time cuando correspondan.
5. Verificar la cobertura para cada activo, mercado, instrumento, intervalo y periodo; no extrapolar desde la cobertura general del proveedor.
6. Registrar el estado del activo y del mercado a lo largo del tiempo, incluidos listings, delistings, migraciones y cambios de contrato.
7. Revisar términos de uso antes de almacenar, mostrar o redistribuir datos. No asumir que el acceso gratuito concede derechos comerciales o de redistribución.
8. Mantener al menos una vía de contraste independiente para series críticas.
9. Conservar consultas, parámetros, versión de endpoint, fecha de consulta, respuesta original o hash verificable y transformaciones aplicadas.

## 6. Sesgos y riesgos históricos

- **Survivorship bias:** analizar solo activos que siguen listados elimina proyectos fallidos, tokens desaparecidos y mercados cerrados.
- **Delisting bias:** la ausencia de un activo en un catálogo actual no demuestra que nunca existiera ni que no tuviera datos históricos.
- **Symbol collision:** un ticker no es un identificador global; usar identificadores de proveedor, contrato, red y periodo de validez.
- **Methodology drift:** los agregadores pueden modificar fuentes, filtros, ponderaciones o reglas de exclusión.
- **Backfill/revisions:** los proveedores pueden completar o corregir datos históricos; registrar cuándo se observó cada versión.
- **Venue fragmentation:** el precio y volumen de un exchange no representan necesariamente el mercado global.
- **Timestamp ambiguity:** distinguir tiempo del evento, tiempo del exchange, publicación, captura e ingesta.
- **Social manipulation:** bots, cuentas comprometidas, contenido editado, rumores coordinados y publicaciones borradas.
- **Metric attribution:** las etiquetas de wallets, entidades y flujos pueden cambiar y no deben tratarse como identidad demostrada sin evidencia.

## 7. Recomendación para una prueba de concepto

Propuesta inicial, sujeta a una prueba técnica y revisión de licencias:

1. **Binance Spot API** como fuente primaria inicial para velas y trades de un venue.
2. **Coinbase Exchange o Kraken** como segundo venue independiente para contrastar series.
3. **CoinGecko API o CoinMarketCap API** —evaluar uno primero— para contexto agregado, metadatos y cobertura más amplia.
4. **DefiLlama** para una primera capa de contexto DeFi/on-chain; evaluar Glassnode solo si una pregunta concreta requiere sus métricas especializadas.
5. **Fuentes oficiales del proyecto y autoridades** para eventos; añadir medios y redes sociales como evidencia contextual atribuida.
6. **Tardis.dev** queda como candidato especializado si la investigación requiere trades tick-level, order book L2, funding, liquidations o replay histórico que no resulte viable capturar directamente.

Esta propuesta no autoriza compras, suscripciones ni despliegues. Antes de decidir, ejecutar una prueba pequeña sobre BTC y ETH con un periodo común, comparar timestamps, huecos, OHLCV, identificadores y diferencias entre fuentes.

## 8. Datos pendientes antes de seleccionar proveedores

- Presupuesto mensual y restricciones de licencia.
- Universo inicial de activos y exchanges.
- Periodo histórico mínimo requerido por caso de uso.
- Granularidad mínima: diaria, horaria, minutos, trades o order book.
- Necesidad de datos Spot, Futures, Options y DEX.
- Volumen esperado, frecuencia de actualización y retención.
- Requisitos de almacenamiento, redistribución y uso comercial.

## 9. Referencias consultadas

- Binance Spot REST API: https://developers.binance.com/en/docs/products/spot/rest-api
- Coinbase Exchange candles: https://docs.cdp.coinbase.com/exchange/reference/exchangerestapi_getproductcandles
- Kraken OHLC: https://docs.kraken.com/api/docs/rest-api/get-ohlc-data
- Tardis documentation: https://docs.tardis.dev/
- Tardis historical data details: https://docs.tardis.dev/historical-data-details
- Tardis downloadable CSV: https://docs.tardis.dev/downloadable-csv-files
- CoinGecko API: https://www.coingecko.com/en/api
- CoinGecko historical depth: https://support.coingecko.com/articles/7171295369-how-far-back-is-the-historical-data
- CoinMarketCap API: https://coinmarketcap.com/api/documentation/
- DefiLlama API: https://api-docs.defillama.com/
- Glassnode API: https://docs.glassnode.com/basic-api/api

Las condiciones comerciales, límites, endpoints y cobertura pueden cambiar. Volver a verificar las páginas oficiales y registrar la fecha de consulta antes de contratar o implementar.
