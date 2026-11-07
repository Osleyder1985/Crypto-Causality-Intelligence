from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.research.analyze_btcusdt_flow_leadlag import analyze_cohorts, load_cohorts


def row(ts: int, close: str, buy: str = "60", total: str = "100") -> dict:
    return {
        "provider": "binance", "market_type": "SPOT", "symbol": "BTCUSDT",
        "interval": "1h", "cohort_window": "cohort_a", "open_time_ms": ts,
        "close": close, "quote_volume": total, "taker_buy_quote_volume": buy,
    }


class FlowLeadLagTests(unittest.TestCase):
    def test_horizon_does_not_cross_cohort_boundary(self):
        cohorts = {
            "a": [
                {"_open_time_ms": i * 3_600_000, "_close": float(100 + i),
                 "_quote_volume": 100.0, "_taker_buy_quote": 60.0}
                for i in range(3)
            ],
            "b": [
                {"_open_time_ms": 10 * 3_600_000, "_close": 500.0,
                 "_quote_volume": 100.0, "_taker_buy_quote": 40.0}
            ],
        }
        report = analyze_cohorts(cohorts)
        self.assertEqual(report["cohorts"]["a"]["horizons"]["1"]["observations"], 2)
        self.assertEqual(report["cohorts"]["a"]["horizons"]["3"]["observations"], 0)
        self.assertFalse(report["causal_claim"])

    def test_loader_rejects_hourly_gap(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rows.jsonl"
            path.write_text("\n".join(json.dumps(item) for item in [
                row(0, "100"), row(7_200_000, "101")
            ]), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "non-contiguous"):
                load_cohorts(path)

    def test_loader_accepts_valid_contiguous_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rows.jsonl"
            path.write_text("\n".join(json.dumps(item) for item in [
                row(0, "100"), row(3_600_000, "101")
            ]), encoding="utf-8")
            cohorts = load_cohorts(path)
            self.assertEqual(len(cohorts["cohort_a"]), 2)


if __name__ == "__main__":
    unittest.main()
