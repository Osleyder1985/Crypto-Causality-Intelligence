import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import psycopg


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "postgresql" / "migrate.py"
MANIFEST = ROOT / "migrations" / "manifest.json"


def run_runner(*extra_args, manifest=MANIFEST):
    return subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "--dsn",
            os.environ["CCI_TEST_DATABASE_URL"],
            "--manifest",
            str(manifest),
            *extra_args,
        ],
        cwd=ROOT,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        check=False,
    )


class CCIMigrationRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if "CCI_TEST_DATABASE_URL" not in os.environ:
            raise unittest.SkipTest(
                "Migration runner tests require CCI_TEST_DATABASE_URL; "
                "run them through the dedicated PostgreSQL workflow."
            )
        with psycopg.connect(os.environ["CCI_TEST_DATABASE_URL"], autocommit=True) as conn:
            conn.execute("DROP SCHEMA IF EXISTS cci CASCADE")
        result = run_runner()
        if result.returncode != 0:
            raise RuntimeError(
                "migration runner failed during clean install:\n"
                + result.stdout
                + "\n"
                + result.stderr
            )

    def setUp(self):
        self.conn = psycopg.connect(os.environ["CCI_TEST_DATABASE_URL"])

    def tearDown(self):
        self.conn.rollback()
        self.conn.close()

    def test_clean_install_records_all_eleven_migrations_and_checksums(self):
        rows = self.conn.execute(
            """
            SELECT version, checksum_sha256, applied_by
            FROM cci.schema_migrations
            ORDER BY version
            """
        ).fetchall()
        self.assertEqual(len(rows), 11)
        self.assertTrue(all(len(checksum) == 64 for _, checksum, _ in rows))
        self.assertTrue(all(applied_by for _, _, applied_by in rows))

    def test_verify_only_succeeds_without_applying_or_mutating(self):
        before = self.conn.execute(
            "SELECT version, checksum_sha256 FROM cci.schema_migrations ORDER BY version"
        ).fetchall()
        result = run_runner("--verify-only")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        after = self.conn.execute(
            "SELECT version, checksum_sha256 FROM cci.schema_migrations ORDER BY version"
        ).fetchall()
        self.assertEqual(before, after)
        self.assertIn("OK: 11 migrations verified", result.stdout)

    def test_runner_rerun_is_idempotent_and_skips_applied_migrations(self):
        result = run_runner()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("SKIPPED  001_cci_root_entities", result.stdout)
        self.assertIn("OK: 11 migrations verified", result.stdout)

    def test_database_checksum_drift_is_detected(self):
        original = self.conn.execute(
            """
            SELECT checksum_sha256
            FROM cci.schema_migrations
            WHERE version = '003_provider_platform_reviews'
            """
        ).fetchone()[0]
        self.conn.execute(
            """
            UPDATE cci.schema_migrations
            SET checksum_sha256 = %s
            WHERE version = '003_provider_platform_reviews'
            """,
            ("0" * 64,),
        )
        self.conn.commit()
        result = run_runner("--verify-only")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("database checksum mismatch", result.stderr)
        self.conn.execute(
            """
            UPDATE cci.schema_migrations
            SET checksum_sha256 = %s
            WHERE version = '003_provider_platform_reviews'
            """,
            (original,),
        )
        self.conn.commit()

    def test_manifest_or_sql_file_drift_is_detected_before_database_access(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
            for entry in manifest["migrations"]:
                shutil.copy2(ROOT / "migrations" / entry["file"], temp_root / entry["file"])
            manifest["migrations"][0]["sha256"] = "f" * 64
            temp_manifest = temp_root / "manifest.json"
            temp_manifest.write_text(json.dumps(manifest), encoding="utf-8")
            result = run_runner("--verify-only", manifest=temp_manifest)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("migration checksum mismatch", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
