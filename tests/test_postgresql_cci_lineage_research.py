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
    ROOT / "migrations" / "005_asset_representations_relationships.sql",
    ROOT / "migrations" / "006_asset_identity_resolution.sql",
    ROOT / "migrations" / "007_market_instrument_catalog.sql",
    ROOT / "migrations" / "008_ingestion_requests_dataset_sources.sql",
    ROOT / "migrations" / "009_lineage_validation_research_runs.sql",
]


class CCILineageResearchMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if "CCI_TEST_DATABASE_URL" not in os.environ:
            raise unittest.SkipTest(
                "CCI lineage/research tests require CCI_TEST_DATABASE_URL; "
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
        self.suffix = uuid.uuid4().hex[:12]
        self.dataset_a = uuid.uuid4()
        self.dataset_b = uuid.uuid4()
        self.dataset_c = uuid.uuid4()
        self.ingestion_run_id = uuid.uuid4()
        self.transformation_id = uuid.uuid4()
        self.transformation_run_id = uuid.uuid4()
        self.experiment_id = uuid.uuid4()
        self.conn.execute(
            """
            INSERT INTO cci.datasets (
                id, dataset_key, version, stage, data_format, schema_name,
                schema_version, storage_uri, checksum_sha256, retention_status
            ) VALUES
                (%s, %s, 1, 'source_capture', 'parquet',
                 'synthetic', '1', 'synthetic://lineage/a', %s, 'active'),
                (%s, %s, 1, 'derived', 'parquet',
                 'synthetic', '1', 'synthetic://lineage/b', %s, 'active'),
                (%s, %s, 1, 'derived', 'parquet',
                 'synthetic', '1', 'synthetic://lineage/c', %s, 'active')
            """,
            (
                self.dataset_a, f"synthetic-lineage-a-{self.suffix}", "a" * 64,
                self.dataset_b, f"synthetic-lineage-b-{self.suffix}", "b" * 64,
                self.dataset_c, f"synthetic-lineage-c-{self.suffix}", "c" * 64,
            ),
        )
        self.conn.execute(
            """
            INSERT INTO cci.ingestion_runs (id, run_key, started_at, status)
            VALUES (%s, %s, %s, 'running')
            """,
            (self.ingestion_run_id, f"synthetic-lineage-ingest-{self.suffix}", self.now),
        )
        self.conn.execute(
            """
            INSERT INTO cci.transformations
                (id, transformation_key, version, description)
            VALUES (%s, %s, '1', 'Synthetic transform')
            """,
            (self.transformation_id, f"synthetic-lineage-transform-{self.suffix}"),
        )
        self.conn.execute(
            """
            INSERT INTO cci.transformation_runs (
                id, transformation_id, ingestion_run_id, started_at, status
            ) VALUES (%s, %s, %s, %s, 'running')
            """,
            (self.transformation_run_id, self.transformation_id, self.ingestion_run_id, self.now),
        )
        self.conn.execute(
            """
            INSERT INTO cci.research_experiments
                (id, experiment_key, title, objective, status)
            VALUES (%s, %s, 'Synthetic experiment',
                    'Test lineage and research records', 'planned')
            """,
            (self.experiment_id, f"synthetic-lineage-experiment-{self.suffix}"),
        )

    def tearDown(self):
        self.conn.rollback()
        self.conn.close()

    def insert_lineage(self, input_id, output_id):
        self.conn.execute(
            """
            INSERT INTO cci.dataset_lineage
                (input_dataset_id, output_dataset_id, transformation_run_id)
            VALUES (%s, %s, %s)
            """,
            (input_id, output_id, self.transformation_run_id),
        )

    def test_migration_installs_all_seven_remaining_entities_and_completes_fk_inventory(self):
        tables = {
            row[0] for row in self.conn.execute(
                """
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'cci' AND table_type = 'BASE TABLE'
                """
            ).fetchall()
        }
        self.assertTrue({
            "dataset_lineage", "data_validations", "transformation_runs",
            "research_experiment_runs", "research_run_artifacts",
            "research_hypotheses", "experiment_datasets",
        }.issubset(tables))
        # 34 domain tables plus the operational migration ledger.
        self.assertEqual(len(tables), 35)
        self.assertEqual(
            self.conn.execute(
                "SELECT version FROM cci.schema_migrations WHERE version = '009_lineage_validation_research_runs'"
            ).fetchone()[0],
            "009_lineage_validation_research_runs",
        )
        fk_count = self.conn.execute(
            """
            SELECT count(*) FROM pg_constraint con
            JOIN pg_namespace n ON n.oid = con.connamespace
            WHERE n.nspname = 'cci' AND con.contype = 'f'
            """
        ).fetchone()[0]
        self.assertEqual(fk_count, 60)

    def test_lineage_accepts_directed_input_output_edge_and_rejects_self_edge(self):
        self.insert_lineage(self.dataset_a, self.dataset_b)
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.insert_lineage(self.dataset_a, self.dataset_a)

    def test_lineage_rejects_transitive_cycle(self):
        self.insert_lineage(self.dataset_a, self.dataset_b)
        self.insert_lineage(self.dataset_b, self.dataset_c)
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.insert_lineage(self.dataset_c, self.dataset_a)

    def test_concurrent_opposite_lineage_edges_cannot_create_cycle(self):
        self.conn.commit()

        def insert_edge(input_id, output_id):
            with psycopg.connect(os.environ["CCI_TEST_DATABASE_URL"]) as conn:
                try:
                    conn.execute(
                        """
                        INSERT INTO cci.dataset_lineage
                            (input_dataset_id, output_dataset_id, transformation_run_id)
                        VALUES (%s, %s, %s)
                        """,
                        (input_id, output_id, self.transformation_run_id),
                    )
                    conn.commit()
                    return "accepted"
                except errors.CheckViolation:
                    conn.rollback()
                    return "rejected"

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(insert_edge, self.dataset_a, self.dataset_b),
                pool.submit(insert_edge, self.dataset_b, self.dataset_a),
            ]
            outcomes = [future.result() for future in futures]
        self.assertCountEqual(outcomes, ["accepted", "rejected"])

    def test_dataset_lineage_is_append_only(self):
        self.insert_lineage(self.dataset_a, self.dataset_b)
        with self.assertRaises(errors.ObjectNotInPrerequisiteState):
            with self.conn.transaction():
                self.conn.execute(
                    """
                    DELETE FROM cci.dataset_lineage
                    WHERE input_dataset_id = %s AND output_dataset_id = %s
                    """,
                    (self.dataset_a, self.dataset_b),
                )

    def test_data_validation_accepts_optional_ingestion_run_and_object_details(self):
        validation_id = uuid.uuid4()
        self.conn.execute(
            """
            INSERT INTO cci.data_validations (
                id, dataset_id, ingestion_run_id, validation_suite,
                validation_version, status, checked_at, checks_total,
                checks_passed, checks_failed, details
            ) VALUES (%s, %s, %s, 'synthetic-suite', '1', 'passed',
                      %s, 3, 3, 0, '{"source":"synthetic"}')
            """,
            (validation_id, self.dataset_a, self.ingestion_run_id, self.now),
        )
        self.assertIsNotNone(
            self.conn.execute(
                "SELECT id FROM cci.data_validations WHERE id = %s",
                (validation_id,),
            ).fetchone()
        )

    def test_data_validation_rejects_inconsistent_counts_and_non_object_details(self):
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.conn.execute(
                    """
                    INSERT INTO cci.data_validations (
                        id, dataset_id, validation_suite, validation_version,
                        status, checked_at, checks_total, checks_passed, checks_failed
                    ) VALUES (%s, %s, 'suite', '1', 'failed', %s, 2, 2, 1)
                    """,
                    (uuid.uuid4(), self.dataset_a, self.now),
                )
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.conn.execute(
                    """
                    INSERT INTO cci.data_validations (
                        id, dataset_id, validation_suite, validation_version,
                        status, checked_at, checks_total, checks_passed, checks_failed,
                        details
                    ) VALUES (%s, %s, 'suite', '1', 'passed', %s, 0, 0, 0, '[]'::jsonb)
                    """,
                    (uuid.uuid4(), self.dataset_a, self.now),
                )

    def test_transformation_run_enforces_state_finish_and_json_parameters(self):
        run_id = uuid.uuid4()
        self.conn.execute(
            """
            INSERT INTO cci.transformation_runs (
                id, transformation_id, started_at, status, parameters
            ) VALUES (%s, %s, %s, 'running', '{"scale":"0.0001"}')
            """,
            (run_id, self.transformation_id, self.now),
        )
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.conn.execute(
                    """
                    INSERT INTO cci.transformation_runs (
                        id, transformation_id, started_at, status, finished_at
                    ) VALUES (%s, %s, %s, 'succeeded', NULL)
                    """,
                    (uuid.uuid4(), self.transformation_id, self.now),
                )

    def test_research_experiment_run_enforces_transition_and_terminal_immutability(self):
        run_id = uuid.uuid4()
        self.conn.execute(
            """
            INSERT INTO cci.research_experiment_runs (
                id, experiment_id, run_key, status, code_commit, protocol_version
            ) VALUES (%s, %s, 'synthetic-run-1', 'queued', 'abc123', '1')
            """,
            (run_id, self.experiment_id),
        )
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.conn.execute(
                    "UPDATE cci.research_experiment_runs SET status = 'succeeded', finished_at = %s WHERE id = %s",
                    (self.now, run_id),
                )
        self.conn.execute(
            """
            UPDATE cci.research_experiment_runs
            SET status = 'running', started_at = %s
            WHERE id = %s
            """,
            (self.now, run_id),
        )
        self.conn.execute(
            """
            UPDATE cci.research_experiment_runs
            SET status = 'succeeded', finished_at = %s, metrics = '{"sharpe":"1.25"}'
            WHERE id = %s
            """,
            (self.now + timedelta(seconds=1), run_id),
        )
        with self.assertRaises(errors.ObjectNotInPrerequisiteState):
            with self.conn.transaction():
                self.conn.execute(
                    "UPDATE cci.research_experiment_runs SET error_summary = 'mutated' WHERE id = %s",
                    (run_id,),
                )

    def test_research_experiment_run_identity_fields_are_immutable(self):
        run_id = uuid.uuid4()
        self.conn.execute(
            """
            INSERT INTO cci.research_experiment_runs (
                id, experiment_id, run_key, status, code_commit, protocol_version
            ) VALUES (%s, %s, 'synthetic-run-2', 'queued', 'abc123', '1')
            """,
            (run_id, self.experiment_id),
        )
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.conn.execute(
                    "UPDATE cci.research_experiment_runs SET code_commit = 'different' WHERE id = %s",
                    (run_id,),
                )

    def test_research_run_artifact_checks_hash_size_and_uniqueness(self):
        run_id = uuid.uuid4()
        self.conn.execute(
            """
            INSERT INTO cci.research_experiment_runs (
                id, experiment_id, run_key, status, code_commit, protocol_version
            ) VALUES (%s, %s, 'artifact-run', 'queued', 'abc123', '1')
            """,
            (run_id, self.experiment_id),
        )
        artifact_id = uuid.uuid4()
        params = (
            artifact_id, run_id, "summary", "synthetic://artifact/summary",
            "application/json", "json", "e" * 64, 12, "research",
        )
        self.conn.execute(
            """
            INSERT INTO cci.research_run_artifacts (
                id, run_id, artifact_role, logical_uri, media_type,
                format, sha256, byte_size, retention_class
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            params,
        )
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.conn.execute(
                    """
                    INSERT INTO cci.research_run_artifacts (
                        id, run_id, artifact_role, logical_uri, media_type,
                        format, sha256, byte_size, retention_class
                    ) VALUES (%s, %s, 'summary', 'synthetic://bad', 'application/json',
                              'json', %s, -1, 'research')
                    """,
                    (uuid.uuid4(), run_id, "F" * 64),
                )
        with self.assertRaises(errors.UniqueViolation):
            with self.conn.transaction():
                self.conn.execute(
                    """
                    INSERT INTO cci.research_run_artifacts (
                        id, run_id, artifact_role, logical_uri, media_type,
                        format, sha256, byte_size, retention_class
                    ) VALUES (%s, %s, 'summary', 'synthetic://artifact/summary',
                              'application/json', 'json', %s, 12, 'research')
                    """,
                    (uuid.uuid4(), run_id, "e" * 64),
                )

    def test_research_hypothesis_and_experiment_dataset_associations(self):
        hypothesis_id = uuid.uuid4()
        self.conn.execute(
            """
            INSERT INTO cci.research_hypotheses (
                id, experiment_id, hypothesis_key, statement, alternative_explanations, status
            ) VALUES (%s, %s, 'synthetic-h1', 'Synthetic causal hypothesis',
                      '["confounding","reverse_causality"]', 'proposed')
            """,
            (hypothesis_id, self.experiment_id),
        )
        self.conn.execute(
            """
            INSERT INTO cci.experiment_datasets (experiment_id, dataset_id, dataset_role)
            VALUES (%s, %s, 'input')
            """,
            (self.experiment_id, self.dataset_a),
        )
        with self.assertRaises(errors.CheckViolation):
            with self.conn.transaction():
                self.conn.execute(
                    """
                    INSERT INTO cci.research_hypotheses (
                        id, experiment_id, hypothesis_key, statement,
                        alternative_explanations, status
                    ) VALUES (%s, %s, 'bad-json', 'Bad explanations',
                              '{}'::jsonb, 'proposed')
                    """,
                    (uuid.uuid4(), self.experiment_id),
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
