from __future__ import annotations

import unittest
from datetime import datetime, timezone
from decimal import Decimal

from scripts.persistence.market_writer import (
    StoragePermissionDenied, canonicalize_rows, payload_digest,
)

BASE = {
    "open_time_ms": 1794009600000,
    "open_time_utc": datetime.fromtimestamp(1794009600, tz=timezone.utc),
    "open": "100", "high": "110", "low": "90", "close": "105",
    "volume_base": "2", "quote_volume": "200", "close_time_ms": 1794013199999,
    "trade_count": 10, "taker_buy_base_volume": "1",
    "taker_buy_quote_volume": "100", "source_ignore_field": "0",
}


class TransactionalWriterValidationTests(unittest.TestCase):
    def test_canonicalizes_decimal_and_utc(self):
        row = canonicalize_rows([BASE])[0]
        self.assertEqual(row["open"], Decimal("100"))
        self.assertEqual(row["open_time_utc"].tzinfo, timezone.utc)

    def test_rejects_timestamp_mismatch(self):
        bad = dict(BASE, open_time_ms=BASE["open_time_ms"] + 3600000)
        with self.assertRaisesRegex(ValueError, "disagree"):
            canonicalize_rows([bad])

    def test_rejects_duplicate_timestamp(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            canonicalize_rows([BASE, BASE])

    def test_rejects_invalid_ohlc(self):
        bad = dict(BASE, high="99")
        with self.assertRaisesRegex(ValueError, "OHLC"):
            canonicalize_rows([bad])

    def test_digest_is_stable(self):
        rows = canonicalize_rows([BASE])
        self.assertEqual(
            payload_digest("binance", "SPOT", "BTCUSDT", "1h", rows),
            payload_digest("binance", "SPOT", "BTCUSDT", "1h", rows),
        )

    def test_empty_batch_rejected(self):
        with self.assertRaisesRegex(ValueError, "at least one"):
            canonicalize_rows([])


if __name__ == "__main__":
    unittest.main()
