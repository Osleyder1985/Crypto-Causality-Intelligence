# Revisión técnica del modelo lógico de PostgreSQL

- **Estado:** reconciliación documental v0.6 parcial; pendiente de validación automatizada y PostgreSQL real. No autoriza todavía migraciones.
- **Fecha:** 2026-11-06.
- **Documentos:** `postgresql-logical-data-model.md` v0.6 y `postgresql-physical-schema.md` v0.5.
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

La alineación de inventario y entidades está cerrada como propuesta. La comparación automatizada confirma 31/31 tablas representadas en el modelo lógico. Todavía se requiere:

1. **Inventario de entidades verificado:** comparación automatizada del inventario físico contra el modelo lógico: 31/31 tablas físicas están representadas en el modelo lógico, sin entidades ausentes. Esta comprobación confirma cobertura de nombres de tablas; no sustituye una revisión semántica de cada columna y restricción.
2. Mantener el catálogo `identity_namespaces` sin poblar hasta que exista evidencia concreta por proveedor/endpoint y la etapa de validación autorice su carga. El procedimiento de resolución de redes y plataformas ya está documentado; las filas y mappings reales siguen fuera de alcance.
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
- Antes del DDL, traducir las reglas de `network-identity-resolution-policy.md` y de `identity_namespaces` a restricciones/funciones/triggers; después probar exclusión temporal por clave bajo bloqueo transaccional.
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


## 10. Cierre documental del procedimiento de identidad de redes

Se incorpora `network-identity-resolution-policy.md` y se amplía el contrato lógico/físico con `provider_platforms` y `provider_platform_resolution_reviews`. El inventario físico pasa de 29 a **31 entidades**, y el modelo lógico y el diagrama incorporan ambas relaciones.

Decisiones:
- `networks.network_key` permanece como identidad interna canónica.
- `network_identifiers` conserva identificadores técnicos y externos namespaced, con evidencia.
- El ID de plataforma CoinGecko se registra como identificador del proveedor, nunca como clave canónica.
- `chain_identifier` nullable se conserva como dato reportado; no se imputa ni se acepta aisladamente como prueba.
- En EVM se requiere Chain ID namespaced y corroboración independiente cuando corresponda; no se presume unicidad universal.
- En Solana se utiliza `getGenesisHash` como evidencia nativa de clúster, sin inventar Chain ID.
- La publicación de la correspondencia accepted y del identificador externo debe ser atómica y append-only.
- Las direcciones contractuales quedan bloqueadas hasta que la plataforma se resuelva a una única red canónica.

**Estado:** cierre del procedimiento documental. No se ha poblado el catálogo, no se han creado mappings reales, no se han generado migraciones ni se ha probado PostgreSQL real. La ampliación de entidades y restricciones debe someterse a comparación automatizada y revisión de integridad antes de generar DDL. Las pruebas Python existentes no validan estas restricciones del motor.

Fuente normativa/técnica: CoinGecko Asset Platforms List, EIP-155 y Solana RPC `getGenesisHash`; referencias y procedimiento completos en `network-identity-resolution-policy.md`.


## 11. Auditoría de integridad: plataformas de proveedor → redes canónicas

**Resultado:** se detectaron brechas en la especificación anterior y se corrigió el contrato lógico/físico. La auditoría no equivale a pruebas ejecutadas en PostgreSQL.

### Hallazgos

| ID | Riesgo detectado | Corrección documental | Estado |
|---|---|---|---|
| NET-01 | Un `network_identifiers` podía declarar un ID de proveedor sin FK hacia la revisión accepted que lo autorizó. | Se añadieron referencias opcionales a observación, fuente, revisión y estado; FKs compuestas para exigir misma observación, valor literal, destino y estado accepted. | Corregido en diseño; DDL pendiente |
| NET-02 | La revisión podía referir una plataforma por UUID sin hacer explícita la coherencia de proveedor. | Se añadió `data_source_id` a la revisión y FK compuesta hacia la observación de `provider_platforms`. | Corregido en diseño; DDL pendiente |
| NET-03 | La revisión no expresaba el intervalo de validez de la correspondencia. | Se añadieron `valid_from/valid_until` y CHECK de intervalo semiabierto. | Corregido en diseño; DDL pendiente |
| NET-04 | La sucesión histórica podía enlazar revisiones de plataformas distintas o admitir dos sucesoras concurrentes. | Se exige sucesión de la misma clave de proveedor/plataforma, unicidad de sucesora y trigger transaccional para ciclo y coherencia. | Especificado parcialmente; requiere diseño detallado y pruebas |
| NET-05 | La unicidad por timestamp exacto y la semántica de snapshots frente a correcciones no estaban resueltas. | Se registró como decisión bloqueante antes del DDL. | Pendiente |
| NET-06 | El tipo `NUMERIC` para `chain_identifier` se eligió sin cerrar si el contrato oficial garantiza forma numérica canónica. | Se exige verificar el tipo y preservar literal reportado; no se convierte a número por conveniencia. | Pendiente de contrato endpoint |

### Invariantes relacionales obligatorias

1. Una fila de `network_identifiers` que represente una plataforma de proveedor debe contener conjuntamente observación, fuente, revisión y estado accepted; para identificadores nativos esos campos serán todos NULL.
2. La FK de la observación debe hacer coincidir exactamente `provider_platform_id` con `identifier_value` y `data_source_id` con la fuente de la observación.
3. La FK de revisión debe hacer coincidir exactamente revisión, observación, red destino y `resolution_status = 'accepted'`.
4. CHECK adicional debe vincular los campos de procedencia con el namespace/tipo de identificador esperado para plataforma; no se permite una fila parcialmente poblada.
5. Una revisión accepted exige una red destino, evidencia, decisión/revisor y `valid_from`; una revisión no accepted no puede publicarse como identificador.
6. La publicación de revisión e identificador externo se hace en una sola transacción. Las FKs impiden combinaciones incompatibles, pero no demuestran calidad ni autoridad de la evidencia.
7. La sucesión debe operar sobre `(data_source_id, provider_platform_id)`, no sobre el UUID aislado del snapshot. Debe distinguir corrección de una decisión de la mera llegada de un snapshot nuevo.

### Decisiones que bloquean la implementación SQL

- Definir si una nueva observación de la misma plataforma requiere revisión nueva sin sustituir la revisión anterior, o si la sucesión representa exclusivamente correcciones/revocaciones de decisiones. No mezclar ambas dimensiones.
- Definir la regla para dos capturas con el mismo `observed_at`: rechazar duplicado, usar un `snapshot_id` determinista o conservar una secuencia de captura. No depender de timestamps de precisión finita como orden total.
- Definir las columnas de sucesión necesarias para una FK compuesta y el índice parcial UNIQUE de sucesora; completar el trigger para validar que no haya ciclos y que toda la cadena mantenga la misma clave de proveedor/plataforma.
- Definir bloqueo transaccional estable por proveedor + platform ID y pruebas de dos sesiones concurrentes.
- Confirmar en documentación oficial el tipo JSON de `chain_identifier`; preservar NULL y el literal sin inferir valores.

### Pruebas negativas requeridas en PostgreSQL real

- Insertar identificador de plataforma sin revisión: debe fallar.
- Insertar identificador con revisión `pending_review`, `rejected` o `ambiguous`: debe fallar.
- Insertar identificador con revisión accepted pero red distinta: debe fallar.
- Insertar identificador cuyo literal no coincide con el `provider_platform_id` observado: debe fallar.
- Cruzar observación de proveedor A con fuente/proveedor B: debe fallar.
- Insertar una revisión accepted sin candidato, evidencia o `valid_from`: debe fallar.
- Insertar dos sucesoras de una revisión o crear un ciclo: debe fallar.
- Publicar revisión sin mapping o mapping sin revisión dentro de una transacción: rollback atómico según el contrato de servicio.
- Ejecutar dos resoluciones concurrentes para la misma plataforma con redes distintas: como máximo una puede publicarse como vigente.

### Estado del trabajo

Se actualizaron `postgresql-physical-schema.md` y `postgresql-logical-data-model.md` con las FKs compuestas y la temporalidad de las revisiones. No se han creado migraciones, no se ha ejecutado DDL y no se afirma que estas restricciones hayan sido probadas por el motor PostgreSQL. PR #16 continúa Draft.
