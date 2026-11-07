import unittest
from datetime import datetime, timedelta, timezone

from scripts.persistence.check_storage_permission import validate_permission

NOW = datetime(2026, 11, 7, 4, 0, tzinfo=timezone.utc)
FUTURE = NOW + timedelta(days=30)
UPDATED = NOW - timedelta(minutes=1)


class StoragePermissionPreflightTests(unittest.TestCase):
    def test_allows_valid_unexpired_evidence(self):
        result = validate_permission(
            (True, FUTURE, "signed-approval:CCI-001", UPDATED),
            "binance", "SPOT", "BTCUSDT", now=NOW,
        )
        self.assertEqual(result["status"], "authorized")

    def test_denies_missing_permission(self):
        with self.assertRaisesRegex(PermissionError, "No storage authorization"):
            validate_permission(None, "binance", "SPOT", "BTCUSDT", now=NOW)

    def test_denies_explicit_false(self):
        with self.assertRaisesRegex(PermissionError, "explicitly denied"):
            validate_permission(
                (False, FUTURE, "review-pending", UPDATED),
                "binance", "SPOT", "BTCUSDT", now=NOW,
            )

    def test_denies_expired_permission(self):
        with self.assertRaisesRegex(PermissionError, "expired"):
            validate_permission(
                (True, NOW - timedelta(seconds=1), "approval", UPDATED),
                "binance", "SPOT", "BTCUSDT", now=NOW,
            )

    def test_denies_missing_retention_deadline(self):
        with self.assertRaisesRegex(PermissionError, "absent or expired"):
            validate_permission(
                (True, None, "approval", UPDATED),
                "binance", "SPOT", "BTCUSDT", now=NOW,
            )

    def test_denies_missing_evidence(self):
        with self.assertRaisesRegex(PermissionError, "no evidence reference"):
            validate_permission(
                (True, FUTURE, "  ", UPDATED),
                "binance", "SPOT", "BTCUSDT", now=NOW,
            )


if __name__ == "__main__":
    unittest.main()
