# Migraciones PostgreSQL de CCI

El esquema global se instala mediante once migraciones SQL ordenadas, con ledger y checksums SHA-256. Las migraciones son transaccionales; el runner no reejecuta una versión ya aplicada y rechaza huecos, versiones desconocidas, archivos fuera del manifiesto o divergencias de checksum.

## Inventario de migraciones

| Versión | Archivo | Alcance |
|---|---|---|
| 001 | `001_cci_root_entities.sql` | Esquema `cci`, ledger y ocho entidades raíz |
| 002 | `002_source_policy_catalog.sql` | Endpoints, políticas y evaluaciones |
| 003 | `003_provider_platform_reviews.sql` | Plataformas de proveedor, observaciones y revisiones bitemporales |
| 004 | `004_network_identifiers.sql` | Identificadores de red y mappings accepted de plataforma |
| 005 | `005_asset_representations_relationships.sql` | Representaciones y relaciones dirigidas de activos |
| 006 | `006_asset_identity_resolution.sql` | Revisiones y mappings accepted de identidad de activos |
| 007 | `007_market_instrument_catalog.sql` | Instrumentos por fuente, alias, metadata y reglas |
| 008 | `008_ingestion_requests_dataset_sources.sql` | Solicitudes, asociación Run–dataset y procedencia ligada a policy evaluation |
| 009 | `009_lineage_validation_research_runs.sql` | Linaje, validaciones, ejecuciones y artifacts de investigación |
| 010 | `010_runtime_role_bootstrap.sql` | Diez roles NOLOGIN, ownership y grants SELECT deny-by-default |
| 011 | `011_migration_checksums.sql` | SHA-256 y rol ejecutor en el ledger |

## Aplicación recomendada

Desde la raíz del repositorio, con PostgreSQL 16 y el driver instalado:

```bash
python -m pip install "psycopg[binary]==3.2.9"
export CCI_DATABASE_URL="postgresql://..."
python scripts/postgresql/migrate.py
python scripts/postgresql/migrate.py --verify-only
```

El runner:

1. Comprueba que `migrations/manifest.json` enumere exactamente todos los SQL y que cada archivo coincida con su SHA-256.
2. Comprueba que el ledger sea un prefijo secuencial sin versiones desconocidas ni huecos.
3. Aplica únicamente las migraciones pendientes; cada SQL gestiona su propia transacción.
4. Comprueba que cada migración se haya registrado en `cci.schema_migrations`.
5. Tras la migración 011, completa los checksums iniciales del ledger y los compara en cada ejecución posterior.
6. En modo `--verify-only`, no aplica ni modifica nada: solo verifica el estado y los checksums.

La primera instalación requiere una conexión administrativa capaz de crear roles y transferir ownership, porque la migración 010 crea grupos NOLOGIN y establece `cci_owner`. No crea cuentas LOGIN, contraseñas ni secretos. El bootstrap verifica los atributos de roles preexistentes antes de adoptarlos. Tras ese bootstrap, el migrador controlado debe usar la membresía aprobada de `cci_migrator`.

No se recomienda aplicar manualmente los SQL con `psql`: hacerlo omite el manifiesto y la verificación de checksums. Cada archivo puede inspeccionarse de forma independiente, pero la aplicación soportada es mediante `scripts/postgresql/migrate.py`.

## Cobertura y evidencia

- **34/34 entidades** del contrato global instaladas en `cci`.
- **60/60 relaciones FK** materializadas.
- **12/12 claves compuestas destino** materializadas.
- **35 tablas físicas** en `cci`, contando `cci.schema_migrations`.
- **Diez roles NOLOGIN**; `cci_owner` es propietario y `cci_migrator` hereda esa membresía.
- Los roles de runtime no tienen DML ni DDL. `cci_reader` solo puede consultar `provider_platform_resolution_current` y `provider_platform_mappings_current`.
- La función bitemporal `provider_platform_resolution_as_known` se concede solo a `cci_identity_resolver`.
- CI PostgreSQL 16: [Run #42330173135](https://github.com/Osleyder1985/Crypto-Causality-Intelligence/actions/runs/42330173135), **145/145 pruebas aprobadas**: 102 del esquema global, 29 del laboratorio aislado, 9 de roles y 5 del migration runner.
- El laboratorio `cci_lab` sigue separado; sus seis tablas no se cuentan como entidades globales.
- Todas las pruebas usan fixtures sintéticos. No se habilita ingestión real ni se almacena OHLCV en PostgreSQL.

## Límites operativos

El gate DDL y el bootstrap inicial de roles están cerrados en CI. La infraestructura productiva todavía requiere:

- funciones transaccionales de escritura por dominio, con `SECURITY DEFINER`, `search_path` seguro, validación de actor y grants EXECUTE explícitos;
- contrato append-only de auditoría privilegiada con actor, acción, objeto, instante, motivo, evidencia y correlación;
- identidades LOGIN separadas por servicio y gestión externa de secretos/rotación;
- validación de actualización desde versiones anteriores y política de forward-fix;
- despliegue PostgreSQL persistente, backup/restore y verificación de hashes/metadata;
- confirmación de permisos de retención/licencias por proveedor antes de ingerir o persistir datos reales.

El cierre del DDL no constituye autorización de producción. PR #26 permanece Draft hasta cerrar estos gates.
