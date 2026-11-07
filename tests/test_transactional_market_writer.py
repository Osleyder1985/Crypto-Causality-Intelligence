from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import psycopg

from scripts.persistence.market_writer import (
    IdempotencyConflict, StoragePermissionDenied, canonicalize_rows,
    payload_digest, purge_expired_market_data, write_candle_batch,
)

OPEN_TIME = datetime(2026, 11, 7, 0, 0, tzinfo=timezone.utc)
BASE = {
    "open_time_ms": int(OPEN_TIME.timestamp() * 1000),
    "open_time_utc": OPEN_TIME,
    "open": "100", "high": "110", "low": "90", "close": "105",
    "volume_base": "2", "quote_volume": "200",
    "close_time_ms": int(OPEN_TIME.timestamp() * 1000) + 3599999,
    "trade_count": 10, "taker_buy_base_volume": "1",
    "taker_buy_quote_volume": "100", "source_ignore_field": "0",
}


class TransactionalWriterValidationTests(unittest.TestCase):
    def test_canonicalizes_decimal_and_utc(self):
        row = canonicalize_rows([BASE])[0]
        self.assertEqual(row["open"], Decimal("100"))
        self.assertEqual(row["open_time_utc"].tzinfo, timezone.utc)

    def test_rejects_timestamp_mismatch(self):
        bad = dict(BASE, open_time_ms=BASE["open_time_ms"] + 3600000,
                    close_time_ms=BASE["close_time_ms"] + 3600000)
        with self.assertRaisesRegex(ValueError, "disagree"):
            canonicalize_rows([bad])

    def test_rejects_duplicate_timestamp(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            canonicalize_rows([BASE, BASE])

    def test_rejects_invalid_ohlc(self):
        bad = dict(BASE, high="99")
        with self.assertRaisesRegex(ValueError, "OHLC"):
            canonicalize_rows([bad])

    def test_digest_is_stable(self):
        rows = canonicalize_rows([BASE])
        self.assertEqual(
            payload_digest("binance", "SPOT", "BTCUSDT", "1h", rows),
            payload_digest("binance", "SPOT", "BTCUSDT", "1h", rows),
        )

    def test_empty_batch_rejected(self):
        with self.assertRaisesRegex(ValueError, "at least one"):
            canonicalize_rows([])


@unittest.skipUnless(os.getenv("DATABASE_URL"), "DATABASE_URL not set; PostgreSQL integration tests skipped")
class PostgreSQLTransactionalWriterTests(unittest.TestCase):
    def setUp(self):
        self.conn = psycopg.connect(os.environ["DATABASE_URL"])
        self.conn.execute(
            "TRUNCATE cci.audit_events, cci.market_candles, "
            "cci.ingestion_runs, cci.source_permissions RESTART IDENTITY CASCADE"
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def authorize(self):
        self.conn.execute(
            """INSERT INTO cci.source_permissions
               (provider, market_type, symbol, storage_allowed, retention_until, evidence_ref)
               VALUES ('binance', 'SPOT', 'BTCUSDT', TRUE, %s, 'test-authorization-evidence')""",
            (datetime.now(timezone.utc) + timedelta(days=1),),
        )
        self.conn.commit()

    def write(self, key="test-batch-1", rows=None):
        return write_candle_batch(
            self.conn, provider="binance", market_type="SPOT", symbol="BTCUSDT",
            interval="1h", rows=[BASE] if rows is None else rows,
            idempotency_key=key, actor="ci-test",
        )

    def test_deny_by_default_without_permission(self):
        with self.assertRaises(StoragePermissionDenied):
            self.write()
        self.assertEqual(self.conn.execute("SELECT count(*) FROM cci.ingestion_runs").fetchone()[0], 0)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM cci.audit_events").fetchone()[0], 0)

    def test_atomic_write_audit_and_idempotent_replay(self):
        self.authorize()
        result = self.write()
        self.assertFalse(result["replayed"])
        self.assertEqual(self.conn.execute("SELECT count(*) FROM cci.market_candles").fetchone()[0], 1)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM cci.audit_events").fetchone()[0], 1)
        replay = self.write()
        self.assertTrue(replay["replayed"])
        self.assertEqual(replay["run_id"], result["run_id"])
        with self.assertRaises(IdempotencyConflict):
            changed = dict(BASE, close="106")
            self.write(rows=[changed])

    def test_failed_candle_insert_rolls_back_run_and_audit(self):
        self.authorize()
        self.write()
        before_runs = self.conn.execute("SELECT count(*) FROM cci.ingestion_runs").fetchone()[0]
        before_audit = self.conn.execute("SELECT count(*) FROM cci.audit_events").fetchone()[0]
        with self.assertRaises(psycopg.errors.UniqueViolation):
            self.write(key="different-key")
        self.assertEqual(self.conn.execute("SELECT count(*) FROM cci.ingestion_runs").fetchone()[0], before_runs)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM cci.audit_events").fetchone()[0], before_audit)

    def test_audit_events_reject_update_and_delete(self):
        self.authorize()
        self.write()
        with self.assertRaises(psycopg.Error):
            with self.conn.transaction():
                self.conn.execute("UPDATE cci.audit_events SET actor = 'tampered'")
        with self.assertRaises(psycopg.Error):
            with self.conn.transaction():
                self.conn.execute("DELETE FROM cci.audit_events")

    def test_expired_permission_purges_data_and_audits_atomically(self):
        self.authorize()
        self.write()
        self.conn.execute(
            "UPDATE cci.source_permissions SET storage_allowed = FALSE, retention_until = NULL "
            "WHERE provider = 'binance' AND market_type = 'SPOT' AND symbol = 'BTCUSDT'"
        )
        self.conn.commit()
        result = purge_expired_market_data(self.conn, actor="retention-worker")
        self.assertEqual(result["deleted_rows"], 1)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM cci.market_candles").fetchone()[0], 0)
        event = self.conn.execute(
            "SELECT event_type, payload->>'deleted_rows' FROM cci.audit_events "
            "WHERE event_type = 'market_data.retention_purged'"
        ).fetchone()
        self.assertEqual(event, ("market_data.retention_purged", "1"))
        replay = purge_expired_market_data(self.conn, actor="retention-worker")
        self.assertEqual(replay["deleted_rows"], 0)


if __name__ == "__main__":
    unittest.main()
