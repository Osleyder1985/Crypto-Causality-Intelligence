#!/usr/bin/env python3
"""Compare Spot/Futures sell-flow extremeness with paired circular block bootstrap.

Input JSONL files are Binance flow_1s exports. Missing seconds are explicitly
filled with zero. This is an event-level anomaly comparison, not a causal test.
Only the Python standard library is required.
"""
from __future__ import annotations

import argparse
import json
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamps must include a timezone (prefer Z)")
    return parsed.astimezone(timezone.utc)


def load_dense_flow(path: str | Path, day_start: datetime, seconds: int) -> list[float]:
    """Load signed taker notional into a complete second grid; absent = zero."""
    start_ms = int(day_start.timestamp() * 1000)
    values = [0.0] * seconds
    seen: set[int] = set()
    with Path(path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if int(row.get("bucket_ms", 0)) != 1000:
                raise ValueError(f"{path}:{line_number}: expected bucket_ms=1000")
            timestamp = int(row["bucket_start_ms"])
            offset_ms = timestamp - start_ms
            if offset_ms % 1000:
                raise ValueError(f"{path}:{line_number}: timestamp is not second-aligned")
            index = offset_ms // 1000
            if not 0 <= index < seconds:
                raise ValueError(f"{path}:{line_number}: timestamp outside requested UTC day")
            if index in seen:
                raise ValueError(f"{path}:{line_number}: duplicate second bucket")
            seen.add(index)
            values[index] = float(row["signed_taker_notional_usdt"])
    return values


def rolling_sell(values: list[float], horizon: int) -> list[float]:
    """Return positive net aggressive sell notional over each forward window."""
    if horizon < 1 or horizon > len(values):
        raise ValueError("invalid rolling horizon")
    prefix = [0.0]
    for value in values:
        prefix.append(prefix[-1] + value)
    return [-(prefix[i + horizon] - prefix[i])
            for i in range(len(values) - horizon + 1)]


def percentile(sorted_values: list[float], probability: float) -> float:
    if not sorted_values:
        raise ValueError("cannot calculate percentile of empty sample")
    position = (len(sorted_values) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    weight = position - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def circular_block_ci(
    spot_exceed: list[int],
    futures_exceed: list[int],
    block_length: int,
    replicates: int,
    rng: random.Random,
    family_size: int = 1,
) -> dict[str, float]:
    """Paired circular moving-block percentile CI for p(Spot)-p(Futures)."""
    n = len(spot_exceed)
    if n != len(futures_exceed) or n == 0:
        raise ValueError("paired bootstrap inputs must have equal nonzero length")
    if not 1 <= block_length <= n:
        raise ValueError("block length must be between 1 and sample length")
    if family_size < 1:
        raise ValueError("family size must be at least one")
    differences = [a - b for a, b in zip(spot_exceed, futures_exceed)]
    prefix = [0]
    for value in differences:
        prefix.append(prefix[-1] + value)

    def circular_sum(start: int, length: int) -> int:
        end = start + length
        if end <= n:
            return prefix[end] - prefix[start]
        return (prefix[n] - prefix[start]) + prefix[end - n]

    estimates: list[float] = []
    blocks_needed = math.ceil(n / block_length)
    for _ in range(replicates):
        total = 0
        remaining = n
        for _ in range(blocks_needed):
            take = min(block_length, remaining)
            total += circular_sum(rng.randrange(n), take)
            remaining -= take
            if remaining <= 0:
                break
        estimates.append(total / n)
    estimates.sort()
    bonferroni_tail = 0.05 / (2 * family_size)
    return {
        "lower_95": percentile(estimates, 0.025),
        "upper_95": percentile(estimates, 0.975),
        "lower_familywise_95_bonferroni": percentile(estimates, bonferroni_tail),
        "upper_familywise_95_bonferroni": percentile(estimates, 1 - bonferroni_tail),
        "family_size": family_size,
        "familywise_confidence_level": 0.95,
        "multiplicity_method": "Bonferroni across configured horizons",
        "replicates": replicates,
        "block_length_seconds": block_length,
    }


def analyze(
    spot_values: list[float],
    futures_values: list[float],
    day_start: datetime,
    event_start: datetime,
    event_seconds: int,
    baseline_seconds: int,
    horizons: Iterable[int],
    block_lengths: Iterable[int],
    replicates: int,
    seed: int,
) -> dict:
    if len(spot_values) != len(futures_values):
        raise ValueError("Spot and Futures grids must have equal length")
    day_seconds = len(spot_values)
    event_offset = int((event_start - day_start).total_seconds())
    if event_offset < baseline_seconds or event_offset + event_seconds > day_seconds:
        raise ValueError("event/baseline range falls outside the available UTC grid")
    horizons = list(horizons)
    if not horizons or len(set(horizons)) != len(horizons):
        raise ValueError("horizons must be a nonempty list of unique values")
    rng = random.Random(seed)
    results = []
    for horizon in horizons:
        spot_roll = rolling_sell(spot_values, horizon)
        futures_roll = rolling_sell(futures_values, horizon)
        if event_seconds < horizon:
            raise ValueError("event duration must be at least the rolling horizon")
        baseline_start = event_offset - baseline_seconds
        baseline_episode_stop = event_offset - event_seconds + 1
        if baseline_episode_stop <= baseline_start:
            raise ValueError("baseline is too short for equal-duration episodes")
        event_stop = event_offset + event_seconds - horizon + 1
        episode_window_count = event_seconds - horizon + 1
        spot_event = spot_roll[event_offset:event_stop]
        futures_event = futures_roll[event_offset:event_stop]
        # Compare the event maximum with maxima from baseline episodes of the
        # same duration, not with individual rolling windows.
        spot_baseline = [
            max(spot_roll[start:start + episode_window_count])
            for start in range(baseline_start, baseline_episode_stop)
        ]
        futures_baseline = [
            max(futures_roll[start:start + episode_window_count])
            for start in range(baseline_start, baseline_episode_stop)
        ]
        spot_max = max(spot_event)
        futures_max = max(futures_event)
        spot_exceed = [int(value >= spot_max) for value in spot_baseline]
        futures_exceed = [int(value >= futures_max) for value in futures_baseline]
        spot_p = sum(spot_exceed) / len(spot_exceed)
        futures_p = sum(futures_exceed) / len(futures_exceed)
        bootstrap = {}
        for block in block_lengths:
            bootstrap[str(block)] = circular_block_ci(
                spot_exceed, futures_exceed, block, replicates, rng, len(horizons)
            )
        results.append({
            "horizon_seconds": horizon,
            "baseline_observations": len(spot_baseline),
            "spot_event_max_sell_usdt": spot_max,
            "futures_event_max_sell_usdt": futures_max,
            "spot_empirical_upper_tail_probability": spot_p,
            "futures_empirical_upper_tail_probability": futures_p,
            "difference_spot_minus_futures": spot_p - futures_p,
            "spot_peak_window_start_utc": (
                event_start + timedelta(seconds=spot_event.index(spot_max))
            ).isoformat(),
            "futures_peak_window_start_utc": (
                event_start + timedelta(seconds=futures_event.index(futures_max))
            ).isoformat(),
            "paired_block_bootstrap_ci": bootstrap,
        })
    return {
        "method": "paired circular moving-block bootstrap of baseline exceedance indicators",
        "interpretation": "lower tail probability means more exceptional vs own baseline",
        "causal_claim": False,
        "event_start_utc": event_start.isoformat(),
        "event_seconds": event_seconds,
        "baseline_seconds": baseline_seconds,
        "input_days": day_seconds // 86400,
        "baseline_episode_seconds": event_seconds,
        "comparison_unit": "maximum sell-flow over equal-duration event and baseline episodes",
        "seed": seed,
        "results": results,
        "limitations": [
            "event maxima are selected from the specified event window",
            "confidence intervals quantify baseline sampling uncertainty, not causality",
            "multiple horizons are correlated; apply a pre-specified multiplicity procedure",
            "a single UTC-day file cannot provide a multi-day or regime-matched baseline",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spot-flow", required=True)
    parser.add_argument("--futures-flow", required=True)
    parser.add_argument("--date-utc", required=True, help="first UTC date in the input grid, YYYY-MM-DD")
    parser.add_argument("--days", type=int, default=1, help="number of consecutive UTC days in each flow file")
    parser.add_argument("--event-start-utc", required=True, help="ISO-8601, e.g. 2026-10-06T09:25:45Z")
    parser.add_argument("--event-seconds", type=int, default=15)
    parser.add_argument("--baseline-hours", type=float, default=6)
    parser.add_argument("--horizons", default="1,2,3,5")
    parser.add_argument("--block-lengths", default="30,60,300,900")
    parser.add_argument("--replicates", type=int, default=1500)
    parser.add_argument("--seed", type=int, default=20261107)
    parser.add_argument("--output", help="write JSON to this path; otherwise stdout")
    args = parser.parse_args()

    day_start = datetime.strptime(args.date_utc, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    event_start = parse_utc(args.event_start_utc)
    if args.days < 1 or args.days > 31:
        parser.error("--days must be between 1 and 31")
    seconds = args.days * 86400
    spot = load_dense_flow(args.spot_flow, day_start, seconds)
    futures = load_dense_flow(args.futures_flow, day_start, seconds)
    result = analyze(
        spot, futures, day_start, event_start, args.event_seconds,
        int(args.baseline_hours * 3600),
        [int(x) for x in args.horizons.split(",")],
        [int(x) for x in args.block_lengths.split(",")],
        args.replicates, args.seed,
    )
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
