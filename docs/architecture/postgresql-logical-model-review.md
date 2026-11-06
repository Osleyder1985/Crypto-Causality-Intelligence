# Revisión técnica del modelo lógico de PostgreSQL

- **Estado:** reconciliación documental v0.5 parcial; pendiente de validación automatizada y PostgreSQL real. No autoriza todavía migraciones.
- **Fecha:** 2026-11-06.
- **Documentos:** `postgresql-logical-data-model.md` v0.5 y `postgresql-physical-schema.md` v0.4.
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

La alineación de inventario y entidades está cerrada como propuesta. La comparación automatizada confirma 29/29 tablas representadas en el modelo lógico. Todavía se requiere:

1. **Inventario de entidades verificado:** comparación automatizada del inventario físico contra el modelo lógico: 29/29 tablas físicas están representadas en el modelo lógico, sin entidades ausentes. Esta comprobación confirma cobertura de nombres de tablas; no sustituye una revisión semántica de cada columna y restricción.
2. Definir y registrar los namespaces concretos que CCI utilizará inicialmente, con evidencia de autoridad, semántica y nivel de destino; la tabla `identity_namespaces` ya está especificada, pero no hay catálogo poblado ni namespaces aprobados todavía.
3. Verificar que el vocabulario de `data_type` en endpoints, evaluaciones y contribuciones sea canónico y no se permita una discrepancia semántica.
4. Definir la semántica operacional de `scope_reference` y documentar el formato de claves de producto/plan y de tipo de dato.
5. **Integridad revisión→mapping especificada:** FKs compuestas que incorporan `resolution_status = 'accepted'`, destino, namespace e identificador; para mappings de representación también red y FK a `(asset_representation_id, network_id)`. Para mappings de activo, un trigger compara `network_id` con semántica NULL-safe. La publicación se ejecuta en una única transacción. Falta implementar y probar estas reglas en PostgreSQL real.
6. Definir reglas de no solapamiento y selección histórica de mappings bajo concurrencia; CHECK no puede imponerlas por sí solo.
7. Revisar las restricciones de estado terminal y las invariantes de contadores antes del DDL.
8. Implementar el trigger de ámbito de red y nivel de destino para `asset_identity_resolution_reviews`, el trigger NULL-safe de ámbito para `asset_identifiers`, permisos de escritura append-only y pruebas de rollback atómico para ambos tipos de mapping.

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

La especificación física debe concretar la función/trigger, la clave de bloqueo, los permisos append-only y el procedimiento de reintento transaccional. Las FKs y CHECK actuales no prueban estas invariantes. El catálogo `identity_namespaces` ya está especificado en los modelos lógico y físico, con FK desde las revisiones. Sigue pendiente poblarlo con namespaces concretos respaldados por evidencia e implementar/probar el trigger que valida `scope_mode` y `target_level`.

## 8. Pendientes técnicos actualizados

- Definir la semántica completa de sucesión de intervalos (nueva vigencia frente a corrección retroactiva), el desempate determinista de revisiones registradas en el mismo instante y la validación de sucesión por clave.
- Definir el conjunto inicial de filas de `identity_namespaces` con evidencia y validar por trigger `scope_mode`/`target_level`; después implementar exclusión temporal por clave bajo bloqueo transaccional.
- Garantizar que los mappings reproduzcan el intervalo exacto de la revisión aceptada.
- Probar consultas `valid_at/known_at`, correcciones retroactivas, cierre y reapertura de vigencia, solapamientos, sustituciones inválidas y carreras concurrentes en PostgreSQL real.
- Definir una secuencia monotónica por clave si se necesita desempate total además de `recorded_at`; mantener eventos/revisiones append-only mediante roles y triggers; comprobar rollback atómico de revisión y mapping.


## 9. Validación documental inicial de namespaces (2026-11-06)

Se revisó documentación oficial de CoinGecko, Binance Spot y Kraken Spot. Resultado:

| Campo | Decisión | Motivo |
|---|---|---|
| CoinGecko `/coins/list[].id` | Aprobar `coingecko:coin_id`, global / asset | Es el identificador del catálogo del proveedor; los nombres y símbolos no son identificadores inequívocos. No representa por sí solo una identidad universal. |
| CoinGecko `platforms[platform_id]` | Aprobar `coingecko:contract_address`, network / representation, condicionado a resolver plataforma→red | La dirección es específica de una plataforma/red y representa un contrato, no el activo abstracto. |
| Binance `baseAsset` / `quoteAsset` | No crear namespace de activo | Son campos de los componentes de un símbolo de mercado; la documentación consultada no prueba unicidad global. |
| Kraken `base_asset` / `quote_asset` | No crear namespace de activo | Son códigos de los componentes de un par de mercado; no prueban identidad global. |
| Binance/Kraken símbolos y alias de pares | Mantener en `market_instruments` / `instrument_identifiers` | Identifican instrumentos/listados o interfaces, no activos universales. |

Fuentes oficiales: CoinGecko Coins List (ID Map), https://docs.coingecko.com/reference/coins-list; CoinGecko Asset Platforms List, https://docs.coingecko.com/reference/asset-platforms-list; Binance Spot Exchange Information y Spot Glossary, https://developers.binance.com/en/docs/products/spot/market-data/rest-api/exchange-information y https://developers.binance.com/en/docs/products/spot/faqs/spot_glossary; Kraken Spot Post-Trade Data, https://docs.kraken.com/api/docs/rest-api/get-post-trade.

### Condiciones pendientes antes de poblar el catálogo

1. Obtener y revisar una captura documental/versionada de los metadatos CoinGecko usados, sin almacenar datos cuya licencia o política no lo permita.
2. Definir la tabla de correspondencia CoinGecko platform ID → `networks.network_key`, con fuente oficial de chain ID/genesis u otra evidencia adecuada; no equiparar IDs por coincidencia textual.
3. Confirmar el tratamiento de redes sin chain ID numérico y de plataformas que representan redes/entornos distintos.
4. Verificar semántica y normalización de direcciones por familia de red sin modificar el literal original.
5. Mantener los códigos Binance/Kraken en contexto de instrumento hasta que una evidencia independiente permita una resolución revisada a `assets`.

La documentación no autoriza todavía insertar filas en `identity_namespaces`, crear mappings aceptados, generar migraciones ni declarar pruebas PostgreSQL. El próximo paso es cerrar el catálogo de redes/plataformas y las reglas de normalización de direcciones; después se podrá fijar el conjunto inicial de filas del registro.
