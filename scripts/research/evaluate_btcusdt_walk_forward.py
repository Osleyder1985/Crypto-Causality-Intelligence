"""Leakage-safe expanding-window walk-forward evaluation for BTCUSDT Spot."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from scripts.research.analyze_btcusdt_hac import FEATURES, _features
from scripts.research.analyze_btcusdt_multifactor import HORIZONS_HOURS, load_cohorts


def _solve(matrix: list[list[float]], vector: list[float]) -> list[float]:
    n = len(vector)
    aug = [list(map(float, matrix[i])) + [float(vector[i])] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(aug[r][col]))
        if abs(aug[pivot][col]) < 1e-14:
            raise ValueError("regularized design matrix is singular")
        aug[col], aug[pivot] = aug[pivot], aug[col]
        scale = aug[col][col]
        aug[col] = [v / scale for v in aug[col]]
        for r in range(n):
            if r == col:
                continue
            factor = aug[r][col]
            aug[r] = [a - factor * b for a, b in zip(aug[r], aug[col])]
    return [aug[i][-1] for i in range(n)]


def _fit_predict(train_x: list[list[float]], train_y: list[float],
                 test_x: list[float], ridge_alpha: float) -> tuple[float, float]:
    k = len(FEATURES)
    means = [sum(row[j] for row in train_x) / len(train_x) for j in range(k)]
    scales = []
    for j in range(k):
        variance = sum((row[j] - means[j]) ** 2 for row in train_x) / len(train_x)
        scales.append(math.sqrt(variance) or 1.0)
    z_train = [[(row[j] - means[j]) / scales[j] for j in range(k)] for row in train_x]
    y_mean = sum(train_y) / len(train_y)
    centered_y = [v - y_mean for v in train_y]
    gram = [[sum(row[i] * row[j] for row in z_train) for j in range(k)] for i in range(k)]
    for j in range(k):
        gram[j][j] += ridge_alpha
    cross = [sum(row[j] * y for row, y in zip(z_train, centered_y)) for j in range(k)]
    beta = _solve(gram, cross)
    z_test = [(test_x[j] - means[j]) / scales[j] for j in range(k)]
    prediction = y_mean + sum(a * b for a, b in zip(beta, z_test))
    return prediction, y_mean


def _metrics(actual: list[float], predicted: list[float], baseline: list[float]) -> dict:
    n = len(actual)
    if not n:
        return {"status": "insufficient_test_observations", "observations": 0}
    mae = sum(abs(a-p) for a, p in zip(actual, predicted)) / n
    rmse = math.sqrt(sum((a-p)**2 for a, p in zip(actual, predicted)) / n)
    base_mae = sum(abs(a-p) for a, p in zip(actual, baseline)) / n
    base_rmse = math.sqrt(sum((a-p)**2 for a, p in zip(actual, baseline)) / n)
    mean_actual = sum(actual) / n
    ss_tot = sum((a-mean_actual)**2 for a in actual)
    ss_res = sum((a-p)**2 for a, p in zip(actual, predicted))
    direction = sum((a >= 0) == (p >= 0) for a, p in zip(actual, predicted)) / n
    baseline_direction = sum((a >= 0) == (p >= 0) for a, p in zip(actual, baseline)) / n
    return {
        "status": "evaluated", "observations": n,
        "mae": mae, "rmse": rmse, "out_of_sample_r_squared": 1-ss_res/ss_tot if ss_tot else None,
        "directional_accuracy": direction,
        "baseline_train_mean_mae": base_mae, "baseline_train_mean_rmse": base_rmse,
        "baseline_train_mean_directional_accuracy": baseline_direction,
        "mae_improvement_vs_baseline_pct": (1-mae/base_mae)*100 if base_mae else None,
        "rmse_improvement_vs_baseline_pct": (1-rmse/base_rmse)*100 if base_rmse else None,
    }


def evaluate_cohort(rows: list[dict[str, Any]], min_train: int = 168,
                    ridge_alpha: float = 1e-6) -> dict:
    if min_train < 24:
        raise ValueError("min_train must be at least 24 hourly observations")
    closes = [row["_close"] for row in rows]
    features = [_features(row) for row in rows]
    results = {}
    for horizon in HORIZONS_HOURS:
        actual, predicted, baseline = [], [], []
        first_origin = min_train + horizon
        for origin in range(first_origin, len(rows) - horizon):
            # A training label is admissible only when its endpoint is at or before
            # the current forecast origin. No future close enters model fitting.
            train_end_exclusive = origin - horizon + 1
            train_indices = range(train_end_exclusive)
            train_x = [features[i] for i in train_indices]
            train_y = [math.log(closes[i+horizon] / closes[i]) for i in train_indices]
            target = math.log(closes[origin+horizon] / closes[origin])
            prediction, train_mean = _fit_predict(train_x, train_y, features[origin], ridge_alpha)
            actual.append(target)
            predicted.append(prediction)
            baseline.append(train_mean)
        results[str(horizon)] = _metrics(actual, predicted, baseline)
        results[str(horizon)]["first_test_origin_index"] = first_origin if len(rows) > first_origin + horizon else None
        results[str(horizon)]["training_policy"] = "expanding window; refit at every hourly origin; training labels end no later than forecast origin"
    return {"candles": len(rows), "minimum_training_observations": min_train,
            "ridge_alpha": ridge_alpha, "horizons": results}


def analyze(cohorts: dict[str, list[dict[str, Any]]], min_train: int = 168,
            ridge_alpha: float = 1e-6) -> dict:
    return {
        "status": "walk_forward_out_of_sample_evaluation",
        "provider": "binance", "market_type": "SPOT", "symbol": "BTCUSDT", "interval": "1h",
        "model": "standardized ridge regression; scaling fitted only on each training window",
        "features": list(FEATURES),
        "validation": "expanding-window; one-step hourly forecast origins; refit at every origin",
        "leakage_controls": [
            "training labels are included only when their horizon endpoint is at or before the forecast origin",
            "feature scaling is fitted exclusively on the current training window",
            "each cohort is evaluated independently; no cross-cohort training",
            "the forecast target begins at the close of the feature candle"
        ],
        "benchmark": "training-window mean forward return (no-predictor baseline)",
        "limitations": [
            "overlapping forecast horizons make test errors serially dependent",
            "metrics are descriptive; confidence intervals and block-bootstrap significance are not included",
            "no transaction costs, slippage, or executable trading strategy is modeled",
            "ridge alpha is fixed, not tuned on test observations"
        ],
        "causal_claim": False,
        "cohorts": {name: evaluate_cohort(rows, min_train, ridge_alpha)
                    for name, rows in sorted(cohorts.items())}
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output")
    parser.add_argument("--min-train", type=int, default=168)
    parser.add_argument("--ridge-alpha", type=float, default=1e-6)
    args = parser.parse_args()
    if args.ridge_alpha <= 0:
        parser.error("--ridge-alpha must be positive")
    rendered = json.dumps(analyze(load_cohorts(args.input), args.min_train, args.ridge_alpha),
                           indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
