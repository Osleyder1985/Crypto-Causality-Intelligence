# Auditoría de claves candidatas para FKs compuestas — Issue #25

- Fuente revisada: `postgresql-physical-schema.md` v0.8, incluidas §4 y §13.
- Matriz relacionada: `postgresql-fk-normalized-matrix.md`.
- Estado: revisión documental y contraste parcial contra PostgreSQL global; diez de las doce claves compuestas destino ya están materializadas en migraciones 002, 003, 005 y 006. No equivale a validar el esquema completo.
- Resultado: 12 claves compuestas destino identificadas para las FKs compuestas normalizadas.

## 1. Claves compuestas destino

| ID | Tabla destino | Columnas UNIQUE requeridas (orden) | FKs consumidoras | Evidencia del contrato | Estado documental |
|---|---|---|---|---|---|
| UK-01 | data_endpoints | (id, data_source_id) | FK-003, FK-039, FK-045 | §4.1 declara UNIQUE candidato (id, data_source_id). | Materializada y probada en migración 002. |
| UK-02 | source_usage_policies | (id, data_source_id) | FK-004 | §4.1 declara UNIQUE (id, data_source_id). | Materializada y probada en migración 002. |
| UK-03 | policy_evaluations | (id, data_source_id, data_endpoint_id, data_type, intended_use) | FK-048 | §4.1 declara UNIQUE con las cinco columnas para dataset_sources. | Materializada en migración 002; pendiente test consumidor FK-048. |
| UK-04 | provider_platforms | (id, data_source_id) | FK-008, FK-011, FK-012 | §13.1 nombra provider_platforms_uq_id_source. | Materializada y probada en migración 003. |
| UK-05 | provider_platform_observations | (id, provider_platform_id, data_source_id) | FK-013 | §13.1 nombra provider_platform_observations_uq_id_platform_source. | Materializada y probada en migración 003. |
| UK-06 | provider_platform_resolution_reviews | (id, provider_platform_id) | FK-015 | §13.1 nombra provider_platform_resolution_reviews_uq_id_platform. | Materializada y probada en migración 003. |
| UK-07 | provider_platform_resolution_reviews | (id, provider_platform_id, candidate_network_id, resolution_status) | FK-009 | §13.1 nombra provider_platform_resolution_reviews_uq_mapping. | Materializada y probada en migración 003. |
| UK-08 | asset_representations | (id, network_id) | FK-028 | §4.2 declara UNIQUE candidato en asset_representations(id, network_id). | Materializada y probada en migración 005. |
| UK-09 | asset_identity_resolution_reviews | (id, candidate_asset_id, resolution_status, namespace, external_identifier) | FK-027 | §4.2 declara UNIQUE candidato para asset_identifiers. | Materializada y probada en migración 006. |
| UK-10 | asset_identity_resolution_reviews | (id, candidate_asset_representation_id, resolution_status, namespace, external_identifier, network_id) | FK-029 | §4.2 declara UNIQUE candidato para asset_representation_identifiers. | Materializada y probada en migración 006. |
| UK-11 | market_instruments | (id, data_source_id) | FK-040, FK-046 | §4.2 declara UNIQUE candidato (id, data_source_id). | Candidata; requiere DDL. |
| UK-12 | ingestion_requests | (id, data_source_id, data_endpoint_id) | FK-047 | §4.3 declara UNIQUE candidato para referencias de procedencia. | Candidata; requiere DDL. |

## 2. Comprobación de orden y tipos

La matriz FK conserva el mismo orden de columnas en origen y destino. En el contrato v0.8, las columnas de estas claves compuestas son UUID para identificadores y TEXT para estados/códigos/identificadores externos; no se ha identificado una diferencia de tipo declarada entre los pares origen-destino.

Esto es una comprobación documental de nombres y tipos declarados, no una introspección de PostgreSQL. El DDL debe confirmar:
- igualdad de tipos, dominios y collation aplicable;
- orden exacto de columnas;
- existencia de PRIMARY KEY o UNIQUE no parcial que cubra exactamente las columnas destino;
- ausencia de columnas extra o reordenadas;
- nombres de constraint estables y no duplicados.

## 3. Claves adicionales del subsistema de plataformas

§13.1 también define claves UNIQUE que no son destino directo de una de las 60 FKs listadas, pero sostienen la identidad del subsistema:

- `provider_platforms(id, data_source_id, provider_platform_key)`;
- `provider_platform_observations(id, provider_platform_id)`;
- `provider_platform_observations(provider_platform_id, capture_id)`;
- índices UNIQUE parciales de raíz y sucesora para la cadena de revisiones;
- `network_identifiers(provider_platform_resolution_review_id)` parcial para impedir más de un mapping por revisión.

No deben confundirse con las 12 claves compuestas destino de esta auditoría.

## 4. Autorreferencias

- FK-015 (`provider_platform_resolution_reviews.supersedes_review_id, provider_platform_id`) consume UK-06 y exige que la sucesora pertenezca a la misma plataforma. La sección 13 añade índices parciales de raíz/sucesora y un trigger de cabeza actual.
- FK-024 (`asset_identity_resolution_reviews.supersedes_review_id`) referencia solo la PK `id`; no requiere una UNIQUE compuesta adicional. La coherencia de la misma clave de identidad, cadena lineal y ausencia de ciclos debe imponerse mediante función/trigger transaccional.

## 5. Hallazgos y gates

1. La clave destino de FK-009 tiene **cuatro columnas**: `(id, provider_platform_id, candidate_network_id, resolution_status)`. Se corrigió en la especificación física la frase aislada que decía “cinco columnas”.
2. Las claves UK-11 y UK-12 se expresan como candidatas o necesarias y aún no tienen materialización global.
3. Las claves de proveedor UK-04 a UK-07 ya están materializadas y probadas en `cci`; el laboratorio `cci_lab` sigue siendo evidencia separada.
4. Las FKs que referencian claves con componentes nullable (UK-09/UK-10 y FK-009) deben probar inserciones accepted y estados no accepted; la FK compuesta debe impedir mappings a destinos nulos o estados distintos de accepted.
5. Ninguna de estas comprobaciones valida por sí sola los triggers de cadena, inmutabilidad, concurrencia o publicación atómica.

## 6. Dictamen

Las 12 claves compuestas destino necesarias están identificadas. Diez ya se materializan en el esquema global `cci`: UK-01 a UK-07 en migraciones 002–003, UK-08 en 005 y UK-09/UK-10 en 006. Las dos restantes (UK-11 y UK-12) continúan pendientes de DDL global. Las pruebas de migración verifican instalación y parte de la integridad compuesta, pero el gate permanece abierto hasta materializar y probar todas las claves, las FKs consumidoras y sus casos negativos desde base vacía.
