# Matriz de preparación para DDL PostgreSQL — Issue #25

- Rama: `integration/issue-25-postgresql-foundation`
- Contrato físico: `postgresql-physical-schema.md` v0.8
- Alcance: 34 tablas del esquema `cci`
- Estado: once migraciones versionadas implementadas (nueve de esquema de dominio, bootstrap de roles y ledger de checksums); 34/34 entidades, 60/60 FKs y 12/12 claves compuestas verificadas en PostgreSQL 16. El gate DDL está cerrado; los gates de operación productiva permanecen abiertos.

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

El grafo de 34 tablas y las 60 relaciones FK ya están documentados. La siguiente migración debe incorporar `network_identifiers` y el guard transaccional de publicación de mappings de plataforma. Debe conectar las revisiones accepted con la red canónica, comprobar namespace y literal exactos del proveedor, impedir doble mapping por revisión y probar rollback/concurrencia en el esquema global `cci`. No se activarán grants administrativos ni ingestión real.

## 6. Implementación parcial verificada — migraciones 001–003

Se incorporó `migrations/001_cci_root_entities.sql`, que crea el esquema `cci`, la tabla operativa `cci.schema_migrations` y ocho entidades raíz sin dependencias FK entre ellas: `data_sources`, `assets`, `identity_namespaces`, `networks`, `ingestion_runs`, `datasets`, `transformations` y `research_experiments`.

La migración conserva tipos, vocabularios CHECK, claves primarias/únicas, checks JSONB, hash SHA-256, rangos temporales y coherencia de estados definidos para esas entidades en el contrato físico. No incorpora datos reales ni OHLCV. No crea FKs porque estas ocho entidades son raíces en el grafo de dependencias; tampoco concede roles/grants productivos.

Suite reproducible: `tests/test_postgresql_cci_core.py`, nueve pruebas de instalación limpia, inventario, checks positivos/negativos y unicidad. El workflow PostgreSQL ejecuta conjuntamente esta suite y el laboratorio proveedor.

- Ejecución: [Run #42326803388](https://github.com/Osleyder1985/Crypto-Causality-Intelligence/actions/runs/42326803388).
- Motor: PostgreSQL 16.
- Resultado conjunto: **38/38 pruebas aprobadas** (9 de esquema raíz + 29 del laboratorio proveedor), `OK`.
- HEAD probado: `13a920b0c3a0f54c2f2ce822b2222651a6f3a44d`.

La migración 002 añade `data_endpoints`, `source_usage_policies` y `policy_evaluations`, incluyendo FKs simples/compuestas, 5 índices de consulta/FK y checks de alcance, permisos, hash y vigencia. La suite `tests/test_postgresql_cci_policy.py` prueba referencias cruzadas de fuente, alcance provider/product/endpoint, vigencia y evaluación concreta.

**Resultado acumulado tras migración 009:** las 34 entidades globales de `cci` están instaladas, con 60/60 FKs y 12/12 claves compuestas destino. La migración 009 incorpora las siete entidades finales, prevención transaccional de ciclos en el linaje, validaciones de datasets, ejecuciones de transformación e investigación, transiciones de estado y artifacts inmutables. La suite ejecuta 102 pruebas globales más 29 del laboratorio aislado: [Run #42329331544](https://github.com/Osleyder1985/Crypto-Causality-Intelligence/actions/runs/42329331544), PostgreSQL 16, **131/131 aprobadas**.

**Límite:** el modelo lógico-físico de 34 entidades, 60 FKs y 12 claves compuestas está materializado en nueve migraciones; la migración 010 añade diez roles NOLOGIN y grants SELECT deny-by-default. La CI [Run #42330173135](https://github.com/Osleyder1985/Crypto-Causality-Intelligence/actions/runs/42330173135) aprueba 145 pruebas (102 globales, 29 laboratorio, 9 roles y 5 del migration runner). Esto cierra el gate DDL, no el de producción. Restan funciones transaccionales de escritura, auditoría privilegiada, cuentas LOGIN gestionadas externamente, introspección automática del catálogo, migrador con checksums/drift, despliegue persistente y backup/restore.
