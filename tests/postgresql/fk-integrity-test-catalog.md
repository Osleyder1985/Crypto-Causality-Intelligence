# Catálogo de pruebas de integridad referencial — Issue #25

- Base: `postgresql-fk-normalized-matrix.md` (60 relaciones).
- Objetivo: especificar una prueba positiva y una negativa por cada FK.
- Total planificado: 120 casos (60 positivos, 60 negativos).
- Estado: **diseño de pruebas; no son tests implementados ni ejecutados**.
- Motor objetivo: PostgreSQL 16, instalación completa desde base vacía, fixtures sintéticos.
- SQLSTATE esperado para violación FK: `23503`; los CHECK, triggers y UNIQUE pueden producir SQLSTATE distintos y deben comprobarse por constraint/condición concreta.

## 1. Casos por relación

| FK | Test ID | Escenario y resultado esperado |
|---|---|---|
| FK-001 | `P-FK-001` | Crear primero la fila destino en `data_sources` con `id`; insertar después la fila origen en `data_endpoints` con `data_source_id` exactamente coincidentes. Esperado: INSERT aceptado. |
| FK-001 | `N-FK-001` | Insertar la fila origen en `data_endpoints` con un valor `data_source_id` que no exista en `data_sources.id`. Esperado: violación FK (SQLSTATE 23503). |
| FK-002 | `P-FK-002` | Crear primero la fila destino en `data_sources` con `id`; insertar después la fila origen en `source_usage_policies` con `data_source_id` exactamente coincidentes. Esperado: INSERT aceptado. |
| FK-002 | `N-FK-002` | Insertar la fila origen en `source_usage_policies` con un valor `data_source_id` que no exista en `data_sources.id`. Esperado: violación FK (SQLSTATE 23503). |
| FK-003 | `P-FK-003` | Crear primero la fila destino en `data_endpoints` con `id, data_source_id`; insertar después la fila origen en `source_usage_policies` con `data_endpoint_id, data_source_id` exactamente coincidentes. Esperado: INSERT aceptado. |
| FK-003 | `N-FK-003` | Conservar una fila destino válida, mantener **todos los componentes de la FK NOT NULL**, y alterar un componente no nulo de `data_endpoint_id, data_source_id` para que no coincida con la tupla `id, data_source_id`. Esperado: violación FK (SQLSTATE 23503). Mantener todos los componentes no nulos; con MATCH SIMPLE, un NULL podría omitir la comprobación compuesta. |
| FK-004 | `P-FK-004` | Crear primero la fila destino en `source_usage_policies` con `id, data_source_id`; insertar después la fila origen en `policy_evaluations` con `source_usage_policy_id, data_source_id` exactamente coincidentes. Esperado: INSERT aceptado. |
| FK-004 | `N-FK-004` | Conservar una fila destino válida, mantener todos los componentes de la FK NOT NULL, y alterar un componente no nulo de `source_usage_policy_id, data_source_id` para que no coincida con la tupla `id, data_source_id`. Esperado: violación FK (SQLSTATE 23503). Mantener todos los componentes no nulos; con MATCH SIMPLE, un NULL podría omitir la comprobación compuesta. |
| FK-005 | `P-FK-005` | Crear primero la fila destino en `data_sources` con `id`; insertar después la fila origen en `policy_evaluations` con `data_source_id` exactamente coincidentes. Esperado: INSERT aceptado. |
| FK-005 | `N-FK-005` | Insertar la fila origen en `policy_evaluations` con un valor `data_source_id` que no exista en `data_sources.id`. Esperado: violación FK (SQLSTATE 23503). |
| FK-006 | `P-FK-006` | Crear primero la fila destino en `data_endpoints` con `id, data_source_id`; insertar después la fila origen en `policy_evaluations` con `data_endpoint_id, data_source_id` exactamente coincidentes. Esperado: INSERT aceptado. |
| FK-006 | `N-FK-006` | Conservar una fila destino válida, mantener todos los componentes de la FK NOT NULL, y alterar un componente no nulo de `data_endpoint_id, data_source_id` para que no coincida con la tupla `id, data_source_id`. Esperado: violación FK (SQLSTATE 23503). Mantener todos los componentes no nulos; con MATCH SIMPLE, un NULL podría omitir la comprobación compuesta. |
| FK-007 | `P-FK-007` | Crear primero la fila destino en `networks` con `id`; insertar después la fila origen en `network_identifiers` con `network_id` exactamente coincidentes. Esperado: INSERT aceptado. |
| FK-007 | `N-FK-007` | Insertar la fila origen en `network_identifiers` con un valor `network_id` que no exista en `networks.id`. Esperado: violación FK (SQLSTATE 23503). |
| FK-008 | `P-FK-008` | Crear plataforma y fuente coincidentes, o usar ambos campos de procedencia NULL para un identificador nativo. Esperado: aceptación en ambos estados válidos. |
| FK-008 | `N-FK-008` | Proporcionar provider_platform_id sin provider_data_source_id (o viceversa). Esperado: rechazo por CHECK de procedencia; no basta la FK compuesta. |
| FK-009 | `P-FK-009` | Para identificador nativo: mantener network_id válido y los cuatro campos de procedencia NULL. Para plataforma: usar revisión accepted y coincidencia exacta plataforma/red/status. Esperado: aceptación. |
| FK-009 | `N-FK-009` | Usar revisión pending/rejected, red distinta de candidate_network_id o procedencia parcialmente NULL. Esperado: rechazo por FK o CHECK. |
| FK-010 | `P-FK-010` | Crear primero la fila destino en `data_sources` con `id`; insertar después la fila origen en `provider_platforms` con `data_source_id` exactamente coincidentes. Esperado: INSERT aceptado. |
| FK-010 | `N-FK-010` | Insertar la fila origen en `provider_platforms` con un valor `data_source_id` que no exista en `data_sources.id`. Esperado: violación FK (SQLSTATE 23503). |
| FK-011 | `P-FK-011` | Crear primero la fila destino en `provider_platforms` con `id, data_source_id`; insertar después la fila origen en `provider_platform_observations` con `provider_platform_id, data_source_id` exactamente coincidentes. Esperado: INSERT aceptado. |
| FK-011 | `N-FK-011` | Conservar una fila destino válida, mantener todos los componentes de la FK NOT NULL, y alterar un componente no nulo de `provider_platform_id, data_source_id` para que no coincida con la tupla `id, data_source_id`. Esperado: violación FK (SQLSTATE 23503). Mantener todos los componentes no nulos; con MATCH SIMPLE, un NULL podría omitir la comprobación compuesta. |
| FK-012 | `P-FK-012` | Crear primero la fila destino en `provider_platforms` con `id, data_source_id`; insertar después la fila origen en `provider_platform_resolution_reviews` con `provider_platform_id, data_source_id` exactamente coincidentes. Esperado: INSERT aceptado. |
| FK-012 | `N-FK-012` | Conservar una fila destino válida, mantener todos los componentes de la FK NOT NULL, y alterar un componente no nulo de `provider_platform_id, data_source_id` para que no coincida con la tupla `id, data_source_id`. Esperado: violación FK (SQLSTATE 23503). Mantener todos los componentes no nulos; con MATCH SIMPLE, un NULL podría omitir la comprobación compuesta. |
| FK-013 | `P-FK-013` | Insertar revisión con based_on_observation_id NULL o con observación de la misma plataforma/fuente. Esperado: aceptación. |
| FK-013 | `N-FK-013` | Referenciar observación existente de otra plataforma o fuente. Esperado: violación FK 23503. |
| FK-014 | `P-FK-014` | Crear primero la fila destino en `networks` con `id`; insertar después la fila origen en `provider_platform_resolution_reviews` con `candidate_network_id` exactamente coincidentes. Esperado: INSERT aceptado. |
| FK-014 | `N-FK-014` | Insertar la fila origen en `provider_platform_resolution_reviews` con un valor `candidate_network_id` que no exista en `networks.id`. Esperado: violación FK (SQLSTATE 23503). |
| FK-015 | `P-FK-015` | Crear sucesora que apunte a la cabeza vigente de la misma plataforma. Esperado: aceptación si trigger y UNIQUE parciales permiten la cadena. |
| FK-015 | `N-FK-015` | Apuntar a revisión de otra plataforma, a una revisión que ya tenga sucesora o construir una raíz/ramificación duplicada. Esperado: rechazo FK/índice/trigger. |
| FK-016 | `P-FK-016` | Crear primero la fila destino en `assets` con `id`; insertar después la fila origen en `asset_representations` con `asset_id` exactamente coincidentes. Esperado: INSERT aceptado. |
| FK-016 | `N-FK-016` | Insertar la fila origen en `asset_representations` con un valor `asset_id` que no exista en `assets.id`. Esperado: violación FK (SQLSTATE 23503). |
| FK-017 | `P-FK-017` | Crear primero la fila destino en `networks` con `id`; insertar después la fila origen en `asset_representations` con `network_id` exactamente coincidentes. Esperado: INSERT aceptado. |
| FK-017 | `N-FK-017` | Insertar la fila origen en `asset_representations` con un valor `network_id` que no exista en `networks.id`. Esperado: violación FK (SQLSTATE 23503). |
| FK-018 | `P-FK-018` | Crear primero la fila destino en `assets` con `id`; insertar después la fila origen en `asset_relationships` con `subject_asset_id` exactamente coincidentes. Esperado: INSERT aceptado. |
| FK-018 | `N-FK-018` | Insertar la fila origen en `asset_relationships` con un valor `subject_asset_id` que no exista en `assets.id`. Esperado: violación FK (SQLSTATE 23503). |
| FK-019 | `P-FK-019` | Crear primero la fila destino en `assets` con `id`; insertar después la fila origen en `asset_relationships` con `object_asset_id` exactamente coincidentes. Esperado: INSERT aceptado. |
| FK-019 | `N-FK-019` | Insertar la fila origen en `asset_relationships` con un valor `object_asset_id` que no exista en `assets.id`. Esperado: violación FK (SQLSTATE 23503). |
| FK-020 | `P-FK-020` | Crear primero la fila destino en `identity_namespaces` con `namespace_key`; insertar después la fila origen en `asset_identity_resolution_reviews` con `namespace` exactamente coincidentes. Esperado: INSERT aceptado. |
| FK-020 | `N-FK-020` | Insertar la fila origen en `asset_identity_resolution_reviews` con un valor `namespace` que no exista en `identity_namespaces.namespace_key`. Esperado: violación FK (SQLSTATE 23503). |
| FK-021 | `P-FK-021` | Usar network_id NULL con namespace global o una red existente con namespace por red. Esperado: aceptación. |
| FK-021 | `N-FK-021` | Usar network_id NULL con namespace por red o una red con namespace global. Esperado: rechazo por trigger de scope. |
| FK-022 | `P-FK-022` | Mantener el destino candidato NULL para estados no accepted; para accepted, exactamente uno de candidate_asset_id/candidate_asset_representation_id debe estar informado. Esperado: aceptación solo con CHECK satisfecho. |
| FK-022 | `N-FK-022` | Crear revisión accepted con ambos destinos NULL o ambos NOT NULL. Esperado: rechazo por CHECK. |
| FK-023 | `P-FK-023` | Mantener el destino candidato NULL para estados no accepted; para accepted, exactamente uno de candidate_asset_id/candidate_asset_representation_id debe estar informado. Esperado: aceptación solo con CHECK satisfecho. |
| FK-023 | `N-FK-023` | Crear revisión accepted con ambos destinos NULL o ambos NOT NULL. Esperado: rechazo por CHECK. |
| FK-024 | `P-FK-024` | Insertar sucesora que apunte a una revisión previa de la misma clave de identidad. Esperado: aceptación si cumple regla de cabeza. |
| FK-024 | `N-FK-024` | Apuntar a revisión de otra clave, a sí misma, a revisión ya sucedida o crear rama/ciclo. Esperado: rechazo por trigger/función. |
| FK-025 | `P-FK-025` | Crear primero la fila destino en `assets` con `id`; insertar después la fila origen en `asset_identifiers` con `asset_id` exactamente coincidentes. Esperado: INSERT aceptado. |
| FK-025 | `N-FK-025` | Insertar la fila origen en `asset_identifiers` con un valor `asset_id` que no exista en `assets.id`. Esperado: violación FK (SQLSTATE 23503). |
| FK-026 | `P-FK-026` | Crear primero la fila destino en `networks` con `id`; insertar después la fila origen en `asset_identifiers` con `network_id` exactamente coincidentes. Esperado: INSERT aceptado. |
| FK-026 | `N-FK-026` | Insertar la fila origen en `asset_identifiers` con un valor `network_id` que no exista en `networks.id`. Esperado: violación FK (SQLSTATE 23503). |
| FK-027 | `P-FK-027` | Publicar mapping solo con revisión accepted que coincida en activo, namespace e identificador; comparar network_id con semántica NULL-safe. Esperado: aceptación. |
| FK-027 | `N-FK-027` | Usar revisión pending/rejected o cambiar activo, namespace, identificador o ámbito de red. Esperado: rechazo FK/trigger. |
| FK-028 | `P-FK-028` | Vincular representación existente con su network_id exacto. Esperado: aceptación. |
| FK-028 | `N-FK-028` | Vincular una representación con otra red, aunque la representación exista. Esperado: violación FK 23503. |
| FK-029 | `P-FK-029` | Publicar mapping de representación solo con revisión accepted que coincida en representación, red, namespace e identificador. Esperado: aceptación. |
| FK-029 | `N-FK-029` | Cambiar uno de esos componentes o usar revisión no accepted. Esperado: violación FK 23503. |
| FK-030 | `P-FK-030` | Crear primero la fila destino en `data_sources` con `id`; insertar después la fila origen en `market_instruments` con `data_source_id` exactamente coincidentes. Esperado: INSERT aceptado. |
| FK-030 | `N-FK-030` | Insertar la fila origen en `market_instruments` con un valor `data_source_id` que no exista en `data_sources.id`. Esperado: violación FK (SQLSTATE 23503). |
| FK-031 | `P-FK-031` | Aceptar ambos asset IDs NULL o ambos existentes y distintos. Esperado: aceptación. |
| FK-031 | `N-FK-031` | Probar un solo asset ID NULL o ambos IDs iguales. Esperado: rechazo por CHECK (el FK por separado no garantiza la pareja). |
| FK-032 | `P-FK-032` | Aceptar ambos asset IDs NULL o ambos existentes y distintos. Esperado: aceptación. |
| FK-032 | `N-FK-032` | Probar un solo asset ID NULL o ambos IDs iguales. Esperado: rechazo por CHECK (el FK por separado no garantiza la pareja). |
| FK-033 | `P-FK-033` | Crear primero la fila destino en `market_instruments` con `id`; insertar después la fila origen en `instrument_identifiers` con `market_instrument_id` exactamente coincidentes. Esperado: INSERT aceptado. |
| FK-033 | `N-FK-033` | Insertar la fila origen en `instrument_identifiers` con un valor `market_instrument_id` que no exista en `market_instruments.id`. Esperado: violación FK (SQLSTATE 23503). |
| FK-034 | `P-FK-034` | Crear primero la fila destino en `market_instruments` con `id`; insertar después la fila origen en `instrument_metadata_versions` con `market_instrument_id` exactamente coincidentes. Esperado: INSERT aceptado. |
| FK-034 | `N-FK-034` | Insertar la fila origen en `instrument_metadata_versions` con un valor `market_instrument_id` que no exista en `market_instruments.id`. Esperado: violación FK (SQLSTATE 23503). |
| FK-035 | `P-FK-035` | Crear primero la fila destino en `datasets` con `id`; insertar después la fila origen en `instrument_metadata_versions` con `source_dataset_id` exactamente coincidentes. Esperado: INSERT aceptado. |
| FK-035 | `N-FK-035` | Insertar la fila origen en `instrument_metadata_versions` con un valor `source_dataset_id` que no exista en `datasets.id`. Esperado: violación FK (SQLSTATE 23503). |
| FK-036 | `P-FK-036` | Crear primero la fila destino en `instrument_metadata_versions` con `id`; insertar después la fila origen en `instrument_trading_rules` con `metadata_version_id` exactamente coincidentes. Esperado: INSERT aceptado. |
| FK-036 | `N-FK-036` | Insertar la fila origen en `instrument_trading_rules` con un valor `metadata_version_id` que no exista en `instrument_metadata_versions.id`. Esperado: violación FK (SQLSTATE 23503). |
| FK-037 | `P-FK-037` | Crear primero la fila destino en `ingestion_runs` con `id`; insertar después la fila origen en `ingestion_requests` con `ingestion_run_id` exactamente coincidentes. Esperado: INSERT aceptado. |
| FK-037 | `N-FK-037` | Insertar la fila origen en `ingestion_requests` con un valor `ingestion_run_id` que no exista en `ingestion_runs.id`. Esperado: violación FK (SQLSTATE 23503). |
| FK-038 | `P-FK-038` | Crear primero la fila destino en `data_sources` con `id`; insertar después la fila origen en `ingestion_requests` con `data_source_id` exactamente coincidentes. Esperado: INSERT aceptado. |
| FK-038 | `N-FK-038` | Insertar la fila origen en `ingestion_requests` con un valor `data_source_id` que no exista en `data_sources.id`. Esperado: violación FK (SQLSTATE 23503). |
| FK-039 | `P-FK-039` | Crear primero la fila destino en `data_endpoints` con `id, data_source_id`; insertar después la fila origen en `ingestion_requests` con `data_endpoint_id, data_source_id` exactamente coincidentes. Esperado: INSERT aceptado. |
| FK-039 | `N-FK-039` | Conservar una fila destino válida, mantener todos los componentes de la FK NOT NULL, y alterar un componente no nulo de `data_endpoint_id, data_source_id` para que no coincida con la tupla `id, data_source_id`. Esperado: violación FK (SQLSTATE 23503). Mantener todos los componentes no nulos; con MATCH SIMPLE, un NULL podría omitir la comprobación compuesta. |
| FK-040 | `P-FK-040` | Probar market_instrument_id NULL y, por separado, un instrumento existente de la misma fuente. Esperado: ambas formas aceptadas. |
| FK-040 | `N-FK-040` | Con instrumento informado, usar un instrumento de otra fuente. Esperado: violación FK 23503. |
| FK-041 | `P-FK-041` | Crear primero la fila destino en `ingestion_runs` con `id`; insertar después la fila origen en `run_datasets` con `ingestion_run_id` exactamente coincidentes. Esperado: INSERT aceptado. |
| FK-041 | `N-FK-041` | Insertar la fila origen en `run_datasets` con un valor `ingestion_run_id` que no exista en `ingestion_runs.id`. Esperado: violación FK (SQLSTATE 23503). |
| FK-042 | `P-FK-042` | Crear primero la fila destino en `datasets` con `id`; insertar después la fila origen en `run_datasets` con `dataset_id` exactamente coincidentes. Esperado: INSERT aceptado. |
| FK-042 | `N-FK-042` | Insertar la fila origen en `run_datasets` con un valor `dataset_id` que no exista en `datasets.id`. Esperado: violación FK (SQLSTATE 23503). |
| FK-043 | `P-FK-043` | Crear primero la fila destino en `datasets` con `id`; insertar después la fila origen en `dataset_sources` con `dataset_id` exactamente coincidentes. Esperado: INSERT aceptado. |
| FK-043 | `N-FK-043` | Insertar la fila origen en `dataset_sources` con un valor `dataset_id` que no exista en `datasets.id`. Esperado: violación FK (SQLSTATE 23503). |
| FK-044 | `P-FK-044` | Crear primero la fila destino en `data_sources` con `id`; insertar después la fila origen en `dataset_sources` con `data_source_id` exactamente coincidentes. Esperado: INSERT aceptado. |
| FK-044 | `N-FK-044` | Insertar la fila origen en `dataset_sources` con un valor `data_source_id` que no exista en `data_sources.id`. Esperado: violación FK (SQLSTATE 23503). |
| FK-045 | `P-FK-045` | Crear primero la fila destino en `data_endpoints` con `id, data_source_id`; insertar después la fila origen en `dataset_sources` con `data_endpoint_id, data_source_id` exactamente coincidentes. Esperado: INSERT aceptado. |
| FK-045 | `N-FK-045` | Conservar una fila destino válida, mantener todos los componentes de la FK NOT NULL, y alterar un componente no nulo de `data_endpoint_id, data_source_id` para que no coincida con la tupla `id, data_source_id`. Esperado: violación FK (SQLSTATE 23503). Mantener todos los componentes no nulos; con MATCH SIMPLE, un NULL podría omitir la comprobación compuesta. |
| FK-046 | `P-FK-046` | Probar market_instrument_id NULL y, por separado, un instrumento existente de la misma fuente. Esperado: ambas formas aceptadas. |
| FK-046 | `N-FK-046` | Con instrumento informado, usar un instrumento de otra fuente. Esperado: violación FK 23503. |
| FK-047 | `P-FK-047` | Probar ingestion_request_id NULL con fuente/endpoint válidos; después probar request existente con la misma fuente y endpoint. Esperado: ambas formas aceptadas. |
| FK-047 | `N-FK-047` | Con request informado, usar request de otra fuente o endpoint. Esperado: violación FK 23503. |
| FK-048 | `P-FK-048` | Crear primero la fila destino en `policy_evaluations` con `id, data_source_id, data_endpoint_id, data_type, intended_use`; insertar después la fila origen en `dataset_sources` con `policy_evaluation_id, data_source_id, data_endpoint_id, data_type, evaluated_intended_use` exactamente coincidentes. Esperado: INSERT aceptado. |
| FK-048 | `N-FK-048` | Conservar una fila destino válida, mantener todos los componentes de la FK NOT NULL, y alterar un componente no nulo de `policy_evaluation_id, data_source_id, data_endpoint_id, data_type, evaluated_intended_use` para que no coincida con la tupla `id, data_source_id, data_endpoint_id, data_type, intended_use`. Esperado: violación FK (SQLSTATE 23503). Mantener todos los componentes no nulos; con MATCH SIMPLE, un NULL podría omitir la comprobación compuesta. |
| FK-049 | `P-FK-049` | Crear primero la fila destino en `datasets` con `id`; insertar después la fila origen en `dataset_lineage` con `input_dataset_id` exactamente coincidentes. Esperado: INSERT aceptado. |
| FK-049 | `N-FK-049` | Insertar la fila origen en `dataset_lineage` con un valor `input_dataset_id` que no exista en `datasets.id`. Esperado: violación FK (SQLSTATE 23503). |
| FK-050 | `P-FK-050` | Crear primero la fila destino en `datasets` con `id`; insertar después la fila origen en `dataset_lineage` con `output_dataset_id` exactamente coincidentes. Esperado: INSERT aceptado. |
| FK-050 | `N-FK-050` | Insertar la fila origen en `dataset_lineage` con un valor `output_dataset_id` que no exista en `datasets.id`. Esperado: violación FK (SQLSTATE 23503). |
| FK-051 | `P-FK-051` | Crear primero la fila destino en `transformation_runs` con `id`; insertar después la fila origen en `dataset_lineage` con `transformation_run_id` exactamente coincidentes. Esperado: INSERT aceptado. |
| FK-051 | `N-FK-051` | Insertar la fila origen en `dataset_lineage` con un valor `transformation_run_id` que no exista en `transformation_runs.id`. Esperado: violación FK (SQLSTATE 23503). |
| FK-052 | `P-FK-052` | Crear primero la fila destino en `datasets` con `id`; insertar después la fila origen en `data_validations` con `dataset_id` exactamente coincidentes. Esperado: INSERT aceptado. |
| FK-052 | `N-FK-052` | Insertar la fila origen en `data_validations` con un valor `dataset_id` que no exista en `datasets.id`. Esperado: violación FK (SQLSTATE 23503). |
| FK-053 | `P-FK-053` | Probar FK nullable con NULL y con un run existente. Esperado: ambas formas aceptadas. |
| FK-053 | `N-FK-053` | Proporcionar un run_id no existente. Esperado: violación FK 23503. |
| FK-054 | `P-FK-054` | Crear primero la fila destino en `transformations` con `id`; insertar después la fila origen en `transformation_runs` con `transformation_id` exactamente coincidentes. Esperado: INSERT aceptado. |
| FK-054 | `N-FK-054` | Insertar la fila origen en `transformation_runs` con un valor `transformation_id` que no exista en `transformations.id`. Esperado: violación FK (SQLSTATE 23503). |
| FK-055 | `P-FK-055` | Probar FK nullable con NULL y con un run existente. Esperado: ambas formas aceptadas. |
| FK-055 | `N-FK-055` | Proporcionar un run_id no existente. Esperado: violación FK 23503. |
| FK-056 | `P-FK-056` | Crear primero la fila destino en `research_experiments` con `id`; insertar después la fila origen en `research_experiment_runs` con `experiment_id` exactamente coincidentes. Esperado: INSERT aceptado. |
| FK-056 | `N-FK-056` | Insertar la fila origen en `research_experiment_runs` con un valor `experiment_id` que no exista en `research_experiments.id`. Esperado: violación FK (SQLSTATE 23503). |
| FK-057 | `P-FK-057` | Crear primero la fila destino en `research_experiment_runs` con `id`; insertar después la fila origen en `research_run_artifacts` con `run_id` exactamente coincidentes. Esperado: INSERT aceptado. |
| FK-057 | `N-FK-057` | Insertar la fila origen en `research_run_artifacts` con un valor `run_id` que no exista en `research_experiment_runs.id`. Esperado: violación FK (SQLSTATE 23503). |
| FK-058 | `P-FK-058` | Crear primero la fila destino en `research_experiments` con `id`; insertar después la fila origen en `research_hypotheses` con `experiment_id` exactamente coincidentes. Esperado: INSERT aceptado. |
| FK-058 | `N-FK-058` | Insertar la fila origen en `research_hypotheses` con un valor `experiment_id` que no exista en `research_experiments.id`. Esperado: violación FK (SQLSTATE 23503). |
| FK-059 | `P-FK-059` | Crear primero la fila destino en `research_experiments` con `id`; insertar después la fila origen en `experiment_datasets` con `experiment_id` exactamente coincidentes. Esperado: INSERT aceptado. |
| FK-059 | `N-FK-059` | Insertar la fila origen en `experiment_datasets` con un valor `experiment_id` que no exista en `research_experiments.id`. Esperado: violación FK (SQLSTATE 23503). |
| FK-060 | `P-FK-060` | Crear primero la fila destino en `datasets` con `id`; insertar después la fila origen en `experiment_datasets` con `dataset_id` exactamente coincidentes. Esperado: INSERT aceptado. |
| FK-060 | `N-FK-060` | Insertar la fila origen en `experiment_datasets` con un valor `dataset_id` que no exista en `datasets.id`. Esperado: violación FK (SQLSTATE 23503). |

## 2. Pruebas transversales adicionales obligatorias

Las pruebas por FK no sustituyen los siguientes casos de integridad:

1. **MATCH y NULL:** probar todas las combinaciones de NULL para FK-003, FK-008/009, FK-013/015, FK-021/026, FK-031/032, FK-040/046/047 y FK-053/055. Confirmar que solo se admiten combinaciones expresamente documentadas.
2. **Claves compuestas:** para UK-01…UK-12, comprobar que la clave UNIQUE destino existe, está ordenada correctamente y es referenciable; probar duplicados y tuplas con un solo componente distinto.
3. **Identidad de proveedor:** probar que plataforma, fuente, observación, revisión y red coinciden exactamente; no aceptar mapping a revisión pending/rejected/ambiguous.
4. **Cadenas append-only:** probar raíz única, sucesora única, sucesora de la cabeza, rechazo de bifurcación, autorreferencia y ciclo; probar dos sesiones concurrentes.
5. **Mappings de activos:** probar destino accepted exacto, ámbito global vs red, igualdad NULL-safe, publicación atómica revisión + mapping y rollback si falla la segunda inserción.
6. **Procedencia:** probar endpoint/instrumento/request/evaluación de la misma fuente; dataset_sources no puede mezclar fuente, endpoint, tipo de dato ni uso previsto.
7. **Linaje:** probar aristas válidas, rechazo input=output y prevención concurrente de ciclos de dataset_lineage.
8. **Borrado/actualización:** probar RESTRICT en padres históricos y verificar que no se permite borrar ni modificar evidencia inmutable.
9. **Diferibilidad:** cuando se apruebe el atributo DEFERRABLE, probar el comportamiento dentro de una transacción y tras SET CONSTRAINTS.
10. **Reinstalación:** ejecutar desde base vacía, dos veces en entornos aislados, y comparar catálogo de constraints/índices con el manifiesto esperado.

## 3. Evidencia que debe conservar cada ejecución

Para cada test:
- ID estable de test y FK/constraint cubierto.
- versión/commit de migraciones y hash del esquema;
- versión exacta de PostgreSQL;
- SQL de fixture y resultado;
- SQLSTATE y nombre de constraint cuando falle;
- estado de transacción y evidencia de rollback;
- fecha UTC y resultado reproducible.

No se aceptará un test Python que simule la FK como sustituto de la ejecución contra PostgreSQL. Las pruebas de contrato de aplicación y las pruebas del motor se reportarán por separado.

## 4. Gate de aceptación

El gate se cierra solo cuando los 120 casos planificados estén implementados y ejecutados en PostgreSQL 16 global `cci`, además de las pruebas transversales de concurrencia, rollback, triggers, claves candidatas y reinstalación. El laboratorio `cci_lab` y sus 29/29 pruebas no sustituyen esta suite.


## 5.1 Reglas de construcción para casos negativos compuestos

La suite no debe generar una falsa aceptación por semántica NULL. Para toda FK compuesta que use MATCH SIMPLE (o cuyo MATCH aún no esté ratificado):

- el caso negativo de referencia inexistente debe asignar valores NOT NULL a **todos** los componentes;
- se conserva una fila destino válida y se altera exactamente un componente de la tupla origen;
- los escenarios con NULL se prueban aparte como casos de nulabilidad/MATCH, nunca como sustitutos de la prueba negativa de integridad;
- el test debe verificar constraint name y SQLSTATE 23503, y confirmar rollback de la sentencia/transacción según el harness.

Para FK compuestas con un componente nullable (FK-003, FK-008/009, FK-013/015, FK-047), se deben incluir explícitamente los estados nativo/opcional válidos y los estados parciales inválidos definidos por CHECK/trigger. Un NULL no puede ser el valor “alterado” de la prueba de referencia inexistente, porque podría desactivar la FK.
