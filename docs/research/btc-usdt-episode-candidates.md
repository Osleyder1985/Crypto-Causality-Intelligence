# Registro de candidatos de episodios BTC/USDT

- Experimento: `btc-usdt-directional-episodes-v1`
- Fuente seleccionada: Binance Spot, símbolo `BTCUSDT`, velas de 1 hora.
- Zona horaria de los límites comunicados: UTC-05:00 (offset fijo indicado por el operador).
- Semántica objetivo: intervalos semiabiertos `[start, end)`.
- Estado: `candidate_reconciliation_required`; este documento no es un manifiesto aprobado ni habilita captura o análisis.
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
| `bull-2026-02` | bullish | 2026-02-05 19:00 | 2026-05-06, hora no resuelta | En el historial aparece 04:00 en un mensaje y 19:00 en otro |
| `bear-2026-05` | bearish | 2026-05-06 04:00 | Desconocido | Falta el límite final |

## Reglas de reconciliación

1. No elegir automáticamente entre 04:00 y 19:00 para el fin de `bull-2026-02`.
2. No deducir el fin de `bear-2026-05` a partir de gráficos, máximos/mínimos o datos de Binance.
3. Confirmar si el límite de 2026-05-06 04:00 corresponde al inicio de la caída y si la subida previa termina exactamente en ese mismo instante.
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
| 2026-08-16 16:00 | 2026-08-16 21:00Z |
| 2026-09-21 16:00 | 2026-09-21 21:00Z |

La tabla UTC solo normaliza los límites completos comunicados. No resuelve ni completa los dos episodios de la sección anterior.

## Puerta de ejecución

Este registro es documental. No contiene velas, precios, volumen ni resultados de mercado. El primer run real seguirá bloqueado hasta:
- confirmar los límites faltantes/contradictorios;
- aprobar la política de uso, almacenamiento y retención aplicable a las respuestas de Binance Spot;
- completar y validar el manifiesto canónico;
- comprobar cobertura real de las velas de 1h y de las ventanas previas requeridas.
