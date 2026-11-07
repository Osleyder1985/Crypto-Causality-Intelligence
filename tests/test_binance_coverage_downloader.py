import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "research"))

import download_binance_btcusdt_coverage as coverage


class CoverageManifestTests(unittest.TestCase):
    def test_five_windows_have_expected_total(self):
        self.assertEqual(sum(window[3] for window in coverage.WINDOWS), 5976)
        self.assertEqual([window[3] for window in coverage.WINDOWS], [1099, 532, 2145, 1336, 864])

    def test_windows_are_hour_aligned_and_expected_count_matches_duration(self):
        for _, start, end, expected in coverage.WINDOWS:
            start_ms = coverage.epoch_ms(start)
            end_ms = coverage.epoch_ms(end)
            self.assertEqual(start_ms % coverage.INTERVAL_MS, 0)
            self.assertEqual(end_ms % coverage.INTERVAL_MS, 0)
            self.assertEqual((end_ms - start_ms) // coverage.INTERVAL_MS, expected)

    def test_naive_timestamps_are_rejected(self):
        with self.assertRaises(ValueError):
            coverage.epoch_ms("2026-05-06T09:00:00")

    def test_valid_ohlcv_candle_passes(self):
        row = [0, "100", "110", "95", "105", "12.5", 3599999, "1300", 42, "6", "620", "0"]
        self.assertEqual(coverage.validate_candle(row), [])

    def test_invalid_ohlc_and_negative_volume_are_detected(self):
        row = [0, "100", "90", "95", "105", "-1", 3599999, "0", 0, "0", "0", "0"]
        problems = coverage.validate_candle(row)
        self.assertIn("ohlc_invariant_violation", problems)
        self.assertIn("negative_volume", problems)

    def test_close_time_must_end_the_hour(self):
        row = [0, "100", "110", "95", "105", "12.5", 3599998, "1300", 42, "6", "620", "0"]
        self.assertIn("invalid_close_time", coverage.validate_candle(row))

    def test_non_finite_market_values_are_rejected(self):
        row = [0, "100", "110", "95", "105", "NaN", 3599999, "1300", 42, "6", "620", "0"]
        self.assertIn("non_finite_market_fields", coverage.validate_candle(row))

    def test_taker_volume_cannot_exceed_total_volume(self):
        row = [0, "100", "110", "95", "105", "12.5", 3599999, "1300", 42, "13", "620", "0"]
        self.assertIn("taker_volume_exceeds_total", coverage.validate_candle(row))

    def test_invalid_response_shape_is_detected(self):
        self.assertEqual(coverage.validate_candle([1, 2, 3]), ["invalid_field_count"])


class PaginationRegressionTests(unittest.TestCase):
    @staticmethod
    def candle(open_time):
        return [
            open_time, "100", "110", "95", "105", "12.5",
            open_time + coverage.INTERVAL_MS - 1,
            "1300", 42, "6", "620", "0",
        ]

    def test_nonempty_partial_page_does_not_stop_pagination(self):
        start = "1970-01-01T00:00:00+00:00"
        end = "1970-01-01T03:00:00+00:00"
        window = ("pagination_regression", start, end, 3)
        first_page = [self.candle(0), self.candle(coverage.INTERVAL_MS)]
        second_page = [self.candle(2 * coverage.INTERVAL_MS)]
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(coverage, "WINDOWS", [window]):
                with patch.object(coverage, "fetch_page", side_effect=[
                    (b"first-page", first_page), (b"second-page", second_page)
                ]) as fetch:
                    report = coverage.download(Path(tmp))
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(report["summary"]["received_unique_candles"], 3)
        self.assertEqual(report["windows"][0]["status"], "candidate_complete")
        self.assertEqual(len(report["windows"][0]["pages"]), 2)

    def test_empty_page_before_window_end_is_not_complete(self):
        start = "1970-01-01T00:00:00+00:00"
        end = "1970-01-01T03:00:00+00:00"
        window = ("early_empty_page", start, end, 3)
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(coverage, "WINDOWS", [window]):
                with patch.object(coverage, "fetch_page", return_value=(b"[]", [])):
                    report = coverage.download(Path(tmp))
        self.assertEqual(report["summary"]["received_unique_candles"], 0)
        self.assertEqual(report["windows"][0]["missing_open_times"], 3)
        self.assertEqual(report["windows"][0]["status"], "pending_review")


if __name__ == "__main__":
    unittest.main()

# CI trigger: keep this suite covered by the PR validation workflow.
# Regression fixtures intentionally use Binance's documented positional kline schema.
