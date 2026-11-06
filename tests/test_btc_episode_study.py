import csv
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.research.btc_episode_study import (
    Candle, StudyError, load_candles, load_episodes, study,
)


class EpisodeStudyTests(unittest.TestCase):
    def setUp(self):
        self.start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.candles = []
        for i in range(240):
            price = 100.0 + i * 0.1
            self.candles.append(Candle(
                timestamp=self.start + timedelta(hours=i),
                open=price, high=price + 1, low=price - 1,
                close=price + 0.5, volume=10.0 + i,
                quote_volume=(10.0 + i) * price,
            ))
        self.episodes = [{
            "episode_id": "test-rise",
            "direction": "bullish",
            "start": self.start + timedelta(hours=168),
            "end": self.start + timedelta(hours=192),
        }]

    def test_computes_episode_and_pre_event_metrics(self):
        result = study(self.candles, self.episodes)
        self.assertEqual(result["episode_count"], 1)
        episode = result["episodes"][0]
        self.assertEqual(episode["candle_count"], 24)
        self.assertGreater(episode["return_pct"], 0)
        self.assertIn("pre_24h", episode["pre_event"])
        self.assertIsNotNone(episode["pre_event"]["pre_168h"])
        self.assertIsNotNone(episode["volume_ratio_vs_pre_168h"])
        self.assertIn("does not establish causality", " ".join(result["limitations"]))

    def test_incomplete_episode_window_is_rejected(self):
        incomplete = self.candles[:]
        del incomplete[180]
        with self.assertRaisesRegex(StudyError, "faltan velas"):
            study(incomplete, self.episodes)

    def test_global_gaps_are_reported(self):
        sparse = self.candles[:100] + self.candles[101:]
        result = study(sparse, [])
        self.assertEqual(result["global_gap_count"], 1)

    def test_bad_ohlc_is_rejected_on_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.csv"
            path.write_text(
                "open_time_utc,open,high,low,close,volume\n"
                "2026-01-01T00:00:00Z,10,9,8,10,1\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(StudyError, "OHLC inconsistente"):
                load_candles(path)

    def test_timezone_naive_timestamp_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.csv"
            path.write_text(
                "open_time_utc,open,high,low,close,volume\n"
                "2026-01-01T00:00:00,10,11,9,10,1\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(StudyError, "UTC"):
                load_candles(path)

    def test_duplicate_timestamp_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dup.csv"
            path.write_text(
                "open_time_utc,open,high,low,close,volume\n"
                "2026-01-01T00:00:00Z,10,11,9,10,1\n"
                "2026-01-01T00:00:00Z,10,11,9,10,1\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(StudyError, "duplicado"):
                load_candles(path)

    def test_episode_end_is_exclusive(self):
        result = study(self.candles, self.episodes)
        self.assertEqual(result["episodes"][0]["candle_count"], 24)
        self.assertTrue(result["episodes"][0]["end_utc_exclusive"].endswith("00:00:00Z"))

    def test_loads_episodes_and_rejects_invalid_direction(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "episodes.json"
            path.write_text(json.dumps([{
                "episode_id": "x", "direction": "sideways",
                "start_utc": "2026-01-01T00:00:00Z",
                "end_utc": "2026-01-02T00:00:00Z",
            }]), encoding="utf-8")
            with self.assertRaisesRegex(StudyError, "direction"):
                load_episodes(path)


if __name__ == "__main__":
    unittest.main()
