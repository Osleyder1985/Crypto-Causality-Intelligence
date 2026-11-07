import os
import unittest
import uuid
from pathlib import Path

import psycopg
from psycopg import errors


ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = ROOT / "migrations" / "001_cci_root_entities.sql"


class CCIRootSchemaMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if "CCI_TEST_DATABASE_URL" not in os.environ:
            raise unittest.SkipTest(
                "CCI schema integration tests require CCI_TEST_DATABASE_URL; "
                "run them through the dedicated PostgreSQL workflow."
            )
        cls.dsn = os.environ["CCI_TEST_DATABASE_URL"]
        migration = MIGRATION_PATH.read_text(encoding="utf-8")
        with psycopg.connect(cls.dsn, autocommit=True) as conn:
            conn.execute("DROP SCHEMA IF EXISTS cci CASCADE")
            conn.execute(migration, prepare=False)

    def setUp(self):
        self.conn = psycopg.connect(os.environ["CCI_TEST_DATABASE_URL"])

    def tearDown(self):
        self.conn.rollback()
        self.conn.close()

    def test_fresh_install_creates_exact_root_inventory_and_migration_record(self):
        rows = self.conn.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'cci' AND table_type = 'BASE TABLE'
            ORDER BY table_name
            """
        ).fetchall()
        self.assertEqual(
            [row[0] for row in rows],
            [
                "assets",
                "data_sources",
                "datasets",
                "identity_namespaces",
                "ingestion_runs",
                "networks",
                "research_experiments",
                "schema_migrations",
                "transformations",
            ],
        )
        migration = self.conn.execute(
            "SELECT version FROM cci.schema_migrations"
        ).fetchone()
        self.assertEqual(migration[0], "001_cci_root_entities")

    def test_root_tables_have_no_unplanned_foreign_keys_or_ohlcv_facts(self):
        fk_count = self.conn.execute(
            """
            SELECT count(*)
            FROM pg_constraint con
            JOIN pg_namespace n ON n.oid = con.connamespace
            WHERE n.nspname = 'cci' AND con.contype = 'f'
            """
        ).fetchone()[0]
        self.assertEqual(fk_count, 0)
        self.assertIsNone(
            self.conn.execute(
                """
                SELECT to_regclass('cci.candles')
                """
            ).fetchone()[0]
        )

    def test_data_source_accepts_contract_values_and_rejects_unknown_enum(self):
        source_id = uuid.uuid4()
        self.conn.execute(
            """
            INSERT INTO cci.data_sources
                (id, source_key, display_name, source_type, status)
            VALUES (%s, 'synthetic-fixture', 'Synthetic fixture', 'synthetic', 'active')
            """,
            (source_id,),
        )
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.conn.execute(
                    """
                    INSERT INTO cci.data_sources
                        (id, source_key, display_name, source_type, status)
                    VALUES (%s, 'invalid-source', 'Invalid', 'unknown-provider', 'active')
                    """,
                    (uuid.uuid4(),),
                )

    def test_asset_requires_object_json_and_known_asset_type(self):
        self.conn.execute(
            """
            INSERT INTO cci.assets
                (id, canonical_code, display_name, asset_type)
            VALUES (%s, 'SYNTHETIC:BTC', 'Synthetic Bitcoin', 'crypto')
            """,
            (uuid.uuid4(),),
        )
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.conn.execute(
                    """
                    INSERT INTO cci.assets
                        (id, canonical_code, display_name, asset_type, external_identifiers)
                    VALUES (%s, 'SYNTHETIC:BAD', 'Bad asset', 'crypto', '[]'::jsonb)
                    """,
                    (uuid.uuid4(),),
                )

    def test_identity_namespace_enforces_scope_and_target_vocabularies(self):
        self.conn.execute(
            """
            INSERT INTO cci.identity_namespaces
                (namespace_key, scope_mode, target_level, description)
            VALUES ('synthetic:asset_id', 'global', 'asset', 'Synthetic test namespace')
            """
        )
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.conn.execute(
                    """
                    INSERT INTO cci.identity_namespaces
                        (namespace_key, scope_mode, target_level, description)
                    VALUES ('synthetic:bad', 'mixed', 'asset', 'Invalid scope')
                    """
                )

    def test_network_enforces_family_and_environment_vocabularies(self):
        self.conn.execute(
            """
            INSERT INTO cci.networks
                (id, network_key, display_name, network_family, environment)
            VALUES (%s, 'synthetic:mainnet', 'Synthetic network', 'evm', 'mainnet')
            """,
            (uuid.uuid4(),),
        )
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.conn.execute(
                    """
                    INSERT INTO cci.networks
                        (id, network_key, display_name, network_family, environment)
                    VALUES (%s, 'synthetic:bad', 'Bad network', 'evm', 'production')
                    """,
                    (uuid.uuid4(),),
                )

    def test_ingestion_run_terminal_state_requires_finish_time(self):
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.conn.execute(
                    """
                    INSERT INTO cci.ingestion_runs (id, run_key, started_at, status)
                    VALUES (%s, 'bad-terminal-run', now(), 'succeeded')
                    """,
                    (uuid.uuid4(),),
                )
        self.conn.execute(
            """
            INSERT INTO cci.ingestion_runs
                (id, run_key, started_at, status)
            VALUES (%s, 'valid-queued-run', now(), 'queued')
            """,
            (uuid.uuid4(),),
        )

    def test_dataset_rejects_bad_hash_negative_size_and_inverted_time(self):
        base = (
            uuid.uuid4(), "synthetic-dataset", 1, "source_capture", "parquet",
            "synthetic_schema", "1", "synthetic://dataset/one", "a" * 64,
            "active",
        )
        self.conn.execute(
            """
            INSERT INTO cci.datasets (
                id, dataset_key, version, stage, data_format, schema_name,
                schema_version, storage_uri, checksum_sha256, retention_status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            base,
        )
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.conn.execute(
                    """
                    INSERT INTO cci.datasets (
                        id, dataset_key, version, stage, data_format, schema_name,
                        schema_version, storage_uri, checksum_sha256, file_size_bytes,
                        retention_status
                    ) VALUES (%s, 'bad-hash', 1, 'source_capture', 'parquet',
                              'schema', '1', 'synthetic://bad', %s, -1, 'active')
                    """,
                    (uuid.uuid4(), "G" * 64),
                )
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.conn.execute(
                    """
                    INSERT INTO cci.datasets (
                        id, dataset_key, version, stage, data_format, schema_name,
                        schema_version, storage_uri, checksum_sha256, time_start,
                        time_end, retention_status
                    ) VALUES (%s, 'inverted-time', 1, 'source_capture', 'parquet',
                              'schema', '1', 'synthetic://bad-time', %s,
                              '2026-01-02T00:00:00Z', '2026-01-01T00:00:00Z', 'active')
                    """,
                    (uuid.uuid4(), "b" * 64),
                )

    def test_transformation_and_experiment_keys_are_unique(self):
        self.conn.execute(
            """
            INSERT INTO cci.transformations
                (id, transformation_key, version, description)
            VALUES (%s, 'synthetic-normalize', '1.0', 'Synthetic normalization')
            """,
            (uuid.uuid4(),),
        )
        with self.assertRaises(errors.UniqueViolation):
            with self.conn.transaction():
                self.conn.execute(
                    """
                    INSERT INTO cci.transformations
                        (id, transformation_key, version, description)
                    VALUES (%s, 'synthetic-normalize', '1.0', 'Duplicate version')
                    """,
                    (uuid.uuid4(),),
                )
        self.conn.execute(
            """
            INSERT INTO cci.research_experiments
                (id, experiment_key, title, objective, status)
            VALUES (%s, 'synthetic-experiment', 'Synthetic experiment',
                    'Validate root schema', 'planned')
            """,
            (uuid.uuid4(),),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
