# Política de resolución de identidad de activos

- **Estado:** propuesta técnica para revisión.
- **Versión:** 0.1.0-draft.
- **Fecha:** 2026-11-06.
- **Documentos relacionados:** `canonical-market-data-schemas.md`, `postgresql-physical-schema.md`, `provider-instrument-schema-cross-review.md` y `asset-representation-domain-model.md`.
- **PR:** #15.

## 1. Objetivo

Definir cuándo un código nativo de proveedor puede asociarse a un activo canónico del catálogo CCI. La política evita crear equivalencias por similitud textual, ticker, prefijo, nombre comercial o intuición.

La resolución de un activo no es la resolución de un instrumento. `BTCUSDT`, `XBT/USD` y una clave interna de Kraken identifican instrumentos o interfaces de mercado; no son identificadores de un activo individual.

## 2. Principios obligatorios

1. **Namespace obligatorio:** un código solo se interpreta dentro del proveedor, producto, endpoint o sistema que lo publica. Ejemplos: `binance_spot`, `kraken_spot_assets`, `kraken_spot_assetpairs`.
2. **Código nativo inmutable:** conservar exactamente el código recibido. No reemplazar `XXBT` por `BTC` en la metadata original.
3. **Sin inferencia por ticker:** igualdad o similitud de `BTC`, `XBT`, `XXBT`, `USDT` o nombres no demuestra identidad.
4. **Red explícita:** si la identidad depende de una red, contrato, emisor o representación tokenizada, esos atributos forman parte de la evidencia y del alcance de la correspondencia. Un campo `network` descriptivo no es por sí solo una clave universal.
5. **Evidencia trazable:** toda correspondencia aceptada requiere referencia verificable y una decisión registrada.
6. **Incertidumbre conservada:** si la evidencia falta, es contradictoria o no distingue activos homónimos, el vínculo canónico permanece NULL.
7. **Historial, no sobrescritura:** una corrección o cambio de criterio crea una nueva decisión/versionado; no reescribe silenciosamente la evidencia anterior.
8. **Separación de conceptos:** activo, instrumento, alias de instrumento, red y contrato/token no son entidades intercambiables.

## 3. Identificador canónico interno

- `assets.id` es la identidad técnica primaria y no depende de un ticker.
- `assets.canonical_code` debe ser un código interno estable, único y no ambiguo dentro de CCI; no se exige que coincida con el ticker de un exchange.
- Ejemplos ilustrativos de claves internas: `bitcoin`, `usd`, `tether_usd`. Son claves propuestas, no correspondencias aprobadas por sí mismas.
- Los símbolos y códigos de proveedores viven en `asset_identifiers`, siempre con namespace y red cuando corresponda.
- No se crea un activo canónico únicamente porque aparezca un nuevo ticker. Primero se verifica qué entidad económica/técnica representa.

## 4. Flujo de resolución

1. Capturar código nativo, namespace, red/contrato si la fuente los proporciona, endpoint, instante y referencia de metadata.
2. Buscar correspondencia exacta por `(namespace, network, external_identifier)`; no ejecutar fallback a otro namespace ni quitar prefijos.
3. Si existe una única correspondencia previamente aceptada y vigente, utilizarla.
4. Si no existe, registrar el identificador como pendiente de revisión; el instrumento puede crearse con `base_asset_id` y `quote_asset_id` NULL.
5. Si hay más de un candidato o evidencia contradictoria, marcar la revisión como ambigua y bloquear la asociación automática.
6. Una persona/proceso de revisión con evidencia documentada acepta o rechaza la correspondencia.
7. Solo las correspondencias aceptadas se publican en `asset_identifiers` y se propagan a `market_instruments`.
8. Al cambiar la correspondencia, preservar las observaciones previas y aplicar vigencias; no actualizar datasets históricos de forma silenciosa.

## 5. Estados de resolución

| Estado | Significado | ¿Permite FK canónica? |
|---|---|---:|
| `unresolved` | No hay correspondencia conocida | No |
| `pending_review` | Existe candidato o revisión pendiente | No |
| `ambiguous` | Más de una interpretación defendible o evidencia conflictiva | No |
| `accepted` | Correspondencia exacta aprobada con evidencia | Sí |
| `rejected` | La correspondencia propuesta fue descartada | No |

El estado `accepted` debe incluir un activo destino y una referencia de evidencia. Una revisión pendiente nunca equivale a una aceptación.

## 6. Aplicación inicial a Binance Spot y Kraken Spot

| Fuente | Código nativo | Tratamiento inicial |
|---|---|---|
| Binance Spot | `BTC` | Mantener bajo namespace Binance; sin equivalencia implícita |
| Kraken Spot Assets/AssetPairs | `XBT` | Mantener bajo namespace Kraken; sin equivalencia implícita |
| Kraken Spot AssetPairs | `XXBT` | Mantener bajo namespace Kraken; sin equivalencia implícita |
| Binance Spot | `USDT` | Mantener bajo namespace Binance; no inferir red/contrato no publicado |
| Kraken Spot | `ZUSD` | Mantener bajo namespace Kraken; no equiparar automáticamente con cualquier código USD |

Esta tabla es deliberadamente conservadora. No afirma que los códigos representen activos distintos; indica que el parser no tiene autoridad para declarar que son iguales. Una revisión documental posterior puede aprobar equivalencias si acredita la semántica del proveedor y la identidad del activo.

## 7. Reglas para casos especiales

- **Fiat:** distinguir código ISO, unidad monetaria y representación de proveedor; usar evidencia oficial del proveedor o estándar pertinente.
- **Stablecoins:** no inferir identidad a partir del ticker; verificar emisor, activo referenciado y, cuando aplique, red/contrato.
- **Wrapped/bridged assets:** el activo envuelto/bridged mantiene identidad propia; la relación con el subyacente se registra mediante `asset_relationships` y no como alias. No fusionar sus series de mercado.
- **Representaciones multi-chain:** un mismo activo puede tener varias filas `asset_representations`, una por red/despliegue verificado. Cada contrato se identifica por red + dirección literal + tipo; no asumir que contratos distintos son intercambiables sin evidencia.
- **Activos nativos:** se representan mediante `asset_representations` de tipo `native`, sin dirección de contrato.
- **Resolución de contratos:** los identificadores de despliegue se resuelven contra `asset_representations`; no se publican en `asset_identifiers` a nivel de activo.
- **Tokens con ticker reutilizado:** distinguir por emisor, contrato y red; ticker igual no es identidad.
- **Activos renombrados o migrados:** conservar identificadores históricos y periodos de vigencia; no reasignar retrospectivamente sin evidencia.
- **Pares de mercado:** resolver base y quote de forma independiente. El símbolo concatenado no debe analizarse por partición de texto para deducir ambos activos.

## 8. Criterios de aceptación y pruebas

1. `BTC`, `XBT` y `XXBT` permanecen sin resolver cuando no hay correspondencias aprobadas.
2. Una correspondencia exacta aceptada resuelve solo dentro de su namespace y red.
3. Un alias en otro namespace no hereda una resolución.
4. Un registro `pending_review` o `ambiguous` no produce FK a `assets`.
5. Dos destinos aceptados distintos para la misma clave exacta provocan error de integridad.
6. Una correspondencia aceptada sin evidencia se rechaza.
7. Los códigos nativos y la metadata de origen permanecen intactos después de resolver.
8. La identidad del instrumento no depende de que ambos activos estén resueltos.
9. Los cambios de mapeo son auditables y respetan los intervalos de vigencia.

## 9. Límites y trabajo pendiente

- La política no declara todavía equivalencias reales BTC/XBT/XXBT ni USD/ZUSD.
- No se ha validado contra respuestas API actuales en esta tarea.
- No se han creado migraciones PostgreSQL.
- La estructura de revisión/auditoría debe implementarse físicamente antes de poblar mappings aprobados.
- El modelo conceptual de redes, activos y representaciones se propone en `asset-representation-domain-model.md`; su implementación, reglas de direcciones y catálogo de redes siguen pendientes.


## 10. Catálogo inicial y aprobación

La matriz inicial y el protocolo de evidencia se mantienen en `docs/catalog/initial-asset-catalog.md`. Ese documento propone claves internas para Bitcoin, USD y Tether USD, y registra identificadores Binance/Kraken como hipótesis pendientes de revisión.

Ningún mapping listado allí se considera aprobado. La aprobación requiere evidencia oficial específica del namespace, identificación inequívoca del activo y de su scope de red/contrato cuando aplique, decisión auditable y vigencia. La inclusión en el catálogo no autoriza almacenamiento de payloads ni sustituye la evaluación de políticas de uso de datos.


## 11. Semántica temporal bitemporal de las identidades

La resolución debe distinguir dos relojes que responden preguntas diferentes:

- **Tiempo de validez (`valid time`):** cuándo el identificador representa al activo dentro del dominio del proveedor. Se almacena como intervalo semiabierto `[valid_from, valid_until)`; el límite final es exclusivo.
- **Tiempo de conocimiento (`transaction/record time`):** cuándo CCI registró una decisión y pudo utilizarla. Se representa mediante `recorded_at`, inmutable y asignado al insertar la revisión. `observed_at` conserva cuándo se observó la fuente; `reviewed_at` cuándo se tomó la decisión. Ninguno sustituye a `recorded_at`.

### 11.1 Consultas reproducibles

Toda resolución histórica debe declarar ambos instantes:

- `valid_at`: instante del dominio de mercado cuya identidad se desea resolver.
- `known_at`: instante límite de conocimiento de CCI.

Una fila solo es elegible si `valid_from <= valid_at < valid_until` (o `valid_until IS NULL`) y `recorded_at <= known_at`. Todos los timestamps deben incluir zona horaria y normalizarse a UTC.

Si `valid_from` es NULL, el comienzo de validez es desconocido: la fila no puede resolver una consulta temporal. No se interpreta como “válida desde siempre”. Si `recorded_at` falta, tampoco puede participar en una consulta bitemporal.

### 11.2 Correcciones y cambios

- Las decisiones son append-only. Una corrección inserta una nueva revisión; no modifica ni elimina la anterior.
- Para un mismo identificador exacto y scope, la revisión con mayor `recorded_at` que no supere `known_at` representa el conocimiento vigente de CCI en esa consulta. Si varias revisiones máximas simultáneas discrepan, la resolución es `ambiguous` y no genera FK.
- El periodo de validez de la nueva revisión describe el periodo de proveedor al que se aplica; no se debe alterar el pasado para reflejar una decisión posterior.
- Una revisión nueva puede corregir retroactivamente el periodo de validez. Una consulta con `known_at` anterior a su registro debe seguir devolviendo la decisión que CCI conocía entonces; una consulta con `known_at` posterior puede devolver la corrección.
- La ausencia de una revisión aplicable produce `unresolved`; una revisión pendiente o ambigua nunca genera FK canónica.

### 11.3 Invariantes

1. Intervalos semiabiertos; se permiten intervalos contiguos, no solapamientos contradictorios dentro de la misma versión de conocimiento.
2. `valid_until` debe ser estrictamente posterior a `valid_from`.
3. Los tiempos de observación, revisión y registro se conservan separadamente.
4. No se reescribe la identidad asociada a un dataset ya publicado. Una nueva interpretación se registra como una nueva versión de transformación o resultado de investigación, con linaje explícito.
5. La resolución usada por una transformación debe persistir ambos instantes (`valid_at`, `known_at`) y la referencia de revisión elegida para permitir reproducción.

