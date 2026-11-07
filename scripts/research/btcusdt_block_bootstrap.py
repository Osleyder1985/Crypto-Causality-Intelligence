"""Paired moving-block bootstrap inference for BTCUSDT walk-forward forecasts."""
from __future__ import annotations

import math
import random
from typing import Sequence


def _percentile(sorted_values: list[float], probability: float) -> float:
    if not sorted_values:
        raise ValueError("cannot compute percentile of an empty sample")
    position = (len(sorted_values) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    weight = position - lower
    return sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def _moving_block_indices(n: int, block_length: int, rng: random.Random) -> list[int]:
    sampled: list[int] = []
    max_start = n - block_length
    while len(sampled) < n:
        start = rng.randint(0, max_start)
        sampled.extend(range(start, start + block_length))
    return sampled[:n]



def benjamini_yekutieli(p_values: Sequence[float]) -> list[float]:
    """Return BY-adjusted q-values, controlling FDR under arbitrary dependence."""
    if any(not math.isfinite(p) or p < 0 or p > 1 for p in p_values):
        raise ValueError("p-values must be finite and within [0, 1]")
    m = len(p_values)
    if not m:
        return []
    harmonic = sum(1.0 / rank for rank in range(1, m + 1))
    ordered = sorted(enumerate(p_values), key=lambda item: item[1])
    adjusted = [1.0] * m
    running = 1.0
    for index in range(m - 1, -1, -1):
        original_index, p_value = ordered[index]
        rank = index + 1
        running = min(running, p_value * m * harmonic / rank)
        adjusted[original_index] = min(1.0, running)
    return adjusted


def paired_block_bootstrap(
    actual: Sequence[float],
    predicted: Sequence[float],
    baseline: Sequence[float],
    *,
    block_length: int = 24,
    replicates: int = 2000,
    seed: int = 20261106,
) -> dict:
    """Estimate paired forecast improvements while preserving local time dependence.

    Positive improvement means the model has lower loss / higher directional
    accuracy than the no-predictor baseline. P-values use a centered moving-block
    bootstrap under the one-sided null of no positive mean paired improvement.
    """
    n = len(actual)
    if len(predicted) != n or len(baseline) != n:
        raise ValueError("actual, predicted and baseline must have equal lengths")
    if block_length < 1:
        raise ValueError("block_length must be positive")
    if replicates < 100:
        raise ValueError("replicates must be at least 100")
    if n < block_length:
        return {
            "status": "insufficient_observations_for_block_bootstrap",
            "observations": n,
            "block_length_hours": block_length,
            "replicates": 0,
            "seed": seed,
        }
    values = [*actual, *predicted, *baseline]
    if any(not math.isfinite(float(value)) for value in values):
        raise ValueError("bootstrap inputs must be finite")

    mae_delta = [abs(b - a) - abs(p - a) for a, p, b in zip(actual, predicted, baseline)]
    mse_delta = [(b - a) ** 2 - (p - a) ** 2 for a, p, b in zip(actual, predicted, baseline)]
    direction_delta = [
        float((a >= 0) == (b >= 0)) - float((a >= 0) == (p >= 0))
        for a, p, b in zip(actual, predicted, baseline)
    ]
    observed = {
        "mae": _mean(mae_delta),
        "mse": _mean(mse_delta),
        "directional_accuracy": _mean(direction_delta),
    }
    rng = random.Random(seed)
    draws = {key: [] for key in observed}
    null_exceedances = {key: 0 for key in observed}
    centered = {
        key: [value - observed[key] for value in series]
        for key, series in (
            ("mae", mae_delta),
            ("mse", mse_delta),
            ("directional_accuracy", direction_delta),
        )
    }
    for _ in range(replicates):
        indices = _moving_block_indices(n, block_length, rng)
        for key, series in (
            ("mae", mae_delta),
            ("mse", mse_delta),
            ("directional_accuracy", direction_delta),
        ):
            draws[key].append(_mean([series[index] for index in indices]))
            null_statistic = _mean([centered[key][index] for index in indices])
            if null_statistic >= observed[key]:
                null_exceedances[key] += 1

    intervals = {}
    tests = {}
    for key in observed:
        ordered = sorted(draws[key])
        intervals[key] = {
            "estimate": observed[key],
            "confidence_level": 0.95,
            "ci_lower": _percentile(ordered, 0.025),
            "ci_upper": _percentile(ordered, 0.975),
        }
        tests[key] = {
            "alternative": "model_superior_to_baseline",
            "p_value_one_sided": (null_exceedances[key] + 1) / (replicates + 1),
        }

    # RMSE is a monotone transform of MSE, so the paired MSE test is its
    # corresponding superiority test. Its interval is computed on the RMSE scale.
    rmse_draws = []
    base_squared = [(b - a) ** 2 for a, b in zip(actual, baseline)]
    model_squared = [(p - a) ** 2 for a, p in zip(actual, predicted)]
    for _ in range(replicates):
        indices = _moving_block_indices(n, block_length, rng)
        base_rmse = math.sqrt(_mean([base_squared[index] for index in indices]))
        model_rmse = math.sqrt(_mean([model_squared[index] for index in indices]))
        rmse_draws.append(base_rmse - model_rmse)
    rmse_draws.sort()
    rmse_observed = math.sqrt(_mean(base_squared)) - math.sqrt(_mean(model_squared))

    return {
        "status": "evaluated",
        "method": "paired moving-block bootstrap; non-circular contiguous blocks",
        "observations": n,
        "block_length_hours": block_length,
        "replicates": replicates,
        "seed": seed,
        "improvement_direction": "positive values favor the walk-forward model",
        "confidence_intervals_95": {
            "mae_improvement": intervals["mae"],
            "rmse_improvement": {
                "estimate": rmse_observed,
                "confidence_level": 0.95,
                "ci_lower": _percentile(rmse_draws, 0.025),
                "ci_upper": _percentile(rmse_draws, 0.975),
            },
            "directional_accuracy_improvement": intervals["directional_accuracy"],
        },
        "one_sided_superiority_tests": {
            "mae": tests["mae"],
            "mse_equivalent_to_rmse_superiority": tests["mse"],
            "directional_accuracy": tests["directional_accuracy"],
        },
        "null": "mean paired improvement is zero; centered block-resampled differentials",
    }
