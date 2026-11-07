"""Leakage-safe expanding-window walk-forward evaluation for BTCUSDT Spot."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from scripts.research.analyze_btcusdt_hac import FEATURES, _features
from scripts.research.analyze_btcusdt_multifactor import HORIZONS_HOURS, load_cohorts
from scripts.research.btcusdt_block_bootstrap import benjamini_yekutieli, paired_block_bootstrap


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


def _metrics(actual: list[float], predicted: list[float], baseline: list[float], *,
             block_length: int, bootstrap_replicates: int, bootstrap_seed: int) -> dict:
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
        "block_bootstrap_inference": paired_block_bootstrap(
            actual, predicted, baseline, block_length=block_length,
            replicates=bootstrap_replicates, seed=bootstrap_seed,
        ),
    }


def evaluate_cohort(rows: list[dict[str, Any]], min_train: int = 168,
                    ridge_alpha: float = 1e-6, block_length: int = 24,
                    bootstrap_replicates: int = 2000, bootstrap_seed: int = 20261106) -> dict:
    if min_train < 24:
        raise ValueError("min_train must be at least 24 hourly observations")
    if block_length < 1:
        raise ValueError("block_length must be positive")
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
        results[str(horizon)] = _metrics(
            actual, predicted, baseline, block_length=block_length,
            bootstrap_replicates=bootstrap_replicates, bootstrap_seed=bootstrap_seed + horizon,
        )
        results[str(horizon)]["first_test_origin_index"] = first_origin if len(rows) > first_origin + horizon else None
        results[str(horizon)]["training_policy"] = "expanding window; refit at every hourly origin; training labels end no later than forecast origin"
    return {"candles": len(rows), "minimum_training_observations": min_train,
            "ridge_alpha": ridge_alpha, "horizons": results}


def analyze(cohorts: dict[str, list[dict[str, Any]]], min_train: int = 168,
            ridge_alpha: float = 1e-6, block_length: int = 24,
            bootstrap_replicates: int = 2000, bootstrap_seed: int = 20261106) -> dict:
    report = {
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
        "bootstrap_protocol": {
            "method": "paired moving-block bootstrap with non-circular contiguous blocks",
            "block_length_hours": block_length,
            "replicates": bootstrap_replicates,
            "seed": bootstrap_seed,
            "confidence_level": 0.95,
            "superiority_alternative": "model improves over baseline",
            "block_length_policy": "fixed at 24 hours, the maximum forecast horizon; not selected from observed performance",
        },
        "limitations": [
            "forecast origins are hourly and horizons overlap, so pointwise IID confidence intervals are invalid",
            "bootstrap inference is unavailable when a cohort/horizon has fewer observations than the fixed block length",
            "the centered bootstrap p-values are approximate finite-sample tests of mean paired improvement",
            "no transaction costs, slippage, or executable trading strategy is modeled",
            "ridge alpha is fixed, not tuned on test observations",
            "predictive superiority does not establish causal identification",
        ],
        "causal_claim": False,
        "cohorts": {
            name: evaluate_cohort(
                rows, min_train, ridge_alpha, block_length, bootstrap_replicates,
                bootstrap_seed + sum(name.encode("utf-8")),
            )
            for name, rows in sorted(cohorts.items())
        }
    }
    # Correct the full confirmatory family across all available cohort/horizon/metric
    # tests; BY is conservative and remains valid under arbitrary test dependence.
    test_locations = []
    p_values = []
    for cohort_name, cohort_result in report["cohorts"].items():
        for horizon_name, horizon_result in cohort_result["horizons"].items():
            inference = horizon_result.get("block_bootstrap_inference", {})
            tests = inference.get("one_sided_superiority_tests", {})
            for metric_name, test_result in tests.items():
                if "p_value_one_sided" in test_result:
                    test_locations.append((cohort_name, horizon_name, metric_name, test_result))
                    p_values.append(test_result["p_value_one_sided"])
    q_values = benjamini_yekutieli(p_values)
    for (cohort_name, horizon_name, metric_name, test_result), q_value in zip(test_locations, q_values):
        test_result["by_q_value"] = q_value
        test_result["fdr_adjustment"] = "Benjamini-Yekutieli"
        test_result["fdr_family_size"] = len(p_values)
    report["multiple_testing"] = {
        "method": "Benjamini-Yekutieli",
        "family": "all bootstrap superiority tests across available cohorts, horizons and metrics",
        "tests": len(p_values),
        "reason": "controls false discovery rate under arbitrary dependence",
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output")
    parser.add_argument("--min-train", type=int, default=168)
    parser.add_argument("--ridge-alpha", type=float, default=1e-6)
    parser.add_argument("--bootstrap-block-length", type=int, default=24)
    parser.add_argument("--bootstrap-replicates", type=int, default=2000)
    parser.add_argument("--bootstrap-seed", type=int, default=20261106)
    args = parser.parse_args()
    if args.ridge_alpha <= 0:
        parser.error("--ridge-alpha must be positive")
    if args.bootstrap_block_length < 1 or args.bootstrap_replicates < 100:
        parser.error("bootstrap block length must be positive and replicates must be at least 100")
    rendered = json.dumps(
        analyze(load_cohorts(args.input), args.min_train, args.ridge_alpha,
                args.bootstrap_block_length, args.bootstrap_replicates, args.bootstrap_seed),
        indent=2, sort_keys=True,
    ) + "\n"
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
