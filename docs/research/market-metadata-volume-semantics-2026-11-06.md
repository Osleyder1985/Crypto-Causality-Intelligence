# Revisión de metadata de mercados y semántica de volumen — 2026-11-06

## Estado de esta revisión

Esta es una revisión documental de los contratos públicos de las API. **No representa todavía una captura nueva de metadata ni una validación en vivo de los símbolos**. La siguiente ejecución debe archivar las respuestas de metadata con fecha de captura, endpoint, parámetros, código HTTP y SHA-256.

## 1. Binance Spot

### Metadata del instrumento

El endpoint `GET /api/v3/exchangeInfo` permite consultar los símbolos y sus reglas actuales. Para cada instrumento se deben conservar, como mínimo:

- `symbol`, `status`, `baseAsset` y `quoteAsset`;
- `baseAssetPrecision` y `quoteAssetPrecision`;
- `isSpotTradingAllowed`;
- `permissionSets` (no depender del campo antiguo `permissions`, cuya semántica y disponibilidad han cambiado);
- filtros relevantes, especialmente `PRICE_FILTER`, `LOT_SIZE` y `MARKET_LOT_SIZE`, si aparecen.

La metadata es una fotografía del estado actual; no demuestra por sí sola que el instrumento tuviera el mismo estado, reglas o disponibilidad durante todo el periodo histórico.

### Semántica de Klines

La respuesta de Spot Klines contiene 12 posiciones. Para la extracción actual:

| Posición | Campo | Interpretación |
|---:|---|---|
| 0 | Open time | Inicio de vela, milisegundos |
| 1–4 | OHLC | Precios expresados en la moneda cotizada |
| 5 | Volume | Cantidad negociada del activo base |
| 6 | Close time | Cierre de vela, milisegundos |
| 7 | Quote asset volume | Cantidad negociada del activo cotizado |
| 8 | Number of trades | Número de operaciones |
| 9 | Taker buy base asset volume | Volumen base comprado por takers |
| 10 | Taker buy quote asset volume | Volumen cotizado comprado por takers |
| 11 | Ignore | Campo reservado; no utilizar analíticamente |

Para BTCUSDT, el volumen de la posición 5 está expresado en BTC y el de la posición 7 en USDT. Para ETHUSDT, las unidades correspondientes son ETH y USDT. El valor de volumen no debe etiquetarse como USD.

## 2. Kraken Spot

### Metadata del instrumento

El endpoint público `GET /0/public/AssetPairs` permite resolver los identificadores internos y las representaciones de cada par. Para cada instrumento se deben conservar:

- clave del resultado (identificador devuelto por Kraken);
- `altname` y `wsname`;
- `base` y `quote` junto con `aclass_base` y `aclass_quote`;
- `status`, si aparece;
- `pair_decimals`, `lot_decimals`, `lot_multiplier`, `ordermin` y `costmin`, cuando estén presentes.

La clave devuelta por el endpoint OHLC debe seguir siendo el identificador de mercado usado para vincular la vela con la metadata. No asumir que la clave, el nombre REST y el nombre WebSocket son intercambiables.

### Semántica de OHLC

La respuesta OHLC de Kraken contiene: timestamp, open, high, low, close, VWAP, volumen, número de operaciones. El volumen está expresado en el activo base; VWAP es un precio y el contador representa operaciones. No debe tratarse el VWAP como volumen cotizado ni compararse el campo de volumen directamente con el volumen cotizado de Binance.

Kraken documenta que sus archivos OHLCVT contienen datos de los intervalos en los que hubo operaciones; las velas vacías no se incluyen. Por ello:

- una ausencia de vela puede representar ausencia de operaciones;
- no rellenar automáticamente la ausencia con OHLC sintético ni volumen cero;
- distinguir los huecos internos de las observaciones que no llegaron por límites de consulta;
- conservar el número de operaciones para ayudar a interpretar actividad y ausencia de velas.

El endpoint REST OHLC devuelve como máximo las 720 velas más recientes del intervalo. La muestra horaria de 720 horas queda, por tanto, expuesta al truncamiento por el extremo más reciente y no puede considerarse una extracción histórica paginable mediante el parámetro `since` únicamente.

Kraken también publica archivos históricos OHLCVT descargables. La documentación consultada indica que el conjunto completo disponible llega hasta el 30 de septiembre de 2026. Ese archivo puede servir para periodos anteriores, pero no cubre por sí solo la ventana horaria de esta PoC, que comienza el 7 de octubre de 2026.

## 3. Comparabilidad de volumen

| Proveedor / mercado | Campo de volumen | Unidad | Campos complementarios |
|---|---|---|---|
| Binance BTCUSDT | `volume` | BTC | `quote_volume` en USDT, operaciones, taker-buy base/cotizado |
| Binance ETHUSDT | `volume` | ETH | `quote_volume` en USDT, operaciones, taker-buy base/cotizado |
| Kraken XBT/USD | `volume` | XBT | VWAP en USD, número de operaciones |
| Kraken ETH/USD | `volume` | ETH | VWAP en USD, número de operaciones |

No se debe comparar directamente el volumen base entre activos distintos, ni equiparar el volumen cotizado USDT de Binance con USD de Kraken. Para comparar notional cotizado se necesita una conversión USDT/USD independiente, con su propio origen, timestamp, metodología y evidencia. La comparación de actividad en unidades base puede realizarse por activo, pero debe seguir separada por venue y con la semántica de cada mercado preservada.

## 4. Cambios requeridos en la ingestión

Antes de considerar completa la evaluación técnica:

1. Añadir captura de `exchangeInfo` para BTCUSDT y ETHUSDT y de `AssetPairs` para los pares de Kraken.
2. Guardar las respuestas originales de metadata como evidencia versionada por ejecución, con hashes y hora de captura.
3. Incorporar a la normalización los campos de operaciones y taker-buy de Binance.
4. Normalizar nombres explícitos de volumen (`base_volume`, `quote_volume`) sin borrar el campo original ni sus unidades.
5. Registrar por separado `vwap` y `trade_count` de Kraken.
6. Cambiar la interpretación de cobertura: informar cobertura observada, huecos y conteo de operaciones; no clasificar automáticamente una vela ausente como pérdida de datos.
7. Añadir pruebas unitarias para el mapeo de campos y unidades de ambos proveedores.
8. Ejecutar de nuevo el workflow y revisar las respuestas de metadata reales antes de emitir una clasificación final.

## 5. Conclusión provisional

- **Binance Spot:** el esquema Kline proporciona suficiente detalle para separar volumen base, volumen cotizado, número de operaciones y actividad taker. Falta capturar y validar metadata vigente de los dos símbolos en una ejecución reproducible.
- **Kraken Spot:** OHLC proporciona volumen base, VWAP y número de operaciones, pero el endpoint REST de 720 velas no basta para reconstruir una ventana horaria superior a ese límite. La omisión de velas sin operaciones debe formar parte de la lógica de validación.
- **Comparación entre venues:** es viable comparar series de precios y métricas de actividad solo después de alinear activo, intervalo, timestamp y moneda/unidad. Los volúmenes cotizados USDT y USD no son equivalentes.

No se declara todavía aptitud definitiva de ninguna fuente. Esta revisión reduce ambigüedades de esquema, pero no sustituye la captura empírica de metadata ni la repetición de las descargas.

## 6. Documentación oficial consultada

- Binance Spot REST API — Exchange information: https://developers.binance.com/en/docs/catalog/core-trading-spot-trading/api/rest-api/general
- Binance Spot API — Kline stream payload and field meanings: https://github.com/binance/binance-spot-api-docs/blob/master/web-socket-streams.md
- Binance public data — Kline column definitions: https://github.com/binance/binance-public-data
- Kraken — API symbols and tickers / AssetPairs: https://support.kraken.com/articles/360000920306-api-symbols-and-tickers
- Kraken — OHLC endpoint: https://docs.kraken.com/api/docs/rest-api/get-ohlc-data
- Kraken — Historical OHLCVT files and empty intervals: https://support.kraken.com/articles/360047124832-downloadable-historical-ohlcvt-open-high-low-close-volume-trades-data

## 7. Implementación incorporada en la rama de investigación

En la rama `research/issue-11-empirical-data-poc` se actualizó el descargador para:

- Consultar `GET /api/v3/exchangeInfo` y archivar la respuesta original de Binance.
- Consultar `GET /0/public/AssetPairs` y archivar la respuesta original de Kraken.
- Registrar para cada captura de metadata el endpoint, parámetros, estado HTTP, latencia, reintentos, hora UTC y SHA-256, además de conservar un resumen de los mercados BTC/ETH relevantes en el manifiesto.
- Normalizar explícitamente `base_volume` y `quote_volume` con sus unidades. Se conserva también `volume` como campo de compatibilidad.
- Incorporar `trade_count`, `taker_buy_base_volume` y `taker_buy_quote_volume` de Binance.
- Incorporar `vwap` y `trade_count` de Kraken; `quote_volume` queda vacío porque el endpoint OHLC no proporciona ese dato.
- Informar huecos, conteos de operaciones y cobertura teórica sin convertir automáticamente la ausencia de una vela en una declaración de pérdida de datos.

Las pruebas unitarias se ampliaron para comprobar la selección de metadata de los pares, la asignación de unidades y campos de volumen y la interpretación prudente de huecos.

**Estado de verificación:** el código y las pruebas están incorporados en la rama, pero la ejecución del workflow con la nueva captura y la inspección de sus artefactos siguen pendientes. Por tanto, todavía no se afirma que la metadata haya sido validada empíricamente ni que las nuevas llamadas hayan respondido correctamente en GitHub Actions.
