import unittest

from scripts.research.fetch_btcusdt_funding_history import (
    _coverage_summary,
    attach_funding_asof,
    fetch_funding_history,
)


def record(timestamp, rate="0.0001"):
    return {
        "symbol": "BTCUSDT",
        "fundingTime": timestamp,
        "fundingRate": rate,
        "markPrice": "50000.0",
        "rateType": "Regular",
    }


class FundingHistoryTests(unittest.TestCase):
    def test_paginates_using_last_timestamp_plus_one_and_deduplicates(self):
        calls = []

        def fetch(params):
            calls.append(params)
            if len(calls) == 1:
                return [record(100), record(200)]
            if len(calls) == 2:
                return [record(201), record(300)]
            return []

        result = fetch_funding_history("BTCUSDT", 100, 300, page_fetcher=fetch, limit=2)
        self.assertEqual([item["funding_time_ms"] for item in result], [100, 200, 201, 300])
        self.assertEqual(calls[1]["startTime"], 201)
        self.assertEqual(calls[0]["endTime"], 300)

    def test_preserves_inclusive_start_and_end(self):
        def fetch(params):
            self.assertEqual(params["startTime"], 100)
            self.assertEqual(params["endTime"], 200)
            return [record(100), record(200)]
        result = fetch_funding_history("BTCUSDT", 100, 200, page_fetcher=fetch)
        self.assertEqual(len(result), 2)

    def test_rejects_out_of_range_wrong_symbol_and_nonfinite_rate(self):
        with self.assertRaisesRegex(ValueError, "outside"):
            fetch_funding_history("BTCUSDT", 100, 200, page_fetcher=lambda p: [record(201)])
        wrong = lambda p: [{**record(100), "symbol": "ETHUSDT"}]
        with self.assertRaisesRegex(ValueError, "unexpected symbol"):
            fetch_funding_history("BTCUSDT", 100, 200, page_fetcher=wrong)
        bad = lambda p: [record(100, "nan")]
        with self.assertRaisesRegex(ValueError, "non-finite"):
            fetch_funding_history("BTCUSDT", 100, 200, page_fetcher=bad)

    def test_rejects_unsorted_pages_and_nonadvancing_pagination(self):
        unsorted = lambda p: [record(200), record(100)]
        with self.assertRaisesRegex(ValueError, "ascending"):
            fetch_funding_history("BTCUSDT", 100, 200, page_fetcher=unsorted)

    def test_asof_alignment_never_uses_future_funding_settlement(self):
        spot = [{"_ts": 0}, {"_ts": 3_600_000}, {"_ts": 7_200_000}]
        funding = [
            {"funding_time_ms": 3_600_000, "funding_rate": 0.001},
            {"funding_time_ms": 10_800_000, "funding_rate": 0.009},
        ]
        aligned = attach_funding_asof(spot, funding)
        self.assertIsNone(aligned[0]["funding_latest_rate_asof"])
        self.assertEqual(aligned[1]["funding_latest_rate_asof"], 0.001)
        self.assertEqual(aligned[2]["funding_latest_rate_asof"], 0.001)
        self.assertEqual(aligned[0]["funding_settlements_available_asof"], 0)

    def test_reports_observed_gaps_without_filling_them(self):
        report = _coverage_summary(
            [{"funding_time_ms": 0}, {"funding_time_ms": 8 * 3_600_000},
             {"funding_time_ms": 16 * 3_600_000}, {"funding_time_ms": 48 * 3_600_000}],
            0, 40 * 3_600_000,
        )
        self.assertEqual(report["settlement_count"], 4)
        self.assertEqual(len(report["gaps_above_1_5x_median"]), 1)
        self.assertEqual(report["gaps_above_1_5x_median"][0]["gap_hours"], 24)


if __name__ == "__main__":
    unittest.main()
