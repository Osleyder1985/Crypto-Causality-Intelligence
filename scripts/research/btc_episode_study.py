#!/usr/bin/env python3
"""Descriptive BTC/USDT episode study; reads local CSV/Parquet, never downloads data."""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DISCLAIMER = (
    "Descriptive historical analysis only. It does not establish causality, "
    "predict future returns, or constitute investment advice."
)
REQUIRED_COLUMNS = ("open_time_utc", "open", "high", "low", "close", "volume")


class StudyError(ValueError):
    """Invalid input or an episode that cannot be evaluated safely."""


@dataclass(frozen=True)
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float | None = None


def parse_utc(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise StudyError(f"{field}: timestamp ISO-8601 inválido: {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise StudyError(f"{field}: se exige timestamp explícito en UTC: {value!r}")
    return parsed.astimezone(timezone.utc)


def _number(row: dict[str, str], name: str, line: int, *, optional: bool = False) -> float | None:
    raw = row.get(name, "")
    if optional and raw == "":
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise StudyError(f"Línea {line}: {name} no es numérico") from exc
    if not math.isfinite(value):
        raise StudyError(f"Línea {line}: {name} no es finito")
    return value


def load_candles(path: str | Path) -> list[Candle]:
    candles: list[Candle] = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise StudyError("CSV vacío o sin encabezado")
        missing = [name for name in REQUIRED_COLUMNS if name not in reader.fieldnames]
        if missing:
            raise StudyError(f"Faltan columnas obligatorias: {', '.join(missing)}")
        for line, row in enumerate(reader, start=2):
            timestamp = parse_utc(row.get("open_time_utc", ""), f"Línea {line} open_time_utc")
            values = {name: _number(row, name, line) for name in ("open", "high", "low", "close", "volume")}
            quote_volume = _number(row, "quote_volume", line, optional=True) if "quote_volume" in reader.fieldnames else None
            candle = Candle(timestamp=timestamp, **values, quote_volume=quote_volume)  # type: ignore[arg-type]
            if min(candle.open, candle.high, candle.low, candle.close) <= 0:
                raise StudyError(f"Línea {line}: OHLC debe ser estrictamente positivo")
            if candle.volume < 0 or (candle.quote_volume is not None and candle.quote_volume < 0):
                raise StudyError(f"Línea {line}: el volumen no puede ser negativo")
            if candle.low > min(candle.open, candle.close) or candle.high < max(candle.open, candle.close) or candle.low > candle.high:
                raise StudyError(f"Línea {line}: OHLC inconsistente")
            if candles and timestamp <= candles[-1].timestamp:
                reason = "duplicado" if timestamp == candles[-1].timestamp else "fuera de orden"
                raise StudyError(f"Línea {line}: timestamp {reason}: {timestamp.isoformat()}")
            candles.append(candle)
    if not candles:
        raise StudyError("El CSV no contiene velas")
    return candles



def load_parquet_candles(path: str | Path) -> list[Candle]:
    """Read a local Parquet file through in-memory DuckDB; never writes a copy."""
    try:
        import duckdb
    except ImportError as exc:
        raise StudyError(
            "Para leer Parquet instala la dependencia fijada en requirements-research.txt"
        ) from exc

    file_path = Path(path).expanduser().resolve()
    if not file_path.is_file():
        raise StudyError(f"No existe el archivo Parquet: {file_path}")

    connection = duckdb.connect(database=":memory:")
    try:
        # DESCRIBE validates the schema before reading rows. The file path is
        # passed as a bound parameter rather than interpolated into SQL.
        description = connection.execute(
            "DESCRIBE SELECT * FROM read_parquet(?)", [str(file_path)]
        ).fetchall()
        available = {row[0] for row in description}
        missing = [name for name in REQUIRED_COLUMNS if name not in available]
        if missing:
            raise StudyError(f"Parquet: faltan columnas obligatorias: {', '.join(missing)}")
        columns = list(REQUIRED_COLUMNS)
        if "quote_volume" in available:
            columns.append("quote_volume")
        connection.execute("SET preserve_insertion_order = true")
        projection = ", ".join(
            ('CAST("' + name + '" AS VARCHAR) AS "' + name + '" ').strip()
            if name == "open_time_utc" else '"' + name + '"'
            for name in columns
        )
        rows = connection.execute(
            f"SELECT {projection} FROM read_parquet(?)",
            [str(file_path)],
        ).fetchall()
        candles: list[Candle] = []
        for line, row in enumerate(rows, start=1):
            values = dict(zip(columns, row))
            raw_timestamp = values["open_time_utc"]
            if isinstance(raw_timestamp, datetime):
                timestamp_text = raw_timestamp.isoformat()
            elif isinstance(raw_timestamp, str):
                timestamp_text = raw_timestamp
            else:
                raise StudyError(
                    f"Parquet fila {line}: open_time_utc debe ser timestamp UTC o texto ISO-8601"
                )
            timestamp = parse_utc(timestamp_text, f"Parquet fila {line} open_time_utc")
            numeric: dict[str, float] = {}
            for name in ("open", "high", "low", "close", "volume"):
                value = values[name]
                if value is None:
                    raise StudyError(f"Parquet fila {line}: {name} es null")
                try:
                    numeric[name] = float(value)
                except (TypeError, ValueError) as exc:
                    raise StudyError(f"Parquet fila {line}: {name} no es numérico") from exc
                if not math.isfinite(numeric[name]):
                    raise StudyError(f"Parquet fila {line}: {name} no es finito")
            quote_volume = values.get("quote_volume")
            if quote_volume is not None:
                quote_volume = float(quote_volume)
                if not math.isfinite(quote_volume):
                    raise StudyError(f"Parquet fila {line}: quote_volume no es finito")
            candle = Candle(timestamp=timestamp, **numeric, quote_volume=quote_volume)
            if min(candle.open, candle.high, candle.low, candle.close) <= 0:
                raise StudyError(f"Parquet fila {line}: OHLC debe ser estrictamente positivo")
            if candle.volume < 0 or (candle.quote_volume is not None and candle.quote_volume < 0):
                raise StudyError(f"Parquet fila {line}: el volumen no puede ser negativo")
            if candle.low > min(candle.open, candle.close) or candle.high < max(candle.open, candle.close) or candle.low > candle.high:
                raise StudyError(f"Parquet fila {line}: OHLC inconsistente")
            if candles and timestamp <= candles[-1].timestamp:
                reason = "duplicado" if timestamp == candles[-1].timestamp else "fuera de orden"
                raise StudyError(f"Parquet fila {line}: timestamp {reason}")
            candles.append(candle)
        if not candles:
            raise StudyError("El Parquet no contiene velas")
        return candles
    except StudyError:
        raise
    except Exception as exc:
        raise StudyError(f"No se pudo leer Parquet: {exc}") from exc
    finally:
        connection.close()


def load_episodes(path: str | Path) -> list[dict[str, Any]]:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StudyError(f"No se pudo leer el archivo de episodios: {exc}") from exc
    if not isinstance(raw, list) or not raw:
        raise StudyError("El archivo de episodios debe ser una lista JSON no vacía")
    episodes = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            raise StudyError("Cada episodio debe ser un objeto")
        episode_id = item.get("episode_id")
        direction = item.get("direction")
        if not isinstance(episode_id, str) or not episode_id.strip() or episode_id in seen:
            raise StudyError("episode_id debe ser texto no vacío y único")
        if direction not in ("bullish", "bearish"):
            raise StudyError(f"{episode_id}: direction debe ser bullish o bearish")
        start = parse_utc(item.get("start_utc"), f"{episode_id}.start_utc")
        end = parse_utc(item.get("end_utc"), f"{episode_id}.end_utc")
        if end <= start:
            raise StudyError(f"{episode_id}: end_utc debe ser posterior a start_utc")
        seen.add(episode_id)
        episodes.append({"episode_id": episode_id, "direction": direction, "start": start, "end": end})
    return episodes


def _returns(candles: list[Candle]) -> list[float]:
    return [math.log(b.close / a.close) for a, b in zip(candles, candles[1:])]


def _volatility(candles: list[Candle]) -> float | None:
    values = _returns(candles)
    return statistics.pstdev(values) if len(values) >= 2 else None


def _close_drawdown(candles: list[Candle]) -> float:
    """Maximum drawdown measured only at observed candle closes."""
    peak = candles[0].open
    worst = 0.0
    for candle in candles:
        peak = max(peak, candle.close)
        worst = min(worst, candle.close / peak - 1.0)
    return worst


def _period_metrics(candles: list[Candle]) -> dict[str, float | int | None]:
    if not candles:
        raise StudyError("Ventana sin velas")
    first, last = candles[0], candles[-1]
    quote_values = [c.quote_volume for c in candles if c.quote_volume is not None]
    return {
        "candle_count": len(candles),
        "return_pct": (last.close / first.open - 1.0) * 100.0,
        "realized_volatility_hourly": _volatility(candles),
        "max_close_drawdown_pct": _close_drawdown(candles) * 100.0,
        "intraperiod_range_pct": (max(c.high for c in candles) / min(c.low for c in candles) - 1.0) * 100.0,
        "mean_base_volume": statistics.fmean(c.volume for c in candles),
        "mean_quote_volume": statistics.fmean(quote_values) if len(quote_values) == len(candles) else None,
    }


def _complete_window(candles: list[Candle], start: datetime, end: datetime, interval: timedelta) -> list[Candle] | None:
    selected = [c for c in candles if start <= c.timestamp < end]
    expected = int((end - start) / interval)
    if len(selected) != expected:
        return None
    if any(b.timestamp - a.timestamp != interval for a, b in zip(selected, selected[1:])):
        return None
    return selected


def study(
    candles: list[Candle],
    episodes: list[dict[str, Any]],
    interval_seconds: int = 3600,
    lookbacks_hours: tuple[int, ...] = (24, 72, 168),
) -> dict[str, Any]:
    if interval_seconds <= 0:
        raise StudyError("interval_seconds debe ser positivo")
    interval = timedelta(seconds=interval_seconds)
    if not candles:
        raise StudyError("No hay velas")
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    misaligned = [c.timestamp for c in candles
                  if (c.timestamp - epoch).total_seconds() % interval_seconds != 0]
    if misaligned:
        raise StudyError(f"Timestamp no alineado al intervalo: {misaligned[0].isoformat()}")
    gaps = []
    for a, b in zip(candles, candles[1:]):
        delta_seconds = (b.timestamp - a.timestamp).total_seconds()
        if delta_seconds > interval_seconds:
            exact_multiple = delta_seconds % interval_seconds == 0
            gaps.append({
                "after_utc": a.timestamp.isoformat().replace("+00:00", "Z"),
                "before_utc": b.timestamp.isoformat().replace("+00:00", "Z"),
                "gap_duration_seconds": int(delta_seconds),
                "missing_intervals": int(delta_seconds / interval_seconds) - 1 if exact_multiple else None,
                "irregular_spacing": not exact_multiple,
            })
    results = []
    for episode in episodes:
        start, end = episode["start"], episode["end"]
        if (end - start).total_seconds() % interval_seconds:
            raise StudyError(f"{episode['episode_id']}: los límites deben estar alineados con el intervalo")
        period = _complete_window(candles, start, end, interval)
        if period is None:
            raise StudyError(f"{episode['episode_id']}: faltan velas o hay huecos dentro del episodio")
        metrics = _period_metrics(period)
        pre = {}
        for hours in lookbacks_hours:
            lookback = _complete_window(candles, start - timedelta(hours=hours), start, interval)
            pre[f"pre_{hours}h"] = _period_metrics(lookback) if lookback is not None else None
        baseline = _complete_window(candles, start - timedelta(hours=168), start, interval)
        if baseline is not None:
            base_volume = statistics.fmean(c.volume for c in baseline)
            metrics["volume_ratio_vs_pre_168h"] = (
                metrics["mean_base_volume"] / base_volume if base_volume > 0 else None
            )
        else:
            metrics["volume_ratio_vs_pre_168h"] = None
        results.append({
            "episode_id": episode["episode_id"],
            "direction": episode["direction"],
            "start_utc": start.isoformat().replace("+00:00", "Z"),
            "end_utc_exclusive": end.isoformat().replace("+00:00", "Z"),
            **metrics,
            "pre_event": pre,
        })
    return {
        "asset": "BTC",
        "market": "BTC/USDT",
        "interval_seconds": interval_seconds,
        "episode_count": len(results),
        "data_start_utc": candles[0].timestamp.isoformat().replace("+00:00", "Z"),
        "data_end_utc_exclusive": (candles[-1].timestamp + interval).isoformat().replace("+00:00", "Z"),
        "candle_count": len(candles),
        "global_gap_count": len(gaps),
        "global_gaps": gaps,
        "episodes": results,
        "limitations": [
            DISCLAIMER,
            "Las ventanas previas incompletas se reportan como null; no se imputan datos.",
            "La etiqueta bullish/bearish describe la selección manual del episodio, no una señal predictiva.",
            "La volatilidad es desviación estándar poblacional de retornos logarítmicos por vela; no está anualizada.",
            "El análisis usa un único mercado/venue indicado por el archivo de entrada; no representa todo el mercado.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Estudio descriptivo BTC/USDT desde CSV o Parquet local.")
    parser.add_argument("--input", required=True, help="Archivo CSV o Parquet local; no se realizan descargas")
    parser.add_argument("--input-format", choices=("csv", "parquet"), default="csv", help="Formato de entrada (por defecto: csv)")
    parser.add_argument("--episodes", required=True, help="JSON con ventanas UTC [inicio, fin)")
    parser.add_argument("--json-out", required=True, help="Ruta de salida del resumen JSON agregado")
    parser.add_argument("--csv-out", required=True, help="Ruta de salida CSV por episodio")
    parser.add_argument("--interval-seconds", type=int, default=3600)
    args = parser.parse_args(argv)
    try:
        candles = load_candles(args.input) if args.input_format == "csv" else load_parquet_candles(args.input)
        result = study(candles, load_episodes(args.episodes), args.interval_seconds)
        Path(args.json_out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        fields = [k for k, v in result["episodes"][0].items() if k != "pre_event"]
        with Path(args.csv_out).open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for episode in result["episodes"]:
                writer.writerow({k: episode[k] for k in fields})
        print(f"Estudio completado: {result['episode_count']} episodios; {result['global_gap_count']} huecos globales.")
        print(DISCLAIMER)
        return 0
    except (StudyError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
