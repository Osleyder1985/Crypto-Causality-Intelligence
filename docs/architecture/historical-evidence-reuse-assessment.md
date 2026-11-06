# Evaluación de reutilización de evidencia histórica — 2026-11-06

## Objetivo

Determinar si las capturas ya existentes de los Runs #13 y #14 permiten validar los parsers canónicos sin repetir solicitudes a Binance o Kraken, sin alterar ejecuciones históricas y sin publicar nuevamente valores de mercado.

## Evidencia localizada

Se consultaron los artefactos de GitHub Actions asociados a:

- [Run #13](https://github.com/Osleyder1985/Crypto-Causality-Intelligence/actions/runs/42234403548), artefacto `issue-11-exchange-evidence`, ID `13509539076`.
- [Run #14](https://github.com/Osleyder1985/Crypto-Causality-Intelligence/actions/runs/42235228173), artefacto `issue-11-exchange-evidence`, ID `13510164857`.

Al momento de la inspección, ambos artefactos figuraban como no expirados, con expiración configurada para el 4 de febrero de 2027.

### Run #13

El ZIP contiene:

- `manifest.json`.
- Ocho respuestas JSON de velas: BTC y ETH, Binance y Kraken, intervalos 1h y 1d.
- Ocho CSV normalizados correspondientes a esas ocho series.

El manifiesto registra además respuestas de metadata de Binance `exchangeInfo` y Kraken `AssetPairs`, con hashes y tamaños. Sin embargo, los archivos JSON completos de esas dos respuestas de metadata no están incluidos en el ZIP inspeccionado. Por tanto, el artefacto permite examinar payloads de velas, pero no ejecutar una validación directa de los parsers de metadata contra las respuestas originales completas.

El artefacto no contiene valores de CoinGecko; el manifiesto solo registra metadatos y conteos de esa consulta.

### Run #14

El ZIP contiene exclusivamente `manifest.json`. No contiene respuestas JSON originales ni CSV con series OHLCV. Esto concuerda con el control de publicación incorporado después de Run #13.

## Restricciones y decisión de reutilización

La revisión de condiciones de uso del proyecto identifica una diferencia entre uso interno de investigación y publicación de datos en un repositorio público:

- La investigación se mantiene clasificada como privada y no comercial.
- El repositorio GitHub es público; los artefactos de Actions no constituyen almacenamiento privado ni controlado.
- El artefacto de Run #13 contiene respuestas originales y series normalizadas de Binance/Kraken y fue publicado antes del control que limita los nuevos artefactos al manifiesto.
- Las condiciones revisadas no permiten asumir que la publicación de datasets en ese artefacto público esté autorizada. Tampoco se debe inferir que el vencimiento automático del artefacto resuelve por sí mismo las obligaciones de uso o almacenamiento.

En consecuencia, esta evaluación no copia, vuelve a publicar ni incorpora payloads o CSV históricos al repositorio. La validación automatizada contra esos valores queda pendiente de confirmar que su inspección temporal para investigación interna está cubierta por las condiciones aplicables y de definir cómo manejar el artefacto público preexistente.

No se elimina ni modifica el artefacto histórico Run #13. Cualquier acción de eliminación o cambio de retención requiere una decisión expresa del propietario y debe considerar la trazabilidad del experimento.

## Alcance de validación que sí queda establecido

1. La evidencia empírica de velas existe en el artefacto Run #13 y puede localizarse.
2. Run #14 demuestra que el workflow posterior publica únicamente el manifiesto.
3. El manifiesto de Run #13 permite revisar parámetros, unidades temporales, hashes, conteos y resultados de validación declarados.
4. Los payloads completos de metadata Binance/Kraken no están incluidos en el artefacto inspeccionado.
5. No se ha ejecutado todavía el parser nuevo sobre los payloads históricos reales.
6. Las 13 pruebas actuales siguen siendo pruebas sintéticas; no deben presentarse como validación empírica del parser.

## Próximo paso

Obtener una determinación documentada sobre el alcance permitido de inspección temporal de los archivos Binance/Kraken ya existentes. Si queda autorizado, ejecutar los parsers en un entorno efímero, comparar sus salidas con el manifiesto y los CSV normalizados existentes, registrar únicamente métricas de conformidad y discrepancias no sensibles, y descartar las copias de trabajo. No incorporar payloads, valores OHLCV ni CSV al repositorio público.

La validación de metadata requerirá una fuente original completa autorizada; el manifiesto por sí solo no sustituye esos payloads.
