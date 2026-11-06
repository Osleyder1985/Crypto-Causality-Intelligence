import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from scripts.validation.market_contracts import (
    map_binance_instrument_metadata,
    map_kraken_instrument_metadata,
    parse_binance_kline,
    parse_kraken_ohlc_row,
)


class BinanceKlineContractTests(unittest.TestCase):
    def setUp(self):
        self.row = [
            1_000, "100.0100", "110.0000", "90.0000", "105.5000",
            "2.2500", 59_999, "236.5000", 17, "0.7500", "78.7500", "0"
        ]

    def test_maps_exact_decimals_and_explicit_units(self):
        result = parse_binance_kline(self.row)
        self.assertEqual(result["open"], Decimal("100.0100"))
        self.assertEqual(result["volume_base"], Decimal("2.2500"))
        self.assertEqual(result["volume_quote"], Decimal("236.5000"))
        self.assertEqual(result["trade_count"], 17)
        self.assertEqual(result["taker_buy_base_volume"], Decimal("0.7500"))
        self.assertEqual(result["taker_buy_quote_volume"], Decimal("78.7500"))

    def test_converts_inclusive_close_to_exclusive_millisecond(self):
        result = parse_binance_kline(self.row)
        self.assertEqual(
            result["close_time_exclusive"],
            datetime.fromtimestamp(60, tz=timezone.utc),
        )

    def test_rest_does_not_invent_finality(self):
        self.assertIsNone(parse_binance_kline(self.row)["is_final"])

    def test_supports_explicit_microsecond_resolution(self):
        row = list(self.row)
        row[0] = 1_000_000
        row[6] = 59_999_000
        result = parse_binance_kline(row, timestamp_unit="us")
        self.assertEqual(result["open_time"], datetime.fromtimestamp(1, tz=timezone.utc))
        self.assertEqual(
            result["close_time_exclusive"],
            datetime.fromtimestamp(60, tz=timezone.utc),
        )

    def test_rejects_wrong_tuple_length_and_bad_timestamp_unit(self):
        with self.assertRaises(ValueError):
            parse_binance_kline(self.row[:-1])
        with self.assertRaises(ValueError):
            parse_binance_kline(self.row, timestamp_unit="s")

    def test_rejects_non_finite_decimal(self):
        row = list(self.row)
        row[1] = "NaN"
        with self.assertRaises(ValueError):
            parse_binance_kline(row)


class KrakenOhlcContractTests(unittest.TestCase):
    def setUp(self):
        self.row = [1_700_000_000, "100.00", "110.00", "90.00", "105.00",
                    "103.25", "3.5000", 12]

    def test_maps_vwap_base_volume_and_trade_count(self):
        result = parse_kraken_ohlc_row(
            self.row, interval_minutes=60, is_last_row=False
        )
        self.assertEqual(result["vwap"], Decimal("103.25"))
        self.assertEqual(result["volume_base"], Decimal("3.5000"))
        self.assertIsNone(result["volume_quote"])
        self.assertEqual(result["trade_count"], 12)

    def test_calculates_exclusive_close_from_interval(self):
        result = parse_kraken_ohlc_row(
            self.row, interval_minutes=60, is_last_row=False
        )
        self.assertEqual(
            result["close_time_exclusive"],
            result["open_time"] + timedelta(hours=1),
        )

    def test_only_last_returned_row_is_provisional(self):
        final = parse_kraken_ohlc_row(
            self.row, interval_minutes=60, is_last_row=False
        )
        provisional = parse_kraken_ohlc_row(
            self.row, interval_minutes=60, is_last_row=True
        )
        self.assertTrue(final["is_final"])
        self.assertFalse(provisional["is_final"])

    def test_rejects_invalid_interval_and_row_length(self):
        with self.assertRaises(ValueError):
            parse_kraken_ohlc_row(self.row, interval_minutes=0, is_last_row=True)
        with self.assertRaises(ValueError):
            parse_kraken_ohlc_row(self.row[:-1], interval_minutes=60, is_last_row=True)


class InstrumentMetadataContractTests(unittest.TestCase):
    def test_binance_maps_filters_without_conflating_precision(self):
        symbol = {
            "symbol": "BTCUSDT", "status": "TRADING", "baseAsset": "BTC",
            "quoteAsset": "USDT", "baseAssetPrecision": 8, "quoteAssetPrecision": 8,
            "filters": [
                {"filterType": "PRICE_FILTER", "minPrice": "0.01000000",
                 "maxPrice": "1000000.00000000", "tickSize": "0.01000000"},
                {"filterType": "LOT_SIZE", "minQty": "0.00001000",
                 "maxQty": "9000.00000000", "stepSize": "0.00001000"},
                {"filterType": "NOTIONAL", "minNotional": "5.00",
                 "maxNotional": "1000000.00", "applyMinToMarket": True,
                 "applyMaxToMarket": False, "avgPriceMins": 5},
            ],
        }
        result = map_binance_instrument_metadata(symbol)
        self.assertEqual(result["price_tick"], Decimal("0.01000000"))
        self.assertEqual(result["quantity_step"], Decimal("0.00001000"))
        self.assertEqual(result["min_notional"], Decimal("5.00"))
        self.assertEqual(result["max_notional"], Decimal("1000000.00"))
        self.assertEqual(result["provider_extensions"]["baseAssetPrecision"], 8)
        self.assertNotIn("price_precision", result)

    def test_kraken_preserves_aliases_and_does_not_infer_quantity_step(self):
        pair = {
            "altname": "XBTUSD", "wsname": "XBT/USD", "base": "XXBT",
            "quote": "ZUSD", "status": "online", "tick_size": "0.1",
            "pair_decimals": 1, "lot_decimals": 8, "ordermin": "0.0001",
            "costmin": "0.5", "lot_multiplier": 1,
        }
        result = map_kraken_instrument_metadata("XXBTZUSD", pair)
        self.assertEqual(result["source_instrument_id"], "XXBTZUSD")
        self.assertEqual(result["native_aliases"]["wsname"], "XBT/USD")
        self.assertEqual(result["price_tick"], Decimal("0.1"))
        self.assertEqual(result["quantity_precision"], 8)
        self.assertIsNone(result["quantity_step"])
        self.assertEqual(result["min_notional"], Decimal("0.5"))


if __name__ == "__main__":
    unittest.main()
