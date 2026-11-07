"""Fail-closed preflight for durable market-data storage."""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

import psycopg


def check_permission(database_url: str, provider: str, market_type: str, symbol: str) -> dict:
    with psycopg.connect(database_url) as conn:
        row = conn.execute(
            """SELECT storage_allowed, retention_until, evidence_ref, updated_at
               FROM cci.source_permissions
               WHERE provider = %s AND market_type = %s AND symbol = %s""",
            (provider, market_type, symbol),
        ).fetchone()

    if row is None:
        raise PermissionError(f"No storage authorization exists for {provider}/{market_type}/{symbol}")

    allowed, retention_until, evidence_ref, updated_at = row
    now = datetime.now(timezone.utc)
    if not allowed:
        raise PermissionError(f"Storage is explicitly denied for {provider}/{market_type}/{symbol}")
    if retention_until is None or retention_until <= now:
        raise PermissionError(f"Storage authorization is absent or expired for {provider}/{market_type}/{symbol}")
    if not evidence_ref or not evidence_ref.strip():
        raise PermissionError("Storage authorization has no evidence reference")

    return {
        "status": "authorized",
        "provider": provider,
        "market_type": market_type,
        "symbol": symbol,
        "retention_until": retention_until.isoformat(),
        "evidence_ref": evidence_ref,
        "permission_updated_at": updated_at.isoformat(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--provider", default="binance")
    parser.add_argument("--market-type", default="SPOT")
    parser.add_argument("--symbol", default="BTCUSDT")
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    try:
        import json
        print(json.dumps(check_permission(
            args.database_url, args.provider, args.market_type, args.symbol
        ), indent=2))
    except PermissionError as exc:
        print(f"DENIED: {exc}", file=sys.stderr)
        raise SystemExit(3) from exc


if __name__ == "__main__":
    main()
