# Migraciones PostgreSQL de CCI

Estas migraciones son SQL versionado, secuencial y transaccional. No son un instalador productivo completo todavía.

## Orden actual

| Versión | Archivo | Alcance | Estado |
|---|---|---|---|
| 001 | `001_cci_root_entities.sql` | Esquema `cci`, ledger y ocho entidades raíz | Implementada y probada |
| 002 | `002_source_policy_catalog.sql` | Endpoints, políticas de uso y evaluaciones concretas | Implementada y probada |
| 003 | `003_provider_platform_reviews.sql` | Plataformas de proveedor, observaciones inmutables, revisiones append-only y consultas bitemporales | Implementada y probada |
| 004 | `004_network_identifiers.sql` | Identificadores de red y publicación validada de mappings de plataforma accepted | Implementada y probada |
| 005 | `005_asset_representations_relationships.sql` | Representaciones canónicas de activos y relaciones dirigidas con evidencia | Implementada y probada |
| 006 | `006_asset_identity_resolution.sql` | Revisiones append-only de identidad y mappings accepted de activo/representación | Implementada y probada |
| 007 | `007_market_instrument_catalog.sql` | Instrumentos por fuente, alias, versiones de metadata y reglas de negociación | Implementada y probada |
| 008 | `008_ingestion_requests_dataset_sources.sql` | Solicitudes de ingesta, asociación run-dataset y procedencia de dataset vinculada a policy evaluation | Implementada y probada |
| 009 | `009_lineage_validation_research_runs.sql` | Linaje/validación de datasets, ejecuciones de transformación e investigación, hipótesis y artifacts | Implementada y probada |

La cadena 001→002→003→004→005 requiere una base PostgreSQL vacía. Cada archivo abre y confirma su propia transacción. No deben ejecutarse de nuevo si su versión ya aparece en `cci.schema_migrations`; no usan `IF NOT EXISTS` deliberadamente, para que una divergencia no quede silenciada.

## Aplicación controlada

Desde la raíz del repositorio, usando una conexión de PostgreSQL 16 de pruebas:

```bash
psql "$CCI_TEST_DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/001_cci_root_entities.sql
psql "$CCI_TEST_DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/002_source_policy_catalog.sql
psql "$CCI_TEST_DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/003_provider_platform_reviews.sql
psql "$CCI_TEST_DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/004_network_identifiers.sql
psql "$CCI_TEST_DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/005_asset_representations_relationships.sql
psql "$CCI_TEST_DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/006_asset_identity_resolution.sql
psql "$CCI_TEST_DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/007_market_instrument_catalog.sql
psql "$CCI_TEST_DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/008_ingestion_requests_dataset_sources.sql
```

Verificar el ledger:

```sql
SELECT version, description, applied_at
FROM cci.schema_migrations
ORDER BY version;
```

La ejecución automatizada de CI aplica las migraciones desde una instalación limpia mediante psycopg y luego ejecuta las pruebas positivas y negativas contra PostgreSQL real.

## Límites explícitos

- La versión 001 instala 8 de las 34 entidades del contrato global.
- La versión 002 añade 3 entidades: cobertura acumulada 11/34.
- La versión 003 añade 3 entidades: cobertura acumulada 14/34; implementa seis FKs adicionales, cadenas append-only de revisiones, bloqueo de concurrencia por identidad, vista de resolución vigente y función `valid_at`/`known_at`.
- La versión 004 añade `network_identifiers`: cobertura acumulada 15/34 entidades y 15/60 FKs. Implementa validación de procedencia, literal/namespace, estado accepted, mapping único por revisión, inmutabilidad y vista de mappings vigentes.
- La versión 005 añade `asset_representations` y `asset_relationships`: cobertura acumulada 17/34 entidades, 19/60 FKs y 8/12 claves compuestas destino.
- La versión 006 añade revisiones de identidad y mappings accepted de activos/representaciones: cobertura acumulada 20/34 entidades, 29/60 FKs y 10/12 claves compuestas.
- La versión 007 añade el catálogo de instrumentos: cobertura acumulada 24/34 entidades, 36/60 FKs y 11/12 claves compuestas destino.
- La versión 008 añade `ingestion_requests`, `run_datasets` y `dataset_sources`: cobertura acumulada **27/34 entidades**, **48/60 FKs** y **12/12 claves compuestas destino**. Las contribuciones de datasets quedan ligadas a la fuente, endpoint, instrumento opcional, request opcional y evaluación concreta de permiso; UK-12 queda materializada.
- La CI PostgreSQL 16 [Run #42328891406](https://github.com/Osleyder1985/Crypto-Causality-Intelligence/actions/runs/42328891406) aprueba 90 pruebas del esquema global y 29 del laboratorio aislado: **119/119**.
- El laboratorio de plataformas de proveedor continúa en el esquema aislado `cci_lab`; no debe contarse como tablas instaladas en `cci`.
- Todavía no están implementadas las restantes entidades, todas las FKs globales, funciones/triggers de identidad, roles/grants, vistas, ni backup/restore.
- No se deben insertar datos reales de proveedores ni OHLCV. Las pruebas usan fixtures sintéticos.
- El ledger registra versiones aplicadas, pero aún no valida checksums ni sustituye un futuro ejecutor de migraciones con control de drift.
