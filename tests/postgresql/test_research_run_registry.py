"""Integration tests; run only against a disposable PostgreSQL database."""
import os
import unittest
import uuid
from pathlib import Path

DSN = os.environ.get("CCI_TEST_DATABASE_URL")

@unittest.skipUnless(DSN, "CCI_TEST_DATABASE_URL not configured")
class ResearchRunRegistryPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg
        cls.psycopg = psycopg
        cls.conn = psycopg.connect(DSN, autocommit=True)
        cls.conn.execute("CREATE SCHEMA IF NOT EXISTS cci")
        cls.conn.execute("""CREATE TABLE IF NOT EXISTS cci.research_experiments (
            id UUID PRIMARY KEY, experiment_key TEXT NOT NULL UNIQUE)""")
        cls.experiment_id = uuid.uuid4()
        cls.conn.execute("INSERT INTO cci.research_experiments VALUES (%s,%s)",
                         (cls.experiment_id, "test-"+str(cls.experiment_id)))
        migration = Path("migrations/postgresql/002_research_run_registry.sql").read_text(encoding="utf-8")
        cls.conn.execute(migration)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "conn"):
            cls.conn.execute("DELETE FROM cci.research_run_artifacts WHERE run_id IN (SELECT id FROM cci.research_experiment_runs WHERE experiment_id=%s)", (cls.experiment_id,))
            cls.conn.execute("DELETE FROM cci.research_experiment_runs WHERE experiment_id=%s", (cls.experiment_id,))
            cls.conn.execute("DELETE FROM cci.research_experiments WHERE id=%s", (cls.experiment_id,))
            cls.conn.close()

    def make_run(self, status="queued"):
        run_id=uuid.uuid4()
        self.conn.execute("""INSERT INTO cci.research_experiment_runs
            (id,experiment_id,run_key,status,code_commit,protocol_version)
            VALUES (%s,%s,%s,%s,'abcdef1234567','v1')""",
            (run_id,self.experiment_id,str(run_id),status))
        return run_id

    def test_create_and_valid_transitions(self):
        rid=self.make_run()
        self.conn.execute("UPDATE cci.research_experiment_runs SET status='running',started_at=now() WHERE id=%s",(rid,))
        self.conn.execute("UPDATE cci.research_experiment_runs SET status='succeeded',finished_at=now(),metrics='{}'::jsonb WHERE id=%s",(rid,))
        self.assertEqual(self.conn.execute("SELECT status FROM cci.research_experiment_runs WHERE id=%s",(rid,)).fetchone()[0],"succeeded")

    def test_invalid_transition_rejected(self):
        rid=self.make_run()
        with self.assertRaises(self.psycopg.errors.RaiseException):
            self.conn.execute("UPDATE cci.research_experiment_runs SET status='succeeded',finished_at=now() WHERE id=%s",(rid,))

    def test_terminal_run_is_immutable(self):
        rid=self.make_run()
        self.conn.execute("UPDATE cci.research_experiment_runs SET status='cancelled',finished_at=now() WHERE id=%s",(rid,))
        with self.assertRaises(self.psycopg.errors.RaiseException):
            self.conn.execute("UPDATE cci.research_experiment_runs SET error_summary='rewrite' WHERE id=%s",(rid,))

    def test_fk_and_hash_constraints(self):
        with self.assertRaises(self.psycopg.errors.ForeignKeyViolation):
            self.conn.execute("""INSERT INTO cci.research_experiment_runs
                (id,experiment_id,run_key,status,code_commit,protocol_version)
                VALUES (%s,%s,'bad','queued','abcdef1','v1')""",(uuid.uuid4(),uuid.uuid4()))
        rid=self.make_run()
        with self.assertRaises(self.psycopg.errors.CheckViolation):
            self.conn.execute("""INSERT INTO cci.research_run_artifacts
                (id,run_id,artifact_role,logical_uri,media_type,format,sha256,byte_size,retention_class)
                VALUES (%s,%s,'summary','cci://x','application/json','json','bad',0,'research')""",(uuid.uuid4(),rid))

    def test_unique_run_key_per_experiment(self):
        rid=self.make_run()
        with self.assertRaises(self.psycopg.errors.UniqueViolation):
            self.conn.execute("""INSERT INTO cci.research_experiment_runs
                (id,experiment_id,run_key,status,code_commit,protocol_version)
                VALUES (%s,%s,%s,'queued','abcdef1234567','v1')""",
                (uuid.uuid4(),self.experiment_id,str(rid)))

    def test_artifact_reference_and_hash(self):
        rid=self.make_run()
        artifact_id=uuid.uuid4()
        values=(artifact_id,rid,'summary','cci://synthetic/run-summary.json',
                'application/json','json','a'*64,128,'research','v1')
        self.conn.execute("""INSERT INTO cci.research_run_artifacts
            (id,run_id,artifact_role,logical_uri,media_type,format,sha256,byte_size,retention_class,schema_version)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",values)
        row=self.conn.execute("SELECT sha256,byte_size FROM cci.research_run_artifacts WHERE id=%s",
                              (artifact_id,)).fetchone()
        self.assertEqual(row,('a'*64,128))

    def test_transaction_rollback_removes_partial_run(self):
        rid=uuid.uuid4()
        with self.assertRaises(RuntimeError):
            with self.conn.transaction():
                self.conn.execute("""INSERT INTO cci.research_experiment_runs
                    (id,experiment_id,run_key,status,code_commit,protocol_version)
                    VALUES (%s,%s,%s,'queued','abcdef1234567','v1')""",
                    (rid,self.experiment_id,str(rid)))
                raise RuntimeError("synthetic failure after insert")
        self.assertIsNone(self.conn.execute(
            "SELECT id FROM cci.research_experiment_runs WHERE id=%s",(rid,)).fetchone())

if __name__ == "__main__":
    unittest.main()
