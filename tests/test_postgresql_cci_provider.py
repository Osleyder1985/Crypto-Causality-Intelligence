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
]


class CCIProviderPlatformMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if "CCI_TEST_DATABASE_URL" not in os.environ:
            raise unittest.SkipTest(
                "CCI provider platform tests require CCI_TEST_DATABASE_URL; "
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
        self.conn.execute(
            """
            INSERT INTO cci.data_sources
                (id, source_key, display_name, source_type, status)
            VALUES (%s, 'synthetic-provider', 'Synthetic provider', 'synthetic', 'active')
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
        self.platform_key = f"synthetic-platform-{self.platform_id.hex[:10]}"
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

    def insert_observation(self, *, capture_id=None, chain_json="137", evidence_sha256=None):
        observation_id = uuid.uuid4()
        self.conn.execute(
            """
            INSERT INTO cci.provider_platform_observations (
                id, provider_platform_id, data_source_id, capture_id,
                observed_at, reported_chain_identifier_json, evidence_reference, evidence_sha256
            ) VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s)
            """,
            (
                observation_id, self.platform_id, self.source_id,
                capture_id or uuid.uuid4(), self.now, chain_json,
                "synthetic://provider/observation", evidence_sha256,
            ),
        )
        return observation_id

    def insert_review(self, *, status="accepted", supersedes=None, valid_from=None,
                      candidate_network_id=None, reviewed_at=None, evidence_reference=None):
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
                candidate_network_id if candidate_network_id is not None else (
                    self.network_id if status == "accepted" else None
                ),
                status,
                evidence_reference if evidence_reference is not None else (
                    "synthetic://provider/review" if status == "accepted" else None
                ),
                reviewed_at if reviewed_at is not None else (
                    self.now if status == "accepted" else None
                ),
                valid_from or self.now - timedelta(minutes=1),
                supersedes,
            ),
        )
        return review_id

    def test_migration_installs_platform_tables_view_and_temporal_function(self):
        tables = {
            row[0] for row in self.conn.execute(
                """
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'cci' AND table_type = 'BASE TABLE'
                """
            ).fetchall()
        }
        self.assertTrue({
            "provider_platforms",
            "provider_platform_observations",
            "provider_platform_resolution_reviews",
        }.issubset(tables))
        self.assertIsNotNone(self.conn.execute(
            "SELECT to_regclass('cci.provider_platform_resolution_current')"
        ).fetchone()[0])
        self.assertEqual(
            self.conn.execute(
                "SELECT count(*) FROM cci.schema_migrations WHERE version = '003_provider_platform_reviews'"
            ).fetchone()[0],
            1,
        )

    def test_observation_rejects_platform_source_mismatch(self):
        with self.assertRaises(errors.ForeignKeyViolation):
            with self.conn.transaction():
                self.conn.execute(
                    """
                    INSERT INTO cci.provider_platform_observations (
                        id, provider_platform_id, data_source_id, capture_id,
                        observed_at, reported_chain_identifier_json, evidence_reference
                    ) VALUES (%s, %s, %s, %s, %s, '137'::jsonb, 'synthetic://bad')
                    """,
                    (uuid.uuid4(), self.platform_id, uuid.uuid4(), uuid.uuid4(), self.now),
                )

    def test_capture_id_is_unique_per_platform(self):
        capture_id = uuid.uuid4()
        self.insert_observation(capture_id=capture_id)
        with self.assertRaises(errors.UniqueViolation):
            with self.conn.transaction():
                self.insert_observation(capture_id=capture_id)

    def test_observation_json_type_and_evidence_hash_are_checked(self):
        self.insert_observation(chain_json="null", evidence_sha256="a" * 64)
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.insert_observation(chain_json='"137"')
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.insert_observation(evidence_sha256="A" * 64)

    def test_observations_are_append_only(self):
        self.insert_observation()
        with self.assertRaises(errors.ObjectNotInPrerequisiteState):
            with self.conn.transaction():
                self.conn.execute(
                    """
                    UPDATE cci.provider_platform_observations
                    SET provider_name = 'mutated'
                    WHERE provider_platform_id = %s
                    """,
                    (self.platform_id,),
                )

    def test_accepted_review_requires_network_evidence_and_review_timestamp(self):
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.insert_review(candidate_network_id=None)
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.insert_review(evidence_reference=" ")

    def test_first_review_is_current_and_visible_as_known(self):
        review_id = self.insert_review()
        current = self.conn.execute(
            """
            SELECT resolution_review_id, network_id, resolution_status
            FROM cci.provider_platform_resolution_current
            WHERE provider_platform_id = %s
            """,
            (self.platform_id,),
        ).fetchone()
        self.assertEqual(current, (review_id, self.network_id, "accepted"))
        known = self.conn.execute(
            """
            SELECT resolution_review_id
            FROM cci.provider_platform_resolution_as_known(%s, %s)
            WHERE provider_platform_id = %s
            """,
            (self.now, self.now + timedelta(days=1), self.platform_id),
        ).fetchone()
        self.assertEqual(known[0], review_id)

    def test_second_root_review_is_rejected(self):
        self.insert_review()
        with self.assertRaises(errors.UniqueViolation):
            with self.conn.transaction():
                self.insert_review()

    def test_successor_must_supersede_current_chain_head(self):
        root = self.insert_review()
        self.insert_review(supersedes=root, status="pending_review")
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.insert_review(supersedes=root, status="rejected")

    def test_successor_valid_from_cannot_precede_predecessor(self):
        root = self.insert_review(valid_from=self.now)
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.insert_review(
                    supersedes=root, status="pending_review",
                    valid_from=self.now - timedelta(seconds=1),
                )

    def test_reviews_are_append_only(self):
        review_id = self.insert_review()
        with self.assertRaises(errors.ObjectNotInPrerequisiteState):
            with self.conn.transaction():
                self.conn.execute(
                    """
                    UPDATE cci.provider_platform_resolution_reviews
                    SET resolution_status = 'rejected'
                    WHERE id = %s
                    """,
                    (review_id,),
                )

    def test_two_sessions_cannot_create_competing_successors(self):
        root = self.insert_review()
        self.conn.commit()
        successor_time = self.now + timedelta(seconds=1)

        def create_successor():
            with psycopg.connect(os.environ["CCI_TEST_DATABASE_URL"]) as conn:
                try:
                    conn.execute(
                        """
                        INSERT INTO cci.provider_platform_resolution_reviews (
                            id, provider_platform_id, data_source_id,
                            resolution_status, valid_from, supersedes_review_id
                        ) VALUES (%s, %s, %s, 'pending_review', %s, %s)
                        """,
                        (uuid.uuid4(), self.platform_id, self.source_id, successor_time, root),
                    )
                    conn.commit()
                    return "accepted"
                except errors.CheckViolation:
                    conn.rollback()
                    return "rejected"

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda _: create_successor(), range(2)))
        self.assertCountEqual(outcomes, ["accepted", "rejected"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
