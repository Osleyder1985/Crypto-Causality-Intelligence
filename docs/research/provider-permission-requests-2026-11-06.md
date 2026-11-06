# Verificación documental de permisos y retención de datos — 2026-11-06

## 1. Objetivo y criterio

Este documento establece una revisión documental previa para decidir si hace falta consultar a Binance, Kraken o CoinGecko.

**Regla de trabajo:** no contactar a soporte para pedir que repita información que ya aparece en términos, políticas o documentación oficial. Primero se identifica la cláusula aplicable, se registra su alcance y se adapta el uso del proyecto. Solo se prepara una consulta cuando queda una ambigüedad material que no puede resolverse con documentación pública ni con información disponible en la cuenta del proyecto.

**Estado:** revisión documental en curso. No se ha contactado a ningún proveedor, no se ha contratado ningún plan y no se ha eliminado ningún artefacto.

## 2. Contexto del proyecto

Crypto Causality Intelligence es una investigación técnica no comercial sobre integridad temporal, cobertura, consistencia OHLCV, procedencia y reproducibilidad de datos de mercado.

Fuentes de la prueba empírica:

- Binance Spot: `BTCUSDT` y `ETHUSDT`.
- Kraken Spot: `XBT/USD` y `ETH/USD`.
- CoinGecko: datos históricos agregados de Bitcoin y Ethereum.

El repositorio GitHub es público. Los artefactos nuevos se han limitado a manifiestos técnicos sin valores OHLCV ni respuestas originales. Persisten artefactos históricos pendientes de decisión:

- Binance/Kraken: Run #13, con respuestas originales y CSV normalizados.
- CoinGecko: Runs #1–#8, con respuestas y CSV normalizados.

No se debe interpretar el carácter no comercial de la investigación como una autorización automática para publicar o redistribuir datos.

## 3. Resultado de la revisión por proveedor

### 3.1 Binance Spot

**Lo que la documentación oficial confirma**

La página oficial *Market Data Only URLs* indica que `data-api.binance.vision` ofrece endpoints REST públicos que no requieren autenticación y enumera expresamente `GET /api/v3/klines` y `GET /api/v3/exchangeInfo`. Esto confirma que el host y los endpoints usados en la prueba corresponden al servicio oficial de datos públicos.

**Lo que no queda resuelto por esa página**

La documentación de acceso técnico no concede por sí misma derechos específicos de almacenamiento histórico, retención de respuestas, publicación de datos o publicación de artefactos derivados. Tampoco debe suponerse que los términos de los datasets descargables de Binance Vision (`data.binance.vision`) se aplican automáticamente al host REST `data-api.binance.vision`.

**Decisión operativa provisional**

- Mantener las nuevas ejecuciones limitadas a manifiestos metadata-only.
- No publicar respuestas REST originales ni series OHLCV.
- No ampliar ni redistribuir el artefacto histórico Run #13.
- No abrir una consulta general sobre acceso público: eso ya está documentado.

**Única ambigüedad que podría justificar una consulta posterior**

Si se considera necesario conservar o publicar el artefacto histórico Run #13, determinar primero si los términos aplicables a las respuestas REST de `data-api.binance.vision` permiten esa retención o publicación. La consulta, si finalmente resulta necesaria, deberá limitarse a ese caso y citar los endpoints exactos. No preguntar por el funcionamiento de los endpoints ni por el carácter público de los datos.

Fuentes:
- Market Data Only URLs: https://developers.binance.com/en/docs/products/spot/faqs/market_data_only
- Spot REST API: https://developers.binance.com/en/docs/products/spot/rest-api
- Binance Vision Terms: https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md

### 3.2 Kraken Spot

**Lo que la documentación oficial confirma**

La guía oficial de Kraken indica que ciertos usos de sus APIs requieren permiso previo e incluye como ejemplo el uso comercial no personal de datos de endpoints públicos. La guía identifica `marketdata@kraken.com` como canal para solicitar ese permiso.

**Aplicación al proyecto**

La finalidad declarada del proyecto es investigación no comercial. Por tanto, no corresponde enviar una consulta genérica preguntando si cualquier investigación privada necesita autorización: la documentación citada no formula esa exigencia de manera general.

Sin embargo, la guía no establece por sí sola una política detallada de retención histórica ni resuelve inequívocamente si la publicación de respuestas o series de datos en un repositorio público se considera un uso que requiere autorización.

**Decisión operativa provisional**

- Mantener las nuevas ejecuciones limitadas a manifiestos metadata-only.
- No publicar respuestas originales ni series OHLCV.
- No ampliar ni redistribuir el artefacto histórico Run #13.
- No pedir aclaración sobre el supuesto ya definido de uso comercial no personal.

**Única ambigüedad que podría justificar una consulta posterior**

Solo si el proyecto pretende conservar o publicar el artefacto histórico Run #13, consultar si esa retención o publicación concreta está permitida bajo los términos aplicables. La consulta deberá describir exactamente el contenido, el carácter público del repositorio y la finalidad no comercial. Si se decide no conservar ni publicar esos datos, no será necesario contactar a Kraken por este asunto.

Fuentes:
- Kraken API Guide: https://docs-legacy.kraken.com/api/docs/guides/global-intro/
- Kraken Global Terms: https://www.kraken.com/legal/global-terms
- Public OHLC endpoint: https://docs.kraken.com/api/docs/rest-api/get-ohlc-data

### 3.3 CoinGecko API

**Lo que los términos oficiales ya definen**

La versión publicada de los API Terms indica:

- El alcance de la licencia depende del plan de uso aplicable.
- Si se almacenan o cachean datos, la caché debe actualizarse al menos cada 24 horas y deben aplicarse cifrado robusto y otras medidas de seguridad.
- Si CoinGecko termina el acceso a la API, los datos y demás información almacenados por el uso de la API deben eliminarse de forma pronta y permanente, sin conservar copias salvo obligación legal.
- Fuera de los supuestos expresamente permitidos, los términos restringen duplicar, reproducir, copiar, almacenar, derivar o traducir los datos.

La guía de licencias también aclara que los planes de pago incluyen derechos comerciales estándar para ciertos usos, pero no conceden automáticamente derechos de redistribución o distribución de datasets. Para informes de investigación permite figuras limitadas junto con análisis original bajo las condiciones de atribución indicadas.

**Decisión operativa provisional**

- No preguntar a soporte por las reglas generales de caché, almacenamiento, eliminación o redistribución: están descritas en los términos.
- No archivar nuevos valores de CoinGecko en ejecuciones futuras.
- No publicar ni redistribuir los artefactos históricos Runs #1–#8.
- Antes de decidir qué hacer con esos artefactos, identificar el plan y los términos que correspondían a la cuenta durante las fechas de ejecución.

**Paso previo a cualquier consulta**

Revisar el panel de cuenta, historial de facturación, correos de alta/renovación y registros disponibles para identificar el plan y las fechas de vigencia. No compartir API keys ni credenciales.

**Única ambigüedad que podría justificar una consulta posterior**

Si los registros de la cuenta no permiten identificar el plan histórico o si, una vez identificado, los términos aplicables no resuelven el tratamiento de los archivos Runs #1–#8 tras la expiración/cambio de plan, formular una pregunta puntual sobre ese escenario histórico. No pedir que soporte vuelva a explicar las reglas generales que ya aparecen en los términos.

Fuentes:
- CoinGecko API Terms: https://www.coingecko.com/en/api_terms
- CoinGecko licensing FAQ: https://support.coingecko.com/articles/1043089972-what-are-the-differences-between-commercial-and-custom-licenses
- API pricing: https://www.coingecko.com/en/api/pricing

## 4. Registro de verificación y consultas

| Proveedor | Información ya definida | Verificación interna pendiente | ¿Contactar ahora? |
|---|---|---|---|
| Binance | Host de datos públicos y endpoints disponibles | Determinar si se pretende conservar/publicar Run #13 y qué términos REST aplican a ese caso | No |
| Kraken | Permiso previo para ciertos usos, incluido uso comercial no personal | Determinar si se pretende conservar/publicar Run #13 | No |
| CoinGecko | Condiciones generales de caché, almacenamiento, seguridad, eliminación y redistribución | Identificar plan histórico y fechas de vigencia para Runs #1–#8 | No |

No registrar una consulta como enviada hasta que exista evidencia del envío y un número de ticket o referencia.

## 5. Secuencia de trabajo acordada

1. Completar la revisión documental y conservar enlaces a las cláusulas oficiales.
2. Consultar los registros propios para identificar el plan histórico de CoinGecko.
3. Determinar qué artefactos históricos se pretende conservar, sin eliminarlos todavía.
4. Si una ambigüedad material persiste, redactar una consulta breve que cite la cláusula revisada y pregunte exclusivamente por el punto no resuelto.
5. Registrar la respuesta y actualizar el Issue #12.
6. Mantener los artefactos nuevos en formato metadata-only mientras no exista una decisión documentada distinta.

## 6. Decisiones reservadas al propietario

- Enviar cualquier consulta a proveedores.
- Facilitar identificadores de cuenta u otra información personal o de cuenta.
- Contratar planes, licencias o aceptar acuerdos.
- Eliminar los artefactos CoinGecko Runs #1–#8.
- Eliminar el artefacto Binance/Kraken Run #13.
- Cambiar la visibilidad del repositorio.

## 7. Estado de contacto

| Proveedor | Estado |
|---|---|
| Binance | No contactado |
| Kraken | No contactado |
| CoinGecko | No contactado |

Fecha de revisión documental: 2026-11-06.
