#!/usr/bin/env python3
"""Minute-resolution BTCUSDT event study with explicit bar-alignment caveats.

Input is the normalized Binance Spot 1m JSONL produced by
download_binance_btcusdt_intraday.py. Event timestamps must be timezone-aware.
The report is descriptive and makes no causal or statistical-significance claim.
"""
from __future__ import annotations

import argparse
import json
from bisect import bisect_left
from datetime import datetime
from pathlib import Path
from typing import Any

MINUTE_MS = 60_000
DEFAULT_HORIZONS = (1, 5, 15, 30, 60)


def parse_utc_ms(value: str) -> int:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"Timezone-aware timestamp required: {value}")
    return int(parsed.timestamp() * 1000)


def load_cohorts(path: str | Path) -> dict[str, list[dict[str, Any]]]:
    cohorts: dict[str, list[dict[str, Any]]] = {}
    with Path(path).open(encoding="utf-8") as stream:
        for line_no, line in enumerate(stream, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if (row.get("provider"), row.get("market_type"), row.get("symbol"), row.get("interval")) != (
                "binance", "SPOT", "BTCUSDT", "1m"
            ):
                raise ValueError(f"line {line_no}: expected Binance Spot BTCUSDT 1m")
            cohort = row.get("cohort_window")
            if not cohort:
                raise ValueError(f"line {line_no}: missing cohort_window")
            normalized = {
                "open_time_ms": int(row["open_time_ms"]),
                "close_time_ms": int(row["close_time_ms"]),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "quote_volume": float(row["quote_volume"]),
                "trade_count": int(row["trade_count"]),
                "taker_buy_quote_volume": float(row["taker_buy_quote_volume"]),
            }
            if normalized["close"] <= 0 or normalized["quote_volume"] < 0:
                raise ValueError(f"line {line_no}: invalid close or quote volume")
            if not 0 <= normalized["taker_buy_quote_volume"] <= normalized["quote_volume"]:
                raise ValueError(f"line {line_no}: invalid taker-buy quote volume")
            cohorts.setdefault(cohort, []).append(normalized)

    for name, rows in cohorts.items():
        rows.sort(key=lambda item: item["open_time_ms"])
        opens = [r["open_time_ms"] for r in rows]
        if len(opens) != len(set(opens)):
            raise ValueError(f"{name}: duplicate minute timestamps")
        if any(b - a != MINUTE_MS for a, b in zip(opens, opens[1:])):
            raise ValueError(f"{name}: non-contiguous minute timestamps")
        for row in rows:
            if row["close_time_ms"] != row["open_time_ms"] + MINUTE_MS - 1:
                raise ValueError(f"{name}: invalid candle close timestamp")
            if not (0 < row["low"] <= row["open"] <= row["high"] and row["low"] <= row["close"] <= row["high"]):
                raise ValueError(f"{name}: invalid OHLC")
    return cohorts


def _flow(rows: list[dict[str, Any]]) -> dict[str, Any]:
    quote = sum(r["quote_volume"] for r in rows)
    taker_buy = sum(r["taker_buy_quote_volume"] for r in rows)
    return {
        "candle_count": len(rows),
        "quote_volume_usdt": quote,
        "trade_count": sum(r["trade_count"] for r in rows),
        "taker_buy_quote_volume_usdt": taker_buy,
        "taker_buy_share": taker_buy / quote if quote else None,
        "signed_taker_imbalance": (2 * taker_buy - quote) / quote if quote else None,
    }


def _excursions(rows: list[dict[str, Any]], reference: float) -> dict[str, float | None]:
    if not rows:
        return {"max_favorable_excursion_pct": None, "max_adverse_excursion_pct": None}
    return {
        "max_favorable_excursion_pct": (max(r["high"] for r in rows) / reference - 1) * 100,
        "max_adverse_excursion_pct": (min(r["low"] for r in rows) / reference - 1) * 100,
    }


def analyze_event(
    rows: list[dict[str, Any]], event: dict[str, Any], horizons: tuple[int, ...] = DEFAULT_HORIZONS
) -> dict[str, Any]:
    event_ms = parse_utc_ms(event["event_at_utc"])
    opens = [r["open_time_ms"] for r in rows]
    closes_at = [r["close_time_ms"] for r in rows]
    event_bar_index = bisect_left(opens, event_ms)
    pre_index = bisect_left(closes_at, event_ms) - 1
    if pre_index < 0 or event_bar_index >= len(rows):
        raise ValueError(f"{event.get('event_id', 'event')}: event lacks pre/post candle coverage")
    reference = rows[pre_index]["close"]
    if event_bar_index > 0 and opens[event_bar_index] != event_ms and opens[event_bar_index - 1] <= event_ms < opens[event_bar_index]:
        event_bar_index -= 1

    results: dict[str, Any] = {}
    for horizon in horizons:
        if horizon <= 0:
            raise ValueError("Horizons must be positive")
        end_ms = event_ms + horizon * MINUTE_MS
        end_index = bisect_left(closes_at, end_ms)
        if end_index >= len(rows):
            raise ValueError(f"{event.get('event_id', 'event')}: insufficient post-event data for {horizon}m")
        post_rows = [r for r in rows if event_ms <= r["open_time_ms"] < end_ms]
        post_close = rows[end_index]["close"]
        pre_target = event_ms - horizon * MINUTE_MS
        pre_ref_index = bisect_left(closes_at, pre_target) - 1
        pre_start_index = bisect_left(opens, pre_target)
        pre_rows = [r for r in rows if pre_target <= r["open_time_ms"] < event_ms]
        pre_return = None
        if pre_ref_index >= 0:
            pre_return = (reference / rows[pre_ref_index]["close"] - 1) * 100
        results[str(horizon)] = {
            "pre_event_return_pct": pre_return,
            "post_event_return_pct": (post_close / reference - 1) * 100,
            "post_event_flow": _flow(post_rows),
            "post_event_excursions_pct": _excursions(post_rows, reference),
            "pre_event_flow": _flow(pre_rows),
            "post_close_time_utc_ms": rows[end_index]["close_time_ms"],
            "pre_window_available": pre_ref_index >= 0 and pre_start_index < len(rows),
        }

    return {
        "event_id": event.get("event_id"),
        "event_at_utc": event["event_at_utc"],
        "cohort_window": event["cohort_window"],
        "event_bar_aligned_to_minute": event_ms % MINUTE_MS == 0,
        "event_bar_overlap_warning": event_ms % MINUTE_MS != 0,
        "pre_event_reference_close_time_utc_ms": rows[pre_index]["close_time_ms"],
        "pre_event_reference_close": reference,
        "horizons_minutes": results,
        "interpretation_limit": (
            "Descriptive event study only; OHLCV bars do not identify within-minute ordering, "
            "news exposure, counterfactual returns, or causal effects."
        ),
    }


def run(input_path: str | Path, events_path: str | Path) -> dict[str, Any]:
    cohorts = load_cohorts(input_path)
    events = json.loads(Path(events_path).read_text(encoding="utf-8"))
    if not isinstance(events, list):
        raise ValueError("Events file must contain a JSON array")
    results = []
    for event in events:
        cohort = event.get("cohort_window")
        if cohort not in cohorts:
            raise ValueError(f"Unknown cohort_window: {cohort}")
        results.append(analyze_event(cohorts[cohort], event))
    return {
        "status": "descriptive_one_minute_event_study",
        "provider": "binance",
        "market_type": "SPOT",
        "symbol": "BTCUSDT",
        "interval": "1m",
        "causal_claim": False,
        "events": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Normalized Binance BTCUSDT 1m JSONL")
    parser.add_argument("--events", required=True, help="JSON array of timestamped event anchors")
    parser.add_argument("--output", help="Output JSON file; stdout if omitted")
    args = parser.parse_args()
    rendered = json.dumps(run(args.input, args.events), indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
