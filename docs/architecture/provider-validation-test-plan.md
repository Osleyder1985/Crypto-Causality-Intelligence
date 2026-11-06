# Protocolo reproducible de validación de proveedores

## 1. Propósito

Definir un procedimiento repetible para contrastar los contratos canónicos de datos de mercado con respuestas públicas de Binance Spot y Kraken Spot antes de implementar adaptadores definitivos, migraciones SQL o persistencia histórica.

Este documento establece el diseño de las pruebas y sus criterios de aceptación. **No declara completada la validación empírica**: esa declaración requiere capturas reales, reproducibles y revisadas de ambos proveedores.

## 2. Alcance y límites

### Incluido

- Velas OHLCV de los instrumentos de referencia:
  - Binance Spot: `BTCUSDT`.
  - Kraken Spot: `XBT/USD` (el identificador nativo devuelto por Kraken debe verificarse en la respuesta de `AssetPairs`; no se debe asumir que el nombre visible coincide con la clave interna).
- Metadata de instrumentos y reglas de negociación.
- Normalización temporal, decimal y semántica de campos.
- Diferenciación entre velas cerradas y provisionales.
- Pruebas unitarias con fixtures sintéticos y capturas públicas controladas.

### Excluido

- Modificación de Runs históricos #1–#8.
- Escritura o publicación de datasets históricos.
- Persistencia de respuestas raw en el repositorio.
- Migraciones o cambios en el esquema físico de PostgreSQL.
- Adaptadores de producción y ejecución programada.
- Inferir derechos de almacenamiento o redistribución a partir del carácter público de un endpoint.

## 3. Endpoints y parámetros de referencia

| Proveedor | Recurso | Endpoint | Parámetros iniciales |
|---|---|---|---|
| Binance Spot | Klines | `GET /api/v3/klines` | `symbol=BTCUSDT`, `interval=1m`, `limit=3`, `timeZone=0` |
| Binance Spot | Exchange information | `GET /api/v3/exchangeInfo` | `symbol=BTCUSDT` |
| Kraken Spot | OHLC | `GET /0/public/OHLC` | `pair=XBTUSD` (confirmar alias admitido), `interval=1` |
| Kraken Spot | Asset pairs | `GET /0/public/AssetPairs` | Sin filtro inicial; localizar el par BTC/USD por sus campos y alias |

Hosts oficiales de referencia:

- Binance: `https://api.binance.com`
- Kraken: `https://api.kraken.com`

La captura debe registrar la URL efectiva, parámetros enviados, código HTTP, hora UTC de inicio y fin, y cualquier cabecera relevante para interpretar la respuesta. No incluir claves, cookies ni credenciales; los endpoints de este protocolo son públicos.

Para Binance, solicitar timestamps en milisegundos por defecto y registrar explícitamente la ausencia o presencia de `X-MBX-TIME-UNIT`. La primera validación fija `timeZone=0`; no mezclar velas de diferentes zonas de alineación.

## 4. Diseño de pruebas

Las pruebas se implementarán primero como pruebas unitarias puras, alimentadas por fixtures sintéticos versionados. No necesitan conectividad de red y no deben depender de datos de mercado cambiantes.

### 4.1 Mapeo OHLCV

Verificar para cada proveedor:

- Correspondencia exacta de open, high, low y close.
- Unidad y conversión del timestamp de apertura.
- Volumen expresado en activo base.
- Volumen en activo cotizado solo cuando el proveedor lo entrega explícitamente.
- VWAP, número de operaciones y volúmenes taker solo cuando existan en la fuente.
- Campos no proporcionados por la fuente deben permanecer nulos; no estimarlos ni reconstruirlos sin una regla explícita y documentada.

### 4.2 Tiempo e intervalos

- Normalizar timestamps a UTC sin perder la precisión original.
- Binance: el cierre recibido es inclusivo; derivar `close_time_exclusive` sumando una unidad de la resolución recibida (1 ms en el modo inicial).
- Kraken: no entrega un cierre separado en OHLC; calcular el límite exclusivo como apertura más duración del intervalo.
- Probar límites de minuto y cambios de día, semana y mes cuando aplique.
- Rechazar timestamps inválidos, unidades ambiguas y cierres anteriores o iguales a la apertura.

### 4.3 Finalidad de la vela

- Kraken REST: según la documentación, la última fila es la vela del intervalo actual y aún no está confirmada. La prueba debe marcarla como provisional y no tratarla como dato final.
- Binance REST Klines: la respuesta no incluye un indicador booleano equivalente a `x` del stream WebSocket. No inventar ese campo. Para la primera etapa, conservar `is_final=null` en el modelo canónico cuando la finalidad no pueda probarse desde la respuesta REST capturada. Una regla temporal heurística solo podrá incorporarse después como campo derivado, con nombre y procedencia explícitos.
- No equiparar “vela histórica” con inmutabilidad: una fuente puede corregir o republicar datos.

### 4.4 Metadata y filtros

Binance:

- Mapear `PRICE_FILTER.tickSize`, `minPrice` y `maxPrice`.
- Mapear `LOT_SIZE.stepSize`, `minQty` y `maxQty`.
- Mapear `MIN_NOTIONAL` o `NOTIONAL` sin perder sus indicadores de aplicabilidad.
- Conservar filtros adicionales como extensiones específicas del proveedor.
- No interpretar `baseAssetPrecision` ni `quoteAssetPrecision` como tick o step.

Kraken:

- Conservar la clave interna del par y sus alias.
- Mapear `tick_size`, `pair_decimals`, `lot_decimals`, `ordermin` y `costmin` según el contrato documentado.
- No derivar `quantity_step` a partir de `lot_decimals`.
- Conservar códigos internos de activos y nombres de presentación cuando estén disponibles.

### 4.5 Precisión y valores numéricos

- Tratar precios, volúmenes, ticks y cantidades como decimales exactos.
- No usar aritmética binaria de punto flotante para validar igualdad financiera.
- Verificar que la normalización no redondea ni trunca valores recibidos.
- Mantener separadas la precisión decimal de presentación y las reglas efectivas de tick/step.

### 4.6 Integridad temporal

- Orden estrictamente creciente por tiempo de apertura para una serie de un mismo instrumento e intervalo.
- No permitir duplicados de la clave lógica proveedor + instrumento + intervalo + apertura.
- Detectar gaps; no rellenarlos con velas artificiales.
- Kraken puede omitir intervalos sin operaciones en sus ficheros históricos OHLCVT; esa semántica no debe confundirse con un error de captura REST.
- Respetar el límite de 720 filas de Kraken REST OHLC y documentar que no permite reconstrucción histórica completa.

## 5. Fixtures sintéticos requeridos

Mantener fixtures mínimos, pequeños y diseñados para cubrir:

1. Una vela Binance con todos los campos del array Klines.
2. Una vela Kraken con VWAP y trade count.
3. Una respuesta Kraken donde la última vela sea provisional.
4. Una respuesta Binance con filtros `PRICE_FILTER`, `LOT_SIZE` y `NOTIONAL`.
5. Una respuesta Kraken AssetPairs con clave interna y alias.
6. Valores decimales con ceros finales y escalas distintas.
7. Timestamps en milisegundos y un caso de microsegundos para probar rechazo o conversión explícita.
8. Una serie con gap temporal y otra con timestamp duplicado.
9. Campos opcionales ausentes y valores nulos.
10. Respuestas de error o payloads incompletos.

Los fixtures sintéticos deben etiquetarse como tales y no presentarse como capturas reales de los exchanges.

## 6. Captura empírica controlada

Una vez que las pruebas sintéticas estén implementadas y pasen:

1. Consultar los endpoints públicos definidos en la sección 3.
2. Guardar la respuesta únicamente en memoria temporal durante la ejecución inicial.
3. Registrar metadatos de captura: proveedor, endpoint, parámetros, hora UTC, estado HTTP, hash SHA-256 del cuerpo y versión del protocolo de captura.
4. Evitar registrar secretos, cabeceras de autenticación, datos personales o contenido innecesario.
5. No subir cuerpos raw, dumps ni datasets al repositorio público.
6. Ejecutar el validador contra la respuesta en memoria.
7. Si se necesita conservar evidencia, revisar primero las condiciones vigentes de uso, almacenamiento, caché, retención y redistribución para ese endpoint y propósito. La autorización debe ser explícita y trazable; en caso de duda, no persistir.
8. Registrar el resultado como observación puntual, con fecha y limitaciones; no generalizar una única respuesta a todos los instrumentos o periodos.

La captura no debe modificar ningún Run histórico ni escribir en PostgreSQL o Parquet.

## 7. Criterios de aceptación

Un proveedor y recurso se considerarán validados solo cuando:

- Se haya obtenido al menos una respuesta real legible del endpoint.
- La captura incluya parámetros y contexto temporal suficientes para reproducir la consulta.
- El parser convierta correctamente los campos obligatorios y preserve los opcionales.
- Las pruebas de unidad y de contrato pasen.
- Las unidades, precisión y semántica de cierre estén documentadas.
- Los campos ausentes no se inventen.
- Las limitaciones conocidas del endpoint estén reflejadas.
- La evidencia y cualquier retención posterior respeten las condiciones de uso aplicables.

La validación global de OHLCV no se completa hasta cumplir los criterios para ambos proveedores. La validación de metadata se registra por separado de la validación OHLCV.

## 8. Matriz de evidencia existente y brechas

La revisión del historial del repositorio identificó evidencia empírica anterior que debe reutilizarse; no corresponde repetirla como si no existiera.

| Proveedor/recurso | Evidencia existente | Estado y brecha para este contrato |
|---|---|---|
| Binance `exchangeInfo` | Run #13: HTTP 200, respuesta original archivada con SHA-256 y resumen BTCUSDT/ETHUSDT; Run #14: HTTP 200 y manifiesto técnico | Captura empírica existente. Falta verificar explícitamente el mapeo campo a campo contra el esquema canónico de metadata y sus filtros. |
| Binance `klines` | Runs #10, #13 y #14: extracción real BTC/ETH, intervalos 1h y 1d; Run #14 valida cobertura y manifiesto sin publicar series | Evidencia empírica OHLCV existente. Falta probar el contrato canónico con casos de 1m, close time inclusivo, unidad de timestamp y semántica `is_final`. |
| Kraken `AssetPairs` | Run #13: HTTP 200, respuesta original archivada con SHA-256 y resumen XBT/USD y ETH/USD; Run #14: HTTP 200 y manifiesto técnico | Captura empírica existente. Falta verificar el mapeo campo a campo, aliases, códigos internos y reglas de precisión contra el esquema canónico. |
| Kraken `OHLC` | Runs #10, #13 y #14: extracción real BTC/ETH, intervalos 1h y 1d; Run #14 valida cobertura y manifiesto sin publicar series | Evidencia empírica OHLCV existente. Falta probar explícitamente el parser canónico de la fila de 8 campos, cálculo de cierre exclusivo y última vela provisional. |

### Evidencia y retención conocidas

- Run #13 obtuvo HTTP 200 para `exchangeInfo` y `AssetPairs`; las respuestas originales se archivaron con SHA-256. También ejecutó 11 pruebas unitarias, todas aprobadas. Su artefacto incluía respuestas originales y CSV, con retención configurada de 90 días.
- Run #14 volvió a ejecutar extracción y validaciones. Se descargó e inspeccionó el ZIP: contiene exclusivamente `manifest.json`, sin JSON originales ni CSV OHLCV.
- Los resultados empíricos de Run #13/14 registran series BTC/ETH horarias y diarias, controles de duplicados, huecos internos, alineación temporal y reglas OHLC/volumen. Para Kraken 1h la cobertura observada fue 706/720 en Run #13/14 debido al límite de 720 filas y al momento de consulta; no se detectaron huecos internos en el tramo recibido.
- La evidencia de Runs #10, #13 y #14 demuestra que sí hubo capturas reales. No demuestra automáticamente que todos los campos del nuevo contrato canónico estén cubiertos por las pruebas existentes.
- La retención de los artefactos previos, especialmente Run #13 y los Runs #1–#8 que incluyen valores de CoinGecko, sigue sujeta a la revisión de permisos correspondiente. Este protocolo no autoriza su reutilización, redistribución ni extensión de retención.

La brecha prioritaria ya no es conseguir por primera vez datos reales de ambos exchanges. Es ejecutar pruebas de contrato explícitas sobre la evidencia existente cuando esté disponible legítimamente y completar únicamente los casos semánticos que las pruebas anteriores no acreditan.

## 9. Implementación inicial de pruebas de contrato

En la rama del PR #15 se añadieron parsers puros y pruebas sintéticas, independientes de la red:

- `scripts/validation/market_contracts.py`: parsers para Binance REST Klines y Kraken REST OHLC, más mapeo inicial de metadata Binance `exchangeInfo` y Kraken `AssetPairs`.
- `tests/test_market_contracts.py`: fixtures sintéticos que cubren decimales exactos, volumen base/cotizado, VWAP, conteo de operaciones, timestamps en ms/us/s, cierre exclusivo, estado provisional, filtros y aliases de instrumentos.
- `.github/workflows/contract-tests.yml`: workflow aislado que ejecuta únicamente las pruebas de contrato; no realiza solicitudes a exchanges ni publica datasets.

Decisiones implementadas:

- Binance REST Klines conserva `is_final=null`; no se deduce la finalidad a partir de la hora.
- El cierre inclusivo de Binance se convierte a límite exclusivo sumando una unidad de la resolución solicitada.
- Kraken calcula el límite exclusivo desde apertura + intervalo y marca la última fila recibida como provisional, conforme a la semántica documentada del endpoint.
- Los números financieros se convierten desde texto a `Decimal`; no se utiliza `float` en los parsers.
- En Kraken no se infiere `quantity_step` a partir de `lot_decimals`.
- Los filtros específicos de Binance se preservan como extensiones del proveedor.

**Estado de CI:** la primera ejecución encontró un error en el fixture sintético de microsegundos (el valor de cierre del fixture no representaba el mismo instante que el caso en milisegundos). Se corrigió el fixture y se agregó una aserción de zona UTC. La ejecución posterior a esa corrección está pendiente de confirmación; no declarar las pruebas aprobadas hasta revisar el resultado de GitHub Actions.

## 10. Secuencia de implementación

1. Crear fixtures sintéticos mínimos.
2. Implementar parsers puros y pruebas unitarias sin red.
3. Revisar resultados y ajustar los contratos canónicos si hay discrepancias.
4. Añadir un comando de captura pública opt-in, sin persistencia raw por defecto.
5. Ejecutar capturas controladas de Binance y Kraken.
6. Documentar resultados y limitaciones en el informe de validación.
7. Solo después de la aceptación, diseñar adaptadores operativos y migraciones PostgreSQL.

## 10. Regla de seguridad

La política de persistencia es de denegación por defecto. Si la autorización de almacenamiento, caché o redistribución es desconocida, vencida o no cubre el endpoint, tipo de dato y uso concreto, no escribir los datos en Parquet, PostgreSQL ni en el repositorio. Las pruebas sintéticas no requieren ni implican autorización para almacenar datos reales.
