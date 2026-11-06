# Calidad de datos y evaluación de fuentes

## Propósito

Este documento define los controles iniciales de calidad para observaciones de mercado, documentos, eventos y evidencias de investigación. Las etiquetas de calidad describen propiedades y limitaciones conocidas; no convierten datos inciertos en datos ciertos.

## Dimensiones de validación

### Completitud

Comprobar los campos obligatorios, la cobertura temporal esperada, los intervalos faltantes y los valores ausentes. Distinguir entre valores no proporcionados por la fuente, no aplicables, no disponibles por un fallo de recuperación, retenidos/restringidos y de motivo desconocido.

No sustituir silenciosamente los valores faltantes por cero, ni aplicar forward-fill o interpolación. Cualquier imputación debe ser explícita, contar con una versión independiente y ser adecuada para la tarea de investigación.

### Integridad y validez

Validar tipos, unidades, identificadores, interpretación de marcas de tiempo, dominios numéricos y conformidad con el esquema. Para velas OHLCV, comprobar invariantes aplicables como:

- high no debe ser inferior a open, close o low;
- low no debe ser superior a open, close o high;
- volume debe ser no negativo cuando así lo requiera la definición de la métrica;
- el inicio del intervalo debe preceder a su final;
- los valores deben respetar la precisión y unidad declaradas.

Una comprobación fallida debe generar un resultado de validación o un estado de cuarentena, no descartar silenciosamente el registro de origen.

### Consistencia

Comparar registros a lo largo del tiempo, entre campos relacionados y entre fuentes cuando tenga sentido. Las diferencias entre exchanges, monedas de cotización, métodos de agregación o metodologías de proveedores no son automáticamente errores. Las comparaciones requieren definiciones y unidades compatibles.

### Duplicados

Utilizar IDs nativos de la fuente cuando sean confiables, complementados con claves lógicas de alcance definido y hashes de contenido. Distinguir las recuperaciones duplicadas exactas de las republicaciones legítimas, revisiones y observaciones independientes que casualmente compartan valores.

### Outliers y anomalías

Marcar valores inusuales mediante reglas documentadas y adecuadas al contexto. Preservar la observación original. Un outlier estadístico puede corresponder a un evento real del mercado; por defecto, se prohíbe su eliminación automática. La revisión debe considerar la plataforma, liquidez, condiciones de mercado, intervalos cercanos y fuentes independientes.

### Revisiones y llegadas tardías

Registrar explícitamente los registros corregidos, sustituidos, provisionales y recibidos con retraso. Conservar las versiones anteriores y el momento en que cada versión estuvo disponible. Los datasets de investigación deben declarar la política de revisión que utilizan.

## Evaluación de fuentes

Evaluar las fuentes mediante evidencias documentadas en dimensiones como identidad/responsabilidad del publicador, relación primaria o secundaria con el evento o medición, transparencia de la metodología, cobertura histórica y precisión temporal, consistencia y prácticas de corrección, independencia respecto de fuentes de corroboración, estabilidad de acceso/rate limits/latencia operativa y permisos de licencia/retención/redistribución.

No reducir estas dimensiones a una puntuación universal de confianza sin explicación. Si un flujo de trabajo posterior utiliza valoraciones o rankings, debe revelar los criterios, evidencias, alcance, revisor y limitaciones. Una fuente puede ser confiable para un tipo de dato e inadecuada para otro.

## Gestión de evidencias

Para cada elemento de evidencia, registrar su origen, contexto de extracción, hora de disponibilidad y relación con la afirmación o hipótesis correspondiente. Conservar por separado las evidencias de apoyo, contradicción, explicaciones alternativas, disputas no resueltas y la interpretación del analista respecto del contenido de la fuente.

La corroboración independiente debe evaluarse para determinar si existe independencia real. Varios medios que reproducen un mismo informe original no constituyen necesariamente varias fuentes independientes.

## Estados de calidad

Vocabulario propuesto:

- `valid`: superó las comprobaciones automatizadas aplicables;
- `valid_with_warnings`: puede utilizarse con limitaciones documentadas;
- `quarantined`: requiere revisión antes de su uso normal;
- `rejected`: no es válido para el uso especificado; se conserva el motivo;
- `unknown`: información insuficiente para evaluarlo.

Estos estados dependen del contexto. Un registro rechazado para un uso analítico puede seguir siendo útil como evidencia de lo que publicó una fuente.

## Informes operativos

Cada ejecución de ingesta o transformación debe informar, cuando corresponda, los recuentos de registros recibidos, aceptados, con advertencias, puestos en cuarentena, rechazados, duplicados y revisados. Los informes deben incluir los identificadores de reglas/versiones y ejemplos representativos de los motivos de fallo.

## Salvaguardas de investigación

- Preservar los registros originales y los resultados de validación.
- No equiparar datos faltantes con actividad igual a cero.
- No eliminar outliers sin una regla auditable y una justificación.
- No tratar copias repetidas de un mismo informe como corroboraciones independientes.
- No inferir causalidad únicamente a partir de correlación, confiabilidad de la fuente o proximidad temporal.
- Excluir de los análisis point-in-time la información futura o todavía no disponible.
