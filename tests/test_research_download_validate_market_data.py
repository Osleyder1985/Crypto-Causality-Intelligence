import unittest

from scripts.research.download_validate_market_data import utc_epoch, validate_candles


def candle(timestamp, *, open_price="100", high="110", low="90", close="105", volume="1"):
    return {
        "open_time_utc": str(timestamp),
        "open": open_price,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }


class TimestampTests(unittest.TestCase):
    def test_utc_epoch_accepts_explicit_utc(self):
        self.assertEqual(utc_epoch("1970-01-01T00:00:00Z"), 0)

    def test_utc_epoch_rejects_naive_timestamp(self):
        with self.assertRaises(ValueError):
            utc_epoch("2026-11-06T00:00:00")


class CandleValidationTests(unittest.TestCase):
    def test_complete_continuous_window(self):
        report = validate_candles(
            [candle(0), candle(3600)], 3600, 0, 7200
        )
        self.assertEqual(report["records_in_window"], 2)
        self.assertEqual(report["coverage_pct_if_continuous"], 100.0)
        self.assertEqual(report["duplicate_timestamps"], 0)
        self.assertTrue(report["strictly_ordered"])
        self.assertEqual(report["gaps"], [])
        self.assertEqual(report["ohlc_or_volume_violations"], [])

    def test_reports_missing_interval(self):
        report = validate_candles(
            [candle(0), candle(7200)], 3600, 0, 10800
        )
        self.assertEqual(report["coverage_pct_if_continuous"], 66.6667)
        self.assertEqual(report["gaps"][0]["missing_intervals"], 1)

    def test_reports_duplicate_timestamp(self):
        report = validate_candles(
            [candle(0), candle(0)], 3600, 0, 7200
        )
        self.assertEqual(report["duplicate_timestamps"], 1)
        self.assertFalse(report["strictly_ordered"])

    def test_reports_ohlc_and_negative_volume_violations(self):
        report = validate_candles(
            [candle(0, high="101", close="105", volume="-1")],
            3600, 0, 3600
        )
        self.assertEqual(
            {item["type"] for item in report["ohlc_or_volume_violations"]},
            {"ohlc", "negative_volume"},
        )

    def test_reports_misaligned_outside_and_zero_volume(self):
        report = validate_candles(
            [candle(1800, volume="0"), candle(7200)],
            3600, 0, 3600
        )
        self.assertEqual(report["records_outside_window"], 1)
        self.assertEqual(report["misaligned_timestamps"], [1800])
        self.assertEqual(report["zero_volume_records"], 1)


if __name__ == "__main__":
    unittest.main()
