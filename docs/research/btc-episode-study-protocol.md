# Protocolo del primer estudio de episodios BTC/USDT

- Issue: #17
- Estado: implementación inicial; pendiente de ejecutar con un dataset cuyo tratamiento esté autorizado.
- Granularidad inicial: velas de 1 hora.
- Ventanas de episodio: intervalos UTC semiabiertos [inicio, fin).

## Restricción de datos

Este módulo no descarga datos ni se conecta a Binance, Kraken o CoinGecko. Lee un CSV local proporcionado por el operador. La política vigente mantiene las nuevas ejecuciones de proveedores en modalidad metadata-only y prohíbe incorporar a este repositorio respuestas originales o series OHLCV. Los datos reales solo se procesarán localmente cuando su uso y tratamiento estén autorizados. Las pruebas automatizadas usan exclusivamente datos sintéticos.

Los reportes de salida son agregados por episodio. No deben versionarse en Git si contienen métricas derivadas de proveedores cuyo almacenamiento no esté autorizado.

## Formato de entrada CSV

Columnas obligatorias:

| Campo | Semántica |
|---|---|
| `open_time_utc` | Inicio de vela en ISO-8601 UTC, por ejemplo `2026-01-01T00:00:00Z` |
| `open`, `high`, `low`, `close` | Precios positivos de la vela |
| `volume` | Volumen base, sin conversión implícita |

Columna opcional:

- `quote_volume`: volumen expresado en el activo cotizado. Solo se calcula si está presente en todas las velas de la ventana.

El archivo debe contener un solo instrumento y un solo proveedor/venue. No mezclar BTCUSDT con XBT/USD ni series agregadas con datos de un exchange. La procedencia y la unidad de volumen deben quedar documentadas fuera del CSV o en el manifiesto operativo del experimento.

## Formato de episodios JSON

Cada episodio identifica una ventana manualmente clasificada:

```json
[
  {
    "episode_id": "btc-rise-01",
    "direction": "bullish",
    "start_utc": "2026-08-16T16:00:00Z",
    "end_utc": "2026-08-17T16:00:00Z"
  }
]
```

La fecha final es exclusiva: una vela cuya apertura coincide con `end_utc` no pertenece al episodio. Las fechas deben alinearse con la granularidad seleccionada. El ejemplo anterior es ilustrativo, no una ventana de investigación aprobada.

## Métricas

Por episodio:
- retorno porcentual desde la apertura de la primera vela hasta el cierre de la última;
- desviación estándar poblacional de retornos logarítmicos por vela, no anualizada;
- máximo drawdown medido sobre cierres de vela (no reconstruye el recorrido intravela);
- rango entre máximo high y mínimo low;
- volumen base medio y, si existe, volumen cotizado medio;
- ratio del volumen base medio del episodio frente a las 168 horas previas.

Ventanas previas: 24, 72 y 168 horas antes del inicio. Si no hay cobertura completa, se devuelve `null`; no se rellenan huecos ni se extrapola.

## Controles

- timestamps ISO-8601 con zona UTC explícita;
- orden estrictamente creciente y cero duplicados;
- precios positivos;
- consistencia OHLC;
- volúmenes no negativos;
- límites de episodios alineados al intervalo;
- cobertura completa dentro de cada episodio;
- huecos globales informados, sin imputación.

## Ejecución local

```bash
python scripts/research/btc_episode_study.py \
  --input /ruta/local/btcusdt_1h.csv \
  --episodes /ruta/local/btc_episodes.json \
  --json-out /ruta/local/btc_episode_summary.json \
  --csv-out /ruta/local/btc_episode_summary.csv \
  --interval-seconds 3600
```

El CSV de entrada permanece local. El JSON/CSV de salida contiene métricas agregadas por episodio y no se debe publicar ni retener si las condiciones de la fuente no lo permiten.

## Interpretación

Este incremento es un estudio descriptivo de episodios seleccionados manualmente. No demuestra que una variable cause una subida o caída, no estima probabilidades predictivas y no valida una estrategia. Para inferencia se necesitarán hipótesis preregistradas, controles comparables, múltiples episodios, tratamiento de selección y pruebas fuera de muestra.


## Entrada Parquet con DuckDB

Además del CSV, el CLI admite Parquet local mediante DuckDB:

```bash
python -m pip install -r requirements-research.txt
python scripts/research/btc_episode_study.py \
  --input /ruta/local/btcusdt_1h.parquet \
  --input-format parquet \
  --episodes /ruta/local/btc_episodes.json \
  --json-out /ruta/local/btc_episode_summary.json \
  --csv-out /ruta/local/btc_episode_summary.csv \
  --interval-seconds 3600
```

El Parquet debe contener las mismas columnas canónicas. `open_time_utc` debe ser un timestamp con zona horaria UTC o texto ISO-8601 con offset UTC explícito; los timestamps sin zona se rechazan. OHLCV debe ser numérico, no nulo (salvo `quote_volume`, opcional), finito y cumplir las validaciones del adaptador CSV.

DuckDB se ejecuta en memoria y consulta directamente el archivo local. No crea una copia persistente, no escribe tablas temporales al dataset y no realiza conexiones a proveedores. La lectura conserva el orden físico para que los timestamps duplicados o fuera de orden no se oculten mediante ordenación automática. La versión de DuckDB está fijada en `requirements-research.txt`.

Las pruebas crean archivos Parquet temporales con datos sintéticos y verifican equivalencia con el contrato de análisis. No contienen ni requieren datos reales.


## Prerregistro del experimento histórico

La pregunta de investigación, hipótesis exploratorias, reglas de cohorte, definiciones de métricas, controles de calidad y condiciones para iniciar el primer run real se especifican en [btc-usdt-first-experiment-preregistration.md](btc-usdt-first-experiment-preregistration.md). Ese prerregistro es la referencia antes de inspeccionar resultados reales. La lista definitiva de episodios aún debe reconciliarse; no se deben completar límites por inferencia.


## Manifiesto canónico versionado (preferido)

Para el primer experimento se prefiere el manifiesto versionado frente a la lista JSON heredada. Los archivos de referencia son:

- [Esquema JSON](btc-usdt-episode-manifest.schema.json).
- [Plantilla pendiente de confirmación](btc-usdt-episode-manifest.template.json).
- Validador ejecutable: `scripts/research/episode_manifest.py`.

El manifiesto conserva los límites originales en `start_local` y `end_local` con offset explícito `-05:00), junto con sus equivalentes `start_utc` y `end_utc`. El validador exige que ambos pares representen exactamente los mismos instantes, que los límites estén alineados al intervalo, que los IDs sean únicos y que no existan solapamientos.

El manifiesto solo puede pasar a `approved` cuando se identifiquen un venue y tipo de mercado únicos, la procedencia del dataset, la autorización de uso/retención y todos los episodios confirmados. El CLI rechaza manifiestos `pending_confirmation`, datasets sin autorización y episodios no confirmados. El esquema JSON documenta la estructura; el validador Python aplica además las invariantes temporales y de ejecución.

Las listas JSON heredadas siguen admitidas únicamente por compatibilidad en la función de lectura y en pruebas históricas. El CLI de investigación las rechaza: toda ejecución operativa exige el manifiesto versionado y sus controles de procedencia, zona horaria local y autorización.


Antes de disponer de las velas, el manifiesto aprobado puede validarse de forma independiente:

```bash
python -m scripts.research.episode_manifest \
  --manifest /ruta/local/btc-usdt-episode-manifest.json
```

El comando devuelve código distinto de cero si el manifiesto sigue pendiente, carece de autorización o incumple las reglas de cohorte y tiempo. No abre archivos OHLCV ni consulta proveedores.
