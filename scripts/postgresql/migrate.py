#!/usr/bin/env python3
"""Apply and verify the versioned CCI PostgreSQL migrations.

Each SQL migration owns its transaction boundary. The runner verifies pinned
SHA-256 checksums before execution and records them in cci.schema_migrations
once migration 011 has introduced the checksum column.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import psycopg


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "migrations" / "manifest.json"
VERSION_RE = re.compile(r"^[0-9]{3}_[a-z0-9_]+$")
CHECKSUM_RE = re.compile(r"^[0-9a-f]{64}$")


class MigrationError(RuntimeError):
    """Raised when the migration manifest or database ledger is inconsistent."""


def load_manifest(manifest_path: Path) -> list[dict[str, str]]:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MigrationError(f"cannot read migration manifest: {exc}") from exc

    if manifest.get("manifest_version") != 1 or manifest.get("hash_algorithm") != "sha256":
        raise MigrationError("unsupported migration manifest version or hash algorithm")

    entries = manifest.get("migrations")
    if not isinstance(entries, list) or not entries:
        raise MigrationError("manifest migrations must be a non-empty array")

    migration_dir = manifest_path.parent
    disk_files = sorted(p.name for p in migration_dir.glob("*.sql"))
    manifest_files = [entry.get("file") for entry in entries]
    if disk_files != manifest_files:
        raise MigrationError(
            f"manifest/file inventory mismatch: manifest={manifest_files}, disk={disk_files}"
        )

    validated: list[dict[str, str]] = []
    seen_versions: set[str] = set()
    for index, entry in enumerate(entries, start=1):
        version = entry.get("version")
        filename = entry.get("file")
        expected_hash = entry.get("sha256")
        if not isinstance(version, str) or not VERSION_RE.fullmatch(version):
            raise MigrationError(f"invalid migration version at position {index}")
        if not isinstance(filename, str) or Path(filename).name != filename:
            raise MigrationError(f"invalid migration filename for {version}")
        if not isinstance(expected_hash, str) or not CHECKSUM_RE.fullmatch(expected_hash):
            raise MigrationError(f"invalid SHA-256 in manifest for {version}")
        if version in seen_versions:
            raise MigrationError(f"duplicate migration version: {version}")
        seen_versions.add(version)

        expected_prefix = f"{index:03d}_"
        if not filename.startswith(expected_prefix) or not version.startswith(expected_prefix):
            raise MigrationError(
                f"migration order is not contiguous at {filename}; expected prefix {expected_prefix}"
            )

        path = migration_dir / filename
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise MigrationError(f"cannot read {path}: {exc}") from exc
        actual_hash = hashlib.sha256(raw).hexdigest()
        if actual_hash != expected_hash:
            raise MigrationError(
                f"migration checksum mismatch for {filename}: "
                f"manifest={expected_hash}, actual={actual_hash}"
            )

        validated.append(
            {"version": version, "file": filename, "sha256": expected_hash, "path": str(path)}
        )
    return validated


def ledger_exists(conn: psycopg.Connection[Any]) -> bool:
    return conn.execute("SELECT to_regclass('cci.schema_migrations')").fetchone()[0] is not None


def checksum_column_exists(conn: psycopg.Connection[Any]) -> bool:
    return bool(
        conn.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'cci'
                  AND table_name = 'schema_migrations'
                  AND column_name = 'checksum_sha256'
            )
            """
        ).fetchone()[0]
    )


def read_ledger(conn: psycopg.Connection[Any], has_checksum: bool) -> dict[str, tuple[str, str | None]]:
    if not ledger_exists(conn):
        return {}
    if has_checksum:
        rows = conn.execute(
            "SELECT version, description, checksum_sha256 FROM cci.schema_migrations"
        ).fetchall()
        return {version: (description, checksum) for version, description, checksum in rows}
    rows = conn.execute(
        "SELECT version, description FROM cci.schema_migrations"
    ).fetchall()
    return {version: (description, None) for version, description in rows}


def verify_ledger_prefix(
    ledger: dict[str, tuple[str, str | None]], entries: list[dict[str, str]]
) -> None:
    known = {entry["version"] for entry in entries}
    unknown = set(ledger) - known
    if unknown:
        raise MigrationError(f"database ledger contains versions absent from manifest: {sorted(unknown)}")

    applied = [entry["version"] in ledger for entry in entries]
    first_missing = next((i for i, is_applied in enumerate(applied) if not is_applied), len(applied))
    if any(applied[first_missing:]):
        raise MigrationError("database migration ledger has a gap or out-of-order version")


def apply_migrations(
    conn: psycopg.Connection[Any],
    entries: list[dict[str, str]],
    *,
    verify_only: bool,
) -> None:
    has_ledger = ledger_exists(conn)
    has_checksum = checksum_column_exists(conn) if has_ledger else False
    ledger = read_ledger(conn, has_checksum)
    verify_ledger_prefix(ledger, entries)

    for entry in entries:
        version = entry["version"]
        if version in ledger:
            stored_checksum = ledger[version][1]
            if has_checksum and stored_checksum is not None and stored_checksum != entry["sha256"]:
                raise MigrationError(
                    f"database checksum mismatch for {version}: "
                    f"database={stored_checksum}, manifest={entry['sha256']}"
                )
            if verify_only:
                if has_checksum and stored_checksum is None:
                    raise MigrationError(f"checksum not initialized for applied migration {version}")
                print(f"VERIFIED {version}")
            else:
                print(f"SKIPPED  {version}")
            continue

        if verify_only:
            raise MigrationError(f"migration {version} is pending; verify-only cannot apply it")

        sql = Path(entry["path"]).read_text(encoding="utf-8")
        print(f"APPLYING {version}")
        conn.execute(sql, prepare=False)

        if not ledger_exists(conn):
            raise MigrationError(f"{version} completed without creating cci.schema_migrations")
        has_checksum = checksum_column_exists(conn)
        ledger = read_ledger(conn, has_checksum)
        if version not in ledger:
            raise MigrationError(f"{version} completed but did not register itself in the migration ledger")

    has_checksum = checksum_column_exists(conn)
    ledger = read_ledger(conn, has_checksum)
    verify_ledger_prefix(ledger, entries)

    if has_checksum:
        if verify_only:
            for entry in entries:
                stored = ledger[entry["version"]][1]
                if stored != entry["sha256"]:
                    raise MigrationError(
                        f"checksum not verified for {entry['version']}: "
                        f"database={stored}, manifest={entry['sha256']}"
                    )
        else:
            # One-time adoption for databases upgraded from the pre-checksum ledger.
            with conn.transaction():
                for entry in entries:
                    stored = ledger[entry["version"]][1]
                    if stored is None:
                        conn.execute(
                            """
                            UPDATE cci.schema_migrations
                            SET checksum_sha256 = %s
                            WHERE version = %s AND checksum_sha256 IS NULL
                            """,
                            (entry["sha256"], entry["version"]),
                        )
                    elif stored != entry["sha256"]:
                        raise MigrationError(
                            f"checksum mismatch for {entry['version']}: "
                            f"database={stored}, manifest={entry['sha256']}"
                        )

            ledger = read_ledger(conn, True)
            for entry in entries:
                if ledger[entry["version"]][1] != entry["sha256"]:
                    raise MigrationError(f"failed to persist checksum for {entry['version']}")

    if len(ledger) != len(entries):
        raise MigrationError(
            f"ledger contains {len(ledger)} versions; manifest contains {len(entries)}"
        )

    print(f"OK: {len(entries)} migrations verified")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dsn",
        default=os.environ.get("CCI_DATABASE_URL") or os.environ.get("CCI_TEST_DATABASE_URL"),
        help="PostgreSQL DSN (default: CCI_DATABASE_URL or CCI_TEST_DATABASE_URL)",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="pinned migration manifest",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="verify the complete applied ledger and checksums without applying migrations",
    )
    args = parser.parse_args()

    if not args.dsn:
        parser.error("provide --dsn or set CCI_DATABASE_URL")

    try:
        entries = load_manifest(args.manifest.resolve())
        with psycopg.connect(args.dsn, autocommit=True) as conn:
            apply_migrations(conn, entries, verify_only=args.verify_only)
    except (MigrationError, psycopg.Error, OSError) as exc:
        print(f"migration runner error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
