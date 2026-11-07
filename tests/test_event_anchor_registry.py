"""Structural validation for the BTCUSDT research event-anchor registry."""

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANCHORS_PATH = ROOT / "research" / "event_anchors" / "btcusdt_2026.json"
REQUIRED_FIELDS = {"event_id", "cohort_window", "event_at_utc", "event_type", "note"}


class EventAnchorRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with ANCHORS_PATH.open(encoding="utf-8") as handle:
            cls.anchors = json.load(handle)

    def test_registry_is_a_non_empty_list(self):
        self.assertIsInstance(self.anchors, list)
        self.assertTrue(self.anchors)

    def test_each_anchor_has_required_non_empty_fields(self):
        for index, anchor in enumerate(self.anchors):
            with self.subTest(anchor_index=index):
                self.assertIsInstance(anchor, dict)
                self.assertTrue(REQUIRED_FIELDS.issubset(anchor))
                for field in REQUIRED_FIELDS:
                    self.assertIsInstance(anchor[field], str)
                    self.assertTrue(anchor[field].strip())

    def test_event_ids_are_unique(self):
        ids = [anchor["event_id"] for anchor in self.anchors]
        self.assertEqual(len(ids), len(set(ids)))

    def test_event_timestamps_are_explicit_utc_instants(self):
        for anchor in self.anchors:
            with self.subTest(event_id=anchor["event_id"]):
                value = anchor["event_at_utc"]
                self.assertTrue(value.endswith("Z"), value)
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                self.assertIsNotNone(parsed.tzinfo)
                self.assertEqual(parsed.utcoffset(), timezone.utc.utcoffset(parsed))


if __name__ == "__main__":
    unittest.main()
