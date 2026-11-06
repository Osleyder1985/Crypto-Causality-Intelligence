# Diseño físico de PostgreSQL

- **Estado:** especificación física propuesta v0.1; pendiente de revisión e implementación.
- **Fecha:** 2026-11-06.
- **Modelo lógico:** `postgresql-logical-data-model.md`, propuesta v0.2.
- **Revisión:** `postgresql-logical-model-review.md`.
- **Decisión relacionada:** `ADR-001-storage-and-analytics-architecture.md`.
- **Issue / PR:** #14 / #15.

## 1. Objetivo y límites

Convertir el modelo lógico en una especificación implementable y verificable. Este documento fija nombres físicos, tipos, claves, restricciones, índices, reglas temporales y orden de migraciones. No crea todavía tablas, no ejecuta SQL y no despliega PostgreSQL.

PostgreSQL almacena catálogo, operaciones, procedencia, permisos evaluados y referencias a artefactos. No almacena las series históricas OHLCV como tablas de hechos: los datasets autorizados residen en Parquet y DuckDB los consulta.

Las pruebas de esquema utilizarán exclusivamente datos sintéticos. La especificación no concede autorización para persistir datos de Binance, Kraken, CoinGecko ni de otros terceros.

## 2. Decisiones físicas generales

### 2.1 Base de datos y namespace

- Una base de datos de aplicación, denominada inicialmente `crypto_causality_intelligence`.
- Un esquema de aplicación: `cci`.
- Las tablas y columnas usan `snake_case` en inglés.
- No se crean esquemas `catalog`, `ops` y `research` en esta fase. Los dominios ya se distinguen por las tablas y una división física prematura aumentaría grants, migraciones y complejidad de consultas sin una necesidad de aislamiento demostrada.
- Las extensiones PostgreSQL se evitan en la primera migración. En particular, no se exige `btree_gist`; los solapamientos temporales se validarán transaccionalmente hasta que exista una justificación para una exclusión GiST.

### 2.2 Tipos

| Uso | Tipo PostgreSQL | Regla |
|---|---|---|
| Identificadores internos | `UUID` | PK generada por la aplicación o `gen_random_uuid()`; no usar UUID como dato externo. |
| Códigos, nombres, estados y referencias | `TEXT` | Evitar `CHAR(n)`; limitar longitudes en aplicación o CHECK cuando haya un límite contractual. |
| Instantes | `TIMESTAMPTZ` | Interpretados y escritos en UTC; PostgreSQL los almacena como instantes, no conserva la zona original. |
| Conteos y tamaños | `BIGINT` | CHECK no negativo; `INTEGER` para intentos, versiones y contadores acotados. |
| Precios, cantidades y reglas de mercado | `NUMERIC` | Exactitud decimal; sin precisión/escala universal hasta medir valores reales. |
| Configuración y extensiones | `JSONB` | Solo atributos variables; no sustituye relaciones ni campos consultados con frecuencia. |
| Indicadores | `BOOLEAN` | NULL solo cuando el estado es realmente desconocido/no proporcionado. |
| Hash SHA-256 | `TEXT` | Hexadecimal minúsculo de 64 caracteres, CHECK de formato. |
| Direcciones y referencias de almacenamiento | `TEXT` | URI lógica; no asumir proveedor cloud ni exponer rutas locales del operador. |

No se usarán tipos ENUM nativos inicialmente. Los vocabularios controlados se implementan con CHECK; un catálogo separado se justifica solo si los valores necesitan administración independiente.

### 2.3 Convenciones de claves y borrado

- Todas las tablas maestras e históricas usan PK UUID, salvo las tablas puente con PK compuesta explícita.
- Las FKs históricas usan `ON DELETE RESTRICT ON UPDATE RESTRICT`.
- `CASCADE` queda reservado a tablas puente puramente asociativas y solo si la eliminación de la entidad padre está permitida por política. En el primer diseño se prefiere RESTRICT incluso en esas tablas.
- No se permite borrar fuentes, endpoints, instrumentos, Runs, políticas, datasets publicados, validaciones, transformaciones ni experimentos que tengan evidencia dependiente.
- Las eliminaciones lógicas no sustituyen las obligaciones de retención o supresión de datos. El estado tombstone no debe conservar datos que una obligación exija eliminar.
- No se define `updated_at` como sustituto de historial. Las políticas y observaciones de metadata se versionan mediante nuevas filas.

## 3. Inventario físico

Todas las tablas siguientes pertenecen a `cci`.

| Tabla | PK | Responsabilidad |
|---|---|---|
| `data_sources` | `id` | Proveedores y sistemas de origen. |
| `data_endpoints` | `id` | Productos y familias de endpoints. |
| `source_usage_policies` | `id` | Evidencia versionada de condiciones de uso. |
| `policy_evaluations` | `id` | Decisión concreta de aplicabilidad de una política a endpoint, uso e instante. |
| `assets` | `id` | Identidad canónica de activos. |
| `asset_identifiers` | `id` | Identificadores externos con correspondencia canónica aceptada. |\n| `asset_identity_resolution_reviews` | `id` | Candidatos, decisiones y evidencia de resolución, incluidas ambigüedad y pendientes. |
| `market_instruments` | `id` | Identidad estable de instrumentos específicos de una fuente/mercado. |
| `instrument_identifiers` | `id` | Claves y alias nativos del instrumento por interfaz/namespace. |
| `instrument_metadata_versions` | `id` | Observaciones históricas de metadata y estado. |
| `instrument_trading_rules` | `id` | Reglas de negociación versionadas por tipo y ámbito. |
| `ingestion_runs` | `id` | Ejecuciones lógicas. |
| `ingestion_requests` | `id` | Solicitudes e intentos a endpoints. |
| `datasets` | `id` | Catálogo de artefactos versionados. |
| `run_datasets` | `ingestion_run_id, dataset_id, dataset_role` | Datasets producidos/registrados por Runs. |
| `dataset_sources` | `id` | Procedencia y evaluación de política por contribución. |
| `dataset_lineage` | `input_dataset_id, output_dataset_id, transformation_run_id` | Linaje entre datasets. |
| `data_validations` | `id` | Resultados históricos de validación. |
| `transformations` | `id` | Definiciones versionadas de transformaciones. |
| `transformation_runs` | `id` | Ejecuciones concretas de transformaciones. |
| `research_experiments` | `id` | Experimentos reproducibles. |
| `research_hypotheses` | `id` | Hipótesis y criterios de falsación. |
| `experiment_datasets` | `experiment_id, dataset_id, dataset_role` | Datasets utilizados por experimentos. |

## 4. Definición de columnas y restricciones

La notación `NULL` indica nulabilidad. Los campos no listados como nullable son `NOT NULL`. Todas las tablas incorporan `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`, salvo que se indique una semántica específica. Los defaults no sustituyen la validación de la aplicación.

### 4.1 Fuentes, endpoints y políticas

**`data_sources`**
- `id UUID PK`
- `source_key TEXT NOT NULL UNIQUE`
- `display_name TEXT NOT NULL`
- `source_type TEXT NOT NULL`: CHECK en `exchange, aggregator, on_chain, news, calendar, synthetic, internal, other`.
- `documentation_url TEXT NULL`
- `status TEXT NOT NULL`: CHECK en `active, paused, deprecated`.
- `created_at, updated_at TIMESTAMPTZ NOT NULL`.
- UNIQUE adicional `(id, source_key)` solo si una FK futura necesita garantizar el código junto con el UUID; de lo contrario, la PK y UNIQUE existentes bastan.

**`data_endpoints`**
- `id UUID PK`
- `data_source_id UUID NOT NULL FK data_sources(id)`
- `endpoint_key TEXT NOT NULL`
- `base_url TEXT NULL`, `resource_path TEXT NULL`
- `data_type TEXT NOT NULL`
- `documentation_url TEXT NULL`
- `status TEXT NOT NULL`: CHECK en `active, paused, deprecated`.
- `created_at TIMESTAMPTZ NOT NULL`
- UNIQUE `(data_source_id, endpoint_key)`
- UNIQUE candidato `(id, data_source_id)`, requerido por FKs compuestas de consistencia.

**`source_usage_policies`**
- `id UUID PK`
- `data_source_id UUID NOT NULL FK data_sources(id)`
- `data_endpoint_id UUID NULL`
- `policy_scope TEXT NOT NULL`: CHECK en `provider, product, endpoint, data_type`.
- `intended_use TEXT NOT NULL`: vocabulario controlado inicial `private_research, public_display, redistribution, commercial_use, internal_testing, other`.
- `permission_status TEXT NOT NULL`: CHECK en `allowed, restricted, denied, unknown, pending_confirmation`.
- `evidence_url TEXT NULL`, `evidence_reference TEXT NULL`
- `evidence_sha256 TEXT NULL`: si existe, formato SHA-256 hexadecimal.
- `reviewed_at TIMESTAMPTZ NULL`
- `valid_from TIMESTAMPTZ NOT NULL`, `valid_until TIMESTAMPTZ NULL`
- `retention_rule TEXT NULL`, `notes TEXT NULL`
- `created_at TIMESTAMPTZ NOT NULL`
- FK compuesta `(data_endpoint_id, data_source_id) -> data_endpoints(id, data_source_id)`; cuando `data_endpoint_id` sea NULL, la política tendrá alcance de fuente/producto/tipo según `policy_scope`.
- UNIQUE `(id, data_source_id)`, necesaria para la FK desde evaluaciones.
- CHECK `valid_until IS NULL OR valid_until > valid_from`.
- CHECK de coherencia: `policy_scope = 'endpoint'` requiere endpoint no nulo.
- Filas append-only. Una modificación de condiciones crea una nueva política; no se actualiza evidencia histórica.

**`policy_evaluations`**
- `id UUID PK`
- `source_usage_policy_id UUID NOT NULL`
- `data_source_id UUID NOT NULL FK data_sources(id)`
- `data_endpoint_id UUID NOT NULL`
- `data_type TEXT NOT NULL`
- `intended_use TEXT NOT NULL`
- `permission_status TEXT NOT NULL`: CHECK en `allowed, restricted, denied, unknown, pending_confirmation`.
- `evaluated_at TIMESTAMPTZ NOT NULL`
- `policy_valid_from_snapshot TIMESTAMPTZ NOT NULL`, `policy_valid_until_snapshot TIMESTAMPTZ NULL`
- `evidence_sha256 TEXT NULL`
- `decision_reference TEXT NULL` (identificador de la regla/protocolo que realizó la evaluación).
- `created_at TIMESTAMPTZ NOT NULL`
- FK compuesta `(source_usage_policy_id, data_source_id) -> source_usage_policies(id, data_source_id)`.
- FK compuesta `(data_endpoint_id, data_source_id) -> data_endpoints(id, data_source_id)`.
- UNIQUE `(id, data_source_id, data_endpoint_id, intended_use)`, requerida por `dataset_sources`.
- CHECK `policy_valid_until_snapshot IS NULL OR policy_valid_until_snapshot > policy_valid_from_snapshot`.
- Registro append-only. La evaluación materializa la decisión concreta, aunque la política de origen tenga alcance provider/product/data_type y no un endpoint específico.
- El servicio de autorización comprueba que la política cubra la fuente, endpoint, tipo, uso e instante evaluado. La FK garantiza coherencia referencial, no la validez jurídica de la interpretación.

La política aplicable se resuelve considerando fuente, endpoint, tipo de dato, uso previsto, vigencia y evidencia. No se asume que una política de proveedor cubra automáticamente todos sus productos.

### 4.2 Activos e instrumentos

**`assets`**
- `id UUID PK`
- `canonical_code TEXT NOT NULL UNIQUE` (clave interna estable; no se exige que sea ticker).
- `display_name TEXT NOT NULL`
- `asset_type TEXT NOT NULL`: CHECK en `crypto, fiat, stablecoin, tokenized_asset, other`.
- `network TEXT NULL` (atributo descriptivo; no es identidad universal).
- `external_identifiers JSONB NOT NULL DEFAULT '{}'` (extensión transitoria; no sustituye la tabla normalizada).
- `created_at TIMESTAMPTZ NOT NULL`.

**`asset_identity_resolution_reviews`**
- `id UUID PK`
- `namespace TEXT NOT NULL`
- `network TEXT NULL`
- `external_identifier TEXT NOT NULL` (código nativo exacto).
- `candidate_asset_id UUID NULL FK assets(id)`
- `resolution_status TEXT NOT NULL`: CHECK en `pending_review, accepted, rejected, ambiguous`.
- `evidence_reference TEXT NULL`
- `decision_reference TEXT NULL` (identidad del proceso/revisor o acta de decisión; nunca credenciales).
- `observed_at TIMESTAMPTZ NOT NULL`
- `reviewed_at TIMESTAMPTZ NULL`
- `valid_from TIMESTAMPTZ NULL`, `valid_until TIMESTAMPTZ NULL`
- CHECK: `valid_until IS NULL OR valid_from IS NULL OR valid_until > valid_from`.
- CHECK: `resolution_status <> 'accepted' OR (candidate_asset_id IS NOT NULL AND evidence_reference IS NOT NULL AND reviewed_at IS NOT NULL)`.
- Registro append-only. Una nueva decisión crea otra fila; no sobrescribir decisiones históricas.
- Índice `(namespace, network, external_identifier, observed_at DESC)`; índice parcial por `candidate_asset_id` cuando no sea NULL.
- Esta tabla conserva estados pendientes, ambiguos y rechazados; no autoriza por sí misma la asociación canónica.

**`asset_identifiers`**

- `id UUID PK`
- `asset_id UUID NOT NULL FK assets(id)`
- `namespace TEXT NOT NULL`
- `network TEXT NULL`
- `external_identifier TEXT NOT NULL`
- `valid_from TIMESTAMPTZ NULL`, `valid_until TIMESTAMPTZ NULL`
- `evidence_reference TEXT NULL`
- `created_at TIMESTAMPTZ NOT NULL`
- CHECK `valid_until IS NULL OR valid_from IS NULL OR valid_until > valid_from`.
- Índice de búsqueda `(namespace, network, external_identifier)`.
- No se impone UNIQUE simple con `valid_from`: PostgreSQL permite múltiples NULL en una restricción UNIQUE convencional y los identificadores pueden tener periodos históricos. Se implementarán índices únicos parciales para identidades vigentes sin fecha inicial y para observaciones con fecha inicial, una vez definida la política de correcciones.
- Esta tabla contiene solo correspondencias aceptadas. La evidencia y decisión aprobatoria deben existir en `asset_identity_resolution_reviews`; la aplicación impide solapamientos temporales del mismo identificador dentro de namespace/red bajo bloqueo transaccional.

**`market_instruments`**
- `id UUID PK`
- `data_source_id UUID NOT NULL FK data_sources(id)`
- `source_instrument_id TEXT NULL` (identificador estable del proveedor cuando exista; no se inventa si el proveedor no lo ofrece).
- `native_symbol TEXT NOT NULL` (símbolo de referencia conservado literalmente; no se considera globalmente único).
- `native_base_asset_code TEXT NOT NULL`
- `native_quote_asset_code TEXT NOT NULL`
- `base_asset_id UUID NULL FK assets(id)`
- `quote_asset_id UUID NULL FK assets(id)`
- `canonical_symbol TEXT NULL` (solo presentación; nunca clave).
- `market_type TEXT NOT NULL`: CHECK en `spot, perpetual, future, option, other`.
- `created_at TIMESTAMPTZ NOT NULL`
- UNIQUE candidato `(id, data_source_id)`.
- CHECK: `base_asset_id` y `quote_asset_id` son ambos NULL o ambos NOT NULL; si ambos existen deben ser distintos.
- No guardar estado cambiante ni reglas de negociación en esta tabla de identidad. No declarar UNIQUE global sobre `native_symbol`, ni asumir que `source_instrument_id` siempre existe.
- Índice parcial único recomendado: `(data_source_id, source_instrument_id, market_type) WHERE source_instrument_id IS NOT NULL`, sujeto a confirmar que la clave nativa es estable y única en cada API Spot.

**`instrument_identifiers`**
- `id UUID PK`
- `market_instrument_id UUID NOT NULL FK market_instruments(id)`
- `identifier_namespace TEXT NOT NULL` (por ejemplo `rest_pair_key`, `rest_altname`, `rest_wsname`, `websocket_symbol`, `provider_id`).
- `identifier_value TEXT NOT NULL` (conservado exactamente).
- `is_primary BOOLEAN NOT NULL DEFAULT false`
- `valid_from TIMESTAMPTZ NULL`, `valid_until TIMESTAMPTZ NULL`
- `observed_at TIMESTAMPTZ NOT NULL`
- `created_at TIMESTAMPTZ NOT NULL`
- CHECK `valid_until IS NULL OR valid_from IS NULL OR valid_until > valid_from`.
- Índice `(identifier_namespace, identifier_value)` y `(market_instrument_id, observed_at DESC)`.
- Los alias de Kraken no se colapsan: la clave interna de AssetPairs, `altname` y `wsname` pueden ser valores distintos para el mismo mercado. Los símbolos de distintas interfaces tampoco se consideran equivalentes sin mapeo explícito.

**`instrument_metadata_versions`**
- `id UUID PK`
- `market_instrument_id UUID NOT NULL FK market_instruments(id)`
- `source_dataset_id UUID NULL FK datasets(id)`
- `observed_at TIMESTAMPTZ NOT NULL` (tiempo de conocimiento/observación).
- `valid_from TIMESTAMPTZ NULL`, `valid_until TIMESTAMPTZ NULL` (tiempo de validez declarado/defendible).
- `source_status TEXT NOT NULL` (estado nativo sin pérdida).
- `normalized_status TEXT NULL` (mapeo canónico documentado y versionado).
- `price_precision INTEGER NULL`, `quantity_precision INTEGER NULL` (precisión decimal declarada; no equivale a tick/step).
- `pair_decimals INTEGER NULL`, `lot_decimals INTEGER NULL` (campos nativos de Kraken cuando estén presentes; no se generalizan como reglas de incremento).
- `provider_metadata JSONB NOT NULL DEFAULT '{}'` (extensiones no normalizadas y campos originales permitidos).
- `mapping_version TEXT NOT NULL`
- `schema_version TEXT NOT NULL`
- `created_at TIMESTAMPTZ NOT NULL`
- CHECK `valid_until IS NULL OR valid_from IS NULL OR valid_until > valid_from`.
- CHECK de precisiones no negativas cuando no sean NULL.
- Índice `(market_instrument_id, observed_at DESC)`.
- Tabla append-only. Una nueva observación o corrección genera otra fila.

**`instrument_trading_rules`**
- `id UUID PK`
- `metadata_version_id UUID NOT NULL FK instrument_metadata_versions(id)`
- `rule_namespace TEXT NOT NULL` (por ejemplo `PRICE_FILTER`, `LOT_SIZE`, `MARKET_LOT_SIZE`, `MIN_NOTIONAL`, `NOTIONAL`, `kraken_pair_rules`).
- `rule_scope TEXT NOT NULL`: CHECK en `price, limit_quantity, market_quantity, notional, order, asset, exchange, other`.
- `parameters JSONB NOT NULL` (valores decimales conservados como strings decimales; no convertir a float).
- `applicability JSONB NOT NULL DEFAULT '{}'` (por ejemplo applyToMarket, applyMinToMarket, applyMaxToMarket y avgPriceMins).
- `created_at TIMESTAMPTZ NOT NULL`
- UNIQUE `(metadata_version_id, rule_namespace, rule_scope)`.
- Cada fila representa una regla diferenciada y su ámbito; no se sintetiza un `quantity_step` universal cuando la fuente tiene reglas distintas para mercado y órdenes límite o cuando solo publica decimales de presentación.
- Las reglas no reconocidas se conservan como extensiones tipadas por adapter y no se descartan.

### 4.3 Runs y solicitudes

**`ingestion_runs`**
- `id UUID PK`
- `run_key TEXT NOT NULL UNIQUE`
- `started_at TIMESTAMPTZ NOT NULL`, `finished_at TIMESTAMPTZ NULL`
- `status TEXT NOT NULL`: CHECK en `queued, running, succeeded, partial, failed, cancelled`.
- `code_version TEXT NULL`, `protocol_version TEXT NULL`
- `configuration JSONB NOT NULL DEFAULT '{}'`
- `trigger_type TEXT NULL`, `notes TEXT NULL`
- `created_at TIMESTAMPTZ NOT NULL`
- CHECK `finished_at IS NULL OR finished_at >= started_at`.
- CHECK: estados terminales `succeeded, partial, failed, cancelled` requieren `finished_at IS NOT NULL`; `queued, running` no deben tenerlo.
- Las transiciones de estado se validan en servicio transaccional; no se reabre una ejecución terminal.

**`ingestion_requests`**
- `id UUID PK`
- `ingestion_run_id UUID NOT NULL FK ingestion_runs(id)`
- `data_source_id UUID NOT NULL FK data_sources(id)` (redundancia deliberada para integridad compuesta).
- `data_endpoint_id UUID NOT NULL`
- `market_instrument_id UUID NULL`
- `attempt_number INTEGER NOT NULL`
- `requested_at TIMESTAMPTZ NOT NULL`, `completed_at TIMESTAMPTZ NULL`
- `http_status SMALLINT NULL`
- `response_status TEXT NOT NULL`: CHECK en `succeeded, rate_limited, rejected, timeout, network_error, invalid_response`.
- `request_parameters JSONB NOT NULL DEFAULT '{}'`
- `response_headers_safe JSONB NOT NULL DEFAULT '{}'`
- `response_hash TEXT NULL`, `records_received BIGINT NULL`
- `error_code TEXT NULL`, `error_message TEXT NULL`
- `created_at TIMESTAMPTZ NOT NULL`
- FK `(data_endpoint_id, data_source_id) -> data_endpoints(id, data_source_id)`.
- FK `(market_instrument_id, data_source_id) -> market_instruments(id, data_source_id)`.
- UNIQUE candidato `(id, data_source_id, data_endpoint_id)`, para validar referencias de procedencia.
- CHECK `attempt_number > 0`; CHECK `records_received IS NULL OR records_received >= 0`; CHECK `completed_at IS NULL OR completed_at >= requested_at`; CHECK `http_status IS NULL OR http_status BETWEEN 100 AND 599`.
- Índice `(ingestion_run_id, requested_at)`; índice `(data_endpoint_id, requested_at DESC)`.
- No guardar cuerpos de respuesta, credenciales, cookies ni cabeceras secretas.

La FK compuesta impide combinar endpoint de una fuente con instrumento de otra. Si el instrumento es NULL, la FK compuesta no se aplica y el endpoint sigue validado contra la fuente declarada.

### 4.4 Datasets y procedencia

**`datasets`**
- `id UUID PK`
- `dataset_key TEXT NOT NULL`, `version INTEGER NOT NULL`
- `stage TEXT NOT NULL`: CHECK en `source_capture, normalized, derived, analytical_result, validation_report`.
- `data_format TEXT NOT NULL`: CHECK inicial en `parquet, json, csv, other`.
- `schema_name TEXT NOT NULL`, `schema_version TEXT NOT NULL`
- `storage_uri TEXT NOT NULL` (referencia lógica; nunca contiene credenciales).
- `checksum_sha256 TEXT NOT NULL`
- `file_size_bytes BIGINT NULL`, `record_count BIGINT NULL`
- `time_start TIMESTAMPTZ NULL`, `time_end TIMESTAMPTZ NULL`
- `created_at TIMESTAMPTZ NOT NULL`
- `retention_status TEXT NOT NULL`: CHECK en `active, pending_review, expired, deletion_pending, deleted`.
- `metadata JSONB NOT NULL DEFAULT '{}'`
- UNIQUE `(dataset_key, version)`; UNIQUE candidato `(id, stage)`.
- CHECK `version > 0`; CHECK tamaño/conteo no negativos; CHECK `time_end IS NULL OR time_start IS NULL OR time_end >= time_start`.
- CHECK de hash SHA-256: exactamente 64 caracteres hexadecimales minúsculos.
- El identificador de versión es inmutable. Una corrección genera otra versión, no UPDATE del contenido publicado.
- El cambio de `retention_status` se gestiona como transición auditada; no se permite volver de `deleted` a `active`. El tombstone conserva solo los metadatos mínimos permitidos.

**`run_datasets`**
- `ingestion_run_id UUID NOT NULL FK ingestion_runs(id)`
- `dataset_id UUID NOT NULL FK datasets(id)`
- `dataset_role TEXT NOT NULL`: CHECK en `source_capture, normalized, validation_report, derived, analytical_result`.
- `created_at TIMESTAMPTZ NOT NULL`
- PK `(ingestion_run_id, dataset_id, dataset_role)`.
- Índice inverso `(dataset_id)`.

**`dataset_sources`**
- `id UUID PK`
- `dataset_id UUID NOT NULL FK datasets(id)`
- `data_source_id UUID NOT NULL FK data_sources(id)`
- `data_endpoint_id UUID NOT NULL`
- `market_instrument_id UUID NULL`
- `ingestion_request_id UUID NULL`
- `policy_evaluation_id UUID NOT NULL`
- `evaluated_intended_use TEXT NOT NULL` (debe coincidir con la evaluación).
- `created_at TIMESTAMPTZ NOT NULL`
- FK `(data_endpoint_id, data_source_id) -> data_endpoints(id, data_source_id)`.
- FK `(market_instrument_id, data_source_id) -> market_instruments(id, data_source_id)`.
- FK `(ingestion_request_id, data_source_id, data_endpoint_id) -> ingestion_requests(id, data_source_id, data_endpoint_id)`. Esta FK se satisface cuando existe solicitud; sin solicitud, los tres campos pueden ser NULL.
- FK `(policy_evaluation_id, data_source_id, data_endpoint_id, evaluated_intended_use) -> policy_evaluations(id, data_source_id, data_endpoint_id, intended_use)`.
- UNIQUE candidato en `policy_evaluations` para la clave compuesta anterior.
- Índices `(dataset_id)`, `(data_source_id, created_at DESC)` y `(policy_evaluation_id)`.

**Regla obligatoria de autorización:** cada contribución de origen a un dataset persistido referencia una evaluación concreta. El servicio solo permite escribir si la evaluación devuelve `allowed` y comprueba alcance, vigencia, tipo de dato, endpoint y uso. Los estados `restricted, denied, unknown, pending_confirmation` bloquean la persistencia. La evaluación y su snapshot son append-only; una nueva revisión genera otra evaluación. La FK impide mezclar fuentes/endpoints/usos entre contribución y evaluación, pero no sustituye el juicio de aplicabilidad que debe realizar el servicio de autorización.

### 4.5 Linaje, validaciones y transformaciones

**`dataset_lineage`**
- `input_dataset_id UUID NOT NULL FK datasets(id)`
- `output_dataset_id UUID NOT NULL FK datasets(id)`
- `transformation_run_id UUID NOT NULL FK transformation_runs(id)`
- `created_at TIMESTAMPTZ NOT NULL`
- PK `(input_dataset_id, output_dataset_id, transformation_run_id)`.
- CHECK `input_dataset_id <> output_dataset_id`.
- Índices `(input_dataset_id)` y `(output_dataset_id)`.
- La prevención de ciclos requiere lógica transaccional serializable o bloqueo de grafo; CHECK/FK no bastan.

**`data_validations`**
- `id UUID PK`, `dataset_id UUID NOT NULL FK datasets(id)`
- `ingestion_run_id UUID NULL FK ingestion_runs(id)`
- `validation_suite TEXT NOT NULL`, `validation_version TEXT NOT NULL`
- `status TEXT NOT NULL`: CHECK en `passed, failed, warning, skipped`.
- `checked_at TIMESTAMPTZ NOT NULL`
- `checks_total INTEGER NOT NULL`, `checks_passed INTEGER NOT NULL`, `checks_failed INTEGER NOT NULL`
- `report_uri TEXT NULL`, `report_hash TEXT NULL`
- `details JSONB NOT NULL DEFAULT '{}'`, `created_at TIMESTAMPTZ NOT NULL`
- CHECK contadores no negativos y `checks_passed + checks_failed <= checks_total`.
- Índice `(dataset_id, checked_at DESC)`.

**`transformations`**
- `id UUID PK`
- `transformation_key TEXT NOT NULL`, `version TEXT NOT NULL`
- `description TEXT NOT NULL`, `code_reference TEXT NULL`
- `parameters_schema JSONB NOT NULL DEFAULT '{}'`
- `created_at TIMESTAMPTZ NOT NULL`
- UNIQUE `(transformation_key, version)`.

**`transformation_runs`**
- `id UUID PK`, `transformation_id UUID NOT NULL FK transformations(id)`
- `ingestion_run_id UUID NULL FK ingestion_runs(id)`
- `started_at TIMESTAMPTZ NOT NULL`, `finished_at TIMESTAMPTZ NULL`
- `status TEXT NOT NULL`: CHECK en `queued, running, succeeded, partial, failed, cancelled`.
- `parameters JSONB NOT NULL DEFAULT '{}'`
- `code_commit TEXT NULL`, `error_summary TEXT NULL`
- `created_at TIMESTAMPTZ NOT NULL`
- CHECK `finished_at IS NULL OR finished_at >= started_at`.
- Índice `(transformation_id, started_at DESC)`; índice `(ingestion_run_id)`.

### 4.6 Investigación

**`research_experiments`**
- `id UUID PK`, `experiment_key TEXT NOT NULL UNIQUE`
- `title TEXT NOT NULL`, `objective TEXT NOT NULL`
- `methodology_version TEXT NULL`
- `status TEXT NOT NULL`: CHECK en `planned, running, completed, inconclusive, rejected`.
- `started_at TIMESTAMPTZ NULL`, `finished_at TIMESTAMPTZ NULL`
- `code_version TEXT NULL`, `protocol JSONB NOT NULL DEFAULT '{}'`
- `conclusion_summary TEXT NULL`, `created_at TIMESTAMPTZ NOT NULL`
- CHECK `finished_at IS NULL OR started_at IS NULL OR finished_at >= started_at`.

**`research_hypotheses`**
- `id UUID PK`, `experiment_id UUID NOT NULL FK research_experiments(id)`
- `hypothesis_key TEXT NOT NULL`, `statement TEXT NOT NULL`
- `alternative_explanations JSONB NOT NULL DEFAULT '[]'`
- `falsification_criteria TEXT NULL`
- `status TEXT NOT NULL`: CHECK en `proposed, testing, supported, not_supported, inconclusive`.
- `created_at TIMESTAMPTZ NOT NULL`
- UNIQUE `(experiment_id, hypothesis_key)`.

**`experiment_datasets`**
- `experiment_id UUID NOT NULL FK research_experiments(id)`
- `dataset_id UUID NOT NULL FK datasets(id)`
- `dataset_role TEXT NOT NULL`: CHECK en `input, benchmark, validation, output`.
- `created_at TIMESTAMPTZ NOT NULL`
- PK `(experiment_id, dataset_id, dataset_role)`.

## 5. Índices: estrategia inicial

Se crearán índices explícitos para FKs usadas en joins y patrones de consulta observables. PostgreSQL no crea automáticamente índices en el lado que referencia una FK.

| Tabla | Índice / restricción | Motivo |
|---|---|---|
| `data_sources` | UNIQUE `source_key` | Resolución estable de fuente. |
| `data_endpoints` | UNIQUE `(data_source_id, endpoint_key)`; UNIQUE `(id, data_source_id)` | Búsqueda por fuente y FKs compuestas. |
| `source_usage_policies` | `(data_source_id, valid_from DESC)`; parcial por endpoint | Resolver política aplicable e historial. |
| `policy_evaluations` | `(data_source_id, data_endpoint_id, intended_use, evaluated_at DESC)`; FK índices | Consultar decisión concreta por endpoint y uso. |
| `asset_identity_resolution_reviews` | `(namespace, network, external_identifier, observed_at DESC)`; parcial por candidato | Auditar resoluciones pendientes, ambiguas, aceptadas y rechazadas. |\n| `asset_identifiers` | `(namespace, network, external_identifier)` | Resolver solo identificadores con correspondencia aprobada. |
| `market_instruments` | `(data_source_id, native_symbol)` no único; UNIQUE candidato `(id, data_source_id)` | Búsqueda por símbolo conservando alias y ambigüedad. |
| `instrument_identifiers` | `(identifier_namespace, identifier_value)`; `(market_instrument_id, observed_at DESC)` | Resolver alias nativos y símbolos por interfaz. |
| `instrument_metadata_versions` | `(market_instrument_id, observed_at DESC)` | Recuperar la última observación conocida. |
| `instrument_trading_rules` | UNIQUE `(metadata_version_id, rule_namespace, rule_scope)`; índice `(metadata_version_id)` | Recuperar reglas por versión y ámbito.
| `ingestion_requests` | `(ingestion_run_id, requested_at)`; `(data_endpoint_id, requested_at DESC)` | Inspección de Run y endpoint. |
| `datasets` | UNIQUE `(dataset_key, version)`; UNIQUE `checksum_sha256` solo si se decide que no pueden coexistir artefactos idénticos | Versionado y deduplicación opcional. No imponer deduplicación por hash sin decisión. |
| `run_datasets` | PK compuesta; índice `(dataset_id)` | Recorrido Run→dataset y dataset→Run. |
| `dataset_sources` | `(dataset_id)`; `(data_source_id, created_at DESC)`; `(policy_evaluation_id)` | Procedencia y auditoría de política. |
| `dataset_lineage` | PK; índices por input y output | Recorrido del grafo en ambos sentidos. |
| `data_validations` | `(dataset_id, checked_at DESC)` | Última validación. |
| `transformation_runs` | `(transformation_id, started_at DESC)`; `(ingestion_run_id)` | Historial de ejecuciones. |
| `research_hypotheses` | UNIQUE `(experiment_id, hypothesis_key)` | Identidad de hipótesis. |
| `experiment_datasets` | PK compuesta; índice `(dataset_id)` | Consultas por experimento y dataset. |

No crear índices GIN sobre todos los JSONB ni índices parciales sin consulta concreta. No particionar tablas operativas antes de disponer de volúmenes medidos. No añadir índices duplicados que ya cubra una PK/UNIQUE.

## 6. Tiempo, estados e inmutabilidad

### 6.1 Tiempo bitemporal

Se distinguen dos dimensiones cuando el dato lo requiere:
- **Valid time:** `valid_from / valid_until`, periodo durante el cual una regla o metadata aplica en el mercado/proveedor.
- **Observation/record time:** `observed_at`, `reviewed_at`, `permission_evaluated_at` o `created_at`, momento en que el proyecto conoció o registró la información.

No se inferirá el tiempo de validez a partir del tiempo de observación. Los intervalos de validez son semiabiertos `[valid_from, valid_until)`. Si `valid_from` es NULL en un identificador histórico, significa que el inicio no está documentado, no que sea válido desde siempre.

### 6.2 Inmutabilidad

- Las políticas de uso, versiones de metadata, solicitudes, resultados de validación, ejecuciones y relaciones de linaje son append-only desde el servicio de aplicación.
- Un dataset publicado es inmutable en identidad, versión, formato, esquema, URI y hash. La retención puede cambiar mediante transición auditada.
- Las correcciones crean nuevas versiones o nuevos registros de observación.
- Las reglas de inmutabilidad se aplican mediante privilegios de rol y, cuando sea necesario, triggers. No confiar únicamente en convenciones de Python.
- Se recomienda una tabla de eventos de auditoría antes de permitir operaciones administrativas que alteren estados de retención o políticas; su diseño se tratará como entregable separado para no inventar ahora un sistema de auditoría incompleto.

### 6.3 Estados y transiciones

Los CHECK validan pertenencia al vocabulario y coherencia local. Las transiciones entre estados se controlan en funciones/servicios transaccionales. Por ejemplo, un Run terminal no vuelve a `running`; un dataset `deleted` no vuelve a `active`; una política anterior no se edita para simular un cambio contractual.

## 7. Consistencia PostgreSQL–Parquet

No existe transacción distribuida entre PostgreSQL y el sistema de archivos/almacenamiento Parquet. El flujo de publicación debe ser recuperable:

1. Crear Run y solicitud en estado inicial.
2. Evaluar la política aplicable; denegar por defecto.
3. Producir el artefacto en ubicación temporal no publicada, solo si la persistencia está autorizada.
4. Verificar formato, esquema, tamaño y SHA-256.
5. Publicar atómicamente el artefacto según las capacidades del almacenamiento.
6. Registrar dataset y relaciones `run_datasets` / `dataset_sources` en una transacción PostgreSQL.
7. Marcar el Run como finalizado.
8. Un reconciliador detecta artefactos temporales huérfanos, registros sin archivo y operaciones interrumpidas; no elimina evidencia sin aplicar la política de retención.

El diseño de estados intermedios exactos y el mecanismo de publicación atómica dependen del almacenamiento elegido y quedan fuera de esta especificación física inicial.

## 8. Orden de migraciones SQL

Las migraciones serán versionadas, secuenciales, revisables y ejecutables desde una base vacía. Orden propuesto:

1. Crear esquema `cci` y convenciones mínimas.
2. Crear `data_sources`, `assets`, `ingestion_runs`, `transformations`, `research_experiments`.
3. Crear `data_endpoints`, `source_usage_policies`, `asset_identifiers`, `market_instruments`.
4. Crear `instrument_identifiers` y `policy_evaluations` con sus FKs compuestas.
5. Crear `datasets` antes de las tablas que lo referencian.
6. Crear `ingestion_requests`, `run_datasets` y `dataset_sources` con FK compuestas.
7. Crear `instrument_metadata_versions`, `instrument_trading_rules`, `data_validations` y `transformation_runs`.
8. Crear `dataset_lineage` y `experiment_datasets`.
9. Crear `research_hypotheses`.
10. Crear índices adicionales, triggers de inmutabilidad y funciones de transición solo después de probar su necesidad.
11. Registrar versión de migración y probar migración desde cero, actualización desde versión previa y reversión controlada.

Las migraciones no deben depender de datos reales ni de llamadas de red. La reversión de DDL no autoriza borrar artefactos Parquet; la base y el almacenamiento se gestionan por separado.

## 9. Pruebas de aceptación del esquema

La implementación física no se considerará aceptada hasta que las pruebas automáticas demuestren:

1. Instalación completa desde una base vacía y orden de migración reproducible.
2. Rechazo de endpoint e instrumento pertenecientes a fuentes distintas.
3. Rechazo de una solicitud que vincule un instrumento incompatible con su endpoint/fuente.
4. Rechazo de una contribución persistida sin evaluación de política.
5. Rechazo de política vencida, denegada, desconocida o no aplicable en el servicio de autorización.
6. Trazabilidad dataset→Run, dataset→fuentes/políticas y dataset→linaje.
7. Rechazo de hashes mal formados, conteos negativos y rangos temporales inválidos.
8. Inmutabilidad de versiones publicadas y de evidencia histórica.
9. Rechazo de transiciones de estado ilegales.
10. Prevención transaccional de ciclos en el linaje.
11. Reversión de migraciones sin dejar objetos huérfanos.
12. Pruebas con fixtures sintéticos únicamente; ningún test debe consultar Binance, Kraken o CoinGecko.

Las pruebas unitarias existentes de parsers (13/13 en la ejecución CI documentada en el PR) no prueban este esquema físico. Son suites diferentes y deberán reportarse por separado.

## 10. Decisiones pendientes que bloquean el DDL

1. **Resolución de identidad de activos:** decidir los criterios documentales para asociar los códigos nativos de base/cotización con `assets`; el diseño admite identidad aún no resuelta.
2. **Identificadores externos temporales:** definir cómo se representan observaciones corregidas y periodos solapados antes de añadir índices únicos parciales definitivos.
3. **Auditoría de cambios administrativos:** definir si se añade `audit_events` y qué operaciones requieren actor, motivo y evidencia.
4. **Almacenamiento Parquet:** seleccionar el backend concreto antes de definir validación de URI, publicación atómica y reconciliación.

La evaluación de políticas queda modelada mediante `policy_evaluations`; sus reglas de aplicabilidad y el flujo de autorización deberán probarse antes de permitir escrituras. Las demás decisiones pueden cerrarse en iteraciones previas a las migraciones que dependan de ellas.

## 11. Secuencia de trabajo posterior

1. Aceptar o corregir esta especificación física.
2. Resolver la identidad canónica de activos y las restricciones temporales de alias.
3. Contrastar restricciones con los contratos canónicos OHLCV y metadata.
4. Preparar migración inicial SQL y pruebas de integridad con PostgreSQL temporal.
5. Revisar el SQL y la evidencia de pruebas antes de considerar la implementación aceptada.
6. Mantener PR #15 en Draft hasta cerrar las brechas de validación empírica y permisos ya documentadas.

## 12. Referencias internas

- `ADR-001-storage-and-analytics-architecture.md`
- `postgresql-logical-data-model.md`
- `postgresql-logical-model-review.md`
- `canonical-market-data-schemas.md`
- `provider-validation-test-plan.md`
