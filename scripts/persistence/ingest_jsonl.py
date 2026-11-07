"""Load the approved Binance BTCUSDT JSONL into PostgreSQL atomically."""
from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

import psycopg

from scripts.persistence.market_writer import (
    CANDLE_FIELDS, canonicalize_rows, payload_digest, write_candle_batch,
)
from scripts.validation.storage_conformance import load_jsonl


def ingest_jsonl(
    database_url: str, input_path: Path, *, actor: str
) -> dict[str, Any]:
    rows = load_jsonl(input_path)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["cohort_window"]].append(
            {field: row[field] for field in CANDLE_FIELDS}
        )

    results = []
    with psycopg.connect(database_url) as conn:
        # All five cohorts form one all-or-nothing historical ingestion.
        with conn.transaction():
            for cohort in sorted(grouped):
                canonical = canonicalize_rows(grouped[cohort])
                digest = payload_digest("binance", "SPOT", "BTCUSDT", "1h", canonical)
                result = write_candle_batch(
                    conn, provider="binance", market_type="SPOT", symbol="BTCUSDT",
                    interval="1h", rows=canonical,
                    idempotency_key=f"binance:SPOT:BTCUSDT:1h:{cohort}:{digest}",
                    actor=actor,
                )
                results.append({"cohort": cohort, **result})
    return {
        "status": "persisted",
        "total_rows": sum(item["row_count"] for item in results),
        "cohorts": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--actor", required=True)
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    print(json.dumps(ingest_jsonl(args.database_url, args.input, actor=args.actor), indent=2))


if __name__ == "__main__":
    main()
