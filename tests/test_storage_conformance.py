import sys
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "validation"))

import storage_conformance as storage


def valid_row():
    return {
        "cohort_window": "decline_2025_10_06_2025_11_21",
        "provider": "binance", "market_type": "SPOT", "symbol": "BTCUSDT", "interval": "1h",
        "open_time_ms": 0, "open_time_utc": "1970-01-01T00:00:00Z",
        "open": "100.00000000", "high": "110.00000000", "low": "95.00000000",
        "close": "105.00000000", "volume_base": "12.50000000", "close_time_ms": 3599999,
        "quote_volume": "1300.00000000", "trade_count": 42,
        "taker_buy_base_volume": "6.00000000", "taker_buy_quote_volume": "620.00000000",
        "source_ignore_field": "0",
    }


class StorageRowContractTests(unittest.TestCase):
    def test_valid_row_preserves_exact_decimal_and_utc(self):
        row = storage.validate_row(valid_row())
        self.assertEqual(row["open"], Decimal("100.000000000000000000"))
        self.assertEqual(row["open_time_utc"], datetime(1970, 1, 1, tzinfo=timezone.utc))

    def test_timestamp_epoch_mismatch_is_rejected(self):
        row = valid_row()
        row["open_time_ms"] = 3600000
        with self.assertRaisesRegex(ValueError, "disagree"):
            storage.validate_row(row)

    def test_naive_timestamp_is_rejected(self):
        row = valid_row()
        row["open_time_utc"] = "1970-01-01T00:00:00"
        with self.assertRaises(ValueError):
            storage.validate_row(row)

    def test_float_market_identity_is_rejected(self):
        row = valid_row()
        row["market_type"] = "FUTURES"
        with self.assertRaisesRegex(ValueError, "market identity"):
            storage.validate_row(row)

    def test_incoherent_ohlc_is_rejected(self):
        row = valid_row()
        row["high"] = "99"
        with self.assertRaisesRegex(ValueError, "OHLC"):
            storage.validate_row(row)

    def test_negative_volume_is_rejected(self):
        row = valid_row()
        row["volume_base"] = "-0.1"
        with self.assertRaisesRegex(ValueError, "non-negative"):
            storage.validate_row(row)

    def test_taker_volume_cannot_exceed_total(self):
        row = valid_row()
        row["taker_buy_base_volume"] = "13"
        with self.assertRaisesRegex(ValueError, "exceeds"):
            storage.validate_row(row)

    def test_non_integral_decimal_scale_is_rejected(self):
        row = valid_row()
        row["open"] = "1.0000000000000000001"
        with self.assertRaisesRegex(ValueError, "DECIMAL"):
            storage.validate_row(row)

    def test_non_finite_decimal_is_rejected(self):
        row = valid_row()
        row["open"] = "NaN"
        with self.assertRaises(ValueError):
            storage.validate_row(row)

    def test_trade_count_boolean_is_rejected(self):
        row = valid_row()
        row["trade_count"] = True
        with self.assertRaisesRegex(ValueError, "integer"):
            storage.validate_row(row)

    def test_required_field_is_enforced(self):
        row = valid_row()
        del row["quote_volume"]
        with self.assertRaisesRegex(ValueError, "missing required"):
            storage.validate_row(row)

    def test_arrow_schema_uses_decimal_and_utc_timestamp(self):
        row = storage.validate_row(valid_row())
        table = storage.to_arrow([row])
        self.assertEqual(table.schema.field("open").type, storage.DECIMAL)
        self.assertEqual(table.schema.field("open_time_utc").type, storage.pa.timestamp("us", tz="UTC"))


if __name__ == "__main__":
    unittest.main()
