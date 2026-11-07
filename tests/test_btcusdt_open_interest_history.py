import unittest
from datetime import date

from scripts.research.fetch_btcusdt_open_interest_history import (
    audit_and_align,
    effective_snapshot_time_ms,
    _finite,
)


def spot_row(timestamp, cohort="test"):
    return {
        "cohort_window": cohort,
        "_ts": timestamp,
        "_close": 100.0,
        "open_time_ms": timestamp,
    }


class OpenInterestHistoryTests(unittest.TestCase):
    def test_timestamp_convention_change_is_applied_exactly_on_june_25(self):
        label = 1_782_259_200_000
        self.assertEqual(
            effective_snapshot_time_ms(label, date(2026, 6, 24)), label
        )
        self.assertEqual(
            effective_snapshot_time_ms(label, date(2026, 6, 25)),
            label + 300_000,
        )

    def test_invalid_and_negative_open_interest_values_are_rejected(self):
        for value in ("not-a-number", "nan", "inf", "-1"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                _finite(value, "sum_open_interest")

    def test_asof_alignment_does_not_use_future_or_stale_snapshots(self):
        hour = 3_600_000
        rows = [spot_row(0), spot_row(hour), spot_row(2 * hour)]
        snapshots = [
            {"snapshot_time_ms": 4_000_000, "sum_open_interest": 10.0,
             "sum_open_interest_value": 1_000.0},
            {"snapshot_time_ms": 6_900_000, "sum_open_interest": 11.0,
             "sum_open_interest_value": 1_100.0},
        ]
        report = {"cohorts": {}}
        aligned = audit_and_align({"test": rows}, snapshots, report)
        # First candle closes before the first snapshot: no future value.
        self.assertIsNone(aligned[0]["open_interest_base_asof"])
        # Second candle closes after snapshot 1; snapshot 2 is later than that close.
        self.assertEqual(aligned[1]["open_interest_base_asof"], 11.0)
        # Third candle has no sufficiently recent snapshot and remains null.
        self.assertIsNone(aligned[2]["open_interest_base_asof"])
        self.assertEqual(report["cohorts"]["test"]["fresh_asof_candles"], 1)


    def test_change_features_reject_stale_comparison_snapshots(self):
        rows = [spot_row(0)]
        snapshots = [
            {"snapshot_time_ms": -1_000_000, "sum_open_interest": 9.0,
             "sum_open_interest_value": 900.0},
            {"snapshot_time_ms": 3_500_000, "sum_open_interest": 10.0,
             "sum_open_interest_value": 1_000.0},
        ]
        report = {"cohorts": {}}
        aligned = audit_and_align({"test": rows}, snapshots, report)
        self.assertIsNone(aligned[0]["open_interest_change_1h_pct"])

    def test_missing_snapshot_is_not_imputed_as_zero(self):
        rows = [spot_row(0)]
        report = {"cohorts": {}}
        aligned = audit_and_align({"test": rows}, [], report)
        self.assertIsNone(aligned[0]["open_interest_base_asof"])
        self.assertIsNone(aligned[0]["open_interest_quote_asof"])


if __name__ == "__main__":
    unittest.main()
