# Plan de laboratorio para validación real de PostgreSQL

- **Estado:** primer incremento ejecutado correctamente; matriz PG-NET-01–PG-NET-25 pendiente.
- **Fecha de actualización:** 2026-11-06.
- **Ámbito:** validación del subsistema de identidad de plataformas y redes (NET-04/NET-05/NET-06).
- **PR:** #16 (permanece Draft).
- **Restricción:** solo datos sintéticos; no se conecta a Binance, Kraken ni CoinGecko.

## 1. Objetivo

Convertir la especificación de las secciones 10 y 13 de `postgresql-physical-schema.md` en DDL de laboratorio y comprobar sus garantías en un servidor PostgreSQL real. El laboratorio no es una migración de producción ni crea el esquema completo de 32 entidades.

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
- `tests/test_postgresql_lab.py`: siete pruebas de integración contra PostgreSQL real.
- `.github/workflows/postgresql-lab.yml`: workflow separado con servicio efímero PostgreSQL 16 y driver psycopg fijado.

### Evidencia de ejecución

- **Workflow:** [Pruebas reales de PostgreSQL — Run #7](https://github.com/Osleyder1985/Crypto-Causality-Intelligence/actions/runs/42291704131).
- **Evento:** `pull_request`, asociado al PR #16.
- **HEAD del PR:** `cf996df815b625a50f87f3520023edcade8a15cc`.
- **Commit merge probado por el runner:** `5cb8fcae67accef15471d735183ac026fc79ace1`.
- **Servicio:** imagen `postgres:16`; logs del servidor identifican PostgreSQL **16.15**.
- **Job:** `postgresql-lab`, conclusión `success`.
- **Resultado:** **7/7 pruebas aprobadas**.

Casos ejecutados:
1. JSON number y JSON null aceptados; string rechazado.
2. `capture_id` único y `observed_at` repetible con capturas distintas.
3. Una revisión accepted publica el mapping vigente.
4. Una revisión `pending_review` es visible, pero no publica mapping.
5. Los snapshots de observaciones son inmutables.
6. La procedencia parcial de un identificador es rechazada.
7. Literal y namespace de mapping incorrectos son rechazados.

Los errores SQL visibles en los logs corresponden a las operaciones negativas esperadas por las pruebas; las siete pruebas finalizaron `ok`. No se detectó fallo de DDL, infraestructura ni de pruebas en esta ejecución.

Durante la revisión estática del DDL se había detectado una sutileza de SQL: en PostgreSQL un CHECK que evalúa a NULL no rechaza la fila. Se reforzó explícitamente la condición `provider_platform_resolution_status IS NOT NULL`; la prueba de procedencia parcial confirma ahora el rechazo real del motor.

### Límites de esta evidencia

Esta ejecución valida el primer subconjunto de siete comportamientos en PostgreSQL 16.15. No demuestra todavía la matriz completa PG-NET-01–PG-NET-25, la concurrencia entre conexiones independientes, la atomicidad de publicación bajo fallos ni la consulta bitemporal. Tampoco valida el esquema completo de 32 entidades ni constituye una migración productiva.

## 9. Próximo paso

Ampliar el laboratorio hasta cubrir de forma trazable PG-NET-01–PG-NET-25. Prioridad inmediata:

1. FKs compuestas y sus casos de identidad cruzada.
2. Cadena de revisiones: raíz única, sucesor único, rechazo de bifurcación, sucesor no-head y retroceso temporal.
3. Vigencia semiabierta y vistas con sucesora futura.
4. Mapping accepted, rechazo de mapping no accepted o de una revisión que dejó de ser head.
5. Atomicidad: rollback cuando falla la inserción del mapping después de insertar la revisión.
6. Concurrencia con dos conexiones independientes y sincronización determinista; demostrar que no puede formarse una bifurcación.
7. Consulta bitemporal con `valid_at` y `known_at`, una vez implementada en el laboratorio o en la capa de repositorio que corresponda.

Cada caso tendrá identificador, precondiciones, operación, resultado esperado, SQLSTATE/constraint cuando aplique y prueba automatizada. Se corregirá el SQL a partir de evidencia de PostgreSQL, no de inferencias estáticas.

El PR #16 permanece Draft. No se crearán migraciones productivas ni se fusionará el PR como parte de esta etapa.
