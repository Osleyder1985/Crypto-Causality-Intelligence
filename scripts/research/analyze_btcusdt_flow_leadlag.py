#!/usr/bin/env python3
"""Descriptive lead/lag analysis of BTCUSDT Spot hourly taker flow.

Each cohort is analyzed independently so forward returns cannot cross a
user-defined experiment boundary. Results are exploratory, not causal.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

HORIZONS_HOURS = (1, 3, 6, 12, 24)


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 2:
        return None
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    dx, dy = [x - mx for x in xs], [y - my for y in ys]
    vx, vy = sum(v * v for v in dx), sum(v * v for v in dy)
    if vx == 0 or vy == 0:
        return None
    return sum(a * b for a, b in zip(dx, dy)) / math.sqrt(vx * vy)


def load_cohorts(path: str | Path) -> dict[str, list[dict[str, Any]]]:
    cohorts: dict[str, list[dict[str, Any]]] = defaultdict(list)
    with Path(path).open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("provider") != "binance" or row.get("market_type") != "SPOT":
                raise ValueError(f"line {line_number}: unexpected provider or market")
            if row.get("symbol") != "BTCUSDT" or row.get("interval") != "1h":
                raise ValueError(f"line {line_number}: expected BTCUSDT 1h")
            name = row.get("cohort_window")
            if not name:
                raise ValueError(f"line {line_number}: missing cohort_window")
            row["_open_time_ms"] = int(row["open_time_ms"])
            row["_close"] = float(row["close"])
            row["_quote_volume"] = float(row["quote_volume"])
            row["_taker_buy_quote"] = float(row["taker_buy_quote_volume"])
            if row["_close"] <= 0 or row["_quote_volume"] <= 0:
                raise ValueError(f"line {line_number}: close and quote volume must be positive")
            if not 0 <= row["_taker_buy_quote"] <= row["_quote_volume"]:
                raise ValueError(f"line {line_number}: taker buy quote volume outside total")
            cohorts[name].append(row)
    for name, rows in cohorts.items():
        rows.sort(key=lambda item: item["_open_time_ms"])
        times = [row["_open_time_ms"] for row in rows]
        if len(times) != len(set(times)):
            raise ValueError(f"{name}: duplicate hourly timestamps")
        if any(b - a != 3_600_000 for a, b in zip(times, times[1:])):
            raise ValueError(f"{name}: non-contiguous hourly timestamps")
    return dict(cohorts)


def analyze_cohorts(cohorts: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "descriptive_lead_lag_baseline",
        "provider": "binance",
        "market_type": "SPOT",
        "symbol": "BTCUSDT",
        "interval": "1h",
        "predictor": "signed_taker_buy_quote_imbalance",
        "predictor_definition": "(2 * taker_buy_quote_volume - quote_volume) / quote_volume",
        "future_return_definition": "log(close[t+h] / close[t]) within the same cohort",
        "horizons_hours": list(HORIZONS_HOURS),
        "causal_claim": False,
        "inference": "exploratory correlations are not evidence of causality or out-of-sample predictability",
        "cohorts": {},
    }
    total = 0
    for name, rows in sorted(cohorts.items()):
        total += len(rows)
        closes = [row["_close"] for row in rows]
        imbalances = [
            (2 * row["_taker_buy_quote"] - row["_quote_volume"]) / row["_quote_volume"]
            for row in rows
        ]
        horizons = {}
        for horizon in HORIZONS_HOURS:
            xs, ys = [], []
            for index in range(len(rows) - horizon):
                xs.append(imbalances[index])
                ys.append(math.log(closes[index + horizon] / closes[index]))
            horizons[str(horizon)] = {
                "observations": len(xs),
                "pearson_correlation": _pearson(xs, ys),
                "mean_future_log_return_pct": sum(ys) / len(ys) * 100 if ys else None,
            }
        result["cohorts"][name] = {
            "candles": len(rows),
            "start_open_time_ms": rows[0]["_open_time_ms"],
            "end_open_time_ms": rows[-1]["_open_time_ms"],
            "horizons": horizons,
        }
    result["total_candles"] = total
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Normalized BTCUSDT hourly JSONL")
    parser.add_argument("--output", help="Output JSON path; stdout when omitted")
    args = parser.parse_args()
    report = analyze_cohorts(load_cohorts(args.input))
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
