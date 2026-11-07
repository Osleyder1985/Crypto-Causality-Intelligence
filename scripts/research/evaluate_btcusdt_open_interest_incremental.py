"""Paired walk-forward test of incremental USD-M open_interest features over BTCUSDT Spot."""
from __future__ import annotations

import argparse
import json
import bisect
import math
import random
import zlib
from pathlib import Path
from typing import Any

from scripts.research.analyze_btcusdt_hac import FEATURES as SPOT_FEATURES, _features
from scripts.research.analyze_btcusdt_multifactor import HORIZONS_HOURS, load_cohorts

OPEN_INTEREST_FEATURES = (
    "open_interest_base_asof",
    "open_interest_quote_asof",
    "open_interest_change_1h_pct",
    "open_interest_change_4h_pct",
    "open_interest_change_24h_pct",
)


def _solve(matrix: list[list[float]], vector: list[float]) -> list[float]:
    n = len(vector)
    aug = [list(map(float, matrix[i])) + [float(vector[i])] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(aug[r][col]))
        if abs(aug[pivot][col]) < 1e-14:
            raise ValueError("regularized design matrix is singular")
        aug[col], aug[pivot] = aug[pivot], aug[col]
        scale = aug[col][col]
        aug[col] = [value / scale for value in aug[col]]
        for row in range(n):
            if row == col:
                continue
            factor = aug[row][col]
            aug[row] = [a - factor * b for a, b in zip(aug[row], aug[col])]
    return [aug[i][-1] for i in range(n)]


def _prefix_statistics(features: list[list[float]], targets: list[float]) -> dict[str, Any]:
    """Build cumulative sufficient statistics so each expanding fit is O(k^3), not O(n*k^2)."""
    if not features or len(features) != len(targets):
        raise ValueError("features and targets must be non-empty and aligned")
    k = len(features[0])
    sum_x = [[0.0] * (len(features) + 1) for _ in range(k)]
    sum_xx = [[[0.0] * (len(features) + 1) for _ in range(k)] for _ in range(k)]
    sum_xy = [[0.0] * (len(features) + 1) for _ in range(k)]
    sum_y = [0.0] * (len(features) + 1)
    for index, (row, target) in enumerate(zip(features, targets), start=1):
        sum_y[index] = sum_y[index - 1] + target
        for i in range(k):
            sum_x[i][index] = sum_x[i][index - 1] + row[i]
            sum_xy[i][index] = sum_xy[i][index - 1] + row[i] * target
            for j in range(k):
                sum_xx[i][j][index] = sum_xx[i][j][index - 1] + row[i] * row[j]
    return {"count": len(features), "sum_x": sum_x, "sum_xx": sum_xx,
            "sum_xy": sum_xy, "sum_y": sum_y}


def _ridge_predict_from_prefix(stats: dict[str, Any], train_count: int,
                               test_x: list[float], alpha: float) -> tuple[float, float]:
    k = len(test_x)
    n = train_count
    if n < 1 or n > stats["count"]:
        raise ValueError("invalid prefix training count")
    sx, sxx, sxy, sy = stats["sum_x"], stats["sum_xx"], stats["sum_xy"], stats["sum_y"]
    y_mean = sy[n] / n
    means = [sx[i][n] / n for i in range(k)]
    scales = []
    for i in range(k):
        variance = max(0.0, sxx[i][i][n] / n - means[i] * means[i])
        scales.append(math.sqrt(variance) or 1.0)
    gram = []
    cross = []
    for i in range(k):
        cross.append((sxy[i][n] - sx[i][n] * sy[n] / n) / scales[i])
        gram_row = []
        for j in range(k):
            covariance_sum = sxx[i][j][n] - sx[i][n] * sx[j][n] / n
            gram_row.append(covariance_sum / (scales[i] * scales[j]))
        gram.append(gram_row)
    for i in range(k):
        gram[i][i] += alpha
    beta = _solve(gram, cross)
    z_test = [(test_x[i] - means[i]) / scales[i] for i in range(k)]
    prediction = y_mean + sum(a * b for a, b in zip(beta, z_test))
    return prediction, y_mean


def _quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("cannot compute a quantile from an empty sample")
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] * (upper - position) + ordered[upper] * (position - lower)


def _block_bootstrap_mean(values: list[float], block_length: int,
                          repetitions: int, seed: int) -> tuple[float, float, float]:
    """Circular moving-block bootstrap CI and two-sided null test for a paired mean."""
    n = len(values)
    if n < 2:
        return (float("nan"), float("nan"), 1.0)
    block = min(max(1, block_length), n)
    observed = sum(values) / n
    centered = [value - observed for value in values]
    rng = random.Random(seed)
    draws = []
    for _ in range(repetitions):
        sample = []
        while len(sample) < n:
            start = rng.randrange(n)
            sample.extend(centered[(start + offset) % n] for offset in range(block))
        draws.append(sum(sample[:n]) / n)
    low = observed + _quantile(draws, 0.025)
    high = observed + _quantile(draws, 0.975)
    extreme = sum(abs(value) >= abs(observed) for value in draws)
    p_value = min(1.0, 2.0 * (extreme + 1) / (repetitions + 1))
    return low, high, p_value


def _benjamini_yekutieli(items: list[tuple[float, dict[str, Any]]]) -> None:
    if not items:
        return
    ordered = sorted(items, key=lambda item: item[0])
    count = len(ordered)
    harmonic = sum(1.0 / rank for rank in range(1, count + 1))
    running = 1.0
    for index in range(count - 1, -1, -1):
        p_value, target = ordered[index]
        rank = index + 1
        running = min(running, p_value * count * harmonic / rank)
        target["by_q_value_mae"] = min(1.0, running)


def _row_features(row: dict[str, Any]) -> tuple[list[float], list[float]]:
    spot = _features(row)
    values = []
    for key in OPEN_INTEREST_FEATURES:
        value = row.get(key)
        if value is None:
            raise ValueError(f"missing as-of Open Interest feature: {key}")
        number = float(value)
        if not math.isfinite(number):
            raise ValueError(f"non-finite as-of Open Interest feature: {key}")
        values.append(number)

    # Log-transform positive levels; percentage changes remain in percentage points.
    if values[0] <= 0 or values[1] <= 0:
        raise ValueError("Open Interest levels must be strictly positive")
    incremental = [math.log(values[0]), math.log(values[1]), *values[2:]]

    snapshot_ms = int(row["open_interest_snapshot_time_ms"])
    close_ms = int(row["close_time_ms"])
    age_minutes = float(row["open_interest_age_minutes"])
    if snapshot_ms > close_ms:
        raise ValueError("Open Interest snapshot is future-dated")
    actual_age = (close_ms - snapshot_ms) / 60_000
    if actual_age < 0 or actual_age > 10 or abs(actual_age - age_minutes) > 1e-6:
        raise ValueError("Open Interest snapshot is stale or age metadata is inconsistent")
    return spot, spot + incremental


def evaluate_cohort(rows: list[dict[str, Any]], min_train: int = 168,
                    ridge_alpha: float = 1e-6, bootstrap_repetitions: int = 1000,
                    seed: int = 20261106) -> dict[str, Any]:
    if min_train < 24:
        raise ValueError("min_train must be at least 24 hourly observations")
    if ridge_alpha <= 0 or bootstrap_repetitions < 100:
        raise ValueError("ridge_alpha must be positive and bootstrap repetitions at least 100")

    closes = [float(row["_close"]) for row in rows]
    feature_rows: dict[int, tuple[list[float], list[float]]] = {}
    for index, row in enumerate(rows):
        if any(row.get(key) is None for key in OPEN_INTEREST_FEATURES):
            continue
        try:
            feature_rows[index] = _row_features(row)
        except (KeyError, TypeError, ValueError):
            continue

    horizons = {}
    for horizon in HORIZONS_HOURS:
        actual: list[float] = []
        spot_predictions: list[float] = []
        augmented_predictions: list[float] = []
        mean_predictions: list[float] = []
        eligible_indices = [
            index for index in sorted(feature_rows) if index + horizon < len(rows)
        ]
        horizon_targets = [
            math.log(closes[index + horizon] / closes[index])
            for index in eligible_indices
        ]
        spot_stats = _prefix_statistics(
            [feature_rows[index][0] for index in eligible_indices], horizon_targets
        )
        augmented_stats = _prefix_statistics(
            [feature_rows[index][1] for index in eligible_indices], horizon_targets
        )
        for origin in range(min_train + horizon, len(rows) - horizon):
            if origin not in feature_rows:
                continue
            # Only eligible training labels ending at or before this forecast origin are admissible.
            train_count = bisect.bisect_right(eligible_indices, origin - horizon)
            if train_count < min_train:
                continue
            target = math.log(closes[origin + horizon] / closes[origin])
            spot_prediction, train_mean = _ridge_predict_from_prefix(
                spot_stats, train_count, feature_rows[origin][0], ridge_alpha
            )
            augmented_prediction, _ = _ridge_predict_from_prefix(
                augmented_stats, train_count, feature_rows[origin][1], ridge_alpha
            )
            actual.append(target)
            spot_predictions.append(spot_prediction)
            augmented_predictions.append(augmented_prediction)
            mean_predictions.append(train_mean)

        n = len(actual)
        if n == 0:
            horizons[str(horizon)] = {"status": "insufficient_test_observations", "observations": 0}
            continue

        spot_abs = [abs(a - p) for a, p in zip(actual, spot_predictions)]
        aug_abs = [abs(a - p) for a, p in zip(actual, augmented_predictions)]
        spot_sq = [(a - p) ** 2 for a, p in zip(actual, spot_predictions)]
        aug_sq = [(a - p) ** 2 for a, p in zip(actual, augmented_predictions)]
        mae_spot = sum(spot_abs) / n
        mae_aug = sum(aug_abs) / n
        rmse_spot = math.sqrt(sum(spot_sq) / n)
        rmse_aug = math.sqrt(sum(aug_sq) / n)
        direction_spot = sum((a >= 0) == (p >= 0) for a, p in zip(actual, spot_predictions)) / n
        direction_aug = sum((a >= 0) == (p >= 0) for a, p in zip(actual, augmented_predictions)) / n
        mae_difference = [a - b for a, b in zip(spot_abs, aug_abs)]
        mse_difference = [a - b for a, b in zip(spot_sq, aug_sq)]
        cohort_seed = seed + zlib.crc32(str(rows[0].get("cohort_window", "cohort")).encode())
        ci_low, ci_high, p_value = _block_bootstrap_mean(
            mae_difference, max(horizon, 8), bootstrap_repetitions, cohort_seed + horizon
        )
        mse_low, mse_high, mse_p = _block_bootstrap_mean(
            mse_difference, max(horizon, 8), bootstrap_repetitions, cohort_seed + 100 + horizon
        )
        horizons[str(horizon)] = {
            "status": "evaluated",
            "observations": n,
            "first_test_origin_index": min_train + horizon,
            "spot_baseline": {
                "mae": mae_spot,
                "rmse": rmse_spot,
                "directional_accuracy": direction_spot,
            },
            "spot_plus_open_interest": {
                "mae": mae_aug,
                "rmse": rmse_aug,
                "directional_accuracy": direction_aug,
            },
            "incremental_change": {
                "mae_improvement_pct": (1 - mae_aug / mae_spot) * 100 if mae_spot else None,
                "rmse_improvement_pct": (1 - rmse_aug / rmse_spot) * 100 if rmse_spot else None,
                "directional_accuracy_delta": direction_aug - direction_spot,
                "mean_paired_absolute_error_reduction": sum(mae_difference) / n,
                "mae_block_bootstrap_95pct_ci": [ci_low, ci_high],
                "mae_block_bootstrap_two_sided_p": p_value,
                "mean_paired_squared_error_reduction": sum(mse_difference) / n,
                "mse_block_bootstrap_95pct_ci": [mse_low, mse_high],
                "mse_block_bootstrap_two_sided_p": mse_p,
                "bootstrap_block_length_hours": max(horizon, 8),
            },
            "naive_train_mean_benchmark": {
                "mae": sum(abs(a - p) for a, p in zip(actual, mean_predictions)) / n,
                "rmse": math.sqrt(sum((a - p) ** 2 for a, p in zip(actual, mean_predictions)) / n),
            },
            "training_policy": (
                "expanding window; same open_interest-available rows for both models; "
                "training labels end no later than forecast origin; scaling fitted on training rows only"
            ),
        }
    return {
        "candles": len(rows),
        "candles_with_fresh_open_interest": len(feature_rows),
        "fresh_open_interest_pct": 100 * len(feature_rows) / len(rows) if rows else None,
        "minimum_training_observations": min_train,
        "ridge_alpha": ridge_alpha,
        "horizons": horizons,
    }


def analyze(cohorts: dict[str, list[dict[str, Any]]], min_train: int = 168,
            ridge_alpha: float = 1e-6, bootstrap_repetitions: int = 1000,
            seed: int = 20261106) -> dict[str, Any]:
    report: dict[str, Any] = {
        "status": "paired_walk_forward_incremental_open_interest_evaluation",
        "provider": "binance",
        "market_type": "SPOT_with_USD_M_FUTURES_covariate",
        "timestamp_semantics_fully_verified": False,
        "timestamp_availability_policy": "preserve raw create_time; conservatively delay all labels by five minutes; reject future or >10-minute-old snapshots",
        "symbol": "BTCUSDT",
        "interval": "1h",
        "spot_features": list(SPOT_FEATURES),
        "incremental_open_interest_features": list(OPEN_INTEREST_FEATURES),
        "horizons_hours": list(HORIZONS_HOURS),
        "model": "standardized ridge regression; alpha fixed before evaluation",
        "validation": "cohort-isolated expanding-window walk-forward; refit at every eligible hourly origin",
        "comparison": "paired observations and identical training rows for Spot baseline and Spot + Open Interest",
        "bootstrap": {
            "method": "circular moving-block bootstrap on paired loss differences",
            "repetitions": bootstrap_repetitions,
            "primary_block_length": "max(forecast horizon, 8 hours)",
            "primary_metric": "mean paired absolute-error reduction; positive favors Spot + Open Interest",
        },
        "multiple_testing": "Benjamini-Yekutieli correction across all evaluated cohort x horizon MAE contrasts",
        "leakage_controls": [
            "Open Interest features are aligned as-of the Spot candle close",
            "rows without a fresh prior snapshot are excluded from both model variants",
            "snapshots older than the effective open_interest interval plus one minute are rejected",
            "training labels end at or before each forecast origin",
            "scaling parameters are estimated only from the current training window",
            "each cohort is evaluated independently",
        ],
        "causal_claim": False,
        "limitations": [
            "predictive association is not causal identification",
            "the five episodes are selected historical cohorts, not a random sample of all market regimes",
            "Open Interest history is USD-M Futures data, not Spot-native data",
            "archive data does not provide markPrice or rateType",
            "results do not model transaction costs, slippage, or executable strategy performance",
        ],
        "cohorts": {},
    }
    tests: list[tuple[float, dict[str, Any]]] = []
    for name, rows in sorted(cohorts.items()):
        result = evaluate_cohort(rows, min_train, ridge_alpha, bootstrap_repetitions, seed)
        for horizon, metrics in result["horizons"].items():
            if metrics.get("status") == "evaluated":
                target = metrics["incremental_change"]
                tests.append((target["mae_block_bootstrap_two_sided_p"], target))
        report["cohorts"][name] = result
    _benjamini_yekutieli(tests)
    report["multiple_testing_contrasts"] = len(tests)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Spot + as-of Open Interest JSONL")
    parser.add_argument("--output", required=True)
    parser.add_argument("--min-train", type=int, default=168)
    parser.add_argument("--ridge-alpha", type=float, default=1e-6)
    parser.add_argument("--bootstrap-repetitions", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20261106)
    args = parser.parse_args()
    if args.ridge_alpha <= 0 or args.bootstrap_repetitions < 100:
        parser.error("ridge-alpha must be positive and bootstrap repetitions at least 100")
    report = analyze(
        load_cohorts(args.input), args.min_train, args.ridge_alpha,
        args.bootstrap_repetitions, args.seed
    )
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(json.dumps({"status": report["status"], "cohorts": len(report["cohorts"]),
                      "contrasts": report["multiple_testing_contrasts"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
