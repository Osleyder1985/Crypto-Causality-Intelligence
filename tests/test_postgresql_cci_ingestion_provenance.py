import os
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
from psycopg import errors


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = [
    ROOT / "migrations" / "001_cci_root_entities.sql",
    ROOT / "migrations" / "002_source_policy_catalog.sql",
    ROOT / "migrations" / "003_provider_platform_reviews.sql",
    ROOT / "migrations" / "004_network_identifiers.sql",
    ROOT / "migrations" / "005_asset_representations_relationships.sql",
    ROOT / "migrations" / "006_asset_identity_resolution.sql",
    ROOT / "migrations" / "007_market_instrument_catalog.sql",
    ROOT / "migrations" / "008_ingestion_requests_dataset_sources.sql",
]


class CCIIngestionProvenanceMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if "CCI_TEST_DATABASE_URL" not in os.environ:
            raise unittest.SkipTest(
                "CCI ingestion provenance tests require CCI_TEST_DATABASE_URL; "
                "run them through the dedicated PostgreSQL workflow."
            )
        cls.dsn = os.environ["CCI_TEST_DATABASE_URL"]
        with psycopg.connect(cls.dsn, autocommit=True) as conn:
            conn.execute("DROP SCHEMA IF EXISTS cci CASCADE")
            for migration_path in MIGRATIONS:
                conn.execute(migration_path.read_text(encoding="utf-8"), prepare=False)

    def setUp(self):
        self.conn = psycopg.connect(os.environ["CCI_TEST_DATABASE_URL"])
        self.now = datetime.now(timezone.utc)
        self.source_a = uuid.uuid4()
        self.source_b = uuid.uuid4()
        self.endpoint_a = uuid.uuid4()
        self.endpoint_b = uuid.uuid4()
        self.instrument_a = uuid.uuid4()
        self.instrument_b = uuid.uuid4()
        self.run_id = uuid.uuid4()
        self.dataset_id = uuid.uuid4()
        self.policy_id = uuid.uuid4()
        self.evaluation_id = uuid.uuid4()
        self.conn.execute(
            """
            INSERT INTO cci.data_sources
                (id, source_key, display_name, source_type, status)
            VALUES
                (%s, 'synthetic-ingest-a', 'Synthetic ingest A', 'synthetic', 'active'),
                (%s, 'synthetic-ingest-b', 'Synthetic ingest B', 'synthetic', 'active')
            """,
            (self.source_a, self.source_b),
        )
        self.conn.execute(
            """
            INSERT INTO cci.data_endpoints
                (id, data_source_id, endpoint_key, data_type, status)
            VALUES
                (%s, %s, 'endpoint-a', 'market_metadata', 'active'),
                (%s, %s, 'endpoint-b', 'market_metadata', 'active')
            """,
            (self.endpoint_a, self.source_a, self.endpoint_b, self.source_b),
        )
        self.conn.execute(
            """
            INSERT INTO cci.market_instruments (
                id, data_source_id, native_symbol, native_base_asset_code,
                native_quote_asset_code, market_type
            ) VALUES
                (%s, %s, 'SYNTH/USDT', 'SYNTH', 'USDT', 'spot'),
                (%s, %s, 'SYNTH/USDT', 'SYNTH', 'USDT', 'spot')
            """,
            (self.instrument_a, self.source_a, self.instrument_b, self.source_b),
        )
        self.conn.execute(
            """
            INSERT INTO cci.ingestion_runs (id, run_key, started_at, status)
            VALUES (%s, 'synthetic-ingestion-run', %s, 'running')
            """,
            (self.run_id, self.now),
        )
        self.conn.execute(
            """
            INSERT INTO cci.datasets (
                id, dataset_key, version, stage, data_format, schema_name,
                schema_version, storage_uri, checksum_sha256, retention_status
            ) VALUES (%s, 'synthetic-provenance-dataset', 1, 'source_capture',
                      'json', 'synthetic', '1', 'synthetic://provenance',
                      %s, 'active')
            """,
            (self.dataset_id, "d" * 64),
        )
        self.conn.execute(
            """
            INSERT INTO cci.source_usage_policies (
                id, data_source_id, data_endpoint_id, policy_scope,
                intended_use, permission_status, valid_from
            ) VALUES (%s, %s, %s, 'endpoint', 'private_research',
                      'allowed', %s)
            """,
            (self.policy_id, self.source_a, self.endpoint_a, self.now - timedelta(hours=1)),
        )
        self.conn.execute(
            """
            INSERT INTO cci.policy_evaluations (
                id, source_usage_policy_id, data_source_id, data_endpoint_id,
                data_type, intended_use, permission_status, evaluated_at,
                policy_valid_from_snapshot
            ) VALUES (%s, %s, %s, %s, 'market_metadata', 'private_research',
                      'allowed', %s, %s)
            """,
            (
                self.evaluation_id, self.policy_id, self.source_a, self.endpoint_a,
                self.now, self.now - timedelta(hours=1),
            ),
        )

    def tearDown(self):
        self.conn.rollback()
        self.conn.close()

    def insert_request(self, *, source_id=None, endpoint_id=None, instrument_id=None,
                       attempt=1, status="succeeded", http_status=200,
                       requested_at=None, completed_at=None):
        request_id = uuid.uuid4()
        requested_at = requested_at or self.now
        if completed_at is None and status in ("succeeded", "rejected", "invalid_response"):
            completed_at = requested_at + timedelta(seconds=1)
        self.conn.execute(
            """
            INSERT INTO cci.ingestion_requests (
                id, ingestion_run_id, data_source_id, data_endpoint_id,
                market_instrument_id, attempt_number, requested_at, completed_at,
                http_status, response_status, request_parameters,
                response_headers_safe, records_received
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                      '{}'::jsonb, '{}'::jsonb, 0)
            """,
            (
                request_id, self.run_id, source_id or self.source_a,
                endpoint_id or self.endpoint_a, instrument_id, attempt,
                requested_at, completed_at, http_status, status,
            ),
        )
        return request_id

    def insert_dataset_source(self, *, source_id=None, endpoint_id=None,
                              instrument_id=None, request_id=None,
                              evaluation_id=None, data_type="market_metadata",
                              intended_use="private_research"):
        row_id = uuid.uuid4()
        self.conn.execute(
            """
            INSERT INTO cci.dataset_sources (
                id, dataset_id, data_source_id, data_endpoint_id, data_type,
                market_instrument_id, ingestion_request_id, policy_evaluation_id,
                evaluated_intended_use
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                row_id, self.dataset_id, source_id or self.source_a,
                endpoint_id or self.endpoint_a, data_type, instrument_id,
                request_id, evaluation_id or self.evaluation_id, intended_use,
            ),
        )
        return row_id

    def test_migration_installs_ingestion_and_provenance_tables_and_uk12(self):
        names = {
            row[0] for row in self.conn.execute(
                """
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'cci' AND table_type = 'BASE TABLE'
                """
            ).fetchall()
        }
        self.assertTrue({
            "ingestion_requests", "run_datasets", "dataset_sources"
        }.issubset(names))
        self.assertEqual(
            self.conn.execute(
                "SELECT version FROM cci.schema_migrations WHERE version = '008_ingestion_requests_dataset_sources'"
            ).fetchone()[0],
            "008_ingestion_requests_dataset_sources",
        )
        fk_count = self.conn.execute(
            """
            SELECT count(*) FROM pg_constraint con
            JOIN pg_namespace n ON n.oid = con.connamespace
            WHERE n.nspname = 'cci' AND con.contype = 'f'
            """
        ).fetchone()[0]
        self.assertEqual(fk_count, 48)
        uk12 = self.conn.execute(
            """
            SELECT count(*) FROM pg_constraint
            WHERE conname = 'ingestion_requests_uq_id_source_endpoint' AND contype = 'u'
            """
        ).fetchone()[0]
        self.assertEqual(uk12, 1)

    def test_ingestion_request_accepts_endpoint_and_instrument_from_same_source(self):
        request_id = self.insert_request(instrument_id=self.instrument_a)
        self.assertIsNotNone(
            self.conn.execute(
                "SELECT id FROM cci.ingestion_requests WHERE id = %s",
                (request_id,),
            ).fetchone()
        )

    def test_ingestion_request_allows_null_instrument_but_requires_source_and_endpoint(self):
        self.insert_request(instrument_id=None)
        with self.assertRaises(errors.NotNullViolation):
            with self.conn.transaction():
                self.conn.execute(
                    """
                    INSERT INTO cci.ingestion_requests (
                        id, ingestion_run_id, data_source_id, data_endpoint_id,
                        attempt_number, requested_at, response_status
                    ) VALUES (%s, %s, %s, NULL, 1, %s, 'succeeded')
                    """,
                    (uuid.uuid4(), self.run_id, self.source_a, self.now),
                )

    def test_ingestion_request_rejects_endpoint_from_another_source(self):
        with self.assertRaises(errors.ForeignKeyViolation):
            with self.conn.transaction():
                self.insert_request(endpoint_id=self.endpoint_b)

    def test_ingestion_request_rejects_instrument_from_another_source(self):
        with self.assertRaises(errors.ForeignKeyViolation):
            with self.conn.transaction():
                self.insert_request(instrument_id=self.instrument_b)

    def test_ingestion_request_checks_attempt_count_http_status_and_time(self):
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.insert_request(attempt=0)
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.insert_request(http_status=99)
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.insert_request(
                    requested_at=self.now,
                    completed_at=self.now - timedelta(seconds=1),
                )

    def test_run_dataset_association_requires_existing_run_and_dataset(self):
        self.conn.execute(
            """
            INSERT INTO cci.run_datasets (ingestion_run_id, dataset_id, dataset_role)
            VALUES (%s, %s, 'source_capture')
            """,
            (self.run_id, self.dataset_id),
        )
        with self.assertRaises(errors.ForeignKeyViolation):
            with self.conn.transaction():
                self.conn.execute(
                    """
                    INSERT INTO cci.run_datasets (ingestion_run_id, dataset_id, dataset_role)
                    VALUES (%s, %s, 'derived')
                    """,
                    (uuid.uuid4(), self.dataset_id),
                )

    def test_dataset_source_requires_exact_policy_evaluation_scope(self):
        row_id = self.insert_dataset_source(instrument_id=self.instrument_a)
        self.assertIsNotNone(
            self.conn.execute(
                "SELECT id FROM cci.dataset_sources WHERE id = %s",
                (row_id,),
            ).fetchone()
        )
        with self.assertRaises(errors.ForeignKeyViolation):
            with self.conn.transaction():
                self.insert_dataset_source(intended_use="redistribution")

    def test_dataset_source_rejects_cross_source_endpoint_and_instrument(self):
        with self.assertRaises(errors.ForeignKeyViolation):
            with self.conn.transaction():
                self.insert_dataset_source(endpoint_id=self.endpoint_b)
        with self.assertRaises(errors.ForeignKeyViolation):
            with self.conn.transaction():
                self.insert_dataset_source(instrument_id=self.instrument_b)

    def test_dataset_source_can_omit_request_and_instrument_but_not_source_endpoint(self):
        self.insert_dataset_source(request_id=None, instrument_id=None)
        with self.assertRaises(errors.NotNullViolation):
            with self.conn.transaction():
                self.conn.execute(
                    """
                    INSERT INTO cci.dataset_sources (
                        id, dataset_id, data_source_id, data_endpoint_id, data_type,
                        policy_evaluation_id, evaluated_intended_use
                    ) VALUES (%s, %s, %s, NULL, 'market_metadata', %s, 'private_research')
                    """,
                    (uuid.uuid4(), self.dataset_id, self.source_a, self.evaluation_id),
                )

    def test_dataset_source_request_provenance_requires_exact_request_endpoint_and_source(self):
        request_id = self.insert_request()
        self.insert_dataset_source(request_id=request_id)
        with self.assertRaises(errors.ForeignKeyViolation):
            with self.conn.transaction():
                self.insert_dataset_source(request_id=request_id, endpoint_id=self.endpoint_b)

    def test_dataset_source_is_append_only(self):
        row_id = self.insert_dataset_source()
        with self.assertRaises(errors.ObjectNotInPrerequisiteState):
            with self.conn.transaction():
                self.conn.execute(
                    "DELETE FROM cci.dataset_sources WHERE id = %s",
                    (row_id,),
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
