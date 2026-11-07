# Auditoría de normalización de claves foráneas — Issue #25

- Rama: `integration/issue-25-postgresql-foundation`
- Fuente: `postgresql-physical-schema.md` v0.8
- Inventario revisado: 34 tablas.
- Estado: hallazgo de preparación; no es una validación de PostgreSQL.

## 1. Hallazgo

El inventario de tablas contiene 34 entidades. Sin embargo, una extracción mecánica de cláusulas literales `REFERENCES tabla(...)` sobre la especificación física encuentra solo seis menciones, concentradas en el subsistema de plataformas de proveedor. El resto del contrato expresa numerosas relaciones mediante descripciones como “FK a…”, “FK compuesta” o claves candidatas, sin una representación uniforme de origen, columnas, destino, columnas referenciadas, MATCH, acciones ON UPDATE/DELETE y diferibilidad.

Esto **no demuestra que solo existan seis FKs**. Demuestra que el documento no es todavía una fuente estructurada suficientemente uniforme para generar DDL automáticamente ni para verificar de forma exhaustiva todas las relaciones mediante un parser simple.

## 2. Riesgo

Generar migraciones directamente desde la prosa actual podría:
- omitir relaciones compuestas;
- elegir columnas referenciadas que no tengan UNIQUE/PK compatible;
- cambiar accidentalmente la semántica NULL de FKs opcionales;
- perder acciones `ON DELETE`/`ON UPDATE`;
- crear tablas en un orden incorrecto o introducir dependencias circulares;
- validar una referencia en Python que debería estar garantizada por PostgreSQL.

Por ello, la migración integral queda bloqueada hasta que exista un registro explícito de cada FK.

## 3. Formato obligatorio de la matriz FK

Cada relación debe tener una fila con:

| Campo | Significado |
|---|---|
| constraint_name | Nombre estable y único de la restricción |
| source_table | Tabla que contiene la FK |
| source_columns | Columnas ordenadas de la FK |
| target_table | Tabla referenciada |
| target_columns | PK/UNIQUE candidata referenciada, mismo orden |
| match_type | SIMPLE / FULL / PARTIAL (normalmente SIMPLE) |
| on_update | Acción explícita |
| on_delete | Acción explícita |
| deferrable | Sí/No |
| initially_deferred | Sí/No |
| null_semantics | Qué combinación de NULL permite la relación |
| rationale | Invariante de dominio protegido |
| test_ids | Pruebas positivas y negativas que la verifican |

La matriz deberá cubrir las 34 tablas, aunque una tabla no tenga FKs. Toda FK compuesta debe identificar su clave candidata destino y demostrar que existe una PK/UNIQUE compatible. Toda FK nullable debe declarar expresamente su semántica NULL.

## 4. Orden de trabajo corregido

1. Extraer todas las relaciones expresadas en prosa de la especificación v0.8.
2. Normalizarlas en una matriz FK completa, sin inventar columnas o acciones ausentes.
3. Marcar cada dato no especificado como decisión pendiente y resolverlo contra el contrato lógico y los invariantes del dominio.
4. Verificar que cada destino tenga PK/UNIQUE compatible y que las columnas estén tipadas de forma idéntica.
5. Calcular el grafo de dependencias desde la matriz validada y obtener el orden topológico; tratar autorreferencias y ciclos explícitamente.
6. Generar DDL a partir de esa matriz revisada, no de búsquedas de texto ni de nombres de tablas.
7. Ejecutar pruebas PostgreSQL 16 desde base vacía, incluyendo FKs compuestas, NULL, acciones referenciales y rollback.

## 5. Dictamen

La correspondencia lógica-física 34/34 y de atributos declarados sigue siendo válida como comprobación documental de inventario. No equivale a una auditoría completa de claves foráneas. El siguiente entregable prioritario no es todavía el SQL: es la matriz FK normalizada y verificable. No se debe declarar cerrada la correspondencia lógica-física en su dimensión relacional hasta aprobarla.
