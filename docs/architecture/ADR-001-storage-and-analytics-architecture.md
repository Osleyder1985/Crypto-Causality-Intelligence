# ADR-001: Arquitectura de almacenamiento y análisis

- **Estado:** Aceptada para el diseño lógico; implementación pendiente.
- **Fecha:** 2026-11-06.
- **Ámbito:** Crypto Causality Intelligence.
- **Issue relacionado:** #14.

## Contexto

El proyecto necesita conservar evidencia histórica trazable, registrar las operaciones de adquisición e investigación y ejecutar análisis reproducibles sobre datos de mercado y, en fases posteriores, noticias, acontecimientos y calendarios.

La arquitectura debe distinguir los datos originales, los datos normalizados y los conjuntos derivados. También debe respetar las condiciones de uso, almacenamiento, retención y redistribución aplicables a cada proveedor. La aptitud técnica de una fuente no implica autorización para conservar o publicar sus datos.

El repositorio es público y la investigación prevista es privada y no comercial. Ninguna de estas circunstancias concede por sí misma derechos adicionales sobre los datos de terceros.

## Decisión

Se adoptan desde el inicio tres componentes con responsabilidades separadas:

1. **PostgreSQL:** catálogo relacional y registro operativo.
2. **Apache Parquet:** formato de almacenamiento de conjuntos de datos históricos y derivados cuya persistencia esté autorizada.
3. **DuckDB:** motor de consulta y análisis sobre los archivos Parquet.

Python coordinará la adquisición, validación, transformación, escritura y ejecución de consultas. Esta decisión define la arquitectura lógica; no obliga a desplegar servicios cloud ni determina todavía el mecanismo concreto de instalación o alojamiento de PostgreSQL.

## Responsabilidades y límites

### PostgreSQL — catálogo y operaciones

Almacenará información relacional y operativa, por ejemplo:

- Registro de proveedores, fuentes, endpoints e instrumentos.
- Estado documentado de autorización, restricciones y políticas de retención por fuente.
- Registro de ejecuciones (*Runs*), parámetros, versiones de código y protocolos.
- Estado de adquisición, validación y transformación.
- Referencias a datasets, rutas de almacenamiento, versiones de esquema y hashes.
- Registro de experimentos, hipótesis y resultados de investigación, cuando corresponda.

PostgreSQL no será el almacén principal de las series históricas OHLCV ni una copia paralela de los archivos Parquet. Los registros operativos deberán referenciar los artefactos mediante identificadores estables, versiones y hashes.

### Apache Parquet — conjuntos de datos

Se utilizará para conservar, cuando esté permitido:

- Capturas originales o representaciones fieles de datos de proveedores.
- Datos normalizados y canónicos.
- Conjuntos derivados para investigación.
- Resultados analíticos que deban conservarse como artefactos reproducibles.

Los datos originales, normalizados y derivados permanecerán separados. Los artefactos históricos autorizados serán inmutables: una corrección generará una nueva versión, no una sobrescritura silenciosa.

Los archivos se organizarán mediante particiones justificadas por proveedor, mercado, intervalo y tiempo. El diseño evitará particiones excesivamente pequeñas y no impondrá una estructura física definitiva antes de medir los volúmenes reales.

### DuckDB — análisis

DuckDB será el motor analítico principal para:

- Consultar archivos Parquet mediante SQL.
- Alinear series temporales y construir ventanas de acontecimientos.
- Calcular métricas, comparaciones y variables derivadas.
- Ejecutar análisis exploratorios y validaciones reproducibles.

DuckDB no será el catálogo maestro de fuentes ni el registro transaccional de operaciones. Sus bases de trabajo o archivos temporales no sustituirán los artefactos versionados de Parquet ni los registros operativos de PostgreSQL.

### Python — orquestación

Python coordinará los componentes y aplicará las reglas de validación. Cada transformación deberá identificar sus entradas, versión de código, parámetros, versión de esquema y resultado verificable.

## Flujo lógico

1. Python obtiene datos de una fuente autorizada para el uso previsto.
2. PostgreSQL registra la ejecución, fuente, parámetros y estado.
3. La capa de validación comprueba estructura, unidades, timestamps, duplicados, cobertura y reglas específicas del proveedor.
4. Si la persistencia está autorizada, los datos se escriben como artefactos Parquet separados por etapa y con trazabilidad.
5. PostgreSQL registra la ubicación lógica, versión, hash y resultado de validación del artefacto.
6. DuckDB consulta los conjuntos Parquet para producir análisis y datasets derivados.
7. Los resultados relevantes se conservan como artefactos reproducibles y se registran en PostgreSQL.

Una autorización desconocida, pendiente o denegada bloqueará la persistencia de los valores afectados. La política deberá aplicarse por proveedor, producto, endpoint, tipo de dato y uso; no se asumirá una autorización global.

## Reglas de integridad y trazabilidad

- Todos los timestamps canónicos se normalizarán a UTC, conservando cuando sea necesario el valor y la zona horaria originales.
- Los identificadores de mercado conservarán la distinción entre activos y cotizaciones; por ejemplo, USD y USDT no son equivalentes.
- Los datos agregados de un proveedor no se etiquetarán como datos originales de un exchange.
- Cada dataset tendrá un identificador, versión de esquema, etapa, fuente o conjunto de fuentes, ventana temporal y hash.
- Las transformaciones registrarán entradas, código, parámetros y reglas aplicadas.
- Los huecos no se rellenarán silenciosamente ni se mezclarán proveedores en la capa original.
- Las credenciales y secretos no se almacenarán en Git ni en los artefactos de investigación.
- La retención y eliminación se definirán por fuente y por las condiciones aplicables.
- GitHub se utilizará para código y documentación, no como almacén de series históricas.

## Consecuencias positivas

- Separa las operaciones transaccionales del análisis histórico.
- Permite consultar grandes conjuntos Parquet sin duplicarlos en PostgreSQL.
- Mantiene un catálogo relacional para procedencia, ejecuciones y relaciones entre entidades.
- Favorece la reproducibilidad y la auditoría de experimentos.
- Permite incorporar posteriormente noticias, eventos y calendarios sin mezclarlos con las observaciones de mercado.
- Mantiene abierta la evolución de la infraestructura sin cambiar el formato de los datasets.

## Costes y riesgos aceptados

- Operar tres componentes aumenta la complejidad de configuración, pruebas, copias de seguridad y observabilidad.
- PostgreSQL requiere administración de esquema, roles, migraciones, respaldos y recuperación.
- Parquet no proporciona por sí mismo transacciones ni un catálogo de datasets.
- DuckDB está optimizado para analítica local y no sustituye un servidor multiusuario de propósito general. La concurrencia de escritores y el acceso compartido a archivos deberán controlarse explícitamente.
- La consistencia entre PostgreSQL y Parquet no será una transacción distribuida. Se utilizará un flujo recuperable: registrar estados, escribir artefactos de forma segura, verificar hashes y confirmar referencias; los procesos incompletos deberán poder detectarse y reconciliarse.
- Se deberán probar los límites de memoria, tamaño de archivos, particionamiento y rendimiento con cargas representativas antes de fijar parámetros físicos.

## Alternativas consideradas

### PostgreSQL como único almacenamiento

No se elige como solución única porque mezclaría el registro operativo con grandes conjuntos históricos y analíticos, y no aporta por sí solo las ventajas de un formato columnar portable como Parquet.

### Parquet + DuckDB sin PostgreSQL

Es una alternativa técnicamente válida y más sencilla para una herramienta local de un solo operador. No se elige porque el proyecto ha decidido contar desde el inicio con un catálogo relacional y un registro operativo explícito, preparado para mayor concurrencia y relaciones entre entidades.

### PostgreSQL + Parquet sin DuckDB

No se elige porque DuckDB ofrece un motor especializado para consultas analíticas sobre Parquet, reduciendo la necesidad de cargar o duplicar los datasets históricos en PostgreSQL.

## Alcance pendiente antes de implementar

Esta decisión no aprueba todavía:

- Persistir datos de Binance, Kraken o CoinGecko cuya autorización o retención siga sin resolverse.
- Recuperar, volver a publicar o eliminar artefactos históricos.
- Contratar infraestructura o servicios gestionados.
- Definir credenciales, despliegue cloud o exposición pública de PostgreSQL.
- Fijar el esquema físico final, índices, particiones o tamaños de archivo sin pruebas.

## Próximos entregables

1. Modelo lógico de entidades y relaciones de PostgreSQL.
2. Esquemas canónicos versionados para datos de mercado y metadata.
3. Convenciones de directorios, nombres, particiones y manifiestos Parquet.
4. Protocolo de escritura, verificación, recuperación y reconciliación entre PostgreSQL y Parquet.
5. Integración de DuckDB y pruebas reproducibles sobre datasets de prueba sintéticos o autorizados.
6. Política de acceso, respaldo, retención y eliminación.
7. Criterios de aceptación y plan incremental de implementación.

## Criterio de revisión

Revisar esta decisión si cambian materialmente el volumen, la concurrencia, los requisitos de despliegue, las licencias de las fuentes o las necesidades de consulta. Cualquier sustitución o incorporación de componentes deberá justificarse mediante una nueva decisión documentada.
