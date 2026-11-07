"""Cohort-isolated multifactor OLS with Newey-West HAC inference for BTCUSDT."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from scripts.research.analyze_btcusdt_multifactor import HORIZONS_HOURS, load_cohorts

FEATURES = (
    "signed_taker_buy_quote_imbalance",
    "log_quote_volume",
    "log_trade_count",
    "normalized_candle_range",
    "candle_body_return",
    "close_location_value",
)


def _features(row: dict[str, Any]) -> list[float]:
    span = row["_high"] - row["_low"]
    return [
        (2 * row["_taker_buy_quote"] - row["_quote_volume"]) / row["_quote_volume"],
        math.log(row["_quote_volume"]),
        math.log(row["_trade_count"]),
        span / row["_open"],
        math.log(row["_close"] / row["_open"]),
        (2 * row["_close"] - row["_high"] - row["_low"]) / span if span else 0.0,
    ]


def _inverse(matrix: list[list[float]]) -> list[list[float]]:
    n = len(matrix)
    aug = [list(map(float, row)) + [float(i == j) for j in range(n)] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(aug[r][col]))
        if abs(aug[pivot][col]) < 1e-12:
            raise ValueError("singular design matrix; predictors are collinear or constant")
        aug[col], aug[pivot] = aug[pivot], aug[col]
        scale = aug[col][col]
        aug[col] = [v / scale for v in aug[col]]
        for r in range(n):
            if r == col:
                continue
            factor = aug[r][col]
            aug[r] = [a - factor * b for a, b in zip(aug[r], aug[col])]
    return [row[n:] for row in aug]


def _matmul(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [[sum(a[i][k] * b[k][j] for k in range(len(b))) for j in range(len(b[0]))] for i in range(len(a))]


def _normal_p(z: float) -> float:
    return math.erfc(abs(z) / math.sqrt(2.0))


def _bh_adjust(items: list[tuple[float, dict]]) -> None:
    ordered = sorted(items, key=lambda item: item[0])
    running = 1.0
    m = len(ordered)
    for rank0 in range(m - 1, -1, -1):
        p, target = ordered[rank0]
        rank = rank0 + 1
        running = min(running, p * m / rank)
        target["bh_q_value"] = min(1.0, running)


def _fit_hac(x: list[list[float]], y: list[float], max_lag: int) -> dict:
    n, k = len(x), len(x[0])
    xtx = [[sum(row[i] * row[j] for row in x) for j in range(k)] for i in range(k)]
    inv = _inverse(xtx)
    xty = [sum(row[j] * target for row, target in zip(x, y)) for j in range(k)]
    beta = [sum(inv[i][j] * xty[j] for j in range(k)) for i in range(k)]
    residuals = [target - sum(a * b for a, b in zip(row, beta)) for row, target in zip(x, y)]
    scores = [[row[j] * residual for j in range(k)] for row, residual in zip(x, residuals)]
    meat = [[sum(s[i] * s[j] for s in scores) for j in range(k)] for i in range(k)]
    for lag in range(1, min(max_lag, n - 1) + 1):
        weight = 1.0 - lag / (max_lag + 1.0)
        cross = [[sum(scores[t][i] * scores[t-lag][j] + scores[t-lag][i] * scores[t][j]
                      for t in range(lag, n)) * weight for j in range(k)] for i in range(k)]
        meat = [[meat[i][j] + cross[i][j] for j in range(k)] for i in range(k)]
    cov = _matmul(_matmul(inv, meat), inv)
    correction = n / max(1, n - k)
    se = [math.sqrt(max(0.0, cov[i][i] * correction)) for i in range(k)]
    mean_y = sum(y) / n
    ss_tot = sum((v - mean_y) ** 2 for v in y)
    ss_res = sum(v * v for v in residuals)
    return {
        "observations": n,
        "predictors": k - 1,
        "r_squared": 1 - ss_res / ss_tot if ss_tot else None,
        "hac_max_lag": max_lag,
        "coefficients": [
            {"term": "intercept" if j == 0 else FEATURES[j-1], "estimate": beta[j],
             "hac_standard_error": se[j],
             "z_statistic": beta[j] / se[j] if se[j] else None,
             "p_value": _normal_p(beta[j] / se[j]) if se[j] else None}
            for j in range(k)
        ],
    }


def analyze(cohorts: dict[str, list[dict[str, Any]]]) -> dict:
    report = {
        "status": "multifactor_ols_hac_diagnostics",
        "provider": "binance", "market_type": "SPOT", "symbol": "BTCUSDT", "interval": "1h",
        "target": "log(close[t+h] / close[t])",
        "predictor_timing": "features from candle t; target begins at close t and ends at close t+h",
        "inference": "Newey-West HAC standard errors with Bartlett kernel; overlapping-return lag set to horizon-1",
        "multiple_testing": "Benjamini-Hochberg q-values across all coefficients and horizons within each cohort",
        "causal_claim": False,
        "limitations": ["exploratory in-sample association, not causal identification",
                        "normal-reference p-values are asymptotic",
                        "no out-of-sample predictive claim; walk-forward validation remains required"],
        "cohorts": {},
    }
    for name, rows in sorted(cohorts.items()):
        closes = [r["_close"] for r in rows]
        feats = [_features(r) for r in rows]
        horizon_results = {}
        tests = []
        for horizon in HORIZONS_HOURS:
            n = len(rows) - horizon
            if n <= len(FEATURES) + 2:
                horizon_results[str(horizon)] = {"status": "insufficient_observations", "observations": max(0, n)}
                continue
            x = [[1.0] + feats[i] for i in range(n)]
            y = [math.log(closes[i+horizon] / closes[i]) for i in range(n)]
            fit = _fit_hac(x, y, horizon - 1)
            for coefficient in fit["coefficients"]:
                if coefficient["p_value"] is not None:
                    tests.append((coefficient["p_value"], coefficient))
            horizon_results[str(horizon)] = fit
        _bh_adjust(tests)
        report["cohorts"][name] = {
            "candles": len(rows), "horizons": horizon_results,
            "multiple_testing_tests": len(tests),
        }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    rendered = json.dumps(analyze(load_cohorts(args.input)), indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
