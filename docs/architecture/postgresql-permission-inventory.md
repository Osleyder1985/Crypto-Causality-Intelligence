# Inventario de permisos PostgreSQL — CCI

- **Estado:** propuesta de autorización v0.1; pendiente de revisión y aprobación.
- **Fecha:** 2026-11-06.
- **Base documental:** `postgresql-physical-schema.md` v0.7 y `postgresql-logical-data-model.md` v0.7.
- **Rama:** `architecture/issue-14-storage-resynced`.
- **Alcance:** 32 tablas del esquema `cci`.
- **No incluido:** DDL de roles, GRANT/REVOKE, funciones SQL implementadas ni migraciones.

## 1. Principios de autorización

1. Aplicar mínimo privilegio por servicio y por operación.
2. Separar lectura de metadatos, escritura de catálogo, adquisición, transformación, resolución de identidad, evaluación de políticas e investigación.
3. Los servicios de ejecución no son propietarios de objetos y no reciben privilegios DDL.
4. Las tablas históricas son append-only: el rol ordinario puede insertar y leer según necesidad, pero no actualizar ni eliminar.
5. Los cambios de estado se realizan mediante funciones transaccionales con validación de transición; no mediante UPDATE libre.
6. Los lectores analíticos consultan vistas aprobadas. No reciben acceso general a tablas internas ni a ubicaciones de almacenamiento sin una autorización independiente.
7. Ninguna autorización de base de datos sustituye la evaluación contractual de uso de datos. Una contribución solo se persiste cuando una evaluación aplicable autoriza el uso.
8. No se concede TRUNCATE, REFERENCES, TRIGGER, CREATE ni ownership a roles de aplicación.

## 2. Clasificación de operaciones

| Código | Semántica | Política propuesta |
|---|---|---|
| A | Append-only | INSERT mediante servicio/función autorizado; SELECT según necesidad; sin UPDATE/DELETE. |
| T | Transición controlada | INSERT inicial y cambios de estado solo mediante función transaccional; sin UPDATE/DELETE directo. |
| V | Versionado append-only | Nuevas versiones/observaciones mediante INSERT; no se sobrescriben versiones anteriores. |
| B | Asociación append-only | INSERT de relación; sin UPDATE/DELETE ordinario. |

La clasificación T no significa que se permita modificar libremente la fila. Solo los campos de estado expresamente definidos pueden cambiar mediante una operación validada y auditada.

## 3. Inventario de las 32 entidades

| # | Entidad | Dominio | Clase | Lectura | Escritura autorizada propuesta |
|---:|---|---|---|---|---|
| 1 | `data_sources` | Fuentes y políticas | T | Servicios internos y administradores de catálogo | Administrador de catálogo, mediante función de alta/cambio de estado |
| 2 | `data_endpoints` | Fuentes y políticas | T | Adquisición, catálogo, evaluación de políticas | Administrador de catálogo, mediante función; cambios de estado controlados |
| 3 | `source_usage_policies` | Fuentes y políticas | V | Evaluador de políticas y auditoría | Administrador de políticas, mediante función de registro de nueva versión |
| 4 | `policy_evaluations` | Fuentes y políticas | A | Adquisición, procedencia, auditoría | Evaluador de políticas, mediante función transaccional |
| 5 | `assets` | Identidad de activos | A | Servicios internos y vistas analíticas aprobadas | Administrador/resolvedor de catálogo, mediante función |
| 6 | `identity_namespaces` | Identidad de activos | A | Resolvedor de identidad y auditoría | Administrador de identidad, mediante función; sin edición de claves existentes |
| 7 | `networks` | Identidad de redes | A | Servicios internos y resolvedor | Administrador de identidad, mediante función |
| 8 | `network_identifiers` | Identidad de redes | A | Resolvedor y auditoría | Resolvedor de identidad, mediante publicación transaccional |
| 9 | `provider_platforms` | Identidad de redes | A | Captura de metadata y resolvedor | Servicio de catálogo de proveedor, mediante función |
| 10 | `provider_platform_observations` | Identidad de redes | A | Resolvedor y auditoría | Servicio de captura, mediante INSERT |
| 11 | `provider_platform_resolution_reviews` | Identidad de redes | A | Resolvedor y auditoría | Resolvedor, mediante función que serializa la cadena de revisiones |
| 12 | `asset_representations` | Identidad de activos | A | Servicios internos y resolvedor | Resolvedor, mediante función de publicación |
| 13 | `asset_relationships` | Identidad de activos | A | Investigación y servicios internos | Administrador/resolvedor, mediante función con evidencia |
| 14 | `asset_identity_resolution_reviews` | Identidad de activos | A | Resolvedor y auditoría | Resolvedor, mediante función transaccional |
| 15 | `asset_identifiers` | Identidad de activos | A | Servicios internos y resolvedor | Resolvedor, en la misma transacción que su revisión accepted |
| 16 | `asset_representation_identifiers` | Identidad de activos | A | Servicios internos y resolvedor | Resolvedor, en la misma transacción que su revisión accepted |
| 17 | `market_instruments` | Instrumentos y metadata | A | Adquisición, catálogo y analítica autorizada | Servicio de catálogo de instrumentos, mediante función |
| 18 | `instrument_identifiers` | Instrumentos y metadata | A | Adquisición y catálogo | Mapeador de metadata, mediante INSERT |
| 19 | `instrument_metadata_versions` | Instrumentos y metadata | V | Adquisición, catálogo y auditoría | Mapeador de metadata, mediante INSERT de observación |
| 20 | `instrument_trading_rules` | Instrumentos y metadata | V | Adquisición y validadores | Mapeador de metadata, mediante INSERT de versión |
| 21 | `ingestion_runs` | Adquisición y ejecución | T | Operaciones, auditoría y servicios internos | Servicio de adquisición: alta y transición mediante función |
| 22 | `ingestion_requests` | Adquisición y ejecución | T | Servicio de adquisición y auditoría | Servicio de adquisición: registrar intento y completar resultado mediante función |
| 23 | `datasets` | Datasets y procedencia | T | Servicios internos; lectores solo mediante vistas | Ingestión/transformación: alta inmutable; retención mediante función separada |
| 24 | `run_datasets` | Datasets y procedencia | B | Operaciones y auditoría | Servicio de adquisición, mediante INSERT |
| 25 | `dataset_sources` | Datasets y procedencia | A | Autorización, auditoría y servicios internos | Servicio de procedencia, mediante función que exige evaluación allowed |
| 26 | `dataset_lineage` | Datasets y procedencia | B | Transformación, investigación y auditoría | Servicio de transformación, mediante función con control transaccional de ciclos |
| 27 | `data_validations` | Calidad y validación | A | Servicios internos y auditoría | Servicio validador, mediante INSERT |
| 28 | `transformations` | Transformación | V | Servicio de transformación y auditoría | Administrador de transformaciones, mediante alta de nueva versión |
| 29 | `transformation_runs` | Transformación | T | Transformación, operaciones y auditoría | Servicio de transformación: alta y transición mediante función |
| 30 | `research_experiments` | Investigación | T | Investigación y vistas aprobadas | Servicio de investigación: alta y transición mediante función |
| 31 | `research_hypotheses` | Investigación | T | Investigación y vistas aprobadas | Servicio de investigación: alta y transición mediante función |
| 32 | `experiment_datasets` | Investigación | B | Investigación y auditoría | Servicio de investigación, mediante INSERT |

**Resultado de clasificación:** 32 entidades inventariadas; 17 A, 4 V, 3 B y 8 T. Las clases describen la política de escritura propuesta, no privilegios ya concedidos.

## 4. Roles de aplicación propuestos

Los nombres son identificadores de diseño, no roles creados en PostgreSQL.

| Rol | Responsabilidad | Límites |
|---|---|---|
| `cci_owner` | Propietario NOLOGIN de objetos del esquema | Sin uso por servicios ni credenciales de aplicación |
| `cci_migrator` | Ejecutar migraciones aprobadas | Credencial temporal de despliegue; no se usa en runtime |
| `cci_catalog_writer` | Altas de fuentes, endpoints, activos, redes e instrumentos | Sin DELETE; cambios de estado por funciones |
| `cci_policy_admin` | Registrar evidencia versionada de políticas | No puede autorizar por sí solo la persistencia de datasets |
| `cci_policy_evaluator` | Evaluar aplicabilidad y registrar snapshots de decisión | Sin UPDATE/DELETE de políticas ni evaluaciones |
| `cci_ingest_writer` | Registrar Runs, solicitudes, datasets de captura y procedencia | No modifica historia ni omite evaluación de política |
| `cci_identity_resolver` | Publicar revisiones y mappings de identidad | Solo funciones transaccionales; sin escritura directa a mappings |
| `cci_transform_writer` | Registrar transformaciones, ejecuciones, linaje y validaciones | No altera datasets publicados ni rompe linaje |
| `cci_research_writer` | Registrar experimentos, hipótesis y asociaciones | No cambia datasets ni permisos de adquisición |
| `cci_reader` | Consultar vistas de lectura autorizadas | Sin DML y sin acceso general a tablas base |

Los roles de servicio deben ser NOLOGIN y heredarse desde cuentas LOGIN individuales de servicio cuando se implemente la autenticación. No se compartirán credenciales humanas ni se concederá membresía de escritura al rol lector.

## 5. Lectura por dominio

- **Fuentes, endpoints y políticas:** lectura para adquisición y evaluación; escritura separada entre catálogo y administración/evaluación de políticas.
- **Identidad de activos y redes:** lectura para servicios que resuelven instrumentos y activos; escritura exclusiva del resolvedor mediante funciones de publicación.
- **Instrumentos y metadata:** lectura para adquisición/validación; nuevas observaciones mediante el mapeador.
- **Adquisición:** acceso operativo del servicio de ingestión; investigación no obtiene acceso directo a parámetros o respuestas sensibles.
- **Datasets y procedencia:** lectura interna para autorización y trazabilidad; analistas consultan vistas aprobadas, no tablas base por defecto.
- **Transformación:** el servicio puede registrar sus ejecuciones y linaje; no puede reescribir la evidencia de entrada.
- **Investigación:** acceso a metadatos y asociaciones autorizadas; la lectura del contenido Parquet se controla por separado del permiso SQL.

## 6. Operaciones que deben pasar por funciones transaccionales

1. Evaluar política aplicable y registrar `policy_evaluations` con su snapshot.
2. Registrar una contribución en `dataset_sources` solo si la evaluación está vigente y devuelve `allowed`; la función debe comprobar fuente, endpoint, tipo de dato, uso e instante.
3. Crear una revisión de identidad y su mapping accepted en una única transacción; validar namespace, destino, red, literal y estado.
4. Crear una revisión de plataforma y su identificador de red en una única transacción, con bloqueo por identidad estable.
5. Serializar sucesiones de revisiones para evitar bifurcaciones, ciclos y decisiones incompatibles.
6. Registrar aristas de linaje comprobando ausencia de ciclos bajo concurrencia.
7. Aplicar transiciones válidas de Runs y transformation_runs; impedir reabrir estados terminales.
8. Cambiar retención de datasets con transición auditada; un dataset deleted no vuelve a active.
9. Aplicar transiciones de experimentos e hipótesis sin reescribir sus evidencias previas.

Las funciones deben validar parámetros, fijar un `search_path` seguro, usar nombres de esquema explícitos cuando corresponda, evitar SQL dinámico inseguro y ejecutarse con privilegios mínimos. Si son `SECURITY DEFINER`, su propietario será un rol NOLOGIN dedicado y se revocará EXECUTE a PUBLIC.

## 7. Privilegios que se deniegan por defecto

- `UPDATE` y `DELETE` sobre tablas A, V y B.
- `TRUNCATE` sobre todas las tablas de aplicación.
- DDL y ownership a cualquier servicio de runtime.
- Escritura directa de mappings sin revisión accepted.
- Escritura de procedencia sin evaluación de política.
- Acceso de investigación a tablas internas de credenciales, cabeceras o parámetros sensibles (que además no deben persistirse).
- Acceso directo de analistas a tablas base y a objetos Parquet sin autorización independiente.
- `EXECUTE` público sobre funciones privilegiadas.
- Membresía de roles administrativos para lectores o servicios de ejecución ordinarios.

## 8. Decisiones pendientes antes del DDL de permisos

1. Confirmar si habrá una identidad de base de datos por servicio o si varios procesos compartirán una cuenta técnica; se recomienda una identidad por servicio.
2. Definir qué vistas de lectura constituirán la interfaz SQL de investigación y analítica.
3. Decidir si las funciones transaccionales serán propiedad de `cci_owner` o de roles NOLOGIN dedicados por dominio.
4. Concretar qué campos de Runs, solicitudes, datasets, experimentos e hipótesis cambian durante sus transiciones y cuáles quedan inmutables desde el INSERT.
5. Definir auditoría de cambios administrativos y de retención antes de habilitar esas operaciones.
6. Probar aislamiento entre roles con sesiones reales: operaciones permitidas, operaciones denegadas, invocación de funciones, rollback y concurrencia.
7. Revisar la interacción entre permisos SQL y permisos de almacenamiento Parquet/DuckDB; un SELECT en PostgreSQL no debe implicar acceso automático a archivos.

## 9. Criterio de aprobación

La matriz se considerará aprobada cuando cada rol tenga un propósito único, cada entidad tenga lectura/escritura justificada, todas las mutaciones estén clasificadas como append-only o transición controlada, y cada operación multi-entidad tenga una función transaccional definida.

Solo después se redactará el DDL de roles, esquemas, privilegios por tabla/columna, funciones y vistas. La prueba de seguridad deberá ejecutarse contra PostgreSQL real con sesiones separadas para cada rol.

**Estado final:** inventario y propuesta inicial completados documentalmente. No se han creado roles, grants, funciones SQL ni migraciones; no se ha ejecutado una prueba de autorización en PostgreSQL.
