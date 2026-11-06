"""Transactional PostgreSQL registry for research runs; stores metadata, never OHLCV rows."""
from __future__ import annotations

import os
import uuid
from typing import Any

class RegistryError(RuntimeError):
    pass

class PostgresRunRegistry:
    def __init__(self, dsn: str | None = None):
        self.dsn = dsn or os.environ.get("CCI_DATABASE_URL")
        if not self.dsn:
            raise RegistryError("Define CCI_DATABASE_URL")
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RegistryError("Install requirements-research.txt (psycopg)") from exc
        self._psycopg = psycopg
        self._dict_row = dict_row

    def create_run(self, *, experiment_id: str, run_key: str, code_commit: str,
                   protocol_version: str, parameters: dict[str, Any] | None = None,
                   input_manifest: dict[str, Any] | None = None,
                   run_id: str | None = None) -> str:
        identifier = run_id or str(uuid.uuid4())
        with self._psycopg.connect(self.dsn) as conn:
            conn.execute(
                """INSERT INTO cci.research_experiment_runs
                   (id, experiment_id, run_key, status, code_commit, protocol_version, parameters, input_manifest)
                   VALUES (%s,%s,%s,'queued',%s,%s,%s,%s)""",
                (identifier, experiment_id, run_key, code_commit, protocol_version,
                 self._psycopg.types.json.Jsonb(parameters or {}),
                 self._psycopg.types.json.Jsonb(input_manifest or {})),
            )
        return identifier

    def transition(self, run_id: str, status: str, *, metrics: dict[str, Any] | None = None,
                   error_code: str | None = None, error_summary: str | None = None) -> None:
        if status not in {"running", "succeeded", "failed", "cancelled"}:
            raise RegistryError(f"Unsupported target status: {status}")
        with self._psycopg.connect(self.dsn) as conn:
            row = conn.execute(
                "SELECT status FROM cci.research_experiment_runs WHERE id=%s FOR UPDATE",
                (run_id,),
            ).fetchone()
            if row is None:
                raise RegistryError(f"Unknown run: {run_id}")
            conn.execute(
                """UPDATE cci.research_experiment_runs
                   SET status=%s,
                       started_at=CASE WHEN %s='running' AND started_at IS NULL THEN now() ELSE started_at END,
                       finished_at=CASE WHEN %s IN ('succeeded','failed','cancelled') THEN now() ELSE NULL END,
                       metrics=COALESCE(%s, metrics), error_code=%s, error_summary=%s
                   WHERE id=%s""",
                (status, status, status,
                 self._psycopg.types.json.Jsonb(metrics) if metrics is not None else None,
                 error_code, error_summary, run_id),
            )

    def register_artifact(self, *, run_id: str, artifact_role: str, logical_uri: str,
                          media_type: str, format: str, sha256: str, byte_size: int,
                          retention_class: str, schema_version: str | None = None,
                          artifact_id: str | None = None) -> str:
        identifier = artifact_id or str(uuid.uuid4())
        with self._psycopg.connect(self.dsn) as conn:
            conn.execute(
                """INSERT INTO cci.research_run_artifacts
                   (id,run_id,artifact_role,logical_uri,media_type,format,sha256,byte_size,retention_class,schema_version)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (identifier,run_id,artifact_role,logical_uri,media_type,format,sha256,
                 byte_size,retention_class,schema_version),
            )
        return identifier
