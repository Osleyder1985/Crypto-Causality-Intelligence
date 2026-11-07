# BTC/USDT — manifiesto de cobertura histórica Binance Spot

- Estado: **DISEÑO CONGELADO; COBERTURA EMPÍRICA RECONCILIADA (100%)**
- Fecha de preparación: 2026-11-06
- Cohorte: episodios BTC/USDT comunicados por el usuario
- Fuente primaria: Binance Spot REST API
- Instrumento: `BTCUSDT`
- Granularidad primaria: `1h`
- Zona horaria de origen de los límites: UTC-05:00
- Zona horaria canónica de consulta y almacenamiento: UTC

## 1. Objetivo

Definir exactamente las ventanas históricas y registrar la evidencia empírica de cobertura Binance Spot. La descarga y reconciliación descritas en la sección 7 se completaron el 2026-11-07.

## 2. Ventanas congeladas

Los límites se interpretan como intervalos semiabiertos: inicio inclusivo y final exclusivo. Todos los límites están alineados con la hora UTC y con la apertura de velas de una hora.

| Episodio | Inicio UTC-05:00 | Final UTC-05:00 | Inicio UTC | Final UTC | Velas 1h esperadas |
|---|---|---|---|---|---:|
| Caída 1 | 2025-10-06 12:00 | 2025-11-21 07:00 | 2025-10-06 17:00Z | 2025-11-21 12:00Z | 1,099 |
| Caída 2 | 2026-01-14 15:00 | 2026-02-05 19:00 | 2026-01-14 20:00Z | 2026-02-06 00:00Z | 532 |
| Subida 1 | 2026-02-05 19:00 | 2026-05-06 04:00 | 2026-02-06 00:00Z | 2026-05-06 09:00Z | 2,145 |
| Caída 3 | 2026-05-06 04:00 | 2026-06-30 20:00 | 2026-05-06 09:00Z | 2026-07-01 01:00Z | 1,336 |
| Subida 2 | 2026-08-16 16:00 | 2026-09-21 16:00 | 2026-08-16 21:00Z | 2026-09-21 21:00Z | 864 |
| **Total** | | | | | **5,976** |

Los episodios son ventanas separadas. No se deben descargar ni analizar como si el periodo completo entre octubre de 2025 y septiembre de 2026 fuera una única tendencia continua. Los intervalos intermedios permanecen fuera de esta cohorte hasta que se clasifiquen con evidencia.

## 3. Endpoint y semántica

Endpoint documentado: `GET https://data-api.binance.vision/api/v3/klines`.

Parámetros de la prueba:
- `symbol=BTCUSDT`
- `interval=1h`
- `startTime`: apertura UTC inclusiva, Unix epoch en milisegundos
- `endTime`: último milisegundo anterior al límite final exclusivo
- `limit=1000` como máximo documentado para esta consulta

Binance documenta que las klines se identifican de forma única por `open time`, que las respuestas se devuelven en orden cronológico y que los timestamps son milisegundos por defecto. El parámetro `timeZone` se omitirá: los límites se convertirán explícitamente a UTC y no se reinterpretarán las aperturas en UTC-05:00.

La respuesta de una kline contiene 12 posiciones. Para el conjunto canónico se necesitan, como mínimo, open time, OHLC, volumen base, close time, volumen cotizado y número de trades. Se conservará la respuesta original sin redondeo ni pérdida de precisión.

Referencia oficial: https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md#klinecandlestick-data

## 4. Plan mínimo de paginación

Con límite de 1,000 registros por petición, el mínimo teórico para estas cinco ventanas es:

| Episodio | Velas esperadas | Peticiones mínimas |
|---|---:|---:|
| Caída 1 | 1,099 | 2 |
| Caída 2 | 532 | 1 |
| Subida 1 | 2,145 | 3 |
| Caída 3 | 1,336 | 2 |
| Subida 2 | 864 | 1 |
| **Total BTCUSDT** | **5,976** | **9** |

La paginación debe avanzar usando el último `open_time` recibido más una hora, no sumando un número de filas supuesto. Cada página debe conservar parámetros, código HTTP, hora de recuperación, cantidad de filas y hash del cuerpo bruto. Reintentos y respuestas parciales deben quedar registrados; nunca deben convertirse en cobertura exitosa por inferencia.

## 5. Controles obligatorios

Para cada episodio, independientemente:

1. Confirmar que el símbolo `BTCUSDT` existe en los metadatos de exchange y que corresponde a Spot.
2. Comprobar que cada apertura está dentro de `[start_utc, end_utc)`.
3. Comprobar unicidad de `open_time`, orden cronológico y ausencia de duplicados.
4. Comprobar los 5,976 timestamps esperados en el conjunto agregado, y los conteos específicos por ventana.
5. Verificar que cada diferencia entre aperturas consecutivas es exactamente 3,600,000 ms, clasificando cualquier hueco.
6. Validar OHLC: `low <= open <= high`, `low <= close <= high` y `low <= high`.
7. Validar volumen no negativo y tipos/precisión numérica.
8. Comprobar que el cierre de cada vela concuerda con la semántica de Binance y que no se incorporan velas abiertas/incompletas.
9. Registrar respuestas API, errores, reintentos, paginación, timestamps y hashes.
10. No rellenar ausencias con forward-fill, interpolación ni datos de otro exchange.

Un hueco no se clasificará automáticamente como pérdida de datos: se investigará si corresponde a ausencia de operaciones, indisponibilidad del mercado, límite/API o causa desconocida. La explicación debe tener evidencia.

## 6. Granularidad diaria

Las velas `1d` podrán recuperarse como contraste secundario, pero no sustituyen a las velas horarias. Los límites de varios episodios no coinciden con medianoche UTC, por lo que una vela diaria puede cruzar el inicio o final de un episodio. Las métricas exactas de cohorte se calcularán con `1h`; cualquier serie diaria se etiquetará como contexto y se documentará su regla de alineación.

## 7. Ejecución empírica, reconciliación y conclusión

Ejecución automatizada:
- Ejecución inicial: [Run 42320078342](https://github.com/Osleyder1985/Crypto-Causality-Intelligence/actions/runs/42320078342), conclusión `success`.
- Workflow actualizado para retener artefactos durante 90 días; commit: `f86f81065addfabdb768f13441df7f2dd2dd2701`.
- Ejecución reproducida: [Run 42320400840](https://github.com/Osleyder1985/Crypto-Causality-Intelligence/actions/runs/42320400840), conclusión `success`.
- Artefacto vigente: `binance-btcusdt-coverage-42320400840` (Artifact ID `13552925747`).
- SHA-256 del ZIP: `2ae3516d879f7f75194ec0bd0ec1c3e738efef9fd6c3cef62424701eba823d3b`.
- Tamaño: 776,704 bytes; retención de GitHub hasta 2027-02-05T00:47:51Z.
- El JSONL normalizado y las nueve páginas originales coinciden byte a byte entre las dos ejecuciones; el informe difiere únicamente en metadatos propios de la ejecución.
- El ZIP contiene nueve páginas originales, un JSONL normalizado y `coverage_report.json`.

| Episodio | Esperadas | Recibidas | Cobertura | Huecos | Duplicados | Violaciones OHLCV |
|---|---:|---:|---:|---:|---:|---:|
| Caída 1 | 1,099 | 1,099 | 100% | 0 | 0 | 0 |
| Caída 2 | 532 | 532 | 100% | 0 | 0 | 0 |
| Subida 1 | 2,145 | 2,145 | 100% | 0 | 0 | 0 |
| Caída 3 | 1,336 | 1,336 | 100% | 0 | 0 | 0 |
| Subida 2 | 864 | 864 | 100% | 0 | 0 | 0 |
| **Total** | **5,976** | **5,976** | **100%** | **0** | **0** | **0** |

Controles independientes ejecutados sobre el ZIP:
- Digest SHA-256 del archivo coincidente con el digest publicado por GitHub.
- SHA-256 y número de filas de las nueve páginas coincidentes con el informe.
- 5,976 timestamps de origen únicos; sin duplicados entre páginas.
- 5,976 registros normalizados; correspondencia exacta de los campos OHLCV, close time, trade count, taker volumes y campo ignore contra las posiciones originales de Binance.
- Timestamps dentro de los límites semiabiertos, continuidad horaria por episodio y UTC derivado coincidente con el campo normalizado.
- Cero errores en identidad de mercado, close time, coherencia OHLC, volúmenes no negativos, taker buy base <= volumen base y trade count entero no negativo.

| Evidencia | Estado |
|---|---|
| Límites y conteos teóricos | **Completado** |
| Descarga real Binance Spot | **Completado** |
| Respuestas originales preservadas y hasheadas | **Completado** |
| Conteos, continuidad, huecos y duplicados | **Completado** |
| Reconciliación raw → normalized | **Completado** |
| Validaciones OHLCV y temporalidad | **Completado** |

**Conclusión: `SUITABLE` para las cinco ventanas definidas en este manifiesto**, con cobertura empírica de 5,976/5,976 velas y sin anomalías detectadas en los controles enumerados. La conclusión certifica la completitud y consistencia de la extracción frente a la respuesta de Binance Spot para este universo; no certifica la ausencia de errores históricos en la fuente ni constituye una validación cruzada contra otro exchange.

El límite de la Caída 3 queda fijado en `2026-06-30 20:00 UTC-05:00` (final exclusivo), equivalente a `2026-07-01 01:00Z`. La última vela incluida abre a las 19:00 UTC-05:00. Esta es la convención del manifiesto y produce las 1,336 velas esperadas.

## 8. Criterio de aceptación

El episodio solo podrá clasificarse como `suitable` cuando:
- las respuestas cubran exactamente la ventana definida según la semántica del endpoint;
- cada ausencia o anomalía esté explicada y respaldada;
- no existan timestamps inválidos, duplicados no explicados ni violaciones OHLC;
- la procedencia y las respuestas permitan reproducir la consulta.

Si hay incidencias explicadas o exclusiones, evaluar `suitable_with_reservations`. Si faltan respuestas o evidencia, mantener `not_evaluated`; si existe un defecto crítico o cobertura insuficiente, clasificar `not_suitable`.
