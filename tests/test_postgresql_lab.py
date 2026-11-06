import os
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
from psycopg import errors


ROOT = Path(__file__).resolve().parents[1]
DDL_PATH = ROOT / "tests" / "postgresql" / "001_provider_platform_lab.sql"


class PostgreSQLProviderPlatformLabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ["CCI_TEST_DATABASE_URL"]
        ddl = DDL_PATH.read_text(encoding="utf-8")
        with psycopg.connect(cls.dsn, autocommit=True) as conn:
            conn.execute(ddl, prepare=False)

    def setUp(self):
        self.conn = psycopg.connect(self.dsn)
        self.source_id = uuid.uuid4()
        self.network_id = uuid.uuid4()
        self.platform_id = uuid.uuid4()
        self.platform_key = f"synthetic-chain-{self.platform_id.hex[:10]}"
        self.now = datetime.now(timezone.utc)

        self.conn.execute(
            "INSERT INTO cci_lab.data_sources (id, source_key) VALUES (%s, %s)",
            (self.source_id, "synthetic"),
        )
        self.conn.execute(
            "INSERT INTO cci_lab.networks (id, network_key) VALUES (%s, %s)",
            (self.network_id, f"synthetic-network-{self.network_id.hex[:10]}"),
        )
        self.conn.execute(
            """
            INSERT INTO cci_lab.provider_platforms
                (id, data_source_id, provider_platform_key)
            VALUES (%s, %s, %s)
            """,
            (self.platform_id, self.source_id, self.platform_key),
        )

    def tearDown(self):
        self.conn.rollback()
        self.conn.close()

    def insert_observation(self, capture_id=None, observed_at=None, chain_json="137"):
        observation_id = uuid.uuid4()
        self.conn.execute(
            """
            INSERT INTO cci_lab.provider_platform_observations (
                id, provider_platform_id, data_source_id, capture_id,
                observed_at, reported_chain_identifier_json, evidence_reference
            ) VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s)
            """,
            (
                observation_id, self.platform_id, self.source_id,
                capture_id or uuid.uuid4(), observed_at or self.now,
                chain_json, "synthetic://evidence/observation",
            ),
        )
        return observation_id

    def insert_review(self, status="accepted", supersedes=None, valid_from=None):
        review_id = uuid.uuid4()
        self.conn.execute(
            """
            INSERT INTO cci_lab.provider_platform_resolution_reviews (
                id, provider_platform_id, data_source_id,
                candidate_network_id, resolution_status, evidence_reference,
                reviewed_at, valid_from, supersedes_review_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                review_id, self.platform_id, self.source_id,
                self.network_id if status == "accepted" else None,
                status,
                "synthetic://evidence/review" if status == "accepted" else None,
                self.now if status == "accepted" else None,
                valid_from or self.now - timedelta(minutes=1),
                supersedes,
            ),
        )
        return review_id

    def insert_mapping(self, review_id, identifier_value=None, namespace="synthetic:asset_platform_id"):
        self.conn.execute(
            """
            INSERT INTO cci_lab.network_identifiers (
                id, network_id, namespace, identifier_type, identifier_value,
                observed_at, evidence_reference, provider_platform_id,
                provider_data_source_id, provider_platform_resolution_review_id,
                provider_platform_resolution_status
            ) VALUES (%s, %s, %s, 'asset_platform_id', %s, %s, %s, %s, %s, %s, 'accepted')
            """,
            (
                uuid.uuid4(), self.network_id, namespace,
                identifier_value or self.platform_key, self.now,
                "synthetic://evidence/mapping", self.platform_id,
                self.source_id, review_id,
            ),
        )

    def test_json_number_and_json_null_are_accepted_but_string_is_rejected(self):
        self.insert_observation(chain_json="137")
        self.insert_observation(chain_json="null")
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.insert_observation(chain_json='"137"')

    def test_capture_id_is_unique_but_observed_at_is_not(self):
        capture_id = uuid.uuid4()
        self.insert_observation(capture_id=capture_id)
        self.insert_observation(observed_at=self.now, capture_id=uuid.uuid4())
        with self.assertRaises(errors.UniqueViolation):
            with self.conn.transaction():
                self.insert_observation(capture_id=capture_id)

    def test_accepted_review_publishes_current_mapping(self):
        review_id = self.insert_review()
        self.insert_mapping(review_id)
        row = self.conn.execute(
            """
            SELECT count(*)
            FROM cci_lab.provider_platform_mappings_current
            WHERE provider_platform_id = %s
            """,
            (self.platform_id,),
        ).fetchone()
        self.assertEqual(row[0], 1)

    def test_nonaccepted_review_is_visible_but_does_not_publish_mapping(self):
        self.insert_review(status="pending_review")
        row = self.conn.execute(
            """
            SELECT resolution_status
            FROM cci_lab.provider_platform_resolution_current
            WHERE provider_platform_id = %s
            """,
            (self.platform_id,),
        ).fetchone()
        self.assertEqual(row[0], "pending_review")

    def test_observations_are_immutable(self):
        self.insert_observation()
        with self.assertRaises(errors.ObjectNotInPrerequisiteState):
            with self.conn.transaction():
                self.conn.execute(
                    """
                    UPDATE cci_lab.provider_platform_observations
                    SET provider_name = 'mutated'
                    WHERE provider_platform_id = %s
                    """,
                    (self.platform_id,),
                )

    def test_partial_provider_provenance_is_rejected(self):
        review_id = self.insert_review()
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.conn.execute(
                    """
                    INSERT INTO cci_lab.network_identifiers (
                        id, network_id, namespace, identifier_type, identifier_value,
                        observed_at, evidence_reference, provider_platform_id,
                        provider_data_source_id, provider_platform_resolution_review_id,
                        provider_platform_resolution_status
                    ) VALUES (%s, %s, 'synthetic:asset_platform_id',
                              'asset_platform_id', %s, %s, 'synthetic://evidence',
                              %s, %s, %s, NULL)
                    """,
                    (
                        uuid.uuid4(), self.network_id, self.platform_key, self.now,
                        self.platform_id, self.source_id, review_id,
                    ),
                )

    def test_mapping_literal_and_namespace_are_guarded(self):
        review_id = self.insert_review()
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.insert_mapping(review_id, identifier_value="different-literal")
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.insert_mapping(review_id, namespace="wrong:namespace")


if __name__ == "__main__":
    unittest.main(verbosity=2)
