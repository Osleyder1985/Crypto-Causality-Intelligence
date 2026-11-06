# Modelo de dominio para activos y representaciones blockchain

- **Estado:** propuesta técnica para revisión; no implementada.
- **Versión:** 0.2.0-draft.
- **Fecha:** 2026-11-06.
- **Alcance:** identidad de activos nativos, activos emitidos y despliegues tokenizados en redes.
- **Documentos relacionados:** asset-identity-resolution-policy.md, initial-asset-catalog.md, postgresql-physical-schema.md.

## 1. Problema que resuelve

Un ticker no identifica de forma suficiente un activo ni un despliegue blockchain. El mismo producto puede tener contratos distintos en redes diferentes; dos tokens pueden compartir ticker y tener emisores, derechos o riesgos distintos; un activo envuelto puede seguir el precio de un subyacente sin ser la misma unidad jurídica o técnica.

CCI debe separar cuatro preguntas: qué activo es, quién lo emite o respalda, dónde y cómo existe, y qué relación mantiene con otro activo. La igualdad de ticker, precio, marca o colateral no responde por sí sola a ninguna de esas preguntas.

## 2. Vocabulario y límites de identidad

### 2.1 assets: identidad del activo

Un registro de assets representa una unidad de activo definida por su identidad económica/técnica y sus características de emisión relevantes. No representa una dirección de contrato concreta ni un par de mercado.

Ejemplos conceptuales: Bitcoin nativo; WBTC como activo tokenizado distinto de Bitcoin; Tether USD como producto/activo emitido, sujeto a confirmar el alcance exacto de sus condiciones de redención y emisión; y un token homónimo emitido por otro proyecto, que sería otro activo aunque comparta ticker.

El identificador interno canonical_code es estable y no depende de ticker. Los atributos descriptivos no sustituyen identidad ni evidencia.

### 2.2 networks: identidad de red

Una red es un dominio técnico de ejecución/consenso, no un activo. Debe identificarse mediante una clave CCI y conservar identificadores externos dentro de su namespace.

- network_key: clave interna estable, por ejemplo bitcoin_mainnet o ethereum_mainnet, cuando se haya verificado.
- network_identifiers: identificadores externos tipados y con namespace, por ejemplo un chain ID EVM.
- Un chain ID no se considera universal sin indicar el namespace/familia que lo define.
- No inferir que dos redes son iguales por nombre, ticker de moneda nativa o coincidencia de chain ID sin contexto.

### 2.3 asset_representations: existencia del activo en una red

Una representación indica cómo se materializa o referencia un activo en una red concreta:

- native: unidad nativa de la red; no tiene contrato.
- token_contract: token fungible desplegado en una red; requiere dirección/identificador de contrato.
- other: solo para casos documentados que no encajen en las dos categorías anteriores.

La identidad de una representación se determina como mínimo por network_id + representation_kind + contract_address cuando sea contractual. Para una unidad nativa, la identidad se determina por network_id + native_asset_key; no se fuerza una dirección de contrato ficticia.

La dirección original se conserva literalmente. La normalización para comparación depende del formato y de la red; no se aplica una normalización EVM a direcciones de otras familias. Una representación contractual no se crea si faltan red o contrato verificables. El ticker y el nombre no son sustitutos.

### 2.4 asset_relationships: relaciones entre activos distintos

Las relaciones se registran explícitamente, con tipo, dirección, evidencia y vigencia. Tipos iniciales propuestos:

- wrapped_representation_of: un activo envuelto representa o pretende seguir un subyacente.
- bridged_representation_of: representación emitida/movida mediante un mecanismo bridge.
- redeemable_for: existe un derecho o mecanismo documentado de redención hacia otro activo.
- backed_by: relación de respaldo/colateral, sin afirmar identidad.
- tracks_price_of: exposición o seguimiento de precio, sin afirmar equivalencia.
- migrated_to: migración/sustitución documentada de un activo por otro.

No todos los tipos son transitivos. Ninguna relación implica automáticamente fungibilidad, equivalencia jurídica, paridad permanente ni intercambiabilidad. Cada relación debe declarar fuente, evidencia, dirección y periodo cuando puedan establecerse.

## 3. Modelo relacional propuesto

| Entidad | Responsabilidad | Clave/relación principal |
|---|---|---|
| assets | Identidad del activo económico/técnico | id, canonical_code |
| networks | Red blockchain | id, network_key |
| network_identifiers | Chain IDs y alias de red con namespace | FK network_id |
| asset_representations | Unidad nativa o despliegue contractual de un activo en una red | FK asset_id, network_id |
| asset_relationships | Relación tipada entre dos activos distintos | FKs subject_asset_id, object_asset_id |
| asset_identity_resolution_reviews | Decisiones auditables sobre códigos externos | Puede proponer activo o representación |
| asset_identifiers | Identificadores externos aceptados a nivel de activo | FK asset_id |
| asset_representation_identifiers | Identificadores externos aceptados de una representación | FK asset_representation_id |

Cardinalidades:

- Un activo puede tener cero o muchas representaciones.
- Una red puede alojar muchas representaciones.
- Una representación pertenece exactamente a un activo y a una red.
- Una representación nativa no tiene contrato; una representación token_contract debe tener contrato.
- Un activo puede relacionarse con muchos activos mediante relaciones tipadas.
- Una relación conecta dos activos distintos; no se permiten autorrelaciones salvo que un tipo futuro lo justifique expresamente.
- Los instrumentos de mercado referencian assets para base y quote. La metadata de proveedor conserva el código nativo y el scope de representación cuando la fuente lo publique.

## 4. Invariantes obligatorios

1. Un activo subyacente y su wrapper/bridge son registros assets distintos.
2. Dos contratos diferentes no se colapsan por compartir ticker, marca o símbolo.
3. El mismo activo puede tener varias representaciones de red sin duplicar necesariamente su identidad de activo.
4. Una representación contractual requiere red, dirección/identificador de contrato y evidencia de procedencia.
5. Una representación nativa no tiene dirección de contrato.
6. Las claves de red externas siempre están namespaced; no se asume que un chain ID aislado sea globalmente único.
7. Una relación entre activos no crea un alias de identidad ni propaga FKs automáticamente.
8. El mapping a nivel de activo y el mapping a nivel de representación son scopes diferentes y no se sustituyen.
9. Los cambios de contrato, migraciones y cambios de red se versionan; no se sobrescribe la representación histórica.
10. La incertidumbre permanece explícita. Si la evidencia no determina activo, red o contrato, la FK correspondiente queda NULL.
11. Las decisiones y relaciones deben soportar validez temporal y conocimiento bitemporal.
12. Ninguna entidad o relación de este modelo autoriza por sí misma adquisición, almacenamiento o redistribución de datos.

## 5. Ejemplos conceptuales (no mappings aprobados)

### Bitcoin nativo y WBTC

- Bitcoin es un activo.
- Su unidad nativa en Bitcoin Mainnet es una representación native, sin contrato.
- Wrapped Bitcoin (WBTC) es otro activo.
- Su despliegue en Ethereum es una representación token_contract con contrato documentado.
- Puede existir una relación wrapped_representation_of desde WBTC hacia Bitcoin si la evidencia oficial vigente demuestra esa semántica.
- No se fusionan sus instrumentos, precios, riesgos, liquidez ni series OHLCV.

### Tether USD en varias redes

- Se modela el producto/activo de emisión solo en el alcance que la documentación oficial del emisor permita afirmar.
- Cada despliegue en una red tiene una fila distinta de asset_representations, con contrato propio.
- No se inventan direcciones ni se asume que cualquier token con ticker USDT sea una emisión oficial de Tether.
- Si la documentación demuestra diferencias materiales de derechos, emisor, redención o naturaleza de la emisión, deben existir activos separados vinculados mediante relaciones tipadas, en vez de forzar una identidad común.

### Tickers reutilizados

Dos tokens llamados ABC en redes o contratos distintos permanecen separados hasta verificar emisor, contrato, red y documentación. La coincidencia del símbolo no crea relación ni identidad.

## 6. Resolución de identificadores

La resolución se divide en dos ámbitos:

- Identificador de activo: código de proveedor que representa un activo sin identificar un despliegue contractual concreto. Se resuelve contra assets.
- Identificador de representación: dirección de contrato, identificador de despliegue o código cuyo significado depende de una red concreta. Se resuelve contra asset_representations.

Las revisiones deben indicar el ámbito objetivo y nunca aceptar simultáneamente dos destinos. La resolución contractual requiere red exacta y contrato exacto. Los mappings de asset_identifiers no se heredan a asset_representation_identifiers, ni a la inversa.

Las consultas históricas conservan valid_at y known_at. Un cambio de contrato o una corrección retrospectiva crea una nueva revisión y una nueva vigencia; no reescribe la historia conocida anteriormente.

## 7. Decisiones aplazadas

- Catálogo inicial de redes y namespaces de chain IDs.
- Política de checksum/case sensitivity por familia de direcciones.
- Modelo de emisores, custodios, bridges y mecanismos de redención como entidades de primera clase.
- Tratamiento de tokens rebasables, shares de vault, LP tokens, NFT y activos sintéticos.
- Reglas de integridad temporal en PostgreSQL y estrategia de exclusión de solapamientos.
- Criterios para decidir cuándo despliegues del mismo emisor/producto deben separarse en activos distintos.

Estas decisiones no bloquean el modelo conceptual inicial, pero sí deben cerrarse antes de DDL y mappings productivos.

## 8. Estado de validación

- Diseño conceptual: propuesto.
- Validador estructural Python: implementado en `scripts/validation/asset_representation_contracts.py`; valida tipos de entrada, claves no vacías, observación temporal con zona horaria, metadatos físicos opcionales y relaciones normalizadas. No normaliza direcciones ni genera `recorded_at`.
- Fixture sintético: `tests/fixtures/asset_identity/asset_representations.json`; los contratos son placeholders deliberadamente inválidos y no representan despliegues reales.
- Pruebas automatizadas: la suite contiene 58 métodos `test_*` tras ampliar los casos de regresión de identidad. La cobertura añadida incluye entradas malformadas, tipos inválidos, `observed_at`, `directionality`, preservación de metadatos y salida relacional normalizada.
- Alcance probado en código de tests: cardinalidad multi-chain, representación nativa sin contrato, token contractual con contrato obligatorio, duplicados por red, activos distintos con ticker coincidente, relaciones dirigidas, referencias huérfanas, validez temporal, validación de estructuras y tipos, observaciones y preservación de metadatos. La ejecución de CI de esta revisión está pendiente.
- Normalización/checksum de direcciones: no implementada; se preserva el literal y se aplaza la regla específica por familia de red.
- Mappings reales de contratos: ninguno aprobado por este documento.
- Validación empírica con redes o APIs: no realizada en esta etapa.
- DDL/migraciones PostgreSQL: no implementadas.
- CI de la revisión anterior: aprobada en el run [#42275359843](https://github.com/Osleyder1985/Crypto-Causality-Intelligence/actions/runs/42275359843), con 48/48 pruebas. Esa ejecución no valida los cambios posteriores de este borrador.
