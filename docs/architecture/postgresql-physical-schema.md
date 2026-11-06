# Diseño físico de PostgreSQL

- **Estado:** especificación física reconciliada v0.3; propuesta, no implementada.
- **Fecha:** 2026-11-06.
- **Modelo lógico:** `postgresql-logical-data-model.md`, contrato reconciliado v0.4.
- **Revisión:** `postgresql-logical-model-review.md`.
- **Decisión relacionada:** `ADR-001-storage-and-analytics-architecture.md`.
- **Issue / PR:** #14 / #16.

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
| `assets` | `id` | Identidad económica/técnica del activo; no identifica un contrato concreto. |
| `networks` | `id` | Redes blockchain con clave interna estable. |
| `network_identifiers` | `id` | Chain IDs y alias de red namespaced. |
| `asset_representations` | `id` | Unidad nativa o despliegue contractual de un activo en una red. |
| `asset_relationships` | `id` | Relaciones tipadas, dirigidas y evidenciadas entre activos distintos. |
| `asset_identity_resolution_reviews` | `id` | Candidatos, decisiones y evidencia de resolución a nivel de activo o representación. |
| `asset_identifiers` | `id` | Identificadores externos aceptados a nivel de activo. |
| `asset_representation_identifiers` | `id` | Identificadores externos aceptados a nivel de representación. |
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
- `scope_reference TEXT NULL`: clave estable del producto/plan cuando `policy_scope = 'product'`; valor canónico de `data_type` cuando `policy_scope = 'data_type'`; NULL para `provider` y `endpoint`.
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
- CHECK de coherencia: `policy_scope = 'endpoint'` requiere endpoint no nulo y `scope_reference IS NULL`; `product` y `data_type` requieren `scope_reference` no vacío; `provider` requiere endpoint y scope_reference NULL.
- La referencia de producto/plan es una clave textual estable del catálogo de evidencia (no una FK a un catálogo de productos aún inexistente); debe identificar sin ambigüedad el producto, plan y versión contractual revisados.
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
- UNIQUE `(id, data_source_id, data_endpoint_id, data_type, intended_use)`, requerida por `dataset_sources`.
- CHECK `policy_valid_until_snapshot IS NULL OR policy_valid_until_snapshot > policy_valid_from_snapshot`.
- Registro append-only. La evaluación materializa la decisión concreta, aunque la política de origen tenga alcance provider/product/data_type y no un endpoint específico.
- El servicio de autorización comprueba que la política cubra la fuente, endpoint, tipo, uso e instante evaluado. La FK garantiza coherencia referencial, no la validez jurídica de la interpretación.

La política aplicable se resuelve considerando fuente, alcance y referencia estructurada (producto/plan o tipo de dato cuando corresponda), endpoint, tipo de dato, uso previsto, vigencia y evidencia. No se asume que una política de proveedor cubra automáticamente todos sus productos.

### 4.2 Activos e instrumentos

**`assets`**
- `id UUID PK`
- `canonical_code TEXT NOT NULL UNIQUE` (clave interna estable; no se exige que sea ticker).
- `display_name TEXT NOT NULL`
- `asset_type TEXT NOT NULL`: CHECK inicial en `crypto, fiat, stablecoin, tokenized_asset, other`.
- `issuer_key TEXT NULL`, `issuer_name TEXT NULL` (descriptivos; no sustituyen una entidad de emisor ni evidencia).
- `external_identifiers JSONB NOT NULL DEFAULT '{}'` (extensión transitoria; no sustituye tablas normalizadas).
- `created_at TIMESTAMPTZ NOT NULL`.
- No incluir `network` como atributo de identidad del activo: la relación con redes se expresa mediante `asset_representations`.

**`networks`**
- `id UUID PK`
- `network_key TEXT NOT NULL UNIQUE` (clave interna estable y namespaced por familia cuando sea necesario).
- `display_name TEXT NOT NULL`
- `network_family TEXT NOT NULL`: CHECK inicial `bitcoin, evm, solana, other`; vocabulario ampliable mediante migración.
- `environment TEXT NOT NULL`: CHECK `mainnet, testnet, devnet, other`.
- `created_at TIMESTAMPTZ NOT NULL`.
- El nombre o chain ID no se considera por sí solo una prueba de identidad de red.

**`network_identifiers`**
- `id UUID PK`
- `network_id UUID NOT NULL FK networks(id)`
- `namespace TEXT NOT NULL` (familia/especificación que define el identificador).
- `identifier_type TEXT NOT NULL` (por ejemplo `eip155_chain_id`, `genesis_hash`, `provider_network_key`).
- `identifier_value TEXT NOT NULL` (literal exacto).
- `observed_at TIMESTAMPTZ NOT NULL`, `evidence_reference TEXT NOT NULL`.
- UNIQUE candidato `(namespace, identifier_type, identifier_value)`, solo tras verificar que el namespace define unicidad en ese ámbito.
- No almacenar un chain ID aislado sin namespace ni asumir que es globalmente único.

**`asset_representations`**
- `id UUID PK`
- `asset_id UUID NOT NULL FK assets(id)`
- `network_id UUID NOT NULL FK networks(id)`
- `representation_kind TEXT NOT NULL`: CHECK `native, token_contract, other`.
- `native_asset_key TEXT NULL` (identificador nativo de la unidad de red; solo para `native`).
- `contract_address TEXT NULL` (dirección literal; solo para representación contractual).
- `address_normalization TEXT NULL` (regla/versionado de comparación; nunca reemplaza el valor original).
- `token_standard TEXT NULL`, `decimals INTEGER NULL` (metadata observada; decimals no equivale a precisión de mercado).
- `issuer_key TEXT NULL` (referencia descriptiva pendiente de catálogo de emisores).
- `valid_from TIMESTAMPTZ NULL`, `valid_until TIMESTAMPTZ NULL` (vigencia semiabierta).
- `observed_at TIMESTAMPTZ NOT NULL`, `evidence_reference TEXT NOT NULL`.
- CHECK: `representation_kind = 'native'` exige `native_asset_key IS NOT NULL AND contract_address IS NULL`.
- CHECK: `representation_kind = 'token_contract'` exige `contract_address IS NOT NULL AND native_asset_key IS NULL`.
- CHECK: `valid_until IS NULL OR (valid_from IS NOT NULL AND valid_until > valid_from)`.
- Una representación contractual requiere red y dirección verificadas; una unidad nativa nunca recibe una dirección ficticia.
- No imponer unicidad global de `contract_address`; su scope mínimo es red + dirección + tipo de representación. La política de case/checksum se define por familia de red.

**`asset_relationships`**
- `id UUID PK`
- `subject_asset_id UUID NOT NULL FK assets(id)`
- `object_asset_id UUID NOT NULL FK assets(id)`
- `relationship_type TEXT NOT NULL`: CHECK inicial `wrapped_representation_of, bridged_representation_of, redeemable_for, backed_by, tracks_price_of, migrated_to`.
- `directionality TEXT NOT NULL DEFAULT 'directed'`: CHECK `directed`.
- `valid_from TIMESTAMPTZ NULL`, `valid_until TIMESTAMPTZ NULL`.
- `evidence_reference TEXT NOT NULL`, `observed_at TIMESTAMPTZ NOT NULL`, `recorded_at TIMESTAMPTZ NOT NULL` (registro inmutable en CCI).
- CHECK `subject_asset_id <> object_asset_id`.
- CHECK `valid_until IS NULL OR (valid_from IS NOT NULL AND valid_until > valid_from)`.
- Las relaciones no crean equivalencia de identidad, fungibilidad, paridad ni propagación automática de FKs. No asumir transitividad.

**`asset_identity_resolution_reviews`**
- `id UUID PK`
- `namespace TEXT NOT NULL`
- `network_id UUID NULL FK networks(id)` (scope de red normalizado; NULL solo cuando la fuente no delimita una red).
- `external_identifier TEXT NOT NULL` (código/dirección nativa exacta).
- `candidate_asset_id UUID NULL FK assets(id)`
- `candidate_asset_representation_id UUID NULL FK asset_representations(id)`
- CHECK: los dos destinos no pueden ser NOT NULL simultáneamente; una decisión `accepted` exige exactamente uno. Las revisiones `ambiguous` pueden conservar ambos destinos en una tabla de candidatos futura, pero no publican FK.
- `resolution_status TEXT NOT NULL`: CHECK en `pending_review, accepted, rejected, ambiguous`.
- `evidence_reference TEXT NULL`, `decision_reference TEXT NULL`.
- `observed_at TIMESTAMPTZ NOT NULL`, `reviewed_at TIMESTAMPTZ NULL`, `recorded_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()` (tiempo de conocimiento asignado por PostgreSQL; inmutable).
- `valid_from TIMESTAMPTZ NULL`, `valid_until TIMESTAMPTZ NULL` (valid time semiabierto; una decisión accepted exige inicio explícito).
- `supersedes_review_id UUID NULL FK asset_identity_resolution_reviews(id)`; debe referir una revisión previa de la misma clave de identidad y no puede formar ciclos ni ramas competidoras.
- CHECK `valid_until IS NULL OR (valid_from IS NOT NULL AND valid_until > valid_from)`.
- CHECK: una decisión `accepted` requiere exactamente un destino, evidencia, `reviewed_at` y `valid_from`.
- UNIQUE candidato `(id, candidate_asset_id, resolution_status, namespace, external_identifier)`, referenciado por `asset_identifiers`.
- UNIQUE candidato `(id, candidate_asset_representation_id, resolution_status, namespace, external_identifier, network_id)`, referenciado por `asset_representation_identifiers`.
- Las claves candidatas se definen aunque los campos de destino sean NULL en revisiones no aceptadas; los mappings solo pueden referenciar la variante no nula y `resolution_status = 'accepted'`.
- Registro append-only; `recorded_at` se asigna al insertar. Correcciones mediante nueva revisión.
- Las revisiones de activo y de representación son scopes distintos. Una revisión contractual exige `network_id` y el identificador debe corresponder exactamente al contrato/alias documentado. Cada `namespace` tiene un único modo de alcance: global (red NULL) o por red (red NOT NULL); no se permite mezclarlos dentro del mismo namespace.
- Empates máximos contradictorios para la misma clave exacta se resuelven como `ambiguous`, nunca como selección arbitraria.

**`asset_identifiers`**
- `id UUID PK`
- `asset_id UUID NOT NULL FK assets(id)`
- `namespace TEXT NOT NULL`, `external_identifier TEXT NOT NULL`.
- `network_id UUID NULL FK networks(id)`: ámbito de red cuando el identificador sea específico de una red; NULL representa un identificador global dentro del namespace.
- `valid_from TIMESTAMPTZ NOT NULL`, `valid_until TIMESTAMPTZ NULL`, `recorded_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()` (transaction/knowledge time, inmutable).
- `evidence_reference TEXT NOT NULL`, `resolution_review_id UUID NOT NULL`.
- `resolution_status TEXT NOT NULL DEFAULT 'accepted'`: CHECK `resolution_status = 'accepted'`; columna constante para permitir FK compuesta que pruebe el estado aprobado.
- FK compuesta `(resolution_review_id, asset_id, resolution_status, namespace, external_identifier) -> asset_identity_resolution_reviews(id, candidate_asset_id, resolution_status, namespace, external_identifier)`.
- Trigger `validate_asset_identifier_review_scope`: comprueba que el `network_id` del mapping sea idéntico al `network_id` de la revisión, incluyendo la igualdad NULL/NULL. La FK compuesta anterior ya garantiza revisión accepted, destino, namespace e identificador exactos.
- CHECK `valid_until IS NULL OR valid_until > valid_from`.
- `recorded_at` se asigna al insertar y no se modifica; los mappings son eventos append-only cuya vigencia efectiva se reconstruye mediante la revisión y su cadena de sustitución.
- Solo mappings aceptados a nivel de activo. La publicación del mapping y su revisión se realiza en una misma transacción.

**`asset_representation_identifiers`**
- `id UUID PK`
- `asset_representation_id UUID NOT NULL`
- `network_id UUID NOT NULL`: red de la representación; no se admite NULL.
- `namespace TEXT NOT NULL`, `external_identifier TEXT NOT NULL`.
- `valid_from TIMESTAMPTZ NOT NULL`, `valid_until TIMESTAMPTZ NULL`, `recorded_at TIMESTAMPTZ NOT NULL`.
- `evidence_reference TEXT NOT NULL`, `resolution_review_id UUID NOT NULL`.
- `resolution_status TEXT NOT NULL DEFAULT 'accepted'`: CHECK `resolution_status = 'accepted'`.
- UNIQUE candidato en `asset_representations(id, network_id)`.
- FK `(asset_representation_id, network_id) -> asset_representations(id, network_id)`.
- FK compuesta `(resolution_review_id, asset_representation_id, resolution_status, namespace, external_identifier, network_id) -> asset_identity_resolution_reviews(id, candidate_asset_representation_id, resolution_status, namespace, external_identifier, network_id)`.
- CHECK `valid_until IS NULL OR valid_until > valid_from`.
- `recorded_at` se asigna al insertar y no se modifica; los mappings son eventos append-only cuya vigencia efectiva se reconstruye mediante la revisión y su cadena de sustitución.
- La FK compuesta garantiza que la revisión accepted aprueba exactamente esa representación, identificador y red. La publicación se realiza en una misma transacción que inserta la revisión y el mapping.

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
- `data_type TEXT NOT NULL` (debe coincidir exactamente con `policy_evaluations.data_type` y el tipo de dato del endpoint/contribución).
- `market_instrument_id UUID NULL`
- `ingestion_request_id UUID NULL`
- `policy_evaluation_id UUID NOT NULL`
- `evaluated_intended_use TEXT NOT NULL` (debe coincidir con la evaluación).
- `created_at TIMESTAMPTZ NOT NULL`
- FK `(data_endpoint_id, data_source_id) -> data_endpoints(id, data_source_id)`.
- FK `(market_instrument_id, data_source_id) -> market_instruments(id, data_source_id)`.
- FK `(ingestion_request_id, data_source_id, data_endpoint_id) -> ingestion_requests(id, data_source_id, data_endpoint_id)`. Esta FK se satisface cuando existe solicitud; sin solicitud, los tres campos pueden ser NULL.
- FK `(policy_evaluation_id, data_source_id, data_endpoint_id, data_type, evaluated_intended_use) -> policy_evaluations(id, data_source_id, data_endpoint_id, data_type, intended_use)`.
- UNIQUE candidato en `policy_evaluations` para la clave compuesta anterior.
- Índices `(dataset_id)`, `(data_source_id, created_at DESC)` y `(policy_evaluation_id)`.

**Regla obligatoria de autorización:** cada contribución de origen a un dataset persistido referencia una evaluación concreta. El servicio solo permite escribir si la evaluación devuelve `allowed` y comprueba alcance, vigencia, tipo de dato, endpoint y uso. Los estados `restricted, denied, unknown, pending_confirmation` bloquean la persistencia. La evaluación y su snapshot son append-only; una nueva revisión genera otra evaluación. La FK impide mezclar fuentes/endpoints/tipos/usos entre contribución y evaluación, pero no sustituye el juicio de aplicabilidad que debe realizar el servicio de autorización.

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
| `policy_evaluations` | `(data_source_id, data_endpoint_id, data_type, intended_use, evaluated_at DESC)`; FK índices | Consultar decisión concreta por endpoint, tipo y uso. |
| `networks` | UNIQUE `network_key` | Identidad interna estable de red. |
| `network_identifiers` | `(namespace, identifier_type, identifier_value)` | Resolver identificadores de red dentro de su namespace. |
| `asset_representations` | `(network_id, representation_kind, contract_address)`; parcial para representaciones nativas | Identidad de despliegues y unidades nativas por red. |
| `asset_relationships` | `(subject_asset_id, relationship_type)`; `(object_asset_id)` | Consultar relaciones tipadas sin inferir identidad. |
| `asset_identity_resolution_reviews` | `(namespace, network_id, external_identifier, recorded_at DESC)`; parcial por candidato | Auditar resoluciones de activo y representación. |
| `asset_identifiers` | `(namespace, external_identifier)` | Resolver identificadores aceptados a nivel de activo. |
| `asset_representation_identifiers` | `(namespace, external_identifier)` | Resolver identificadores aceptados a nivel de representación. |
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

## 5.1 Semántica temporal de la resolución de identidades

### Dos ejes y reconstrucción histórica

Para `asset_identity_resolution_reviews`, `asset_identifiers` y `asset_representation_identifiers`:

- **Valid time:** intervalo semiabierto `[valid_from, valid_until)`; indica cuándo el identificador corresponde al destino en el dominio representado por la evidencia.
- **Transaction/knowledge time:** `recorded_at`; instante UTC, asignado por PostgreSQL al registrar la decisión y nunca retrodatado. `observed_at` y `reviewed_at` conservan cuándo se observó la evidencia y cuándo se revisó; no sustituyen a `recorded_at`.

El diseño usa un **historial bitemporal reconstruible por eventos append-only**, no intervalos físicos `recorded_from/recorded_until`. Cada revisión es inmutable y `supersedes_review_id` identifica la decisión que corrige o reemplaza. Así, una consulta con `valid_at` y `known_at` reconstruye qué decisión conocía CCI en ese instante, sin modificar ni cerrar filas históricas. No se debe describir `recorded_at` aislado como un intervalo bitemporal: la reconstrucción depende de conservar la cadena completa de revisiones y sus sustituciones.

Regla de lectura:
1. Filtrar revisiones con `recorded_at <= known_at` y cuya clave de identidad coincida exactamente.
2. Resolver la cadena de sustitución y seleccionar la revisión efectiva más reciente conocida en `known_at`; no elegir simplemente el mayor timestamp si existen ramas o sustituciones contradictorias.
3. Evaluar su estado y su intervalo de validez en `valid_at`.
4. Si la revisión efectiva es `rejected`, `ambiguous`, no cubre `valid_at` o la cadena no tiene un único resultado, devolver sin mapping canónico y explicar el motivo.

### Ámbito de la clave y no solapamiento

`namespace` define un dominio de identidad y, por contrato, un único modo de alcance: **global** (`network_id IS NULL` en todas sus decisiones) o **por red** (`network_id IS NOT NULL` en todas sus decisiones). Los namespaces globales y los namespaces de direcciones/identificadores de red deben ser distintos; no se permite mezclar ambos modos dentro de un mismo namespace. Esto evita que NULL signifique unas veces “global” y otras “desconocido”.

La clave de conflicto es:
- Namespace global: `(namespace, external_identifier)`.
- Namespace por red: `(namespace, network_id, external_identifier)`.

Para una misma clave, en un mismo conocimiento de CCI, no pueden existir dos decisiones aceptadas efectivas con intervalos de valid time solapados y destinos distintos. Los intervalos contiguos sí se permiten: `[a,b)` y `[b,c)` no se solapan. Un cambio legítimo de destino requiere una revisión que sustituya explícitamente la decisión anterior y periodos coherentes; una corrección retroactiva crea una nueva revisión con su propio `recorded_at`, sin reescribir lo que CCI conocía antes.

### Sustitución, concurrencia y publicación

- `supersedes_review_id` debe apuntar a una revisión anterior de la misma clave (namespace, external_identifier y modo/ámbito de red). No puede apuntar a sí misma ni crear ciclos. Una sustitución de decisión accepted debe declarar el destino y periodo corregidos, y conservar evidencia y referencia de decisión.
- La cadena debe ser lineal: una revisión no puede ser sustituida por dos revisiones competidoras para la misma rama de conocimiento. Si la evidencia produce alternativas no resolubles, se registra `ambiguous`, no dos mappings accepted.
- La revisión y su mapping, cuando proceda, se publican en una única transacción. El mapping debe copiar exactamente destino, namespace, identificador, red y periodo de la revisión accepted.
- Para evitar carreras, el servicio de escritura obtiene un bloqueo transaccional por clave de identidad antes de comprobar la cadena, validar intervalos y publicar. El diseño físico debe definir una clave de bloqueo determinista y probar dos sesiones concurrentes; `SERIALIZABLE` con reintentos es una alternativa válida. Un chequeo previo en Python sin bloqueo no es suficiente.
- Las restricciones CHECK/FK actuales garantizan coherencia local y referencial, pero no garantizan no solapamiento, cadena lineal ni exclusión bajo concurrencia. Estas reglas requieren trigger/función transaccional o un mecanismo PostgreSQL equivalente, además de pruebas reales.

No se exige `btree_gist` en esta etapa. Se prefiere el bloqueo por clave más validación transaccional porque el ámbito global frente a red requiere comparar claves de alcance distinto y no queda cubierto por una exclusión GiST simple.

## 6. Tiempo, estados e inmutabilidad

### 6.1 Dimensiones temporales

No todos los timestamps representan la misma dimensión:
- **Valid time:** `valid_from / valid_until`, periodo durante el cual una identidad, regla o metadata aplica en el dominio de origen.
- **Observation time:** `observed_at`, momento en que CCI observó la evidencia.
- **Decision time:** `reviewed_at`, momento en que se revisó o decidió, cuando corresponda.
- **Transaction/knowledge time:** `recorded_at`, momento inmutable en que la decisión quedó registrada en CCI.

Los intervalos de validez son semiabiertos `[valid_from, valid_until)`. No se infiere validez a partir de observación o registro. Para resolución de identidades, la reconstrucción bitemporal se basa en revisiones append-only, `recorded_at` y la cadena `supersedes_review_id`; no hay columnas físicas `recorded_from/recorded_until`. Para otras entidades, no se afirmará bitemporalidad si solo existe un timestamp de observación o creación. Si `valid_from` es NULL en un registro que lo admite, el inicio no está documentado, no significa “válido desde siempre”.

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
2. Crear `data_sources`, `assets`, `ingestion_runs`, `transformations` y `research_experiments`.
3. Crear `data_endpoints`, `source_usage_policies` y `policy_evaluations`.
4. Crear `networks`, `network_identifiers`, `asset_representations`, `asset_relationships`, `asset_identity_resolution_reviews`, `asset_identifiers` y `asset_representation_identifiers`.
5. Crear `market_instruments` e `instrument_identifiers`.
6. Crear `datasets` antes de las tablas que los referencian.
7. Crear `ingestion_requests`, `run_datasets` y `dataset_sources` con FKs compuestas.
8. Crear `instrument_metadata_versions`, `instrument_trading_rules`, `data_validations` y `transformation_runs`.
9. Crear `dataset_lineage`, `experiment_datasets` y `research_hypotheses`.
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
13. Una representación `native` requiere clave nativa y prohíbe contrato; `token_contract` requiere contrato y prohíbe clave nativa.
14. Una red no puede contener dos filas para el mismo identificador de despliegue; la unicidad se evalúa con la política de comparación específica de esa familia de red, no mediante normalización global.
15. Un activo puede tener representaciones en varias redes; una relación wrapper/bridge no fusiona el activo con su subyacente.
16. Dos contratos distintos con el mismo ticker pueden pertenecer a activos diferentes; el ticker no participa en la clave de unicidad.

Las pruebas unitarias de parsers y de contratos de representación no prueban todavía el esquema físico PostgreSQL. La suite Python actual incluye 48 métodos `test_*`, de los cuales 13 cubren representaciones con fixtures sintéticos. Son pruebas de contrato de aplicación, no pruebas de restricciones ejecutadas por el motor PostgreSQL; ambas capas deberán reportarse por separado.

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
6. Mantener PR #16 en Draft hasta cerrar las brechas de validación empírica y permisos ya documentadas.

## 12. Referencias internas

- `ADR-001-storage-and-analytics-architecture.md`
- `postgresql-logical-data-model.md`
- `postgresql-logical-model-review.md`
- `canonical-market-data-schemas.md`
- `provider-validation-test-plan.md`


## 8. Publicación consistente de mappings de identidad

La publicación se define como una operación atómica de base de datos, no como dos escrituras independientes de la aplicación.

### 8.1 Mapping a nivel de activo

1. Insertar una fila en `asset_identity_resolution_reviews` con `resolution_status = 'accepted'`, `candidate_asset_id` no nulo, `candidate_asset_representation_id` NULL, namespace, identificador y ámbito de red.
2. Insertar `asset_identifiers` con el mismo activo, namespace, identificador, revisión y estado constante `accepted`.
3. La FK compuesta verifica estado, destino y clave externa exactos.
4. Un trigger valida igualdad de ámbito de red con semántica NULL-safe (`IS NOT DISTINCT FROM`); esto evita que una revisión global respalde un mapping de red o viceversa.
5. Confirmar ambas inserciones en una sola transacción. Si falla cualquier comprobación, se revierte la publicación completa.


**Contrato del trigger `validate_asset_identifier_review_scope`:**

- Se ejecuta `BEFORE INSERT` sobre `asset_identifiers`.
- Lee la revisión referenciada y exige coincidencia con `NEW.asset_id`, `NEW.namespace`, `NEW.external_identifier` y `resolution_status = 'accepted'`. La FK compuesta vuelve a imponer estas condiciones como garantía declarativa.
- Compara `review.network_id IS DISTINCT FROM NEW.network_id`; si la expresión es verdadera, aborta con excepción de integridad.
- No transforma ni normaliza el identificador. La comparación es literal; cualquier normalización debe quedar definida por namespace y versionada antes de publicar el mapping.
- La tabla de revisiones es append-only, por lo que el destino y el ámbito validados no pueden cambiar después de la inserción.

### 8.2 Mapping a nivel de representación

1. Insertar revisión accepted con `candidate_asset_representation_id` y `network_id` no nulos.
2. Insertar `asset_representation_identifiers` con la misma representación, red, namespace e identificador.
3. La FK compuesta verifica conjuntamente revisión, destino, estado, namespace, identificador y red. Otra FK verifica que la red corresponda a la representación.
4. Confirmar ambas inserciones en una sola transacción.

### 8.3 Inmutabilidad y seguridad

- Los roles de aplicación no reciben UPDATE/DELETE sobre revisiones ni mappings publicados; correcciones y revocaciones se expresan con nuevas filas/versiones y reglas temporales, no sobrescribiendo evidencia.
- Los triggers son defensas de integridad de la base; la aplicación no debe duplicar la decisión como única garantía.
- Una transacción que no consiga insertar revisión y mapping completos no deja una revisión accepted publicada parcialmente.
- Estas reglas deben probarse en PostgreSQL real, incluidos intentos de mapping con revisión inexistente, pendiente, rechazada, destino distinto, namespace/identificador distinto y red incompatible.
