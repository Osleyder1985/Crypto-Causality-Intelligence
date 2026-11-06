import json
import unittest
from pathlib import Path
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from scripts.validation.asset_representation_contracts import (
    validate_asset_representation,
    validate_asset_representation_catalog,
)

from scripts.validation.market_contracts import (
    map_binance_instrument_metadata,
    map_kraken_instrument_metadata,
    parse_binance_kline,
    parse_kraken_ohlc_row,
    resolve_asset_identity,
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

    def test_normalized_timestamps_are_utc_aware(self):
        result = parse_binance_kline(self.row)
        self.assertEqual(result["open_time"].tzinfo, timezone.utc)

    def test_supports_explicit_microsecond_resolution(self):
        row = list(self.row)
        row[0] = 1_000_000
        row[6] = 59_999_999
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


    def test_binance_keeps_market_lot_separate_and_unknown_filters(self):
        symbol = {
            "symbol": "BTCUSDT", "status": "TRADING",
            "baseAsset": "BTC", "quoteAsset": "USDT",
            "filters": [
                {"filterType": "LOT_SIZE", "minQty": "0.001",
                 "maxQty": "10", "stepSize": "0.001"},
                {"filterType": "MARKET_LOT_SIZE", "minQty": "0.01",
                 "maxQty": "5", "stepSize": "0.01"},
                {"filterType": "ICEBERG_PARTS", "limit": 10},
                {"filterType": "PRICE_FILTER", "minPrice": "0",
                 "maxPrice": "0", "tickSize": "0.10"},
            ],
            "futureProviderField": {"revision": "synthetic-v2"},
        }
        result = map_binance_instrument_metadata(symbol)
        self.assertEqual(result["quantity_step"], Decimal("0.001"))
        self.assertEqual(result["market_quantity_step"], Decimal("0.01"))
        self.assertEqual(result["price_tick"], Decimal("0.10"))
        self.assertEqual(result["trading_rules"][2]["parameters"]["limit"], 10)
        self.assertEqual(result["provider_extensions"]["unknown_filter_types"],
                         ["ICEBERG_PARTS"])
        self.assertEqual(result["provider_extensions"]["futureProviderField"],
                         {"revision": "synthetic-v2"})

    def test_binance_rejects_malformed_or_duplicate_filters(self):
        with self.assertRaises(ValueError):
            map_binance_instrument_metadata({
                "symbol": "BTCUSDT", "filters": [{"minQty": "1"}]
            })
        with self.assertRaises(ValueError):
            map_binance_instrument_metadata({
                "symbol": "BTCUSDT", "filters": [
                    {"filterType": "LOT_SIZE", "stepSize": "1"},
                    {"filterType": "LOT_SIZE", "stepSize": "2"},
                ]
            })

    def test_binance_missing_optional_filters_remain_null(self):
        result = map_binance_instrument_metadata({
            "symbol": "BTCUSDT", "baseAsset": "BTC", "quoteAsset": "USDT",
            "filters": [],
        })
        self.assertIsNone(result["price_tick"])
        self.assertIsNone(result["quantity_step"])
        self.assertIsNone(result["market_quantity_step"])
        self.assertEqual(result["trading_rules"], [])

    def test_kraken_preserves_unrecognized_fields_and_rule_parameters(self):
        pair = {
            "altname": "XBTUSD", "wsname": "XBT/USD", "base": "XXBT",
            "quote": "ZUSD", "status": "online", "tick_size": "0.1",
            "pair_decimals": 1, "lot_decimals": 8, "ordermin": "0.0001",
            "costmin": "0.5", "future_field": {"mode": "synthetic"},
        }
        result = map_kraken_instrument_metadata("XXBTZUSD", pair)
        self.assertEqual(result["provider_extensions"]["future_field"],
                         {"mode": "synthetic"})
        self.assertEqual(result["trading_rules"][0]["parameters"]["tick_size"],
                         "0.1")
        self.assertIsNone(result["quantity_step"])

    def test_kraken_missing_optional_fields_are_not_invented(self):
        result = map_kraken_instrument_metadata(
            "UNKNOWNPAIR", {"base": "XAAA", "quote": "ZBBB"}
        )
        self.assertEqual(result["source_instrument_id"], "UNKNOWNPAIR")
        self.assertIsNone(result["price_tick"])
        self.assertIsNone(result["min_quantity"])
        self.assertIsNone(result["min_notional"])
        self.assertEqual(result["provider_extensions"], {})


class AssetIdentityResolutionTests(unittest.TestCase):
    def test_ticker_similarity_never_creates_implicit_equivalence(self):
        for namespace, code in (
            ("binance_spot", "BTC"),
            ("kraken_spot", "XBT"),
            ("kraken_spot", "XXBT"),
        ):
            result = resolve_asset_identity(namespace, code, [])
            self.assertEqual(result["resolution_status"], "unresolved")
            self.assertIsNone(result["canonical_asset_key"])

    def test_exact_approved_mapping_resolves_with_evidence(self):
        mappings = [{
            "namespace": "kraken_spot",
            "native_code": "XXBT",
            "network": None,
            "canonical_asset_key": "bitcoin",
            "status": "accepted",
            "evidence_reference": "evidence:asset-review-001",
        }]
        result = resolve_asset_identity("kraken_spot", "XXBT", mappings)
        self.assertEqual(result["resolution_status"], "resolved")
        self.assertEqual(result["canonical_asset_key"], "bitcoin")
        self.assertEqual(result["evidence_reference"], "evidence:asset-review-001")

    def test_namespace_and_network_are_exact_scopes(self):
        mappings = [{
            "namespace": "kraken_spot", "native_code": "XBT",
            "network": None, "canonical_asset_key": "bitcoin",
            "status": "accepted", "evidence_reference": "evidence:001",
        }]
        self.assertEqual(
            resolve_asset_identity("binance_spot", "XBT", mappings)["resolution_status"],
            "unresolved",
        )
        self.assertEqual(
            resolve_asset_identity(
                "kraken_spot", "XBT", mappings, network="bitcoin"
            )["resolution_status"],
            "unresolved",
        )

    def test_pending_mapping_does_not_resolve_asset(self):
        mappings = [{
            "namespace": "kraken_spot", "native_code": "XBT",
            "network": None, "canonical_asset_key": "bitcoin",
            "status": "pending_review", "evidence_reference": None,
        }]
        result = resolve_asset_identity("kraken_spot", "XBT", mappings)
        self.assertEqual(result["resolution_status"], "pending_review")
        self.assertIsNone(result["canonical_asset_key"])

    def test_conflicting_accepted_mappings_are_rejected(self):
        mappings = [
            {"namespace": "provider", "native_code": "ABC", "network": None,
             "canonical_asset_key": "asset-a", "status": "accepted",
             "evidence_reference": "evidence:a"},
            {"namespace": "provider", "native_code": "ABC", "network": None,
             "canonical_asset_key": "asset-b", "status": "accepted",
             "evidence_reference": "evidence:b"},
        ]
        with self.assertRaises(ValueError):
            resolve_asset_identity("provider", "ABC", mappings)

    def test_ambiguous_review_blocks_otherwise_accepted_mapping(self):
        mappings = [
            {"namespace": "provider", "native_code": "ABC", "network": None,
             "canonical_asset_key": "asset-a", "status": "accepted",
             "evidence_reference": "evidence:a"},
            {"namespace": "provider", "native_code": "ABC", "network": None,
             "canonical_asset_key": "asset-b", "status": "ambiguous",
             "evidence_reference": "evidence:conflict"},
        ]
        result = resolve_asset_identity("provider", "ABC", mappings)
        self.assertEqual(result["resolution_status"], "ambiguous")
        self.assertIsNone(result["canonical_asset_key"])

    def test_accepted_mapping_requires_evidence(self):
        mappings = [{
            "namespace": "provider", "native_code": "ABC", "network": None,
            "canonical_asset_key": "asset-a", "status": "accepted",
        }]
        with self.assertRaises(ValueError):
            resolve_asset_identity("provider", "ABC", mappings)


class BitemporalAssetIdentityResolutionTests(unittest.TestCase):
    def setUp(self):
        self.mappings = [{
            "namespace": "provider",
            "native_code": "ABC",
            "network": None,
            "canonical_asset_key": "asset-old",
            "status": "accepted",
            "evidence_reference": "evidence:old",
            "valid_from": "2020-01-01T00:00:00Z",
            "valid_until": "2024-01-01T00:00:00Z",
            "recorded_at": "2020-01-02T00:00:00Z",
        }, {
            "namespace": "provider",
            "native_code": "ABC",
            "network": None,
            "canonical_asset_key": "asset-new",
            "status": "accepted",
            "evidence_reference": "evidence:new",
            "valid_from": "2024-01-01T00:00:00Z",
            "valid_until": None,
            "recorded_at": "2024-01-03T00:00:00Z",
        }]

    def test_valid_time_selects_historical_mapping(self):
        result = resolve_asset_identity(
            "provider", "ABC", self.mappings,
            valid_at="2022-06-01T00:00:00Z",
            known_at="2023-01-01T00:00:00Z",
        )
        self.assertEqual(result["canonical_asset_key"], "asset-old")

    def test_new_mapping_does_not_rewrite_what_was_previously_known(self):
        result = resolve_asset_identity(
            "provider", "ABC", self.mappings,
            valid_at="2024-06-01T00:00:00Z",
            known_at="2024-01-02T00:00:00Z",
        )
        self.assertEqual(result["resolution_status"], "unresolved")
        self.assertIsNone(result["canonical_asset_key"])

    def test_later_recorded_correction_is_used_only_after_known_at(self):
        correction = {
            "namespace": "provider",
            "native_code": "ABC",
            "network": None,
            "canonical_asset_key": "asset-corrected",
            "status": "accepted",
            "evidence_reference": "evidence:correction",
            "valid_from": "2020-01-01T00:00:00Z",
            "valid_until": "2024-01-01T00:00:00Z",
            "recorded_at": "2025-01-01T00:00:00Z",
        }
        mappings = [self.mappings[0], correction]
        before_correction = resolve_asset_identity(
            "provider", "ABC", mappings,
            valid_at="2022-06-01T00:00:00Z",
            known_at="2024-12-31T23:59:59Z",
        )
        after_correction = resolve_asset_identity(
            "provider", "ABC", mappings,
            valid_at="2022-06-01T00:00:00Z",
            known_at="2025-01-02T00:00:00Z",
        )
        self.assertEqual(before_correction["canonical_asset_key"], "asset-old")
        self.assertEqual(after_correction["canonical_asset_key"], "asset-corrected")

    def test_validity_interval_is_half_open(self):
        result = resolve_asset_identity(
            "provider", "ABC", self.mappings,
            valid_at="2024-01-01T00:00:00Z",
            known_at="2025-01-01T00:00:00Z",
        )
        self.assertEqual(result["canonical_asset_key"], "asset-new")

    def test_temporal_resolution_requires_both_query_clocks_and_aware_timestamps(self):
        with self.assertRaises(ValueError):
            resolve_asset_identity(
                "provider", "ABC", self.mappings,
                valid_at="2024-06-01T00:00:00Z",
            )
        with self.assertRaises(ValueError):
            resolve_asset_identity(
                "provider", "ABC", self.mappings,
                valid_at="2024-06-01T00:00:00",
                known_at="2025-01-01T00:00:00Z",
            )

    def test_conflicting_latest_temporal_reviews_are_ambiguous(self):
        mappings = [
            {
                "namespace": "provider",
                "native_code": "ABC",
                "network": None,
                "canonical_asset_key": "asset-one",
                "status": "accepted",
                "evidence_reference": "evidence:one",
                "valid_from": "2020-01-01T00:00:00Z",
                "valid_until": None,
                "recorded_at": "2025-01-01T00:00:00Z",
            },
            {
                "namespace": "provider",
                "native_code": "ABC",
                "network": None,
                "canonical_asset_key": "asset-two",
                "status": "accepted",
                "evidence_reference": "evidence:two",
                "valid_from": "2020-01-01T00:00:00Z",
                "valid_until": None,
                "recorded_at": "2025-01-01T00:00:00Z",
            },
        ]
        result = resolve_asset_identity(
            "provider", "ABC", mappings,
            valid_at="2024-06-01T00:00:00Z",
            known_at="2025-01-02T00:00:00Z",
        )
        self.assertEqual(result["resolution_status"], "ambiguous")
        self.assertIsNone(result["canonical_asset_key"])
        self.assertIsNone(result["evidence_reference"])

    def test_mapping_without_documented_valid_from_is_not_resolved_temporally(self):
        mapping = dict(self.mappings[1])
        mapping["valid_from"] = None
        result = resolve_asset_identity(
            "provider", "ABC", [mapping],
            valid_at="2024-06-01T00:00:00Z",
            known_at="2025-01-01T00:00:00Z",
        )
        self.assertEqual(result["resolution_status"], "unresolved")


class InitialAssetCatalogFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture_path = (
            Path(__file__).parent
            / "fixtures"
            / "asset_identity"
            / "initial_asset_catalog.json"
        )
        cls.fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

    def test_all_initial_external_mappings_remain_pending(self):
        self.assertEqual(self.fixture["status"], "synthetic_test_fixture")
        self.assertEqual(len(self.fixture["mappings"]), 5)
        for mapping in self.fixture["mappings"]:
            with self.subTest(
                namespace=mapping["namespace"],
                native_code=mapping["native_code"],
            ):
                self.assertEqual(mapping["status"], "pending_review")
                self.assertIsNone(mapping["evidence_reference"])
                result = resolve_asset_identity(
                    mapping["namespace"],
                    mapping["native_code"],
                    [mapping],
                    network=mapping["network"],
                )
                self.assertEqual(result["resolution_status"], "pending_review")
                self.assertIsNone(result["canonical_asset_key"])

    def test_usd_and_tether_usd_are_distinct_canonical_entities(self):
        assets = {
            item["canonical_asset_key"]: item
            for item in self.fixture["canonical_assets"]
        }
        self.assertNotEqual(assets["usd"]["canonical_asset_key"],
                            assets["tether_usd"]["canonical_asset_key"])
        self.assertEqual(assets["usd"]["asset_type"], "fiat")
        self.assertEqual(assets["tether_usd"]["asset_type"], "stablecoin")

    def test_fixture_contains_no_accepted_external_mapping(self):
        self.assertFalse(any(
            mapping["status"] == "accepted"
            for mapping in self.fixture["mappings"]
        ))




class AssetRepresentationFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture_path = (
            Path(__file__).parent
            / "fixtures"
            / "asset_identity"
            / "asset_representations.json"
        )
        cls.fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

    def test_synthetic_catalog_is_structurally_valid(self):
        result = validate_asset_representation_catalog(self.fixture)
        self.assertEqual(result["assets_count"], 5)
        self.assertEqual(result["networks_count"], 3)
        self.assertEqual(result["representations_count"], 6)
        self.assertEqual(result["relationships_count"], 1)

    def test_one_asset_can_have_representations_on_multiple_networks(self):
        result = validate_asset_representation_catalog(self.fixture)
        tether = [
            item for item in result["representations"]
            if item["asset_key"] == "tether_usd_synthetic"
        ]
        self.assertEqual(len(tether), 2)
        self.assertEqual(
            {item["network_key"] for item in tether},
            {"ethereum_mainnet_synthetic", "tron_mainnet_synthetic"},
        )

    def test_native_representation_has_no_contract(self):
        bitcoin = next(
            item for item in self.fixture["representations"]
            if item["representation_key"] == "bitcoin_native"
        )
        result = validate_asset_representation(bitcoin)
        self.assertEqual(result["representation_kind"], "native")
        self.assertIsNone(result["contract_address"])
        self.assertEqual(result["native_asset_key"], "BTC_NATIVE_SYNTHETIC")

    def test_native_representation_rejects_contract_address(self):
        item = dict(self.fixture["representations"][0])
        item["contract_address"] = "0xSYNTHETIC_CONTRACT"
        with self.assertRaises(ValueError):
            validate_asset_representation(item)

    def test_token_contract_requires_contract_and_rejects_native_key(self):
        item = dict(self.fixture["representations"][1])
        item["contract_address"] = None
        with self.assertRaises(ValueError):
            validate_asset_representation(item)
        item["contract_address"] = "0xSYNTHETIC_CONTRACT"
        item["native_asset_key"] = "BTC"
        with self.assertRaises(ValueError):
            validate_asset_representation(item)

    def test_same_ticker_does_not_merge_distinct_contract_assets(self):
        result = validate_asset_representation_catalog(self.fixture)
        abc = [
            item for item in result["representations"]
            if item["representation_key"].startswith("abc_")
        ]
        self.assertEqual(len(abc), 2)
        self.assertEqual(
            {item["asset_key"] for item in abc},
            {"token_abc_alpha", "token_abc_beta"},
        )
        self.assertEqual(len({item["contract_address"] for item in abc}), 2)

    def test_duplicate_contract_on_same_network_is_rejected(self):
        catalog = json.loads(json.dumps(self.fixture))
        duplicate = dict(catalog["representations"][-1])
        duplicate["representation_key"] = "abc_beta_duplicate"
        duplicate["asset_key"] = "token_abc_alpha"
        duplicate["contract_address"] = catalog["representations"][-2]["contract_address"]
        catalog["representations"].append(duplicate)
        with self.assertRaises(ValueError):
            validate_asset_representation_catalog(catalog)

    def test_wrapped_asset_remains_distinct_from_underlying_asset(self):
        result = validate_asset_representation_catalog(self.fixture)
        assets = {item["asset_key"] for item in self.fixture["assets"]}
        self.assertIn("bitcoin", assets)
        self.assertIn("wbtc_synthetic", assets)
        self.assertNotEqual("bitcoin", "wbtc_synthetic")
        self.assertEqual(
            self.fixture["relationships"][0]["relationship_type"],
            "wrapped_representation_of",
        )
        self.assertEqual(result["relationships_count"], 1)

    def test_unknown_asset_or_network_reference_is_rejected(self):
        catalog = json.loads(json.dumps(self.fixture))
        catalog["representations"][0]["network_key"] = "unknown_network"
        with self.assertRaises(ValueError):
            validate_asset_representation_catalog(catalog)
        catalog = json.loads(json.dumps(self.fixture))
        catalog["representations"][0]["asset_key"] = "unknown_asset"
        with self.assertRaises(ValueError):
            validate_asset_representation_catalog(catalog)

    def test_relationship_cannot_be_self_referential_or_unsupported(self):
        catalog = json.loads(json.dumps(self.fixture))
        catalog["relationships"][0]["object_asset_key"] = "wbtc_synthetic"
        with self.assertRaises(ValueError):
            validate_asset_representation_catalog(catalog)
        catalog = json.loads(json.dumps(self.fixture))
        catalog["relationships"][0]["relationship_type"] = "same_as"
        with self.assertRaises(ValueError):
            validate_asset_representation_catalog(catalog)

    def test_invalid_or_timezone_naive_validity_interval_is_rejected(self):
        item = dict(self.fixture["representations"][1])
        item["valid_until"] = "2019-01-01T00:00:00Z"
        with self.assertRaises(ValueError):
            validate_asset_representation(item)
        item["valid_from"] = "2020-01-01T00:00:00"
        item["valid_until"] = None
        with self.assertRaises(ValueError):
            validate_asset_representation(item)

    def test_contract_address_is_preserved_without_global_normalization(self):
        item = dict(self.fixture["representations"][1])
        item["contract_address"] = "0xAbCd_SYNTHETIC"
        result = validate_asset_representation(item)
        self.assertEqual(result["contract_address"], "0xAbCd_SYNTHETIC")


if __name__ == "__main__":
    unittest.main()
