# Matriz de preparación para DDL PostgreSQL — Issue #25

- Rama: `integration/issue-25-postgresql-foundation`
- Contrato físico: `postgresql-physical-schema.md` v0.8
- Alcance: 34 tablas del esquema `cci`
- Estado: diseño reconciliado; DDL integral aún no generado ni ejecutado.

## 1. Decisiones de diseño

| Dominio | Decisión | Estado | Consecuencia para SQL |
|---|---|---|---|
| Identidad de activos | UUID interno; códigos canónicos internos; sin equivalencia por ticker; revisión con evidencia | Cerrado por política | FKs opcionales para activos no resueltos; no seed automático inferido |
| Instrumentos | Identidad por fuente/mercado; símbolo nativo preservado | Cerrado | UNIQUE y FKs compuestas por fuente |
| Alias externos | Namespace global o por red; valid time semiabierto y knowledge time append-only | Cerrado | Revisiones inmutables, cadena lineal y función transaccional |
| Concurrencia de mappings | Lock determinista por clave de identidad y comprobación en transacción | Cerrado como estrategia | Prueba de dos sesiones; CHECK/FK no sustituyen el lock |
| Auditoría administrativa | Sin operaciones privilegiadas hasta disponer de actor, motivo, evidencia y registro append-only | Gate abierto | No conceder grants para mutaciones administrativas |
| Almacenamiento | Parquet como formato; backend concreto sin seleccionar | Gate abierto | URI opaca, hash y metadata; publicación productiva bloqueada |
| OHLCV | Fuera de PostgreSQL | Cerrado | PostgreSQL conserva catálogo y referencias, no filas OHLCV |
| Política de uso | Evaluación concreta por fuente, endpoint, tipo, uso e instante | Cerrado como contrato | Toda persistencia exige evaluación allowed verificable |

## 2. Dependencias para el orden de migraciones

1. Roles propietarios y esquema `cci`; revocar privilegios de `PUBLIC`.
2. Catálogos raíz: fuentes, namespaces, activos, redes, transformaciones y experimentos.
3. Endpoints, políticas y evaluaciones con sus FKs compuestas.
4. Identidad de plataformas, observaciones y revisiones de proveedores.
5. Representaciones, relaciones y revisiones de identidad de activos.
6. Identificadores de activos/representaciones e instrumentos.
7. Metadata y reglas de negociación versionadas.
8. Runs de ingesta, solicitudes y datasets.
9. Asociaciones de runs, fuentes, validaciones y linaje.
10. Runs de investigación, hipótesis, datasets de experimentos y referencias a artefactos.
11. Índices secundarios, restricciones temporales, funciones API y triggers.
12. Grants mínimos, privilegios por defecto y pruebas de rol negativo.

La secuencia exacta se derivará del grafo de FKs; esta lista es un orden por capas, no sustituye la topología calculada.

## 3. Pruebas que deben acompañar la migración

| Área | Pruebas positivas | Pruebas negativas / concurrencia |
|---|---|---|
| FKs compuestas | Mismo source/endpoint/instrumento/política | Cruce entre fuentes, endpoints, estados o destinos |
| CHECK y enums | Cada estado permitido y transición válida | Estados desconocidos, intervalos invertidos, valores fuera de dominio |
| Identidad de activos | Mapping exacto con revisión accepted | Ticker ambiguo, namespace incorrecto, red distinta, revisión rejected |
| Tiempo | Intervalos contiguos semiabiertos | Solapamiento, cadena bifurcada, corrección retroactiva mal enlazada |
| Publicación atómica | Revisión y mapping en una transacción | Fallo intermedio y rollback total |
| Concurrencia | Dos claves independientes en paralelo | Dos sesiones publicando la misma clave simultáneamente |
| Inmutabilidad | INSERT append-only | UPDATE/DELETE/TRUNCATE por roles runtime |
| Runs | Transiciones válidas y artefactos asociados | Run terminal reabierto, transición inválida, FK de artefacto ajena |
| Permisos | Cada rol ejecuta solo su API autorizada | INSERT directo, escalamiento, CREATE, TRUNCATE, SECURITY DEFINER insegura |
| Recuperación | Backup restaurado y hashes verificados | Interrupción durante staging/publicación y reconciliación |

## 4. Gate de evidencia

No se considera terminado ningún paso por existir documentación o código solamente:

- **Diseñado:** contrato y matriz revisados.
- **Implementado:** migración/función/trigger versionado en Git.
- **Ejecutado:** workflow o entorno PostgreSQL 16 registra ejecución con SHA identificable.
- **Aprobado:** pruebas positivas, negativas y de concurrencia pasan.
- **Recuperable:** backup restaurado en instancia separada y hashes/metadata reconciliados.

Las 10 pruebas del registro de investigación, las 29 del laboratorio aislado de plataformas y las pruebas de 5.976 velas son evidencias de subsistemas distintos; ninguna acredita la instalación integral de las 34 tablas.

## 5. Próximo entregable técnico

Generar el grafo de dependencias de las 34 tablas y contrastarlo con las FKs compuestas de la especificación. A continuación, preparar la migración inicial versionada por bloques, sin activar grants administrativos ni publicación durable hasta cerrar sus gates. La ejecución se hará desde una base vacía PostgreSQL 16 y deberá producir evidencia vinculada al commit exacto.
