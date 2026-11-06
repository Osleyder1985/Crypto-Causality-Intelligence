# Registro de candidatos de episodios BTC/USDT

- Experimento: `btc-usdt-directional-episodes-v1`
- Fuente seleccionada: Binance Spot, símbolo `BTCUSDT`, velas de 1 hora.
- Zona horaria de los límites comunicados: UTC-05:00 (offset fijo indicado por el operador).
- Semántica objetivo: intervalos semiabiertos `[start, end)`.
- Estado: `candidate_reconciliation_required`; el límite de la subida de febrero–mayo quedó confirmado por el operador como 2026-05-06 04:00 UTC-05:00. El final de la caída de mayo sigue sin confirmarse. Este documento no es un manifiesto aprobado ni habilita captura o análisis.
- Procedencia: fechas transcritas de los mensajes del operador en la conversación del proyecto; no inferidas a partir de precios.

## Episodios con ambos límites comunicados

| ID provisional | Dirección | Inicio local UTC-05:00 | Fin local UTC-05:00 | Estado |
|---|---|---|---|---|
| `bear-2025-10` | bearish | 2025-10-06 12:00 | 2025-11-21 07:00 | Límites comunicados; pendiente de confirmación final |
| `bear-2026-01` | bearish | 2026-01-14 15:00 | 2026-02-05 19:00 | Límites comunicados; pendiente de confirmación final |
| `bull-2026-08` | bullish | 2026-08-16 16:00 | 2026-09-21 16:00 | Límites comunicados; pendiente de confirmación final |

## Episodios con límites incompletos o contradictorios

| ID provisional | Dirección | Inicio local UTC-05:00 | Fin local UTC-05:00 | Problema |
|---|---|---|---|---|
| `bull-2026-02` | bullish | 2026-02-05 19:00 | 2026-05-06 04:00 | Confirmado por el operador en la conversación del 2026-11-06 |
| `bear-2026-05` | bearish | 2026-05-06 04:00 | Desconocido | Falta el límite final |

## Reglas de reconciliación

1. El operador confirmó que `bull-2026-02` termina el 2026-05-06 a las 04:00 UTC-05:00; se conserva esa hora como límite definitivo comunicado.
2. No deducir el fin de `bear-2026-05` a partir de gráficos, máximos/mínimos o datos de Binance.
3. La subida `bull-2026-02` termina y la caída `bear-2026-05` comienza en el mismo instante comunicado: 2026-05-06 04:00 UTC-05:00. Se trata de ventanas contiguas, no solapadas, bajo la semántica `[start, end)`.
4. Mantener todos los límites en UTC-05:00 como fueron comunicados y calcular UTC únicamente después de confirmarlos.
5. Verificar que cada límite coincide con la apertura de una vela de una hora de Binance Spot.
6. Confirmar todos los episodios como una cohorte antes de cambiar el manifiesto a `approved`.

## Conversión UTC de los límites no ambiguos

| Límite local UTC-05:00 | Instante UTC |
|---|---|
| 2025-10-06 12:00 | 2025-10-06 17:00Z |
| 2025-11-21 07:00 | 2025-11-21 12:00Z |
| 2026-01-14 15:00 | 2026-01-14 20:00Z |
| 2026-02-05 19:00 | 2026-02-06 00:00Z |
| 2026-05-06 04:00 | 2026-05-06 09:00Z |
| 2026-08-16 16:00 | 2026-08-16 21:00Z |
| 2026-09-21 16:00 | 2026-09-21 21:00Z |

La tabla UTC normaliza los límites completos comunicados, incluida la confirmación de 2026-05-06 04:00. El único límite temporal todavía ausente es el final de `bear-2026-05`.

## Puerta de ejecución

Este registro es documental. No contiene velas, precios, volumen ni resultados de mercado. El primer run real seguirá bloqueado hasta:
- confirmar el límite final de `bear-2026-05`;
- aprobar la política de uso, almacenamiento y retención aplicable a las respuestas de Binance Spot;
- completar y validar el manifiesto canónico;
- comprobar cobertura real de las velas de 1h y de las ventanas previas requeridas.
