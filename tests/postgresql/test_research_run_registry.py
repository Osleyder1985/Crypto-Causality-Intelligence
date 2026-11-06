"""Integration tests; run only against a disposable PostgreSQL database."""
import contextlib
import csv
import io
import json
import os
import tempfile
import threading
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch
from datetime import datetime, timedelta, timezone

DSN = os.environ.get("CCI_TEST_DATABASE_URL")

@unittest.skipUnless(DSN, "CCI_TEST_DATABASE_URL not configured")
class ResearchRunRegistryPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg
        cls.psycopg = psycopg
        cls.conn = psycopg.connect(DSN, autocommit=True)
        base_migration = Path("migrations/postgresql/001_research_experiments.sql").read_text(encoding="utf-8")
        cls.conn.execute(base_migration)
        cls.experiment_id = uuid.uuid4()
        cls.conn.execute("""INSERT INTO cci.research_experiments
            (id,experiment_key,title,objective,status,protocol)
            VALUES (%s,%s,'Synthetic integration test','Verify PostgreSQL registry','planned','{}'::jsonb)""",
            (cls.experiment_id, "test-"+str(cls.experiment_id)))
        migration = Path("migrations/postgresql/002_research_run_registry.sql").read_text(encoding="utf-8")
        cls.conn.execute(migration)
        cls.conn.execute("CREATE ROLE cci_research_runner NOLOGIN")
        cls.conn.execute("GRANT USAGE ON SCHEMA cci TO cci_research_runner")
        cls.conn.execute("GRANT SELECT, INSERT, UPDATE ON cci.research_experiment_runs TO cci_research_runner")
        cls.conn.execute("GRANT SELECT, INSERT ON cci.research_run_artifacts TO cci_research_runner")

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

    def test_btc_episode_cli_registers_successful_run_and_artifacts(self):
        from scripts.research.btc_episode_study import main
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            input_path=root/"candles.csv"
            episodes_path=root/"episodes.json"
            json_out=root/"summary.json"
            csv_out=root/"summary.csv"
            start=datetime(2026,1,1,tzinfo=timezone.utc)
            with input_path.open("w",encoding="utf-8",newline="") as handle:
                writer=csv.writer(handle)
                writer.writerow(["open_time_utc","open","high","low","close","volume"])
                for i in range(336):
                    price=100.0+i*0.1
                    stamp=(start+timedelta(hours=i)).isoformat().replace("+00:00","Z")
                    writer.writerow([stamp,price,price+1,price-1,price+0.5,10+i])
            utc_offset=timezone(timedelta(hours=-5))
            first_start=start+timedelta(hours=168)
            first_end=start+timedelta(hours=192)
            second_start=start+timedelta(hours=192)
            second_end=start+timedelta(hours=216)
            def stamp_pair(value):
                return {
                    "local":value.astimezone(utc_offset).isoformat(),
                    "utc":value.isoformat().replace("+00:00","Z"),
                }
            a,b,c_stamp,d=map(stamp_pair,(first_start,first_end,second_start,second_end))
            manifest={
                "schema_version":"cci.episode-manifest.v1",
                "manifest_status":"approved",
                "experiment_key":"btc-usdt-directional-episodes-v1",
                "market":"BTC/USDT",
                "venue":"synthetic-test-venue",
                "market_type":"spot",
                "interval_seconds":3600,
                "input_timezone":"UTC-05:00",
                "data_source":{
                    "provider":"synthetic-test",
                    "dataset_id":"postgres-cli-fixture",
                    "acquisition_method":"generated in test",
                },
                "data_usage_authorization":{"status":"authorized","evidence_ref":"synthetic-only"},
                "episodes":[
                    {"episode_id":"synthetic-rise","direction":"bullish","status":"confirmed",
                     "start_local":a["local"],"end_local":b["local"],
                     "start_utc":a["utc"],"end_utc":b["utc"]},
                    {"episode_id":"synthetic-fall","direction":"bearish","status":"confirmed",
                     "start_local":c_stamp["local"],"end_local":d["local"],
                     "start_utc":c_stamp["utc"],"end_utc":d["utc"]},
                ],
            }
            episodes_path.write_text(json.dumps(manifest),encoding="utf-8")
            output=io.StringIO()
            with patch.dict(os.environ,{"CCI_DATABASE_URL":DSN}), contextlib.redirect_stdout(output):
                result=main([
                    "--input",str(input_path),"--episodes",str(episodes_path),
                    "--json-out",str(json_out),"--csv-out",str(csv_out),
                    "--experiment-id",str(self.experiment_id),
                    "--run-key","cli-e2e-"+str(uuid.uuid4()),
                    "--code-commit","abcdef1234567890",
                ])
            self.assertEqual(result,0,output.getvalue())
            run_id=output.getvalue().split("Run PostgreSQL: ")[1].splitlines()[0]
            row=self.conn.execute(
                "SELECT status,metrics->>'episode_count' FROM cci.research_experiment_runs WHERE id=%s",
                (run_id,)).fetchone()
            self.assertEqual(row,("succeeded","2"))
            artifacts=self.conn.execute(
                "SELECT artifact_role,sha256,byte_size FROM cci.research_run_artifacts WHERE run_id=%s ORDER BY artifact_role",
                (run_id,)).fetchall()
            self.assertEqual([a[0] for a in artifacts],["report","summary"])
            self.assertTrue(all(len(a[1])==64 and a[2]>0 for a in artifacts))

    def test_minimum_runtime_role_can_run_without_delete_privilege(self):
        rid=uuid.uuid4()
        self.conn.execute("SET ROLE cci_research_runner")
        try:
            self.conn.execute("""INSERT INTO cci.research_experiment_runs
                (id,experiment_id,run_key,status,code_commit,protocol_version)
                VALUES (%s,%s,%s,'queued','abcdef1234567','v1')""",
                (rid,self.experiment_id,str(rid)))
            self.conn.execute("UPDATE cci.research_experiment_runs SET status='running',started_at=now() WHERE id=%s",(rid,))
            self.conn.execute("UPDATE cci.research_experiment_runs SET status='succeeded',finished_at=now() WHERE id=%s",(rid,))
            self.conn.execute("""INSERT INTO cci.research_run_artifacts
                (id,run_id,artifact_role,logical_uri,media_type,format,sha256,byte_size,retention_class)
                VALUES (%s,%s,'summary','cci://least-privilege','application/json','json',%s,10,'research')""",
                (uuid.uuid4(),rid,'b'*64))
            with self.assertRaises(self.psycopg.errors.InsufficientPrivilege):
                self.conn.execute("DELETE FROM cci.research_experiment_runs WHERE id=%s",(rid,))
        finally:
            self.conn.execute("RESET ROLE")

    def test_concurrent_transition_waits_for_row_lock(self):
        from scripts.research.postgres_run_registry import PostgresRunRegistry
        rid=self.make_run()
        started=threading.Event()
        errors=[]
        with self.conn.transaction():
            self.conn.execute("SELECT id FROM cci.research_experiment_runs WHERE id=%s FOR UPDATE",(rid,))
            def transition_in_second_session():
                try:
                    with patch.dict(os.environ,{"CCI_DATABASE_URL":DSN}):
                        started.set()
                        PostgresRunRegistry().transition(str(rid),"running")
                except Exception as exc:
                    errors.append(exc)
            worker=threading.Thread(target=transition_in_second_session,daemon=True)
            worker.start()
            self.assertTrue(started.wait(timeout=2))
            time.sleep(0.15)
            self.assertTrue(worker.is_alive(),"second session should wait for the first session row lock")
        worker.join(timeout=3)
        self.assertFalse(worker.is_alive(),"second session did not finish after row lock release")
        self.assertEqual(errors,[])
        self.assertEqual(self.conn.execute(
            "SELECT status FROM cci.research_experiment_runs WHERE id=%s",(rid,)).fetchone()[0],"running")

if __name__ == "__main__":
    unittest.main()
