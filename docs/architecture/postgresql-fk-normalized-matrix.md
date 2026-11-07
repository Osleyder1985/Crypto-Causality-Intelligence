# Matriz normalizada de claves foráneas — Issue #25

- Fuente normativa: `docs/architecture/postgresql-physical-schema.md`, contrato v0.8.
- Cobertura de inventario: 34/34 tablas.
- Estado: **60/60 relaciones FK de la matriz implementadas en migraciones globales 002–009 y ejecutadas en PostgreSQL 16; falta reconciliación final automatizada de catálogo y permisos**.
- Regla de seguridad: no se inventan columnas. Las decisiones no expresadas en v0.8 se marcan como pendientes.
- Convención de nombres: los nombres `fk_<tabla>__<destino>__<rol>` son identificadores propuestos, no nombres ya implementados.

## 1. Convenciones que deben ratificarse

La especificación física establece como convención general `ON DELETE RESTRICT ON UPDATE RESTRICT` para FKs históricas y prefiere RESTRICT también en tablas asociativas. Esta matriz lo registra como **acción propuesta por convención**, no como DDL ya ejecutado.

La especificación no fija individualmente `MATCH`, `DEFERRABLE` ni `INITIALLY DEFERRED` para la mayoría de las FKs. La sección 13 sí fija nombres y acciones concretas para el subsistema de plataformas de proveedor; esos casos se reflejan en §8. Para no ocultar las ausencias restantes:
- `MATCH SIMPLE`: comportamiento PostgreSQL por defecto propuesto; requiere ratificación, especialmente en FKs compuestas opcionales.
- `NOT DEFERRABLE`: comportamiento PostgreSQL por defecto propuesto; requiere ratificación.
- `INITIALLY IMMEDIATE`: comportamiento por defecto si la FK no es diferible; requiere ratificación.
- Acciones referenciales propuestas: `RESTRICT / RESTRICT`, según la convención general del contrato.

No se debe interpretar estos defaults como decisiones de dominio aprobadas. Antes de generar SQL se debe resolver cada pendiente y comprobar las claves candidatas de destino.

## 2. Registro normalizado de relaciones documentadas

En la columna de nulabilidad, `NN` significa que todos los componentes de la FK están declarados NOT NULL; `OPT` significa que al menos un componente admite NULL. Bajo MATCH SIMPLE, si cualquier componente de una FK compuesta es NULL, PostgreSQL no exige una fila referenciada. Si el dominio exige “todos NULL o todos completos”, debe añadirse CHECK explícito; no asumir que MATCH SIMPLE lo garantiza.

| ID | Tabla origen | Columnas origen (orden) | Tabla destino | Columnas destino (orden) | Nulabilidad | Semántica / comprobación pendiente |
|---|---|---|---|---|---|---|
| FK-001 | data_endpoints | data_source_id | data_sources | id | NN | FK simple. |
| FK-002 | source_usage_policies | data_source_id | data_sources | id | NN | FK simple. |
| FK-003 | source_usage_policies | data_endpoint_id, data_source_id | data_endpoints | id, data_source_id | OPT | Endpoint opcional; con MATCH SIMPLE, NULL en data_endpoint_id omite la comprobación compuesta. Confirmar CHECK de alcance/policy_scope. |
| FK-004 | policy_evaluations | source_usage_policy_id, data_source_id | source_usage_policies | id, data_source_id | NN | Exige misma fuente que la política. |
| FK-005 | policy_evaluations | data_source_id | data_sources | id | NN | FK simple redundante de trazabilidad; confirmar necesidad frente a FK-004. |
| FK-006 | policy_evaluations | data_endpoint_id, data_source_id | data_endpoints | id, data_source_id | NN | Exige endpoint de la misma fuente. |
| FK-007 | network_identifiers | network_id | networks | id | NN | FK simple. |
| FK-008 | network_identifiers | provider_platform_id, provider_data_source_id | provider_platforms | id, data_source_id | OPT | Campos de procedencia deben ser ambos NULL o completos; falta CHECK explícito en extracto. |
| FK-009 | network_identifiers | provider_platform_resolution_review_id, provider_platform_id, network_id, provider_platform_resolution_status | provider_platform_resolution_reviews | id, provider_platform_id, candidate_network_id, resolution_status | OPT | `network_id` es siempre NOT NULL, por lo que MATCH SIMPLE es necesario para permitir identificadores nativos. El grupo de procedencia separado (provider_platform_id, provider_data_source_id, provider_platform_resolution_review_id, provider_platform_resolution_status) debe ser todo NULL o todo NOT NULL; CHECK explícito en §13.2. |
| FK-010 | provider_platforms | data_source_id | data_sources | id | NN | Identidad de plataforma dentro de una fuente. |
| FK-011 | provider_platform_observations | provider_platform_id, data_source_id | provider_platforms | id, data_source_id | NN | Exige coherencia de fuente/plataforma. |
| FK-012 | provider_platform_resolution_reviews | provider_platform_id, data_source_id | provider_platforms | id, data_source_id | NN | Exige coherencia de fuente/plataforma. |
| FK-013 | provider_platform_resolution_reviews | based_on_observation_id, provider_platform_id, data_source_id | provider_platform_observations | id, provider_platform_id, data_source_id | OPT | Observación de soporte opcional; coincidencia de plataforma y fuente. |
| FK-014 | provider_platform_resolution_reviews | candidate_network_id | networks | id | OPT | Candidato de red nullable para estados no accepted. |
| FK-015 | provider_platform_resolution_reviews | supersedes_review_id, provider_platform_id | provider_platform_resolution_reviews | id, provider_platform_id | OPT | Autorreferencia; exige misma plataforma. Índices parciales y trigger deben impedir ramas/ciclos. |
| FK-016 | asset_representations | asset_id | assets | id | NN | FK simple. |
| FK-017 | asset_representations | network_id | networks | id | NN | FK simple. |
| FK-018 | asset_relationships | subject_asset_id | assets | id | NN | Primer extremo de relación dirigida. |
| FK-019 | asset_relationships | object_asset_id | assets | id | NN | Segundo extremo; CHECK prohíbe igualdad con subject_asset_id. |
| FK-020 | asset_identity_resolution_reviews | namespace | identity_namespaces | namespace_key | NN | Namespace debe existir; trigger debe validar scope_mode y target_level. |
| FK-021 | asset_identity_resolution_reviews | network_id | networks | id | OPT | NULL representa scope global según namespace; validar contra identity_namespaces.scope_mode. |
| FK-022 | asset_identity_resolution_reviews | candidate_asset_id | assets | id | OPT | Candidato a nivel de activo. |
| FK-023 | asset_identity_resolution_reviews | candidate_asset_representation_id | asset_representations | id | OPT | Candidato a nivel de representación. |
| FK-024 | asset_identity_resolution_reviews | supersedes_review_id | asset_identity_resolution_reviews | id | OPT | Autorreferencia; misma clave de identidad, cadena lineal y sin ciclos requieren trigger/función. |
| FK-025 | asset_identifiers | asset_id | assets | id | NN | Mapping aceptado a nivel de activo. |
| FK-026 | asset_identifiers | network_id | networks | id | OPT | Ámbito nullable; igualdad NULL-safe con revisión no se obtiene con FK simple. |
| FK-027 | asset_identifiers | resolution_review_id, asset_id, resolution_status, namespace, external_identifier | asset_identity_resolution_reviews | id, candidate_asset_id, resolution_status, namespace, external_identifier | NN | FK compuesta a revisión accepted exacta; además trigger compara network_id NULL-safe. |
| FK-028 | asset_representation_identifiers | asset_representation_id, network_id | asset_representations | id, network_id | NN | Requiere UNIQUE candidato en asset_representations(id, network_id). |
| FK-029 | asset_representation_identifiers | resolution_review_id, asset_representation_id, resolution_status, namespace, external_identifier, network_id | asset_identity_resolution_reviews | id, candidate_asset_representation_id, resolution_status, namespace, external_identifier, network_id | NN | FK compuesta a revisión accepted exacta. |
| FK-030 | market_instruments | data_source_id | data_sources | id | NN | Instrumento específico de fuente/mercado. |
| FK-031 | market_instruments | base_asset_id | assets | id | OPT | Nullable; base_asset_id y quote_asset_id deben ser ambos NULL o ambos completos mediante CHECK. |
| FK-032 | market_instruments | quote_asset_id | assets | id | OPT | Nullable; debe ser distinto de base_asset_id cuando ambos existen. |
| FK-033 | instrument_identifiers | market_instrument_id | market_instruments | id | NN | Alias nativo del instrumento. |
| FK-034 | instrument_metadata_versions | market_instrument_id | market_instruments | id | NN | Observaciones históricas por instrumento. |
| FK-035 | instrument_metadata_versions | source_dataset_id | datasets | id | OPT | Dataset de origen opcional; confirmar política de retención/autoridad del artefacto. |
| FK-036 | instrument_trading_rules | metadata_version_id | instrument_metadata_versions | id | NN | Reglas ligadas a una versión concreta. |
| FK-037 | ingestion_requests | ingestion_run_id | ingestion_runs | id | NN | Solicitud dentro de una ejecución lógica. |
| FK-038 | ingestion_requests | data_source_id | data_sources | id | NN | Fuente declarada; además se valida endpoint/instrumento por FKs compuestas. |
| FK-039 | ingestion_requests | data_endpoint_id, data_source_id | data_endpoints | id, data_source_id | NN | Impide endpoint de otra fuente. |
| FK-040 | ingestion_requests | market_instrument_id, data_source_id | market_instruments | id, data_source_id | OPT | Si market_instrument_id es NULL, MATCH SIMPLE omite la FK compuesta; data_source_id sigue siendo obligatorio. |
| FK-041 | run_datasets | ingestion_run_id | ingestion_runs | id | NN | Asociación Run–dataset. |
| FK-042 | run_datasets | dataset_id | datasets | id | NN | Asociación Run–dataset. |
| FK-043 | dataset_sources | dataset_id | datasets | id | NN | Procedencia de un dataset. |
| FK-044 | dataset_sources | data_source_id | data_sources | id | NN | Fuente de la contribución. |
| FK-045 | dataset_sources | data_endpoint_id, data_source_id | data_endpoints | id, data_source_id | NN | Endpoint de la misma fuente. |
| FK-046 | dataset_sources | market_instrument_id, data_source_id | market_instruments | id, data_source_id | OPT | Instrumento opcional; si existe debe pertenecer a la fuente. |
| FK-047 | dataset_sources | ingestion_request_id, data_source_id, data_endpoint_id | ingestion_requests | id, data_source_id, data_endpoint_id | OPT | Solo ingestion_request_id es nullable; data_source_id y data_endpoint_id son NOT NULL. MATCH SIMPLE omite la referencia si no hay request. La prosa de v0.8 dice que los tres pueden ser NULL sin que las definiciones de columnas lo permitan: contradicción bloqueante que debe resolverse. |
| FK-048 | dataset_sources | policy_evaluation_id, data_source_id, data_endpoint_id, data_type, evaluated_intended_use | policy_evaluations | id, data_source_id, data_endpoint_id, data_type, intended_use | NN | Exige coincidencia exacta de fuente, endpoint, tipo y uso; requiere UNIQUE candidato en destino. |
| FK-049 | dataset_lineage | input_dataset_id | datasets | id | NN | Dataset de entrada. |
| FK-050 | dataset_lineage | output_dataset_id | datasets | id | NN | Dataset de salida; CHECK prohíbe input=output; ciclos requieren lógica transaccional. |
| FK-051 | dataset_lineage | transformation_run_id | transformation_runs | id | NN | Arista asociada a ejecución concreta. |
| FK-052 | data_validations | dataset_id | datasets | id | NN | Resultado sobre dataset. |
| FK-053 | data_validations | ingestion_run_id | ingestion_runs | id | OPT | Run de ingesta opcional. |
| FK-054 | transformation_runs | transformation_id | transformations | id | NN | Definición versionada ejecutada. |
| FK-055 | transformation_runs | ingestion_run_id | ingestion_runs | id | OPT | Run de ingesta asociado opcionalmente. |
| FK-056 | research_experiment_runs | experiment_id | research_experiments | id | NN | Run individual de un experimento. |
| FK-057 | research_run_artifacts | run_id | research_experiment_runs | id | NN | Referencia a artefacto externo del run. |
| FK-058 | research_hypotheses | experiment_id | research_experiments | id | NN | Hipótesis perteneciente al experimento. |
| FK-059 | experiment_datasets | experiment_id | research_experiments | id | NN | Asociación experimento–dataset. |
| FK-060 | experiment_datasets | dataset_id | datasets | id | NN | Asociación experimento–dataset. |

## 3. Cobertura de las 34 tablas

| Tabla | FKs salientes documentadas | Estado de extracción |
|---|---:|---|
| data_sources | 0 | Sin FK saliente descrita. |
| data_endpoints | 1 | Normalizada FK-001. |
| source_usage_policies | 2 | Normalizadas FK-002–003. |
| policy_evaluations | 3 | Normalizadas FK-004–006. |
| assets | 0 | Sin FK saliente descrita. |
| identity_namespaces | 0 | PK referenciada por FK-020. |
| networks | 0 | PK referenciada por otras tablas. |
| network_identifiers | 3 | Normalizadas FK-007–009. |
| provider_platforms | 1 | Normalizada FK-010. |
| provider_platform_observations | 1 | Normalizada FK-011. |
| provider_platform_resolution_reviews | 4 | Normalizadas FK-012–015. |
| asset_representations | 2 | Normalizadas FK-016–017. |
| asset_relationships | 2 | Normalizadas FK-018–019. |
| asset_identity_resolution_reviews | 5 | Normalizadas FK-020–024. |
| asset_identifiers | 3 | Normalizadas FK-025–027. |
| asset_representation_identifiers | 2 | Normalizadas FK-028–029. |
| market_instruments | 3 | Normalizadas FK-030–032. |
| instrument_identifiers | 1 | Normalizada FK-033. |
| instrument_metadata_versions | 2 | Normalizadas FK-034–035. |
| instrument_trading_rules | 1 | Normalizada FK-036. |
| ingestion_runs | 0 | PK referenciada por tablas operativas. |
| ingestion_requests | 4 | Normalizadas FK-037–040. |
| datasets | 0 | PK referenciada por tablas de datasets/linaje. |
| run_datasets | 2 | Normalizadas FK-041–042. |
| dataset_sources | 6 | Normalizadas FK-043–048. |
| dataset_lineage | 3 | Normalizadas FK-049–051. |
| data_validations | 2 | Normalizadas FK-052–053. |
| transformations | 0 | PK referenciada por transformation_runs. |
| transformation_runs | 2 | Normalizadas FK-054–055. |
| research_experiments | 0 | PK referenciada por runs/hipótesis/asociaciones. |
| research_hypotheses | 1 | Normalizada FK-058. |
| experiment_datasets | 2 | Normalizadas FK-059–060. |
| research_experiment_runs | 1 | Normalizada FK-056. |
| research_run_artifacts | 1 | Normalizada FK-057. |

**Nota de conteo:** el inventario físico vigente contiene 34 tablas. La tabla anterior enumera 34 nombres; la cobertura se validará automáticamente contra el inventario antes de aprobar la matriz. Los 60 registros incluyen relaciones simples, compuestas y autorreferencias expresamente descritas en el contrato v0.8.

## 4. Claves candidatas destino que deben existir

Además de las PK primarias, el DDL debe declarar UNIQUE compatibles para las referencias compuestas siguientes:

| Tabla destino | Columnas que deben tener PK/UNIQUE compatible | Referencias |
|---|---|---|
| data_endpoints | (id, data_source_id) | FK-003, 039, 045 |
| source_usage_policies | (id, data_source_id) | FK-004 |
| policy_evaluations | (id, data_source_id, data_endpoint_id, data_type, intended_use) | FK-048 |
| provider_platforms | (id, data_source_id) | FK-008, 011–012 |
| provider_platform_observations | (id, provider_platform_id, data_source_id) | FK-013 |
| provider_platform_resolution_reviews | (id, provider_platform_id, candidate_network_id, resolution_status) | FK-009 |
| provider_platform_resolution_reviews | (id, provider_platform_id) | FK-015 |
| asset_representations | (id, network_id) | FK-028 |
| asset_identity_resolution_reviews | (id, candidate_asset_id, resolution_status, namespace, external_identifier) | FK-027 |
| asset_identity_resolution_reviews | (id, candidate_asset_representation_id, resolution_status, namespace, external_identifier, network_id) | FK-029 |
| market_instruments | (id, data_source_id) | FK-040, 046 |
| ingestion_requests | (id, data_source_id, data_endpoint_id) | FK-047 |

La especificación usa la expresión “UNIQUE candidato” en varios de estos puntos. No se considerará resuelto hasta comprobar que la restricción aparece realmente en el DDL final y que las columnas y tipos coinciden en orden.

## 5. Pendientes bloqueantes antes de DDL

1. **Recuento y cobertura:** validar automáticamente los 34 nombres contra el inventario físico; confirmar que la tabla de cobertura no contiene duplicados ni omisiones.
2. **Claves destino:** comprobar PK/UNIQUE real para cada referencia compuesta, especialmente las marcadas como candidatas.
3. **Nulabilidad:** el grupo de procedencia de FK-008/009 está definido por CHECK en §13.2. FK-047 quedó resuelta en la especificación física: solo ingestion_request_id es nullable; fuente y endpoint siguen NOT NULL. FK-040 y FK-046 tienen solo el ID de instrumento nullable, por lo que MATCH SIMPLE omite la referencia cuando ese ID es NULL.
4. **MATCH:** ratificar SIMPLE o FULL por relación. MATCH FULL puede ser apropiado para FK-008/009 si todos sus componentes son nullable; no es aplicable a FK-047 mientras data_source_id y data_endpoint_id permanezcan NOT NULL.
5. **Claves candidatas:** el auto-referenciado FK-024 usa la PK (id) y no necesita una UNIQUE compuesta adicional; la consistencia de la misma clave de identidad debe imponerse mediante trigger/función.
6. **Acciones:** confirmar RESTRICT/RESTRICT por relación, sin asumir CASCADE en asociaciones.
7. **Diferibilidad:** confirmar NOT DEFERRABLE/INITIALLY IMMEDIATE o justificar diferibilidad para inserciones cíclicas/operaciones atómicas.
8. **Triggers/funciones:** especificar y probar igualdad NULL-safe de scope, cadenas append-only, no ciclos de sustitución y publicación atómica de mappings; una FK no implementa esas invariantes.
9. **Grafo:** cálculo provisional completado en §7: 34/34 tablas ordenables, dos autorreferencias y cero ciclos entre tablas distintas. Recalcular cuando cambie una relación o se cierre una decisión pendiente.
10. **Tests:** asignar IDs de pruebas positivas/negativas a cada FK y ejecutar contra PostgreSQL 16 desde base vacía.

## 6. Dictamen

Se han convertido las relaciones descritas explícitamente en v0.8 en registros tabulares, incluidas las FKs compuestas de consistencia de fuente, las revisiones de identidad y el subsistema de plataformas de proveedor. Esto es un avance de normalización documental, **no una aprobación de las 60 relaciones ni una prueba del motor**. Las acciones, MATCH, diferibilidad, claves candidatas y semánticas NULL que no están completamente especificadas permanecen como gates.

No generar aún migraciones integrales a partir de esta matriz. El siguiente paso es una auditoría cruzada de cada clave candidata y de los grupos NULL; después se ratificará el orden provisional de §7 y se asignarán pruebas por restricción.


## 7. Grafo de dependencias y orden topológico provisional

Se calculó el grafo dirigido desde las 60 filas FK-001…FK-060, orientando cada arista desde la tabla destino (prerrequisito) hacia la tabla origen (dependiente). Resultado mecánico sobre la matriz actual:

- Tablas incluidas: **34/34**.
- Relaciones documentadas: **60**.
- Componentes de autorreferencia: **2** (`provider_platform_resolution_reviews` y `asset_identity_resolution_reviews`).
- Ciclos entre tablas distintas: **0 detectados** en este grafo.
- Orden topológico resultante: **34/34 tablas**.

Orden provisional de creación de tablas (las referencias a una misma tabla y las claves candidatas deben materializarse conforme a la revisión de constraints):

1. `assets`
2. `data_sources`
3. `identity_namespaces`
4. `ingestion_runs`
5. `transformations`
6. `research_experiments`
7. `networks`
8. `datasets`
9. `data_endpoints`
10. `asset_relationships`
11. `data_validations`
12. `market_instruments`
13. `provider_platforms`
14. `source_usage_policies`
15. `asset_representations`
16. `instrument_identifiers`
17. `instrument_metadata_versions`
18. `provider_platform_observations`
19. `provider_platform_resolution_reviews`
20. `asset_identity_resolution_reviews`
21. `network_identifiers`
22. `asset_identifiers`
23. `asset_representation_identifiers`
24. `instrument_trading_rules`
25. `policy_evaluations`
26. `ingestion_requests`
27. `run_datasets`
28. `transformation_runs`
29. `research_experiment_runs`
30. `research_hypotheses`
31. `research_run_artifacts`
32. `experiment_datasets`
33. `dataset_sources`
34. `dataset_lineage`

**Interpretación limitada:** este orden resuelve dependencias de tablas expresadas en la matriz, no demuestra que las claves candidatas existan ni que el DDL compile. Las dos autorreferencias pueden declararse al crear su propia tabla o añadirse como ALTER TABLE posterior; se recomienda añadirlas después de crear PK/UNIQUE y probar cadena, ciclo y concurrencia. El orden de creación de tablas no sustituye el orden de creación de índices, triggers y funciones.

Antes de convertirlo en plan de migraciones: ratificar las 60 relaciones, verificar todas las claves destino y cerrar MATCH/acciones/diferibilidad/semántica NULL. Una relación ausente o una clave compuesta mal definida cambiaría el grafo.


## 8. Atributos de constraint y catálogo de pruebas por FK

Este overlay completa los atributos de implementación que no estaban especificados fila por fila. Los valores marcados como provisionales heredan las convenciones generales del contrato, no una aprobación definitiva. `P-FK-xxx` y `N-FK-xxx` son IDs propuestos para pruebas positiva y negativa; no representan pruebas existentes ni ejecutadas.

| ID | constraint_name propuesto | match_type | on_update | on_delete | deferrable | initially_deferred | test_ids propuestos |
|---|---|---|---|---|---|---|---|
| FK-001 | `fk_001_data_endpoints_data_sources` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-001`, `N-FK-001` (propuestos; no ejecutados) |
| FK-002 | `fk_002_source_usage_policies_data_sources` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-002`, `N-FK-002` (propuestos; no ejecutados) |
| FK-003 | `fk_003_source_usage_policies_data_endpoints` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-003`, `N-FK-003` (propuestos; no ejecutados) |
| FK-004 | `fk_004_policy_evaluations_source_usage_policies` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-004`, `N-FK-004` (propuestos; no ejecutados) |
| FK-005 | `fk_005_policy_evaluations_data_sources` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-005`, `N-FK-005` (propuestos; no ejecutados) |
| FK-006 | `fk_006_policy_evaluations_data_endpoints` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-006`, `N-FK-006` (propuestos; no ejecutados) |
| FK-007 | `fk_007_network_identifiers_networks` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-007`, `N-FK-007` (propuestos; no ejecutados) |
| FK-008 | `fk_008_network_identifiers_provider_platforms` | SIMPLE (con CHECK de grupo) | RESTRICT | RESTRICT | NO (provisional) | NO (provisional) | `P-FK-008`, `N-FK-008` (propuestos; no ejecutados) |
| FK-009 | `fk_009_network_identifiers_provider_platform_resolution_reviews` | SIMPLE (necesario: network_id siempre NN) | RESTRICT | RESTRICT | NO (provisional) | NO (provisional) | `P-FK-009`, `N-FK-009` (propuestos; no ejecutados) |
| FK-010 | `fk_010_provider_platforms_data_sources` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-010`, `N-FK-010` (propuestos; no ejecutados) |
| FK-011 | `provider_platform_observations_fk_platform_source` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-011`, `N-FK-011` (propuestos; no ejecutados) |
| FK-012 | `provider_platform_resolution_reviews_fk_platform_source` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-012`, `N-FK-012` (propuestos; no ejecutados) |
| FK-013 | `provider_platform_resolution_reviews_fk_observation` | SIMPLE (explícito en §13.2) | RESTRICT | RESTRICT | NO (provisional) | NO (provisional) | `P-FK-013`, `N-FK-013` (propuestos; no ejecutados) |
| FK-014 | `fk_014_provider_platform_resolution_reviews_networks` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-014`, `N-FK-014` (propuestos; no ejecutados) |
| FK-015 | `provider_platform_resolution_reviews_fk_successor_chain` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-015`, `N-FK-015` (propuestos; no ejecutados) |
| FK-016 | `fk_016_asset_representations_assets` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-016`, `N-FK-016` (propuestos; no ejecutados) |
| FK-017 | `fk_017_asset_representations_networks` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-017`, `N-FK-017` (propuestos; no ejecutados) |
| FK-018 | `fk_018_asset_relationships_assets` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-018`, `N-FK-018` (propuestos; no ejecutados) |
| FK-019 | `fk_019_asset_relationships_assets` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-019`, `N-FK-019` (propuestos; no ejecutados) |
| FK-020 | `fk_020_asset_identity_resolution_reviews_identity_namespaces` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-020`, `N-FK-020` (propuestos; no ejecutados) |
| FK-021 | `fk_021_asset_identity_resolution_reviews_networks` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-021`, `N-FK-021` (propuestos; no ejecutados) |
| FK-022 | `fk_022_asset_identity_resolution_reviews_assets` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-022`, `N-FK-022` (propuestos; no ejecutados) |
| FK-023 | `fk_023_asset_identity_resolution_reviews_asset_representations` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-023`, `N-FK-023` (propuestos; no ejecutados) |
| FK-024 | `fk_024_asset_identity_resolution_reviews_asset_identity_resolution_reviews` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-024`, `N-FK-024` (propuestos; no ejecutados) |
| FK-025 | `fk_025_asset_identifiers_assets` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-025`, `N-FK-025` (propuestos; no ejecutados) |
| FK-026 | `fk_026_asset_identifiers_networks` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-026`, `N-FK-026` (propuestos; no ejecutados) |
| FK-027 | `fk_027_asset_identifiers_asset_identity_resolution_reviews` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-027`, `N-FK-027` (propuestos; no ejecutados) |
| FK-028 | `fk_028_asset_representation_identifiers_asset_representations` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-028`, `N-FK-028` (propuestos; no ejecutados) |
| FK-029 | `fk_029_asset_representation_identifiers_asset_identity_resolution_reviews` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-029`, `N-FK-029` (propuestos; no ejecutados) |
| FK-030 | `fk_030_market_instruments_data_sources` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-030`, `N-FK-030` (propuestos; no ejecutados) |
| FK-031 | `fk_031_market_instruments_assets` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-031`, `N-FK-031` (propuestos; no ejecutados) |
| FK-032 | `fk_032_market_instruments_assets` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-032`, `N-FK-032` (propuestos; no ejecutados) |
| FK-033 | `fk_033_instrument_identifiers_market_instruments` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-033`, `N-FK-033` (propuestos; no ejecutados) |
| FK-034 | `fk_034_instrument_metadata_versions_market_instruments` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-034`, `N-FK-034` (propuestos; no ejecutados) |
| FK-035 | `fk_035_instrument_metadata_versions_datasets` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-035`, `N-FK-035` (propuestos; no ejecutados) |
| FK-036 | `fk_036_instrument_trading_rules_instrument_metadata_versions` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-036`, `N-FK-036` (propuestos; no ejecutados) |
| FK-037 | `fk_037_ingestion_requests_ingestion_runs` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-037`, `N-FK-037` (propuestos; no ejecutados) |
| FK-038 | `fk_038_ingestion_requests_data_sources` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-038`, `N-FK-038` (propuestos; no ejecutados) |
| FK-039 | `fk_039_ingestion_requests_data_endpoints` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-039`, `N-FK-039` (propuestos; no ejecutados) |
| FK-040 | `fk_040_ingestion_requests_market_instruments` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-040`, `N-FK-040` (propuestos; no ejecutados) |
| FK-041 | `fk_041_run_datasets_ingestion_runs` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-041`, `N-FK-041` (propuestos; no ejecutados) |
| FK-042 | `fk_042_run_datasets_datasets` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-042`, `N-FK-042` (propuestos; no ejecutados) |
| FK-043 | `fk_043_dataset_sources_datasets` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-043`, `N-FK-043` (propuestos; no ejecutados) |
| FK-044 | `fk_044_dataset_sources_data_sources` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-044`, `N-FK-044` (propuestos; no ejecutados) |
| FK-045 | `fk_045_dataset_sources_data_endpoints` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-045`, `N-FK-045` (propuestos; no ejecutados) |
| FK-046 | `fk_046_dataset_sources_market_instruments` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-046`, `N-FK-046` (propuestos; no ejecutados) |
| FK-047 | `fk_047_dataset_sources_ingestion_requests` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-047`, `N-FK-047` (propuestos; no ejecutados) |
| FK-048 | `fk_048_dataset_sources_policy_evaluations` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-048`, `N-FK-048` (propuestos; no ejecutados) |
| FK-049 | `fk_049_dataset_lineage_datasets` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-049`, `N-FK-049` (propuestos; no ejecutados) |
| FK-050 | `fk_050_dataset_lineage_datasets` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-050`, `N-FK-050` (propuestos; no ejecutados) |
| FK-051 | `fk_051_dataset_lineage_transformation_runs` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-051`, `N-FK-051` (propuestos; no ejecutados) |
| FK-052 | `fk_052_data_validations_datasets` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-052`, `N-FK-052` (propuestos; no ejecutados) |
| FK-053 | `fk_053_data_validations_ingestion_runs` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-053`, `N-FK-053` (propuestos; no ejecutados) |
| FK-054 | `fk_054_transformation_runs_transformations` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-054`, `N-FK-054` (propuestos; no ejecutados) |
| FK-055 | `fk_055_transformation_runs_ingestion_runs` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-055`, `N-FK-055` (propuestos; no ejecutados) |
| FK-056 | `fk_056_research_experiment_runs_research_experiments` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-056`, `N-FK-056` (propuestos; no ejecutados) |
| FK-057 | `fk_057_research_run_artifacts_research_experiment_runs` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-057`, `N-FK-057` (propuestos; no ejecutados) |
| FK-058 | `fk_058_research_hypotheses_research_experiments` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-058`, `N-FK-058` (propuestos; no ejecutados) |
| FK-059 | `fk_059_experiment_datasets_research_experiments` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-059`, `N-FK-059` (propuestos; no ejecutados) |
| FK-060 | `fk_060_experiment_datasets_datasets` | SIMPLE (provisional) | RESTRICT (provisional) | RESTRICT (provisional) | NO (provisional) | NO (provisional) | `P-FK-060`, `N-FK-060` (propuestos; no ejecutados) |

La columna `constraint_name` propone nombres estables únicos; puede ajustarse a la convención final del repositorio, conservando el ID FK como referencia cruzada. `MATCH SIMPLE`, `RESTRICT`, `NOT DEFERRABLE` e `INITIALLY IMMEDIATE` se registran como baseline provisional. Para FK-008/009 debe decidirse si `MATCH FULL` es compatible con la semántica exacta de sus columnas y CHECKs. FK-047 queda en MATCH SIMPLE: la solicitud es opcional, mientras fuente y endpoint siguen siendo obligatorios.


### 8.1 Correcciones de consistencia aplicadas a la especificación física

Se corrigieron dos contradicciones documentales en `postgresql-physical-schema.md` dentro de esta misma rama:

1. En `dataset_sources`, la frase que decía que los tres componentes de la FK de `ingestion_requests` podían ser NULL contradice las definiciones `data_source_id NOT NULL` y `data_endpoint_id NOT NULL`. Ahora se especifica que solo `ingestion_request_id` es nullable y que MATCH SIMPLE omite esa FK opcional, mientras las FKs independientes siguen validando fuente y endpoint.
2. En §13.2, se corrigió “clave candidata de cinco columnas” a “cuatro columnas”, coincidiendo con la FK y el UNIQUE explícitos: `(id, provider_platform_id, candidate_network_id, resolution_status)`.
