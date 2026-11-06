# Plan de laboratorio para validación real de PostgreSQL

- **Estado:** plan de ejecución; entorno local no disponible en la sesión actual.
- **Fecha:** 2026-11-06.
- **Ámbito:** validación del subsistema de identidad de plataformas y redes (NET-04/NET-05/NET-06).
- **PR:** #16.
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

En el entorno de ejecución disponible para esta sesión no se encontraron `psql`, servidor `postgres`, Docker, Podman ni el driver Python `psycopg`. Por tanto, no es posible afirmar ni ejecutar aquí pruebas contra un motor PostgreSQL.

La vía reproducible prevista es un servicio PostgreSQL efímero de GitHub Actions. El servicio se crea para cada ejecución, recibe únicamente fixtures sintéticos y se destruye al terminar. La CI de contratos Python seguirá separada de la CI de motor PostgreSQL.

## 4. Alcance del laboratorio

El primer laboratorio incluirá únicamente las tablas y dependencias mínimas para PG-NET-01 a PG-NET-25:

- `data_sources` y `networks` como catálogos mínimos sintéticos.
- `provider_platforms`.
- `provider_platform_observations`.
- `provider_platform_resolution_reviews`.
- `network_identifiers).
- Índices, FKs, CHECKs, triggers, funciones y vistas del subsistema.

El DDL residirá en `tests/postgresql/` y se ejecutará dentro de una base de datos de CI aislada. No se reutilizará como migración productiva sin una revisión y decisión separadas.

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

## 9. Primer incremento implementado

Se añadieron los siguientes artefactos de laboratorio:

- `tests/postgresql/001_provider_platform_lab.sql`: DDL aislado de las seis tablas mínimas, claves candidatas, FKs compuestas, CHECKs, índices parciales, triggers y vistas.
- `tests/test_postgresql_lab.py`: pruebas iniciales de smoke/integración para JSONB number/null, unicidad de captura, resolución accepted, visibilidad pending, inmutabilidad, literal/namespace y procedencia parcial.
- `.github/workflows/postgresql-lab.yml`: workflow separado con servicio efímero PostgreSQL 16 y driver psycopg fijado.

Durante la revisión estática del DDL se detectó una sutileza de SQL: en PostgreSQL un CHECK que evalúa a NULL no rechaza la fila. Se reforzó explícitamente la condición `provider_platform_resolution_status IS NOT NULL` para impedir que una procedencia parcialmente nula eluda la validación.

**Estado de ejecución:** los archivos están versionados en la rama, pero no hay todavía una ejecución de workflow PostgreSQL confirmada para el HEAD inspeccionado. Por tanto, el DDL y las pruebas aún no están validados en el motor. La suite inicial es un primer subconjunto de smoke tests; no sustituye la matriz completa PG-NET-01–PG-NET-25.


## 10. Próximo paso

Implementar el DDL desechable del subsistema NET en `tests/postgresql/`, añadir fixtures sintéticos y crear un workflow separado de GitHub Actions con servicio PostgreSQL. Después se ejecutará la matriz PG-NET-01 a PG-NET-25 y se corregirá el SQL a partir de resultados observados.
