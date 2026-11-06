# Catálogo inicial de activos y protocolo de aprobación

- **Estado:** propuesta técnica para revisión; ningún mapping externo queda aprobado por este documento.
- **Versión:** 0.1.0-draft.
- **Fecha:** 2026-11-06.
- **Alcance:** preparación del catálogo para Binance Spot y Kraken Spot.
- **Documentos rectores:** `asset-identity-resolution-policy.md` y `asset-representation-domain-model.md`.
- **PR:** #15.

## 1. Objetivo

Establecer un conjunto inicial, pequeño y auditable de activos canónicos y de identificadores nativos observados en los contratos y fixtures actuales. La matriz separa:

1. La entidad que CCI pretende representar (`canonical_code`).
2. El código literal publicado por un proveedor.
3. La hipótesis de correspondencia que debe revisar una persona/proceso autorizado.
4. La evidencia necesaria para aceptar, rechazar o mantener ambigua esa correspondencia.

La inclusión de una fila no constituye una declaración de equivalencia ni autoriza la persistencia de datos de proveedor.

## 2. Catálogo canónico propuesto

Los códigos siguientes son claves internas estables propuestas. No son tickers ni identificadores externos.

| canonical_code | display_name | asset_type | Definición de dominio | Estado del registro |
|---|---|---|---|---|
| `bitcoin` | Bitcoin | `crypto` | Activo nativo Bitcoin; no representa automáticamente wrapped/bridged BTC. | Propuesto |
| `usd` | US dollar | `fiat` | Unidad monetaria USD; no confundir con saldo, token o representación digital emitida por terceros. | Propuesto |
| `tether_usd` | Tether USD | `stablecoin` | Familia de activo referida a USD; la red y el contrato identifican representaciones tokenizadas específicas. | Propuesto |

No se crea todavía un registro canónico para cada ticker nuevo. Ethereum y otros activos se incorporarán cuando el inventario de instrumentos y la evidencia de metadata de los proveedores definan el alcance inicial con precisión.

## 3. Matriz inicial de identificadores externos

**Todos los casos comienzan en `pending_review` o `unresolved`. Ninguno se debe cargar como `accepted` por el mero hecho de aparecer en esta tabla.**

| canonical_code candidato | Namespace exacto | Código nativo | Scope de red/contrato | Estado inicial | Evidencia requerida |
|---|---|---|---|---|---|
| `bitcoin` | `binance_spot` | `BTC` | No especificado por el campo de activo de `exchangeInfo`; no inventar red. | `pending_review` | Documentación oficial del endpoint y respuesta de metadata conservada de forma permitida que defina la semántica de `baseAsset`. |
| `bitcoin` | `kraken_spot_assets` | `XBT` | Namespace de activos Kraken; red/contrato no inferidos. | `pending_review` | Documentación oficial de códigos de activos Kraken y evidencia oficial del endpoint que publica el código. |
| `bitcoin` | `kraken_spot_assetpairs` | `XXBT` | Campo `base` de AssetPairs; no confundir con `altname` o `wsname`. | `pending_review` | Documentación oficial de AssetPairs y confirmación de que `base` referencia el activo Kraken XBT. |
| `tether_usd` | `binance_spot` | `USDT` | La metadata Spot de símbolo no determina por sí sola una red/contrato. | `pending_review` | Documentación oficial de Binance para la semántica de `baseAsset`/`quoteAsset`; evidencia del alcance del activo listado en Spot. No asumir una red. |
| `usd` | `kraken_spot_assetpairs` | `ZUSD` | Campo `quote` de AssetPairs; código nativo Kraken. | `pending_review` | Documentación oficial de Kraken para códigos de activos y confirmación de la semántica de ZUSD como unidad USD en este endpoint. |

### 3.1 Interpretación y límites

- Las filas BTC, XBT y XXBT son **hipótesis de alias de proveedor para revisión**, no tres activos canónicos distintos ni una equivalencia ya demostrada.
- USDT no se fusiona con USD: el primero es una stablecoin emitida; el segundo es una unidad fiat.
- ZUSD no se equipara con cualquier representación tokenizada de USD.
- Un campo de par como `BTCUSDT`, `XBTUSD` o una clave concatenada no se descompone por heurística para crear identidades de activos.
- Si la evidencia no permite determinar la entidad exacta o el scope, el resultado permanece sin resolver.
- No se añaden redes o contratos a partir de convenciones, conocimiento informal o nombres de mercado.

## 4. Protocolo de aprobación

Cada decisión debe registrar, como mínimo:

| Campo de evidencia | Requisito |
|---|---|
| `namespace` | Identificador exacto del producto/interfaz que publica el código. |
| `external_identifier` | Código literal, respetando mayúsculas, prefijos y formato. |
| `network` / contrato | Valor exacto cuando la fuente lo publique o cuando sea necesario para distinguir representaciones; NULL si no está establecido. |
| `canonical_code` candidato | Clave interna propuesta; no se deriva del ticker. |
| Fuente documental | URL oficial, título/sección y versión o fecha de consulta. |
| Evidencia de proveedor | Endpoint/campo y referencia a una observación verificable; no incluir secretos ni credenciales. |
| `observed_at` | Instante en que se observó el dato o documento. |
| `reviewed_at` | Instante de la decisión. |
| Decisión | `accepted`, `rejected`, `ambiguous` o `pending_review`. |
| Alcance de vigencia | `valid_from` y `valid_until`, si se puede establecer. |
| Responsable/proceso | Referencia de revisión auditable, sin almacenar credenciales personales. |
| Justificación | Por qué la evidencia prueba (o no) identidad en ese namespace y scope. |

### 4.1 Criterios para aceptar

Se permite `accepted` solo si se cumplen todos:

1. La fuente es oficial y define el significado del identificador dentro del namespace correspondiente.
2. La evidencia identifica inequívocamente el activo o la representación concreta.
3. La red, contrato, emisor o naturaleza fiat/cripto se han delimitado cuando son relevantes.
4. No existe evidencia contradictoria ni otro candidato igualmente válido.
5. La decisión especifica el periodo de vigencia o explica por qué la fuente no permite determinarlo.
6. La referencia documental y la evidencia de observación son reproducibles y quedan registradas.
7. La decisión se conserva de forma append-only y puede ser auditada.

La evidencia de que dos códigos se usan para el mismo mercado o que sus nombres se parecen no es suficiente.

### 4.2 Criterios para otros estados

- `pending_review`: hay una hipótesis que requiere más evidencia.
- `unresolved`: no hay candidato defendible.
- `ambiguous`: existen múltiples interpretaciones posibles o fuentes contradictorias.
- `rejected`: la evidencia descarta la correspondencia propuesta.
- Un mapping rechazado no debe reutilizarse automáticamente. Una nueva propuesta requiere evidencia y decisión nuevas.

## 5. Flujo operativo de revisión

1. Capturar el código literal y su namespace desde metadata de proveedor obtenida de forma autorizada.
2. Registrar endpoint, campo de origen, instante y hash/referencia de evidencia cuando la retención esté permitida.
3. Crear o localizar el activo canónico candidato sin propagar todavía la FK.
4. Verificar documentación oficial del proveedor y, cuando proceda, estándar oficial o documentación del emisor.
5. Evaluar si la evidencia define identidad, no solo equivalencia económica, paridad o exposición de precio.
6. Registrar decisión, alcance temporal y justificación.
7. Publicar el mapping únicamente cuando la decisión sea `accepted` y cumpla todas las restricciones.
8. Ejecutar pruebas de namespace exacto, scope de red, ausencia de conflictos y no solapamiento temporal.
9. Conservar el historial de decisiones; las correcciones se representan como nuevas filas.

## 6. Reglas de persistencia y seguridad

- Este catálogo documental no concede autorización para almacenar payloads de Binance, Kraken, CoinGecko ni terceros.
- La política de uso del endpoint, finalidad, retención y redistribución se evalúa separadamente de la identidad del activo.
- Si el permiso de almacenamiento es `restricted`, `denied`, `unknown` o `pending_confirmation`, no persistir el payload ni su copia; conservar solo referencias/metadatos mínimos cuando la política lo permita.
- Los fixtures de pruebas deben ser sintéticos y claramente identificados.
- No incorporar credenciales, claves API, datos privados ni respuestas de proveedor al repositorio público.
- No usar este catálogo como fuente de verdad para operaciones de trading ni como lista de instrumentos habilitados.

## 7. Criterios de aceptación de esta etapa

- [ ] El catálogo canónico tiene claves internas estables y tipos explícitos.
- [ ] Cada identificador externo incluye namespace exacto.
- [ ] Las hipótesis no aprobadas permanecen en `pending_review`.
- [ ] No hay equivalencias aprobadas sin evidencia oficial y decisión auditable.
- [ ] USDT y USD permanecen como entidades conceptualmente distintas.
- [ ] Las representaciones tokenizadas requieren red/contrato cuando corresponda.
- [ ] La política de uso de datos se evalúa independientemente de la identidad.
- [ ] La implementación futura prueba que solo mappings aceptados y vigentes generan FKs canónicas.

## 8. Integración con el modelo de representaciones

La separación entre activo y despliegue se define en `docs/architecture/asset-representation-domain-model.md` y se refleja como propuesta en `postgresql-physical-schema.md`.

- Bitcoin nativo requiere una representación `native` en una red verificada; no requiere contrato.
- WBTC, si se incorpora, será un activo distinto de Bitcoin y su despliegue contractual será una representación de ese activo.
- Los despliegues de USDT en redes distintas requieren representaciones separadas con contratos documentados. No se añaden direcciones por conocimiento informal ni se considera que cualquier token USDT sea oficial.
- Los cinco identificadores externos de esta matriz siguen en `pending_review`; el nuevo modelo no los aprueba ni modifica su estado.
- Ninguna relación `wrapped`, `bridged`, `backed_by` o `tracks_price_of` autoriza a fusionar activos o series de mercado.

## 9. Próximas decisiones técnicas

Antes de DDL definitivo:

1. Confirmar si `asset_identifiers` debe incluir `network`, `contract_address`, `issuer` y/o `representation_type` como columnas normalizadas, o si parte de esos atributos pertenece a entidades separadas.
2. Definir el tratamiento de activos nativos frente a tokens envueltos, bridged y emitidos en múltiples redes.
3. Definir la semántica temporal exacta de las decisiones y mappings: fecha de observación, periodo de validez y precedencia de revisiones.
4. Convertir esta matriz en fixture estructurado y añadir validaciones automatizadas antes de crear migraciones PostgreSQL.

Hasta cerrar estas decisiones, no generar DDL definitivo ni cargar mappings aprobados.
