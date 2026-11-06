# Anexo de validación y trazabilidad — 2026-11-06

Revisión de condiciones de uso: [source-licensing-review-2026-11-06.md](source-licensing-review-2026-11-06.md).

## Ejecución reproducible

Run #8 de GitHub Actions:
https://github.com/Osleyder1985/Crypto-Causality-Intelligence/actions/runs/42167506238

Commit: `a76b5c9d8227a5b8ad9ddc58af15d20709adaac8`.

El artefacto conserva respuestas JSON originales, CSV normalizados y manifiesto. Retención configurada: 90 días.

## Controles adicionales observados

El manifiesto registra endpoint, parámetros de consulta, código HTTP, latencia, reintentos, momento de captura, unidad del timestamp y hash SHA-256 de cada respuesta original.

- Solicitudes: todas HTTP 200, cero reintentos.
- Latencia Binance: 667–788 ms.
- Latencia Kraken: 235–323 ms.
- Latencia CoinGecko: 110–217 ms.
- Registros fuera de ventana: cero.
- Timestamps desalineados: cero.
- Registros con volumen cero: cero.
- Duplicados, huecos internos y violaciones OHLC/volumen: cero en las velas revisadas.
- Pruebas unitarias: 7 de 7 aprobadas.

Las latencias corresponden a una sola ejecución desde GitHub Actions en la región central de EE. UU.; no representan un SLA ni rendimiento sostenido.

## Clasificación provisional según el protocolo

| Fuente y uso | Estado | Motivo |
|---|---|---|
| Binance Spot, BTC/ETH, 1h y 1d | `suitable_with_reservations` | Cobertura completa y controles iniciales aprobados; faltan licencias, metadata de mercado y revisión completa de volumen. |
| Kraken Spot, BTC/ETH, 1d | `suitable_with_reservations` | Cobertura completa; faltan verificaciones de metadata, volumen y licencia. |
| Kraken Spot, BTC/ETH, 1h | `suitable_with_reservations` | Límite de 720 puntos; solo es válido el tramo común de 715 velas. |
| CoinGecko, BTC/ETH, 1h y 1d | `suitable_with_reservations` | Serie agregada con cobertura confirmada; no sustituye OHLCV de un venue. |

La clasificación aplica al activo, intervalo y uso evaluado; no es una aprobación general del proveedor.

## Próximas verificaciones

1. Revisar metadata oficial de los mercados y vigencia de los instrumentos.
2. Documentar semántica de volumen base/cotizado y tratamiento de velas sin operaciones.
3. Verificar licencias, almacenamiento y redistribución.
4. Definir si se requiere una serie USDT/USD para comparar niveles de precio.
5. Repetir la captura en otra fecha para evaluar estabilidad y revisiones históricas.
