# Procedencia de datos y semántica temporal

## Propósito

La investigación histórica debe establecer no solo qué dice un registro, sino también cuándo ocurrió el evento subyacente, cuándo se publicó la información y desde cuándo pudo utilizarla el sistema.

## Definiciones de marcas de tiempo

| Campo | Definición | Notas |
|---|---|---|
| `event_time` | Momento en que ocurrió el evento en el mundo real | Puede ser desconocido, aproximado o estar representado como un intervalo. |
| `published_at` | Momento en que una fuente hizo público un documento o anuncio | Conservar la precisión y la zona horaria proporcionadas por la fuente cuando estén disponibles. |
| `captured_at` | Momento en que el sistema recuperó o capturó el contenido de la fuente | Registrar por separado los fallos de recuperación y las capturas retrasadas. |
| `ingested_at` | Momento en que el registro se incorporó al almacén de datos gestionado por la plataforma | Lo genera el sistema de ingesta. |
| `available_at` | Primer momento defendible en que el registro estuvo disponible para su uso según la política de información declarada por la plataforma | No debe retrotraerse simplemente porque el evento subyacente ocurrió antes. |

Estos campos no son intercambiables. Algunos registros no tendrán todas las marcas de tiempo. Los valores desconocidos deben permanecer como desconocidos, en lugar de inferirse sin un método explícito y documentado.

## Corrección point-in-time

La política predeterminada de investigación exige disponibilidad estricta point-in-time.

Un registro puede utilizarse en un análisis con corte temporal `T` únicamente si se conoce su `available_at` y es menor o igual que `T`, sujeto a la política de disponibilidad declarada para el dataset.

En publicaciones de fuentes, `published_at` puede establecer la disponibilidad pública cuando sea confiable de forma independiente y tenga precisión suficiente. `captured_at` establece cuándo el sistema obtuvo realmente el contenido. Si la hora de publicación no está disponible, es controvertida o no es confiable, debe utilizarse la hora defendible de captura/disponibilidad en lugar de estimar una hora anterior.

Para datos de mercado, la disponibilidad depende del comportamiento de entrega y finalización del proveedor. La hora de cierre del intervalo de una vela no demuestra que la vela final estuviera disponible exactamente en ese instante. La captura/disponibilidad y el estado provisional/final deben registrarse por separado.

## Incertidumbre sobre el momento del evento

Los eventos deben admitir marcas de tiempo exactas cuando estén respaldadas por evidencias, marcas aproximadas con precisión declarada, límites mínimos/máximos cuando solo se conozca un intervalo y tiempo desconocido cuando no exista una estimación defendible.

No se debe convertir un evento conocido solo por fecha en una marca de tiempo arbitraria a medianoche sin conservar su precisión original. Deben preservarse la zona horaria y la representación originales de la fuente cuando sean relevantes, mientras que las marcas de tiempo comparables por máquina se normalizan a UTC.

## Representación de marcas de tiempo

- Almacenar instantes en UTC mediante una representación inequívoca (por ejemplo, RFC 3339 con offset UTC).
- Conservar el texto original de la marca de tiempo, la zona horaria y la precisión cuando la fuente los proporcione.
- Diferenciar instantes, valores de fecha sin hora e intervalos temporales inciertos.
- Utilizar límites explícitos para los intervalos de velas y agregados, con una convención documentada como intervalos semiabiertos `[start, end)`.
- Registrar, cuando sea relevante desde el punto de vista operativo, las suposiciones sobre la fuente y sincronización del reloj de la infraestructura de ingesta.

## Requisitos de procedencia

Cada registro conservado debe poder rastrearse hasta la fuente/proveedor y su identificador nativo; URL, endpoint, dataset u otra referencia recuperable; registros de captura e ingesta; payload original o representación permitida legalmente; hash del contenido y algoritmo; versión del esquema y de normalización; relación de revisión/sustitución; y ejecuciones de transformación que produjeron registros derivados.

Un hash demuestra integridad a nivel de bytes respecto de la representación sometida a hash; no demuestra que una fuente sea auténtica ni que sus afirmaciones sean verdaderas.

## Reconstrucción de lo que se conocía en el momento T

Un dataset point-in-time debe generarse a partir de registros que cumplan el corte de disponibilidad y la política de revisión seleccionada. La consulta o el manifiesto del dataset debe registrar la marca de tiempo de corte, la política de disponibilidad, la selección de fuentes y registros, el tratamiento de revisiones y datos recibidos con retraso, las versiones de esquema y transformación, las exclusiones y la incertidumbre temporal no resuelta.

Las correcciones posteriores no deben reescribir silenciosamente un dataset histórico de investigación generado previamente. Una nueva reconstrucción puede incorporar correcciones posteriores, pero debe poder distinguirse de la vista point-in-time anterior.

## Ejemplo

Un evento ocurre a las 10:00 UTC. Un documento oficial se publica a las 10:15 UTC y se captura a las 10:17 UTC.

- Una simulación a las 10:05 no puede utilizar el documento.
- Una simulación a las 10:16 puede utilizarlo solo si la marca de publicación es confiable y la política permite usar la hora de publicación pública como disponibilidad.
- Si la plataforma exige captura efectiva por el sistema, el documento puede utilizarse a partir de las 10:17.
- La hora de ocurrencia del evento, 10:00, no hace que el documento posterior estuviera disponible a las 10:00.

## Prevención de leakage

- Nunca retrotraer registros basándose en la hora del evento.
- Excluir de los datasets point-in-time estrictos los registros con disponibilidad desconocida o no confiable, salvo que se aplique y documente una regla conservadora de disponibilidad.
- Ajustar imputers, scalers, selección de features y otros preprocesamientos aprendidos únicamente con la ventana de entrenamiento permitida.
- Evitar que valores revisados/finalizados se filtren a snapshots anteriores.
- Conservar los manifiestos de datasets y las políticas de corte para cada backtest o ejecución de investigación.
