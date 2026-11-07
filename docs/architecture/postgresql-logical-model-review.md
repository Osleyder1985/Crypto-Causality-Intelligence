# Revisión técnica del modelo lógico de PostgreSQL

- **Estado:** reconciliación documental v0.8 parcial; pendiente de validación automatizada y PostgreSQL real. No autoriza todavía migraciones.
- **Fecha:** 2026-11-06.
- **Documentos:** `postgresql-logical-data-model.md` v0.8 y `postgresql-physical-schema.md` v0.8.
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

La alineación de inventario y entidades está cerrada como propuesta. La comparación automatizada de nombres entre el inventario físico y las entidades lógicas confirma 34/34 tablas representadas; no sustituye la revisión semántica de columnas, FKs, CHECKs, triggers e índices. Todavía se requiere:

1. **Inventario de entidades verificado:** comparación automatizada del inventario físico contra el modelo lógico: 34/34 tablas físicas están representadas en el modelo lógico, sin entidades ausentes. Esta comprobación confirma cobertura de nombres de tablas; no sustituye una revisión semántica de cada columna y restricción.
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

Se incorpora `network-identity-resolution-policy.md` y se amplía el contrato lógico/físico con `provider_platforms` y `provider_platform_resolution_reviews`. En la revisión inicial el inventario físico pasó de 29 a **32 entidades**; la versión v0.8 integra después el registro de runs y alcanza 34, y el modelo lógico y el diagrama incorporan ambas relaciones.

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


## 11. Cierre de semántica temporal: identidad, snapshots y decisiones

**Decisión arquitectónica:** separar identidad estable de plataforma, observaciones del proveedor y decisiones de resolución. La versión previa mezclaba identidad y snapshot dentro de `provider_platforms`; ese acoplamiento ligaba una revisión a una captura arbitraria y confundía ingestión con cambio de decisión.

### Modelo aprobado a nivel documental

| Entidad | Semántica | Regla de identidad |
|---|---|---|
| `provider_platforms` | Identidad estable de plataforma dentro de un proveedor | UNIQUE `(data_source_id, provider_platform_key)` |
| `provider_platform_observations` | Snapshot inmutable de metadata | UNIQUE `(provider_platform_id, capture_id)` |
| `provider_platform_resolution_reviews` | Decisión append-only sobre identidad estable | Cadena lineal mediante `supersedes_review_id` |

### Decisiones NET-04 y NET-05

1. **Nueva captura ≠ nueva decisión.** Insertar una observación no crea una revisión ni modifica la cabeza de la cadena. La resolución accepted anterior permanece vigente mientras no exista una decisión sucesora y su intervalo cubra el instante consultado.
2. **La revisión se asocia a la identidad estable.** `provider_platform_id` es la FK principal. `based_on_observation_id` es opcional y, cuando existe, una FK compuesta obliga a que la observación pertenezca a la misma identidad y fuente.
3. **La sucesión solo expresa una decisión.** `supersedes_review_id` significa corrección, revocación o sustitución explícita. Nunca enlaza snapshots.
4. **Cadena lineal por identidad.** Una raíz y una única sucesora por revisión. UNIQUE parciales evitan bifurcaciones; FK compuesta asegura misma identidad; trigger impide ciclos.
5. **Snapshots con timestamps iguales.** La unicidad no depende de `observed_at`. Cada lote tiene `capture_id`; UNIQUE `(provider_platform_id, capture_id)` distingue capturas y rechaza duplicados de una plataforma dentro del mismo lote.
6. **Tiempo bitemporal.** `observed_at` es tiempo de observación; `recorded_at` es tiempo de conocimiento de CCI; `valid_from/valid_until` expresa vigencia real. Los intervalos son semiabiertos. El final efectivo de una decisión anterior puede derivarse del `valid_from` de su sucesora, sin UPDATE histórico.
7. **Inicio de vigencia obligatorio.** Toda revisión, incluso `pending_review`, `ambiguous` o `rejected`, exige `valid_from`. Sin ese instante, la vista no podría exponer correctamente estados no accepted ni calcular el intervalo efectivo. `valid_until`, cuando exista, debe ser posterior a `valid_from`.
8. **Serialización.** Antes de insertar una revisión, la transacción bloquea la fila de `provider_platforms` con `SELECT ... FOR UPDATE`, lee la cabeza y crea la sucesora. El lock se aplica a la identidad estable, no al UUID del snapshot.
8. **Cambio material.** Una diferencia descriptiva no cambia automáticamente la red. Si nueva evidencia altera la interpretación, contradice la resolución o activa revalidación, se crea una revisión sucesora.

### Cierre de NET-06

La documentación oficial del endpoint Asset Platforms List declara `chain_identifier` como `number | null` y lo describe como Chainlist chain ID. No especifica `integer`. Se adopta `reported_chain_identifier_json JSONB NOT NULL`, con CHECK `jsonb_typeof(...) IN ('number','null')`, evitando `REAL`/`DOUBLE PRECISION` y sin forzar integralidad en la observación. JSONB preserva el valor numérico exacto, pero no el lexema original; el cuerpo HTTP de evidencia con hash conserva esa fidelidad cuando sea necesaria. Antes de publicar un identificador EVM `eip155`, la capa de resolución valida que el valor sea un entero exacto. Fuente oficial: https://docs.coingecko.com/reference/asset-platforms-list.

### Invariantes relacionales obligatorias

- Identidad única por proveedor + literal externo.
- Cada observación pertenece a una identidad y fuente.
- Cada revisión pertenece a una identidad estable; la observación de soporte, si existe, pertenece a esa misma identidad.
- La cadena no puede cruzar plataformas/proveedores, ramificarse ni contener ciclos.
- Un snapshot nuevo no invalida por sí solo una revisión accepted.
- Solo la cabeza accepted y temporalmente vigente autoriza un mapping.
- `network_identifiers` conserva identidad de plataforma y revisión accepted exacta; el literal debe coincidir con `provider_platform_key`.
- Dos transacciones concurrentes para la misma identidad se serializan mediante bloqueo de fila.

### Matriz de pruebas PostgreSQL pendiente

| Caso | Resultado esperado |
|---|---|
| Dos snapshots con mismo `observed_at`, distinto `capture_id` | Ambos aceptados |
| Misma plataforma repetida en un `capture_id` | Rechazo por UNIQUE |
| Observación de otra identidad/proveedor | Rechazo por FK compuesta |
| Revisión con observación de otra plataforma | Rechazo por FK compuesta |
| Dos raíces o dos sucesoras | Rechazo por UNIQUE parcial |
| Ciclo en la cadena | Rechazo por trigger |
| Nueva observación sin revisión | La resolución accepted anterior permanece |
| Mapping con revisión no accepted, destino/literal distinto | Rechazo |
| Dos revisiones incompatibles concurrentes | Serialización; una sola sucesora confirma |
| Publicación parcial de revisión/mapping | Rollback atómico |

### Estado

Se cierra documentalmente NET-04 y NET-05 en cuanto a semántica y estructura propuesta. NET-06 queda acotado: se conserva literal y tipo JSON hasta confirmar el contrato. No se han generado migraciones, DDL ni pruebas PostgreSQL; las pruebas Python de contratos no validan el motor.


## 12. Especificación SQL y pruebas PostgreSQL

La sección 13 de `postgresql-physical-schema.md` concreta las claves candidatas, FKs compuestas, CHECKs, índices UNIQUE parciales, triggers de inmutabilidad/cadena/mapping, vista de resolución por tiempo válido, consulta bitemporal parametrizada, transacción de publicación y comportamiento de revocación.

Se incorpora una matriz de 25 pruebas de motor (PG-NET-01 a PG-NET-25), incluyendo pruebas con dos sesiones independientes para concurrencia y rollback. La CI Python no satisface esas pruebas.

**Estado:** especificación documental completa para revisión. No hay DDL ejecutable ni resultados de PostgreSQL real; no se declara validación empírica del motor.
