"""Reconcile the approved BTCUSDT Spot hourly historical episodes.

This computes descriptive market baselines only. OHLCV alone cannot establish
causal drivers; event evidence must be joined in a separate, time-aware study.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

INTERVAL_MS = 3_600_000
EXPECTED = {
    "decline_2025_10_06_2025_11_21": ("2025-10-06T17:00:00Z", "2025-11-21T12:00:00Z", 1099, "decline"),
    "decline_2026_01_14_2026_02_05": ("2026-01-14T20:00:00Z", "2026-02-06T00:00:00Z", 532, "decline"),
    "rise_2026_02_05_2026_05_06": ("2026-02-06T00:00:00Z", "2026-05-06T09:00:00Z", 2145, "rise"),
    "decline_2026_05_06_2026_06_30": ("2026-05-06T09:00:00Z", "2026-07-01T01:00:00Z", 1336, "decline"),
    "rise_2026_08_16_2026_09_21": ("2026-08-16T21:00:00Z", "2026-09-21T21:00:00Z", 864, "rise"),
}
DECIMAL_FIELDS = (
    "open", "high", "low", "close", "volume_base", "quote_volume",
    "taker_buy_base_volume", "taker_buy_quote_volume",
)


def _ms(iso: str) -> int:
    value = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"timestamp must be timezone-aware: {iso}")
    return int(value.astimezone(timezone.utc).timestamp() * 1000)


def _decimal(value: Any, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"{field} is not a decimal") from exc
    if not result.is_finite():
        raise ValueError(f"{field} must be finite")
    return result


def _pct(value: Decimal) -> float:
    return round(float(value * Decimal(100)), 8)


def validate_row(row: dict[str, Any]) -> dict[str, Any]:
    required = {
        "cohort_window", "provider", "market_type", "symbol", "interval",
        "open_time_ms", "open_time_utc", *DECIMAL_FIELDS, "close_time_ms",
        "trade_count",
    }
    missing = required - row.keys()
    if missing:
        raise ValueError(f"missing fields: {sorted(missing)}")
    if (row["provider"], row["market_type"], row["symbol"], row["interval"]) != (
        "binance", "SPOT", "BTCUSDT", "1h"
    ):
        raise ValueError("unexpected market identity")
    if isinstance(row["open_time_ms"], bool) or not isinstance(row["open_time_ms"], int):
        raise ValueError("open_time_ms must be an integer")
    if isinstance(row["close_time_ms"], bool) or not isinstance(row["close_time_ms"], int):
        raise ValueError("close_time_ms must be an integer")
    if row["close_time_ms"] != row["open_time_ms"] + INTERVAL_MS - 1:
        raise ValueError("close_time_ms does not end the 1h candle")
    timestamp = datetime.fromisoformat(row["open_time_utc"].replace("Z", "+00:00"))
    if timestamp.tzinfo is None or int(timestamp.timestamp() * 1000) != row["open_time_ms"]:
        raise ValueError("open_time_utc and open_time_ms disagree")
    for field in DECIMAL_FIELDS:
        row[field] = _decimal(row[field], field)
    if not (Decimal(0) < row["low"] <= row["open"] <= row["high"]
            and row["low"] <= row["close"] <= row["high"]):
        raise ValueError("OHLC invariant violated")
    if min(row[k] for k in DECIMAL_FIELDS[4:]) < 0:
        raise ValueError("negative volume")
    if row["taker_buy_base_volume"] > row["volume_base"]:
        raise ValueError("taker base volume exceeds total")
    if row["taker_buy_quote_volume"] > row["quote_volume"]:
        raise ValueError("taker quote volume exceeds total")
    if isinstance(row["trade_count"], bool) or not isinstance(row["trade_count"], int) or row["trade_count"] < 0:
        raise ValueError("invalid trade_count")
    return row


def calculate_window_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(rows, key=lambda item: item["open_time_ms"])
    if not ordered:
        raise ValueError("window is empty")
    first, last = ordered[0], ordered[-1]
    start_price = first["open"]
    end_price = last["close"]
    total_return = end_price / start_price - Decimal(1)
    closes = [row["close"] for row in ordered]
    running_peak = closes[0]
    running_trough = closes[0]
    max_drawdown = Decimal(0)
    max_runup = Decimal(0)
    for close in closes:
        running_peak = max(running_peak, close)
        running_trough = min(running_trough, close)
        max_drawdown = min(max_drawdown, close / running_peak - Decimal(1))
        max_runup = max(max_runup, close / running_trough - Decimal(1))
    hourly_returns = [float(first["close"] / first["open"] - Decimal(1))]
    hourly_returns.extend(
        float(ordered[i]["close"] / ordered[i - 1]["close"] - Decimal(1))
        for i in range(1, len(ordered))
    )
    volatility = statistics.stdev(hourly_returns) if len(hourly_returns) > 1 else 0.0
    base_volume = sum((r["volume_base"] for r in ordered), Decimal(0))
    quote_volume = sum((r["quote_volume"] for r in ordered), Decimal(0))
    taker_base = sum((r["taker_buy_base_volume"] for r in ordered), Decimal(0))
    taker_quote = sum((r["taker_buy_quote_volume"] for r in ordered), Decimal(0))
    taker_imbalance = (Decimal(2) * taker_base / base_volume - Decimal(1)) if base_volume else Decimal(0)
    taker_quote_imbalance = (Decimal(2) * taker_quote / quote_volume - Decimal(1)) if quote_volume else Decimal(0)
    positive = sum(value > 0 for value in hourly_returns)
    negative = sum(value < 0 for value in hourly_returns)
    return {
        "candles": len(ordered),
        "start_open": str(start_price),
        "end_close": str(end_price),
        "return_pct": _pct(total_return),
        "high": str(max(r["high"] for r in ordered)),
        "low": str(min(r["low"] for r in ordered)),
        "high_vs_start_pct": _pct(max(r["high"] for r in ordered) / start_price - Decimal(1)),
        "low_vs_start_pct": _pct(min(r["low"] for r in ordered) / start_price - Decimal(1)),
        "close_max_drawdown_pct": _pct(max_drawdown),
        "close_max_runup_pct": _pct(max_runup),
        "hourly_realized_volatility_pct": round(volatility * 100, 8),
        "annualized_realized_volatility_pct": round(volatility * math.sqrt(24 * 365) * 100, 8),
        "positive_hour_share_pct": round(positive / len(hourly_returns) * 100, 8),
        "negative_hour_share_pct": round(negative / len(hourly_returns) * 100, 8),
        "base_volume_sum": str(base_volume),
        "quote_volume_sum": str(quote_volume),
        "mean_hourly_quote_volume": str(quote_volume / len(ordered)),
        "trade_count_sum": sum(r["trade_count"] for r in ordered),
        "aggregate_taker_base_imbalance_pct": _pct(taker_imbalance),
        "aggregate_taker_quote_imbalance_pct": _pct(taker_quote_imbalance),
    }


def reconcile_rows(raw_rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen: set[tuple[str, int]] = set()
    for raw in raw_rows:
        row = validate_row(dict(raw))
        cohort = row["cohort_window"]
        if cohort not in EXPECTED:
            raise ValueError(f"unexpected cohort: {cohort}")
        key = (cohort, row["open_time_ms"])
        if key in seen:
            raise ValueError(f"duplicate candle: {key}")
        seen.add(key)
        grouped[cohort].append(row)
    if set(grouped) != set(EXPECTED):
        raise ValueError("the five approved cohorts are not all present")

    results: dict[str, Any] = {}
    for name, (start_iso, end_iso, count, direction) in EXPECTED.items():
        rows = sorted(grouped[name], key=lambda item: item["open_time_ms"])
        start_ms, end_ms = _ms(start_iso), _ms(end_iso)
        expected_times = list(range(start_ms, end_ms, INTERVAL_MS))
        actual_times = [row["open_time_ms"] for row in rows]
        if len(rows) != count or actual_times != expected_times:
            raise ValueError(f"{name}: count or hourly coverage mismatch")
        metrics = calculate_window_metrics(rows)
        if direction == "rise" and metrics["return_pct"] <= 0:
            raise ValueError(f"{name}: expected positive episode return")
        if direction == "decline" and metrics["return_pct"] >= 0:
            raise ValueError(f"{name}: expected negative episode return")
        results[name] = {
            "start_utc": start_iso,
            "end_utc_exclusive": end_iso,
            "expected_direction": direction,
            "coverage_pct": 100.0,
            "missing_candles": 0,
            "duplicate_candles": 0,
            **metrics,
        }

    adjacent_pairs = (
        ("decline_2026_01_14_2026_02_05", "rise_2026_02_05_2026_05_06"),
        ("rise_2026_02_05_2026_05_06", "decline_2026_05_06_2026_06_30"),
    )
    for left, right in adjacent_pairs:
        left_end = _ms(EXPECTED[left][1])
        right_start = _ms(EXPECTED[right][0])
        if left_end != right_start:
            raise ValueError(f"approved cohort boundary mismatch: {left} -> {right}")

    return {
        "status": "reconciled_descriptive_baseline",
        "provider": "binance",
        "market_type": "SPOT",
        "symbol": "BTCUSDT",
        "interval": "1h",
        "timezone": "UTC-05:00 user-defined boundaries, normalized to UTC",
        "boundary_convention": "start inclusive, end exclusive",
        "total_candles": sum(item["candles"] for item in results.values()),
        "cohort_count": len(results),
        "causal_claim": False,
        "interpretation_limit": (
            "OHLCV and taker-flow summaries describe market behavior; they do not "
            "identify news catalysts or establish causality."
        ),
        "cohorts": results,
    }


def reconcile_file(input_path: Path, output_path: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    with input_path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ValueError(f"{input_path}:{line_number}: invalid JSON") from exc
    report = reconcile_rows(rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(reconcile_file(args.input, args.output), indent=2))


if __name__ == "__main__":
    main()
