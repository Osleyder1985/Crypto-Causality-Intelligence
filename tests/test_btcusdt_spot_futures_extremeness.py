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
from unittest.mock import patch

from scripts.research.download_binance_btcusdt_multiday_flow import run as acquire_multiday


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

    def test_dense_flow_loader_accepts_consecutive_utc_days(self):
        first_day = datetime(2026, 10, 5, tzinfo=timezone.utc)
        start_ms = int(first_day.timestamp() * 1000)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "multiday.jsonl"
            rows = [
                {"bucket_ms": 1000, "bucket_start_ms": start_ms, "signed_taker_notional_usdt": "-2"},
                {"bucket_ms": 1000, "bucket_start_ms": start_ms + 86400000, "signed_taker_notional_usdt": "-3"},
            ]
            path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            values = load_dense_flow(path, first_day, 86402)
            self.assertEqual(len(values), 86402)
            self.assertEqual(values[0], -2.0)
            self.assertEqual(values[86400], -3.0)
            self.assertEqual(values[-1], 0.0)

    def test_event_max_is_compared_with_equal_duration_baseline_episode_maxima(self):
        day = datetime(2026, 10, 6, tzinfo=timezone.utc)
        event = datetime(2026, 10, 6, 0, 0, 50, tzinfo=timezone.utc)
        spot = [0.0] * 100
        futures = [0.0] * 100
        spot[20] = -60.0
        futures[30] = -150.0
        spot[52] = -100.0
        futures[51] = -200.0
        result = analyze(
            spot, futures, day, event, 5, 40, [1], [5], 20, 7
        )["results"][0]
        self.assertEqual(result["baseline_observations"], 36)
        self.assertEqual(result["spot_event_max_sell_usdt"], 100.0)
        self.assertEqual(result["futures_event_max_sell_usdt"], 200.0)
        self.assertEqual(result["spot_empirical_upper_tail_probability"], 0.0)
        self.assertEqual(result["futures_empirical_upper_tail_probability"], 0.0)

    def test_analyze_accepts_event_on_later_day_of_multiday_grid(self):
        day = datetime(2026, 10, 5, tzinfo=timezone.utc)
        event = datetime(2026, 10, 6, 0, 0, 50, tzinfo=timezone.utc)
        spot = [0.0] * 172800
        futures = [0.0] * 172800
        spot[86450] = -100.0
        result = analyze(
            spot, futures, day, event, 5, 40, [1], [5], 20, 7
        )
        self.assertEqual(result["input_days"], 2)
        self.assertIn(
            "inference is conditional on the configured pre-event baseline and may not generalize across market regimes",
            result["limitations"],
        )
        self.assertFalse(any("single UTC-day" in item for item in result["limitations"]))
        self.assertEqual(result["results"][0]["baseline_observations"], 36)
        self.assertEqual(result["results"][0]["spot_event_max_sell_usdt"], 100.0)

    def test_multiday_acquisition_writes_concatenated_flows_and_hash_manifest(self):
        def fake_acquire(day_text, output):
            day = datetime.fromisoformat(day_text).replace(tzinfo=timezone.utc)
            start_ms = int(day.timestamp() * 1000)
            output.mkdir(parents=True, exist_ok=True)
            raw = output / "raw"
            raw.mkdir()
            markets = {}
            for market in ("spot", "usd_m"):
                (output / f"{market}_flow_1s.jsonl").write_text(
                    json.dumps({
                        "bucket_ms": 1000,
                        "bucket_start_ms": start_ms,
                        "signed_taker_notional_usdt": "-1",
                    }) + "\n",
                    encoding="utf-8",
                )
                archive_name = f"{market}-aggTrades-{day_text}.zip"
                (raw / archive_name).write_bytes(f"{market}-{day_text}".encode())
                (raw / (archive_name + ".CHECKSUM")).write_text("checksum", encoding="ascii")
                markets[market] = {"rows": 1, "aggregates": {"1s": {"rows": 1}}}
            return {"markets": markets}

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "result"
            with patch(
                "scripts.research.download_binance_btcusdt_multiday_flow.acquire_day",
                side_effect=fake_acquire,
            ):
                manifest = acquire_multiday("2026-10-05", 2, destination)
            self.assertEqual(manifest["status"], "all_days_acquired_and_checksum_verified")
            self.assertEqual(len(manifest["markets"]["spot"]), 2)
            self.assertEqual(len((destination / "spot_flow_1s.jsonl").read_text().splitlines()), 2)
            self.assertEqual(len(manifest["markets"]["usd_m"][0]["zip_sha256"]), 64)
            with self.assertRaises(FileExistsError):
                with patch(
                    "scripts.research.download_binance_btcusdt_multiday_flow.acquire_day",
                    side_effect=fake_acquire,
                ):
                    acquire_multiday("2026-10-05", 2, destination)

    def test_paired_bootstrap_is_reproducible(self):
        a = [0, 1, 0, 1, 0, 0, 1, 0]
        b = [1, 1, 0, 0, 0, 1, 0, 0]
        first = circular_block_ci(a, b, 2, 100, random.Random(123))
        second = circular_block_ci(a, b, 2, 100, random.Random(123))
        self.assertEqual(first, second)
        self.assertLessEqual(first["lower_95"], first["upper_95"])
        simultaneous = circular_block_ci(a, b, 2, 100, random.Random(123), family_size=4)
        self.assertEqual(simultaneous["family_size"], 4)
        self.assertEqual(simultaneous["multiplicity_method"], "Bonferroni across configured horizons")
        self.assertLessEqual(simultaneous["lower_familywise_95_bonferroni"], simultaneous["lower_95"])
        self.assertGreaterEqual(simultaneous["upper_familywise_95_bonferroni"], simultaneous["upper_95"])


if __name__ == "__main__":
    unittest.main()
