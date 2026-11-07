import unittest

from scripts.research.evaluate_btcusdt_walk_forward import evaluate_cohort


def synthetic_rows(count=220):
    rows = []
    price = 100.0
    for i in range(count):
        change = 0.0004 + 0.001 * ((i % 7) - 3) / 3
        open_price = price
        close = open_price * (1 + change)
        high = max(open_price, close) * 1.002
        low = min(open_price, close) * 0.998
        quote_volume = 1000.0 + (i % 19) * 17.0
        trades = 20.0 + (i % 11)
        buy = quote_volume * (0.45 + (i % 9) * 0.01)
        rows.append({
            "_ts": i * 3_600_000, "_open": open_price, "_high": high,
            "_low": low, "_close": close, "_quote_volume": quote_volume,
            "_trade_count": trades, "_taker_buy_quote": buy,
        })
        price = close
    return rows


class WalkForwardTests(unittest.TestCase):
    def test_expanding_walk_forward_emits_out_of_sample_metrics(self):
        result = evaluate_cohort(synthetic_rows(), min_train=168)
        one_hour = result["horizons"]["1"]
        self.assertEqual(one_hour["status"], "evaluated")
        self.assertEqual(one_hour["observations"], 51)
        self.assertIn("mae", one_hour)
        self.assertIn("baseline_train_mean_mae", one_hour)
        self.assertIn("directional_accuracy", one_hour)
        self.assertIn("training labels end no later than forecast origin", one_hour["training_policy"])

    def test_short_cohort_is_not_misreported_as_evaluated(self):
        result = evaluate_cohort(synthetic_rows(80), min_train=168)
        self.assertEqual(result["horizons"]["24"]["status"], "insufficient_test_observations")
        self.assertEqual(result["horizons"]["24"]["observations"], 0)

    def test_minimum_training_window_is_guarded(self):
        with self.assertRaisesRegex(ValueError, "at least 24"):
            evaluate_cohort(synthetic_rows(), min_train=12)


if __name__ == "__main__":
    unittest.main()
