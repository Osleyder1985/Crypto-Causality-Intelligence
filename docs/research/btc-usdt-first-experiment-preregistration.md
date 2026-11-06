# Prerregistro del primer experimento histórico BTC/USDT

- Experiment key propuesta: `btc-usdt-directional-episodes-v1`
- Estado: `planned`; no ejecutar inferencia hasta cerrar el manifiesto de datos y la lista de episodios.
- Instrumento: BTC/USDT; venue único por dataset.
- Frecuencia objetivo: 1 hora.
- Zona horaria de captura de los límites aportados: UTC-5; normalización de almacenamiento y análisis: UTC.
- Unidad de observación: episodio direccional delimitado por el operador.
- Naturaleza inicial: estudio descriptivo exploratorio, no confirmatorio y no causal.

## 1. Pregunta de investigación

¿Las subidas y caídas históricas de BTC/USDT seleccionadas presentan perfiles diferentes de retorno, volatilidad, drawdown, rango y actividad de volumen, y qué características medibles aparecen en las 24, 72 y 168 horas anteriores a cada episodio?

La pregunta no presupone que exista una diferencia ni que las variables previas expliquen causalmente el movimiento.

## 2. Hipótesis exploratorias

- **H1 — Perfil de régimen:** las distribuciones de volatilidad realizada por vela y de volumen base medio difieren entre episodios alcistas y bajistas.
- **H2 — Actividad previa:** el cociente entre volumen base medio del episodio y volumen medio de las 168 horas previas difiere entre direcciones.
- **H3 — Contexto previo:** los retornos y la volatilidad de las ventanas previas de 24, 72 y 168 horas muestran perfiles distintos antes de episodios alcistas y bajistas.
- **H4 — Riesgo de trayectoria:** el máximo drawdown calculado sobre cierres y el rango high/low del episodio difieren entre direcciones.

Todas son hipótesis exploratorias. No se fijan umbrales de significación ni se interpretarán diferencias como capacidad predictiva. La selección manual de episodios introduce sesgo de selección y limita la generalización.

## 3. Cohorte y selección

La cohorte inicial contiene exclusivamente ventanas alcistas y bajistas que el operador haya identificado y confirmado. No se crearán episodios adicionales mirando los resultados del análisis.

Reglas:
1. Un único símbolo canónico y un único mercado/venue por cohorte. No mezclar BTCUSDT spot de distintos exchanges ni sustituirlo por XBT/USD.
2. Granularidad uniforme de 1 hora y límites alineados a la hora UTC.
3. Ventanas semiabiertas `[start, end)`; la vela que abre exactamente en `end` queda excluida.
4. No solapar episodios dentro de una misma cohorte. Si hay solapamiento, documentar y resolver antes del análisis.
5. Mantener todos los episodios elegibles, incluso si el resultado contradice la hipótesis.
6. No usar episodios de entrenamiento y validación como si fueran muestras independientes cuando pertenecen a un mismo movimiento de mercado.

La lista completa de fechas todavía requiere reconciliación. El contexto disponible confirma algunos límites aportados, pero contiene una discrepancia sobre el final del episodio que comienza el 5 de febrero de 2026 y el inicio de la caída de mayo de 2026. No completar ni inferir los límites faltantes. La tabla definitiva se congelará en un manifiesto versionado antes de ejecutar el experimento.

## 4. Métricas primarias y definiciones

Se utilizará el contrato implementado en `scripts/research/btc_episode_study.py`:

- Retorno del episodio: apertura de la primera vela a cierre de la última vela incluida.
- Volatilidad realizada: desviación estándar poblacional de retornos logarítmicos por vela; no anualizada.
- Máximo drawdown: calculado sobre cierres; no reconstruye el recorrido intravela.
- Rango: mínimo low y máximo high del episodio.
- Volumen base medio; volumen cotizado medio solo si existe completo.
- Ratio de volumen: volumen base medio del episodio dividido por volumen base medio de las 168 horas previas.
- Contexto previo: retornos y volatilidad de 24, 72 y 168 horas. Si la cobertura no es completa, valor `null`, sin imputación.

No comparar volúmenes de venues o unidades diferentes. El volumen base y el quote volume no son intercambiables.

## 5. Calidad y elegibilidad de datos

Antes de aceptar un run:
- Identificar fuente, venue, símbolo, tipo de mercado, intervalo, zona temporal y método de obtención.
- Registrar nombre base y SHA-256 del dataset y del archivo de episodios; no registrar rutas absolutas ni contenido OHLCV en PostgreSQL.
- Confirmar cobertura horaria completa en cada episodio y en las ventanas previas necesarias.
- Rechazar timestamps duplicados, desordenados, naive o fuera de UTC; validar OHLCV y límites alineados.
- Reportar huecos globales por separado; no interpolar, rellenar ni fabricar velas.
- Registrar el tratamiento legal/técnico autorizado para el dataset y su clase de retención antes de crear artefactos persistentes.

Los datos reales no se descargarán desde este experimento. El módulo procesa archivos locales. La política metadata-only de proveedores sigue vigente; un hash no concede permiso para almacenar, compartir o redistribuir datos ni resultados derivados.

## 6. Análisis y límites inferenciales

Primera fase:
1. Resumen individual por episodio.
2. Resumen por dirección con n, mediana, media, dispersión y rango intercuartílico.
3. Comparación descriptiva de alcistas frente a bajistas.
4. Sensibilidad a episodios con cobertura incompleta (se excluyen de la métrica afectada, informando n efectivo).
5. Inspección de valores extremos y dependencia entre episodios.

Con pocos episodios, se priorizarán tamaños de efecto descriptivos e intervalos de incertidumbre adecuados, no p-valores aislados. No se ajustarán modelos predictivos ni se afirmará causalidad. Cualquier estudio confirmatorio posterior requerirá más observaciones, controles temporales, corrección por comparaciones múltiples y validación fuera de muestra.

## 7. Artefactos y trazabilidad

Cada run deberá registrar:
- commit exacto de código y versión de protocolo;
- parámetros y manifiesto de entrada con hashes;
- estado y timestamps;
- métricas agregadas;
- referencias lógicas y SHA-256 de JSON/CSV de salida;
- clasificación de retención.

PostgreSQL conserva metadata y trazabilidad; Parquet conserva únicamente datasets cuya retención esté autorizada; DuckDB consulta los Parquet locales. No subir velas ni artefactos derivados no autorizados al repositorio público.

## 8. Condiciones para iniciar el primer run real

El run real permanece bloqueado hasta que:
- se confirme la lista completa de episodios y se resuelva la discrepancia temporal señalada;
- se confirme el dataset exacto, su venue y su cobertura;
- se documente que el uso y tratamiento local del dataset están autorizados;
- el manifiesto y los archivos de entrada pasen los controles del estudio.

Hasta entonces solo se permiten pruebas sintéticas de software. Un resultado sintético valida el pipeline, nunca una hipótesis de mercado.

## 9. Decisión de preregistro

Este documento fija la pregunta, las hipótesis exploratorias, las métricas y los controles antes de examinar los resultados del dataset. Cambios posteriores deben quedar en una nueva versión del protocolo y en un nuevo run; no sobrescribir silenciosamente el prerregistro original.
