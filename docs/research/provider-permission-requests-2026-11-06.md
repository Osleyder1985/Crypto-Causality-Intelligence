# Solicitudes de aclaración sobre uso y retención de datos — 2026-11-06

## Propósito y estado

Este documento prepara solicitudes para obtener respuestas escritas de Binance, Kraken y CoinGecko sobre el uso de datos de mercado en Crypto Causality Intelligence.

**Estado: borradores no enviados.** No se ha contactado a ningún proveedor, no se ha contratado ningún plan y no se ha solicitado ni ejecutado ninguna eliminación. El envío requiere una acción expresa del propietario.

La investigación se ha clasificado como privada y no comercial. Sin embargo, el repositorio GitHub es público. Por ello, las solicitudes distinguen entre el análisis interno y la exposición pública de archivos o manifiestos.

## Descripción común del proyecto

Crypto Causality Intelligence es un proyecto de investigación técnica no comercial. En la prueba empírica se consultaron datos públicos de mercado para BTC y ETH:

- Binance Spot: `BTCUSDT` y `ETHUSDT`.
- Kraken Spot: `XBT/USD` y `ETH/USD`.
- CoinGecko: referencias agregadas para Bitcoin y Ethereum.

No se ejecutan operaciones, no se ofrecen servicios comerciales y no se revenden ni redistribuyen feeds. El proyecto evalúa integridad temporal, cobertura, consistencia OHLCV, procedencia y reproducibilidad.

El repositorio es público, aunque el propósito de la investigación es privado/no comercial. Los nuevos artefactos de CI se han limitado a un manifiesto técnico sin valores OHLCV. Existe un artefacto histórico Run #13 de Binance/Kraken con respuestas y CSV normalizados, y artefactos de CoinGecko de Runs #1–#8 con respuestas/CSV. No se ha eliminado ninguno.

---

## 1. Binance Spot

**Canal de contacto identificado:** Centro de soporte oficial: https://www.binance.com/en/support  
No se ha verificado una dirección de correo pública específica para consultas de licencia de Market Data. Se recomienda abrir un caso desde el soporte oficial y solicitar que se derive al equipo responsable de Spot API / Market Data / legal.

**Asunto sugerido:** Clarification on permitted use and retention of public Binance Spot REST market data for non-commercial research

### Borrador en inglés para soporte

Hello Binance Support,

I am conducting a private, non-commercial research project called Crypto Causality Intelligence. The project evaluates the technical quality and reproducibility of public cryptocurrency market data. It does not execute trades, provide a commercial service, resell data, or redistribute market-data feeds.

For the empirical test, the project queried the following public Binance Spot REST endpoints through the Market Data Only host:

- `https://data-api.binance.vision/api/v3/klines`
- `https://data-api.binance.vision/api/v3/exchangeInfo`

The markets examined were BTCUSDT and ETHUSDT.

We understand that Binance Vision dataset terms refer to datasets distributed through `data.binance.vision`. We do not want to assume that those dataset-specific terms either apply or do not apply to the separate REST host `data-api.binance.vision`.

Could you please confirm in writing:

1. Which Binance terms, policies, or licenses govern responses obtained from the two REST endpoints above when accessed through `data-api.binance.vision`?
2. May an individual researcher process these responses locally for private, non-commercial analysis and reproducibility testing?
3. May raw responses and normalized OHLCV values be stored temporarily or retained for a defined period in private research storage? If so, what retention, security, attribution, or deletion conditions apply?
4. May a public GitHub repository contain a metadata-only execution manifest with endpoint names, request parameters, timestamps, HTTP status codes, latency, record counts, validation outcomes, and cryptographic hashes, provided it contains no market prices, OHLCV values, raw responses, or downloadable datasets?
5. Does public availability of that metadata-only manifest change the permitted-use analysis?
6. Would any additional permission be required if the project later publishes analytical findings without reproducing raw market data or substantial market-data extracts?

No request is being made for trading access or private account data. We would appreciate links to the applicable terms and, if necessary, referral to the team authorized to clarify these questions.

Thank you.

### Canal y referencia

- Binance Support: https://www.binance.com/en/support
- Spot Market Data Only FAQ: https://developers.binance.com/en/docs/products/spot/faqs/market_data_only
- Spot REST API: https://developers.binance.com/en/docs/products/spot/rest-api
- Binance Vision Terms: https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md

**Pendiente antes del envío:** abrir caso desde el soporte oficial y guardar el número de ticket. No adjuntar respuestas de mercado ni claves API.

---

## 2. Kraken Spot

**Canal de contacto:** `marketdata@kraken.com`, indicado en la guía oficial de API para solicitudes de permiso relacionadas con determinados usos de datos públicos.

**Asunto sugerido:** Request for written clarification — private non-commercial research using public Kraken Spot market data

### Borrador en inglés

Hello Kraken Market Data Team,

I am conducting a private, non-commercial research project called Crypto Causality Intelligence. The project evaluates the integrity, temporal coverage, provenance, and reproducibility of public cryptocurrency market data. It does not execute trades, provide a commercial service, resell data, or redistribute market-data feeds.

The empirical test queried Kraken Spot public REST endpoints:

- `/0/public/OHLC`
- `/0/public/AssetPairs`

The markets examined were XBT/USD and ETH/USD.

We have reviewed Kraken's API guidance stating that prior permission is required for certain uses, including non-personal commercial use of data from publicly accessible endpoints. We would like to avoid interpreting that provision beyond its stated scope and request clarification for the use described below.

Could you please confirm in writing:

1. Is private, individual, non-commercial research and internal analysis of public Spot OHLC and AssetPairs responses permitted without additional prior permission, subject to the applicable Kraken terms and API limits?
2. May raw responses and normalized OHLCV data be stored in private research storage for reproducibility? If so, are there retention, security, or deletion limits?
3. May a public GitHub repository contain only a metadata-only execution manifest (endpoint names, parameters, timestamps, HTTP status, latency, record counts, validation results, and cryptographic hashes), with no prices, OHLCV values, raw responses, or downloadable datasets?
4. Does public availability of that metadata-only manifest require separate permission?
5. Would permission be required for a future publication of research conclusions or derived statistics that do not reproduce raw market data or substantial extracts?
6. If the project's purpose or distribution changes in the future, what process should be followed to request the appropriate permission?

The repository is publicly visible, although the project purpose is private and non-commercial. New CI artifacts have been restricted to metadata-only manifests. A historical CI artifact containing raw and normalized Binance/Kraken market data remains retained pending clarification; it has not been redistributed intentionally as a dataset.

Please identify any applicable terms, retention requirements, or additional conditions in your response.

Thank you.

### Canal y referencia

- Email: marketdata@kraken.com
- API guide: https://docs-legacy.kraken.com/api/docs/guides/global-intro/
- Kraken Global Terms: https://www.kraken.com/legal/global-terms
- Public OHLC endpoint: https://docs.kraken.com/api/docs/rest-api/get-ohlc-data

**Pendiente antes del envío:** confirmar si se desea mencionar explícitamente el identificador del artefacto Run #13. No adjuntar archivos con datos de mercado.

---

## 3. CoinGecko API

**Canales de contacto identificados:**

- Formulario oficial de soporte: https://support.coingecko.com/hc/en-us/requests/new
- Dirección publicada para consultas API: `api@coingecko.com`
- Guía de licencias: https://support.coingecko.com/articles/1043089972-what-are-the-differences-between-commercial-and-custom-licenses

**Asunto sugerido:** Request for clarification on historical API plan, research retention, and legacy CI artifacts

### Borrador en inglés

Hello CoinGecko API Support,

I am conducting a private, non-commercial research project called Crypto Causality Intelligence. The project evaluates historical cryptocurrency market data for research reproducibility and comparison. It does not sell data, provide a commercial data service, sublicense API access, or redistribute raw CoinGecko feeds.

The project queried CoinGecko historical market-chart data for Bitcoin and Ethereum, including price, market capitalization, and 24-hour volume observations.

We have reviewed the CoinGecko API Terms and the licensing guidance. New project runs no longer persist CoinGecko market values; they retain only technical request metadata and process observations in memory.

We need help identifying the applicable subscription and clarifying the treatment of historical CI artifacts:

1. Can you confirm which API plan or license was associated with the account/API key used during the historical runs listed below? We can provide account identification through an appropriate secure support channel if required.
2. For the plan and terms applicable at the time of those runs, was temporary storage or retention of raw API responses and normalized CSV files for private, non-commercial research permitted? What retention period and security requirements applied?
3. Do the current API Terms permit a metadata-only public execution manifest containing endpoint names, request parameters, timestamps, HTTP status, latency, response size, cryptographic hashes, and record counts, without publishing market values or raw responses?
4. What is the required treatment of historical response/CSV artifacts created while a subscription was active if the plan later expires or changes?
5. Are the historical artifacts required to be deleted upon termination of API access, and are there exceptions for internal research records or metadata-only manifests?
6. May the project publish research conclusions or limited derived comparisons with attribution, without publishing raw API responses or redistributable datasets?
7. If additional rights are required for any of these activities, which license or plan would cover them, and what specific terms should be reviewed before proceeding?

Historical artifacts exist for CI Runs #1–#8 and contain CoinGecko API responses and normalized CSV values. The project has not intentionally redistributed those artifacts as a dataset. New runs do not archive CoinGecko values.

We would appreciate a written response identifying the applicable plan, historical terms, and any required retention or deletion actions. We will not make changes to the historical artifacts until the applicable requirements are clear.

Thank you.

### Canal y referencias

- Support request form: https://support.coingecko.com/hc/en-us/requests/new
- API support contact: api@coingecko.com
- API Terms: https://www.coingecko.com/en/api_terms
- Licensing FAQ: https://support.coingecko.com/articles/1043089972-what-are-the-differences-between-commercial-and-custom-licenses
- API pricing and plan descriptions: https://www.coingecko.com/en/api/pricing

**Datos que deben completarse antes del envío, si están disponibles:** identificador de cuenta, nombre del plan, fechas de suscripción y fechas aproximadas de Runs #1–#8. No incluir ni enviar la API key. Si no se conoce el plan histórico, pedir que CoinGecko lo identifique a partir de la cuenta por un canal seguro.

---

## Registro de envío y respuestas

No completar esta tabla hasta que los mensajes hayan sido enviados y exista evidencia.

| Proveedor | Canal | Estado | Ticket / referencia | Respuesta recibida |
|---|---|---|---|---|
| Binance | Centro de soporte | Borrador no enviado | — | — |
| Kraken | marketdata@kraken.com | Borrador no enviado | — | — |
| CoinGecko | Formulario / api@coingecko.com | Borrador no enviado | — | — |

## Reglas para evaluar las respuestas

Una respuesta se considerará suficiente únicamente si identifica:

- La entidad/proveedor y los términos o versión aplicables.
- Los endpoints y tipos de datos cubiertos.
- La finalidad permitida: investigación privada/no comercial.
- Si permite almacenamiento temporal y retención, y durante cuánto tiempo.
- Si permite publicar un manifiesto sin valores de mercado en un repositorio público.
- Qué ocurre con los datos históricos al terminar o cambiar un plan.
- Si hay obligaciones de atribución, seguridad, eliminación o autorización adicional.

No interpretar una respuesta genérica de soporte como una licencia amplia. Si la respuesta es ambigua, solicitar aclaración adicional y mantener las medidas preventivas.

## Decisiones que siguen reservadas al propietario

- Enviar cada solicitud.
- Facilitar identificadores de cuenta o información adicional a los proveedores.
- Aceptar planes, licencias, pagos o acuerdos.
- Eliminar los artefactos CoinGecko Runs #1–#8.
- Eliminar el artefacto Binance/Kraken Run #13.
- Cambiar la visibilidad del repositorio.

## Fuentes oficiales consultadas

- Binance Support: https://www.binance.com/en/support
- Binance Spot Market Data Only: https://developers.binance.com/en/docs/products/spot/faqs/market_data_only
- Kraken API Guide: https://docs-legacy.kraken.com/api/docs/guides/global-intro/
- CoinGecko API Terms: https://www.coingecko.com/en/api_terms
- CoinGecko licensing FAQ: https://support.coingecko.com/articles/1043089972-what-are-the-differences-between-commercial-and-custom-licenses

Fecha de preparación: 2026-11-06.
