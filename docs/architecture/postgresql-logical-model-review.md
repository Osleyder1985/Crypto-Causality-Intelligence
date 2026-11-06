# Revisión técnica del modelo lógico de PostgreSQL

- **Estado:** revisión de diseño; cambios propuestos, pendientes de incorporar al modelo.
- **Fecha:** 2026-11-06.
- **Documento revisado:** `postgresql-logical-data-model.md`.
- **Decisión relacionada:** ADR-001.
- **PR de trabajo:** #16.

## 1. Dictamen

El modelo cubre correctamente los dominios principales: fuentes, endpoints, activos, instrumentos, adquisiciones, datasets, validaciones, transformaciones e investigación. La separación entre PostgreSQL, Parquet y DuckDB es coherente con ADR-001.

**Todavía no debe convertirse directamente en migraciones SQL.** Hay relaciones y restricciones de integridad que el texto conceptual menciona, pero que no están representadas de forma suficiente para impedir inconsistencias en la base de datos.

La prioridad no es añadir muchas entidades, sino cerrar la trazabilidad y la integridad entre entidades existentes.

## 2. Hallazgos que deben resolverse antes de escribir migraciones

### P0 — Trazabilidad de autorización aplicada a cada dataset

**Problema:** `source_usage_policies` registra decisiones de uso, pero `dataset_sources` no identifica qué política y qué evidencia justificaron la adquisición o persistencia de cada contribución.

**Riesgo:** posteriormente no se podrá demostrar con precisión qué autorización se evaluó para un dataset concreto, en qué momento y para qué uso.

**Corrección propuesta:**
- Añadir `source_usage_policy_id` nullable a `dataset_sources`, con FK a la política efectivamente evaluada.
- Registrar en esa relación el uso concreto evaluado y el instante de evaluación (`permission_evaluated_at`).
- La aplicación debe bloquear la persistencia si no existe una política aplicable, vigente y autorizante. La FK por sí sola no demuestra que la política sea válida.
- Conservar la evidencia histórica de la política; las revisiones crean nuevas filas y no reescriben decisiones anteriores.

La misma comprobación debe ejecutarse antes de crear un artefacto persistente, no solo al registrar posteriormente su procedencia.

### P0 — Relación explícita entre Runs y datasets producidos

**Problema:** la sección de relaciones afirma que un Run puede producir varios datasets, pero no existe una relación directa que lo represente. La procedencia mediante `dataset_sources` no cubre datasets sintéticos, resultados analíticos o artefactos generados sin una solicitud de adquisición.

**Corrección propuesta:**
- Crear `ingestion_run_datasets` o, preferiblemente, una relación general `run_datasets` si se decide que distintos tipos de ejecuciones producirán artefactos.
- Registrar el rol del dataset en la ejecución: `source_capture`, `normalized`, `validation_report`, `derived` o `analytical_result`, usando un vocabulario controlado.
- Mantener `dataset_sources` para procedencia de proveedores y `dataset_lineage` para dependencias de transformación. Son relaciones distintas y no deben sustituirse entre sí.

### P0 — Integridad entre fuente, endpoint e instrumento

**Problema:** `ingestion_requests` contiene `data_endpoint_id` y opcionalmente `market_instrument_id`, pero las FKs simples no impiden asociar un endpoint de Binance con un instrumento de Kraken. También existe riesgo de contradicción entre `dataset_sources.data_source_id`, endpoint, instrumento y solicitud.

**Corrección propuesta:**
- Definir claves candidatas compuestas en las entidades correspondientes, por ejemplo `(id, data_source_id)`.
- Usar FKs compuestas para exigir que endpoint, instrumento y solicitud pertenezcan a la misma fuente cuando esa relación sea aplicable.
- Si se mantiene `data_source_id` redundante en `dataset_sources`, imponer la consistencia mediante FK compuesta o eliminar la redundancia y derivar la fuente a través de la entidad referenciada.
- Documentar excepciones para datasets derivados de múltiples fuentes: cada fila de procedencia debe representar una contribución coherente.

### P1 — Versionado histórico de metadata de instrumentos

**Problema:** `market_instruments` contiene campos mutables como `instrument_status` y `metadata`, junto con `valid_from` y `valid_until`, pero no define cómo conservar cambios sucesivos sin sobrescribir el estado anterior.

**Corrección propuesta:**
- Separar la identidad estable del instrumento de sus observaciones/versiones de metadata.
- Añadir una entidad como `instrument_metadata_versions`, con fuente de evidencia, intervalo de validez, instante de observación y referencia al dataset o captura que la respalda.
- Mantener filtros y reglas específicas del proveedor como metadata versionada, sin convertirlos prematuramente en columnas universales.
- Definir si la validez representa el periodo en que la regla aplica en el mercado o el periodo en que el proyecto conoció esa regla. Son tiempos diferentes y no deben confundirse.

### P1 — Aplicabilidad y evidencia de políticas

**Problema:** `source_usage_policies` permite `policy_scope=product`, pero no existe una entidad de producto/plan ni un campo estructurado que identifique con precisión la versión del documento contractual o el alcance revisado.

**Corrección propuesta:**
- Registrar el producto o plan aplicable mediante un identificador textual estable o una entidad específica si la complejidad lo justifica.
- Añadir referencia de versión/fecha del documento, hash de la evidencia cuando esté disponible y fecha de captura/revisión.
- Precisar cómo se resuelve la precedencia entre política de proveedor, producto, endpoint y tipo de dato. Una política más general no debe anular una restricción específica.
- Mantener `unknown`, `pending_confirmation`, vencida o ambigua como estados que bloquean persistencia.

### P1 — Integridad temporal y estados

Añadir restricciones de base de datos, además de validación de aplicación:

- `finished_at IS NULL OR finished_at >= started_at` en ejecuciones y transformaciones.
- `completed_at IS NULL OR completed_at >= requested_at` en solicitudes.
- `valid_until IS NULL OR valid_from IS NULL OR valid_until > valid_from` en vigencias.
- Conteos de validación no negativos y coherentes: `checks_total = checks_passed + checks_failed`, si los controles omitidos se contabilizan por separado.
- `attempt_number > 0`, `records_received >= 0`, tamaños y conteos de datasets no negativos.
- Estados restringidos mediante `CHECK` y transiciones de estado validadas en la capa de aplicación.
- Prohibir que una ejecución finalizada vuelva a estado `running` sin crear una nueva ejecución.

### P1 — Identidad de activos y mercados

**Problema:** `assets.network` como atributo único puede ser insuficiente para activos que existen en varias redes o representaciones envueltas. Un símbolo o código de activo no identifica de forma global una entidad.

**Corrección propuesta:**
- Mantener `assets` como identidad canónica del activo.
- Modelar identificadores externos mediante una tabla `asset_identifiers` con namespace/proveedor, red, identificador externo, vigencia y evidencia.
- No forzar la resolución de activos ambiguos.
- La identidad del instrumento debe incluir el mercado/segmento necesario para evitar colisiones futuras; la restricción única final se decidirá con contratos reales de cada proveedor.

## 3. Ajustes adicionales recomendados

1. **Política de borrado:** documentar explícitamente `ON DELETE RESTRICT` para entidades históricas y reservar `CASCADE` para tablas puente cuya eliminación no destruya evidencia.
2. **Datasets eliminados:** definir si `storage_uri` se conserva como referencia lógica o se anonimiza al pasar a `deleted`; el tombstone no debe mantener información que la obligación de eliminación exija retirar.
3. **Hashes:** especificar algoritmo y formato; SHA-256 en hexadecimal minúsculo, longitud 64, si se mantiene como estándar del proyecto.
4. **Claves de dataset:** mantener `(dataset_key, version)` como unicidad lógica y hacer inmutable cada versión publicada.
5. **Linaje:** mantener PK compuesta y prevenir ciclos en el servicio de aplicación o mediante mecanismo transaccional explícito. Una FK no evita ciclos.
6. **JSONB:** reservarlo para extensiones variables; no usarlo para sustituir relaciones, claves o atributos que necesiten integridad referencial y consultas frecuentes.
7. **Auditoría:** decidir si se necesita una tabla de eventos de auditoría para cambios administrativos de políticas, fuentes y estados de retención. No registrar secretos ni cuerpos de respuesta.

## 4. Orden recomendado para cerrar el diseño

1. Resolver los tres hallazgos P0.
2. Incorporar versionado de metadata y evidencia de políticas.
3. Definir restricciones temporales, estados y reglas de borrado.
4. Cerrar identidad de activos/instrumentos y claves candidatas.
5. Actualizar el diagrama entidad-relación.
6. Revisar el modelo completo contra los contratos canónicos OHLCV y metadata.
7. Solo entonces redactar migraciones SQL versionadas y pruebas de integridad.

## 5. Fuera de alcance de esta revisión

Esta revisión no crea tablas físicas, no ejecuta migraciones, no inicia servicios PostgreSQL, no escribe datasets Parquet y no consulta APIs de proveedores. Tampoco cambia Runs históricos ni decide la eliminación de artefactos existentes.

Las pruebas de implementación deberán usar exclusivamente datos sintéticos hasta que los permisos de persistencia de datos reales estén resueltos.

## 6. Criterio de aceptación

El modelo estará listo para migraciones cuando:

- Cada dataset tenga trazabilidad de ejecución, fuentes contribuyentes y política evaluada.
- La base de datos impida relaciones cruzadas incompatibles entre fuente, endpoint e instrumento.
- Los cambios de metadata y permisos sean históricamente trazables.
- Las restricciones temporales, estados y reglas de borrado estén definidas.
- El diagrama y el diccionario de datos representen las mismas relaciones.
- Se pueda implementar el modelo desde cero y comprobarlo con pruebas de integridad usando datos sintéticos.
