# Reconciliación de integración PostgreSQL — Issue #25

- Estado: auditoría de integración inicial; no es aprobación final ni migración productiva.
- Rama: `integration/issue-25-postgresql-foundation`, creada desde `main`.
- Base inspeccionada: `main` en `995bda88831bda131180a37e57fea091df152748`.
- Referencias recuperadas: PR #16 (`architecture/issue-14-storage-resynced`) y PR #19 (`research/issue-19-postgresql-run-registry`).
- Alcance: recuperar los contratos documentales y reconciliar el registro de runs antes de producir DDL integral.

## 1. Resultado de recuperación

Se recuperaron desde PR #16 los ADR, el modelo lógico, la revisión lógica, la especificación física, la matriz de permisos, la propuesta de roles, los contratos de activos/redes/proveedores, los esquemas canónicos y los planes de validación.

Se eligió la versión lógica/física de la rama PR #19 para integrar las dos entidades de ejecución de investigación que no estaban en el inventario anterior: `research_experiment_runs` y `research_run_artifacts`. Esa versión conserva el modelo de activos, identidades, instrumentos, políticas, datasets y linaje, y añade la semántica de runs analíticos sin reutilizar `ingestion_runs` ni `transformation_runs`.

## 2. Correspondencia de inventario lógico-físico

La comprobación automatizada de los documentos recuperados encontró **34 entidades lógicas y 34 tablas en el inventario físico**.

- Entidades lógicas sin tabla física: **0**.
- Tablas físicas sin entidad lógica: **0**.
- Las dos entidades de registro analítico están incluidas en ambos inventarios.
- Se corrigió el diagrama Mermaid lógico para representar experimento → runs → artefactos.
- Se corrigió la numeración duplicada en las relaciones lógicas.
- Se corrigió el orden propuesto de migraciones para crear runs después de experimentos y artefactos después de runs.

Esta comprobación valida correspondencia de inventario, no todavía igualdad exhaustiva de cada atributo, tipo, nulabilidad, FK, índice, trigger, CHECK o grant. Esas verificaciones siguen siendo criterios de cierre antes de declarar el contrato físico definitivo.

## 3. Hallazgo crítico sobre las migraciones existentes

PR #19 aporta `001_research_experiments.sql` y `002_research_run_registry.sql`. Las dos migraciones implementan únicamente:

- `cci.research_experiments`
- `cci.research_experiment_runs`
- `cci.research_run_artifacts`
- índices y trigger de transición del ciclo de vida del run.

La CI reportada en PR #19 ejecutó ambas migraciones sobre PostgreSQL 16 limpio y obtuvo 10/10 pruebas PostgreSQL. Es evidencia de la porción de registro de investigación, no de la instalación del modelo completo de 34 tablas. Por tanto, **no se deben etiquetar 001/002 como migraciones definitivas del esquema CCI** ni ejecutar la ingestión productiva sobre la base de que el catálogo completo ya existe.

## 4. Divergencia de ramas y decisión de integración

En la comparación contra el HEAD de `main` inspeccionado:

| Rama | Ahead | Behind | Estado |
|---|---:|---:|---|
| `architecture/issue-14-storage-resynced` (PR #16) | 117 | 35 | Divergida |
| `research/issue-19-postgresql-run-registry` (PR #19) | 86 | 35 | Divergida |

PR #19 además apunta como base a `research/issue-18-duckdb-parquet`, no a `main`. No se integraron esas ramas mediante merge ni se promovieron sus migraciones directamente. Esta rama de integración parte del HEAD actual de `main` y recupera selectivamente los contratos documentales, evitando arrastrar sus historiales divergentes.

## 5. Bloqueos antes de DDL integral

1. Completar la matriz atributo por atributo entre el modelo lógico y el diccionario físico, incluidas claves candidatas compuestas y FKs.
2. Resolver los puntos explícitamente pendientes en la especificación física: resolución de identidad de activos, semántica temporal/solapamiento de identificadores, auditoría de actor y backend de almacenamiento/publicación atómica.
3. Cerrar el inventario de permisos para las 34 entidades y decidir el contrato de auditoría y roles por entorno.
4. Diseñar migraciones numeradas que instalen las 34 tablas desde cero; integrar el registro de runs en el orden correcto y evitar duplicar `research_experiments` si ya fue creada.
5. Probar instalación, upgrade y rollback en PostgreSQL 16 real desde base vacía; añadir pruebas negativas de FKs compuestas, triggers temporales, integridad, concurrencia y privilegios.
6. Verificar backup y restauración sobre almacenamiento persistente antes de habilitar cualquier retención de artefactos.

## 6. Límites que se mantienen

- PostgreSQL conserva catálogo, metadata, procedencia, permisos, runs y referencias; no se convierte en almacén de hechos OHLCV.
- Parquet conserva datasets solo cuando exista autorización explícita de uso/retención.
- DuckDB analiza esos datasets.
- No se consulta Binance ni Kraken ni se descargan datos como parte de esta reconciliación.
- La conformidad de 5.976 velas en CI sigue siendo una prueba acotada con PostgreSQL efímero; no prueba despliegue permanente, backup, restore o disponibilidad.

## 7. Siguiente paso

Cerrar la matriz atributo/columna/FK/índice/trigger/grant y producir una especificación física reconciliada única. Solo después se generará la primera migración integral del esquema CCI; las migraciones parciales 001/002 quedarán absorbidas o sustituidas de forma explícita y sin duplicación.
