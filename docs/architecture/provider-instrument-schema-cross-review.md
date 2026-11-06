# Revisión cruzada: instrumentos y metadata de Binance Spot y Kraken Spot

- **Estado:** revisión documental completada; propuesta de ajustes incorporada al diseño físico.
- **Fecha de revisión:** 2026-11-06.
- **Contratos internos revisados:** `canonical-market-data-schemas.md` y `provider-validation-test-plan.md`.
- **Modelo físico revisado:** `postgresql-physical-schema.md`.
- **Alcance:** identidad de instrumentos, símbolos/alias, activos base y cotizados, estado, precisión y reglas de negociación.
- **Límite:** revisión de documentación oficial; no se ejecutaron llamadas API ni se capturaron respuestas reales durante esta tarea.

## 1. Dictamen

El diseño físico anterior era insuficiente para representar sin pérdida las diferencias de metadata de ambos proveedores. En particular, trataba el símbolo nativo como si fuera un atributo simple, exigía resolver inmediatamente los activos canónicos y agrupaba reglas de negociación distintas en campos genéricos.

Se actualizó la especificación física para separar:

1. identidad estable del instrumento;
2. identificadores y alias publicados por cada interfaz;
3. observaciones históricas de metadata;
4. reglas de negociación versionadas y específicas por ámbito.

**Resultado:** el modelo queda mejor alineado con los contratos canónicos. Aún no está listo para generar DDL definitivo: quedan pendientes la verificación empírica de las respuestas actuales y la política de resolución de activos canónicos.

## 2. Evidencia documental por proveedor

### 2.1 Binance Spot

La documentación oficial de `GET /api/v3/exchangeInfo` expone, por símbolo, al menos el símbolo, estado, activo base, activo cotizado, precisiones y una colección de filtros. La documentación oficial de filtros distingue, entre otros:

- `PRICE_FILTER`: `minPrice`, `maxPrice`, `tickSize`.
- `LOT_SIZE`: `minQty`, `maxQty`, `stepSize`.
- `MARKET_LOT_SIZE`: restricciones de cantidad específicas para órdenes de mercado.
- `MIN_NOTIONAL` y `NOTIONAL`: mínimos/máximos y condiciones de aplicabilidad a órdenes de mercado.
- Otros filtros de símbolo, exchange y activo, que no deben descartarse por no formar parte del mínimo canónico.

Las reglas pueden estar deshabilitadas mediante valores cero en campos definidos por la documentación; por tanto, cero no debe transformarse automáticamente en un límite efectivo. Las banderas de aplicabilidad y ventanas de promedio deben conservarse junto con el filtro.

**Implicación para PostgreSQL:** una sola columna `quantity_step` no representa todos los ámbitos. `LOT_SIZE` y `MARKET_LOT_SIZE` deben ser filas/reglas separadas. La metadata debe conservar el tipo nativo del filtro y sus parámetros completos.

### 2.2 Kraken Spot

La documentación oficial de Kraken explica que REST y WebSocket pueden utilizar símbolos diferentes para el mismo mercado. Los endpoints REST `Assets` y `AssetPairs` permiten recuperar los códigos disponibles y sus variantes.

En `AssetPairs`, la clave del objeto identifica el par en esa respuesta y los atributos incluyen, entre otros:

- `altname` y `wsname`, que no deben confundirse con la clave interna;
- `base` y `quote`, códigos nativos de activos;
- `pair_decimals` y `lot_decimals`;
- `ordermin` y `costmin`;
- `tick_size` y `status` en la estructura documentada del par.

La guía de errores de Kraken vincula explícitamente los errores de tamaño mínimo, coste mínimo y tick inválido con `ordermin`, `costmin` y `tick_size`.

**Implicación para PostgreSQL:** se deben conservar la clave interna, `altname`, `wsname` y los símbolos de otras interfaces como identificadores distintos asociados al mismo instrumento. `pair_decimals` y `lot_decimals` son precisiones declaradas; no deben convertirse en un `tick_size` o `quantity_step` inferido. El campo `tick_size` sí se conserva como regla nativa de precio.

## 3. Matriz de correspondencia canónica y física

| Semántica canónica | Binance Spot | Kraken Spot | Representación física propuesta |
|---|---|---|---|
| Fuente/mercado | Namespace `binance_spot` | Namespace `kraken_spot` | `data_sources` + `market_instruments.data_source_id` |
| ID nativo | No asumir que exista una clave universal separada del símbolo | Clave interna del objeto AssetPairs | `market_instruments.source_instrument_id` cuando exista; `instrument_identifiers` para claves de interfaz |
| Símbolo nativo | `symbol` | `altname`/símbolo según interfaz | `native_symbol` + alias explícitos en `instrument_identifiers` |
| Alias REST/WebSocket | Según interfaz y respuesta | `altname`, `wsname`, clave REST y formas WebSocket | Múltiples filas `instrument_identifiers` con namespace |
| Código base/cotizado | `baseAsset`, `quoteAsset` | `base`, `quote` | `native_base_asset_code`, `native_quote_asset_code` |
| Activo canónico | Resolución interna | Resolución interna, considerando códigos como XBT/XXBT | FKs nullable a `assets`; no inventar equivalencias |
| Estado | `status` | `status` | `instrument_metadata_versions.source_status`; mapeo separado `normalized_status` |
| Tick de precio | `PRICE_FILTER.tickSize` | `tick_size` | `instrument_trading_rules` |
| Mínimo/máximo precio | `PRICE_FILTER.minPrice/maxPrice` | Depende de campos/reglas publicados | Parámetros nativos de regla, sin inventar campos ausentes |
| Cantidad límite | `LOT_SIZE` | `ordermin` y precisión de lote, según semántica Kraken | Regla `limit_quantity`; no derivar step de decimales |
| Cantidad mercado | `MARKET_LOT_SIZE` | No mapear a regla Binance equivalente sin evidencia | Regla `market_quantity` solo si la fuente la publica |
| Notional/coste | `MIN_NOTIONAL/NOTIONAL` y banderas | `costmin` | Regla `notional` con parámetros y aplicabilidad nativos |
| Precisión decimal | Campos de precisión de activos/cotización | `pair_decimals`, `lot_decimals` | Columnas de precisión, separadas de ticks y steps |
| Filtros/reglas adicionales | Tipos adicionales de filtros | Campos adicionales del par | `parameters JSONB` tipado por adapter en `instrument_trading_rules` |

## 4. Cambios incorporados al diseño físico

En `postgresql-physical-schema.md`:

1. `market_instruments` se limita a identidad relativamente estable y ya no exige que los activos base/cotizados estén resueltos en el catálogo interno.
2. Se conservan obligatoriamente los códigos nativos base/cotizado. Los FKs a `assets` son nullable y deben ser ambos NULL o ambos informados.
3. Se incorpora `instrument_identifiers` para conservar las distintas claves y alias de interfaces sin colapsarlos.
4. Se separan estado nativo y estado normalizado en `instrument_metadata_versions`.
5. Se conservan `pair_decimals` y `lot_decimals` como atributos de Kraken sin inferir reglas de incremento.
6. Se incorpora `instrument_trading_rules` para representar por separado `PRICE_FILTER`, `LOT_SIZE`, `MARKET_LOT_SIZE`, `MIN_NOTIONAL`, `NOTIONAL`, reglas Kraken y futuras reglas adicionales.
7. Los parámetros numéricos de reglas se conservan como cadenas decimales dentro del JSON; la aplicación debe convertirlos a Decimal, nunca a float binario.
8. El historial de metadata es append-only y diferencia `observed_at` de `valid_from/valid_until`.

## 5. Restricciones que deben probarse

Las siguientes pruebas deben añadirse a la futura suite de integración PostgreSQL, usando fixtures sintéticos:

- Un instrumento puede tener varios alias con namespaces diferentes sin crear instrumentos duplicados.
- La misma cadena de símbolo puede existir en fuentes diferentes sin colisión.
- La clave interna Kraken, `altname` y `wsname` quedan asociados al mismo instrumento cuando la evidencia de captura lo confirma.
- La ausencia de ID nativo no impide registrar un instrumento.
- Un instrumento con activos no resueltos conserva los códigos nativos y tiene ambos FKs canónicos NULL.
- No se permite que solo uno de `base_asset_id` y `quote_asset_id` esté resuelto.
- Un instrumento no puede asociarse al mismo activo canónico como base y cotización.
- Una versión histórica puede conservar estado distinto de la versión actual sin sobrescribirla.
- `LOT_SIZE` y `MARKET_LOT_SIZE` se almacenan como reglas distintas.
- `pair_decimals` y `lot_decimals` no producen automáticamente `price_tick` ni `quantity_step`.
- Las banderas de aplicabilidad de `MIN_NOTIONAL`/`NOTIONAL` permanecen en la versión de regla.
- Los valores decimales se conservan exactamente y los parámetros no se convierten a float.

## 6. Cuestiones pendientes antes del DDL

### P0 — Resolver activos canónicos

<badge>Diseño y pruebas implementados</badge>

La política está definida en `asset-identity-resolution-policy.md`, el diseño físico incorpora `asset_identity_resolution_reviews` y `asset_identifiers` conserva únicamente correspondencias aceptadas. `resolve_asset_identity` y las pruebas sintéticas verifican namespace/código/red exactos, evidencia obligatoria y bloqueo ante ambigüedad. No se han aprobado equivalencias reales entre `BTC`, `XBT`, `XXBT` ni entre `USD` y `ZUSD`: esas asociaciones permanecen pendientes de evidencia documental/empírica suficiente. Por tanto, el riesgo de inferencia automática queda cerrado en el diseño; la aprobación de mappings concretos sigue abierta.

### P1 — Unicidad de identificadores

La clave interna de Kraken y los identificadores de Binance deben contrastarse con respuestas actuales. Solo entonces se fijarán índices únicos parciales para `source_instrument_id` y para alias por namespace. Los alias históricos pueden cambiar o solaparse; no imponer unicidad temporal sin definir intervalos y correcciones.

### P1 — Vigencia de reglas

Las reglas de negociación deben versionarse como observaciones. Una nueva respuesta de metadata no debe actualizar la regla anterior. El sistema debe distinguir el momento de observación de la fecha de validez, que puede no estar publicada por la fuente.

### P1 — Filtros no mapeados

La lista de reglas de Binance y Kraken puede evolucionar. El parser debe conservar filtros desconocidos en una extensión estructurada, marcar la versión de mapping y generar alerta de compatibilidad; no descartarlos ni asumir que el filtro desconocido carece de efecto.

## 7. Evidencia y límites de validación

Esta revisión contrasta los documentos del repositorio con documentación pública oficial. No prueba que los campos concretos estén presentes en la respuesta actual de un símbolo específico, ni que el mapeo de parsers esté implementado correctamente.

No se realizaron capturas en vivo. La validación empírica de `BTCUSDT` en Binance Spot y el mercado BTC/USD de Kraken Spot sigue pendiente y debe respetar el protocolo de captura y las políticas de uso documentadas.

## 8. Fuentes oficiales consultadas

- Binance Spot — [Exchange information / REST API](https://developers.binance.info/en/docs/catalog/core-trading-spot-trading/api/rest-api/general).
- Binance Spot — [Filters](https://github.com/binance/binance-spot-api-docs/blob/master/filters.md).
- Kraken — [API symbols and tickers](https://support.kraken.com/articles/360000920306-api-symbols-and-tickers).
- Kraken — [Spot API error messages](https://docs-legacy.kraken.com/api/docs/guides/spot-errors/).

La documentación de Kraken sobre símbolos fue actualizada el 29 de octubre de 2026, según la página consultada. La documentación de filtros Binance consultada pertenece al repositorio oficial de especificaciones Spot.

## 9. Próximo paso

1. Definir la resolución de activos canónicos y sus identificadores/alias.
2. Añadir fixtures sintéticos de metadata para Binance y Kraken que cubran las diferencias descritas.
3. Ejecutar parsers y pruebas de contrato sin red; separar resultados sintéticos de evidencia empírica.
4. Tras la aceptación, preparar DDL PostgreSQL y pruebas de integridad referencial.
