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

## Actualización de captura — Run #13

La ejecución Run #13, posterior a la incorporación de metadata y normalización ampliada, finalizó correctamente:

https://github.com/Osleyder1985/Crypto-Causality-Intelligence/actions/runs/42234403548

- 11/11 pruebas unitarias aprobadas.
- Extracción y validación completadas.
- Artefacto `issue-11-exchange-evidence` creado y conservado durante 90 días.
- Metadata Binance `exchangeInfo`: HTTP 200, cero reintentos, 1.865 ms; SHA-256 `4e66c0d7e2632b7d990ecb850932e9b2c8c6513f39e787a0f449f664ad52282a`.
- Metadata Kraken `AssetPairs`: HTTP 200, cero reintentos, 296 ms; SHA-256 `e55a61b0fd718a757c9fed185c5d16e1b80c625830512428355f412800e08364`.
- Binance confirmó BTCUSDT y ETHUSDT como `TRADING`, con Spot habilitado.
- Kraken confirmó XBT/USD y ETH/USD como `online`.

### Cobertura de la nueva captura

| Proveedor | Activo | Intervalo | Registros | Esperados | Cobertura teórica |
|---|---|---:|---:|---:|---:|
| Binance | BTC | 1h | 720 | 720 | 100 % |
| Binance | ETH | 1h | 720 | 720 | 100 % |
| Kraken | BTC | 1h | 706 | 720 | 98,0556 % |
| Kraken | ETH | 1h | 706 | 720 | 98,0556 % |
| Binance | BTC | 1d | 350 | 350 | 100 % |
| Binance | ETH | 1d | 350 | 350 | 100 % |
| Kraken | BTC | 1d | 350 | 350 | 100 % |
| Kraken | ETH | 1d | 350 | 350 | 100 % |

En los ocho conjuntos no se detectaron duplicados, huecos internos, timestamps desalineados, registros fuera de ventana ni violaciones OHLC/volumen. Los campos de conteo de operaciones estuvieron presentes en todas las velas recibidas y no registraron conteos cero.

### Interpretación de Kraken 1h

La respuesta REST sin filtrar contiene 721 observaciones, desde 2026-10-07 14:00 UTC hasta 2026-11-06 14:00 UTC, incluyendo la vela en curso. Al aplicar la ventana exclusiva que termina a las 00:00 UTC del 6 de noviembre, quedan 706 observaciones desde el 7 de octubre a las 14:00 UTC hasta el 5 de noviembre a las 23:00 UTC.

El tramo recibido es continuo: no presenta huecos internos. La reducción de 14 observaciones frente a las 720 esperadas se explica por el límite de observaciones recientes y el momento de la consulta, no por una evidencia de pérdida interna de datos. La comparación horaria entre exchanges debe restringirse a la intersección común de 706 velas en esta captura. La cobertura diaria sigue completa.

Las latencias indicadas son mediciones de una sola ejecución y no constituyen un SLA. La captura demuestra que la nueva implementación funciona en este run; no demuestra estabilidad temporal ni disponibilidad histórica uniforme. Se requieren ejecuciones repetidas para evaluar esa dimensión.

## Control de publicación de evidencia tras la revisión de condiciones de uso

A partir del cambio posterior a Run #13, GitHub Actions conserva como artefacto únicamente el manifiesto técnico. Los JSON originales y CSV normalizados de Binance/Kraken ya no se adjuntan a los nuevos artefactos públicos. Los valores se procesan durante la ejecución en el runner efímero; el manifiesto conserva hashes, conteos, parámetros, estados y métricas de validación, sin publicar las series OHLCV.

El artefacto de Run #13 es anterior a este control y contiene datos originales/normalizados. Sigue sujeto a una decisión específica de retención o eliminación; no se ha eliminado automáticamente. Véase la [revisión de condiciones de uso](source-licensing-review-2026-11-06.md).

## Verificación del control de publicación — Run #14

Después de limitar el workflow al manifiesto, la ejecución [Run #14](https://github.com/Osleyder1985/Crypto-Causality-Intelligence/actions/runs/42235228173) finalizó correctamente:

- Pruebas unitarias, extracción, controles y carga del artefacto: completados correctamente.
- Metadata Binance y Kraken: ambas solicitudes HTTP 200.
- La cobertura técnica volvió a ser 720/720 velas horarias para Binance y 706/720 para Kraken, para BTC y ETH; las cuatro series diarias quedaron en 350/350.
- No se detectaron duplicados, huecos internos ni violaciones OHLC/volumen en los ocho conjuntos.
- Se descargó e inspeccionó el ZIP del artefacto: contiene exclusivamente `manifest.json` (37.424 bytes). No contiene JSON originales ni CSV con series OHLCV.

Esta ejecución confirma que el control de publicación funciona y que la extracción/validación sigue operativa. No resuelve los permisos contractuales de almacenamiento local ni la exposición del artefacto histórico Run #13.
