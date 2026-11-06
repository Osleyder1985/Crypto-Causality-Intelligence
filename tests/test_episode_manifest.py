import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from copy import deepcopy
from datetime import datetime, timezone

from scripts.research.episode_manifest import ManifestError, main, validate_manifest


def approved_manifest():
    return {
        "schema_version": "cci.episode-manifest.v1",
        "manifest_status": "approved",
        "experiment_key": "btc-usdt-directional-episodes-v1",
        "market": "BTC/USDT",
        "venue": "binance",
        "market_type": "spot",
        "interval_seconds": 3600,
        "input_timezone": "UTC-05:00",
        "data_source": {
            "provider": "local-file",
            "dataset_id": "synthetic-fixture",
            "acquisition_method": "test fixture",
        },
        "data_usage_authorization": {"status": "authorized", "evidence_ref": "test-only"},
        "episodes": [{
            "episode_id": "bull-001",
            "direction": "bullish",
            "status": "confirmed",
            "start_local": "2026-01-01T00:00:00-05:00",
            "end_local": "2026-01-02T00:00:00-05:00",
            "start_utc": "2026-01-01T05:00:00Z",
            "end_utc": "2026-01-02T05:00:00Z",
        }, {
            "episode_id": "bear-001",
            "direction": "bearish",
            "status": "confirmed",
            "start_local": "2026-01-03T00:00:00-05:00",
            "end_local": "2026-01-04T00:00:00-05:00",
            "start_utc": "2026-01-03T05:00:00Z",
            "end_utc": "2026-01-04T05:00:00Z",
        }],
    }


class EpisodeManifestTests(unittest.TestCase):
    def test_standalone_cli_reports_approved_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            path.write_text(json.dumps(approved_manifest()), encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = main(["--manifest", str(path)])
        self.assertEqual(result, 0)
        self.assertIn("bullish=1, bearish=1", output.getvalue())

    def test_valid_manifest_normalizes_to_utc(self):
        episodes = validate_manifest(approved_manifest())
        self.assertEqual(episodes[0]["start"], datetime(2026, 1, 1, 5, tzinfo=timezone.utc))
        self.assertEqual(episodes[0]["end"], datetime(2026, 1, 2, 5, tzinfo=timezone.utc))

    def test_pending_manifest_is_not_executable(self):
        doc = approved_manifest()
        doc["manifest_status"] = "pending_confirmation"
        with self.assertRaisesRegex(ManifestError, "pendiente"):
            validate_manifest(doc)

    def test_local_and_utc_must_match(self):
        doc = approved_manifest()
        doc["episodes"][0]["start_utc"] = "2026-01-01T04:00:00Z"
        with self.assertRaisesRegex(ManifestError, "no corresponde"):
            validate_manifest(doc)

    def test_local_offset_is_mandatory_and_exact(self):
        doc = approved_manifest()
        doc["episodes"][0]["start_local"] = "2026-01-01T00:00:00Z"
        with self.assertRaisesRegex(ManifestError, "offset -05:00"):
            validate_manifest(doc)

    def test_utc_hour_alignment_is_required(self):
        doc = approved_manifest()
        doc["episodes"][0]["start_utc"] = "2026-01-01T05:30:00Z"
        doc["episodes"][0]["start_local"] = "2026-01-01T00:30:00-05:00"
        with self.assertRaisesRegex(ManifestError, "alineado"):
            validate_manifest(doc)

    def test_duplicate_episode_id_is_rejected(self):
        doc = approved_manifest()
        doc["episodes"].append(deepcopy(doc["episodes"][0]))
        with self.assertRaisesRegex(ManifestError, "único"):
            validate_manifest(doc)

    def test_overlapping_episodes_are_rejected(self):
        doc = approved_manifest()
        second = deepcopy(doc["episodes"][0])
        second.update({
            "episode_id": "bull-002",
            "start_local": "2026-01-01T12:00:00-05:00",
            "start_utc": "2026-01-01T17:00:00Z",
            "end_local": "2026-01-03T00:00:00-05:00",
            "end_utc": "2026-01-03T05:00:00Z",
        })
        doc["episodes"].append(second)
        with self.assertRaisesRegex(ManifestError, "solapados"):
            validate_manifest(doc)

    def test_authorization_requires_evidence_reference(self):
        doc = approved_manifest()
        doc["data_usage_authorization"]["evidence_ref"] = " "
        with self.assertRaisesRegex(ManifestError, "evidence_ref"):
            validate_manifest(doc)

    def test_cohort_requires_both_directions(self):
        doc = approved_manifest()
        doc["episodes"] = doc["episodes"][:1]
        with self.assertRaisesRegex(ManifestError, "bullish y bearish"):
            validate_manifest(doc)

    def test_only_hourly_interval_is_allowed(self):
        doc = approved_manifest()
        doc["interval_seconds"] = 900
        with self.assertRaisesRegex(ManifestError, "3600 segundos"):
            validate_manifest(doc)

    def test_unauthorized_dataset_is_rejected(self):
        doc = approved_manifest()
        doc["data_usage_authorization"]["status"] = "pending"
        with self.assertRaisesRegex(ManifestError, "no está autorizado"):
            validate_manifest(doc)

    def test_only_binance_venue_is_allowed(self):
        doc = approved_manifest()
        doc["venue"] = "kraken"
        with self.assertRaisesRegex(ManifestError, "Binance Spot"):
            validate_manifest(doc)

    def test_non_spot_type_is_explicit_not_implicitly_assumed(self):
        doc = approved_manifest()
        doc["market_type"] = "perpetual"
        with self.assertRaisesRegex(ManifestError, "spot"):
            validate_manifest(doc)


if __name__ == "__main__":
    unittest.main()
