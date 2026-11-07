# Matriz normalizada de claves foráneas — Issue #25

- Fuente normativa: `docs/architecture/postgresql-physical-schema.md`, contrato v0.8.
- Cobertura de inventario: 34/34 tablas.
- Estado: **borrador de normalización documental; no aprobado para generación automática de DDL**.
- Regla de seguridad: no se inventan columnas. Las decisiones no expresadas en v0.8 se marcan como pendientes.
- Convención de nombres: los nombres `fk_<tabla>__<destino>__<rol>` son identificadores propuestos, no nombres ya implementados.

## 1. Convenciones que deben ratificarse

La especificación física establece como convención general `ON DELETE RESTRICT ON UPDATE RESTRICT` para FKs históricas y prefiere RESTRICT también en tablas asociativas. Esta matriz lo registra como **acción propuesta por convención**, no como DDL ya ejecutado.

La especificación no fija individualmente `MATCH`, `DEFERRABLE` ni `INITIALLY DEFERRED`. Para no ocultar esa ausencia:
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
| FK-009 | network_identifiers | provider_platform_resolution_review_id, provider_platform_id, network_id, provider_platform_resolution_status | provider_platform_resolution_reviews | id, provider_platform_id, candidate_network_id, resolution_status | OPT | Cuatro componentes deben ser todos NULL para identificador nativo o completos/accepted para proveedor; requiere CHECK explícito. |
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
| FK-047 | dataset_sources | ingestion_request_id, data_source_id, data_endpoint_id | ingestion_requests | id, data_source_id, data_endpoint_id | OPT | Los tres componentes deben ser NULL o completos; comprobar CHECK para evitar NULL parcial. |
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
| asset_identity_resolution_reviews | (id, clave de sustitución por identidad) | FK-024; pendiente de concretar constraint/índice |
| market_instruments | (id, data_source_id) | FK-040, 046 |
| ingestion_requests | (id, data_source_id, data_endpoint_id) | FK-047 |

La especificación usa la expresión “UNIQUE candidato” en varios de estos puntos. No se considerará resuelto hasta comprobar que la restricción aparece realmente en el DDL final y que las columnas y tipos coinciden en orden.

## 5. Pendientes bloqueantes antes de DDL

1. **Recuento y cobertura:** validar automáticamente los 34 nombres contra el inventario físico; confirmar que la tabla de cobertura no contiene duplicados ni omisiones.
2. **Claves destino:** comprobar PK/UNIQUE real para cada referencia compuesta, especialmente las marcadas como candidatas.
3. **Nulabilidad:** añadir CHECK para grupos de procedencia opcionales que deben ser todos NULL o todos completos: FK-008/009 y FK-047; revisar FK-040 y FK-046.
4. **MATCH:** ratificar SIMPLE o FULL por relación. MATCH FULL puede ser apropiado para grupos opcionales compuestos que deban ser todos NULL/completos; no cambiarlo sin evaluar las columnas y restricciones.
5. **Acciones:** confirmar RESTRICT/RESTRICT por relación, sin asumir CASCADE en asociaciones.
6. **Diferibilidad:** confirmar NOT DEFERRABLE/INITIALLY IMMEDIATE o justificar diferibilidad para inserciones cíclicas/operaciones atómicas.
7. **Triggers/funciones:** especificar y probar igualdad NULL-safe de scope, cadenas append-only, no ciclos de sustitución y publicación atómica de mappings; una FK no implementa esas invariantes.
8. **Grafo:** cálculo provisional completado en §7: 34/34 tablas ordenables, dos autorreferencias y cero ciclos entre tablas distintas. Recalcular cuando cambie una relación o se cierre una decisión pendiente.
9. **Tests:** asignar IDs de pruebas positivas/negativas a cada FK y ejecutar contra PostgreSQL 16 desde base vacía.

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
