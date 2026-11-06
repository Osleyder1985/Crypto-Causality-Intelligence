# Resultados empíricos BTC/ETH — 2026-11-06

**Versión vigente:** esta versión sustituye los conteos y comparaciones preliminares publicados antes de la revisión de condiciones de uso. Los valores de CoinGecko y las métricas derivadas de esa fuente no se publican aquí mientras se confirma la licencia aplicable.

Informe complementario: [anexo de validación](empirical-validation-addendum-2026-11-06.md) y [revisión de condiciones de uso](source-licensing-review-2026-11-06.md).

## Diseño

- Activos: BTC y ETH.
- Binance Spot: BTCUSDT y ETHUSDT.
- Kraken Spot: XBT/USD y ETH/USD.
- CoinGecko: consultado como referencia agregada, pero no se archivan ni publican sus valores desde Run #9.
- Ventana horaria: 2026-10-07T00:00:00Z a 2026-11-06T00:00:00Z (fin exclusivo).
- Ventana diaria: 2025-11-21T00:00:00Z a 2026-11-06T00:00:00Z (fin exclusivo).

## Cobertura de velas de exchanges

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

En los conjuntos de velas Binance/Kraken revisados: cero duplicados, orden cronológico correcto, cero huecos internos, cero timestamps desalineados, cero registros fuera de ventana, cero volúmenes cero y cero violaciones OHLC/volumen.

### Restricción de Kraken

El endpoint OHLC de Kraken devuelve como máximo 720 registros. La consulta horaria produjo 715 velas dentro de la ventana solicitada; la primera fue `2026-10-07T05:00:00Z`, cinco horas después del inicio. No se detectaron huecos internos en el tramo recibido. Para comparar exchanges en 1h debe utilizarse únicamente la intersección común de 715 velas. La ventana diaria quedó completa.

### Binance

El primer intento con `api.binance.com` devolvió HTTP 451 desde GitHub Actions. No se interpretó como caída del proveedor. El host oficial de datos públicos `data-api.binance.vision` respondió correctamente; la ejecución final obtuvo HTTP 200 y 100 % de cobertura para ambos activos e intervalos.

## Trazabilidad y ejecución final

Run #10:
https://github.com/Osleyder1985/Crypto-Causality-Intelligence/actions/runs/42167688358

El manifiesto registra endpoint, parámetros de consulta, HTTP status, latencia, reintentos, hora de captura, unidad temporal y SHA-256. Las solicitudes finalizaron con HTTP 200 y cero reintentos. La ejecución de referencia observó latencias de 667–940 ms para Binance y 191–323 ms para Kraken; son mediciones de una sola ejecución, no un SLA.

GitHub Actions ejecutó siete pruebas unitarias y las siete aprobaron. El artefacto `issue-11-exchange-evidence` conserva el manifiesto y las respuestas/CSV de Binance y Kraken durante 90 días.

## CoinGecko: tratamiento provisional

CoinGecko respondió correctamente y el script contó observaciones dentro de la ventana en memoria. Desde Run #9 no se guarda su respuesta JSON ni se generan CSV con sus valores; el manifiesto conserva solo metadatos de solicitud, tamaño, hash y conteos por métrica. No se publican conteos detallados ni estadísticas derivadas de CoinGecko hasta confirmar el plan y los derechos de almacenamiento/uso.

Los artefactos de Runs #1–#8 contienen respuestas y CSV de CoinGecko, con retención configurada hasta febrero de 2027. No redistribuirlos ni reutilizarlos hasta confirmar que las condiciones aplicables permiten esa conservación. Si no lo permiten, el propietario debe eliminarlos desde GitHub Actions.

## Conclusión provisional

- **Binance Spot:** técnicamente apto para continuar la PoC, con cobertura completa. La aprobación para uso comercial sigue pendiente de verificar los términos aplicables al endpoint REST.
- **Kraken Spot:** técnicamente apto con reservas; cobertura diaria completa y ventana horaria limitada al tramo común de 715 velas. El uso comercial no personal requiere permiso previo según la guía de Kraken.
- **CoinGecko:** consulta técnica comprobada, pero su uso, almacenamiento y publicación quedan en espera de confirmar el plan y la licencia.

La PoC no demuestra causalidad de mercado ni aprueba definitivamente proveedores. Siguen pendientes metadata de mercado, semántica completa de volumen, licencias, permisos comerciales, tratamiento USD/USDT y estabilidad en ejecuciones repetidas.
