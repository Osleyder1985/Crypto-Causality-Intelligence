# Contrato de equivalencia de almacenamiento — BTCUSDT Spot 1h

## Estado
**Primera conformidad empírica ejecutada con éxito** para la cohorte Binance BTCUSDT Spot 1h en Parquet, DuckDB y PostgreSQL efímero de CI. No representa todavía una migración productiva ni un esquema operacional permanente.

## 1. Dataset de referencia
- Fuente: Binance Spot REST API.
- Instrumento: BTCUSDT.
- Intervalo: 1h.
- Cohorte: cinco ventanas del manifiesto BTCUSDT.
- Registros de referencia: 5.976.
- Clave natural de vela: `(provider, market_type, symbol, interval, open_time_ms)`.
- Tiempo: UTC; inicio inclusivo y final exclusivo.
- Fuente de verdad para la comparación: JSONL normalizado y páginas originales preservadas en el artefacto GitHub Actions [42320400840](https://github.com/Osleyder1985/Crypto-Causality-Intelligence/actions/runs/42320400840).

## 2. Tipos canónicos

| Campo | Tipo lógico | Parquet | DuckDB | PostgreSQL |
|---|---|---|---|---|
| provider | string | string | VARCHAR | TEXT |
| market_type | enum/string | string | VARCHAR | TEXT + CHECK |
| symbol | string | string | VARCHAR | TEXT |
| interval | duración codificada | string | VARCHAR | TEXT |
| cohort_window | identificador | string | VARCHAR | TEXT |
| open_time_ms | epoch milliseconds | INT64 | BIGINT | BIGINT |
| open_time_utc | instant UTC | timestamp[us, UTC] | TIMESTAMPTZ | TIMESTAMPTZ |
| open/high/low/close | decimal exacto | DECIMAL(38,18) | DECIMAL(38,18) | NUMERIC(38,18) |
| volume_base | decimal exacto | DECIMAL(38,18) | DECIMAL(38,18) | NUMERIC(38,18) |
| close_time_ms | epoch milliseconds | INT64 | BIGINT | BIGINT |
| quote_volume | decimal exacto | DECIMAL(38,18) | DECIMAL(38,18) | NUMERIC(38,18) |
| trade_count | entero no negativo | INT64 | BIGINT | BIGINT |
| taker_buy_base_volume | decimal exacto | DECIMAL(38,18) | DECIMAL(38,18) | NUMERIC(38,18) |
| taker_buy_quote_volume | decimal exacto | DECIMAL(38,18) | DECIMAL(38,18) | NUMERIC(38,18) |
| source_ignore_field | string | string | VARCHAR | TEXT |

La representación decimal numérica debe evitar FLOAT/DOUBLE. Los valores textuales originales del proveedor deben permanecer recuperables desde la capa raw; no se debe interpretar la representación DECIMAL como sustituto del payload original.

## 3. Invariantes obligatorios

1. Conteo exacto: 5.976 filas.
2. Unicidad de la clave natural.
3. Mismos cinco cohort_window y conteos: 1.099, 532, 2.145, 1.336 y 864.
4. Mismo conjunto de open_time_ms; no basta con comparar el número de filas.
5. Correspondencia exacta entre open_time_ms y open_time_utc.
6. Decimales comparados por valor exacto, sin tolerancias de punto flotante.
7. trade_count preservado como entero exacto.
8. Cero valores nulos en campos obligatorios.
9. Cero filas adicionales, pérdidas, duplicados o cambios de identidad de mercado.
10. Orden de lectura determinista por clave natural; no asumir orden físico del motor.

## 4. Estrategia de Parquet
- Escribir el dataset con tipos explícitos, sin inferencia desde strings.
- Mantener `open_time_ms` como clave temporal entera y `open_time_utc` como timestamp UTC.
- Usar decimal128(38,18) para campos numéricos de mercado.
- Particionar por provider/market_type/symbol/interval/cohort_window; medir si el particionado es adecuado antes de generalizarlo.
- Leer de vuelta el archivo escrito y comparar cada columna con el JSONL de referencia.
- Registrar tamaño, schema, row groups, estadísticas y SHA-256 del artefacto.

## 5. Estrategia DuckDB
- Crear tabla con tipos explícitos; no depender de CREATE TABLE AS SELECT con inferencia implícita.
- Importar desde Parquet y verificar tipos físicos/lógicos.
- Crear restricción o prueba de unicidad sobre la clave natural.
- Comparar conteos, cohortes, timestamps, nulos y agregados exactos.
- Consultar Parquet directamente y la tabla materializada; los resultados deben coincidir.

## 6. Estrategia PostgreSQL
- Separar metadatos de lote/ingesta de la tabla de velas.
- Usar BIGINT para epoch milliseconds, TIMESTAMPTZ para UTC y NUMERIC(38,18) para valores decimales.
- Definir PK/UNIQUE sobre la clave natural y CHECK para conteos/volúmenes no negativos y coherencia OHLC.
- Definir FK a mercado e ingestion_batch cuando estén disponibles los catálogos canónicos.
- Cargar dentro de una transacción; comprobar rollback ante una fila inválida.
- Leer de vuelta y comparar todas las filas con la fuente de referencia.

## 7. Pruebas negativas
- Clave natural duplicada.
- Timestamp UTC que no coincide con epoch milliseconds.
- OHLC incoherente.
- Volumen negativo.
- trade_count negativo o decimal.
- Valor decimal fuera de precisión/escala.
- Campo obligatorio nulo.
- Cohort_window desconocida.
- Fallo durante carga transaccional PostgreSQL con rollback íntegro.

## 8. Criterio de aceptación
La conformidad solo se declara cuando los tres destinos contienen exactamente los mismos 5.976 registros y tipos semánticamente equivalentes, cada destino pasa sus pruebas negativas y la comparación se ejecuta automáticamente en CI. La cobertura Binance ya reconciliada no sustituye esta prueba de persistencia.

## 9. Riesgos que deben evitarse
- FLOAT/DOUBLE para precios o volúmenes.
- Pérdida de zona horaria al almacenar timestamps.
- Comparar solo conteos, no claves y valores.
- Inferir esquema desde una muestra parcial.
- Hacer pasar un test de contrato Python por una prueba real de motor PostgreSQL.
- Usar los datos sintéticos de fixtures de identidad como mappings productivos.


## 10. Primera ejecución empírica

Ejecución automatizada: [GitHub Actions 42321280525](https://github.com/Osleyder1985/Crypto-Causality-Intelligence/actions/runs/42321280525), conclusión `success`.

- Dataset JSONL: 5.976 filas de referencia.
- Parquet: 5.976 filas; DECIMAL(38,18), timestamp[us, UTC].
- DuckDB: 5.976 filas; DECIMAL(38,18), TIMESTAMPTZ y PK natural.
- PostgreSQL 16: 5.976 filas; NUMERIC(38,18), TIMESTAMPTZ y PK natural.
- Igualdad de todos los campos tras lectura de vuelta en los tres destinos.
- Conteos por cohorte preservados: 1.099 / 532 / 2.145 / 1.336 / 864.
- Parquet SHA-256: `e6ec2a702a33c66d5eb69556eb77080eacc028d5278ba891d6f8509bb3a306c8`.
- Tamaño Parquet: 619.416 bytes.
- Tamaño DuckDB: 1.585.152 bytes.
- Pruebas negativas: PK duplicada en DuckDB y PostgreSQL; CHECK de volumen negativo en PostgreSQL; rollback transaccional confirmado.
- Artefacto CI con datos y reporte: `binance-btcusdt-coverage-42321280525`, Artifact ID `13553615526`, SHA-256 `08622dcf713b5a27dbb2bfbd773e536cbd76fd59d125ecf7f7aca4bf1e92b719`, retención hasta 2027-02-05T00:57:01Z.

El runner está implementado en `scripts/validation/storage_conformance.py`; dependencias declaradas en `requirements-validation.txt`. El workflow ejecuta la descarga real, inicia PostgreSQL 16 efímero, ejecuta las tres rutas de almacenamiento y publica evidencia.

**Dictamen de esta ejecución:** conformidad de ida y vuelta para las 5.976 filas entre el JSONL de referencia, Parquet, DuckDB y PostgreSQL. Alcance limitado a la cohorte y esquema de prueba descritos; no equivale a desplegar PostgreSQL productivo, ni a certificar migraciones, backups, rendimiento o alta disponibilidad.
