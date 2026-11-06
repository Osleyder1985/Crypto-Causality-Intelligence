# Protocolo de validación de datos históricos para BTC y ETH

## 1. Propósito

Definir un procedimiento reproducible para evaluar la calidad, cobertura y comparabilidad de datos históricos de BTC y ETH obtenidos de los proveedores identificados en el [catálogo de fuentes](source-catalog.md).

El protocolo está orientado a una primera prueba de concepto (PoC). Dos exchanges, o un exchange y un agregador, no tienen por qué producir valores idénticos: cada serie debe interpretarse según su mercado, instrumento y metodología.

## 2. Alcance

### Incluido
- Datos históricos de mercado de BTC y ETH.
- Velas OHLCV diarias y horarias, cuando estén disponibles.
- Comparación de Binance Spot con un segundo exchange y una fuente agregada.
- Procedencia, integridad temporal y controles de calidad.
- Una métrica on-chain o DeFi solo si se justifica su relación con la investigación.

### Fuera de alcance
- Fuentes de noticias, anuncios, eventos, redes sociales y calendarios.
- Conectores productivos o infraestructura permanente de ingestión.
- Descargas masivas y contratación de planes.
- Señales de trading, predicción de precios y evaluación de estrategias.

## 3. Diseño del conjunto de prueba

### 3.1 Activos e instrumentos

| Activo | Identificador | Instrumento inicial |
|---|---|---|
| Bitcoin | BTC | Spot contra USD o stablecoin cotizada |
| Ethereum | ETH | Spot contra USD o stablecoin cotizada |

El símbolo no identifica por sí solo un mercado. Cada observación debe conservar el proveedor, el identificador exacto del producto y la moneda cotizada. No combinar pares distintos como si fueran una misma serie.

Coinbase Exchange y Kraken permanecen como candidatos para el segundo exchange hasta verificar cobertura, granularidad y límites para el periodo elegido.

### 3.2 Periodo y granularidad

El periodo será un parámetro explícito del experimento, con inicio y fin expresados en UTC. Debe ser común a las fuentes comparadas. Se evaluarán intervalos de una hora y un día cuando estén disponibles.

La granularidad nativa debe registrarse. Una serie diaria derivada de velas horarias se identificará como derivada y no como vela diaria nativa.

### 3.3 Fuentes candidatas

| Función | Fuente | Uso |
|---|---|---|
| Referencia primaria | Binance Spot API | Serie de mercado de referencia |
| Contraste de exchange | Coinbase Exchange o Kraken | Comparación entre venues |
| Contraste agregado | CoinGecko | Comparación metodológica y de cobertura |
| Contexto opcional | DefiLlama | Solo para una métrica on-chain/DeFi justificada |

No se presupone que todas las fuentes ofrezcan el mismo instrumento, periodo o granularidad. Las diferencias deben registrarse antes de calcular métricas comparativas.

## 4. Esquema mínimo de datos

| Campo | Tipo lógico | Descripción |
|---|---|---|
| provider | string | Proveedor |
| endpoint | string | Endpoint o recurso consultado |
| asset | string | BTC o ETH |
| market_id | string | Identificador exacto del mercado |
| base_asset / quote_asset | string | Activo base y cotizado |
| interval | string | Granularidad original |
| open_time_utc | timestamp | Inicio de la vela en UTC |
| close_time_utc | timestamp/null | Cierre según semántica del proveedor |
| open, high, low, close | decimal | Precios OHLC |
| volume | decimal | Volumen |
| volume_unit | string | Unidad del volumen |
| source_timestamp_unit | string | Unidad original del timestamp |
| retrieved_at_utc | timestamp | Momento de captura |
| query_parameters | object | Parámetros relevantes de la solicitud |

Conservar precisión numérica suficiente. No redondear durante la ingestión. La normalización no debe eliminar los valores originales ni la semántica del proveedor.

## 5. Procedimiento

1. **Congelar el diseño:** registrar activos, mercados, proveedores, endpoints, periodo UTC y granularidades.
2. **Revisar capacidades:** documentar límites, paginación, retención, restricciones de plan y semántica de timestamps.
3. **Obtener una muestra acotada:** usar el mismo periodo lógico y conservar la respuesta original o evidencia verificable, respetando términos y licencias.
4. **Normalizar sin pérdida:** convertir timestamps a UTC y unidades a un formato común, conservando valores y metadatos originales.
5. **Ejecutar controles:** aplicar la matriz de la sección 6 por proveedor, mercado, activo e intervalo.
6. **Comparar series compatibles:** comparar el mismo instrumento y ventana; separar diferencias entre venues de defectos de integridad.
7. **Registrar resultados:** guardar métricas, incidencias, exclusiones, parámetros y limitaciones.
8. **Emitir conclusión:** clasificar cada fuente como apta, apta con reservas o no apta para el uso evaluado.

## 6. Matriz de controles

Los criterios siguientes son reglas iniciales de revisión, no garantías universales. Antes de ejecutar la PoC deben confirmarse contra la documentación y semántica de cada endpoint. Toda excepción debe justificarse en el reporte.

| Control | Método | Severidad | Criterio inicial |
|---|---|---|---|
| Cobertura temporal | Comparar registros recibidos con los esperados para intervalo y límites | Alta | Toda diferencia debe explicarse |
| Timestamps inválidos | Validar parseo, unidad, UTC y rango | Crítica | Cero timestamps inválidos o fuera de ventana |
| Orden cronológico | Comprobar monotonía de open_time_utc | Alta | Registrar cualquier desorden original |
| Duplicados | Contar claves repetidas por proveedor, mercado, intervalo y apertura | Alta | Cero duplicados no explicados |
| Huecos | Comparar aperturas consecutivas con el intervalo esperado | Alta | Cada hueco debe clasificarse |
| Consistencia OHLC | Verificar low <= open/close <= high y low <= high | Crítica | Cero violaciones |
| Volumen | Detectar negativos, nulos, ausentes y unidad desconocida | Alta | Cero negativos; interpretar nulos/cero |
| Agregación | Comparar velas derivadas con nativas | Alta | Diferencias cuantificadas y explicadas |
| Comparabilidad | Alinear instrumento, quote asset, periodo e intervalo | Alta | No comparar series incompatibles |
| Procedencia | Verificar proveedor, endpoint, parámetros y captura | Alta | Metadatos suficientes para repetir consulta |
| Respuesta API | Registrar paginación, errores, reintentos y límites | Media | Ningún truncamiento oculto |
| Latencia | Medir duración de solicitud | Media | Reportar valores observados |

### 6.1 Conteo de velas esperadas

Para un intervalo fijo de duración Δt, con límites alineados, inicio inclusivo y fin exclusivo:

N_esperado = (t_fin - t_inicio) / Δt

La fórmula solo aplica si el endpoint devuelve una vela por intervalo, incluso cuando no hay operaciones. Si el proveedor omite velas sin trades, el conteo debe ajustarse a su semántica documentada; la ausencia no puede etiquetarse automáticamente como pérdida de datos.

### 6.2 Clasificación de huecos

Clasificar cada hueco, cuando exista evidencia, como:
- no_trades: el proveedor confirma que no hubo operaciones y omite la vela.
- api_limit: posible truncamiento por límites, paginación o ventana máxima.
- market_unavailable: el mercado o instrumento no estaba disponible.
- unknown_gap: causa no determinada.

No rellenar huecos mediante forward-fill, interpolación o copia de otra fuente en el conjunto original. Toda serie reparada debe ser un artefacto derivado con regla y procedencia explícitas.

### 6.3 Comparación entre proveedores

Las diferencias de precio y volumen entre exchanges pueden ser legítimas por liquidez, composición del mercado, spreads, profundidad, moneda cotizada y metodología. CoinGecko agrega mercados según sus propias reglas y no representa necesariamente un venue concreto.

- Comparar primero el mismo par y granularidad.
- Si la moneda cotizada difiere, documentar la conversión y su fuente.
- Alinear timestamps según la hora de apertura y la convención de cierre.
- Calcular diferencias absolutas y relativas solo sobre observaciones alineadas.
- Reportar mediana, percentil 95 y máximo; investigar extremos.
- No tratar un agregador como verdad de referencia universal frente a un exchange.

## 7. Métricas del reporte

Por proveedor, mercado, activo e intervalo, reportar:
- Registros recibidos y esperados, cuando aplique.
- Porcentaje de cobertura y fórmula utilizada.
- Timestamps inválidos, duplicados y registros fuera de rango.
- Número y duración de huecos por clasificación.
- Violaciones de consistencia OHLCV.
- Errores API, reintentos y páginas solicitadas.
- Tiempo de respuesta observado.
- Diferencias entre series compatibles: mediana, percentil 95 y máximo de diferencias absolutas y relativas.
- Limitaciones conocidas y evidencia de cada conclusión.

No publicar una puntuación compuesta única sin justificar sus ponderaciones. Las observaciones empíricas deben permanecer visibles.

## 8. Registro de ejecución y reproducibilidad

Cada ejecución debe registrar:
- Identificador único y fecha/hora UTC.
- Proveedor, endpoint y versión de API/documentación consultada.
- Activo, mercado, intervalo y límites temporales.
- Parámetros de consulta, paginación y límites relevantes.
- Unidad y semántica de timestamps.
- Estado de respuesta, errores y reintentos.
- Hora de recuperación y, si aplica, hash del archivo de respuesta.
- Versión del protocolo y del código de validación, cuando exista.
- Licencia, restricciones de uso y condiciones de retención verificadas.

Ejemplo ilustrativo; los valores son marcadores de posición y no representan una consulta ejecutada:

~~~json
{
  "run_id": "btc-eth-validation-001",
  "protocol_version": "1.0",
  "provider": "example-provider",
  "endpoint": "documented-endpoint",
  "asset": "BTC",
  "market_id": "BTC-QUOTE",
  "interval": "1h",
  "start_time_utc": "YYYY-MM-DDT00:00:00Z",
  "end_time_utc": "YYYY-MM-DDT00:00:00Z",
  "retrieved_at_utc": "YYYY-MM-DDTHH:MM:SSZ",
  "timestamp_unit": "milliseconds",
  "result_status": "pending"
}
~~~

## 9. Clasificación de resultados

| Estado | Regla |
|---|---|
| suitable | Los controles críticos pasan, las incidencias están explicadas y la procedencia permite reproducir la consulta |
| suitable_with_reservations | La fuente puede utilizarse con exclusiones o limitaciones documentadas |
| not_suitable | Hay defectos críticos, cobertura insuficiente o falta de trazabilidad esencial |
| not_evaluated | No existe evidencia suficiente para emitir una conclusión |

La clasificación se asigna por caso de uso, activo, mercado e intervalo; no como atributo absoluto del proveedor.

## 10. Decisiones pendientes antes de ejecutar la PoC

- Elegir Coinbase Exchange o Kraken como segundo exchange.
- Fijar el periodo común de evaluación.
- Confirmar los pares exactos y la moneda cotizada.
- Verificar semántica de velas sin operaciones y límites de cada endpoint.
- Determinar si se necesita una métrica on-chain/DeFi y justificarla.
- Confirmar licencias y condiciones de almacenamiento y redistribución.

## 11. Referencias internas

- [Catálogo de fuentes históricas](source-catalog.md)

Las referencias técnicas externas y las limitaciones específicas de cada endpoint deben mantenerse en el catálogo y revisarse antes de ejecutar la prueba.
