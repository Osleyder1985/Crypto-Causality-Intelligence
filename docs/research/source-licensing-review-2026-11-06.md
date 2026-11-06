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

Desde Run #9, el script cuenta las observaciones de CoinGecko en memoria y registra únicamente metadatos de la respuesta (endpoint, parámetros, estado, latencia, unidad temporal, tamaño y SHA-256). No guarda el JSON ni genera CSV con los valores de CoinGecko. Run #10 confirma que el artefacto de GitHub Actions conserva únicamente el manifiesto y los archivos de Binance/Kraken.

Las ejecuciones anteriores (Runs #1–#8) sí incluyeron respuestas y CSV de CoinGecko en sus artefactos. El Run #8 tiene retención configurada hasta el 4 de febrero de 2027. No redistribuir ni reutilizar esos archivos hasta confirmar que el plan y las condiciones aplicables permiten esa conservación. Si no lo permiten, el propietario del repositorio debe eliminar los artefactos anteriores desde GitHub Actions.

## Decisión del propietario: investigación privada

El propietario ha confirmado el 6 de noviembre de 2026 que el proyecto se destina a **investigación privada y no comercial**. Esta decisión reemplaza la pregunta pendiente sobre el modelo de explotación.

### Alcance autorizado para esta fase

1. Utilizar los datos únicamente para análisis e investigación interna, sin ofrecer un producto o servicio comercial.
2. No publicar, revender, sublicenciar ni retransmitir datasets o valores de mercado obtenidos de los proveedores.
3. No asumir que el carácter privado/no comercial elimina las condiciones de cada proveedor: se deben respetar límites de almacenamiento, retención, atribución y uso aplicables.
4. Mantener CoinGecko en modo de consulta y conteo en memoria, sin archivar valores, hasta confirmar que la licencia/plan vigente permite conservarlos para investigación.
5. Mantener los datos originales y normalizados de Binance/Kraken bajo acceso controlado y sin redistribución.
6. No contratar planes ni solicitar permisos en nombre del propietario sin autorización expresa.

### Estado de aptitud

- **Binance Spot:** candidato técnico para investigación privada; revisar y conservar referencia de los términos aplicables al endpoint REST.
- **Kraken Spot:** candidato técnico para investigación privada; su requisito de permiso previo para ciertos usos comerciales no personales no debe extrapolarse automáticamente a investigación privada. Aun así, respetar los términos generales y pedir aclaración si el uso evoluciona o queda ambiguo.
- **CoinGecko:** candidato de referencia agregada; mantener sin persistencia de valores hasta confirmar el plan y las condiciones de almacenamiento aplicables.

La decisión de investigación privada no constituye asesoría legal ni una garantía de que cualquier descarga o almacenamiento esté permitido. Es la clasificación de uso adoptada por el proyecto para esta etapa.

### Nota importante sobre la visibilidad del repositorio

El repositorio GitHub actualmente tiene visibilidad **pública**. “Investigación privada” describe el uso previsto de los datos y resultados, pero no hace privado el código, la documentación, los issues, los pull requests ni los artefactos que se publiquen en GitHub. No cambiaré la visibilidad del repositorio sin autorización expresa del propietario. Si el objetivo es confidencialidad real del proyecto, habrá que convertir el repositorio en privado y revisar también los artefactos históricos de Actions.

### Medida pendiente sobre artefactos históricos

Los artefactos de Runs #1–#8 incluyen respuestas y CSV de CoinGecko, con retención configurada hasta febrero de 2027. No deben redistribuirse ni reutilizarse hasta confirmar que el plan y las condiciones aplicables permiten esa retención. El propietario puede eliminarlos desde GitHub Actions si no desea conservarlos o si los términos no lo permiten.
