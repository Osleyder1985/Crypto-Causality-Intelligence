import io
import unittest
import zipfile
from datetime import datetime, timezone

from scripts.research.download_binance_btcusdt_klines import checksum_value, parse_zip


def zipped(rows):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("klines.csv", "\n".join(",".join(map(str, row)) for row in rows) + "\n")
    return stream.getvalue()


def start_ms():
    return int(datetime(2026, 10, 6, tzinfo=timezone.utc).timestamp() * 1000)


class KlinesDownloaderTests(unittest.TestCase):
    def row(self, timestamp):
        return [timestamp, "60000", "60100", "59900", "60050", "12.5",
                timestamp + 59999, "750000", 100, "7.5", "450000", "0"]

    def test_parses_ohlcv_and_trade_metadata(self):
        spot_row = self.row(start_ms() * 1000)
        spot_row[6] = (start_ms() + 59999) * 1000 + 999
        rows, member = parse_zip(zipped([spot_row]), "spot", start_ms())
        self.assertEqual(member, "klines.csv")
        self.assertEqual(rows[0]["timestamp_unit"], "microseconds")
        self.assertEqual(rows[0]["open_time_ms"], start_ms())
        self.assertEqual(rows[0]["close_time_ms"], start_ms() + 59999)
        self.assertEqual(rows[0]["close"], "60050")
        self.assertEqual(rows[0]["trade_count"], 100)
        self.assertEqual(rows[0]["taker_buy_quote_volume_usdt"], "450000")

    def test_rejects_bad_ohlc_and_duplicate_timestamps(self):
        bad = self.row(start_ms() * 1000)
        bad[2] = "59950"
        with self.assertRaisesRegex(ValueError, "inconsistent OHLC"):
            parse_zip(zipped([bad]), "spot", start_ms())
        row = self.row(start_ms() * 1000)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            parse_zip(zipped([row, row]), "spot", start_ms())

    def test_usdm_timestamps_remain_milliseconds(self):
        rows, _ = parse_zip(zipped([self.row(start_ms())]), "usd_m", start_ms())
        self.assertEqual(rows[0]["timestamp_unit"], "milliseconds")
        self.assertEqual(rows[0]["open_time_ms"], start_ms())

    def test_rejects_invalid_checksum(self):
        with self.assertRaises(ValueError):
            checksum_value(b"invalid")


if __name__ == "__main__":
    unittest.main()
