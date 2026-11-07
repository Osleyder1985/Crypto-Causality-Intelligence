# Plan de laboratorio para validación real de PostgreSQL

- **Estado:** subsistema reducido validado en PostgreSQL real (29/29 pruebas); integración productiva en `cci` pendiente.
- **Fecha de actualización:** 2026-11-06.
- **Ámbito:** validación del subsistema de identidad de plataformas y redes (NET-04/NET-05/NET-06).
- **PR:** #16 (permanece Draft).
- **Restricción:** solo datos sintéticos; no se conecta a Binance, Kraken ni CoinGecko.

## 1. Objetivo

Convertir la especificación de las secciones 10 y 13 de `postgresql-physical-schema.md` en DDL de laboratorio y comprobar sus garantías en un servidor PostgreSQL real. El laboratorio no es una migración de producción ni crea el esquema completo de 34 entidades.

## 2. Resultado de la auditoría previa

Se detectó y corrigió una inconsistencia temporal:

- Las revisiones no accepted podían tener `valid_from = NULL`.
- La vista de resolución filtra por `valid_from <= statement_timestamp()`; una revisión sin inicio de vigencia quedaría excluida y el estado `pending_review`, `ambiguous` o `rejected` no sería visible.
- Regla corregida: `valid_from TIMESTAMPTZ NOT NULL` para todas las revisiones. `valid_until`, si existe, debe ser posterior a `valid_from`.
- La regla quedó alineada en el modelo físico, el modelo lógico y el documento de revisión.

La auditoría restante del DDL deberá comprobar también las claves candidatas compuestas, la nulabilidad de los campos de procedencia, la semántica de las FKs con NULL, los locks de fila, la cadena de sucesión y la consulta bitemporal.

## 3. Disponibilidad del entorno

En el entorno interactivo de esta sesión no se encontraron `psql`, servidor `postgres`, Docker, Podman ni el driver Python `psycopg`. Por ello, la validación de motor se realizó mediante un servicio PostgreSQL efímero de GitHub Actions.

El servicio se crea para cada ejecución, recibe únicamente fixtures sintéticos y se destruye al terminar. La CI de contratos Python sigue separada de la CI de motor PostgreSQL.

## 4. Alcance del laboratorio

El primer laboratorio incluye únicamente las tablas y dependencias mínimas del subsistema:

- `data_sources` y `networks` como catálogos mínimos sintéticos.
- `provider_platforms`.
- `provider_platform_observations`.
- `provider_platform_resolution_reviews`.
- `network_identifiers`.
- Índices, FKs, CHECKs, triggers, funciones y vistas del subsistema.

El DDL reside en `tests/postgresql/` y se ejecuta dentro de una base de datos de CI aislada. No se reutilizará como migración productiva sin una revisión y decisión separadas.

## 5. Estrategia de pruebas

- Pruebas declarativas: FKs compuestas, CHECKs, UNIQUE e índices parciales.
- Pruebas de triggers: inmutabilidad, cabeza de cadena, sucesión, literales y namespace.
- Pruebas temporales: vigencia semiabierta, sucesora futura y revocación.
- Pruebas transaccionales: rollback de publicación incompleta.
- Pruebas concurrentes: dos conexiones PostgreSQL independientes, coordinadas para competir por la misma identidad.
- Pruebas JSONB: `number` y `null` válidos; otros tipos rechazados; precisión numérica comprobada.
- Prueba bitemporal: `known_at` anterior y posterior a una revisión sucesora.

Cada caso PG-NET-01 a PG-NET-25 debe tener una prueba identificable y un resultado reproducible. Las pruebas que esperan errores deben verificar el SQLSTATE o la constraint esperada, no limitarse a comprobar que ocurrió cualquier excepción.

## 6. Criterios para declarar la validación

No se marcará un caso como aprobado hasta que:
1. el DDL se haya aplicado en PostgreSQL real;
2. la operación de prueba se haya ejecutado contra ese servidor;
3. el resultado observado coincida con el resultado esperado;
4. la evidencia de CI identifique versión de PostgreSQL, commit, caso y resultado.

Una ejecución de tests Python sin conexión PostgreSQL no satisface estos criterios.

## 7. Fuera de alcance

- Migraciones productivas.
- Despliegue de infraestructura persistente.
- Inserción de plataformas, redes o mappings reales.
- Consultas a APIs de proveedores.
- Fusión del PR #16.

## 8. Primer incremento implementado y ejecutado

Artefactos versionados en la rama `architecture/issue-14-storage-resynced`:

- `tests/postgresql/001_provider_platform_lab.sql`: DDL aislado de las seis tablas mínimas, claves candidatas, FKs compuestas, CHECKs, índices, triggers y vistas.
- `tests/test_postgresql_lab.py`: suite de integración ejecutada contra PostgreSQL real.
- `.github/workflows/postgresql-lab.yml`: workflow separado con servicio efímero PostgreSQL 16 y driver psycopg fijado.

La primera ejecución fue [Run #7](https://github.com/Osleyder1985/Crypto-Causality-Intelligence/actions/runs/42291704131): PostgreSQL 16.15, 7/7 pruebas aprobadas. Ese resultado confirmó que el DDL inicial se aplicaba en el motor y que el primer subconjunto de restricciones funcionaba.

## 9. Segundo incremento: cobertura PG-NET-01–PG-NET-25

Se amplió el laboratorio y se ejecutó la matriz completa de 25 condiciones. La suite contiene **29 métodos de prueba** porque algunos requisitos requieren más de una operación o una comprobación independiente.

### Evidencia de CI

- **Ejecución base de la matriz:** [Pruebas reales de PostgreSQL — Run #21](https://github.com/Osleyder1985/Crypto-Causality-Intelligence/actions/runs/42292792250), 28/28 pruebas.
- **Ejecución confirmatoria después de la auditoría:** [Pruebas reales de PostgreSQL — Run #38](https://github.com/Osleyder1985/Crypto-Causality-Intelligence/actions/runs/42293769631).
- **Evento:** `pull_request`, PR #16.
- **HEAD probado:** `55ba44449a1016e7902e90271801ef8ee3f05fa2`.
- **Job:** `postgresql-lab`, conclusión `success`.
- **Motor:** PostgreSQL **16.15**.
- **Suite:** `python -m unittest discover -s tests -p 'test_postgresql_lab.py' -v`.
- **Resultado confirmatorio:** **29/29 pruebas aprobadas** en 1.911 segundos; incluye validación del formato SHA-256 de evidencia.
- **CI de contratos Python:** ejecución separada, también aprobada; no se contabiliza como prueba del motor.

### Cobertura de los 25 requisitos

| Requisito | Verificación ejecutada |
|---|---|
| PG-NET-01 | FK compuesta plataforma/fuente en observaciones |
| PG-NET-02 | Duplicado de `capture_id` rechazado |
| PG-NET-03 | Igual `observed_at` con capturas distintas aceptado |
| PG-NET-04 | FK compuesta de observación de soporte |
| PG-NET-05 | Índice parcial: una sola raíz |
| PG-NET-06 | Índice parcial: una sola sucesora |
| PG-NET-07 | Sucesión entre plataformas rechazada por FK |
| PG-NET-08 | Sucesor de una revisión que ya no es head rechazado |
| PG-NET-09 | Autorreferencia de cadena rechazada |
| PG-NET-10 | UPDATE/DELETE de observaciones y revisiones rechazado |
| PG-NET-11 | Procedencia parcialmente NULL rechazada |
| PG-NET-12 | Mapping con status no accepted rechazado |
| PG-NET-13 | Mapping con red distinta de la revisión rechazado |
| PG-NET-14 | Literal distinto de `provider_platform_key` rechazado |
| PG-NET-15 | Namespace distinto de `source_key:asset_platform_id` rechazado |
| PG-NET-16 | Nueva observación no revoca mapping vigente |
| PG-NET-17 | Sucesora rejected efectiva retira la resolución/mapping de las vistas |
| PG-NET-18 | Sucesora futura no termina prematuramente la revisión actual |
| PG-NET-19 | Fallo al insertar mapping revierte también la revisión |
| PG-NET-20 | Dos sesiones no pueden crear sucesoras competidoras |
| PG-NET-21 | Dos sesiones no pueden publicar mappings incompatibles |
| PG-NET-22 | JSONB acepta number/null y rechaza string/boolean/object/array |
| PG-NET-23 | Valor numérico JSON con exponente conserva valor decimal exacto |
| PG-NET-24 | Consulta bitemporal reconstruye lo conocido antes/después de una sucesora |
| PG-NET-25 | Consulta respeta el intervalo semiabierto `[valid_from, effective_valid_until)` |

### Cambios técnicos incorporados

1. Se añadió la función de laboratorio `provider_platform_resolution_as_known(valid_at, known_at)`, que filtra decisiones por `recorded_at` y calcula el final efectivo con la sucesora conocida en el instante consultado.
2. Las pruebas de concurrencia usan dos conexiones PostgreSQL independientes y un bloqueo explícito de la fila de identidad antes de insertar la sucesora/publicar el mapping.
3. Cada prueba reconstruye el esquema desechable `cci_lab` desde cero. Esto evita que los commits intencionales de los tests concurrentes contaminen fixtures posteriores.
4. Los tests de índices parciales aíslan el índice deshabilitando temporalmente el trigger de cadena dentro de un savepoint; otros casos comprueban por separado el rechazo del trigger.
5. Las pruebas negativas verifican clases de error PostgreSQL concretas (FK, UNIQUE, CHECK o inmutabilidad), no una excepción genérica.
6. Se añadió un caso adicional para exigir SHA-256 hexadecimal minúsculo de 64 caracteres cuando `evidence_sha256` está presente.

### Límites de la evidencia

La cobertura PG-NET-01–PG-NET-25 está ejecutada en el DDL reducido del laboratorio, con datos sintéticos y PostgreSQL 16.15. Esto **no** equivale a:

- validar las 34 entidades del esquema físico completo;
- aplicar migraciones productivas desde una base vacía;
- validar roles/permisos de producción o resistencia frente al propietario/superusuario;
- implementar la función bitemporal en la capa productiva de repositorio;
- validar integraciones o capturas reales de Binance, Kraken o CoinGecko.

El laboratorio no es una migración productiva y no se han insertado datos reales de proveedores.

## 10. Próximo paso

La auditoría estática de equivalencia del subsistema reducido y su regresión PostgreSQL quedaron cerradas para esta etapa. Antes de redactar migraciones productivas, corresponde una decisión explícita de promoción:

1. Congelar el contrato de estas seis tablas y elaborar un DDL productivo integrado al esquema `cci` (no copiar el schema aislado `cci_lab`).
2. Incorporar al DDL productivo roles y grants que impidan UPDATE/DELETE de snapshots y revisiones a los roles de aplicación; los triggers no protegen frente al propietario/superusuario que puede deshabilitarlos.
3. Implementar el protocolo de escritura en repositorio: lock de identidad en sentencia independiente, lectura de head, INSERT de revisión, INSERT de mapping cuando sea accepted, COMMIT/ROLLBACK.
4. Añadir una prueba de regresión para una publicación de mapping obsoleta que espera el lock mientras otra transacción registra una sucesora.
5. Integrar este subsistema en el esquema completo de 34 entidades y ejecutar migración desde base vacía, sin datos reales.

El laboratorio no se promoverá literalmente a producción. El PR #16 permanece Draft; no se han creado migraciones productivas ni se ha fusionado.


## 11. Auditoría de equivalencia laboratorio ↔ especificación física

Revisión estática realizada sobre `tests/postgresql/001_provider_platform_lab.sql` frente a la sección 13 de `postgresql-physical-schema.md`.

### Discrepancias detectadas y corregidas

1. **Índice de unicidad del mapping:** el laboratorio declaraba una constraint `UNIQUE(provider_platform_resolution_review_id)` sin predicado. En PostgreSQL su tratamiento de NULL era funcionalmente equivalente para esta columna nullable, pero no coincidía con el objeto normativo parcial ni con su nombre/forma. Se reemplazó por el índice exacto `network_identifiers_uq_review` con `WHERE provider_platform_resolution_review_id IS NOT NULL`.
2. **Proyección de la vista vigente:** la especificación incluye `recorded_at`; el laboratorio no lo exponía. Se añadió a `provider_platform_resolution_current`.
3. **Semántica de concurrencia:** el trigger toma un lock de la identidad, pero el procedimiento normativo requiere además un `SELECT ... FOR UPDATE` en una sentencia independiente antes de insertar. Bajo `READ COMMITTED`, esta separación garantiza que la sentencia INSERT posterior use un snapshot nuevo tras esperar el lock. Se explicitó esta condición en el procedimiento físico y se aclaró que el lock dentro del trigger no lo sustituye.
4. **Descripción de prevención de ciclos:** la redacción normativa anterior atribuía al trigger un recorrido de ancestros/sucesores que el DDL no implementaba. Se corrigió: la cadena autorizada es append-only, la FK inmediata exige que la predecesora exista, el trigger solo admite la cabeza y los índices parciales impiden bifurcaciones/raíces duplicadas. No hay recorrido recursivo en el trigger.

### Elementos alineados en la revisión

- Claves candidatas compuestas de plataforma, observación, revisión e identificador de red.
- CHECK del formato hexadecimal SHA-256 de evidencia opcional en observaciones.
- FKs compuestas de fuente/plataforma, observación de soporte, sucesión y mapping accepted.
- `MATCH SIMPLE` para observación de soporte nullable.
- CHECK de `valid_from` obligatorio, intervalo semiabierto y vocabulario de estados.
- JSONB `number | null` para `reported_chain_identifier_json`.
- Índices parciales de raíz y sucesora.
- Triggers de inmutabilidad, cabeza de cadena y literal/namespace del mapping.
- Vista temporal y vista de mappings publicables.
- Función de laboratorio bitemporal por `valid_at/known_at`.
- Procedimiento de publicación atómica y rollback.

### Límites y pendientes

Esta auditoría es estática y cubre el subsistema reducido de seis tablas. No demuestra equivalencia del esquema completo de 34 entidades ni reemplaza la ejecución de regresión. Tras los cambios, debe repetirse el workflow PostgreSQL y revisar sus logs.

Además, las pruebas de concurrencia existentes cubren el protocolo con lock explícito previo. Antes de promover el diseño a productivo debe mantenerse ese protocolo en la capa de repositorio y añadir una prueba de regresión que falle si un caller intenta publicar un mapping para una revisión que dejó de ser cabeza mientras espera el lock.

