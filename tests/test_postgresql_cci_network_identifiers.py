import os
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
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
]


class CCINetworkIdentifierMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if "CCI_TEST_DATABASE_URL" not in os.environ:
            raise unittest.SkipTest(
                "CCI network identifier tests require CCI_TEST_DATABASE_URL; "
                "run them through the dedicated PostgreSQL workflow."
            )
        cls.dsn = os.environ["CCI_TEST_DATABASE_URL"]
        with psycopg.connect(cls.dsn, autocommit=True) as conn:
            conn.execute("DROP SCHEMA IF EXISTS cci CASCADE")
            for migration_path in MIGRATIONS:
                conn.execute(migration_path.read_text(encoding="utf-8"), prepare=False)

    def setUp(self):
        self.conn = psycopg.connect(os.environ["CCI_TEST_DATABASE_URL"])
        self.source_id = uuid.uuid4()
        self.network_id = uuid.uuid4()
        self.platform_id = uuid.uuid4()
        self.now = datetime.now(timezone.utc)
        self.platform_key = f"synthetic-platform-{self.platform_id.hex[:10]}"
        self.conn.execute(
            """
            INSERT INTO cci.data_sources
                (id, source_key, display_name, source_type, status)
            VALUES (%s, 'synthetic-platform-source', 'Synthetic source', 'synthetic', 'active')
            """,
            (self.source_id,),
        )
        self.conn.execute(
            """
            INSERT INTO cci.networks
                (id, network_key, display_name, network_family, environment)
            VALUES (%s, 'synthetic:network', 'Synthetic network', 'evm', 'mainnet')
            """,
            (self.network_id,),
        )
        self.conn.execute(
            """
            INSERT INTO cci.provider_platforms (id, data_source_id, provider_platform_key)
            VALUES (%s, %s, %s)
            """,
            (self.platform_id, self.source_id, self.platform_key),
        )

    def tearDown(self):
        self.conn.rollback()
        self.conn.close()

    def insert_review(self, *, status="accepted", network_id=None, supersedes=None):
        review_id = uuid.uuid4()
        self.conn.execute(
            """
            INSERT INTO cci.provider_platform_resolution_reviews (
                id, provider_platform_id, data_source_id, candidate_network_id,
                resolution_status, evidence_reference, reviewed_at, valid_from,
                supersedes_review_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                review_id, self.platform_id, self.source_id,
                network_id or (self.network_id if status == "accepted" else None),
                status,
                "synthetic://review/evidence" if status == "accepted" else None,
                self.now if status == "accepted" else None,
                self.now - timedelta(minutes=1),
                supersedes,
            ),
        )
        return review_id

    def insert_mapping(self, review_id, *, network_id=None, namespace=None,
                       identifier_type="asset_platform_id", identifier_value=None,
                       provider_platform_id=None, provider_data_source_id=None,
                       provider_status="accepted"):
        mapping_id = uuid.uuid4()
        self.conn.execute(
            """
            INSERT INTO cci.network_identifiers (
                id, network_id, namespace, identifier_type, identifier_value,
                observed_at, evidence_reference, provider_platform_id,
                provider_data_source_id, provider_platform_resolution_review_id,
                provider_platform_resolution_status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                mapping_id, network_id or self.network_id,
                namespace or "synthetic-platform-source:asset_platform_id",
                identifier_type, identifier_value or self.platform_key, self.now,
                "synthetic://mapping/evidence",
                provider_platform_id if provider_platform_id is not None else self.platform_id,
                provider_data_source_id if provider_data_source_id is not None else self.source_id,
                review_id, provider_status,
            ),
        )
        return mapping_id

    def test_migration_installs_network_identifiers_and_current_mapping_view(self):
        self.assertIsNotNone(self.conn.execute(
            "SELECT to_regclass('cci.network_identifiers')"
        ).fetchone()[0])
        self.assertIsNotNone(self.conn.execute(
            "SELECT to_regclass('cci.provider_platform_mappings_current')"
        ).fetchone()[0])
        self.assertEqual(
            self.conn.execute(
                "SELECT count(*) FROM cci.schema_migrations WHERE version = '004_network_identifiers'"
            ).fetchone()[0],
            1,
        )

    def test_native_network_identifier_without_provider_provenance_is_valid(self):
        self.conn.execute(
            """
            INSERT INTO cci.network_identifiers (
                id, network_id, namespace, identifier_type, identifier_value,
                observed_at, evidence_reference
            ) VALUES (%s, %s, 'eip155', 'chain_id', '31337', %s, 'synthetic://native')
            """,
            (uuid.uuid4(), self.network_id, self.now),
        )

    def test_partial_provider_provenance_is_rejected(self):
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.conn.execute(
                    """
                    INSERT INTO cci.network_identifiers (
                        id, network_id, namespace, identifier_type, identifier_value,
                        observed_at, evidence_reference, provider_platform_id
                    ) VALUES (%s, %s, 'synthetic', 'asset_platform_id', %s, %s,
                              'synthetic://partial', %s)
                    """,
                    (uuid.uuid4(), self.network_id, self.platform_key, self.now, self.platform_id),
                )

    def test_accepted_review_publishes_mapping_in_current_view(self):
        review_id = self.insert_review()
        self.insert_mapping(review_id)
        row = self.conn.execute(
            """
            SELECT provider_platform_id, network_id, identifier_value, resolution_review_id
            FROM cci.provider_platform_mappings_current
            WHERE provider_platform_id = %s
            """,
            (self.platform_id,),
        ).fetchone()
        self.assertEqual(row, (self.platform_id, self.network_id, self.platform_key, review_id))

    def test_mapping_must_match_exact_platform_literal_and_namespace(self):
        review_id = self.insert_review()
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.insert_mapping(review_id, identifier_value="different-platform-key")
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.insert_mapping(review_id, namespace="wrong:asset_platform_id")

    def test_mapping_must_reference_same_network_and_accepted_review(self):
        review_id = self.insert_review()
        with self.assertRaises(errors.ForeignKeyViolation):
            with self.conn.transaction():
                self.insert_mapping(review_id, network_id=uuid.uuid4())
        pending_review = self.insert_review(status="pending_review")
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.insert_mapping(pending_review, provider_status="pending_review")

    def test_one_provider_mapping_per_resolution_review(self):
        review_id = self.insert_review()
        self.insert_mapping(review_id)
        with self.assertRaises(errors.UniqueViolation):
            with self.conn.transaction():
                self.insert_mapping(review_id)

    def test_mapping_review_must_be_current_chain_head(self):
        root = self.insert_review()
        successor = self.insert_review(status="rejected", supersedes=root)
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.insert_mapping(root)

    def test_network_identifier_is_append_only(self):
        review_id = self.insert_review()
        mapping_id = self.insert_mapping(review_id)
        with self.assertRaises(errors.ObjectNotInPrerequisiteState):
            with self.conn.transaction():
                self.conn.execute(
                    "UPDATE cci.network_identifiers SET identifier_value = 'mutated' WHERE id = %s",
                    (mapping_id,),
                )

    def test_mapping_and_review_can_be_rolled_back_atomically(self):
        with self.assertRaises(RuntimeError):
            with self.conn.transaction():
                review_id = self.insert_review()
                self.insert_mapping(review_id)
                raise RuntimeError("synthetic rollback")
        count = self.conn.execute(
            """
            SELECT count(*) FROM cci.provider_platform_resolution_reviews
            WHERE provider_platform_id = %s
            """,
            (self.platform_id,),
        ).fetchone()[0]
        self.assertEqual(count, 0)

    def test_two_sessions_cannot_publish_duplicate_mapping_for_one_review(self):
        review_id = self.insert_review()
        self.conn.commit()

        def publish():
            with psycopg.connect(os.environ["CCI_TEST_DATABASE_URL"]) as conn:
                try:
                    conn.execute(
                        """
                        INSERT INTO cci.network_identifiers (
                            id, network_id, namespace, identifier_type, identifier_value,
                            observed_at, evidence_reference, provider_platform_id,
                            provider_data_source_id, provider_platform_resolution_review_id,
                            provider_platform_resolution_status
                        ) VALUES (%s, %s, 'synthetic-platform-source:asset_platform_id',
                                  'asset_platform_id', %s, %s, 'synthetic://concurrent',
                                  %s, %s, %s, 'accepted')
                        """,
                        (
                            uuid.uuid4(), self.network_id, self.platform_key, self.now,
                            self.platform_id, self.source_id, review_id,
                        ),
                    )
                    conn.commit()
                    return "published"
                except errors.UniqueViolation:
                    conn.rollback()
                    return "rejected"

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda _: publish(), range(2)))
        self.assertCountEqual(outcomes, ["published", "rejected"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
