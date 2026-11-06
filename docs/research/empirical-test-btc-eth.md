# Ejecución de la prueba empírica BTC y ETH

## Estado

**Informe de resultados observados:** [empirical-results-2026-11-06.md](empirical-results-2026-11-06.md).

**Preparación técnica; extracción pendiente.** Este documento describe cómo ejecutar la PoC. No contiene resultados experimentales ni presupone que las API hayan respondido correctamente.

## Diseño congelado

Fecha de corte de diseño: 2026-11-06. Los límites son UTC, inicio inclusivo y fin exclusivo.

| Ventana | Inicio UTC | Fin UTC | Granularidad | Registros continuos esperados |
|---|---|---|---|---:|
| Horaria | 2026-10-07 00:00 | 2026-11-06 00:00 | 1h | 720 |
| Diaria | 2025-11-21 00:00 | 2026-11-06 00:00 | 1d | 350 |

Si la descarga se realiza después de la fecha de corte, no se deben desplazar silenciosamente las ventanas. Se debe crear una nueva ejecución con límites nuevos, conservar el diseño original en el manifiesto y explicar el cambio.

## Instrumentos

| Proveedor | BTC | ETH | Tipo de dato |
|---|---|---|---|
| Binance Spot | BTCUSDT | ETHUSDT | Klines OHLCV del venue; quote asset USDT |
| Kraken Spot | XBT/USD | ETH/USD | OHLCV del venue; quote asset USD |
| CoinGecko | bitcoin/USD | ethereum/USD | Series agregadas de precio, market cap y volumen |

Los identificadores de Kraken se resuelven desde la clave real devuelta por el endpoint y se guardan en `market_id`. Deben verificarse contra metadata de mercados antes de una ejecución definitiva.

## Diferencias que no se deben ocultar

1. **USDT no es USD.** Los precios absolutos de Binance no se comparan directamente con los de Kraken o CoinGecko. Una conversión USDT/USD requiere una serie externa identificada, sincronizada y conservada como evidencia.
2. **CoinGecko no entrega las mismas velas.** El endpoint `market_chart/range` entrega observaciones agregadas de precios, capitalización y volumen. No contiene OHLC ni equivale al cierre de una vela de exchange. Su análisis será separado y se compararán únicamente observaciones con semántica temporal compatible.
3. **Kraken OHLC tiene un máximo de 720 observaciones.** La ventana horaria está justo en ese límite. Si falta la primera vela por incluirse una vela en curso o por la semántica del endpoint, registrar la cobertura real; no declarar cobertura completa.
4. La API puede omitir intervalos sin operaciones. Un hueco no se clasifica como pérdida hasta verificar la semántica del proveedor.
5. La respuesta de CoinGecko puede cambiar granularidad según duración, plan y política vigente. Guardar la respuesta original y sus timestamps; no inferir frecuencia a partir del nombre del archivo.

## Requisitos

- Python 3.10 o posterior.
- Acceso de red HTTPS a las API públicas.
- No se requieren dependencias de terceros ni claves API para los endpoints públicos consultados.
- Respetar límites de uso, términos y licencias vigentes.

## Ejecución

Desde la raíz del repositorio:

```bash
python scripts/research/download_validate_market_data.py
```

Para fijar otras ventanas explícitamente:

```bash
python scripts/research/download_validate_market_data.py \
  --hourly-start 2026-10-07T00:00:00Z \
  --hourly-end 2026-11-06T00:00:00Z \
  --daily-start 2025-11-21T00:00:00Z \
  --daily-end 2026-11-06T00:00:00Z \
  --out artifacts/issue-11
```

El script consulta Binance Spot, Kraken OHLC y CoinGecko `market_chart/range` para BTC y ETH. Conserva las respuestas JSON originales, genera CSV normalizados y un manifiesto de ejecución.

## Artefactos esperados

```text
artifacts/issue-11/
├── manifest.json
├── raw/
│   ├── binance_BTC_1h.json
│   ├── binance_ETH_1h.json
│   ├── kraken_BTC_1h.json
│   ├── kraken_ETH_1h.json
│   └── ...
└── normalized/
    ├── binance_BTC_1h.csv
    ├── kraken_BTC_1h.csv
    ├── coingecko_BTC_1h.csv
    └── ...
```

Los archivos exactos se generan por activo e intervalo. El hash SHA-256 de cada respuesta original se registra en el manifiesto para verificar integridad.

## Controles implementados inicialmente

- Conteo recibido frente al conteo continuo teórico.
- Cobertura temporal descriptiva.
- Timestamps duplicados y orden cronológico.
- Huecos entre aperturas consecutivas.
- Consistencia OHLC.
- Volumen negativo.
- Registro de errores de solicitud y hash de la respuesta original.

Estos controles son una primera implementación. Antes de declarar apta una fuente, se requiere revisar manualmente la semántica de velas sin operaciones, paginación, unidades de volumen, límites efectivos y licencia. La latencia de red y los parámetros de respuesta también deben quedar en el reporte final.

## Criterio de interpretación

La ejecución del script no equivale a aprobar un proveedor. Cada resultado debe clasificarse por proveedor, activo, mercado e intervalo como `suitable`, `suitable_with_reservations`, `not_suitable` o `not_evaluated`, aplicando el protocolo de `data-validation-protocol.md`.

No se rellenan huecos ni se mezclan fuentes en los datos originales. Toda transformación posterior debe producir un artefacto derivado con regla, versión y procedencia explícitas.

## Resultados preliminares observados (2026-11-06)

La primera ejecución con `api.binance.com` devolvió HTTP 451 desde el runner de GitHub Actions. Esto no demuestra una caída del proveedor. Se cambió el host de consulta al endpoint oficial de datos públicos `data-api.binance.vision` y la segunda ejecución obtuvo respuestas válidas de Binance para ambos activos e intervalos.

| Proveedor | Activo | Intervalo | Registros dentro de ventana | Esperados | Cobertura |
|---|---|---:|---:|---:|---:|
| Binance | BTC / ETH | 1h | 720 por activo | 720 | 100 % |
| Binance | BTC / ETH | 1d | 350 por activo | 350 | 100 % |
| Kraken | BTC / ETH | 1h | 715 por activo | 720 | 99,3056 % |
| Kraken | BTC / ETH | 1d | 350 por activo | 350 | 100 % |

En los cuatro conjuntos de velas de Binance y los cuatro de Kraken se observaron cero timestamps duplicados, orden cronológico correcto y cero violaciones OHLC/volumen. Kraken no presenta huecos internos en la muestra horaria; la diferencia son las cinco horas iniciales que el endpoint no devolvió al estar limitado a sus 720 registros más recientes. La primera vela horaria recibida fue `2026-10-07T05:00:00Z`, frente al inicio solicitado `2026-10-07T00:00:00Z`. La muestra diaria de Kraken sí cubrió los 350 días.

La primera respuesta de CoinGecko incluyó una observación situada exactamente en el límite final exclusivo (`2026-11-06T00:00:00Z`): 721 observaciones por métrica en la consulta horaria y 351 en la diaria. Se corrigió el script para aplicar explícitamente la ventana `[inicio, fin)` antes de normalizar. Esta corrección debe confirmarse en la siguiente ejecución; los conteos corregidos aún no se consideran verificados.

Las ejecuciones pueden consultarse en [Run #1](https://github.com/Osleyder1985/Crypto-Causality-Intelligence/actions/runs/42167079775) y [Run #2](https://github.com/Osleyder1985/Crypto-Causality-Intelligence/actions/runs/42167129625). Los artefactos de Actions son temporales; los resultados no deben considerarse evidencia archivada a largo plazo hasta incorporarlos al repositorio o a un almacenamiento persistente.

Estos resultados son controles iniciales de integridad y cobertura, no una aprobación definitiva de las fuentes ni una validación de causalidad de mercado. Sigue pendiente revisar unidades y semántica de volumen, metadatos del mercado, alineación temporal entre proveedores y licencias.

## Referencias oficiales

- Binance Spot klines: https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints (el script usa el host público de datos `data-api.binance.vision`, sin endpoints de trading)
- Kraken OHLC: https://docs.kraken.com/api/docs/rest-api/get-ohlc-data
- CoinGecko market chart range: https://docs.coingecko.com/reference/coins-id-market-chart-range
- Protocolo interno: [data-validation-protocol.md](../../docs/research/data-validation-protocol.md)
- Catálogo interno: [source-catalog.md](../../docs/research/source-catalog.md)
