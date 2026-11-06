# Diseño físico de PostgreSQL

- **Estado:** especificación física reconciliada v0.7; propuesta de producción, no implementada. El subsistema NET-04/05/06 tiene contrato de laboratorio ejecutado, sin promoción a `cci`.
- **Fecha:** 2026-11-06.
- **Modelo lógico:** `postgresql-logical-data-model.md`, contrato reconciliado v0.7.
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
| `identity_namespaces` | `namespace_key` | Registro inmutable del significado, alcance y nivel de destino de los namespaces de resolución de activos. |
| `networks` | `id` | Redes blockchain con clave interna estable. |
| `network_identifiers` | `id` | Identificadores técnicos y externos de red namespaced, con evidencia. |
| `provider_platforms` | `id` | Identidad estable de una plataforma dentro de un proveedor. |
| `provider_platform_observations` | `id` | Capturas inmutables de metadata de una plataforma de proveedor. |
| `provider_platform_resolution_reviews` | `id` | Revisiones append-only de correspondencia entre una identidad de plataforma y una red canónica. |
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
| `research_experiment_runs` | `id` | Ejecuciones individuales de experimentos, con parámetros, commit, estado y métricas. |
| `research_run_artifacts` | `id` | Referencias verificables a artefactos externos producidos/consumidos por runs. |

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

**`identity_namespaces`**
- `namespace_key TEXT PK`: clave canónica, estable y namespaced; formato recomendado `<authority>:<identifier_domain>` (por ejemplo, `coingecko:asset_id` o `eip155:contract_address`). Los ejemplos ilustran dominios distintos, no afirman que un proveedor concreto haya sido validado para CCI.
- `scope_mode TEXT NOT NULL`: CHECK `global, network`. `global` exige `network_id IS NULL` en las revisiones; `network` exige `network_id IS NOT NULL`.
- `target_level TEXT NOT NULL`: CHECK `asset, representation, both`; indica qué destino puede aprobar una revisión del namespace.
- `description TEXT NOT NULL`: definición inequívoca del emisor, dominio y semántica del identificador.
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`.
- `namespace_key`, `scope_mode` y `target_level` son inmutables. Un cambio semántico requiere una nueva clave de namespace; no se recicla ni se cambia el significado de una clave ya utilizada.
- La tabla es específica de `asset_identity_resolution_reviews.namespace`. No reemplaza ni unifica `network_identifiers.namespace` ni `instrument_identifiers.identifier_namespace`, cuyos dominios y contratos son distintos.
- Cada fila debe describir un único modo de alcance. No se admite que un mismo namespace sea global en unas revisiones y por red en otras.

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
- `identifier_type TEXT NOT NULL` (por ejemplo `eip155_chain_id`, `genesis_hash`, `asset_platform_id`).
- `identifier_value TEXT NOT NULL` (literal exacto).
- `observed_at TIMESTAMPTZ NOT NULL`, `evidence_reference TEXT NOT NULL`.
- `provider_platform_id UUID NULL`, `provider_data_source_id UUID NULL`, `provider_platform_resolution_review_id UUID NULL`, `provider_platform_resolution_status TEXT NULL` (solo para identificadores originados en una plataforma de proveedor; status debe ser `accepted`).
- FK compuesta `(provider_platform_id, provider_data_source_id) -> provider_platforms(id, data_source_id)`; obliga a que identidad de plataforma y fuente coincidan. Un trigger/servicio valida que `identifier_value` sea exactamente el literal `provider_platform_key` de esa identidad.
- FK compuesta `(provider_platform_resolution_review_id, provider_platform_id, network_id, provider_platform_resolution_status) -> provider_platform_resolution_reviews(id, provider_platform_id, candidate_network_id, resolution_status)`, con `provider_platform_resolution_status TEXT NULL`; CHECK exige que los cuatro campos de procedencia sean todos NULL para identificadores nativos, o todos completos y status = `accepted` para identificadores de plataforma. CHECK adicional exige `identifier_type = 'asset_platform_id'` cuando hay procedencia de plataforma; un trigger verifica que `namespace` coincida con `data_sources.source_key` de `provider_data_source_id`.
- UNIQUE candidato `(namespace, identifier_type, identifier_value)`, solo tras verificar que el namespace define unicidad en ese ámbito.
- UNIQUE candidato `(id, network_id)` y las claves candidatas compuestas requeridas por las FKs anteriores.
- No almacenar un chain ID aislado sin namespace ni asumir que es globalmente único. Una fila con identificador de proveedor no puede existir sin la identidad de plataforma y revisión accepted exactas.

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
- `namespace TEXT NOT NULL FK identity_namespaces(namespace_key)`
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
- Las revisiones de activo y de representación son scopes distintos. Una revisión contractual exige `network_id` y el identificador debe corresponder exactamente al contrato/alias documentado. Cada `namespace` tiene un único modo de alcance: global (red NULL) o por red (red NOT NULL); no se permite mezclarlos dentro del mismo namespace. Un trigger valida `scope_mode` contra la nulabilidad de `network_id` y `target_level` contra el destino candidato. La FK impide usar namespaces no registrados.
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

**`research_experiment_runs`**
- `id UUID PK`
- `experiment_id UUID NOT NULL FK research_experiments(id)`
- `run_key TEXT NOT NULL`; UNIQUE `(experiment_id, run_key)`
- `status TEXT NOT NULL`: CHECK `queued, running, succeeded, failed, cancelled`.
- `code_commit TEXT NOT NULL`, `protocol_version TEXT NOT NULL`
- `parameters JSONB NOT NULL DEFAULT '{}'`, `input_manifest JSONB NOT NULL DEFAULT '{}'`; ambos objetos JSON.
- `metrics JSONB NULL`; si existe debe ser objeto JSON.
- `started_at TIMESTAMPTZ NULL`, `finished_at TIMESTAMPTZ NULL`
- `error_code TEXT NULL`, `error_summary TEXT NULL`, `created_at TIMESTAMPTZ NOT NULL`.
- CHECK: fin no anterior al inicio; estado terminal exige `finished_at`; `running` exige `started_at`; `failed` exige `error_summary`.
- Transiciones: `queued → running|cancelled`; `running → succeeded|failed|cancelled`. Terminales inmutables. Trigger transaccional impide saltos y cambios de identidad.

**`research_run_artifacts`**
- `id UUID PK`, `run_id UUID NOT NULL FK research_experiment_runs(id)`
- `artifact_role TEXT NOT NULL`: CHECK `input_manifest, summary, metrics, report, dataset, log, other`.
- `logical_uri TEXT NOT NULL`, `media_type TEXT NOT NULL`
- `format TEXT NOT NULL`: CHECK `json, csv, parquet, text, other`.
- `sha256 TEXT NOT NULL`: hexadecimal minúsculo de 64 caracteres.
- `byte_size BIGINT NOT NULL CHECK (byte_size >= 0)`
- `schema_version TEXT NULL`
- `retention_class TEXT NOT NULL`: CHECK `ephemeral, research, restricted, do_not_retain`.
- `created_at TIMESTAMPTZ NOT NULL`; UNIQUE `(run_id, artifact_role, logical_uri, sha256)`.
- Almacena referencias y metadatos, no bytes ni series OHLCV.

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
| `research_experiment_runs` | UNIQUE `(experiment_id, run_key)`; `(experiment_id, created_at DESC)`; `(status, created_at DESC)` | Idempotencia lógica y operación por estado. |
| `research_run_artifacts` | UNIQUE `(run_id, artifact_role, logical_uri, sha256)`; `(run_id, created_at)` | Trazabilidad e integridad de artefactos. |

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
2. Crear `identity_namespaces` y los catálogos base `data_sources`, `assets`, `ingestion_runs`, `transformations` y `research_experiments`.
3. Crear `data_endpoints`, `source_usage_policies` y `policy_evaluations`.
4. Crear `networks`, `network_identifiers`, `asset_representations`, `asset_relationships` y `asset_identity_resolution_reviews` (esta última con FK a `identity_namespaces`), `asset_identifiers` y `asset_representation_identifiers`.
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


## 9. Candidatos iniciales de namespaces: validación documental (2026-11-06)

La revisión de documentación oficial distingue identificadores de catálogo de CoinGecko, identificadores de contratos en plataformas blockchain y códigos de activos utilizados por exchanges. Esta sección registra decisiones de diseño; no inserta filas en PostgreSQL ni afirma que se haya validado empíricamente la estabilidad histórica de los identificadores.

| namespace_key | scope_mode | target_level | Campo de origen | Estado / decisión |
|---|---|---|---|---|
| `coingecko:coin_id` | `global` | `asset` | CoinGecko API `/coins/list`: `id` | **Aprobado como namespace del proveedor.** Identifica el registro CoinGecko de una moneda; no constituye por sí solo una prueba de identidad económica universal. |
| `coingecko:contract_address` | `network` | `representation` | CoinGecko API `/coins/list?include_platform=true` y detalle de moneda: `platforms[platform_id]` / dirección de contrato | **Aprobado con condición de resolución de red.** La plataforma CoinGecko debe mapearse mediante evidencia a una fila de `networks`; no se copia el platform ID directamente como si fuera un chain ID. |
| — | — | — | Binance Spot `exchangeInfo.symbols[].baseAsset` / `quoteAsset` | **No registrar en `identity_namespaces`.** Códigos de activos del contexto de un símbolo; conservar como metadata/códigos nativos de `market_instruments`. |
| — | — | — | Kraken Spot `base_asset` / `quote_asset` y `symbol` | **No registrar en `identity_namespaces`.** Códigos de moneda y símbolo de mercado; conservar en el contexto de `market_instruments` / `instrument_identifiers`. |

### Evidencia oficial consultada

- CoinGecko, Coins List (ID Map): https://docs.coingecko.com/reference/coins-list. El endpoint devuelve `id`, `name` y `symbol`; permite incluir plataformas y direcciones de contrato. El proveedor advierte que nombres y símbolos pueden no ser únicos.
- CoinGecko, Asset Platforms List: https://docs.coingecko.com/reference/asset-platforms-list. Devuelve el ID de plataforma, identificador de cadena cuando está disponible y moneda nativa asociada; el platform ID no debe confundirse automáticamente con el identificador canónico interno de red.
- Binance Spot, Exchange Information: https://developers.binance.com/en/docs/products/spot/market-data/rest-api/exchange-information y glosario: https://developers.binance.com/en/docs/products/spot/faqs/spot_glossary. `baseAsset` designa el activo base del símbolo; no define una identidad global del activo.
- Kraken Spot, Post-Trade Data: https://docs.kraken.com/api/docs/rest-api/get-post-trade. La respuesta expone `base_asset`, `quote_asset` y `symbol` en el contexto de cada par. Esto no prueba unicidad global de los códigos.

### Reglas de uso

1. `coingecko:coin_id` solo puede resolver a `assets`; nunca se interpreta como contrato o representación blockchain.
2. `coingecko:contract_address` solo puede resolver a `asset_representations`; la clave de conflicto es (namespace, network_id, external_identifier), y la dirección original se conserva sin normalización destructiva.
3. El mapeo CoinGecko platform ID → `networks.network_key` requiere una tabla/evidencia de resolución de red independiente y verificable. La existencia de un platform ID no prueba por sí sola que coincida con un chain ID.
4. Los códigos `baseAsset`, `quoteAsset`, `base_asset` y `quote_asset` no se promueven automáticamente a `asset_identifiers`. Primero deben resolverse con evidencia explícita, evitando colisiones de tickers y alias históricos.
5. Los símbolos de pares y alias REST/WebSocket pertenecen a `market_instruments` / `instrument_identifiers`, no a namespaces de identidad de activos.
6. La aprobación documental de estos dos namespaces no autoriza a poblar el catálogo con filas hasta que se cierre la correspondencia de plataformas a redes y se revise la evidencia/versión concreta de los endpoints usados.

No se han creado migraciones, no se han insertado registros y no se han ejecutado pruebas en PostgreSQL real.


## 10. Identidad, observaciones y resolución de plataformas de proveedores

La política rectora es `network-identity-resolution-policy.md`. El inventario físico queda en **32 entidades**. Esta ampliación es de diseño: no añade filas de redes, plataformas ni mappings.

**`provider_platforms` — identidad estable de una plataforma dentro de un proveedor**
- `id UUID PK`
- `data_source_id UUID NOT NULL FK data_sources(id)`
- `provider_platform_key TEXT NOT NULL` (literal exacto del ID externo; para CoinGecko corresponde a `asset_platforms[].id`).
- `created_at TIMESTAMPTZ NOT NULL`
- UNIQUE `(data_source_id, provider_platform_key)`.
- UNIQUE candidato `(id, data_source_id)` y `(id, data_source_id, provider_platform_key)`.
- No contiene metadata mutable ni snapshots. El mismo literal en dos proveedores representa dos identidades distintas.

**`provider_platform_observations` — capturas inmutables de metadata**
- `id UUID PK`
- `provider_platform_id UUID NOT NULL`, `data_source_id UUID NOT NULL`; FK compuesta `(provider_platform_id, data_source_id) -> provider_platforms(id, data_source_id)`.
- `capture_id UUID NOT NULL` (identificador del lote de ingestión, compartido por todas las entradas del mismo snapshot).
- `observed_at TIMESTAMPTZ NOT NULL`; `recorded_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()` (sustituye a `created_at` como instante inmutable de incorporación).
- `provider_name TEXT NULL`, `provider_shortname TEXT NULL`, `provider_native_coin_id TEXT NULL`.
- `reported_chain_identifier_json JSONB NOT NULL` (escalar JSON `number` o `null`; CHECK `jsonb_typeof(reported_chain_identifier_json) IN ('number','null')`; conserva el valor numérico exacto de PostgreSQL `numeric`, sin imponer que sea entero ni confundir JSON `null` con SQL NULL). La evidencia del cuerpo HTTP y su hash permiten conservar el lexema original cuando la fidelidad byte a byte sea necesaria.
- `evidence_reference TEXT NOT NULL`, `evidence_sha256 TEXT NULL`.
- UNIQUE `(provider_platform_id, capture_id)`; UNIQUE candidato `(id, provider_platform_id)` y `(id, provider_platform_id, data_source_id)`.
- No hay UNIQUE por `observed_at`: dos capturas distintas pueden compartir timestamp. La repetición de una plataforma dentro del mismo lote se rechaza.

**`provider_platform_resolution_reviews` — decisiones append-only sobre la identidad estable**
- `id UUID PK`
- `provider_platform_id UUID NOT NULL`, `data_source_id UUID NOT NULL`; FK compuesta `(provider_platform_id, data_source_id) -> provider_platforms(id, data_source_id)`.
- `based_on_observation_id UUID NULL`; FK compuesta `(based_on_observation_id, provider_platform_id, data_source_id) -> provider_platform_observations(id, provider_platform_id, data_source_id)`.
- `candidate_network_id UUID NULL FK networks(id)`.
- `resolution_status TEXT NOT NULL`: CHECK `pending_review, accepted, rejected, ambiguous`.
- `evidence_reference TEXT NULL`, `decision_reference TEXT NULL`, `reviewed_at TIMESTAMPTZ NULL`.
- `recorded_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()` (sustituye a `created_at` como instante inmutable de registro).
- `valid_from TIMESTAMPTZ NOT NULL`, `valid_until TIMESTAMPTZ NULL` (intervalo semiabierto; CHECK `valid_until IS NULL OR valid_until > valid_from`). Toda decisión, también `pending_review`, `ambiguous` y `rejected`, debe declarar desde cuándo produce efecto; así la vista temporal puede exponer estados no resolubles y nunca omitirlos por `valid_from IS NULL`.
- `supersedes_review_id UUID NULL`; FK compuesta `(supersedes_review_id, provider_platform_id) -> provider_platform_resolution_reviews(id, provider_platform_id)`.
- CHECK `supersedes_review_id IS NULL OR valid_from IS NOT NULL`: toda sucesión debe fijar el inicio de la nueva decisión para derivar el cierre efectivo de la anterior.
- UNIQUE candidato `(id, provider_platform_id)` y `(id, provider_platform_id, candidate_network_id, resolution_status)`.
- Índices UNIQUE parciales: una sola raíz por `provider_platform_id` (`supersedes_review_id IS NULL`) y una sola sucesora por revisión (`supersedes_review_id IS NOT NULL`).
- CHECK: `accepted` exige exactamente un `candidate_network_id`, evidencia, `reviewed_at` y `valid_from`.
- `supersedes_review_id` significa exclusivamente corrección, revocación o sustitución de una decisión; nunca representa la llegada de una observación nueva.
- La FK compuesta mantiene la cadena en la misma identidad/proveedor; un trigger transaccional impide ciclos.

**`network_identifiers` — publicación del identificador externo**
- Los campos de procedencia son `provider_platform_id`, `provider_data_source_id`, `provider_platform_resolution_review_id` y `provider_platform_resolution_status`; todos NULL para identificadores nativos o todos completos para IDs de plataforma.
- La FK compuesta de plataforma referencia `provider_platforms(id, data_source_id)`; un trigger/servicio transaccional comprueba que `identifier_value = provider_platform_key`.
- La FK compuesta de revisión referencia `(id, provider_platform_id, candidate_network_id, resolution_status)` y exige destino igual a `network_id` y estado `accepted`.
- CHECK adicional exige `identifier_type = 'asset_platform_id'`; un trigger verifica que `namespace` coincida con `data_sources.source_key`.
- La publicación accepted y el mapping se realizan en una única transacción. Las consultas de vigencia deben considerar la cabeza de la cadena, no la mera existencia histórica de una fila accepted.

### Semántica temporal y concurrencia

| Campo | Significado | Inmutable |
|---|---|---|
| `observed_at` | Momento al que corresponde la observación del proveedor | Sí |
| `recorded_at` | Momento en que CCI incorporó observación o decisión | Sí |
| `valid_from/valid_until` | Periodo real de validez de la decisión | Sí, por fila |

- Los intervalos son semiabiertos `[valid_from, valid_until)`. El final efectivo de una decisión anterior se deriva del menor entre su `valid_until` explícito y el `valid_from` de su sucesora; no se actualiza la fila histórica.
- `recorded_at` permite reconstruir qué sabía CCI en `known_at`; `valid_from/valid_until` permite consultar la validez en `valid_at`.
- Una captura nueva agrega una observación; no modifica la cabeza de la cadena ni invalida automáticamente una resolución accepted.
- Se crea una revisión cuando nueva evidencia cambia materialmente la interpretación, contradice la resolución vigente, requiere corrección/revocación o una política explícita exige revalidación.
- Una cabeza `pending_review` o `ambiguous` no autoriza mappings. Una cabeza `rejected` revoca la autorización anterior. Solo una cabeza `accepted` vigente habilita el mapping.
- Antes de crear una revisión, la transacción bloquea la fila de identidad `provider_platforms` con `SELECT ... FOR UPDATE`, lee la cabeza y agrega la sucesora. El lock se toma por identidad estable, no por UUID de snapshot.
- La unicidad de raíz/sucesora evita bifurcaciones; el trigger valida misma identidad y ausencia de ciclos.

### Invariantes de resolución

1. Una identidad de plataforma no equivale a una red ni crea una red automáticamente.
2. Una observación no equivale a una decisión y no altera el estado de resolución.
3. Una revisión accepted apunta a exactamente una red; una revisión pending/rejected/ambiguous no habilita mappings.
4. Una revisión se vincula a una identidad estable; su observación de soporte, si existe, pertenece a esa misma identidad/proveedor.
5. La sucesión expresa corrección/revocación/cambio de decisión, no ingestión de snapshots.
6. Los mappings conservan namespace, tipo, literal, fuente y revisión accepted exacta.
7. La resolución de `coingecko:contract_address` solo se habilita si la cabeza es accepted y su vigencia cubre el instante consultado.
8. EVM requiere Chain ID namespaced y corroboración independiente cuando corresponda; Solana usa Genesis Hash, sin inventar Chain ID.
9. El tipo físico definitivo de `chain_identifier` queda pendiente de verificar; se conserva literal escalar y tipo JSON.

### Pruebas negativas requeridas en PostgreSQL real

- Dos observaciones con mismo `observed_at` y distinto `capture_id`: ambas deben poder insertarse.
- Misma plataforma repetida dentro de un `capture_id`: la segunda debe fallar.
- Observación/revisión vinculada a otra identidad o proveedor: debe fallar.
- Dos raíces para una plataforma o dos sucesoras de una revisión: deben fallar.
- Crear un ciclo: debe fallar.
- Nueva observación sin revisión: la resolución accepted anterior permanece.
- Mapping sin revisión accepted de la cabeza vigente, con destino distinto o literal distinto: debe fallar.
- Dos transacciones concurrentes que creen sucesoras incompatibles: se serializan y solo una confirma.
- Publicación parcial de revisión/mapping: rollback atómico.

### Estado de implementación

El contrato lógico/físico de este subsistema está definido en esta sección y en la sección 13. Su DDL de laboratorio se encuentra en `tests/postgresql/001_provider_platform_lab.sql` y sus pruebas de motor en `tests/test_postgresql_lab.py`; la ejecución confirmatoria documentada en el plan de laboratorio alcanzó 29/29 pruebas en PostgreSQL 16.15.

Esto no constituye una migración productiva: el laboratorio usa el esquema desechable `cci_lab`, no integra todavía todas las FKs con las 32 entidades del esquema `cci` y no define roles/grants productivos. No se han creado migraciones productivas ni se han cargado datos reales. Las pruebas Python de contratos siguen siendo distintas de las pruebas del motor.


## 13. Garantías SQL concretas para resolución de plataformas

Esta sección convierte los invariantes de la sección 10 en objetos PostgreSQL nominados. Es una especificación para el futuro DDL, no una migración ejecutable sobre el esquema actual. Los nombres de constraints e índices son normativos para que las pruebas puedan referenciarlos.

### 13.1 Claves candidatas requeridas

Antes de declarar las FKs compuestas, deben existir estas claves únicas:

- `provider_platforms_uq_id_source UNIQUE (id, data_source_id)`.
- `provider_platforms_uq_id_source_key UNIQUE (id, data_source_id, provider_platform_key)`.
- `provider_platform_observations_uq_id_platform UNIQUE (id, provider_platform_id)` y `provider_platform_observations_uq_id_platform_source UNIQUE (id, provider_platform_id, data_source_id)`.
- `provider_platform_resolution_reviews_uq_id_platform UNIQUE (id, provider_platform_id)`.
- `provider_platform_resolution_reviews_uq_mapping UNIQUE (id, provider_platform_id, candidate_network_id, resolution_status)`.

Las restricciones `UNIQUE` anteriores son necesarias como objetivos de FKs, aunque algunas columnas ya formen parte de una PK. PostgreSQL exige una clave única que coincida con las columnas referenciadas.

### 13.2 FKs y CHECKs normativos

**Observaciones**
- `provider_platform_observations_fk_platform_source`: `(provider_platform_id, data_source_id) REFERENCES provider_platforms(id, data_source_id) ON UPDATE RESTRICT ON DELETE RESTRICT`.
- `provider_platform_observations_uq_capture`: `UNIQUE (provider_platform_id, capture_id)`.

**Revisiones**
- `provider_platform_resolution_reviews_fk_platform_source`: `(provider_platform_id, data_source_id) REFERENCES provider_platforms(id, data_source_id) ON UPDATE RESTRICT ON DELETE RESTRICT`.
- `provider_platform_resolution_reviews_fk_observation`: `(based_on_observation_id, provider_platform_id, data_source_id) REFERENCES provider_platform_observations(id, provider_platform_id, data_source_id) ON UPDATE RESTRICT ON DELETE RESTRICT`. Al ser nullable `based_on_observation_id`, se usa `MATCH SIMPLE` (default): o es NULL, o la FK compuesta debe coincidir.
- `provider_platform_resolution_reviews_fk_successor_chain`: `(supersedes_review_id, provider_platform_id) REFERENCES provider_platform_resolution_reviews(id, provider_platform_id) ON UPDATE RESTRICT ON DELETE RESTRICT`.
- `provider_platform_resolution_reviews_ck_validity`: `valid_until IS NULL OR valid_until > valid_from`; `valid_from` es `NOT NULL` en la columna para todas las revisiones, incluidas raíces y estados no accepted.
- `provider_platform_resolution_reviews_ck_accepted`: `resolution_status <> 'accepted' OR (candidate_network_id IS NOT NULL AND evidence_reference IS NOT NULL AND btrim(evidence_reference) <> '' AND reviewed_at IS NOT NULL AND valid_from IS NOT NULL)`.
- CHECK de vocabulario: `resolution_status IN ('pending_review','accepted','rejected','ambiguous')`.

**Redes y mappings**
- `network_identifiers_fk_platform_source`: `(provider_platform_id, provider_data_source_id) REFERENCES provider_platforms(id, data_source_id) ON UPDATE RESTRICT ON DELETE RESTRICT`.
- `network_identifiers_fk_accepted_review`: `(provider_platform_resolution_review_id, provider_platform_id, network_id, provider_platform_resolution_status) REFERENCES provider_platform_resolution_reviews(id, provider_platform_id, candidate_network_id, resolution_status) ON UPDATE RESTRICT ON DELETE RESTRICT`.
- CHECK de procedencia: los cuatro campos `provider_platform_id`, `provider_data_source_id`, `provider_platform_resolution_review_id` y `provider_platform_resolution_status` son todos NULL (identificador nativo) o todos NOT NULL (identificador de plataforma); en el segundo caso el status debe ser literalmente `accepted` y `identifier_type = 'asset_platform_id'`.
- Para mapping de plataforma, `network_id` e `identifier_value` son NOT NULL (ya lo son en el contrato base); la FK compuesta obliga a que `network_id = candidate_network_id` de la revisión accepted.
- UNIQUE `network_identifiers_uq_review` sobre `(provider_platform_resolution_review_id)` WHERE `provider_platform_resolution_review_id IS NOT NULL`: una decisión accepted no publica dos filas de mapping.
- No crear un UNIQUE global adicional sobre `(namespace, identifier_type, identifier_value)` hasta confirmar su ámbito; el ID externo se interpreta dentro de su proveedor.

La FK compuesta de mapping debe tener como destino la clave candidata de cinco columnas indicada arriba. El campo `provider_platform_resolution_status` se mantiene redundante deliberadamente para que la FK fuerce el literal accepted; el CHECK impide otros estados. No se permite `ON DELETE CASCADE` en estas relaciones históricas.

### 13.3 Índices UNIQUE parciales de cadena

- `provider_platform_reviews_uq_root`: UNIQUE `(provider_platform_id)` WHERE `supersedes_review_id IS NULL`.
- `provider_platform_reviews_uq_successor`: UNIQUE `(supersedes_review_id)` WHERE `supersedes_review_id IS NOT NULL`.

La FK auto-referencial compuesta impide sucesión entre plataformas. El índice de raíz impide dos raíces y el de sucesora impide bifurcaciones. Estos índices no impiden por sí solos ciclos; para eso se requiere el trigger.

### 13.4 Triggers requeridos

1. `trg_provider_platform_observations_immutable`: BEFORE UPDATE OR DELETE; rechaza cualquier modificación/borrado de snapshots. Las correcciones se insertan como nuevas observaciones.
2. `trg_provider_platform_reviews_immutable`: BEFORE UPDATE OR DELETE; rechaza cambios/borrados de decisiones. La única operación válida es insertar una sucesora.
3. `trg_provider_platform_review_chain_guard`: BEFORE INSERT; toma `SELECT ... FOR UPDATE` sobre la identidad `provider_platforms.id`; valida que `supersedes_review_id`, si existe, sea la cabeza actual (ninguna fila la sucede), pertenezca a esa identidad, y que `NEW.valid_from` no sea anterior al `valid_from` de su predecesora. Para una raíz, exige que todavía no haya revisiones de esa identidad. La FK compuesta impide cruzar de identidad; los índices parciales impiden raíces duplicadas y bifurcaciones. La cadena se construye solo por INSERT y las revisiones son inmutables, por lo que una cadena cíclica no puede construirse mediante el flujo autorizado: la FK inmediata exige que la predecesora ya exista y el trigger solo admite la cabeza actual. No se implementa un recorrido recursivo de ancestros dentro del trigger.
4. `trg_network_identifier_platform_guard`: BEFORE INSERT; para filas con procedencia de plataforma, bloquea la identidad, lee fuente y revisión, exige `identifier_value = provider_platform_key`, `namespace = data_sources.source_key || ':asset_platform_id'`, `identifier_type = 'asset_platform_id'`, `resolution_status = 'accepted'` y que la revisión sea la cabeza (sin sucesora). No exige que `valid_from <= now()`: se permite publicar una decisión accepted futura; las vistas solo la exponen cuando entra en vigor. La FK/check garantizan plataforma, red y estado; el trigger valida literales y cabeza.
5. Los triggers de inmutabilidad deben ejecutarse también para roles de aplicación; las tablas no deben conceder UPDATE/DELETE al rol de ingestión/revisión. Un owner privilegiado puede eludir triggers, por lo que operaciones administrativas quedan fuera del contrato normal y deben auditarse.

La función de cadena debe rechazar que una revisión nueva apunte a una revisión que ya tenga sucesora. La comprobación de ciclo es defensiva: con una cabeza única y sin permitir sucesor de una no-cabeza, un ciclo no puede construirse mediante el flujo autorizado.

### 13.5 Vista de resolución vigente

No se debe definir la vigencia como «la revisión accepted más reciente» ni como «existe cualquier revisión accepted». Una decisión anterior puede seguir vigente hasta el `valid_from` de una sucesora futura. La consulta deriva el final efectivo usando la sucesora directa:

```sql
CREATE VIEW provider_platform_resolution_current AS
SELECT
    r.provider_platform_id,
    r.data_source_id,
    r.id AS resolution_review_id,
    r.candidate_network_id AS network_id,
    r.resolution_status,
    r.valid_from,
    r.valid_until,
    r.recorded_at,
    LEAST(
        COALESCE(r.valid_until, 'infinity'::timestamptz),
        COALESCE(s.valid_from, 'infinity'::timestamptz)
    ) AS effective_valid_until
FROM provider_platform_resolution_reviews AS r
LEFT JOIN provider_platform_resolution_reviews AS s
  ON s.supersedes_review_id = r.id
WHERE r.valid_from <= statement_timestamp()
  AND statement_timestamp() < LEAST(
        COALESCE(r.valid_until, 'infinity'::timestamptz),
        COALESCE(s.valid_from, 'infinity'::timestamptz)
      );
```

La vista puede devolver como máximo una revisión por identidad si las reglas de cadena se cumplen y el trigger impide que `valid_from` retroceda en la cadena. La autorización de resolución de plataforma se obtiene filtrando `resolution_status = 'accepted'`; una revisión `pending_review`, `ambiguous` o `rejected` efectiva devuelve estado no resoluble y no habilita el mapping.

La vista de mapping publicable debe unir la resolución efectiva accepted con la fila histórica que referencia esa revisión:

```sql
CREATE VIEW provider_platform_mappings_current AS
SELECT
    m.provider_platform_id,
    m.provider_data_source_id AS data_source_id,
    m.network_id,
    m.namespace,
    m.identifier_type,
    m.identifier_value,
    m.provider_platform_resolution_review_id AS resolution_review_id
FROM network_identifiers AS m
JOIN provider_platform_resolution_current AS r
  ON r.resolution_review_id = m.provider_platform_resolution_review_id
 AND r.provider_platform_id = m.provider_platform_id
 AND r.data_source_id = m.provider_data_source_id
 AND r.network_id = m.network_id
WHERE r.resolution_status = 'accepted'
  AND m.provider_platform_resolution_status = 'accepted';
```

Esta vista no elimina mappings históricos: al entrar en vigor una sucesora no accepted, el mapping anterior deja de aparecer; si una nueva sucesora accepted entra en vigor, aparece el mapping vinculado a esa revisión.

Para reconstrucción bitemporal no basta la vista «ahora»: la consulta debe recibir ambos parámetros `valid_at` y `known_at`, excluir revisiones con `recorded_at > known_at), y truncar una revisión solo por una sucesora que también fuera conocida en `known_at`. Esta consulta parametrizada se incluirá en la capa de repositorio; no se simulará con una vista fija.

### 13.6 Publicación atómica y revocaciones

El único flujo autorizado para aceptar y publicar un mapping es una transacción PostgreSQL:

1. `BEGIN`.
2. `SELECT id FROM provider_platforms WHERE id = :platform_id FOR UPDATE`, en una sentencia independiente y antes de cualquier INSERT de revisión o mapping. Bajo `READ COMMITTED`, la sentencia posterior obtiene un snapshot nuevo después de esperar el lock; no se debe confiar exclusivamente en un lock adquirido dentro de un trigger ejecutado por el mismo INSERT.
3. Leer la cabeza de la cadena y comprobar que la nueva decisión la sucede (o es la raíz si no existe revisión previa).
4. Insertar la revisión accepted con red, evidencia, `reviewed_at`, `recorded_at` y `valid_from`.
5. Insertar `network_identifiers` con el mismo `provider_platform_id`, proveedor, red, literal externo, revisión y status accepted.
6. `COMMIT`; cualquier fallo ejecuta `ROLLBACK`.

El mapping no se publica antes de que la revisión exista. La FK compuesta hace imposible publicar una red distinta de la candidata accepted. Para una decisión `rejected`, `ambiguous` o `pending_review`, la transacción inserta únicamente la revisión y no inserta mapping.

**Revocación/corrección:** insertar una revisión sucesora `rejected`, `ambiguous` o `pending_review` con su `valid_from`; no actualizar ni borrar la revisión ni el mapping históricos. La vista deja de exponer el mapping accepted a partir del inicio efectivo de la sucesora. Una nueva decisión accepted posterior crea otra sucesora y su mapping histórico asociado. No se reescriben filas previas.

Una nueva observación por sí sola no revoca ni cambia la vista. La revocación debe ser una decisión explícita.

### 13.7 Contrato CoinGecko: NET-06 cerrado documentalmente

La referencia oficial del endpoint **Asset Platforms List** declara `chain_identifier` como `number | null`, y lo describe como el Chain ID de Chainlist. No declara que el tipo JSON sea específicamente integer. Por tanto:
- `reported_chain_identifier_json JSONB NOT NULL` conserva el escalar JSON number o JSON null y evita un tipo binario aproximado (`REAL`/`DOUBLE PRECISION`).
- CHECK: `jsonb_typeof(reported_chain_identifier_json) IN ('number','null')`.
- No forzar integridad de entero en la columna de observación. La política de identidad EVM podrá extraer/validar un valor entero exacto antes de crear un `network_identifier` namespaced `eip155`.
- Para fidelidad del lexema recibido (p. ej. `137` frente a `1.37e2`), conservar el cuerpo HTTP original o su artefacto de evidencia con hash; JSONB preserva el valor numérico, no el formato textual exacto del token.
- JSON null se almacena como JSONB `'null'::jsonb`; SQL NULL se reserva para ausencia/no disponibilidad de la observación completa y no se usa para representar un null explícito del proveedor.

Fuente oficial: https://docs.coingecko.com/reference/asset-platforms-list. La documentación visible confirma `number | null`; no confirma semántica de integer. Esta decisión cierra el tipo físico sin sobreinterpretar el contrato.

### 13.8 Matriz de pruebas del motor PostgreSQL

| ID | Fixture / operación | Resultado exigido |
|---|---|---|
| PG-NET-01 | Insertar observación con plataforma/fuente no coincidentes | FK compuesta rechaza |
| PG-NET-02 | Dos observaciones misma plataforma + capture_id | UNIQUE rechaza segunda |
| PG-NET-03 | Dos observaciones mismo observed_at, capture_id distinto | Ambas aceptadas |
| PG-NET-04 | Revisar observación de otra plataforma/fuente | FK compuesta rechaza |
| PG-NET-05 | Segunda raíz para la misma plataforma | UNIQUE parcial rechaza |
| PG-NET-06 | Segunda sucesora para la misma revisión | UNIQUE parcial rechaza |
| PG-NET-07 | Sucesora cruza de plataforma | FK compuesta rechaza |
| PG-NET-08 | Sucesora apunta a revisión que no es cabeza | Trigger rechaza |
| PG-NET-09 | Crear ciclo mediante inserción directa | Trigger rechaza |
| PG-NET-10 | UPDATE/DELETE de observación o revisión | Trigger/permisos rechazan |
| PG-NET-11 | Mapping con campos de procedencia parcialmente NULL | CHECK rechaza |
| PG-NET-12 | Mapping con status pending/rejected/ambiguous | CHECK/FK rechazan |
| PG-NET-13 | Mapping con revisión accepted pero network_id diferente | FK compuesta rechaza |
| PG-NET-14 | Mapping con literal distinto del provider_platform_key | Trigger rechaza |
| PG-NET-15 | Mapping con namespace no derivado del source_key | Trigger rechaza |
| PG-NET-16 | Nueva observación sin revisión | Mapping vigente no cambia |
| PG-NET-17 | Sucesora rejected entra en vigor | Vista deja de resolver la plataforma |
| PG-NET-18 | Sucesora futura aún no entra en vigor | Revisión anterior sigue efectiva |
| PG-NET-19 | Error después de insertar revisión y antes de mapping | ROLLBACK elimina ambos inserts |
| PG-NET-20 | Dos sesiones crean sucesoras incompatibles concurrentemente | Una espera; solo una sucesora confirma |
| PG-NET-21 | Dos sesiones publican mappings de la misma plataforma/redes distintas | Serialización; no pueden quedar dos resoluciones vigentes |
| PG-NET-22 | chain_identifier JSON number, null, string, boolean, object o array | number/null aceptados; los otros tipos rechazados |
| PG-NET-23 | chain_identifier JSON number con exponente o decimal | Se conserva exacto; no se fuerza integer en observación |
| PG-NET-24 | Consulta bitemporal con known_at anterior a una revocación | Devuelve lo que CCI conocía entonces |
| PG-NET-25 | Consulta bitemporal con valid_at antes/después del límite semiabierto | Resultado respeta [valid_from, effective_valid_until) |

Las pruebas PG-NET-20/21 deben usar dos conexiones PostgreSQL independientes y barreras coordinadas; no pueden simularse con mocks ni con una sola transacción secuencial.

### Estado de esta especificación

NET-04/NET-05 quedan traducidos a claves, FKs, índices, triggers, vistas, flujo transaccional y pruebas. NET-06 queda cerrado a nivel de contrato: CoinGecko declara `number | null`; se adopta JSONB escalar exacto y se conserva el cuerpo de evidencia para el lexema.

El contrato de laboratorio está materializado en `tests/postgresql/001_provider_platform_lab.sql` y fue ejecutado contra PostgreSQL 16.15 con 29/29 pruebas aprobadas (Run #38, HEAD probado `55ba44449a1016e7902e90271801ef8ee3f05fa2`). La auditoría de equivalencia laboratorio ↔ especificación está documentada en `postgresql-lab-validation-plan.md`.

**Límite de promoción:** este resultado valida únicamente el subsistema reducido de seis tablas dentro de `cci_lab`. No valida el esquema completo de 32 entidades, la migración desde una base vacía, ni los roles/grants productivos. La especificación de producción sigue siendo propuesta y no se han creado migraciones productivas ni cargado datos reales. La integración en `cci` debe conservar este contrato funcional y añadir sus dependencias, permisos y pruebas de integración.
