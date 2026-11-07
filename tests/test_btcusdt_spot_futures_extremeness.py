import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts.research.analyze_btcusdt_spot_futures_extremeness import (
    analyze,
    circular_block_ci,
    load_dense_flow,
    rolling_sell,
)
import random


class SpotFuturesExtremenessTests(unittest.TestCase):
    def test_rolling_sell_uses_signed_flow_and_forward_windows(self):
        self.assertEqual(rolling_sell([1.0, -5.0, 2.0], 2), [4.0, 3.0])

    def test_missing_seconds_are_zero_and_duplicate_buckets_rejected(self):
        day = datetime(2026, 10, 6, tzinfo=timezone.utc)
        start_ms = int(day.timestamp() * 1000)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "flow.jsonl"
            path.write_text(json.dumps({
                "bucket_ms": 1000,
                "bucket_start_ms": start_ms + 2000,
                "signed_taker_notional_usdt": "-7.5",
            }) + "\n", encoding="utf-8")
            self.assertEqual(load_dense_flow(path, day, 4), [0.0, 0.0, -7.5, 0.0])
            with path.open("a", encoding="utf-8") as handle:
                handle.write(path.read_text(encoding="utf-8"))
            with self.assertRaisesRegex(ValueError, "duplicate"):
                load_dense_flow(path, day, 4)

    def test_analysis_preserves_zero_seconds_and_event_maxima(self):
        day = datetime(2026, 10, 6, tzinfo=timezone.utc)
        event = datetime(2026, 10, 6, 0, 0, 50, tzinfo=timezone.utc)
        spot = [0.0] * 100
        futures = [0.0] * 100
        spot[50] = -100.0
        futures[49] = -200.0
        result = analyze(
            spot, futures, day, event, 5, 40, [1], [5], 20, 7
        )["results"][0]
        self.assertEqual(result["baseline_observations"], 40)
        self.assertEqual(result["spot_event_max_sell_usdt"], 100.0)
        self.assertEqual(result["futures_event_max_sell_usdt"], 0.0)
        self.assertEqual(result["spot_empirical_upper_tail_probability"], 0.0)

    def test_paired_bootstrap_is_reproducible(self):
        a = [0, 1, 0, 1, 0, 0, 1, 0]
        b = [1, 1, 0, 0, 0, 1, 0, 0]
        first = circular_block_ci(a, b, 2, 100, random.Random(123))
        second = circular_block_ci(a, b, 2, 100, random.Random(123))
        self.assertEqual(first, second)
        self.assertLessEqual(first["lower_95"], first["upper_95"])


if __name__ == "__main__":
    unittest.main()
