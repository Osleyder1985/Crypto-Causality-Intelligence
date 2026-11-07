import os
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
from psycopg import errors


ROOT = Path(__file__).resolve().parents[1]
_DEFAULT = object()
MIGRATIONS = [
    ROOT / "migrations" / "001_cci_root_entities.sql",
    ROOT / "migrations" / "002_source_policy_catalog.sql",
    ROOT / "migrations" / "003_provider_platform_reviews.sql",
    ROOT / "migrations" / "004_network_identifiers.sql",
    ROOT / "migrations" / "005_asset_representations_relationships.sql",
    ROOT / "migrations" / "006_asset_identity_resolution.sql",
]


class CCIAssetIdentityMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if "CCI_TEST_DATABASE_URL" not in os.environ:
            raise unittest.SkipTest(
                "CCI asset identity tests require CCI_TEST_DATABASE_URL; "
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
        self.rep_id = uuid.uuid4()
        self.conn.execute(
            """
            INSERT INTO cci.assets (id, canonical_code, display_name, asset_type)
            VALUES
                (%s, 'SYNTHETIC:IDENTITY-A', 'Synthetic identity A', 'crypto'),
                (%s, 'SYNTHETIC:IDENTITY-B', 'Synthetic identity B', 'crypto')
            """,
            (self.asset_a, self.asset_b),
        )
        self.conn.execute(
            """
            INSERT INTO cci.networks
                (id, network_key, display_name, network_family, environment)
            VALUES (%s, 'synthetic:identity-network', 'Synthetic identity network', 'evm', 'mainnet')
            """,
            (self.network_id,),
        )
        self.conn.execute(
            """
            INSERT INTO cci.identity_namespaces
                (namespace_key, scope_mode, target_level, description)
            VALUES
                ('synthetic:global-asset', 'global', 'asset', 'Synthetic global asset namespace'),
                ('synthetic:network-asset', 'network', 'asset', 'Synthetic network asset namespace'),
                ('synthetic:network-representation', 'network', 'representation',
                 'Synthetic network representation namespace')
            """
        )
        self.conn.execute(
            """
            INSERT INTO cci.asset_representations (
                id, asset_id, network_id, representation_kind, contract_address,
                observed_at, evidence_reference
            ) VALUES (%s, %s, %s, 'token_contract', '0xsynthetic123',
                      %s, 'synthetic://identity-representation')
            """,
            (self.rep_id, self.asset_a, self.network_id, self.now),
        )

    def tearDown(self):
        self.conn.rollback()
        self.conn.close()

    def insert_review(self, *, namespace="synthetic:global-asset", network_id=_DEFAULT,
                      external_identifier="SYNTHETIC:ASSET-ID", status="accepted",
                      candidate_asset_id=_DEFAULT, candidate_representation_id=None,
                      supersedes=None, valid_from=_DEFAULT, evidence_reference=_DEFAULT,
                      reviewed_at=_DEFAULT):
        review_id = uuid.uuid4()
        if network_id is _DEFAULT:
            network_id = self.network_id if namespace != "synthetic:global-asset" else None
        if candidate_asset_id is _DEFAULT:
            candidate_asset_id = self.asset_a if status == "accepted" and candidate_representation_id is None else None
        if valid_from is _DEFAULT:
            valid_from = self.now - timedelta(minutes=1) if status == "accepted" else None
        if evidence_reference is _DEFAULT:
            evidence_reference = "synthetic://asset-identity/review" if status == "accepted" else None
        if reviewed_at is _DEFAULT:
            reviewed_at = self.now if status == "accepted" else None
        self.conn.execute(
            """
            INSERT INTO cci.asset_identity_resolution_reviews (
                id, namespace, network_id, external_identifier,
                candidate_asset_id, candidate_asset_representation_id,
                resolution_status, evidence_reference, observed_at, reviewed_at,
                valid_from, supersedes_review_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                review_id, namespace, network_id, external_identifier,
                candidate_asset_id, candidate_representation_id, status,
                evidence_reference, self.now, reviewed_at, valid_from, supersedes,
            ),
        )
        return review_id

    def insert_asset_identifier(self, review_id, *, asset_id=None, namespace="synthetic:global-asset",
                                external_identifier="SYNTHETIC:ASSET-ID", network_id=_DEFAULT):
        identifier_id = uuid.uuid4()
        if network_id is _DEFAULT:
            network_id = None if namespace == "synthetic:global-asset" else self.network_id
        self.conn.execute(
            """
            INSERT INTO cci.asset_identifiers (
                id, asset_id, namespace, external_identifier, network_id,
                valid_from, evidence_reference, resolution_review_id
            ) VALUES (%s, %s, %s, %s, %s, %s, 'synthetic://asset-identifier', %s)
            """,
            (
                identifier_id, asset_id or self.asset_a, namespace, external_identifier,
                network_id, self.now, review_id,
            ),
        )
        return identifier_id

    def insert_representation_identifier(self, review_id, *, representation_id=None,
                                         external_identifier="0xsynthetic123"):
        identifier_id = uuid.uuid4()
        self.conn.execute(
            """
            INSERT INTO cci.asset_representation_identifiers (
                id, asset_representation_id, network_id, namespace, external_identifier,
                valid_from, evidence_reference, resolution_review_id
            ) VALUES (%s, %s, %s, 'synthetic:network-representation', %s,
                      %s, 'synthetic://representation-identifier', %s)
            """,
            (
                identifier_id, representation_id or self.rep_id, self.network_id,
                external_identifier, self.now, review_id,
            ),
        )
        return identifier_id

    def test_migration_installs_review_and_both_mapping_tables(self):
        tables = {
            row[0] for row in self.conn.execute(
                """
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'cci' AND table_type = 'BASE TABLE'
                """
            ).fetchall()
        }
        self.assertTrue({
            "asset_identity_resolution_reviews",
            "asset_identifiers",
            "asset_representation_identifiers",
        }.issubset(tables))
        self.assertEqual(
            self.conn.execute(
                "SELECT version FROM cci.schema_migrations WHERE version = '006_asset_identity_resolution'"
            ).fetchone()[0],
            "006_asset_identity_resolution",
        )

    def test_global_and_network_namespace_scopes_are_enforced(self):
        self.insert_review(namespace="synthetic:global-asset", network_id=None)
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.insert_review(namespace="synthetic:global-asset", network_id=self.network_id)
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.insert_review(namespace="synthetic:network-asset", network_id=None)

    def test_namespace_target_level_rejects_wrong_candidate_kind(self):
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.insert_review(
                    namespace="synthetic:global-asset",
                    candidate_asset_id=None,
                    candidate_representation_id=self.rep_id,
                )
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.insert_review(
                    namespace="synthetic:network-representation",
                    candidate_asset_id=self.asset_a,
                    candidate_representation_id=None,
                )

    def test_accepted_review_requires_exactly_one_destination_and_complete_evidence(self):
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.insert_review(candidate_asset_id=None)
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.insert_review(evidence_reference=" ")
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.insert_review(reviewed_at=None)
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.insert_review(valid_from=None)

    def test_representation_candidate_must_match_review_network(self):
        other_network = uuid.uuid4()
        self.conn.execute(
            """
            INSERT INTO cci.networks
                (id, network_key, display_name, network_family, environment)
            VALUES (%s, 'synthetic:other-network', 'Other network', 'evm', 'mainnet')
            """,
            (other_network,),
        )
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.insert_review(
                    namespace="synthetic:network-representation",
                    network_id=other_network,
                    candidate_asset_id=None,
                    candidate_representation_id=self.rep_id,
                )

    def test_review_chain_is_linear_and_scoped_to_exact_identity_key(self):
        root = self.insert_review(external_identifier="SYNTHETIC:CHAIN")
        successor = self.insert_review(
            external_identifier="SYNTHETIC:CHAIN",
            supersedes=root,
            valid_from=self.now,
            status="rejected",
        )
        self.assertIsNotNone(successor)
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.insert_review(external_identifier="SYNTHETIC:CHAIN")
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.insert_review(
                    external_identifier="SYNTHETIC:OTHER-KEY",
                    supersedes=successor,
                    status="rejected",
                )

    def test_global_root_uniqueness_treats_null_network_as_equal(self):
        self.insert_review(external_identifier="SYNTHETIC:NULL-SCOPE")
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.insert_review(external_identifier="SYNTHETIC:NULL-SCOPE")

    def test_review_and_mappings_are_append_only(self):
        review_id = self.insert_review()
        with self.assertRaises(errors.ObjectNotInPrerequisiteState):
            with self.conn.transaction():
                self.conn.execute(
                    "UPDATE cci.asset_identity_resolution_reviews SET resolution_status = 'rejected' WHERE id = %s",
                    (review_id,),
                )
        identifier_id = self.insert_asset_identifier(review_id)
        with self.assertRaises(errors.ObjectNotInPrerequisiteState):
            with self.conn.transaction():
                self.conn.execute(
                    "DELETE FROM cci.asset_identifiers WHERE id = %s",
                    (identifier_id,),
                )

    def test_accepted_asset_identifier_mapping_matches_review_exactly(self):
        review_id = self.insert_review(external_identifier="SYNTHETIC:ASSET-A")
        identifier_id = self.insert_asset_identifier(
            review_id, external_identifier="SYNTHETIC:ASSET-A"
        )
        self.assertIsNotNone(
            self.conn.execute(
                "SELECT id FROM cci.asset_identifiers WHERE id = %s",
                (identifier_id,),
            ).fetchone()
        )

    def test_asset_identifier_mapping_requires_null_safe_network_scope_match(self):
        review_id = self.insert_review(
            namespace="synthetic:network-asset",
            external_identifier="SYNTHETIC:NETWORK-ASSET",
        )
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.insert_asset_identifier(
                    review_id, namespace="synthetic:network-asset",
                    external_identifier="SYNTHETIC:NETWORK-ASSET", network_id=None,
                )

    def test_asset_identifier_composite_fk_rejects_wrong_asset_or_identifier(self):
        review_id = self.insert_review(external_identifier="SYNTHETIC:EXACT")
        with self.assertRaises(errors.ForeignKeyViolation):
            with self.conn.transaction():
                self.insert_asset_identifier(
                    review_id, asset_id=self.asset_b, external_identifier="SYNTHETIC:EXACT"
                )
        with self.assertRaises(errors.ForeignKeyViolation):
            with self.conn.transaction():
                self.insert_asset_identifier(
                    review_id, external_identifier="SYNTHETIC:DIFFERENT"
                )

    def test_accepted_representation_identifier_matches_review_representation_and_network(self):
        review_id = self.insert_review(
            namespace="synthetic:network-representation",
            network_id=self.network_id,
            candidate_asset_id=None,
            candidate_representation_id=self.rep_id,
            external_identifier="0xsynthetic123",
        )
        identifier_id = self.insert_representation_identifier(review_id)
        self.assertIsNotNone(
            self.conn.execute(
                "SELECT id FROM cci.asset_representation_identifiers WHERE id = %s",
                (identifier_id,),
            ).fetchone()
        )

    def test_representation_identifier_rejects_wrong_network_or_literal(self):
        review_id = self.insert_review(
            namespace="synthetic:network-representation",
            candidate_asset_id=None,
            candidate_representation_id=self.rep_id,
            external_identifier="0xsynthetic123",
        )
        with self.assertRaises(errors.ForeignKeyViolation):
            with self.conn.transaction():
                self.conn.execute(
                    """
                    INSERT INTO cci.asset_representation_identifiers (
                        id, asset_representation_id, network_id, namespace,
                        external_identifier, valid_from, evidence_reference,
                        resolution_review_id
                    ) VALUES (%s, %s, %s, 'synthetic:network-representation',
                              '0xsynthetic123', %s, 'synthetic://bad', %s)
                    """,
                    (uuid.uuid4(), self.rep_id, uuid.uuid4(), self.now, review_id),
                )
        with self.assertRaises(errors.ForeignKeyViolation):
            with self.conn.transaction():
                self.insert_representation_identifier(
                    review_id, external_identifier="0xother-address"
                )

    def test_two_sessions_cannot_create_competing_root_reviews_for_same_global_key(self):
        self.conn.commit()

        def create_root():
            with psycopg.connect(os.environ["CCI_TEST_DATABASE_URL"]) as conn:
                try:
                    conn.execute(
                        """
                        INSERT INTO cci.asset_identity_resolution_reviews (
                            id, namespace, network_id, external_identifier,
                            resolution_status, observed_at
                        ) VALUES (%s, 'synthetic:global-asset', NULL,
                                  'SYNTHETIC:CONCURRENT', 'pending_review', %s)
                        """,
                        (uuid.uuid4(), self.now),
                    )
                    conn.commit()
                    return "accepted"
                except errors.CheckViolation:
                    conn.rollback()
                    return "rejected"

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda _: create_root(), range(2)))
        self.assertCountEqual(outcomes, ["accepted", "rejected"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
