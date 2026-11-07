# Auditoría de trazabilidad del DDL PostgreSQL — Issue #25

## Alcance y estado actual

Se inspeccionaron los árboles Git de `main` y `integration/issue-25-postgresql-foundation`, el contenido de las migraciones y las ejecuciones CI asociadas.

| Elemento | Rama de integración | main |
|---|---:|---:|
| Archivos SQL versionados | 12 (1 laboratorio + 11 migraciones) | 0 |
| Migraciones globales `cci` | 11 | 0 |
| Entidades del contrato instaladas en `cci` | 34/34 | 0 |
| Relaciones FK globales implementadas | 60/60 | 0 |
| Laboratorio `cci_lab` | Recuperado y reproducido | Ausente |

## Fuentes SQL y alcance

- `tests/postgresql/001_provider_platform_lab.sql`: laboratorio aislado y desechable `cci_lab`; no es una migración de aplicación.
- `migrations/001_cci_root_entities.sql`: esquema `cci`, ledger y ocho entidades raíz.
- `migrations/002_source_policy_catalog.sql`: endpoints, políticas y evaluaciones; seis relaciones FK.
- `migrations/003_provider_platform_reviews.sql`: plataformas, observaciones y revisiones; seis relaciones FK.
- `migrations/004_network_identifiers.sql`: identificadores de red y mappings de plataforma accepted; tres relaciones FK.
- `migrations/005_asset_representations_relationships.sql`: representaciones y relaciones de activos; cuatro relaciones FK y clave compuesta `(id, network_id)`.
- `migrations/006_asset_identity_resolution.sql`: revisiones de identidad y mappings de activo/representación; diez FKs y claves compuestas UK-09/UK-10.
- `migrations/007_market_instrument_catalog.sql`: instrumentos, alias, metadata y reglas; siete FKs y clave compuesta UK-11.
- `migrations/008_ingestion_requests_dataset_sources.sql`: solicitudes de ingesta, asociaciones run-dataset y procedencia; doce FKs y clave compuesta UK-12.
- `migrations/009_lineage_validation_research_runs.sql`: linaje, validaciones, ejecuciones de transformación/investigación, artifacts, hipótesis y datasets experimentales; doce FKs finales.
- `migrations/010_runtime_role_bootstrap.sql`: diez grupos NOLOGIN, ownership y grants SELECT deny-by-default; no crea usuarios LOGIN ni concede DML a runtime.
- `migrations/011_migration_checksums.sql`: checksum SHA-256 y rol ejecutor en el ledger.
- `migrations/manifest.json` y `scripts/postgresql/migrate.py`: manifiesto de hashes y runner secuencial con detección de drift.
- `migrations/README.md`: orden de aplicación y límites operativos.
- `tests/postgresql/fk-integrity-test-catalog.md`: catálogo documental de escenarios; no es SQL ejecutable.

## Evidencia PostgreSQL

La CI PostgreSQL 16 [Run #42329699551](https://github.com/Osleyder1985/Crypto-Causality-Intelligence/actions/runs/42329699551) aplicó las diez migraciones desde un esquema limpio y ejecutó:

- 102 pruebas contra el esquema global `cci`.
- 29 pruebas contra el laboratorio independiente `cci_lab`.
- 9 pruebas de ownership, roles, GRANT/REVOKE y aislamiento por sesión.
- **140/140 pruebas aprobadas**.

La cobertura global comprende 34/34 entidades, 60/60 FKs y 12/12 claves compuestas destino. La tabla operativa `cci.schema_migrations` eleva a 35 el número de tablas físicas en el esquema.

## Hallazgo sobre almacenamiento y OHLCV

`scripts/validation/storage_conformance.py` crea una tabla temporal `candles` para comparar JSONL/Parquet/DuckDB/PostgreSQL en CI. No es una tabla del catálogo `cci`, no es una migración productiva y no autoriza almacenar OHLCV en PostgreSQL.

## Pendientes operativos tras el cierre del DDL

1. Implementar funciones transaccionales de escritura por dominio, con `SECURITY DEFINER`, `search_path` seguro, validación de actor y grants EXECUTE explícitos.
2. Aprobar un contrato append-only de auditoría para actor, acción, objeto, instante, motivo, evidencia y correlación.
3. Crear identidades LOGIN individuales por servicio y gestionar credenciales fuera de las migraciones; el bootstrap actual crea solo grupos NOLOGIN.
4. Añadir verificación de checksums/drift al ejecutor de migraciones y validar actualización desde versiones anteriores.
5. Comparar `pg_class`, `pg_constraint`, `pg_indexes`, `pg_proc`, ownership y grants con un manifiesto aprobado.
6. Probar backup/restore en una instancia persistente separada y reconciliar hashes/metadata.
7. Confirmar la política de retención/licencias de cada proveedor antes de habilitar ingestión real o persistencia de OHLCV.

**Dictamen:** gate DDL cerrado y reproducible en CI. El bootstrap de roles es fail-closed, pero los roles de runtime no pueden escribir todavía. PR #26 debe permanecer Draft y no se debe habilitar ingestión real ni persistencia de OHLCV hasta cerrar los gates operativos y de seguridad.

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
