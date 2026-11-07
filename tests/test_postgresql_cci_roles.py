import os
import unittest
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
    ROOT / "migrations" / "010_runtime_role_bootstrap.sql",
]


class CCIRuntimeRoleBootstrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if "CCI_TEST_DATABASE_URL" not in os.environ:
            raise unittest.SkipTest(
                "CCI role tests require CCI_TEST_DATABASE_URL; "
                "run them through the dedicated PostgreSQL workflow."
            )
        cls.dsn = os.environ["CCI_TEST_DATABASE_URL"]
        with psycopg.connect(cls.dsn, autocommit=True) as conn:
            conn.execute("DROP SCHEMA IF EXISTS cci CASCADE")
            for migration_path in MIGRATIONS:
                conn.execute(migration_path.read_text(encoding="utf-8"), prepare=False)

    def setUp(self):
        self.conn = psycopg.connect(os.environ["CCI_TEST_DATABASE_URL"])

    def tearDown(self):
        try:
            self.conn.execute("RESET ROLE")
        except Exception:
            pass
        self.conn.rollback()
        self.conn.close()

    def test_migration_creates_all_runtime_groups_as_nologin(self):
        roles = {
            row[0]: row[1]
            for row in self.conn.execute(
                """
                SELECT rolname, rolcanlogin
                FROM pg_roles
                WHERE rolname LIKE 'cci_%'
                """
            ).fetchall()
        }
        expected = {
            "cci_owner", "cci_migrator", "cci_catalog_writer", "cci_policy_admin",
            "cci_policy_evaluator", "cci_ingest_writer", "cci_identity_resolver",
            "cci_transform_writer", "cci_research_writer", "cci_reader",
        }
        self.assertTrue(expected.issubset(roles))
        self.assertTrue(all(roles[name] is False for name in expected))

    def test_owner_controls_schema_and_all_business_tables(self):
        schema_owner = self.conn.execute(
            """
            SELECT r.rolname
            FROM pg_namespace n JOIN pg_roles r ON r.oid = n.nspowner
            WHERE n.nspname = 'cci'
            """
        ).fetchone()[0]
        self.assertEqual(schema_owner, "cci_owner")
        non_owner_tables = self.conn.execute(
            """
            SELECT count(*)
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            JOIN pg_roles r ON r.oid = c.relowner
            WHERE n.nspname = 'cci'
              AND c.relkind IN ('r', 'p')
              AND r.rolname <> 'cci_owner'
            """
        ).fetchone()[0]
        self.assertEqual(non_owner_tables, 0)

    def test_migrator_is_member_of_owner_and_can_create_in_schema(self):
        member = self.conn.execute(
            "SELECT pg_has_role('cci_migrator', 'cci_owner', 'MEMBER')"
        ).fetchone()[0]
        self.assertTrue(member)
        self.assertTrue(
            self.conn.execute(
                "SELECT has_schema_privilege('cci_migrator', 'cci', 'CREATE')"
            ).fetchone()[0]
        )

    def test_application_roles_have_usage_but_no_schema_create(self):
        roles = [
            "cci_catalog_writer", "cci_policy_admin", "cci_policy_evaluator",
            "cci_ingest_writer", "cci_identity_resolver", "cci_transform_writer",
            "cci_research_writer", "cci_reader",
        ]
        for role in roles:
            self.assertTrue(
                self.conn.execute(
                    "SELECT has_schema_privilege(%s, 'cci', 'USAGE')",
                    (role,),
                ).fetchone()[0]
            )
            self.assertFalse(
                self.conn.execute(
                    "SELECT has_schema_privilege(%s, 'cci', 'CREATE')",
                    (role,),
                ).fetchone()[0]
            )

    def test_reader_can_select_approved_views_but_not_base_tables(self):
        self.assertTrue(
            self.conn.execute(
                """
                SELECT has_table_privilege(
                    'cci_reader', 'cci.provider_platform_mappings_current', 'SELECT'
                )
                """
            ).fetchone()[0]
        )
        self.assertFalse(
            self.conn.execute(
                "SELECT has_table_privilege('cci_reader', 'cci.assets', 'SELECT')"
            ).fetchone()[0]
        )
        self.assertFalse(
            self.conn.execute(
                """
                SELECT has_function_privilege(
                    'cci_reader',
                    'cci.provider_platform_resolution_as_known(timestamptz,timestamptz)',
                    'EXECUTE'
                )
                """
            ).fetchone()[0]
        )
        self.assertTrue(
            self.conn.execute(
                """
                SELECT has_function_privilege(
                    'cci_identity_resolver',
                    'cci.provider_platform_resolution_as_known(timestamptz,timestamptz)',
                    'EXECUTE'
                )
                """
            ).fetchone()[0]
        )

    def test_service_roles_have_no_direct_table_dml(self):
        for role, table in (
            ("cci_catalog_writer", "cci.assets"),
            ("cci_policy_evaluator", "cci.policy_evaluations"),
            ("cci_ingest_writer", "cci.ingestion_requests"),
            ("cci_identity_resolver", "cci.asset_identifiers"),
            ("cci_transform_writer", "cci.dataset_lineage"),
            ("cci_research_writer", "cci.research_experiment_runs"),
            ("cci_reader", "cci.datasets"),
        ):
            for privilege in ("INSERT", "UPDATE", "DELETE", "TRUNCATE"):
                self.assertFalse(
                    self.conn.execute(
                        "SELECT has_table_privilege(%s, %s, %s)",
                        (role, table, privilege),
                    ).fetchone()[0],
                    f"{role} unexpectedly has {privilege} on {table}",
                )

    def test_reader_session_cannot_read_base_table_or_insert_but_can_read_view(self):
        self.conn.execute("SET ROLE cci_reader")
        self.conn.execute("SELECT * FROM cci.provider_platform_mappings_current LIMIT 0")
        with self.assertRaises(errors.InsufficientPrivilege):
            with self.conn.transaction():
                self.conn.execute("SELECT * FROM cci.assets LIMIT 0")
        with self.assertRaises(errors.InsufficientPrivilege):
            with self.conn.transaction():
                self.conn.execute(
                    """
                    INSERT INTO cci.assets (id, canonical_code, display_name, asset_type)
                    VALUES (gen_random_uuid(), 'SYNTHETIC:FORBIDDEN', 'Forbidden', 'crypto')
                    """
                )

    def test_catalog_writer_session_is_read_only_until_domain_functions_exist(self):
        self.conn.execute("SET ROLE cci_catalog_writer")
        self.conn.execute("SELECT * FROM cci.assets LIMIT 0")
        with self.assertRaises(errors.InsufficientPrivilege):
            with self.conn.transaction():
                self.conn.execute(
                    """
                    INSERT INTO cci.assets (id, canonical_code, display_name, asset_type)
                    VALUES (gen_random_uuid(), 'SYNTHETIC:FORBIDDEN2', 'Forbidden', 'crypto')
                    """
                )

    def test_migration_ledger_records_role_bootstrap(self):
        self.assertEqual(
            self.conn.execute(
                "SELECT version FROM cci.schema_migrations WHERE version = '010_runtime_role_bootstrap'"
            ).fetchone()[0],
            "010_runtime_role_bootstrap",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
