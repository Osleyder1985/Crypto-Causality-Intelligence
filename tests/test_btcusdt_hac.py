import unittest

from scripts.research.analyze_btcusdt_hac import _bh_adjust, _fit_hac


class HacRegressionTests(unittest.TestCase):
    def test_hac_fit_reports_robust_uncertainty(self):
        x = [[1.0, float(i)] for i in range(30)]
        y = [0.4 + 0.03 * i + (0.02 if i % 3 == 0 else -0.01) for i in range(30)]
        result = _fit_hac(x, y, max_lag=3)
        self.assertEqual(result["observations"], 30)
        self.assertEqual(result["hac_max_lag"], 3)
        self.assertEqual([c["term"] for c in result["coefficients"]], ["intercept", "signed_taker_buy_quote_imbalance"])
        self.assertGreater(result["coefficients"][1]["hac_standard_error"], 0)
        self.assertIsNotNone(result["r_squared"])

    def test_hac_fit_rejects_singular_design(self):
        x = [[1.0, 2.0] for _ in range(10)]
        with self.assertRaisesRegex(ValueError, "singular"):
            _fit_hac(x, [float(i) for i in range(10)], max_lag=1)

    def test_benjamini_hochberg_is_monotone_in_rank(self):
        a, b, c = {}, {}, {}
        _bh_adjust([(0.01, a), (0.04, b), (0.03, c)])
        self.assertAlmostEqual(a["bh_q_value"], 0.03)
        self.assertAlmostEqual(c["bh_q_value"], 0.045)
        self.assertAlmostEqual(b["bh_q_value"], 0.045)


if __name__ == "__main__":
    unittest.main()
