# Política de resolución de identidad de redes

- **Estado:** propuesta técnica para revisión; catálogo no poblado.
- **Versión:** 0.1.0-draft.
- **Fecha:** 2026-11-06.
- **Ámbito:** Crypto Causality Intelligence (CCI).
- **Documentos relacionados:** `postgresql-logical-data-model.md`, `postgresql-physical-schema.md`, `asset-representation-domain-model.md` y `asset-identity-resolution-policy.md`.
- **PR de trabajo:** #16.

## 1. Objetivo

Definir un procedimiento reproducible para resolver identificadores de plataformas de proveedores —inicialmente CoinGecko Asset Platforms— contra las redes canónicas de CCI. La resolución debe impedir que una dirección contractual se asocie a una red incorrecta y contamine la identidad de representaciones, activos y observaciones posteriores.

Esta política es independiente del proveedor. CoinGecko aporta metadatos y referencias externas; no define la identidad canónica de CCI.

## 2. Decisiones obligatorias

1. `networks.network_key` es la identidad interna estable de CCI. No se deriva de un nombre, ticker, URL, Chain ID ni identificador de proveedor.
2. `networks.id` es la PK técnica. `network_key` es la clave semántica estable, única y legible; no se recicla para otra red, fork o entorno.
3. `network_identifiers` conserva identificadores externos/técnicos namespaced, su literal original, ámbito, evidencia, fuente e instante de observación.
4. CoinGecko `asset_platforms[].id` es un identificador de plataforma del proveedor. Nunca es `network_key`, nunca es un Chain ID y no demuestra por sí solo identidad de red.
5. `chain_identifier` de CoinGecko puede ser NULL. Su presencia tampoco demuestra por sí sola unicidad universal ni identidad inequívoca de una red.
6. `name`, `shortname` y `native_coin_id` son metadatos descriptivos o referencias al catálogo de activos de CoinGecko; no son claves canónicas de red.
7. Las direcciones de contratos solo pueden resolverse después de aprobar la correspondencia plataforma/proveedor → red canónica. Si la red es desconocida o ambigua, la resolución de representación queda bloqueada.
8. Ninguna correspondencia se acepta por igualdad textual, similitud de nombres, ticker, símbolo nativo o coincidencia aislada de Chain ID.
9. La evidencia y las decisiones se conservan de forma append-only y con tiempo de observación, tiempo de decisión, referencia documental y procedencia.
10. No se poblará el catálogo ni se aprobarán mappings reales en esta etapa.

## 3. Separación de entidades y responsabilidades

| Entidad | Responsabilidad | No representa |
|---|---|---|
| `networks` | Identidad canónica interna de una red y su familia/entorno | Un proveedor o su catálogo |
| `network_identifiers` | Identificadores namespaced de una red, con evidencia | La clave canónica de CCI |
| `provider_platforms` | Registro de una plataforma tal como la publica un proveedor y sus snapshots | Una red canónica aprobada |
| `provider_platform_resolution_reviews` | Historial de candidatos, evidencia y decisión plataforma → red | Una aprobación automática |
| `asset_representations` | Representación nativa o contractual de un activo en una red ya resuelta | Un alias de plataforma |

El modelo lógico/físico debe mantener la relación entre proveedor y red como un proceso revisable. Un `provider_platform_id` puede aparecer como identificador externo de la red solo después de que la revisión correspondiente haya sido aceptada y siempre bajo un namespace del proveedor.

## 4. Interpretación del catálogo CoinGecko

El endpoint oficial Asset Platforms List documenta estos campos:

- `id`: asset platform ID del catálogo CoinGecko.
- `chain_identifier`: número o NULL; CoinGecko lo describe como Chainlist's chain ID.
- `name`: nombre de la cadena/plataforma.
- `shortname`: nombre corto.
- `native_coin_id`: CoinGecko ID de la moneda nativa.

Reglas de ingestión documental:

- Conservar el valor literal de `id`, el proveedor, endpoint, fecha de observación y referencia al snapshot/evidencia.
- Preservar `chain_identifier = null` como ausencia de dato. No imputarlo desde el nombre ni desde otro proveedor.
- Si `chain_identifier` está presente, conservar su valor y procedencia como dato reportado por CoinGecko; no convertirlo silenciosamente en un identificador verificado de CCI.
- Preservar `name`, `shortname` y `native_coin_id` como metadata del proveedor. No utilizarlos como claves de unión.
- Los cambios en el catálogo del proveedor crean una nueva observación/snapshot; no sobrescriben la evidencia histórica.
- La ausencia de una plataforma en una captura no demuestra que la red haya dejado de existir.

## 5. Procedimiento de resolución

### Paso 1 — Captura y aislamiento del proveedor

Registrar la plataforma bajo su namespace de proveedor, por ejemplo `coingecko:asset_platform_id`, junto con endpoint, instante, versión/captura y hash o referencia verificable cuando su conservación esté permitida. No crear aún una fila canónica en `networks` por el mero hecho de recibir una plataforma.

### Paso 2 — Clasificación preliminar

Determinar, con documentación y evidencia independiente, si la entrada describe:
- una red principal;
- una red de pruebas/desarrollo;
- una capa o entorno con identidad propia;
- un alias, producto, ecosistema o agrupación que no corresponde a una red independiente;
- una entrada insuficientemente documentada.

No inferir `network_family` o `environment` únicamente por el nombre de CoinGecko.

### Paso 3 — Recolección de identificadores nativos

Seleccionar identificadores que correspondan a la familia de red. Cada identificador debe incluir namespace/especificación, tipo, valor literal, autoridad, fuente, fecha de observación y evidencia. La selección debe ser adecuada a la semántica de la familia; no se exige que todas las familias compartan un mismo tipo de identificador.

### Paso 4 — Corroboración independiente

Contrastar la plataforma con documentación oficial del protocolo, documentación de la red, registros técnicos mantenidos por autoridades reconocibles y, cuando proceda, respuestas de nodos/RPC confiables. Registrar también evidencia contradictoria y limitaciones.

### Paso 5 — Revisión explícita

Crear una revisión con estado `pending_review`, `accepted`, `rejected` o `ambiguous`. Una revisión accepted debe identificar exactamente una fila `networks`, justificar la correspondencia y enlazar la evidencia. La decisión no puede depender únicamente de los campos descriptivos de CoinGecko.

### Paso 6 — Publicación atómica

Solo después de aceptar la revisión se publica la relación plataforma → red y, si corresponde, el identificador del proveedor en `network_identifiers`. La revisión y el mapping deben publicarse en una única transacción. Los mappings aceptados son append-only; una corrección genera una nueva revisión/sucesión, no una modificación silenciosa.

### Paso 7 — Habilitación de direcciones

Solo una plataforma resuelta a una única red puede habilitar la resolución de `coingecko:contract_address` hacia `asset_representations`. La clave de resolución debe incluir la red canónica y la dirección literal normalizada mediante una regla específica de familia, preservando siempre el valor original.

## 6. Evidencia por familia de red

### 6.1 Redes EVM

- El Chain ID debe registrarse namespaced como identificador EVM (por ejemplo, namespace `eip155`, tipo `chain_id`), conservando su representación numérica exacta.
- EIP-155 define el uso del Chain ID en la protección contra replay de transacciones; no establece por sí mismo un registro universal que garantice que ningún operador reutilizará un valor.
- Un Chain ID coincidente es evidencia relevante, pero no prueba suficiente cuando hay redes privadas, forks, clones, configuraciones reutilizadas o registros contradictorios.
- Para una resolución de alto impacto, corroborar como mínimo con documentación oficial de la red y una segunda señal técnica independiente. Según disponibilidad, considerar hash del bloque génesis, checkpoints/bloques de referencia, configuración de chain spec, endpoints RPC oficiales y documentación de bridges/rollups.
- No asumir que todos los EVM tienen un Chain ID válido, único o disponible. Si falta o hay colisión, la resolución permanece pendiente hasta obtener evidencia discriminante.
- No confundir `network_id` de protocolos/clientes con EIP-155 Chain ID.

### 6.2 Solana

- No inventar ni asignar un Chain ID numérico a Solana.
- Utilizar `getGenesisHash` como identificador técnico del clúster observado, namespaced como Solana genesis hash.
- La respuesta RPC debe vincularse a un endpoint identificado y a un instante de observación. Para decisiones críticas, corroborar el hash mediante endpoints independientes y contrastarlo con documentación/fuentes oficiales del clúster.
- El nombre `mainnet-beta`, `devnet` o `testnet` es descriptivo y no sustituye el hash ni la evidencia de origen.
- Un hash inesperado, discordante o no verificable bloquea la aceptación automática.

### 6.3 Otras familias

No reutilizar las reglas EVM o Solana por conveniencia. Cada familia requiere identificar su mecanismo nativo de identidad, el namespace que define su semántica, la autoridad que lo publica y la evidencia necesaria para distinguir redes, entornos y forks. Hasta documentar esa regla, la plataforma permanece pendiente.

## 7. Estados y comportamiento de resolución

| Estado | Significado | Efecto |
|---|---|---|
| `pending_review` | Evidencia incompleta o revisión no terminada | No habilita mappings de contratos |
| `accepted` | Una red canónica determinada con evidencia suficiente | Habilita mapping proveedor → red |
| `ambiguous` | Dos o más redes plausibles o señales contradictorias | Bloquea la resolución automática |
| `rejected` | La correspondencia propuesta no es válida | No habilita mappings |

La ausencia de `chain_identifier` no es un estado de error ni un motivo automático de rechazo: obliga a utilizar evidencia apropiada de la familia. La presencia del valor tampoco cambia automáticamente el estado a accepted.

## 8. Reglas de integridad que deberán reflejarse en PostgreSQL

La especificación física deberá garantizar, mediante FKs, UNIQUE, CHECK y lógica transaccional:

1. `network_key` es NOT NULL y UNIQUE; una clave no se recicla.
2. Los identificadores de red incluyen namespace y tipo; el valor aislado no se trata como global.
3. Un `provider_platform_id` es único dentro de su proveedor y dominio de catálogo, no globalmente.
4. Un mapping aceptado referencia una revisión accepted y la misma plataforma, proveedor y `network_id`.
5. Una revisión no accepted no puede publicar una relación activa que habilite resolución de contratos.
6. La publicación de revisión, identificador externo y mapping se realiza atómicamente.
7. Las decisiones y observaciones son append-only; las correcciones se representan mediante nuevas revisiones.
8. La resolución de una representación contractual exige `network_id` no nulo y una plataforma aceptada cuando el origen del contrato depende de dicha plataforma.
9. Los conflictos y solapamientos temporales se validan por clave bajo bloqueo transaccional; un prechequeo en Python no es suficiente.
10. Las restricciones relacionales no sustituyen la revisión de autoridad/calidad de la evidencia.

## 9. Reglas de no inferencia

Está prohibido:
- convertir `platform_id` en `network_key`;
- inferir una red por igualdad entre `platform_id`, `name`, `shortname` o un slug de otro proveedor;
- convertir NULL de `chain_identifier` en un valor calculado;
- asumir que `native_coin_id` identifica inequívocamente una red;
- aceptar una red EVM solo por Chain ID;
- crear un Chain ID para Solana u otra familia que no lo utilice;
- resolver una dirección contractual sin red canónica confirmada;
- trasladar mappings de un proveedor a otro sin evidencia y revisión independientes.

## 10. Criterios de aceptación de esta política

- [ ] Se documenta la separación entre identidad canónica, identificadores de red y plataformas de proveedor.
- [ ] Se define el tratamiento de los campos CoinGecko y de valores NULL.
- [ ] Se especifican procedimientos de corroboración para EVM y Solana.
- [ ] Se definen estados, evidencia, trazabilidad y publicación transaccional.
- [ ] El modelo lógico y físico incluyen el registro de plataformas y las revisiones de correspondencia.
- [ ] No se han insertado redes, plataformas ni mappings reales.
- [ ] No se han creado migraciones ni se afirma validación del motor PostgreSQL.

## 11. Fuentes técnicas

- CoinGecko, **Asset Platforms List (ID Map)**: https://docs.coingecko.com/reference/asset-platforms-list
- Ethereum Improvement Proposals, **EIP-155: Simple replay attack protection**: https://github.com/ethereum/EIPs/blob/master/EIPS/eip-155.md
- Solana Documentation, **getGenesisHash**: https://solana.com/docs/rpc/http/getgenesishash

Las fuentes describen campos o mecanismos técnicos; no reemplazan la evaluación de evidencia de cada plataforma/red concreta.

## 12. Estado de implementación

Esta entrega cierra el procedimiento documental, no el catálogo. No se han consultado ni guardado filas reales del endpoint, no se han creado registros en `networks`, `network_identifiers` o `provider_platforms`, no se han aceptado correspondencias, no se han creado migraciones SQL y no se ha ejecutado PostgreSQL real.
