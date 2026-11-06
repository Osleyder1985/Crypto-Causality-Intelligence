# Revisión de condiciones de uso de fuentes — 2026-11-06

## Alcance

Esta revisión resume documentación pública de los proveedores para orientar la PoC. No es asesoría legal ni sustituye la confirmación escrita del proveedor. Las condiciones aplicables pueden depender de la jurisdicción, del tipo de usuario, del plan contratado y del producto final.

## Hallazgos por proveedor

### Binance Spot

- La documentación oficial indica que `data-api.binance.vision` es un host para endpoints de datos públicos que no requieren autenticación, incluidos `exchangeInfo` y `klines`.
- Binance mantiene términos específicos para los datasets históricos publicados en `data.binance.vision`. Esos términos conceden una licencia CC BY-NC-SA 4.0, limitan el uso a fines no comerciales y exigen una licencia empresarial escrita para uso comercial.
- El script de esta PoC consulta `data-api.binance.vision`, no descarga los archivos masivos de `data.binance.vision`. No se debe asumir sin confirmación que los términos específicos del archivo histórico se aplican de forma idéntica al endpoint REST; sí debe verificarse el alcance de los Terms of Use aplicables al API.

Referencias:
- https://developers.binance.com/en/docs/products/spot/faqs/market_data_only
- https://developers.binance.com/en/docs/products/spot/rest-api
- https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md
- https://www.binance.com/en/terms

**Estado para uso comercial:** `not_evaluated` hasta confirmar por escrito los derechos aplicables al endpoint REST y al uso previsto.

### Kraken Spot

- Los endpoints públicos de market data no requieren una API key.
- La guía oficial de Kraken indica que ciertos usos requieren permiso previo, incluidos los usos comerciales no personales de datos de endpoints públicos, como market data. La propia guía indica contactar a `marketdata@kraken.com`.
- Los términos globales también restringen la distribución y explotación comercial de su contenido salvo que estén expresamente permitidas.

Referencias:
- https://support.kraken.com/articles/360000919966-how-to-create-an-api-key
- https://docs-legacy.kraken.com/api/docs/guides/global-intro/
- https://www.kraken.com/legal/global-terms

**Estado para uso comercial:** no usar en un producto o servicio comercial sin obtener y conservar autorización escrita de Kraken.

### CoinGecko API

- Los términos de API indican que el alcance de la licencia depende del plan seleccionado.
- Se exige atribución visible con el texto `Powered by CoinGecko` en los usos aplicables.
- Los términos restringen la redistribución, sublicencia o sindicación de acceso a la API sin acuerdo específico.
- La sección de almacenamiento establece condiciones para caché y almacenamiento; también contempla eliminación de los datos al terminar el acceso, salvo autorización expresa.
- La guía de licencias de CoinGecko diferencia uso comercial de redistribución/reventa: los derechos estándar de planes comerciales no equivalen automáticamente a derechos de redistribución o reventa.

Referencias:
- https://www.coingecko.com/en/api_terms
- https://www.coingecko.com/en/api/pricing
- https://support.coingecko.com/articles/1043089972-what-are-the-differences-between-commercial-and-custom-licenses
- https://support.coingecko.com/articles/4315804955-can-i-use-coingecko-data-and-screenshots-for-my-website-book-etc

**Estado para uso comercial:** `not_evaluated` hasta seleccionar un plan que permita el uso concreto y confirmar si se requiere una licencia personalizada.

## Medida aplicada en el repositorio

A partir de la siguiente ejecución, el script cuenta las observaciones de CoinGecko en memoria y registra únicamente metadatos de la respuesta (endpoint, parámetros, estado, latencia, unidad temporal, tamaño y SHA-256). No guarda el JSON ni genera CSV con los valores de CoinGecko. El artefacto de GitHub Actions conserva únicamente el manifiesto y los archivos de Binance/Kraken.

Las ejecuciones anteriores (Runs #1–#8) sí incluyeron respuestas y CSV de CoinGecko en sus artefactos. El Run #8 tiene retención configurada hasta el 4 de febrero de 2027. No redistribuir ni reutilizar esos archivos hasta confirmar que el plan y las condiciones aplicables permiten esa conservación. Si no lo permiten, el propietario del repositorio debe eliminar los artefactos anteriores desde GitHub Actions.

## Regla provisional del proyecto

Hasta que se confirme el uso previsto y se revisen las condiciones contractuales:

1. La PoC se limita a evaluación técnica e investigación interna.
2. No publicar datasets descargados, ni revender, sublicenciar o retransmitir datos de proveedores.
3. No lanzar una aplicación, API, newsletter de pago ni servicio comercial que dependa de estos datos.
4. Registrar por proveedor el plan, la fecha de revisión, el permiso, la atribución exigida y las restricciones de almacenamiento/retención.
5. No comprar planes ni solicitar acuerdos en nombre del propietario sin autorización expresa.

## Decisión pendiente

Antes de seleccionar definitivamente los proveedores, el propietario debe definir si Crypto Causality Intelligence será:

- investigación personal/no comercial;
- proyecto público de código abierto sin monetización;
- producto o servicio comercial.

La categoría de uso cambia los permisos y la selección de fuentes. Hasta entonces, las tres fuentes permanecen técnicamente probadas, pero no aprobadas para explotación comercial.
