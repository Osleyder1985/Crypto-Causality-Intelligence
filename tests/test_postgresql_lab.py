import os
import unittest
import uuid
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
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

    def insert_review(self, status="accepted", supersedes=None, valid_from=None, valid_until=None):
        review_id = uuid.uuid4()
        self.conn.execute(
            """
            INSERT INTO cci_lab.provider_platform_resolution_reviews (
                id, provider_platform_id, data_source_id,
                candidate_network_id, resolution_status, evidence_reference,
                reviewed_at, valid_from, valid_until, supersedes_review_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                review_id, self.platform_id, self.source_id,
                self.network_id if status == "accepted" else None,
                status,
                "synthetic://evidence/review" if status == "accepted" else None,
                self.now if status == "accepted" else None,
                valid_from or self.now - timedelta(minutes=1),
                valid_until,
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


    def test_pg_net_01_observation_rejects_platform_source_mismatch(self):
        other_source_id = uuid.uuid4()
        self.conn.execute(
            "INSERT INTO cci_lab.data_sources (id, source_key) VALUES (%s, %s)",
            (other_source_id, f"synthetic-{other_source_id.hex[:8]}"),
        )
        with self.assertRaises(errors.ForeignKeyViolation):
            with self.conn.transaction():
                self.conn.execute(
                    """
                    INSERT INTO cci_lab.provider_platform_observations (
                        id, provider_platform_id, data_source_id, capture_id,
                        observed_at, reported_chain_identifier_json, evidence_reference
                    ) VALUES (%s, %s, %s, %s, %s, '137'::jsonb, 'synthetic://evidence')
                    """,
                    (uuid.uuid4(), self.platform_id, other_source_id, uuid.uuid4(), self.now),
                )

    def test_pg_net_04_review_rejects_observation_from_another_platform(self):
        other_platform_id = uuid.uuid4()
        self.conn.execute(
            """
            INSERT INTO cci_lab.provider_platforms
                (id, data_source_id, provider_platform_key)
            VALUES (%s, %s, %s)
            """,
            (other_platform_id, self.source_id, f"synthetic-{other_platform_id.hex[:8]}"),
        )
        observation_id = uuid.uuid4()
        self.conn.execute(
            """
            INSERT INTO cci_lab.provider_platform_observations (
                id, provider_platform_id, data_source_id, capture_id,
                observed_at, reported_chain_identifier_json, evidence_reference
            ) VALUES (%s, %s, %s, %s, %s, '137'::jsonb, 'synthetic://evidence')
            """,
            (observation_id, other_platform_id, self.source_id, uuid.uuid4(), self.now),
        )
        with self.assertRaises(errors.ForeignKeyViolation):
            with self.conn.transaction():
                self.conn.execute(
                    """
                    INSERT INTO cci_lab.provider_platform_resolution_reviews (
                        id, provider_platform_id, data_source_id, based_on_observation_id,
                        candidate_network_id, resolution_status, evidence_reference,
                        reviewed_at, valid_from
                    ) VALUES (%s, %s, %s, %s, %s, 'accepted',
                              'synthetic://review', %s, %s)
                    """,
                    (
                        uuid.uuid4(), self.platform_id, self.source_id, observation_id,
                        self.network_id, self.now, self.now - timedelta(minutes=1),
                    ),
                )

    def test_pg_net_05_second_root_is_rejected_by_partial_unique_index(self):
        self.insert_review()
        with self.assertRaises(errors.UniqueViolation):
            with self.conn.transaction():
                self.conn.execute(
                    "ALTER TABLE cci_lab.provider_platform_resolution_reviews DISABLE TRIGGER trg_provider_platform_review_chain_guard"
                )
                self.insert_review()

    def test_pg_net_06_second_successor_is_rejected_by_partial_unique_index(self):
        root_id = self.insert_review()
        self.insert_review(status="pending_review", supersedes=root_id)
        with self.assertRaises(errors.UniqueViolation):
            with self.conn.transaction():
                self.conn.execute(
                    "ALTER TABLE cci_lab.provider_platform_resolution_reviews DISABLE TRIGGER trg_provider_platform_review_chain_guard"
                )
                self.insert_review(status="rejected", supersedes=root_id)

    def test_pg_net_07_successor_cannot_cross_platform_identity(self):
        other_platform_id = uuid.uuid4()
        self.conn.execute(
            """
            INSERT INTO cci_lab.provider_platforms
                (id, data_source_id, provider_platform_key)
            VALUES (%s, %s, %s)
            """,
            (other_platform_id, self.source_id, f"synthetic-{other_platform_id.hex[:8]}"),
        )
        other_root_id = uuid.uuid4()
        self.conn.execute(
            """
            INSERT INTO cci_lab.provider_platform_resolution_reviews (
                id, provider_platform_id, data_source_id, resolution_status, valid_from
            ) VALUES (%s, %s, %s, 'pending_review', %s)
            """,
            (other_root_id, other_platform_id, self.source_id, self.now - timedelta(minutes=1)),
        )
        self.insert_review()
        with self.assertRaises(errors.ForeignKeyViolation):
            with self.conn.transaction():
                self.conn.execute(
                    "ALTER TABLE cci_lab.provider_platform_resolution_reviews DISABLE TRIGGER trg_provider_platform_review_chain_guard"
                )
                self.insert_review(status="rejected", supersedes=other_root_id)

    def test_pg_net_08_non_head_review_cannot_be_superseded(self):
        root_id = self.insert_review()
        self.insert_review(status="pending_review", supersedes=root_id)
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.insert_review(status="rejected", supersedes=root_id)

    def test_pg_net_09_self_referential_review_chain_is_rejected(self):
        review_id = uuid.uuid4()
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.conn.execute(
                    """
                    INSERT INTO cci_lab.provider_platform_resolution_reviews (
                        id, provider_platform_id, data_source_id,
                        resolution_status, valid_from, supersedes_review_id
                    ) VALUES (%s, %s, %s, 'pending_review', %s, %s)
                    """,
                    (review_id, self.platform_id, self.source_id, self.now, review_id),
                )

    def test_pg_net_10_reviews_are_immutable(self):
        self.insert_review()
        with self.assertRaises(errors.ObjectNotInPrerequisiteState):
            with self.conn.transaction():
                self.conn.execute(
                    """
                    UPDATE cci_lab.provider_platform_resolution_reviews
                    SET resolution_status = 'rejected'
                    WHERE provider_platform_id = %s
                    """,
                    (self.platform_id,),
                )
        with self.assertRaises(errors.ObjectNotInPrerequisiteState):
            with self.conn.transaction():
                self.conn.execute(
                    "DELETE FROM cci_lab.provider_platform_resolution_reviews WHERE provider_platform_id = %s",
                    (self.platform_id,),
                )

    def test_pg_net_10_observations_reject_delete(self):
        self.insert_observation()
        with self.assertRaises(errors.ObjectNotInPrerequisiteState):
            with self.conn.transaction():
                self.conn.execute(
                    "DELETE FROM cci_lab.provider_platform_observations WHERE provider_platform_id = %s",
                    (self.platform_id,),
                )

    def test_pg_net_12_nonaccepted_review_cannot_publish_mapping(self):
        review_id = self.insert_review()
        for invalid_status in ("pending_review", "rejected", "ambiguous"):
            with self.subTest(invalid_status=invalid_status):
                with self.assertRaises(errors.CheckViolation):
                    with self.conn.transaction():
                        self.conn.execute(
                            """
                            INSERT INTO cci_lab.network_identifiers (
                                id, network_id, namespace, identifier_type, identifier_value,
                                observed_at, evidence_reference, provider_platform_id,
                                provider_data_source_id, provider_platform_resolution_review_id,
                                provider_platform_resolution_status
                            ) VALUES (%s, %s, 'synthetic:asset_platform_id', 'asset_platform_id',
                                      %s, %s, 'synthetic://evidence', %s, %s, %s, %s)
                            """,
                            (
                                uuid.uuid4(), self.network_id, self.platform_key, self.now,
                                self.platform_id, self.source_id, review_id, invalid_status,
                            ),
                        )

    def test_pg_net_13_mapping_network_must_match_accepted_review(self):
        review_id = self.insert_review()
        other_network_id = uuid.uuid4()
        self.conn.execute(
            "INSERT INTO cci_lab.networks (id, network_key) VALUES (%s, %s)",
            (other_network_id, f"synthetic-network-{other_network_id.hex[:8]}"),
        )
        with self.assertRaises(errors.ForeignKeyViolation):
            with self.conn.transaction():
                self.conn.execute(
                    """
                    INSERT INTO cci_lab.network_identifiers (
                        id, network_id, namespace, identifier_type, identifier_value,
                        observed_at, evidence_reference, provider_platform_id,
                        provider_data_source_id, provider_platform_resolution_review_id,
                        provider_platform_resolution_status
                    ) VALUES (%s, %s, 'synthetic:asset_platform_id', 'asset_platform_id',
                              %s, %s, 'synthetic://evidence', %s, %s, %s, 'accepted')
                    """,
                    (
                        uuid.uuid4(), other_network_id, self.platform_key, self.now,
                        self.platform_id, self.source_id, review_id,
                    ),
                )

    def test_pg_net_16_new_observation_does_not_revoke_current_mapping(self):
        review_id = self.insert_review()
        self.insert_mapping(review_id)
        self.insert_observation()
        count = self.conn.execute(
            """
            SELECT count(*) FROM cci_lab.provider_platform_mappings_current
            WHERE provider_platform_id = %s
            """,
            (self.platform_id,),
        ).fetchone()[0]
        self.assertEqual(count, 1)

    def test_pg_net_17_rejected_successor_revokes_mapping_when_effective(self):
        root_id = self.insert_review(valid_from=self.now - timedelta(minutes=2))
        self.insert_mapping(root_id)
        self.insert_review(
            status="rejected", supersedes=root_id,
            valid_from=self.now - timedelta(seconds=10),
        )
        resolution = self.conn.execute(
            """
            SELECT resolution_status FROM cci_lab.provider_platform_resolution_current
            WHERE provider_platform_id = %s
            """,
            (self.platform_id,),
        ).fetchone()
        mapping_count = self.conn.execute(
            """
            SELECT count(*) FROM cci_lab.provider_platform_mappings_current
            WHERE provider_platform_id = %s
            """,
            (self.platform_id,),
        ).fetchone()[0]
        self.assertEqual(resolution[0], "rejected")
        self.assertEqual(mapping_count, 0)

    def test_pg_net_18_future_successor_does_not_end_current_resolution(self):
        root_id = self.insert_review(valid_from=self.now - timedelta(minutes=2))
        self.insert_mapping(root_id)
        self.insert_review(
            status="pending_review", supersedes=root_id,
            valid_from=self.now + timedelta(days=1),
        )
        resolution = self.conn.execute(
            """
            SELECT resolution_status, effective_valid_until
            FROM cci_lab.provider_platform_resolution_current
            WHERE provider_platform_id = %s
            """,
            (self.platform_id,),
        ).fetchone()
        self.assertEqual(resolution[0], "accepted")
        self.assertIsNotNone(resolution[1])

    def test_pg_net_19_review_and_mapping_publication_roll_back_together(self):
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                review_id = self.insert_review()
                self.insert_mapping(review_id, identifier_value="wrong-literal")
        count = self.conn.execute(
            """
            SELECT count(*) FROM cci_lab.provider_platform_resolution_reviews
            WHERE provider_platform_id = %s
            """,
            (self.platform_id,),
        ).fetchone()[0]
        self.assertEqual(count, 0)

    def test_pg_net_20_two_sessions_cannot_create_competing_successors(self):
        root_id = self.insert_review(valid_from=self.now - timedelta(minutes=2))
        self.conn.commit()
        lock_acquired = threading.Event()
        second_attempting = threading.Event()
        release_first = threading.Event()

        def first_writer():
            with psycopg.connect(self.dsn) as conn:
                conn.execute(
                    "SELECT id FROM cci_lab.provider_platforms WHERE id = %s FOR UPDATE",
                    (self.platform_id,),
                )
                lock_acquired.set()
                if not release_first.wait(timeout=10):
                    raise TimeoutError("test coordination timed out")
                conn.execute(
                    """
                    INSERT INTO cci_lab.provider_platform_resolution_reviews (
                        id, provider_platform_id, data_source_id,
                        resolution_status, valid_from, supersedes_review_id
                    ) VALUES (%s, %s, %s, 'pending_review', %s, %s)
                    """,
                    (
                        uuid.uuid4(), self.platform_id, self.source_id,
                        self.now - timedelta(minutes=1), root_id,
                    ),
                )
                conn.commit()
                return "committed"

        def second_writer():
            if not lock_acquired.wait(timeout=10):
                raise TimeoutError("first writer did not acquire lock")
            with psycopg.connect(self.dsn) as conn:
                second_attempting.set()
                conn.execute(
                    "SELECT id FROM cci_lab.provider_platforms WHERE id = %s FOR UPDATE",
                    (self.platform_id,),
                )
                try:
                    conn.execute(
                        """
                        INSERT INTO cci_lab.provider_platform_resolution_reviews (
                            id, provider_platform_id, data_source_id,
                            resolution_status, valid_from, supersedes_review_id
                        ) VALUES (%s, %s, %s, 'rejected', %s, %s)
                        """,
                        (
                            uuid.uuid4(), self.platform_id, self.source_id,
                            self.now - timedelta(minutes=1), root_id,
                        ),
                    )
                    conn.commit()
                    return "committed"
                except errors.CheckViolation:
                    conn.rollback()
                    return "rejected_non_head"

        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(first_writer)
            second = pool.submit(second_writer)
            self.assertTrue(lock_acquired.wait(timeout=10))
            self.assertTrue(second_attempting.wait(timeout=10))
            time.sleep(0.1)
            release_first.set()
            outcomes = [first.result(timeout=15), second.result(timeout=15)]
        self.assertEqual(outcomes.count("committed"), 1)
        self.assertEqual(outcomes.count("rejected_non_head"), 1)
        successor_count = self.conn.execute(
            """
            SELECT count(*) FROM cci_lab.provider_platform_resolution_reviews
            WHERE supersedes_review_id = %s
            """,
            (root_id,),
        ).fetchone()[0]
        self.assertEqual(successor_count, 1)

    def test_pg_net_21_concurrent_mapping_publication_is_serialized(self):
        root_id = self.insert_review(valid_from=self.now - timedelta(minutes=2))
        self.insert_mapping(root_id)
        self.conn.commit()
        network_ids = [uuid.uuid4(), uuid.uuid4()]
        for network_id in network_ids:
            self.conn.execute(
                "INSERT INTO cci_lab.networks (id, network_key) VALUES (%s, %s)",
                (network_id, f"synthetic-network-{network_id.hex[:8]}"),
            )
        self.conn.commit()
        lock_acquired = threading.Event()
        second_attempting = threading.Event()
        release_first = threading.Event()

        def publish(network_id, first_writer):
            with psycopg.connect(self.dsn) as conn:
                if not first_writer:
                    second_attempting.set()
                conn.execute(
                    "SELECT id FROM cci_lab.provider_platforms WHERE id = %s FOR UPDATE",
                    (self.platform_id,),
                )
                if first_writer:
                    lock_acquired.set()
                    if not release_first.wait(timeout=10):
                        raise TimeoutError("test coordination timed out")
                review_id = uuid.uuid4()
                try:
                    conn.execute(
                        """
                        INSERT INTO cci_lab.provider_platform_resolution_reviews (
                            id, provider_platform_id, data_source_id, candidate_network_id,
                            resolution_status, evidence_reference, reviewed_at,
                            valid_from, supersedes_review_id
                        ) VALUES (%s, %s, %s, %s, 'accepted',
                                  'synthetic://review', %s, %s, %s)
                        """,
                        (
                            review_id, self.platform_id, self.source_id, network_id,
                            self.now, self.now - timedelta(minutes=1), root_id,
                        ),
                    )
                    conn.execute(
                        """
                        INSERT INTO cci_lab.network_identifiers (
                            id, network_id, namespace, identifier_type, identifier_value,
                            observed_at, evidence_reference, provider_platform_id,
                            provider_data_source_id, provider_platform_resolution_review_id,
                            provider_platform_resolution_status
                        ) VALUES (%s, %s, 'synthetic:asset_platform_id', 'asset_platform_id',
                                  %s, %s, 'synthetic://mapping', %s, %s, %s, 'accepted')
                        """,
                        (
                            uuid.uuid4(), network_id, self.platform_key, self.now,
                            self.platform_id, self.source_id, review_id,
                        ),
                    )
                    conn.commit()
                    return "committed"
                except errors.CheckViolation:
                    conn.rollback()
                    return "rejected_non_head"

        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(publish, network_ids[0], True)
            second = pool.submit(publish, network_ids[1], False)
            self.assertTrue(lock_acquired.wait(timeout=10))
            self.assertTrue(second_attempting.wait(timeout=10))
            time.sleep(0.1)
            release_first.set()
            outcomes = [first.result(timeout=15), second.result(timeout=15)]
        self.assertEqual(outcomes.count("committed"), 1)
        self.assertEqual(outcomes.count("rejected_non_head"), 1)
        self.assertEqual(
            self.conn.execute(
                """
                SELECT count(*) FROM cci_lab.provider_platform_resolution_reviews
                WHERE provider_platform_id = %s
                """,
                (self.platform_id,),
            ).fetchone()[0],
            2,
        )
        self.assertEqual(
            self.conn.execute(
                """
                SELECT count(*) FROM cci_lab.provider_platform_mappings_current
                WHERE provider_platform_id = %s
                """,
                (self.platform_id,),
            ).fetchone()[0],
            1,
        )

    def test_pg_net_22_jsonb_rejects_string_boolean_object_and_array(self):
        for invalid_json in ['"137"', "true", '{"chain":137}', "[137]"]:
            with self.subTest(invalid_json=invalid_json):
                with self.assertRaises(errors.CheckViolation):
                    with self.conn.transaction():
                        self.insert_observation(chain_json=invalid_json)

    def test_pg_net_23_jsonb_preserves_exact_decimal_value(self):
        self.insert_observation(chain_json="1.37125e2")
        value = self.conn.execute(
            """
            SELECT reported_chain_identifier_json::text
            FROM cci_lab.provider_platform_observations
            WHERE provider_platform_id = %s
            """,
            (self.platform_id,),
        ).fetchone()[0]
        self.assertEqual(Decimal(value), Decimal("137.125"))

    def test_pg_net_24_bitemporal_query_respects_known_at(self):
        root_id = self.insert_review(valid_from=self.now - timedelta(minutes=5))
        known_before_successor = datetime.now(timezone.utc)
        self.insert_review(
            status="rejected", supersedes=root_id,
            valid_from=self.now - timedelta(minutes=1),
        )
        valid_at = datetime.now(timezone.utc)
        before = self.conn.execute(
            """
            SELECT resolution_status
            FROM cci_lab.provider_platform_resolution_as_known(%s, %s)
            WHERE provider_platform_id = %s
            """,
            (valid_at, known_before_successor, self.platform_id),
        ).fetchone()
        after = self.conn.execute(
            """
            SELECT resolution_status
            FROM cci_lab.provider_platform_resolution_as_known(%s, %s)
            WHERE provider_platform_id = %s
            """,
            (valid_at, datetime.now(timezone.utc) + timedelta(seconds=1), self.platform_id),
        ).fetchone()
        self.assertEqual(before[0], "accepted")
        self.assertEqual(after[0], "rejected")

    def test_pg_net_25_bitemporal_query_uses_semi_open_validity(self):
        valid_from = self.now - timedelta(minutes=2)
        valid_until = self.now - timedelta(minutes=1)
        self.insert_review(valid_from=valid_from, valid_until=valid_until)
        known_at = datetime.now(timezone.utc) + timedelta(seconds=1)
        at_start = self.conn.execute(
            """
            SELECT count(*)
            FROM cci_lab.provider_platform_resolution_as_known(%s, %s)
            WHERE provider_platform_id = %s
            """,
            (valid_from, known_at, self.platform_id),
        ).fetchone()[0]
        at_end = self.conn.execute(
            """
            SELECT count(*)
            FROM cci_lab.provider_platform_resolution_as_known(%s, %s)
            WHERE provider_platform_id = %s
            """,
            (valid_until, known_at, self.platform_id),
        ).fetchone()[0]
        self.assertEqual(at_start, 1)
        self.assertEqual(at_end, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
