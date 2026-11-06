# Resultados empíricos BTC/ETH — 2026-11-06

Anexo de trazabilidad, controles adicionales y clasificación provisional: [empirical-validation-addendum-2026-11-06.md](empirical-validation-addendum-2026-11-06.md).

## Alcance

Ejecución de la PoC con ventanas UTC [inicio, fin):

- Horaria: 2026-10-07 00:00 a 2026-11-06 00:00 (720 intervalos).
- Diaria: 2025-11-21 00:00 a 2026-11-06 00:00 (350 intervalos).
- Activos: BTC y ETH.
- Fuentes: Binance Spot, Kraken Spot y CoinGecko.

La ejecución final se realizó en GitHub Actions, commit `fecaced5dad013b678df23a49b1f44dcce73f575`, Run #5:
https://github.com/Osleyder1985/Crypto-Causality-Intelligence/actions/runs/42167273763

El artefacto `issue-11-market-data-evidence` conserva respuestas JSON originales, CSV normalizados y `manifest.json`. Su retención está configurada a 90 días.

## Cobertura observada

| Proveedor | Activo | Intervalo | Registros | Esperados | Cobertura |
|---|---|---:|---:|---:|---:|
| Binance | BTC | 1h | 720 | 720 | 100 % |
| Binance | ETH | 1h | 720 | 720 | 100 % |
| Binance | BTC | 1d | 350 | 350 | 100 % |
| Binance | ETH | 1d | 350 | 350 | 100 % |
| Kraken | BTC | 1h | 715 | 720 | 99,3056 % |
| Kraken | ETH | 1h | 715 | 720 | 99,3056 % |
| Kraken | BTC | 1d | 350 | 350 | 100 % |
| Kraken | ETH | 1d | 350 | 350 | 100 % |
| CoinGecko | BTC / ETH | 1h | 720 por métrica y activo | 720 | 100 % |
| CoinGecko | BTC / ETH | 1d | 350 por métrica y activo | 350 | 100 % |

En las velas de Binance y Kraken: cero timestamps duplicados, orden cronológico correcto, cero huecos internos detectados y cero violaciones OHLC/volumen.

### Restricción de Kraken

El endpoint OHLC de Kraken devuelve como máximo 720 registros. En la consulta horaria devolvió 715 observaciones dentro de la ventana solicitada: la primera fue `2026-10-07T05:00:00Z`, cinco horas después del inicio solicitado. No se observan huecos dentro del tramo recibido. La ventana diaria de 350 registros quedó completa.

Para cualquier comparación horaria entre exchanges se debe utilizar la intersección temporal común de 715 velas; no se debe completar artificialmente la parte ausente.

### Endpoint de Binance

El primer intento contra `api.binance.com` devolvió HTTP 451 desde el runner de GitHub Actions. El resultado no se interpretó como caída del servicio. Al cambiar al host público de datos `data-api.binance.vision`, las solicitudes de klines para BTC y ETH se completaron con 100 % de cobertura en ambas ventanas.

### CoinGecko

El endpoint de rango devolvió inicialmente un punto situado exactamente en el límite final. El script se ajustó para respetar el intervalo semiabierto [inicio, fin). La ejecución final confirmó 720 observaciones por métrica en la ventana horaria y 350 en la diaria para cada activo. Son series agregadas de precio, capitalización y volumen; no son velas OHLCV de exchange.

## Concordancia exploratoria de rendimientos

Se calcularon rendimientos logarítmicos a partir del precio de apertura de cada vela de Binance/Kraken y de la observación de precio CoinGecko con timestamp coincidente. Se calculó la correlación de Pearson únicamente sobre timestamps compartidos y consecutivos.

| Activo | Intervalo | Binance–Kraken | Binance–CoinGecko | Kraken–CoinGecko |
|---|---:|---:|---:|---:|
| BTC | 1h | 0,997815 | 0,997067 | 0,996086 |
| BTC | 1d | 0,999905 | 0,990934 | 0,991049 |
| ETH | 1h | 0,999612 | 0,997566 | 0,997933 |
| ETH | 1d | 0,999962 | 0,992748 | 0,992731 |

Estos coeficientes indican alta concordancia de los rendimientos en esta muestra. No prueban causalidad, no certifican la exactitud de cada observación y no autorizan comparar directamente niveles de precio absolutos: Binance cotiza en USDT, mientras Kraken y CoinGecko usan USD. La diferencia entre USDT y USD debe mantenerse explícita.

## Pruebas automatizadas

GitHub Actions ejecutó seis pruebas unitarias y las seis aprobaron. Se verificaron timestamps UTC, ventanas continuas, huecos, duplicados y violaciones OHLC/volumen.

## Conclusión provisional

- **Binance Spot:** apto para continuar la investigación en esta PoC, con cobertura completa en ambas ventanas.
- **Kraken Spot:** apto con reserva para el tramo diario; para el horario, solo utilizar el tramo común de 715 velas o ampliar el diseño con otra fuente que permita recuperar el inicio faltante.
- **CoinGecko:** útil como referencia agregada independiente, manteniendo separada su semántica de datos respecto a OHLCV.

No se aprueba todavía la selección definitiva de fuentes. Faltan revisar licencias, metadata de mercados, semántica y unidades de volumen, conversión USDT/USD y estabilidad de las API en ejecuciones repetidas.
