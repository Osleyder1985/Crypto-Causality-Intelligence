import math
import unittest

from scripts.research.evaluate_btcusdt_funding_incremental import (
    _benjamini_yekutieli,
    _block_bootstrap_mean,
    _row_features,
    evaluate_cohort,
)


def synthetic_rows(count=220):
    rows = []
    for index in range(count):
        open_price = 100.0 + 0.015 * index + math.sin(index / 9) * 0.4
        close = open_price * (1 + 0.0008 * math.sin(index / 5) + 0.0002 * math.cos(index / 11))
        high = max(open_price, close) + 0.7 + 0.01 * (index % 3)
        low = min(open_price, close) - 0.6 - 0.01 * (index % 4)
        quote_volume = 10000.0 + (index % 17) * 125.0
        buy_quote = quote_volume * (0.5 + 0.12 * math.sin(index / 7))
        rows.append({
            "cohort_window": "synthetic",
            "_ts": index * 3_600_000,
            "_open": open_price,
            "_high": high,
            "_low": low,
            "_close": close,
            "_quote_volume": quote_volume,
            "_trade_count": 100.0 + (index % 13),
            "_taker_buy_quote": buy_quote,
            "funding_latest_rate_asof": 0.0001 * math.sin(index / 6),
            "funding_mean_last_3_asof": 0.00008 * math.cos(index / 8),
            "funding_latest_age_hours": float(index % 8),
            "funding_settlements_available_asof": min(3, 1 + index % 4),
        })
    return rows


class FundingIncrementalTests(unittest.TestCase):
    def test_walk_forward_compares_same_observations(self):
        result = evaluate_cohort(
            synthetic_rows(), min_train=48, bootstrap_repetitions=100, seed=7
        )
        self.assertEqual(set(result["horizons"]), {"1", "3", "6", "12", "24"})
        for metrics in result["horizons"].values():
            self.assertEqual(metrics["status"], "evaluated")
            self.assertGreater(metrics["observations"], 0)
            self.assertEqual(
                metrics["spot_baseline"]["mae"] >= 0, True
            )
            self.assertEqual(
                metrics["incremental_change"]["bootstrap_block_length_hours"],
                max(int(next(k for k, v in result["horizons"].items() if v is metrics)), 8),
            )

    def test_rejects_future_or_stale_funding_features(self):
        row = synthetic_rows(1)[0]
        row["funding_latest_age_hours"] = -0.01
        with self.assertRaisesRegex(ValueError, "future-dated or stale"):
            _row_features(row)
        row["funding_latest_age_hours"] = 8.1
        with self.assertRaisesRegex(ValueError, "future-dated or stale"):
            _row_features(row)

    def test_block_bootstrap_is_reproducible(self):
        values = [0.2, 0.1, -0.05, 0.3, 0.12, 0.08, -0.02, 0.2]
        first = _block_bootstrap_mean(values, 3, 200, 123)
        second = _block_bootstrap_mean(values, 3, 200, 123)
        self.assertEqual(first, second)
        self.assertLessEqual(first[0], first[1])

    def test_benjamini_yekutieli_adjustment_is_monotone(self):
        a, b, c = {}, {}, {}
        _benjamini_yekutieli([(0.01, a), (0.04, b), (0.20, c)])
        self.assertLessEqual(a["by_q_value_mae"], b["by_q_value_mae"])
        self.assertLessEqual(b["by_q_value_mae"], c["by_q_value_mae"])
        self.assertTrue(all(0 <= x["by_q_value_mae"] <= 1 for x in (a, b, c)))


if __name__ == "__main__":
    unittest.main()
