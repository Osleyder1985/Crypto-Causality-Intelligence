from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.research.analyze_btcusdt_event_study_1m import analyze_event, load_cohorts


def candle(ts: int, close: float, *, quote: float = 100.0, taker: float = 60.0) -> dict:
    return {
        "provider": "binance", "market_type": "SPOT", "symbol": "BTCUSDT",
        "interval": "1m", "cohort_window": "cohort_a",
        "open_time_ms": ts, "close_time_ms": ts + 59_999,
        "open": close, "high": close + 1, "low": close - 1, "close": close,
        "quote_volume": quote, "trade_count": 10,
        "taker_buy_quote_volume": taker,
    }


class EventStudyOneMinuteTests(unittest.TestCase):
    def test_event_study_uses_pre_event_reference_and_aggregates_flow(self):
        rows = [candle(i * 60_000, 100 + i) for i in range(10)]
        event = {"event_id": "e1", "cohort_window": "cohort_a", "event_at_utc": "1970-01-01T00:03:00Z"}
        result = analyze_event(rows, event, horizons=(1, 2))
        self.assertAlmostEqual(result["pre_event_reference_close"], 102)
        self.assertAlmostEqual(result["horizons_minutes"]["1"]["post_event_return_pct"], (103 / 102 - 1) * 100)
        self.assertEqual(result["horizons_minutes"]["2"]["post_event_flow"]["candle_count"], 2)
        self.assertAlmostEqual(result["horizons_minutes"]["2"]["post_event_flow"]["taker_buy_share"], 0.6)
        self.assertTrue(result["event_bar_aligned_to_minute"])
        self.assertFalse(result["causal_claim"] if "causal_claim" in result else False)

    def test_non_minute_event_is_flagged(self):
        rows = [candle(i * 60_000, 100 + i) for i in range(10)]
        event = {"event_id": "e2", "cohort_window": "cohort_a", "event_at_utc": "1970-01-01T00:03:30Z"}
        result = analyze_event(rows, event, horizons=(1,))
        self.assertTrue(result["event_bar_overlap_warning"])

    def test_loader_rejects_gap_and_invalid_market(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rows.jsonl"
            rows = [candle(0, 100), candle(120_000, 102)]
            path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "non-contiguous"):
                load_cohorts(path)

    def test_loader_rejects_naive_event_time(self):
        rows = [candle(i * 60_000, 100 + i) for i in range(10)]
        event = {"event_id": "e3", "cohort_window": "cohort_a", "event_at_utc": "1970-01-01T00:03:00"}
        with self.assertRaisesRegex(ValueError, "Timezone-aware"):
            analyze_event(rows, event, horizons=(1,))

    def test_60m_pre_event_window_requires_a_prior_reference_candle(self):
        rows = [candle(i * 60_000, 100 + i) for i in range(62)]
        event = {
            "event_id": "e60",
            "cohort_window": "cohort_a",
            "event_at_utc": "1970-01-01T01:01:00Z",
        }
        result = analyze_event(rows, event, horizons=(60,))
        self.assertTrue(result["horizons_minutes"]["60"]["pre_window_available"])
        self.assertIsNotNone(result["horizons_minutes"]["60"]["pre_event_return_pct"])

        # Removing the candle before the 60-minute pre-window must fail closed.
        result_without_baseline = analyze_event(rows[1:], event, horizons=(60,))
        self.assertFalse(result_without_baseline["horizons_minutes"]["60"]["pre_window_available"])
        self.assertIsNone(result_without_baseline["horizons_minutes"]["60"]["pre_event_return_pct"])
