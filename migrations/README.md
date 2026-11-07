# Migraciones PostgreSQL de CCI

Estas migraciones son SQL versionado, secuencial y transaccional. No son un instalador productivo completo todavía.

## Orden actual

| Versión | Archivo | Alcance | Estado |
|---|---|---|---|
| 001 | `001_cci_root_entities.sql` | Esquema `cci`, ledger y ocho entidades raíz | Implementada y probada |
| 002 | `002_source_policy_catalog.sql` | Endpoints, políticas de uso y evaluaciones concretas | Implementada y probada |

Las migraciones 001 y 002 requieren una base PostgreSQL vacía. Cada archivo abre y confirma su propia transacción. No deben ejecutarse de nuevo si su versión ya aparece en `cci.schema_migrations`; no usan `IF NOT EXISTS` deliberadamente, para que una divergencia no quede silenciada.

## Aplicación controlada

Desde la raíz del repositorio, usando una conexión de PostgreSQL 16 de pruebas:

```bash
psql "$CCI_TEST_DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/001_cci_root_entities.sql
psql "$CCI_TEST_DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/002_source_policy_catalog.sql
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
- La CI PostgreSQL 16 valida 18 pruebas del esquema global y 29 del laboratorio aislado: 47/47 aprobadas en [Run #42327032198](https://github.com/Osleyder1985/Crypto-Causality-Intelligence/actions/runs/42327032198).
- El laboratorio de plataformas de proveedor continúa en el esquema aislado `cci_lab`; no debe contarse como tablas instaladas en `cci`.
- Todavía no están implementadas las restantes entidades, todas las FKs globales, funciones/triggers de identidad, roles/grants, vistas, ni backup/restore.
- No se deben insertar datos reales de proveedores ni OHLCV. Las pruebas usan fixtures sintéticos.
- El ledger registra versiones aplicadas, pero aún no valida checksums ni sustituye un futuro ejecutor de migraciones con control de drift.
