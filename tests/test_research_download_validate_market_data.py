import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.research.download_validate_market_data import (
    fetch_binance, fetch_binance_metadata, fetch_kraken,
    fetch_kraken_metadata, metadata_validation_issues, utc_epoch, validate_candles,
)


def candle(timestamp, *, open_price="100", high="110", low="90", close="105",
           volume="1", trade_count="2"):
    return {
        "open_time_utc": str(timestamp),
        "open": open_price,
        "high": high,
        "low": low,
        "close": close,
        "base_volume": volume,
        "trade_count": trade_count,
    }


class TimestampTests(unittest.TestCase):
    def test_utc_epoch_accepts_explicit_utc(self):
        self.assertEqual(utc_epoch("1970-01-01T00:00:00Z"), 0)

    def test_utc_epoch_rejects_naive_timestamp(self):
        with self.assertRaises(ValueError):
            utc_epoch("2026-11-06T00:00:00")


class CandleValidationTests(unittest.TestCase):
    def test_complete_continuous_window(self):
        report = validate_candles([candle(0), candle(3600)], 3600, 0, 7200)
        self.assertEqual(report["records_in_window"], 2)
        self.assertEqual(report["coverage_pct_if_continuous"], 100.0)
        self.assertEqual(report["duplicate_timestamps"], 0)
        self.assertTrue(report["strictly_ordered"])
        self.assertEqual(report["gaps"], [])
        self.assertEqual(report["ohlc_or_volume_violations"], [])
        self.assertEqual(report["trade_count_records"], 2)

    def test_reports_gap_without_classifying_it_as_data_loss(self):
        report = validate_candles([candle(0), candle(7200)], 3600, 0, 10800)
        self.assertEqual(report["coverage_pct_if_continuous"], 66.6667)
        self.assertEqual(report["gaps"][0]["missing_intervals"], 1)
        self.assertIn("no se clasifica automáticamente como pérdida", report["gap_interpretation"])

    def test_reports_duplicate_timestamp(self):
        report = validate_candles([candle(0), candle(0)], 3600, 0, 7200)
        self.assertEqual(report["duplicate_timestamps"], 1)
        self.assertFalse(report["strictly_ordered"])

    def test_reports_ohlc_and_negative_volume_violations(self):
        report = validate_candles(
            [candle(0, high="101", close="105", volume="-1")], 3600, 0, 3600
        )
        self.assertEqual(
            {item["type"] for item in report["ohlc_or_volume_violations"]},
            {"ohlc", "negative_base_volume"},
        )

    def test_reports_misaligned_outside_and_zero_volume(self):
        report = validate_candles(
            [candle(1800, volume="0"), candle(7200)], 3600, 0, 3600
        )
        self.assertEqual(report["records_outside_window"], 1)
        self.assertEqual(report["misaligned_timestamps"], [1800])
        self.assertEqual(report["zero_base_volume_records"], 1)

    def test_empty_response_is_a_critical_validation_failure(self):
        report = validate_candles([], 3600, 0, 7200)
        self.assertEqual(report["records_received"], 0)
        self.assertFalse(report["validation_passed"])
        self.assertIn("empty_response", report["critical_violations"])

    def test_unordered_timestamps_are_sorted_only_for_gap_diagnostics(self):
        report = validate_candles([candle(7200), candle(0)], 3600, 0, 10800)
        self.assertFalse(report["strictly_ordered"])
        self.assertEqual(report["gaps"], [{
            "from": 0, "to": 7200, "missing_intervals": 1,
        }])
        self.assertIn("timestamps_not_strictly_ordered", report["critical_violations"])

    def test_unordered_complete_sequence_has_no_false_gap(self):
        report = validate_candles(
            [candle(7200), candle(0), candle(3600)], 3600, 0, 10800
        )
        self.assertFalse(report["strictly_ordered"])
        self.assertEqual(report["gaps"], [])

    def test_validation_failure_is_reported_for_critical_quality_errors(self):
        report = validate_candles(
            [candle(0), candle(0, open_price="100")], 3600, 0, 7200
        )
        self.assertFalse(report["validation_passed"])
        self.assertIn("duplicate_timestamps", report["critical_violations"])


class MetadataValidationTests(unittest.TestCase):
    def test_binance_requires_both_expected_markets_in_trading_state(self):
        selected = [
            {"symbol": "BTCUSDT", "status": "TRADING"},
            {"symbol": "ETHUSDT", "status": "BREAK"},
        ]
        issues = metadata_validation_issues("binance", selected)
        self.assertEqual(issues, ["market_not_trading:ETHUSDT"])

    def test_kraken_accepts_expected_pair_aliases_and_online_status(self):
        selected = [
            {"altname": "XBTUSD", "wsname": "XBT/USD", "status": "online"},
            {"altname": "ETHUSD", "wsname": "ETH/USD", "status": "online"},
        ]
        self.assertEqual(metadata_validation_issues("kraken", selected), [])

    def test_kraken_reports_missing_expected_pair(self):
        selected = [{"altname": "XBTUSD", "wsname": "XBT/USD", "status": "online"}]
        self.assertEqual(
            metadata_validation_issues("kraken", selected),
            ["missing_market:ETHUSD"],
        )


class ProviderMappingTests(unittest.TestCase):
    def test_binance_maps_base_quote_and_trade_fields(self):
        payload = [[
            0, "100", "110", "90", "105", "2", 3599999, "200",
            17, "0.7", "70", "0"
        ]]
        with tempfile.TemporaryDirectory() as directory:
            with patch(
                "scripts.research.download_validate_market_data.request_json",
                return_value=(payload, b"[]", {"url": "https://example.test", "http_status": 200}),
            ):
                rows, _, _ = fetch_binance("BTC", "BTCUSDT", "1h", 0, 3600, Path(directory))
        row = rows[0]
        self.assertEqual(row["base_volume"], "2")
        self.assertEqual(row["base_volume_unit"], "BTC")
        self.assertEqual(row["quote_volume"], "200")
        self.assertEqual(row["quote_volume_unit"], "USDT")
        self.assertEqual(row["trade_count"], 17)
        self.assertEqual(row["taker_buy_base_volume"], "0.7")
        self.assertEqual(row["taker_buy_quote_volume"], "70")

    def test_kraken_maps_vwap_volume_and_trade_count(self):
        payload = {"error": [], "result": {"XXBTZUSD": [
            [0, "100", "110", "90", "105", "103", "3.5", 12]
        ], "last": 3600}}
        with tempfile.TemporaryDirectory() as directory:
            with patch(
                "scripts.research.download_validate_market_data.request_json",
                return_value=(payload, b"{}", {"url": "https://example.test", "http_status": 200}),
            ):
                rows, _, _, _ = fetch_kraken("BTC", "XBTUSD", 60, 0, 3600, Path(directory))
        row = rows[0]
        self.assertEqual(row["base_volume"], "3.5")
        self.assertEqual(row["base_volume_unit"], "XBT")
        self.assertEqual(row["vwap"], "103")
        self.assertEqual(row["trade_count"], 12)
        self.assertEqual(row["quote_volume"], "")

    def test_binance_metadata_selects_only_requested_markets(self):
        payload = {"symbols": [
            {"symbol": "BTCUSDT", "status": "TRADING", "baseAsset": "BTC",
             "quoteAsset": "USDT", "filters": [{"filterType": "LOT_SIZE"}]},
            {"symbol": "OTHER", "status": "TRADING"},
        ]}
        with tempfile.TemporaryDirectory() as directory:
            with patch(
                "scripts.research.download_validate_market_data.request_json",
                return_value=(payload, b"{}", {"url": "https://example.test", "http_status": 200}),
            ):
                record, selected = fetch_binance_metadata(Path(directory))
        self.assertEqual(record["raw"]["sha256"], __import__("hashlib").sha256(b"{}").hexdigest())
        self.assertEqual([item["symbol"] for item in selected], ["BTCUSDT"])
        self.assertEqual(selected[0]["status"], "TRADING")

    def test_kraken_metadata_resolves_pair_aliases(self):
        payload = {"error": [], "result": {
            "XXBTZUSD": {"altname": "XBTUSD", "wsname": "XBT/USD",
                         "base": "XXBT", "quote": "ZUSD", "status": "online"},
            "OTHER": {"altname": "OTHER", "wsname": "OTHER/PAIR"},
        }}
        with tempfile.TemporaryDirectory() as directory:
            with patch(
                "scripts.research.download_validate_market_data.request_json",
                return_value=(payload, b"{}", {"url": "https://example.test", "http_status": 200}),
            ):
                record, selected = fetch_kraken_metadata(Path(directory))
        self.assertEqual(record["provider"], "kraken")
        self.assertEqual([item["result_key"] for item in selected], ["XXBTZUSD"])
        self.assertEqual(selected[0]["status"], "online")


if __name__ == "__main__":
    unittest.main()
