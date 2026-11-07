# Contrato congelado: identidad de plataformas de proveedores

- **Identificador:** CCI-NET-PLATFORM-CONTRACT
- **Versión:** 1.0
- **Estado:** contrato funcional congelado para el subsistema reducido; integración productiva pendiente.
- **Fecha:** 2026-11-06.
- **Issue / PR:** #14 / #16.
- **Especificación normativa:** `postgresql-physical-schema.md`, secciones 10 y 13.
- **Plan y evidencia de validación:** `postgresql-lab-validation-plan.md`.

## 1. Propósito del congelamiento

Fijar el contrato funcional y temporal del subsistema de identidad de plataformas de proveedores antes de integrarlo en el esquema productivo `cci`. El congelamiento evita que la adaptación de nombres, dependencias, roles o grants altere silenciosamente la semántica ya revisada.

Este documento **no** declara congelado el esquema PostgreSQL completo de 34 entidades, no autoriza migraciones productivas y no convierte el DDL del laboratorio en DDL de producción.

## 2. Alcance exacto

El laboratorio utiliza seis tablas:

1. `data_sources`: fixture mínimo de proveedores.
2. `networks`: fixture mínimo de redes.
3. `provider_platforms`: identidad estable por proveedor y clave externa.
4. `provider_platform_observations`: snapshots inmutables de metadata.
5. `provider_platform_resolution_reviews`: decisiones append-only y cadena de sucesión.
6. `network_identifiers`: identificadores de red, incluidos mappings de plataformas aceptados.

En producción, `data_sources` y `networks` se integrarán con sus definiciones canónicas del esquema `cci`; no se duplicarán ni se crearán catálogos paralelos. Las cuatro tablas del subsistema conservarán sus relaciones y restricciones, adaptadas a las claves y convenciones físicas definitivas del esquema completo.

## 3. Contrato funcional congelado

### 3.1 Identidad y observaciones

- Una plataforma se identifica por `(data_source_id, provider_platform_key)`; el mismo literal en dos proveedores representa identidades distintas.
- La identidad estable no contiene metadata mutable.
- Cada snapshot se identifica por `(provider_platform_id, capture_id)`; `observed_at` no es una clave única.
- `observed_at` representa el tiempo de la observación y `recorded_at` el tiempo de incorporación a CCI.
- `reported_chain_identifier_json` acepta únicamente JSON `number` o `null`; no fuerza entero en la observación.
- Observaciones y decisiones son inmutables para los roles ordinarios de aplicación. Las correcciones se registran mediante nuevas filas.

### 3.2 Resolución y temporalidad

- Estados admitidos: `pending_review`, `accepted`, `rejected`, `ambiguous`.
- Toda revisión declara `valid_from`; `valid_until`, si existe, debe ser posterior.
- La vigencia es semiabierta: `[valid_from, valid_until)`.
- `recorded_at` permite reconstruir lo conocido en `known_at`; `valid_from/valid_until` permite consultar validez en `valid_at`.
- La cadena de revisiones es append-only, de una sola raíz y sin bifurcaciones. Una sucesora representa una corrección, revocación o sustitución de decisión; nunca una nueva observación.
- Una nueva observación no revoca por sí misma una resolución.
- Solo una revisión `accepted` vigente y cabeza de cadena puede habilitar un mapping.

### 3.3 Publicación de mappings

- Un mapping de plataforma conserva proveedor, identidad de plataforma, revisión accepted, red, namespace, tipo y literal exacto.
- `identifier_value` debe coincidir con `provider_platform_key`.
- `namespace` debe ser `source_key || ':asset_platform_id'`.
- `identifier_type` y el estado de procedencia deben ser `asset_platform_id` y `accepted`.
- La FK compuesta obliga a que la red del mapping coincida con la red candidata de la revisión accepted.
- La revisión accepted y el mapping se insertan en una única transacción; cualquier fallo revierte ambos.
- El protocolo de escritura bloquea la fila de identidad en una sentencia `SELECT ... FOR UPDATE` independiente antes de leer la cabeza e insertar. El lock interno de un trigger no sustituye este protocolo bajo `READ COMMITTED`.

## 4. Objetos SQL que forman parte del contrato

La implementación integrada debe preservar, con nombres adaptados solo mediante una decisión documentada:

- Claves candidatas compuestas de plataforma, observación y revisión.
- FKs compuestas que mantienen consistencia entre plataforma, fuente, observación, revisión y red.
- CHECKs de estados, intervalos, JSONB y procedencia completa.
- Índices UNIQUE parciales para raíz, sucesora y mapping asociado a una revisión.
- Triggers de inmutabilidad y validación de cabeza/literal/namespace.
- Vista de resolución efectiva y vista de mappings publicables.
- Consulta bitemporal parametrizada por `valid_at` y `known_at` en la capa de repositorio.
- Publicación atómica con lock explícito y rollback.

La especificación exacta de columnas, constraints, índices, triggers y vistas permanece en las secciones 10 y 13 del diseño físico; este documento fija los invariantes que la integración no puede cambiar.

## 5. Baseline de laboratorio y evidencia

- **DDL de referencia:** `tests/postgresql/001_provider_platform_lab.sql`.
- **Git blob SHA del DDL consultado al congelar:** `802b6428b049a8e576f9c3e41f6c7e3f2a31b71a`.
- **Pruebas:** `tests/test_postgresql_lab.py`.
- **Workflow:** `.github/workflows/postgresql-lab.yml`.
- **Evidencia confirmatoria:** [Run #38](https://github.com/Osleyder1985/Crypto-Causality-Intelligence/actions/runs/42293769631), evento `pull_request`, PostgreSQL 16.15, 29/29 pruebas aprobadas.
- **HEAD de código probado:** `55ba44449a1016e7902e90271801ef8ee3f05fa2`.

El laboratorio usa el esquema desechable `cci_lab` y fixtures sintéticos. La evidencia no acredita la migración del esquema completo ni permisos productivos.

## 6. Condiciones para modificar el contrato

Toda modificación posterior debe:

1. identificar el invariante afectado y justificar el cambio;
2. actualizar conjuntamente el modelo lógico, la especificación física, el DDL de laboratorio y las pruebas;
3. añadir o adaptar pruebas PostgreSQL reales, incluidas pruebas concurrentes cuando afecte a la serialización;
4. documentar compatibilidad y estrategia de transición antes de cambiar el contrato productivo;
5. registrar la nueva versión del contrato y la evidencia CI.

No se permiten cambios semánticos implícitos durante la integración en `cci`.

## 7. Seguridad PostgreSQL asociada

La propuesta de roles y grants se desarrolla en `postgresql-security-roles-and-grants.md` v0.1. Establece roles de grupo `NOLOGIN`, separación entre `cci_owner` y `cci_api_owner`, interfaces `SECURITY DEFINER` acotadas para revisión/publicación, denegación por defecto y pruebas SEC-01–SEC-16. Es una propuesta documental: no se han creado roles, funciones ni grants.

## 8. Trabajo todavía necesario antes de producción

1. Integrar las cuatro tablas propias del subsistema con las definiciones canónicas de `data_sources` y `networks` en `cci`.
2. Definir roles separados para migración/propietario, ingestión y revisión/publicación; conceder solo los permisos mínimos. Los roles de aplicación no tendrán `UPDATE` ni `DELETE` sobre observaciones y revisiones.
3. Definir propiedad de objetos, `search_path` seguro y grants explícitos para secuencias/funciones/vistas cuando correspondan.
4. Implementar el protocolo transaccional en la capa de repositorio y prohibir caminos de escritura que omitan el lock previo.
5. Añadir la regresión concurrente de publicación obsoleta: un escritor espera el lock mientras otra transacción registra una sucesora; tras adquirirlo, el escritor debe releer la cabeza y rechazar la publicación antigua.
6. Integrar las 34 entidades y ejecutar migración desde una base vacía en PostgreSQL real con datos sintéticos.
7. Verificar constraints, FKs, grants, vistas, consultas bitemporales, rollback y concurrencia en el esquema integrado.

## 9. Exclusiones explícitas

- No es una migración SQL.
- No debe ejecutarse en una base persistente.
- No autoriza insertar plataformas, redes ni mappings reales.
- No valida las 34 entidades del esquema completo.
- No sustituye la revisión de políticas/licencias de proveedores.
- No autoriza fusionar el PR #16, que permanece Draft.
