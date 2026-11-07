# Seguridad PostgreSQL: roles, privilegios y grants

- **Identificador:** CCI-DB-SECURITY-ROLES
- **Versión:** 0.1
- **Estado:** propuesta de diseño para revisión; no ejecutada.
- **Fecha:** 2026-11-06.
- **Ámbito:** PostgreSQL, esquema productivo `cci`.
- **Relacionado:** `provider-platform-subsystem-contract.md`, secciones 4 y 7; `postgresql-physical-schema.md`.

## 1. Objetivo y principios

Definir separación de responsabilidades y privilegio mínimo para que las credenciales de ejecución no puedan alterar catálogos protegidos, reescribir evidencia histórica ni eludir el protocolo transaccional de resolución.

Principios obligatorios:

1. **Denegar por defecto:** ningún rol de aplicación recibe privilegios por ser miembro de `PUBLIC`; se revocan los grants públicos relevantes.
2. **Separar login de autoridad:** los roles de permisos son `NOLOGIN`; los usuarios/credenciales de despliegue y servicios se asignan por entorno y se agregan a los grupos necesarios.
3. **Propiedad aislada:** las tablas y el esquema pertenecen a un rol propietario `NOLOGIN`; ningún servicio de runtime es propietario ni miembro de ese rol.
4. **Sin privilegios elevados en runtime:** roles de aplicación no son superuser, no tienen `BYPASSRLS`, `CREATEDB`, `CREATEROLE`, `REPLICATION` ni `CREATE` en `cci` o `public`.
5. **Escritura mediante interfaces controladas:** operaciones que exigen invariantes multi-fila o lock explícito se realizan mediante funciones API con permisos limitados; no se exponen INSERT directos que permitan saltarse el protocolo.
6. **Históricos append-only:** ingestión y revisión no reciben `UPDATE` ni `DELETE` sobre observaciones, revisiones o mappings históricos.
7. **No confundir roles SQL con actores humanos:** la identidad del usuario/servicio que ejecuta una decisión debe registrarse en el payload de auditoría de la operación; el rol SQL identifica el servicio, no necesariamente a la persona.

## 2. Roles propuestos

Todos los roles de esta tabla son roles de grupo `NOLOGIN`. Las credenciales de conexión reales serán roles LOGIN separados, específicos por entorno, fuera del repositorio.

| Rol | LOGIN | Responsabilidad | Prohibiciones |
|---|---:|---|---|
| `cci_owner` | No | Propietario del esquema `cci`, tablas, secuencias, vistas y objetos estructurales; ejecuta cambios DDL mediante el proceso de migración | No se usa en servicios ni tareas ordinarias |
| `cci_api_owner` | No | Propietario de funciones API `SECURITY DEFINER`; recibe solo los privilegios mínimos necesarios para ejecutar operaciones controladas | No es propietario de tablas/esquema; no tiene CREATE en `cci`; no es credencial de conexión |
| `cci_ingest` | No | Ingesta de capturas y observaciones, creación de identidades de plataforma cuando proceda, lectura de catálogos de referencia | No decide mappings accepted; no actualiza ni elimina históricos; no ejecuta funciones de revisión |
| `cci_reviewer` | No | Solicita decisiones de identidad y publicación/revocación mediante funciones transaccionales autorizadas | No inserta directamente en revisiones ni mappings; no modifica ni elimina históricos |
| `cci_reader` | No | Lectura de vistas/catálogos aprobados para aplicación y consultas operativas | Sin INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER ni CREATE |
| `cci_analyst` | No | Lectura de vistas analíticas autorizadas y metadatos no sensibles, si el caso de uso se aprueba | Sin escritura; no se concede acceso indiscriminado a tablas operativas |

No se crea un rol genérico `cci_app` con privilegios amplios. Una misma identidad de servicio puede pertenecer a más de un grupo solo si existe una necesidad demostrada y documentada. Se prefiere separar credenciales por proceso.

## 3. Propiedad, migraciones y membresías

- `cci_owner` es propietario de `SCHEMA cci` y de los objetos persistentes del esquema.
- Las migraciones se ejecutan desde una identidad de despliegue autenticada que pueda asumir `cci_owner` mediante un flujo explícito y auditado. La credencial de despliegue no se comparte con servicios.
- Ningún rol runtime recibe membresía de `cci_owner` o `cci_api_owner`.
- `cci_api_owner` es propietario solo de las funciones API `SECURITY DEFINER`. Recibe privilegios DML puntuales sobre tablas específicas; no recibe propiedad de esas tablas.
- Las credenciales LOGIN no se guardan en Git, archivos de configuración versionados ni imágenes. Se inyectan desde el gestor de secretos del entorno.
- No conceder membresías con capacidad de `SET ROLE` hacia `cci_owner` o `cci_api_owner` a usuarios de runtime.
- Los cambios de membresía, grants y ownership son cambios de seguridad revisables, no efectos secundarios de una migración funcional.

## 4. Matriz de acceso por objeto

### 4.1 Subsistema de identidad de plataformas

| Objeto | owner | api_owner | ingest | reviewer | reader |
|---|---|---|---|---|---|
| `data_sources` | DDL/DML | SELECT | SELECT | SELECT | SELECT vía vista |
| `networks` | DDL/DML | SELECT | SELECT | SELECT | SELECT vía vista |
| `provider_platforms` | DDL/DML | SELECT/INSERT limitado por API | SELECT/INSERT | SELECT | SELECT vía vista |
| `provider_platform_observations` | DDL/DML | SELECT/INSERT por API | SELECT/INSERT | SELECT | SELECT vía vista |
| `provider_platform_resolution_reviews` | DDL/DML | SELECT/INSERT por API | SELECT | SELECT vía API/vista | SELECT vía vista |
| `network_identifiers` | DDL/DML | SELECT/INSERT por API | SELECT | SELECT vía API/vista | SELECT vía vista |
| Vistas current / mappings | DDL | SELECT | SELECT | SELECT | SELECT |
| Función de captura/ingesta | DDL | OWNER/EXECUTE | EXECUTE si se adopta | No | No |
| Función de revisión/publicación | DDL | OWNER/EXECUTE | No | EXECUTE | No |
| Función bitemporal de lectura | DDL | OWNER/EXECUTE | EXECUTE según necesidad | EXECUTE | EXECUTE |

**Notación:** DDL/DML solo para el propietario durante migraciones y mantenimiento autorizado; no es una concesión de runtime. Las operaciones de revisión y publicación no se hacen mediante INSERT directo del rol `cci_reviewer`.

### 4.2 Alcance de la matriz para las 34 entidades

Esta matriz es normativa para el subsistema NET-PLATFORM y define el patrón global, pero **no autoriza aún grants sobre las otras 28 entidades**. Antes de crear grants de producción se debe clasificar cada tabla en un inventario con:
- dominio y sensibilidad;
- propietario;
- roles con SELECT;
- rol/es de escritura;
- operaciones permitidas (INSERT/UPDATE/DELETE);
- si es append-only;
- vistas/API autorizadas;
- restricciones de retención y auditoría.

Regla inicial para el resto del esquema: sin grants de runtime hasta que la tabla tenga clasificación y caso de uso aprobados. No se debe resolver el faltante concediendo `GRANT SELECT ON ALL TABLES` ni `GRANT ALL` al rol de aplicación.

## 5. Escritura protegida mediante funciones API

### 5.1 Ingesta

- El rol `cci_ingest` puede crear la identidad estable de plataforma y añadir snapshots mediante una función o conjunto de sentencias acotado por transacción.
- Puede recibir INSERT directo solo en tablas donde el contrato no requiera una operación compuesta no eludible; la opción preferida es función API para validar `data_source_id`, idempotencia de lote y procedencia.
- `provider_platform_observations` es INSERT-only para ingestión; no se concede UPDATE, DELETE ni TRUNCATE.
- La ingestión no puede insertar reviews ni mappings.

### 5.2 Revisión y publicación

El rol `cci_reviewer` recibe EXECUTE únicamente sobre funciones específicas, por ejemplo:
- `cci.api_record_platform_review(...)` para registrar una decisión no accepted;
- `cci.api_accept_platform_mapping(...)` para aceptación y publicación atómica;
- `cci.api_revoke_platform_mapping(...)` para insertar una sucesora no accepted.

Nombres y firmas son ilustrativos y deben cerrarse al diseñar el repositorio. El contrato obligatorio de la función accepted:

1. validar parámetros y evidencia;
2. iniciar/participar en una transacción controlada por el caller, sin ejecutar COMMIT dentro de la función;
3. bloquear `provider_platforms` con `SELECT ... FOR UPDATE` como sentencia separada de cualquier INSERT;
4. releer la cabeza actual después de adquirir el lock;
5. validar que la decisión nueva sucede a la cabeza esperada;
6. insertar la review accepted;
7. insertar el mapping con la misma red, proveedor, literal y review;
8. propagar cualquier error para que la transacción haga ROLLBACK.

La función no debe confiar en un parámetro `supersedes_review_id` sin verificar la cabeza tras el lock. Debe rechazar publicaciones basadas en una cabeza obsoleta.

## 6. SECURITY DEFINER: controles obligatorios

Las funciones `SECURITY DEFINER` elevan privilegios al propietario de la función; por tanto, solo se usarán cuando el flujo controlado lo justifique.

Cada función debe:
- pertenecer a `cci_api_owner`, nunca a un rol LOGIN;
- declarar un `search_path` fijo y seguro, por ejemplo `pg_catalog, cci, pg_temp`, con `cci` sin CREATE para roles no confiables;
- preferir referencias schema-qualified a tablas y funciones;
- validar todos los parámetros y no concatenar SQL dinámico con entrada no confiable;
- revocar EXECUTE de `PUBLIC` y concederlo explícitamente al grupo de aplicación pertinente;
- no aceptar identificadores de actor falsificables como única evidencia de autoría; obtener la identidad autenticada del contexto de conexión o de un mecanismo de auditoría confiable;
- tener pruebas negativas de escalada, acceso cruzado y manipulación de argumentos;
- evitar que una función auxiliar concedida a `PUBLIC` permita invocar rutas privilegiadas.

No se usará `SECURITY DEFINER` como sustituto de un diseño correcto de transacciones o de restricciones SQL.

## 7. Esquema, search_path y privilegios públicos

Al preparar DDL productivo:
- revocar `CREATE` en `SCHEMA cci` a `PUBLIC` y a todos los roles runtime;
- revocar `CREATE` en `SCHEMA public` a `PUBLIC` cuando la política de la instancia lo permita y verificar extensiones que dependan de él;
- conceder `USAGE` en `cci` solo a los roles que necesiten resolver objetos;
- no conceder `CREATE` en `cci` a `cci_ingest`, `cci_reviewer`, `cci_reader` o `cci_analyst`;
- configurar `search_path` por rol/base de datos de forma explícita y no depender del default del servidor;
- no usar nombres de objetos no cualificados dentro de funciones privilegiadas salvo que el `search_path` esté fijado y probado.

La política definitiva para `public` debe comprobar la versión y configuración de PostgreSQL y las extensiones que se instalen; no se asume que revocar CREATE sea inocuo en cualquier instalación.

## 8. Privilegios por defecto y objetos futuros

El proceso de migración debe configurar privilegios por defecto para el rol que crea objetos. Como política, los nuevos objetos no reciben automáticamente permisos de aplicación. Los grants se conceden explícitamente tras clasificar el objeto.

La migración debe revisar:
- `ALTER DEFAULT PRIVILEGES FOR ROLE cci_owner IN SCHEMA cci REVOKE ALL ON TABLES FROM PUBLIC`;
- privilegios por defecto de secuencias;
- `EXECUTE` por defecto de funciones (PostgreSQL concede EXECUTE a PUBLIC en funciones nuevas salvo revocación);
- ownership de vistas, funciones y tipos;
- grants explícitos a roles runtime después de crear cada objeto.

La sintaxis exacta y el orden se verificarán en el DDL integrado y con consultas a `information_schema` y `pg_catalog`; esta propuesta no es un script ejecutable.

## 9. TRUNCATE, secuencias y funciones

- Ningún rol runtime recibe `TRUNCATE`, `REFERENCES` o `TRIGGER`.
- Los roles de ingestión/revisión no reciben privilegio de secuencias salvo que el diseño físico use secuencias; el modelo actual usa UUID y no requiere grants de secuencia por defecto.
- No conceder `EXECUTE ON ALL FUNCTIONS` indiscriminadamente.
- Las funciones API se conceden por firma exacta.
- Las vistas se conceden individualmente; no se concede acceso base-table por comodidad.
- No se usa `GRANT ALL ON ALL TABLES IN SCHEMA cci` para roles de aplicación.

## 10. Row-Level Security

RLS no se activa globalmente por defecto en esta fase. Las entidades actuales no tienen un modelo multi-tenant/ownership por usuario completamente definido en el contrato físico. Activar RLS sin política completa podría generar una falsa sensación de aislamiento o bloquear procesos válidos.

RLS se evaluará si se introduce separación por tenant, proyecto o propietario de datos. En ese caso:
- definir primero la clave de aislamiento y el contexto de identidad confiable;
- activar y forzar RLS donde proceda;
- probar propietario, superusuario y roles BYPASSRLS como excepciones privilegiadas;
- no considerar RLS un sustituto de grants y separación de roles.

## 11. Pruebas de seguridad obligatorias

Las pruebas deben ejecutarse con roles reales no superuser en PostgreSQL, no solo como propietario del laboratorio.

| ID | Prueba | Resultado exigido |
|---|---|---|
| SEC-01 | `cci_ingest` intenta UPDATE/DELETE de observaciones | Permiso denegado |
| SEC-02 | `cci_ingest` intenta INSERT de review o mapping | Permiso denegado |
| SEC-03 | `cci_reviewer` intenta INSERT directo en reviews/mappings | Permiso denegado; solo EXECUTE API |
| SEC-04 | `cci_reviewer` ejecuta función accepted válida | Review + mapping atómicos |
| SEC-05 | Fallo durante publicación accepted | ROLLBACK de ambos registros |
| SEC-06 | Dos revisores compiten por la misma cabeza | Serialización; la segunda relee y rechaza cabeza obsoleta |
| SEC-07 | `cci_reader` intenta cualquier DML | Permiso denegado |
| SEC-08 | Rol runtime intenta CREATE en `cci` o `public` | Permiso denegado |
| SEC-09 | Rol runtime intenta TRUNCATE | Permiso denegado |
| SEC-10 | Rol runtime intenta SET ROLE a `cci_owner`/`cci_api_owner` | No autorizado |
| SEC-11 | Función API invocada por rol no autorizado | EXECUTE denegado |
| SEC-12 | Función SECURITY DEFINER recibe nombre/SQL malicioso | No hay inyección ni resolución de objeto fuera del esquema |
| SEC-13 | Función privilegiada intenta acceder a objeto temporal homónimo | No puede secuestrar resolución por search_path |
| SEC-14 | Objeto nuevo creado por migración | No obtiene grants públicos ni runtime implícitos |
| SEC-15 | Runtime consulta vistas autorizadas | SELECT permitido sin acceso a tablas base no concedidas |
| SEC-16 | Catálogo de roles | Ningún rol runtime tiene superuser, BYPASSRLS, CREATEROLE, CREATEDB o REPLICATION |

Las pruebas SEC-01–SEC-16 se integrarán al workflow de PostgreSQL real una vez que exista el DDL de seguridad y los roles del laboratorio. No se ejecutan en esta etapa documental.

## 12. Decisiones pendientes antes de DDL productivo

1. Completar el inventario de acceso para las 34 entidades.
2. Cerrar si la ingestión de plataformas se hará mediante INSERT acotado o función API; no cambia el contrato append-only.
3. Definir cómo se obtiene y conserva el actor humano/servicio que aprueba una revisión.
4. Definir las credenciales LOGIN por entorno, rotación y gestor de secretos; nunca incluir secretos en Git.
5. Verificar extensiones PostgreSQL y política de `public` en la instancia objetivo.
6. Definir auditoría de DDL, grants, cambios de membresía y operaciones administrativas privilegiadas.
7. Diseñar y probar funciones API con `SECURITY DEFINER` antes de conceder EXECUTE a `cci_reviewer`.

## 13. Estado y límites

Esta es una propuesta de roles y grants. No crea roles, usuarios, funciones, grants ni políticas RLS. No es una migración SQL. No se ha ejecutado en PostgreSQL. No autoriza cambios de privilegios en una instancia compartida.

La próxima etapa debe completar el inventario de permisos de las 34 entidades y el contrato de auditoría de actor antes de producir DDL ejecutable. El PR #16 permanece Draft.
