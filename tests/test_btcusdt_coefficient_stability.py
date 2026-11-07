import unittest

from scripts.research.analyze_btcusdt_coefficient_stability import summarize_coefficients
from scripts.research.analyze_btcusdt_hac import FEATURES, _fit_hac


class CoefficientStabilityTests(unittest.TestCase):
    def test_hac_fit_emits_standardized_coefficients(self):
        x = [[1.0, float(i)] for i in range(30)]
        y = [0.4 + 0.03 * i + (0.02 if i % 3 == 0 else -0.01) for i in range(30)]
        result = _fit_hac(x, y, max_lag=3)
        predictor = result["coefficients"][1]
        self.assertIsNotNone(predictor["standardized_estimate"])
        self.assertIsNotNone(predictor["standardized_hac_standard_error"])

    def test_summarizes_sign_and_dispersion_without_pooling(self):
        feature = FEATURES[0]
        report = {
            "provider": "binance", "market_type": "SPOT", "symbol": "BTCUSDT", "interval": "1h",
            "cohorts": {
                "cohort_a": {"horizons": {"1": {"coefficients": [
                    {"term": feature, "standardized_estimate": 0.4,
                     "standardized_hac_standard_error": 0.1, "bh_q_value": 0.02}
                ]}}},
                "cohort_b": {"horizons": {"1": {"coefficients": [
                    {"term": feature, "standardized_estimate": 0.2,
                     "standardized_hac_standard_error": 0.1, "bh_q_value": 0.2}
                ]}}},
                "cohort_c": {"horizons": {"1": {"coefficients": [
                    {"term": feature, "standardized_estimate": -0.1,
                     "standardized_hac_standard_error": 0.2, "bh_q_value": 0.8}
                ]}}},
            },
        }
        result = summarize_coefficients(report)
        summary = result["stability"]["1"][feature]
        self.assertEqual(summary["available_cohorts"], 3)
        self.assertEqual(summary["positive_cohorts"], 2)
        self.assertEqual(summary["negative_cohorts"], 1)
        self.assertAlmostEqual(summary["sign_agreement_ratio"], 2 / 3)
        self.assertEqual(summary["cohorts_with_bh_q_below_0_05"], 1)
        self.assertNotIn("pooled_estimate", summary)

    def test_missing_cohorts_are_explicit(self):
        feature = FEATURES[0]
        report = {
            "cohorts": {
                "cohort_a": {"horizons": {"1": {"coefficients": [
                    {"term": feature, "standardized_estimate": 0.2,
                     "standardized_hac_standard_error": 0.1, "bh_q_value": None}
                ]}}},
                "cohort_b": {"horizons": {"1": {"coefficients": []}}},
            }
        }
        summary = summarize_coefficients(report)["stability"]["1"][feature]
        self.assertEqual(summary["available_cohorts"], 1)
        self.assertEqual(summary["missing_cohorts"], ["cohort_b"])
        self.assertEqual(summary["sign_agreement_ratio"], 1.0)


if __name__ == "__main__":
    unittest.main()
