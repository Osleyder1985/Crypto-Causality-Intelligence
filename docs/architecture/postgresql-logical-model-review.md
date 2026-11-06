# Revisión técnica del modelo lógico de PostgreSQL

- **Estado:** reconciliación documental v0.3 completada; pendiente de validación automatizada y PostgreSQL real. No autoriza todavía migraciones.
- **Fecha:** 2026-11-06.
- **Documentos:** `postgresql-logical-data-model.md` v0.3 y `postgresql-physical-schema.md` v0.2.
- **Decisión relacionada:** ADR-001.
- **PR de trabajo:** #16.

## 1. Dictamen

Se ha actualizado el modelo lógico para que represente el inventario, las entidades, los atributos y las relaciones del diseño físico. Se corrigieron los desajustes que impedían tratarlos como un único contrato:

- La autorización por contribución se expresa mediante `policy_evaluations`, no mediante una referencia directa de `dataset_sources` a `source_usage_policies`.
- `dataset_sources` incluye `data_type` y lo incorpora en su FK compuesta a la evaluación.
- `source_usage_policies` incorpora `scope_reference` para identificar producto/plan o tipo de dato según el alcance.
- El dominio de activos ya no contiene `assets.network`; redes y representaciones tienen entidades independientes.
- El diagrama lógico refleja redes, identificadores, representaciones, revisiones de identidad, evaluaciones de política, reglas de negociación y `run_datasets`.
- Las FKs compuestas de solicitudes y procedencia quedan expresamente recogidas como parte del contrato, no como una validación exclusiva de aplicación.

## 2. Estado de los hallazgos

| Hallazgo | Estado documental | Evidencia |
|---|---|---|
| Evaluación concreta de política por contribución | <span>Resuelto en documentación</span> | `policy_evaluations` en modelo lógico y físico; snapshot y decisión append-only. |
| Relación Run/dataset | Resuelto en documentación | `run_datasets` en ambos modelos. |
| Coherencia fuente/endpoint/instrumento/solicitud | Resuelto en documentación | FKs compuestas descritas en la especificación física y contrato lógico. |
| Versionado de metadata y reglas | Resuelto en documentación | `instrument_metadata_versions` y `instrument_trading_rules`. |
| Identidad de activos y redes | Resuelto en documentación | `networks`, `network_identifiers`, `asset_representations`, identificadores y relaciones tipadas. |
| Alcance de política product/plan | Resuelto en diseño documental | `scope_reference` con reglas CHECK; referencia textual estable, sin inventar catálogo de productos. |
| Tipo de dato en procedencia | Resuelto en diseño documental | `dataset_sources.data_type` y clave candidata/FK compuesta de cinco columnas. |
| Diagrama y diccionario lógico | Resuelto en documentación | Inventario y diagrama revisados en v0.3. |

**Importante:** “resuelto en documentación” no significa “probado por PostgreSQL”. No existe todavía DDL ejecutable ni evidencia del motor para estas restricciones.

## 3. Decisiones de integridad que deben conservarse

1. La FK de `dataset_sources` debe incluir `policy_evaluation_id, data_source_id, data_endpoint_id, data_type, evaluated_intended_use`.
2. `policy_evaluations` debe exponer UNIQUE sobre `(id, data_source_id, data_endpoint_id, data_type, intended_use)`.
3. `source_usage_policies.scope_reference` debe tener CHECK coherente con `policy_scope`: requerido y no vacío para product/data_type; NULL para provider/endpoint. El alcance endpoint exige `data_endpoint_id`.
4. `ingestion_requests` debe impedir combinar endpoint e instrumento de fuentes distintas.
5. `dataset_sources` debe impedir que solicitud, endpoint, instrumento, fuente y evaluación pertenezcan a ámbitos incompatibles.
6. Las revisiones de identidad aceptadas deben publicar exactamente un destino coherente y conservar evidencia temporal.
7. Las restricciones CHECK no evitan solapamientos de intervalos, ciclos de linaje ni transiciones inválidas; estos casos requieren lógica transaccional y pruebas de concurrencia.

## 4. Pendientes antes de generar migraciones

La alineación de inventario y entidades está cerrada como propuesta. La comparación automatizada confirma 28/28 tablas representadas en el modelo lógico. Todavía se requiere:

1. **Inventario de entidades verificado:** comparación automatizada del inventario físico contra el modelo lógico: 28/28 tablas físicas están representadas en el modelo lógico, sin entidades ausentes. Esta comprobación confirma cobertura de nombres de tablas; no sustituye una revisión semántica de cada columna y restricción.
2. Verificar que el vocabulario de `data_type` en endpoints, evaluaciones y contribuciones sea canónico y no se permita una discrepancia semántica.
3. Definir la semántica operacional de `scope_reference` y documentar el formato de claves de producto/plan y de tipo de dato.
4. Resolver la integridad entre `asset_identity_resolution_reviews` y los mappings publicados: las FKs simples no garantizan por sí solas que el mapping apunte a una revisión accepted del mismo destino. Debe decidirse FK compuesta, trigger o servicio transaccional con pruebas.
5. Definir reglas de no solapamiento y selección bitemporal de mappings; CHECK no puede imponerlas por sí solo.
6. Revisar las restricciones de estado terminal y las invariantes de contadores antes del DDL.

## 5. Plan de validación real PostgreSQL

Una vez cerrados los pendientes anteriores:

- Generar migraciones SQL versionadas desde el contrato reconciliado.
- Levantar PostgreSQL de prueba con versión fijada y configuración reproducible.
- Aplicar migraciones desde una base vacía y comprobar rollback/fallo seguro.
- Insertar fixtures sintéticos válidos y comprobar rechazo de FK cruzadas, CHECKs y UNIQUE.
- Probar intervalos temporales, solapamientos y casos límite UTC.
- Probar transacciones de publicación de mappings y procedencia.
- Probar concurrencia para evitar ciclos de linaje, doble publicación y transiciones terminales incompatibles.
- Separar resultados de pytest/contratos Python de resultados ejecutados por el servidor PostgreSQL.

## 6. Criterio de salida

PR #16 permanece Draft hasta que la comparación documental no encuentre divergencias, se resuelvan los pendientes del apartado 4 y exista una suite que ejecute contra PostgreSQL real. Las 48 pruebas Python aprobadas se reportan exclusivamente como pruebas de contratos de aplicación; nunca como pruebas del motor PostgreSQL.

No se han creado migraciones ni se ha desplegado PostgreSQL en esta revisión.
