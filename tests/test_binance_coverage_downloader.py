import sys
import unittest
from pathlib import Path

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

    def test_invalid_response_shape_is_detected(self):
        self.assertEqual(coverage.validate_candle([1, 2, 3]), ["invalid_field_count"])


if __name__ == "__main__":
    unittest.main()
