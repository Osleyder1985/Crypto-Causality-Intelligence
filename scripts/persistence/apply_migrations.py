"""Apply ordered SQL migrations to a PostgreSQL database."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import psycopg


def apply_migrations(database_url: str, migrations_dir: Path) -> list[str]:
    applied: list[str] = []
    with psycopg.connect(database_url, autocommit=True) as conn:
        for path in sorted(migrations_dir.glob("*.sql")):
            table_exists = conn.execute(
                "SELECT to_regclass('cci.schema_migrations')"
            ).fetchone()[0]
            if table_exists:
                exists = conn.execute(
                    "SELECT 1 FROM cci.schema_migrations WHERE version = %s",
                    (path.stem,),
                ).fetchone()
                if exists:
                    continue
            conn.execute(path.read_text(encoding="utf-8"))
            applied.append(path.stem)
    return applied


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--migrations", type=Path, default=Path("migrations"))
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    print("\\n".join(apply_migrations(args.database_url, args.migrations)) or "No migrations pending")


if __name__ == "__main__":
    main()
