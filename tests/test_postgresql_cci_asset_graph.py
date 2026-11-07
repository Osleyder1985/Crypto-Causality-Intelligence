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
]


class CCIAssetGraphMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if "CCI_TEST_DATABASE_URL" not in os.environ:
            raise unittest.SkipTest(
                "CCI asset graph tests require CCI_TEST_DATABASE_URL; "
                "run them through the dedicated PostgreSQL workflow."
            )
        cls.dsn = os.environ["CCI_TEST_DATABASE_URL"]
        with psycopg.connect(cls.dsn, autocommit=True) as conn:
            conn.execute("DROP SCHEMA IF EXISTS cci CASCADE")
            for migration_path in MIGRATIONS:
                conn.execute(migration_path.read_text(encoding="utf-8"), prepare=False)

    def setUp(self):
        self.conn = psycopg.connect(os.environ["CCI_TEST_DATABASE_URL"])
        self.asset_a = uuid.uuid4()
        self.asset_b = uuid.uuid4()
        self.network_id = uuid.uuid4()
        self.now = datetime.now(timezone.utc)
        self.conn.execute(
            """
            INSERT INTO cci.assets (id, canonical_code, display_name, asset_type)
            VALUES
                (%s, 'SYNTHETIC:ASSET-A', 'Synthetic asset A', 'crypto'),
                (%s, 'SYNTHETIC:ASSET-B', 'Synthetic asset B', 'crypto')
            """,
            (self.asset_a, self.asset_b),
        )
        self.conn.execute(
            """
            INSERT INTO cci.networks
                (id, network_key, display_name, network_family, environment)
            VALUES (%s, 'synthetic:asset-network', 'Synthetic asset network', 'evm', 'mainnet')
            """,
            (self.network_id,),
        )

    def tearDown(self):
        self.conn.rollback()
        self.conn.close()

    def insert_representation(self, *, asset_id=None, kind="native",
                              native_key="synthetic-native", contract=None,
                              valid_from=None, valid_until=None):
        representation_id = uuid.uuid4()
        self.conn.execute(
            """
            INSERT INTO cci.asset_representations (
                id, asset_id, network_id, representation_kind, native_asset_key,
                contract_address, valid_from, valid_until, observed_at, evidence_reference
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'synthetic://representation')
            """,
            (
                representation_id, asset_id or self.asset_a, self.network_id, kind,
                native_key, contract, valid_from, valid_until, self.now,
            ),
        )
        return representation_id

    def insert_relationship(self, *, subject=None, object_id=None, relationship_type="wrapped_representation_of"):
        relationship_id = uuid.uuid4()
        self.conn.execute(
            """
            INSERT INTO cci.asset_relationships (
                id, subject_asset_id, object_asset_id, relationship_type,
                valid_from, valid_until, evidence_reference, observed_at
            ) VALUES (%s, %s, %s, %s, %s, NULL, 'synthetic://relationship', %s)
            """,
            (
                relationship_id, subject or self.asset_a, object_id or self.asset_b,
                relationship_type, self.now, self.now,
            ),
        )
        return relationship_id

    def test_migration_installs_representation_and_relationship_tables(self):
        names = {
            row[0] for row in self.conn.execute(
                """
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'cci' AND table_type = 'BASE TABLE'
                """
            ).fetchall()
        }
        self.assertTrue({"asset_representations", "asset_relationships"}.issubset(names))
        self.assertEqual(
            self.conn.execute(
                "SELECT version FROM cci.schema_migrations WHERE version = '005_asset_representations_relationships'"
            ).fetchone()[0],
            "005_asset_representations_relationships",
        )

    def test_native_representation_requires_native_key_and_no_contract(self):
        self.insert_representation(kind="native", native_key="native:coin")
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.insert_representation(kind="native", native_key=None, contract="0x1234")

    def test_token_contract_requires_contract_and_no_native_key(self):
        self.insert_representation(kind="token_contract", native_key=None, contract="0xabc123")
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.insert_representation(kind="token_contract", native_key="native:bad", contract="0xabc123")
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.insert_representation(kind="token_contract", native_key=None, contract=None)

    def test_representation_validity_interval_requires_positive_range(self):
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.insert_representation(
                    kind="native", valid_from=self.now,
                    valid_until=self.now - timedelta(seconds=1),
                )

    def test_representation_requires_existing_asset_and_network(self):
        with self.assertRaises(errors.ForeignKeyViolation):
            with self.conn.transaction():
                self.insert_representation(asset_id=uuid.uuid4())

    def test_representation_composite_candidate_key_is_installed(self):
        exists = self.conn.execute(
            """
            SELECT count(*) FROM pg_constraint
            WHERE conname = 'asset_representations_uq_id_network'
              AND contype = 'u'
            """
        ).fetchone()[0]
        self.assertEqual(exists, 1)

    def test_asset_relationship_is_directed_evidenced_and_typed(self):
        relationship_id = self.insert_relationship()
        self.assertEqual(
            self.conn.execute(
                "SELECT directionality FROM cci.asset_relationships WHERE id = %s",
                (relationship_id,),
            ).fetchone()[0],
            "directed",
        )
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.insert_relationship(subject=self.asset_a, object_id=self.asset_a)

    def test_asset_relationship_rejects_unknown_type_and_inverted_validity(self):
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.insert_relationship(relationship_type="same_as")
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.conn.execute(
                    """
                    INSERT INTO cci.asset_relationships (
                        id, subject_asset_id, object_asset_id, relationship_type,
                        valid_from, valid_until, evidence_reference, observed_at
                    ) VALUES (%s, %s, %s, 'backed_by', %s, %s,
                              'synthetic://bad-range', %s)
                    """,
                    (
                        uuid.uuid4(), self.asset_a, self.asset_b,
                        self.now, self.now, self.now,
                    ),
                )

    def test_representations_and_relationships_are_append_only(self):
        representation_id = self.insert_representation()
        with self.assertRaises(errors.ObjectNotInPrerequisiteState):
            with self.conn.transaction():
                self.conn.execute(
                    "UPDATE cci.asset_representations SET native_asset_key = 'mutated' WHERE id = %s",
                    (representation_id,),
                )
        relationship_id = self.insert_relationship()
        with self.assertRaises(errors.ObjectNotInPrerequisiteState):
            with self.conn.transaction():
                self.conn.execute(
                    "DELETE FROM cci.asset_relationships WHERE id = %s",
                    (relationship_id,),
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
