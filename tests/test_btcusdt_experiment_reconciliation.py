from __future__ import annotations

import unittest
from datetime import datetime, timezone
from decimal import Decimal

from scripts.research.reconcile_btcusdt_experiment import (
    calculate_window_metrics, validate_row,
)

T0 = datetime(2026, 11, 7, 0, 0, tzinfo=timezone.utc)
BASE = {
    "cohort_window": "rise_2026_02_05_2026_05_06",
    "provider": "binance", "market_type": "SPOT", "symbol": "BTCUSDT",
    "interval": "1h", "open_time_ms": int(T0.timestamp() * 1000),
    "open_time_utc": T0.isoformat().replace("+00:00", "Z"),
    "open": "100", "high": "110", "low": "99", "close": "110",
    "volume_base": "10", "quote_volume": "1000",
    "taker_buy_base_volume": "6", "taker_buy_quote_volume": "600",
    "close_time_ms": int(T0.timestamp() * 1000) + 3599999,
    "trade_count": 100, "source_ignore_field": "0",
}


class HistoricalExperimentReconciliationTests(unittest.TestCase):
    def test_validates_exact_market_and_hourly_time(self):
        row = validate_row(dict(BASE))
        self.assertEqual(row["open"], Decimal("100"))

    def test_rejects_inconsistent_utc_timestamp(self):
        bad = dict(BASE, open_time_ms=BASE["open_time_ms"] + 3600000,
                   close_time_ms=BASE["close_time_ms"] + 3600000)
        with self.assertRaisesRegex(ValueError, "disagree"):
            validate_row(bad)

    def test_rejects_negative_volume(self):
        with self.assertRaisesRegex(ValueError, "negative volume"):
            validate_row(dict(BASE, volume_base="-1"))

    def test_rejects_taker_volume_above_total(self):
        with self.assertRaisesRegex(ValueError, "taker base volume"):
            validate_row(dict(BASE, taker_buy_base_volume="11"))

    def test_calculates_episode_return_and_flow(self):
        first = validate_row(dict(BASE))
        second = dict(
            BASE,
            open_time_ms=BASE["open_time_ms"] + 3600000,
            open_time_utc=datetime.fromtimestamp(
                T0.timestamp() + 3600, tz=timezone.utc
            ).isoformat().replace("+00:00", "Z"),
            open="110", high="122", low="109", close="121",
            volume_base="10", quote_volume="1100",
            taker_buy_base_volume="4", taker_buy_quote_volume="440",
            close_time_ms=BASE["close_time_ms"] + 3600000,
        )
        second = validate_row(second)
        result = calculate_window_metrics([first, second])
        self.assertEqual(result["candles"], 2)
        self.assertEqual(result["return_pct"], 21.0)
        self.assertEqual(result["aggregate_taker_base_imbalance_pct"], 0.0)
        self.assertEqual(result["trade_count_sum"], 200)


if __name__ == "__main__":
    unittest.main()
