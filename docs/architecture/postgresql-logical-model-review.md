# Revisión técnica del modelo lógico de PostgreSQL

- **Estado:** reconciliación documental v0.4 parcial; pendiente de validación automatizada y PostgreSQL real. No autoriza todavía migraciones.
- **Fecha:** 2026-11-06.
- **Documentos:** `postgresql-logical-data-model.md` v0.4 y `postgresql-physical-schema.md` v0.3.
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
4. **Integridad revisión→mapping especificada:** FKs compuestas que incorporan `resolution_status = 'accepted'`, destino, namespace e identificador; para mappings de representación también red y FK a `(asset_representation_id, network_id)`. Para mappings de activo, un trigger compara `network_id` con semántica NULL-safe. La publicación se ejecuta en una única transacción. Falta implementar y probar estas reglas en PostgreSQL real.
5. Definir reglas de no solapamiento y selección histórica de mappings bajo concurrencia; CHECK no puede imponerlas por sí solo.
6. Revisar las restricciones de estado terminal y las invariantes de contadores antes del DDL.
7. Implementar el trigger de ámbito de red para `asset_identifiers`, permisos de escritura append-only y pruebas de rollback atómico para ambos tipos de mapping.

## 5. Plan de validación real PostgreSQL

Una vez cerrados los pendientes anteriores:

- Generar migraciones SQL versionadas desde el contrato reconciliado.
- Levantar PostgreSQL de prueba con versión fijada y configuración reproducible.
- Aplicar migraciones desde una base vacía y comprobar rollback/fallo seguro.
- Insertar fixtures sintéticos válidos y comprobar rechazo de FK cruzadas, CHECKs y UNIQUE.
- Probar intervalos temporales, solapamientos y casos límite UTC.
- Probar transacciones de publicación de mappings y procedencia.
- Verificar en PostgreSQL que las FKs compuestas rechacen mapping con revisión pending/rejected, destino distinto, namespace/identificador distinto y red incompatible; verificar trigger NULL-safe para mappings de activo.
- Probar concurrencia para evitar ciclos de linaje, doble publicación y transiciones terminales incompatibles.
- Separar resultados de pytest/contratos Python de resultados ejecutados por el servidor PostgreSQL.

## 6. Criterio de salida

PR #16 permanece Draft hasta que la comparación documental no encuentre divergencias, se resuelvan los pendientes del apartado 4 y exista una suite que ejecute contra PostgreSQL real. Las 48 pruebas Python aprobadas se reportan exclusivamente como pruebas de contratos de aplicación; nunca como pruebas del motor PostgreSQL.

No se han creado migraciones ni se ha desplegado PostgreSQL en esta revisión.

## 7. Integridad temporal de identidades: decisión de diseño

Se corrige una imprecisión de la versión anterior: `recorded_at` no es por sí solo un intervalo bitemporal. El diseño adoptado conserva eventos/revisiones append-only con `recorded_at` inmutable y reconstruye el estado conocido en `known_at` mediante la cadena lineal de `supersedes_review_id`. La validez en el dominio se consulta por separado con `valid_at` dentro de `[valid_from, valid_until)`. No se añaden columnas `recorded_from/recorded_until`, porque cerrar intervalos de conocimiento exigiría actualizar filas históricas y rompería el contrato append-only.

Decisiones:
1. Cada `namespace` define un solo modo de alcance: global (`network_id IS NULL`) o por red (`network_id IS NOT NULL`). Los identificadores globales y los identificadores contractuales/de red pertenecen a namespaces diferentes. No se admite mezclar ambos modos en un mismo namespace.
2. La clave de conflicto es `(namespace, external_identifier)` para namespace global y `(namespace, network_id, external_identifier)` para namespace por red.
3. Para una misma clave y un mismo `known_at`, no puede haber dos revisiones accepted efectivas con intervalos `valid time` solapados y destinos distintos. Los intervalos son semiabiertos; el contacto exacto entre fin e inicio no es solapamiento.
4. `supersedes_review_id` solo puede enlazar una revisión anterior de la misma clave. No se permiten autorreferencias, ciclos ni dos sucesoras competidoras. Las alternativas irresolubles se registran como `ambiguous`.
5. Una corrección retroactiva crea una revisión nueva con `recorded_at` posterior y el periodo de validez corregido. Las consultas con un `known_at` anterior siguen devolviendo la decisión que CCI conocía entonces.
6. La revisión y el mapping accepted se publican atómicamente. El mapping replica exactamente destino, namespace, identificador, red y periodo de la revisión.
7. La escritura toma un bloqueo transaccional determinista por clave de identidad antes de validar sustituciones y solapamientos. Se probarán carreras con dos sesiones PostgreSQL; un prechequeo de aplicación sin bloqueo no es suficiente.

La especificación física debe concretar la función/trigger, la clave de bloqueo, los permisos append-only y el procedimiento de reintento transaccional. Las FKs y CHECK actuales no prueban estas invariantes. El modo de alcance por namespace debe quedar fijado en un registro canónico. Ese registro todavía no existe como entidad relacional; definirlo y añadir su integridad referencial es un pendiente previo a migraciones.

## 8. Pendientes técnicos actualizados

- Definir la semántica completa de sucesión de intervalos (nueva vigencia frente a corrección retroactiva), el desempate determinista de revisiones registradas en el mismo instante y la validación de sucesión por clave.
- Diseñar el registro persistente de namespaces y su modo de alcance; después implementar exclusión temporal por clave bajo bloqueo transaccional, incluida la prevención de mezcla de scopes.
- Garantizar que los mappings reproduzcan el intervalo exacto de la revisión aceptada.
- Probar consultas `valid_at/known_at`, correcciones retroactivas, cierre y reapertura de vigencia, solapamientos, sustituciones inválidas y carreras concurrentes en PostgreSQL real.
- Definir una secuencia monotónica por clave si se necesita desempate total además de `recorded_at`; mantener eventos/revisiones append-only mediante roles y triggers; comprobar rollback atómico de revisión y mapping.
