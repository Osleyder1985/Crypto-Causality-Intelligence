# Esquemas canónicos de datos de mercado

- **Estado:** propuesta técnica para revisión; no implementada.
- **Versión del contrato:** 0.1.0-draft.
- **Fecha:** 2026-11-06.
- **Decisión relacionada:** ADR-001.
- **Modelo relacional relacionado:** `postgresql-logical-data-model.md`.
- **PR de trabajo:** #15.

## 1. Propósito

Definir contratos independientes del proveedor para las primeras familias de datos de mercado: velas OHLCV y metadatos de instrumentos. Los contratos permiten normalizar datos de Binance Spot, Kraken Spot y otras fuentes sin borrar diferencias semánticas ni atribuir a un proveedor datos procedentes de otro.

Este documento define semántica y estructura lógica. No constituye una autorización para adquirir, almacenar o redistribuir datos. Tampoco fija todavía precisión decimal física, particionamiento definitivo ni migraciones SQL.

## 2. Capas y reglas generales

### 2.1 Separación de capas

| Capa | Contenido | Regla |
|---|---|---|
| `raw` | Payload original o representación fiel permitida | No renombrar ni reinterpretar campos del proveedor. Inmutable; las nuevas capturas o revisiones son nuevas observaciones. |
| `normalized` | Registros que cumplen el contrato canónico | Normalizar nombres, unidades e instantes sin eliminar valores nativos ni incertidumbres. |
| `derived` | Métricas, agregados, features y resultados de investigación | Cada resultado identifica entradas, transformación, parámetros y versiones. |

La existencia de una capa no obliga a persistirla. La política aplicable a la fuente, endpoint, tipo de dato y uso debe autorizar la persistencia antes de escribir valores. Si la autorización es desconocida, vencida, ambigua o no aplicable, se bloquea la escritura.

### 2.2 Convenciones comunes

- Los nombres de campos se escriben en `snake_case` y en inglés.
- Los identificadores internos son UUID. Los identificadores nativos siempre se conservan en su namespace de proveedor.
- Los instantes canónicos representan UTC. La zona, texto y precisión originales se conservan en los metadatos de procedencia cuando estén disponibles.
- Los valores monetarios y cantidades se tratan como decimales exactos. No convertir a binario flotante (`FLOAT`/`DOUBLE`) durante la normalización.
- Los valores no proporcionados por una fuente se representan como `null`, nunca como cero.
- Los campos desconocidos no se completan por inferencia. Las conversiones requieren una regla documentada y versionada.
- Las columnas de procedencia deben permitir rastrear cada registro hasta fuente, endpoint, solicitud/captura, instrumento y versión de esquema.
- El esquema físico de Parquet debe incluir `schema_name` y `schema_version` en el manifiesto del dataset; no depender exclusivamente de metadatos internos del archivo.

## 3. Contrato `market_ohlcv`

### 3.1 Unidad de registro

Una fila representa una vela de un instrumento concreto de un proveedor y mercado, para un intervalo definido. Una vela de Binance Spot y otra de Kraken Spot son observaciones distintas aunque tengan el mismo par, intervalo y valores.

El contrato no convierte automáticamente datos agregados de CoinGecko u otro agregador en datos de un exchange. La fuente y el método de agregación deben permanecer explícitos.

### 3.2 Campos canónicos

| Campo | Tipo lógico | Obligatorio | Definición |
|---|---|---:|---|
| `instrument_id` | UUID | Sí | Identidad interna del instrumento específico del proveedor/mercado. |
| `source_key` | string | Sí | Namespace estable de la fuente, por ejemplo `binance_spot` o `kraken_spot`. |
| `native_symbol` | string | Sí | Símbolo exactamente como lo identifica el proveedor en el contexto del mercado. |
| `interval_code` | string | Sí | Código canónico del intervalo, por ejemplo `1m`, `5m`, `1h`, `1d`, `1w`, `1M`. |
| `interval_kind` | enum/string controlado | Sí | `fixed` o `calendar`; evita asumir que todos los intervalos tienen duración fija. |
| `open_time` | timestamp UTC | Sí | Inicio del intervalo de la vela. |
| `close_time_exclusive` | timestamp UTC | Sí | Límite final exclusivo del intervalo canónico. |
| `open` | decimal exacto | Sí | Precio de apertura. |
| `high` | decimal exacto | Sí | Precio máximo. |
| `low` | decimal exacto | Sí | Precio mínimo. |
| `close` | decimal exacto | Sí | Precio de cierre reportado por la fuente. |
| `volume_base` | decimal exacto nullable | Condicional | Volumen expresado en la unidad del activo base. Null si no está disponible o no puede determinarse. |
| `volume_quote` | decimal exacto nullable | No | Volumen expresado en la unidad del activo cotizado, solo si la fuente lo proporciona o existe una conversión explícita autorizada y versionada. |
| `trade_count` | int64 nullable | No | Número de operaciones, únicamente cuando la fuente lo proporciona con esa semántica. |
| `is_final` | boolean nullable | No | Indica si la fuente declara la vela final/cerrada. Null si el estado no puede determinarse. |
| `source_record_id` | string nullable | No | Identificador nativo del registro, si existe. |
| `source_open_time_raw` | string/valor raw nullable | No | Representación nativa del inicio, conservada para auditoría. |
| `source_close_time_raw` | string/valor raw nullable | No | Representación nativa del cierre, conservada para auditoría. |
| `captured_at` | timestamp UTC | Sí | Momento en que el sistema obtuvo la respuesta. |
| `available_at` | timestamp UTC nullable | No | Primer momento defendible de disponibilidad para uso analítico, según la política point-in-time. |
| `revision_number` | int32 | Sí | Revisión observada dentro del ámbito definido por el adapter/dataset; inicia en 1. |
| `quality_status` | string controlado | Sí | `valid`, `valid_with_warnings`, `quarantined`, `rejected` o `unknown`. |
| `schema_version` | string | Sí | Versión del contrato canónico aplicado. |

Los campos de procedencia del dataset —como `data_source_id`, `data_endpoint_id`, `ingestion_request_id`, `dataset_id` y `normalization_run_id`— se registran en el manifiesto y/o en el catálogo relacional. Si el formato de distribución exige un archivo autónomo, se podrá repetir una selección de esos identificadores por fila sin cambiar su significado.

### 3.3 Semántica temporal

- El intervalo canónico se interpreta como semiabierto: `[open_time, close_time_exclusive)`.
- `open_time` identifica la vela y es el ancla temporal de la serie.
- No se debe copiar directamente un timestamp de cierre del proveedor a `close_time_exclusive` sin verificar si la fuente expresa el último milisegundo incluido, el límite exclusivo o una convención diferente.
- Los intervalos fijos y calendáricos no son intercambiables. `1M` es un mes calendario, no 30 días.
- Las velas diarias/semanales deben respetar la zona y el anclaje que defina la fuente. La normalización a UTC no autoriza a cambiar el día de mercado.
- `captured_at`, `available_at` y el cierre de la vela son instantes diferentes. Una vela no se considera disponible al cierre solo por haber terminado su intervalo.
- Una vela todavía abierta puede aparecer como provisional. No se debe sobrescribir una revisión provisional con una final; se registra una nueva revisión o snapshot, según la política de versionado del dataset.

### 3.4 Semántica numérica y unidades

- `open`, `high`, `low` y `close` están denominados en la unidad del activo cotizado por unidad del activo base.
- `volume_base` se expresa en el activo base; `volume_quote`, en el activo cotizado. No utilizar el nombre genérico `volume` en la capa canónica.
- `volume_quote` no se calcula como `close × volume_base`: esa operación no representa necesariamente el volumen cotizado negociado durante toda la vela.
- No inferir `trade_count`, volumen base/cotizado ni estado final cuando el proveedor no los suministra.
- Los importes deben conservar escala suficiente para representar exactamente el valor de origen. La precisión y escala físicas de Parquet (`DECIMAL(p,s)`) se fijarán después de medir rangos y escalas reales de los instrumentos y revisar los límites de compatibilidad de Parquet, DuckDB y los adapters. Hasta entonces, no se impondrá una precisión universal.

### 3.5 Clave lógica y duplicados

La identidad lógica mínima de una vela es:

`(instrument_id, interval_code, open_time)`

Esta clave identifica el punto temporal de la vela, pero no autoriza a descartar revisiones. Para la capa de captura/versionado se debe distinguir la misma clave lógica de las observaciones recibidas en diferentes momentos. La unicidad física se definirá en función de la estrategia de snapshots y datasets inmutables.

No deduplicar velas de proveedores diferentes, instrumentos diferentes o cotizaciones distintas. USD y USDT permanecen como activos de cotización distintos.

### 3.6 Validaciones mínimas

1. `open_time < close_time_exclusive`.
2. `high >= open`, `high >= close`, `high >= low`.
3. `low <= open`, `low <= close`, `low <= high`.
4. Precios no negativos; cero solo se admite si la semántica de la fuente y el instrumento lo permiten.
5. Volúmenes no negativos cuando estén presentes.
6. `trade_count >= 0` cuando esté presente.
7. Los valores cumplen la precisión declarada para el instrumento/fuente; no redondear silenciosamente.
8. La alineación de `open_time` con el intervalo se valida según la convención específica de la fuente y el tipo de intervalo.
9. `captured_at` no se sustituye por `available_at`; se valida la coherencia temporal sin asumir que ambas marcas son iguales.
10. Una violación produce un resultado de validación y, cuando corresponda, cuarentena; no elimina el registro raw.

## 4. Contrato `market_instrument_metadata`

### 4.1 Unidad de registro

Una fila representa una observación versionada de los metadatos de un instrumento en una fuente concreta. No representa una identidad global del activo. La identidad canónica del activo base y del activo cotizado se resuelve por separado mediante `assets` y relaciones de identificación.

### 4.2 Campos canónicos

| Campo | Tipo lógico | Obligatorio | Definición |
|---|---|---:|---|
| `instrument_id` | UUID | Sí | ID interno estable del instrumento específico de fuente/mercado. |
| `source_key` | string | Sí | Namespace del proveedor. |
| `source_instrument_id` | string nullable | No | ID nativo del instrumento, si existe. |
| `native_symbol` | string | Sí | Símbolo nativo, conservado exactamente. |
| `canonical_symbol` | string nullable | No | Representación legible canónica; no reemplaza el símbolo nativo ni actúa como clave. |
| `base_asset_id` | UUID nullable | Condicional | ID canónico del activo base cuando la identidad esté resuelta. |
| `quote_asset_id` | UUID nullable | Condicional | ID canónico del activo cotizado cuando la identidad esté resuelta. |
| `base_asset_code_native` | string | Sí | Código del activo base según la fuente. |
| `quote_asset_code_native` | string | Sí | Código del activo cotizado según la fuente. |
| `market_type` | string controlado | Sí | Por ejemplo `spot`, `perpetual`, `future` u otro tipo explícitamente soportado. |
| `instrument_status` | string | Sí | Estado reportado por la fuente, preservando el valor nativo y mapeando a un vocabulario canónico documentado. |
| `price_tick` | decimal exacto nullable | No | Incremento mínimo de precio, si la fuente lo define. |
| `quantity_step` | decimal exacto nullable | No | Incremento mínimo de cantidad, si la fuente lo define. |
| `min_quantity` | decimal exacto nullable | No | Cantidad mínima, si está definida. |
| `max_quantity` | decimal exacto nullable | No | Cantidad máxima, si está definida. |
| `min_notional` | decimal exacto nullable | No | Notional mínimo, conservando la unidad y condición aplicable. |
| `price_precision` | int32 nullable | No | Precisión decimal declarada, si la fuente la define; no sustituye `price_tick`. |
| `quantity_precision` | int32 nullable | No | Precisión de cantidad declarada, si la fuente la define; no sustituye `quantity_step`. |
| `listing_time` | timestamp UTC nullable | No | Instante de listado, solo si está documentado por la fuente. |
| `delisting_time` | timestamp UTC nullable | No | Instante de retiro, solo si está documentado por la fuente. |
| `observed_at` | timestamp UTC | Sí | Momento en que el sistema observó esta versión de metadata. |
| `valid_from` | timestamp UTC nullable | No | Inicio de vigencia declarado o defendible de esta versión. No equivale a `observed_at`. |
| `valid_to` | timestamp UTC nullable | No | Fin de vigencia, si se conoce. |
| `source_metadata_hash` | string nullable | No | Hash de la representación de metadata usada para detectar cambios. |
| `source_metadata_reference` | string nullable | No | Referencia al registro/payload raw permitido. |
| `quality_status` | string controlado | Sí | Estado de validación. |
| `schema_version` | string | Sí | Versión del contrato canónico aplicado. |

Los filtros y reglas de trading específicos del proveedor pueden variar por mercado, lado, tipo de orden, estado y fecha. La primera versión no intenta aplanar todas esas reglas en columnas universales. Los filtros no representables en los campos anteriores se conservan en una extensión estructurada y tipada por adapter, junto con su versión de mapeo; nunca se descartan silenciosamente.

### 4.3 Tiempo de observación y vigencia

- `observed_at` responde: ¿cuándo conoció el sistema esta versión?
- `valid_from`/`valid_to` responden: ¿durante qué periodo se considera vigente esta versión según evidencia de la fuente?
- Si la fuente no informa la vigencia y no existe evidencia fiable, los campos de vigencia permanecen null. No se retrotrae `valid_from` a `listing_time` por suposición.
- Un cambio detectado genera una nueva observación versionada; no se sobrescribe el registro anterior.
- Para reconstrucciones point-in-time, se selecciona la versión conocida a la fecha de corte mediante `observed_at`, sin confundirla con la vigencia declarada.

### 4.4 Identidad y unicidad

La identidad de un instrumento está acotada por fuente, mercado y namespace del proveedor. El símbolo por sí solo no es globalmente único. El mapeo a `base_asset_id` y `quote_asset_id` puede quedar sin resolver hasta reunir evidencia suficiente.

La clave de observación debe permitir múltiples versiones de metadata para el mismo instrumento. No imponer unicidad global sobre `native_symbol`. La restricción concreta se definirá en PostgreSQL cuando se conozcan las reglas de reutilización de identificadores de cada fuente.

## 5. Representación física inicial

La correspondencia física se mantiene deliberadamente conservadora:

| Tipo lógico | PostgreSQL (cuando aplique) | Parquet (propuesta) |
|---|---|---|
| UUID | `UUID` | `FIXED_LEN_BYTE_ARRAY(16)` o representación interoperable acordada |
| string | `TEXT` | `STRING` |
| boolean | `BOOLEAN` | `BOOLEAN` |
| int32/int64 | `INTEGER`/`BIGINT` | `INT32`/`INT64` |
| timestamp UTC | `TIMESTAMPTZ` | `TIMESTAMP(MICROS, isAdjustedToUTC=true)` |
| decimal exacto | `NUMERIC` | `DECIMAL(p,s)`, con `p,s` por definir mediante evidencia |

La elección de codificación UUID en Parquet deberá probarse con DuckDB y las herramientas Python seleccionadas. La precisión decimal no se fija en esta propuesta. Se prohíbe degradar silenciosamente decimales a `DOUBLE`.

## 6. Versionado y compatibilidad

- Los contratos usan versionado semántico: `MAJOR.MINOR.PATCH`.
- Cambio incompatible de significado, eliminación o cambio de tipo obligatorio: incremento MAJOR.
- Campo opcional nuevo o ampliación compatible: incremento MINOR.
- Corrección documental que no cambia el contrato: incremento PATCH.
- Cada dataset declara `schema_name`, `schema_version`, `stage`, fuente, ventana temporal, conteo y checksum en su manifiesto.
- Los adapters declaran la versión de contrato que producen. La actualización de un adapter no debe cambiar silenciosamente la semántica de datos ya normalizados.
- Una nueva normalización genera una nueva versión de dataset; no sobrescribe artefactos inmutables.

## 7. Ejemplo ilustrativo (sintético)

El siguiente ejemplo muestra la forma del registro, no datos reales de mercado ni una afirmación sobre el formato de respuesta de un proveedor:

```json
{
  "instrument_id": "00000000-0000-4000-8000-000000000001",
  "source_key": "example_spot",
  "native_symbol": "AAA/BBB",
  "interval_code": "1m",
  "interval_kind": "fixed",
  "open_time": "2026-01-01T00:00:00Z",
  "close_time_exclusive": "2026-01-01T00:01:00Z",
  "open": "10.125",
  "high": "10.250",
  "low": "10.000",
  "close": "10.200",
  "volume_base": "125.50",
  "volume_quote": null,
  "trade_count": null,
  "is_final": true,
  "captured_at": "2026-01-01T00:01:03Z",
  "available_at": "2026-01-01T00:01:03Z",
  "revision_number": 1,
  "quality_status": "valid",
  "schema_version": "0.1.0-draft"
}
```

Los decimales se muestran como cadenas en JSON para evitar pérdida de precisión por parsers que convierten números JSON a coma flotante binaria. La representación Parquet utilizará decimal lógico con precisión/escala aprobadas.

## 8. Decisiones pendientes antes de implementación

1. Verificar con documentación y muestras autorizadas las convenciones de timestamp y cierre de velas de Binance Spot y Kraken Spot.
2. Comparar los campos OHLCV disponibles en ambos proveedores y documentar las correspondencias que sean realmente equivalentes.
3. Medir rangos y escalas de precios y volúmenes para definir `DECIMAL(p,s)` sin truncamiento ni sobredimensionamiento injustificado.
4. Definir el tratamiento de revisiones, velas provisionales y republicaciones por proveedor.
5. Definir cómo representar reglas de trading/filtros que no tengan equivalencia común.
6. Probar interoperabilidad de tipos Parquet con DuckDB y Python.
7. Definir manifiesto de dataset y layout físico sin fijar particiones hasta medir volúmenes.
8. Revisar permisos y retención aplicables antes de persistir datos reales.

## 9. Criterios de aceptación

- [ ] Las velas de distintos proveedores o instrumentos no pueden confundirse ni deduplicarse entre sí.
- [ ] Los timestamps preservan semántica de intervalo, UTC, precisión y disponibilidad.
- [ ] Los volúmenes tienen unidad explícita y no se infieren a partir del precio de cierre.
- [ ] Los valores ausentes no se convierten en cero.
- [ ] Los decimales se conservan sin conversión silenciosa a coma flotante.
- [ ] Las observaciones de metadata conservan tanto el momento de observación como la vigencia declarada.
- [ ] Los cambios de metadata y revisiones de velas son trazables.
- [ ] Los registros normalizados pueden rastrearse a su fuente y captura.
- [ ] La persistencia permanece bloqueada cuando la política aplicable no autoriza el uso.
- [ ] Las pruebas iniciales utilizan datos sintéticos o datos reales cuya persistencia esté autorizada.
