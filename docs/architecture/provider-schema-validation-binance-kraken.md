# Validación de esquemas por proveedor: Binance Spot y Kraken Spot

- **Estado:** validación documental completada en primera pasada; validación empírica parcial.
- **Fecha de revisión:** 2026-11-06.
- **Contratos evaluados:** `market_ohlcv` y `market_instrument_metadata`.
- **Rama:** `docs/issue-14-storage-architecture-decision`.
- **PR:** #15.
- **Alcance:** endpoints públicos Spot; no incluye Futures, Margin, Options ni productos derivados.

## 1. Resumen ejecutivo

Los dos proveedores pueden representarse en un contrato canónico común, pero no con una traducción campo-a-campo ingenua.

| Área | Binance Spot | Kraken Spot | Resultado |
|---|---|---|---|
| OHLC | Open, high, low y close | Open, high, low y close | Compatible |
| Volumen base | Sí | Sí | Compatible |
| Volumen quote | Sí | No aparece en OHLC REST | Campo nullable |
| VWAP | No incluido en Kline | Sí, incluido en OHLC | Campo canónico opcional |
| Número de operaciones | Sí | Sí | Compatible |
| Volumen taker buy | Base y quote | No incluido en OHLC | Extensión opcional |
| Timestamp | Milisegundos por defecto; microsegundos opcionales | Unix en segundos en el ejemplo oficial | Normalizar a UTC conservando precisión original |
| Cierre de vela | Timestamp de cierre incluido en la tupla | No entrega timestamp de cierre separado | Adaptadores diferentes |
| Vela actual | Debe determinarse su finalización según respuesta/flujo y tiempo | Última fila siempre es el intervalo actual no confirmado | Regla explícita de finalización |
| Histórico REST | Klines con paginación por tiempo y límite por petición | OHLC REST limitado a las 720 entradas más recientes | No usar Kraken OHLC REST para reconstruir todo el histórico |
| Metadata | `exchangeInfo` y filtros tipados | `AssetPairs` con precisión, mínimos, estado e identificadores | Compatible con extensiones |

**Conclusión:** el contrato canónico es viable, pero requiere incorporar VWAP y volúmenes taker como campos opcionales, además de reglas específicas de timestamp, intervalos y metadata. Estos ajustes ya se reflejan en `canonical-market-data-schemas.md`.

## 2. Binance Spot: correspondencia documental

Fuentes oficiales:
- [REST API — Binance Spot](https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md)
- [Filters — Binance Spot](https://github.com/binance/binance-spot-api-docs/blob/master/filters.md)
- [Market Data Only](https://github.com/binance/binance-spot-api-docs/blob/master/faqs/market_data_only.md)
- [Spot API Glossary](https://developers.binance.com/en/docs/products/spot/faqs/spot_glossary)

### 2.1 Klines

Endpoint: `GET /api/v3/klines`.

La respuesta es una tupla de 12 posiciones:

| Posición | Campo Binance | Campo canónico | Tratamiento |
|---:|---|---|---|
| 0 | Open time | `open_time` | Epoch a UTC; ms por defecto, µs si se solicita header correspondiente. |
| 1 | Open | `open` | Decimal exacto desde string. |
| 2 | High | `high` | Decimal exacto desde string. |
| 3 | Low | `low` | Decimal exacto desde string. |
| 4 | Close | `close` | Decimal exacto desde string. |
| 5 | Volume | `volume_base` | Volumen en activo base. |
| 6 | Close time | `source_close_time_raw` | Conservar original; convertir a `close_time_exclusive` sumando una unidad de la resolución de timestamp. |
| 7 | Quote asset volume | `volume_quote` | Volumen en activo cotizado. |
| 8 | Number of trades | `trade_count` | Entero. |
| 9 | Taker buy base asset volume | `taker_buy_volume_base` | Decimal exacto. |
| 10 | Taker buy quote asset volume | `taker_buy_volume_quote` | Decimal exacto. |
| 11 | Ignore | No mapear | Conservar únicamente en raw; no es métrica canónica. |

Binance identifica las klines por su open time. El endpoint admite intervalos desde `1s` hasta intervalos mensuales, con una lista específica; el límite documentado es 1000 filas por petición. El parámetro `timeZone` cambia la interpretación/anclaje del intervalo, mientras que `startTime` y `endTime` siguen interpretándose en UTC. Por ello, el adapter inicial fijará `timeZone=0` y registrará ese parámetro.

El timestamp de cierre de Binance representa el último instante incluido de la vela, no el límite exclusivo canónico. Para una respuesta en milisegundos, el límite exclusivo se obtiene sumando 1 ms; si se solicita precisión en microsegundos, se suma 1 µs. Esta conversión debe quedar cubierta por pruebas.

### 2.2 Metadatos de instrumentos

Endpoint: `GET /api/v3/exchangeInfo`.

| Campo Binance | Campo canónico / extensión | Tratamiento |
|---|---|---|
| `symbol` | `native_symbol` y referencia nativa | Conservar exactamente. |
| `status` | `instrument_status` | Conservar valor nativo y mapear por tabla versionada. |
| `baseAsset` | `base_asset_code_native` | Código nativo; resolver identidad por separado. |
| `quoteAsset` | `quote_asset_code_native` | Código nativo; no unificar USD y USDT. |
| `PRICE_FILTER.tickSize` | `price_tick` | Mapeo directo. |
| `PRICE_FILTER.minPrice/maxPrice` | `price_minimum/price_maximum` | Mapeo directo. |
| `LOT_SIZE.stepSize` | `quantity_step` | Mapeo directo. |
| `LOT_SIZE.minQty/maxQty` | `min_quantity/max_quantity` | Mapeo directo. |
| `NOTIONAL.minNotional/maxNotional` | `min_notional/max_notional` | Conservar condiciones `applyMinToMarket` y `applyMaxToMarket`. |
| `MIN_NOTIONAL.minNotional` | `min_notional` | Conservar `applyToMarket` y `avgPriceMins`. |
| `baseAssetPrecision`, `quoteAssetPrecision` | Extensión de metadata de fuente | No confundir con tick size ni step size. |
| `orderTypes`, permisos y filtros adicionales | Extensión estructurada tipada | No descartar filtros que no tengan columna canónica. |

Los filtros son reglas distintas: `PRICE_FILTER`, `LOT_SIZE`, `MARKET_LOT_SIZE`, `MIN_NOTIONAL`, `NOTIONAL` y otros. No deben aplanarse en un único campo de mínimo/máximo porque algunos aplican solo a órdenes de mercado, a determinados lados o dependen de precios de referencia.

### 2.3 Inspección empírica realizada

Se consultó el endpoint público `exchangeInfo?symbol=BTCUSDT` y se obtuvo un payload JSON legible. El registro observado contenía `status`, `baseAsset`, `quoteAsset`, `PRICE_FILTER`, `LOT_SIZE`, `MARKET_LOT_SIZE` y `NOTIONAL`, entre otros filtros. Esto confirma que la estructura de metadata del contrato puede recibir el payload real de Binance Spot y que los campos de filtros no son una lista fija mínima.

**Límite de esta prueba:** no se consiguió recuperar una respuesta legible de `/api/v3/klines` durante esta sesión. Por tanto, la correspondencia OHLCV de Binance está respaldada documentalmente, pero queda pendiente la prueba empírica de payload Klines.

## 3. Kraken Spot: correspondencia documental

Fuentes oficiales:
- [Get OHLC Data — Kraken Spot REST](https://docs.kraken.com/api-reference/market-data/get-ohlc-data)
- [Get Tradable Asset Pairs — Kraken Spot REST](https://docs.kraken.com/api-reference/market-data/get-tradable-asset-pairs)
- [Downloadable historical OHLCVT — Kraken Support](https://support.kraken.com/in/articles/360047124832-downloadable-historical-ohlcvt-open-high-low-close-volume-trades-data)

### 3.1 OHLC REST

Endpoint: `GET /0/public/OHLC`.

La fila de respuesta documentada contiene ocho posiciones:

| Posición | Campo Kraken | Campo canónico | Tratamiento |
|---:|---|---|---|
| 0 | Time | `open_time` | Epoch en segundos en el ejemplo oficial; convertir a UTC y conservar valor/resolución raw. |
| 1 | Open | `open` | Decimal exacto desde string. |
| 2 | High | `high` | Decimal exacto desde string. |
| 3 | Low | `low` | Decimal exacto desde string. |
| 4 | Close | `close` | Decimal exacto desde string. |
| 5 | VWAP | `vwap` | Decimal exacto; no confundir con close ni con volumen quote. |
| 6 | Volume | `volume_base` | Volumen en activo base. |
| 7 | Count | `trade_count` | Número de operaciones. |

El endpoint no proporciona `volume_quote` ni volúmenes taker en esa fila. Se mantienen como null, no se calculan a partir de los otros campos.

La respuesta incluye una clave `last` para paginación incremental. La documentación indica expresamente que la última fila de OHLC es el intervalo actual todavía no confirmado, siempre se incluye y el endpoint devuelve como máximo 720 entradas recientes; no permite recuperar entradas más antiguas aunque se cambie `since`. Por tanto:

- La última fila debe marcarse `is_final=false`.
- No se debe incorporar esa última fila como vela final al dataset histórico sin un mecanismo de actualización/reconciliación.
- El endpoint REST OHLC no es suficiente para reconstruir toda la historia de Kraken.
- Para cobertura histórica se debe evaluar el archivo OHLCVT oficial, sus manifests/checksums, actualizaciones incrementales y condiciones de uso, o una fuente autorizada alternativa.

Kraken REST ofrece intervalos en minutos: 1, 5, 15, 30, 60, 240, 1440, 10080 y 21600. No son idénticos a los intervalos de Binance. La compatibilidad del contrato no implica que todos los proveedores tengan la misma cobertura de granularidades.

El endpoint no incluye timestamp de cierre. El adapter debe calcular `close_time_exclusive` a partir de `open_time` y el intervalo fijo solicitado. No debe fabricar intervalos si el tipo de intervalo no permite un cálculo inequívoco.

### 3.2 Archivos históricos OHLCVT

Kraken documenta archivos OHLCVT CSV con filas:

`timestamp, open, high, low, close, volume, trades`

El volumen es base; trades es el recuento. La documentación enumera granularidades de 1, 5, 15, 60, 240, 720 y 1440 minutos. Solo incluye intervalos en los que hubo operaciones; no rellena huecos con ceros.

Esto es una fuente y un mecanismo de distribución distinto del endpoint REST OHLC. El contrato debe registrar endpoint/dataset y método de adquisición en procedencia, sin tratar ambos canales como una misma captura.

### 3.3 Metadatos de pares

Endpoint: `GET /0/public/AssetPairs`.

| Campo Kraken | Campo canónico / extensión | Tratamiento |
|---|---|---|
| Clave de objeto del par | `source_instrument_id` | Conservar ID interno exactamente. |
| `altname`, `wsname` | `native_symbol` / aliases | Conservar ambos nombres y sus namespaces; no reemplazar ID interno. |
| `base`, `quote` | `base_asset_code_native`, `quote_asset_code_native` | Conservar códigos internos (incluidos prefijos legacy) y versión display si se solicita. |
| `status` | `instrument_status` | Conservar valor nativo; normalizar con mapping versionado. |
| `tick_size` | `price_tick` | Mapeo directo. |
| `pair_decimals` | `price_precision` | Precisión declarada; no sustituye tick size. |
| `lot_decimals` | `quantity_precision` | Precisión declarada; no inventar `quantity_step` a partir de ella. |
| `ordermin` | `min_quantity` | Mapeo directo. |
| `costmin` | `min_notional` | Conservar moneda/unidad y condiciones aplicables. |
| `cost_decimals`, `lot_multiplier`, clases de activo | Extensión tipada | Conservar para interpretación y auditoría. |

Kraken permite solicitar `assetVersion=1` para nombres display; por defecto devuelve identificadores internos legacy. El adapter debe conservar el identificador interno y los nombres alternativos, sin tratar `XBT` y `BTC` como equivalentes globales sin una resolución explícita de identidad.

No se ha identificado en el esquema de `AssetPairs` un equivalente directo universal de `LOT_SIZE.stepSize` de Binance. Por ello, `quantity_step` queda null para Kraken hasta que una regla oficial verificable permita mapearlo. No derivarlo automáticamente de `lot_decimals`.

### 3.4 Inspección empírica realizada

La documentación oficial ofrece ejemplos de respuesta para OHLC y AssetPairs, pero en esta sesión no se obtuvo un payload JSON legible de los endpoints públicos Kraken. Los campos y limitaciones anteriores están verificados documentalmente; la captura empírica en vivo queda pendiente.

## 4. Ajustes requeridos al contrato canónico

Los siguientes cambios se aplicaron en `canonical-market-data-schemas.md`:

1. Añadir `vwap` opcional.
2. Añadir `taker_buy_volume_base` y `taker_buy_volume_quote` opcionales.
3. Añadir `interval_timezone`; la primera versión de ambos adapters solicitará UTC.
4. Añadir `max_notional`, `price_minimum`, `price_maximum` y `quantity_maximum`.
5. Especificar que `quantity_step` no se deduce de un campo de precisión.
6. Especificar la conversión de cierre inclusivo Binance a límite exclusivo canónico.
7. Especificar que Kraken OHLC REST no incluye cierre independiente y que la última fila es provisional.
8. Separar la cobertura del endpoint OHLC REST de los archivos históricos OHLCVT de Kraken.

## 5. Matriz de compatibilidad resultante

| Campo canónico | Binance Spot | Kraken Spot REST | Estado |
|---|---|---|---|
| `open_time` | Sí, epoch ms/µs | Sí, epoch seconds en ejemplo | Compatible tras conversión |
| `close_time_exclusive` | Derivado de cierre inclusivo | Derivado de apertura + intervalo | Reglas específicas |
| `open/high/low/close` | Sí | Sí | Compatible |
| `volume_base` | Sí | Sí | Compatible |
| `volume_quote` | Sí | No | Nullable |
| `vwap` | No | Sí | Nullable |
| `taker_buy_volume_base` | Sí | No | Nullable |
| `taker_buy_volume_quote` | Sí | No | Nullable |
| `trade_count` | Sí | Sí | Compatible |
| `is_final` | Requiere lógica de cierre/captura | Última fila siempre false | Reglas específicas |
| `price_tick` | `PRICE_FILTER.tickSize` | `tick_size` | Compatible |
| `quantity_step` | `LOT_SIZE.stepSize` | Sin equivalente confirmado | Nullable en Kraken |
| `min_quantity` | `LOT_SIZE.minQty` | `ordermin` | Compatible |
| `min_notional` | `MIN_NOTIONAL`/`NOTIONAL` | `costmin` | Requiere preservar condiciones/unidad |
| `price_precision` | No mapear desde tick size | `pair_decimals` | Nullable según fuente |
| `quantity_precision` | No mapear desde step size | `lot_decimals` | Nullable según fuente |
| `instrument_status` | `status` | `status` | Mapping controlado |

## 6. Estado de las pruebas

| Prueba | Binance Spot | Kraken Spot |
|---|---|---|
| Revisión de documentación oficial | Completada | Completada |
| Mapeo de Klines/OHLC | Completado documentalmente | Completado documentalmente |
| Mapeo de metadata | Completado documentalmente | Completado documentalmente |
| Inspección de payload live metadata | Parcialmente completada: `exchangeInfo(BTCUSDT)` legible | Pendiente: no se obtuvo payload legible |
| Inspección de payload live OHLC | Pendiente: Klines no se pudo recuperar en esta sesión | Pendiente: OHLC no se pudo recuperar en esta sesión |
| Validación de histórico completo | Pendiente | REST OHLC insuficiente; evaluar OHLCVT histórico |
| Pruebas adapter automatizadas | No implementadas | No implementadas |

**Resultado de la etapa:** la compatibilidad documental de los dos contratos está validada en primera pasada. La validación empírica completa no está cerrada. No se debe etiquetar esta etapa como aprobada para implementación productiva hasta completar las capturas reproducibles de OHLC y metadata de ambos proveedores.

## 7. Próximas pruebas empíricas controladas

Usar un instrumento de prueba que exista en ambos venues, sin asumir que sus símbolos nativos son iguales. Propuesta inicial: BTC cotizado en USD o USDT, seleccionando el par exacto disponible en cada venue y registrando las diferencias de moneda de cotización.

1. Obtener metadata del par/instrumento de cada proveedor.
2. Capturar una vela cerrada de 1 minuto y, por separado, la vela actual/provisional.
3. Registrar URL/endpoint, parámetros, headers relevantes, hora de captura UTC, estado HTTP, hash y versión de adapter.
4. Verificar tipos, escalas, invariantes OHLC, unidades y conversión temporal.
5. Confirmar que la última vela Kraken se marca provisional y no se trata como histórica final.
6. Comparar el mismo periodo temporal sin asumir que los precios o volúmenes deben coincidir entre venues.
7. Ejecutar pruebas de gaps, duplicados, revisiones y paginación.
8. No persistir respuestas raw ni datos de mercado en el repositorio hasta completar la revisión de permisos/retención aplicables. Si la política no permite conservar payloads, registrar únicamente metadatos de prueba permitidos y resultados de validación no redistributivos.

## 8. Decisión provisional

- Mantener los contratos canónicos ampliados en estado draft.
- Mantener adapters independientes para Binance Spot y Kraken Spot.
- Configurar UTC como único anclaje temporal inicial.
- Tratar los campos no suministrados por una fuente como null.
- No derivar volúmenes, VWAP, quantity step ni estado final sin regla explícita.
- No utilizar Kraken REST OHLC como única vía para reconstrucción histórica completa.
- No crear todavía migraciones SQL ni datasets Parquet reales.
