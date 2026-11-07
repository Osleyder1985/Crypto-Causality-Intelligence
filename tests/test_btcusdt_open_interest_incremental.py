"""Tests for paired walk-forward Open Interest evaluation."""
import math
import unittest

from scripts.research.evaluate_btcusdt_open_interest_incremental import (
    OPEN_INTEREST_FEATURES,
    _row_features,
    evaluate_cohort,
)


HOUR_MS = 3_600_000


def synthetic_rows(count=120):
    rows = []
    base_time = 1_760_000_000_000
    for i in range(count):
        open_price = 100_000 + i * 3 + math.sin(i / 5) * 80
        close_price = open_price * (1 + math.sin(i / 7) * 0.001)
        high = max(open_price, close_price) + 20 + (i % 5)
        low = min(open_price, close_price) - 20 - (i % 3)
        close_time = base_time + (i + 1) * HOUR_MS - 1
        snapshot_time = close_time - 300_000
        rows.append({
            "cohort_window": "synthetic",
            "_ts": base_time + i * HOUR_MS,
            "_open": open_price,
            "_high": high,
            "_low": low,
            "_close": close_price,
            "_quote_volume": 100_000_000 + i * 50_000 + (i % 7) * 100_000,
            "_taker_buy_quote": 50_000_000 + i * 20_000 + (i % 5) * 50_000,
            "_trade_count": 100_000 + i * 20 + (i % 11) * 100,
            "close_time_ms": close_time,
            "open_interest_snapshot_time_ms": snapshot_time,
            "open_interest_age_minutes": (close_time - snapshot_time) / 60_000,
            "open_interest_base_asof": 90_000 + i * 12 + math.sin(i / 4) * 100,
            "open_interest_quote_asof": 9_000_000_000 + i * 1_500_000 + math.sin(i / 6) * 10_000_000,
            "open_interest_change_1h_pct": math.sin(i / 3) * 0.3,
            "open_interest_change_4h_pct": math.sin(i / 9) * 0.7,
            "open_interest_change_24h_pct": math.sin(i / 20) * 1.2,
        })
    return rows


class OpenInterestIncrementalTests(unittest.TestCase):
    def test_declared_features_match_dataset_contract(self):
        self.assertEqual(OPEN_INTEREST_FEATURES, (
            "open_interest_base_asof",
            "open_interest_quote_asof",
            "open_interest_change_1h_pct",
            "open_interest_change_4h_pct",
            "open_interest_change_24h_pct",
        ))

    def test_valid_snapshot_is_asof_and_levels_are_log_transformed(self):
        row = synthetic_rows(1)[0]
        spot, augmented = _row_features(row)
        self.assertEqual(len(augmented), len(spot) + 5)
        self.assertAlmostEqual(augmented[-5], math.log(row["open_interest_base_asof"]))
        self.assertAlmostEqual(augmented[-4], math.log(row["open_interest_quote_asof"]))
        self.assertEqual(augmented[-3:], [
            row["open_interest_change_1h_pct"],
            row["open_interest_change_4h_pct"],
            row["open_interest_change_24h_pct"],
        ])

    def test_future_snapshot_is_rejected(self):
        row = synthetic_rows(1)[0]
        row["open_interest_snapshot_time_ms"] = row["close_time_ms"] + 1
        with self.assertRaisesRegex(ValueError, "future-dated"):
            _row_features(row)

    def test_stale_snapshot_is_rejected(self):
        row = synthetic_rows(1)[0]
        row["open_interest_snapshot_time_ms"] = row["close_time_ms"] - 11 * 60_000
        row["open_interest_age_minutes"] = 11
        with self.assertRaisesRegex(ValueError, "stale"):
            _row_features(row)

    def test_walk_forward_returns_paired_results_for_all_horizons(self):
        report = evaluate_cohort(
            synthetic_rows(), min_train=24, bootstrap_repetitions=100, seed=17
        )
        self.assertEqual(report["candles"], 120)
        self.assertEqual(report["candles_with_fresh_open_interest"], 120)
        self.assertEqual(set(report["horizons"]), {"1", "3", "6", "12", "24"})
        for metrics in report["horizons"].values():
            self.assertEqual(metrics["status"], "evaluated")
            self.assertGreater(metrics["observations"], 0)
            self.assertIn("mae_block_bootstrap_95pct_ci", metrics["incremental_change"])


if __name__ == "__main__":
    unittest.main()
