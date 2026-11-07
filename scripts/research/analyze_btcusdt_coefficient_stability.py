"""Compare standardized HAC coefficients across BTCUSDT experiment cohorts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.research.analyze_btcusdt_hac import FEATURES, analyze
from scripts.research.analyze_btcusdt_multifactor import HORIZONS_HOURS, load_cohorts


def _quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def summarize_coefficients(hac_report: dict[str, Any], zero_tolerance: float = 1e-12) -> dict:
    cohort_names = sorted(hac_report.get("cohorts", {}))
    stability: dict[str, Any] = {}
    for horizon in HORIZONS_HOURS:
        by_feature = {}
        for feature in FEATURES:
            cohort_estimates = []
            for cohort_name in cohort_names:
                cohort = hac_report["cohorts"][cohort_name]
                fit = cohort.get("horizons", {}).get(str(horizon), {})
                coefficient = next(
                    (item for item in fit.get("coefficients", []) if item.get("term") == feature),
                    None,
                )
                if coefficient is None or coefficient.get("standardized_estimate") is None:
                    continue
                estimate = float(coefficient["standardized_estimate"])
                se = coefficient.get("standardized_hac_standard_error")
                q_value = coefficient.get("bh_q_value")
                sign = "positive" if estimate > zero_tolerance else (
                    "negative" if estimate < -zero_tolerance else "near_zero"
                )
                cohort_estimates.append({
                    "cohort": cohort_name,
                    "standardized_estimate": estimate,
                    "standardized_hac_standard_error": se,
                    "bh_q_value": q_value,
                    "sign": sign,
                })
            values = [item["standardized_estimate"] for item in cohort_estimates]
            signs = [item["sign"] for item in cohort_estimates]
            directional = [sign for sign in signs if sign != "near_zero"]
            positive = directional.count("positive")
            negative = directional.count("negative")
            by_feature[feature] = {
                "available_cohorts": len(values),
                "expected_cohorts": len(cohort_names),
                "missing_cohorts": sorted(set(cohort_names) - {item["cohort"] for item in cohort_estimates}),
                "positive_cohorts": positive,
                "negative_cohorts": negative,
                "near_zero_cohorts": signs.count("near_zero"),
                "dominant_sign": (
                    "positive" if positive > negative else
                    "negative" if negative > positive else "mixed_or_unresolved"
                ),
                "sign_agreement_ratio": (
                    max(positive, negative) / len(directional) if directional else None
                ),
                "median_standardized_estimate": _quantile(values, 0.5) if values else None,
                "interquartile_range": (
                    _quantile(values, 0.75) - _quantile(values, 0.25) if values else None
                ),
                "minimum_standardized_estimate": min(values) if values else None,
                "maximum_standardized_estimate": max(values) if values else None,
                "cohorts_with_bh_q_below_0_05": sum(
                    item["bh_q_value"] is not None and item["bh_q_value"] < 0.05
                    for item in cohort_estimates
                ),
                "cohort_estimates": cohort_estimates,
            }
        stability[str(horizon)] = by_feature
    return {
        "status": "cohort_coefficient_stability_diagnostics",
        "provider": hac_report.get("provider"),
        "market_type": hac_report.get("market_type"),
        "symbol": hac_report.get("symbol"),
        "interval": hac_report.get("interval"),
        "cohorts": cohort_names,
        "horizons_hours": list(HORIZONS_HOURS),
        "coefficient_scale": "standardized beta = raw beta * population_sd(feature) / population_sd(forward_return)",
        "sign_zero_tolerance": zero_tolerance,
        "aggregation_policy": "descriptive summaries only; no pooled coefficient is reported",
        "inference_limitations": [
            "cohorts are selected historical episodes, not random independent samples of all market regimes",
            "standardized coefficient comparability does not establish causal effects",
            "HAC q-values remain cohort-local exploratory diagnostics",
            "missing or non-estimable coefficients are reported, never imputed",
        ],
        "stability": stability,
        "causal_claim": False,
    }


def analyze_stability(cohorts: dict[str, list[dict[str, Any]]]) -> dict:
    return summarize_coefficients(analyze(cohorts))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    rendered = json.dumps(analyze_stability(load_cohorts(args.input)), indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
