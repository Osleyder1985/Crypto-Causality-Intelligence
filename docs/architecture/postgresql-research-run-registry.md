# Registro PostgreSQL de ejecuciones de investigación

- Estado: propuesta de implementación incremental del Issue #19.
- Dependencia: esquema canónico `cci.research_experiments` definido en PostgreSQL físico v0.8.
- Migraciones: `001_research_experiments.sql` y después `002_research_run_registry.sql`.
- Alcance: base ejecutable de `research_experiments` y su registro de runs; no instala todas las tablas del modelo CCI.

## Semántica

`research_experiment_runs` representa una ejecución individual, no un experimento ni una ingesta. Un experimento puede tener muchos runs. Cada run fija el commit de código, versión de protocolo, parámetros efectivos y manifiesto de entrada; registra tiempos, métricas agregadas y error terminal.

Estados: `queued → running → succeeded|failed|cancelled`; también `queued → cancelled`. Los estados terminales son inmutables. Una fila comienza en queued/running; no se permite crearla directamente como finalizada.

`research_run_artifacts` guarda referencias lógicas a manifiestos, informes y datasets, junto con SHA-256, formato, tamaño, esquema y clase de retención. No guarda bytes ni series OHLCV. El hash verifica integridad del objeto externo, no autoriza su retención o redistribución.

## Transacciones y límites

Cada método del repositorio usa una transacción PostgreSQL. Las transiciones bloquean la fila con `FOR UPDATE`; la función trigger aplica el grafo de estados también ante escrituras fuera del repositorio. Las restricciones FK/CHECK/UNIQUE son responsabilidad del motor, no solo de Python.

Para una instalación aislada, aplicar en orden `001_research_experiments.sql` y `002_research_run_registry.sql`; la primera crea el esquema `cci` y la tabla base `research_experiments`, la segunda añade runs y artefactos. En un entorno que ya tenga el modelo físico v0.8 aplicado, verificar equivalencia de `research_experiments` y aplicar solo la segunda migración si la tabla ya existe. Estas dos migraciones no instalan todas las tablas del modelo CCI ni sustituyen la migración integral del esquema productivo.

## Rol operativo de mínimo privilegio

La migración no crea usuarios ni contraseñas. El aprovisionamiento del entorno debe crear el rol fuera del DDL de tablas y entregar credenciales mediante un gestor de secretos. Con el rol `cci_research_runner` ya creado, los permisos mínimos probados para la operación son:

```sql
GRANT USAGE ON SCHEMA cci TO cci_research_runner;
GRANT SELECT, INSERT, UPDATE ON cci.research_experiment_runs TO cci_research_runner;
GRANT SELECT, INSERT ON cci.research_run_artifacts TO cci_research_runner;
```

No se concede `DELETE`, `TRUNCATE`, creación de objetos ni propiedad de las tablas. La prueba de integración verifica que el rol puede crear y cerrar runs, insertar artefactos y que un borrado directo falla.

## Reproducibilidad

Un run se identifica por UUID y clave estable dentro del experimento. `input_manifest` debe contener referencias y hashes de entradas, no payloads OHLCV. `parameters` y `protocol_version` registran la configuración efectiva. `code_commit` debe identificar el commit exacto. Los artefactos deben registrar URI lógica, hash SHA-256 y política de retención.

## Integración del CLI de episodios BTC/USDT

El CLI mantiene su modo local por defecto. Para registrar una ejecución se proporcionan juntos `--experiment-id`, `--run-key` y `--code-commit`, y se configura `CCI_DATABASE_URL`. El experimento debe existir previamente en `cci.research_experiments` y la migración del registro debe estar aplicada.

Ejemplo (el UUID, el commit y las rutas son valores que debe proporcionar el operador):

```bash
export CCI_DATABASE_URL="postgresql://..."
python scripts/research/btc_episode_study.py \
  --input /ruta/local/btcusdt_1h.parquet --input-format parquet \
  --episodes /ruta/local/btc_episodes.json \
  --json-out /ruta/local/summary.json --csv-out /ruta/local/summary.csv \
  --experiment-id "$CCI_EXPERIMENT_ID" --run-key "btc-episodes-2026-01" \
  --code-commit "$CCI_CODE_COMMIT"
```

El CLI crea el run en `queued`, lo pasa a `running`, ejecuta el estudio y registra dos artefactos (JSON agregado y CSV por episodio) con SHA-256 y tamaño. Termina en `succeeded`; si falla el análisis después de iniciar el run, intenta registrar `failed` con el tipo y resumen del error. Las URI de artefactos son identificadores lógicos configurables con `--artifact-uri-prefix`; los archivos permanecen en la ruta local indicada y no se transfieren a PostgreSQL ni al repositorio.

El manifiesto guarda hashes y nombres base de los archivos de entrada, no rutas absolutas ni contenido OHLCV. Los parámetros efectivos guardan formato, intervalo y ventanas previas. El modo sin los tres argumentos de registro no requiere psycopg ni conexión PostgreSQL.

La integración end-to-end se valida con un CSV y episodios sintéticos contra PostgreSQL 16; no constituye un resultado de mercado ni una autorización para capturar datos de proveedores.
