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
]


class CCISourcePolicyMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if "CCI_TEST_DATABASE_URL" not in os.environ:
            raise unittest.SkipTest(
                "CCI policy integration tests require CCI_TEST_DATABASE_URL; "
                "run them through the dedicated PostgreSQL workflow."
            )
        cls.dsn = os.environ["CCI_TEST_DATABASE_URL"]
        with psycopg.connect(cls.dsn, autocommit=True) as conn:
            conn.execute("DROP SCHEMA IF EXISTS cci CASCADE")
            for migration_path in MIGRATIONS:
                conn.execute(migration_path.read_text(encoding="utf-8"), prepare=False)

    def setUp(self):
        self.conn = psycopg.connect(os.environ["CCI_TEST_DATABASE_URL"])
        self.source_a = uuid.uuid4()
        self.source_b = uuid.uuid4()
        self.endpoint_a = uuid.uuid4()
        self.now = datetime.now(timezone.utc)
        self.conn.execute(
            """
            INSERT INTO cci.data_sources
                (id, source_key, display_name, source_type, status)
            VALUES
                (%s, 'synthetic-source-a', 'Synthetic source A', 'synthetic', 'active'),
                (%s, 'synthetic-source-b', 'Synthetic source B', 'synthetic', 'active')
            """,
            (self.source_a, self.source_b),
        )
        self.conn.execute(
            """
            INSERT INTO cci.data_endpoints
                (id, data_source_id, endpoint_key, data_type, status)
            VALUES (%s, %s, 'synthetic-endpoint', 'market_metadata', 'active')
            """,
            (self.endpoint_a, self.source_a),
        )

    def tearDown(self):
        self.conn.rollback()
        self.conn.close()

    def insert_policy(self, *, scope="endpoint", endpoint_id=None, source_id=None,
                      scope_reference=None, valid_until=None, permission="allowed"):
        policy_id = uuid.uuid4()
        self.conn.execute(
            """
            INSERT INTO cci.source_usage_policies (
                id, data_source_id, data_endpoint_id, policy_scope, scope_reference,
                intended_use, permission_status, evidence_reference,
                valid_from, valid_until
            ) VALUES (%s, %s, %s, %s, %s, 'private_research', %s,
                      'synthetic://policy/evidence', %s, %s)
            """,
            (
                policy_id, source_id or self.source_a, endpoint_id, scope,
                scope_reference, permission, self.now, valid_until,
            ),
        )
        return policy_id

    def test_migration_chain_installs_three_tables_and_records_both_versions(self):
        tables = self.conn.execute(
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'cci' AND table_type = 'BASE TABLE'
            ORDER BY table_name
            """
        ).fetchall()
        names = [row[0] for row in tables]
        self.assertTrue({"data_endpoints", "source_usage_policies", "policy_evaluations"}.issubset(names))
        versions = self.conn.execute(
            "SELECT version FROM cci.schema_migrations ORDER BY version"
        ).fetchall()
        self.assertEqual([row[0] for row in versions], [
            "001_cci_root_entities", "002_source_policy_catalog"
        ])

    def test_endpoint_must_reference_existing_source(self):
        with self.assertRaises(errors.ForeignKeyViolation):
            with self.conn.transaction():
                self.conn.execute(
                    """
                    INSERT INTO cci.data_endpoints
                        (id, data_source_id, endpoint_key, data_type, status)
                    VALUES (%s, %s, 'orphan-endpoint', 'market_metadata', 'active')
                    """,
                    (uuid.uuid4(), uuid.uuid4()),
                )

    def test_composite_endpoint_policy_fk_prevents_cross_source_reference(self):
        with self.assertRaises(errors.ForeignKeyViolation):
            with self.conn.transaction():
                self.insert_policy(
                    scope="endpoint", endpoint_id=self.endpoint_a, source_id=self.source_b
                )

    def test_policy_scope_rules_accept_provider_product_and_endpoint_forms(self):
        provider_policy = self.insert_policy(scope="provider")
        product_policy = self.insert_policy(scope="product", scope_reference="synthetic:free-tier")
        endpoint_policy = self.insert_policy(scope="endpoint", endpoint_id=self.endpoint_a)
        self.assertEqual(len({provider_policy, product_policy, endpoint_policy}), 3)

    def test_policy_scope_rejects_missing_endpoint_and_empty_product_reference(self):
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.insert_policy(scope="endpoint", endpoint_id=None)
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.insert_policy(scope="product", scope_reference="  ")

    def test_policy_validity_interval_is_semi_open_and_positive(self):
        self.insert_policy(scope="endpoint", endpoint_id=self.endpoint_a,
                           valid_until=self.now + timedelta(seconds=1))
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.insert_policy(scope="endpoint", endpoint_id=self.endpoint_a,
                                   valid_until=self.now)

    def test_policy_evaluation_requires_matching_policy_source_and_endpoint(self):
        policy_id = self.insert_policy(scope="endpoint", endpoint_id=self.endpoint_a)
        self.conn.execute(
            """
            INSERT INTO cci.policy_evaluations (
                id, source_usage_policy_id, data_source_id, data_endpoint_id,
                data_type, intended_use, permission_status, evaluated_at,
                policy_valid_from_snapshot
            ) VALUES (%s, %s, %s, %s, 'market_metadata', 'private_research',
                      'allowed', %s, %s)
            """,
            (uuid.uuid4(), policy_id, self.source_a, self.endpoint_a, self.now, self.now),
        )
        with self.assertRaises(errors.ForeignKeyViolation):
            with self.conn.transaction():
                self.conn.execute(
                    """
                    INSERT INTO cci.policy_evaluations (
                        id, source_usage_policy_id, data_source_id, data_endpoint_id,
                        data_type, intended_use, permission_status, evaluated_at,
                        policy_valid_from_snapshot
                    ) VALUES (%s, %s, %s, %s, 'market_metadata', 'private_research',
                              'allowed', %s, %s)
                    """,
                    (uuid.uuid4(), policy_id, self.source_b, self.endpoint_a, self.now, self.now),
                )

    def test_evaluation_snapshot_rejects_inverted_validity(self):
        policy_id = self.insert_policy(scope="endpoint", endpoint_id=self.endpoint_a)
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.conn.execute(
                    """
                    INSERT INTO cci.policy_evaluations (
                        id, source_usage_policy_id, data_source_id, data_endpoint_id,
                        data_type, intended_use, permission_status, evaluated_at,
                        policy_valid_from_snapshot, policy_valid_until_snapshot
                    ) VALUES (%s, %s, %s, %s, 'market_metadata', 'private_research',
                              'allowed', %s, %s, %s)
                    """,
                    (
                        uuid.uuid4(), policy_id, self.source_a, self.endpoint_a,
                        self.now, self.now, self.now,
                    ),
                )

    def test_policy_lookup_and_composite_fk_indexes_are_installed(self):
        indexes = {
            row[0]
            for row in self.conn.execute(
                """
                SELECT indexname FROM pg_indexes
                WHERE schemaname = 'cci'
                """
            ).fetchall()
        }
        self.assertTrue({
            "source_usage_policies_ix_source_valid_from",
            "source_usage_policies_ix_endpoint_valid_from",
            "policy_evaluations_ix_scope_time",
            "policy_evaluations_ix_policy_source",
            "policy_evaluations_ix_endpoint_source",
        }.issubset(indexes))


if __name__ == "__main__":
    unittest.main(verbosity=2)
