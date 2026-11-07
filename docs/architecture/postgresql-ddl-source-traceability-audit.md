# Auditoría de trazabilidad del DDL PostgreSQL — Issue #25

## Alcance y método

Se inspeccionó el árbol Git recursivo de las ramas `main` y `integration/issue-25-postgresql-foundation`, además del inventario de archivos modificados por PR #26. Se buscaron archivos versionados `.sql`, rutas de migración y los artefactos mencionados por las especificaciones.

## Resultado reproducible del árbol inspeccionado

| Elemento | Rama de integración | main |
|---|---:|---:|
| Archivos `.sql` versionados | 3 (1 laboratorio + 2 migraciones) | 0 |
| Rutas de migraciones SQL | 2 (`001_cci_root_entities.sql`, `002_source_policy_catalog.sql`) | 0 |
| `tests/postgresql/001_provider_platform_lab.sql` | Presente y reproducido | Ausente |
| Catálogo documental FK | Presente | Según árbol de main no hay migración |

El árbol de integración contiene el DDL ejecutable `tests/postgresql/001_provider_platform_lab.sql`, destinado exclusivamente al esquema desechable `cci_lab`, y dos migraciones globales: `001_cci_root_entities.sql` y `002_source_policy_catalog.sql`. En conjunto crean once de las 34 entidades de `cci` y `cci.schema_migrations`. También contiene `tests/postgresql/fk-integrity-test-catalog.md`, que es documentación, no SQL ejecutable.

## Discrepancia de trazabilidad

`postgresql-physical-schema.md` y `postgresql-lab-validation-plan.md` mencionan `tests/postgresql/001_provider_platform_lab.sql` como DDL del laboratorio ejecutado en PostgreSQL 16.15 con 29/29 pruebas. Ese archivo no está presente en el árbol Git inspeccionado de ninguna de las dos ramas.

El DDL de laboratorio se recuperó del historial Git y ahora está versionado en la rama de integración. Su reproducción actual está confirmada en PostgreSQL 16.15 con 29/29 pruebas aprobadas. La fuente continúa siendo un laboratorio aislado, no el DDL del esquema global `cci`.

## Hallazgo adicional: workflow de almacenamiento no equivale a migración CCI

`scripts/validation/storage_conformance.py` construye una tabla `candles` temporal en el PostgreSQL de CI para comparar JSONL/Parquet/DuckDB/PostgreSQL. Esa tabla técnica de conformance no es el catálogo relacional de 34 entidades `cci` y no debe confundirse con una migración productiva ni con persistencia OHLCV en PostgreSQL.

Los workflows versionados actuales ejecutan validación de datos de investigación y cobertura histórica; no existe un workflow que instale el esquema completo `cci` desde cero y ejecute las pruebas de integridad referencial/roles.

## Consecuencia

No es seguro crear una migración integral copiando supuestos del laboratorio sin disponer del SQL de origen y sin resolver la especificación relacional completa. La secuencia correcta es:

1. Mantener el DDL del laboratorio proveedor recuperado y su suite PostgreSQL 16 reproducible, sin promoverlo automáticamente a `cci`.
2. Derivar migraciones versionadas para las 34 entidades del esquema `cci`, respetando el grafo FK y las claves candidatas aprobadas.
3. Resolver los atributos pendientes de cada FK (MATCH, acciones, diferibilidad y nulabilidad) y cerrar las reglas de triggers/funciones.
4. Añadir workflow PostgreSQL 16 que instale migraciones desde base vacía y ejecute pruebas positivas/negativas, seguridad y concurrencia.
5. Conservar logs, versión del motor, SHA del commit, manifiesto de catálogo y resultados como artefactos de CI.

## Criterios de cierre

- El SQL de laboratorio citado existe y su hash/commit de origen está documentado, o se registra explícitamente como reconstrucción nueva.
- Existen dos migraciones SQL versionadas para `cci`; la cobertura actual es 11/34 entidades y no debe confundirse con cierre del gate global.
- Una instancia PostgreSQL 16 vacía debe terminar, al completar todas las migraciones, con las 34 tablas y las restricciones esperadas.
- Los catálogos `pg_class`, `pg_constraint`, `pg_indexes`, `pg_proc` y grants se comparan con un manifiesto aprobado.
- Las pruebas 120 FK, SEC-01…SEC-16 y casos transaccionales se ejecutan contra el motor.
- El workflow se vincula al commit exacto y queda aprobado.

## Dictamen

**Gate DDL iniciado, pero incompleto:** el repositorio ya contiene una migración SQL versionada que instala ocho entidades raíz y una CI PostgreSQL 16 que aprueba sus nueve pruebas junto con las 29 del laboratorio. Restan 26 entidades, las 60 FKs normalizadas, las 12 claves compuestas destino, funciones/triggers, roles y permisos, y pruebas de restauración. No se debe promover el PR #26 ni habilitar ingestión productiva hasta que el gate global se cierre.


## 13. Actualización: recuperación de la fuente histórica

La discrepancia de trazabilidad descrita arriba quedó resuelta parcialmente mediante recuperación Git verificable:

- El contrato congelado identifica el blob original del DDL: `802b6428b049a8e576f9c3e41f6c7e3f2a31b71a`.
- El commit histórico `55ba44449a1016e7902e90271801ef8ee3f05fa2` eliminó el archivo; su padre `627257411163605f5420b7b3d43ae55b299a6778` conserva el DDL, la suite Python y el workflow.
- Se restauraron sin reconstrucción manual en `integration/issue-25-postgresql-foundation`:
  - `tests/postgresql/001_provider_platform_lab.sql` (26.541 caracteres).
  - `tests/test_postgresql_lab.py` (32.190 caracteres).
  - `.github/workflows/postgresql-lab.yml` (1.417 caracteres).
- Commit de restauración: `463ae7480d683efc135a6772e22b501f898f65ff`.
- Se disparó una nueva ejecución PostgreSQL 16 para ese HEAD: [Run #42326316626](https://github.com/Osleyder1985/Crypto-Causality-Intelligence/actions/runs/42326316626).

**Resultado de reejecución confirmado:** el primer intento sobre el commit restaurado desde el padre histórico falló por un fragmento SQL duplicado residual; se reemplazó el DDL por la versión corregida exacta del commit histórico probado. Además, el descubrimiento general de tests ejecuta también esta suite, por lo que se añadió `unittest.SkipTest` cuando no existe `CCI_TEST_DATABASE_URL`; el workflow PostgreSQL dedicado sí define esa variable y ejecuta la suite íntegra.

- Ejecución confirmatoria sobre el HEAD actual `7e783980a47e35054728c166ceb200444ed78567`: [Run #42326438856](https://github.com/Osleyder1985/Crypto-Causality-Intelligence/actions/runs/42326438856).
- Servicio PostgreSQL: **16.15**.
- Resultado: **29/29 pruebas aprobadas**, `Ran 29 tests in 1.658s`, `OK`.
- Incluye pruebas de dos sesiones concurrentes, integridad FK/UNIQUE/CHECK, inmutabilidad, rollback y consulta bitemporal.

La trazabilidad del laboratorio reducido queda restablecida y reproducida en la rama de integración. El gate de DDL global permanece abierto: seis tablas de laboratorio no crean migraciones productivas ni validan las 34 entidades de `cci`.
