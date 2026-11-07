"""Fail-closed preflight for durable market-data storage."""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

import psycopg


def validate_permission(row, provider: str, market_type: str, symbol: str, now=None) -> dict:
    if row is None:
        raise PermissionError(f"No storage authorization exists for {provider}/{market_type}/{symbol}")

    allowed, retention_until, evidence_ref, updated_at = row
    now = now or datetime.now(timezone.utc)
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


def check_permission(database_url: str, provider: str, market_type: str, symbol: str) -> dict:
    with psycopg.connect(database_url) as conn:
        row = conn.execute(
            """SELECT storage_allowed, retention_until, evidence_ref, updated_at
               FROM cci.source_permissions
               WHERE provider = %s AND market_type = %s AND symbol = %s""",
            (provider, market_type, symbol),
        ).fetchone()

    return validate_permission(row, provider, market_type, symbol)
