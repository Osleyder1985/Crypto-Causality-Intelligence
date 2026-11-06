# Registro PostgreSQL de ejecuciones de investigación

- Estado: propuesta de implementación incremental del Issue #19.
- Dependencia: esquema canónico `cci.research_experiments` definido en PostgreSQL físico v0.7.
- Migración: `migrations/postgresql/002_research_run_registry.sql`.

## Semántica

`research_experiment_runs` representa una ejecución individual, no un experimento ni una ingesta. Un experimento puede tener muchos runs. Cada run fija el commit de código, versión de protocolo, parámetros efectivos y manifiesto de entrada; registra tiempos, métricas agregadas y error terminal.

Estados: `queued → running → succeeded|failed|cancelled`; también `queued → cancelled`. Los estados terminales son inmutables. Una fila comienza en queued/running; no se permite crearla directamente como finalizada.

`research_run_artifacts` guarda referencias lógicas a manifiestos, informes y datasets, junto con SHA-256, formato, tamaño, esquema y clase de retención. No guarda bytes ni series OHLCV. El hash verifica integridad del objeto externo, no autoriza su retención o redistribución.

## Transacciones y límites

Cada método del repositorio usa una transacción PostgreSQL. Las transiciones bloquean la fila con `FOR UPDATE`; la función trigger aplica el grafo de estados también ante escrituras fuera del repositorio. Las restricciones FK/CHECK/UNIQUE son responsabilidad del motor, no solo de Python.

La migración presupone que el esquema `cci` y `research_experiments` ya existen. No pretende instalar el modelo completo v0.7 ni ejecutar el laboratorio NET-04/05/06. El despliegue productivo debe aplicar primero la migración base canónica aprobada.

## Reproducibilidad

Un run se identifica por UUID y clave estable dentro del experimento. `input_manifest` debe contener referencias y hashes de entradas, no payloads OHLCV. `parameters` y `protocol_version` registran la configuración efectiva. `code_commit` debe identificar el commit exacto. Los artefactos deben registrar URI lógica, hash SHA-256 y política de retención.

La primera integración end-to-end se probará con experimento, manifiesto y artefactos sintéticos en PostgreSQL 16; no constituye un resultado de mercado ni una autorización para capturar datos de proveedores.
