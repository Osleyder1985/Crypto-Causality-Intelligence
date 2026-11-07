"""Permission-gated, idempotent, atomic market-data writes for PostgreSQL."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Iterable

import psycopg
from psycopg.types.json import Jsonb

CANDLE_FIELDS = (
    "open_time_ms", "open_time_utc", "open", "high", "low", "close",
    "volume_base", "quote_volume", "close_time_ms", "trade_count",
    "taker_buy_base_volume", "taker_buy_quote_volume", "source_ignore_field",
)


class StoragePermissionDenied(PermissionError):
    """Raised when durable storage is not explicitly authorized."""


class IdempotencyConflict(ValueError):
    """Raised when an idempotency key is reused for a different payload."""


def _utc(value: Any) -> datetime:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise ValueError("open_time_utc must be an aware datetime or ISO-8601 string")
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("open_time_utc must be timezone-aware")
    return dt.astimezone(timezone.utc)


def canonicalize_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen: set[int] = set()
    for source in rows:
        missing = set(CANDLE_FIELDS) - source.keys()
        if missing:
            raise ValueError(f"missing candle fields: {sorted(missing)}")
        row = {field: source[field] for field in CANDLE_FIELDS}
        row["open_time_ms"] = int(row["open_time_ms"])
        row["close_time_ms"] = int(row["close_time_ms"])
        row["trade_count"] = int(row["trade_count"])
        row["open_time_utc"] = _utc(row["open_time_utc"])
        for field in (
            "open", "high", "low", "close", "volume_base", "quote_volume",
            "taker_buy_base_volume", "taker_buy_quote_volume",
        ):
            row[field] = Decimal(str(row[field]))
            if not row[field].is_finite():
                raise ValueError(f"{field} must be finite")
        if row["open_time_ms"] in seen:
            raise ValueError("duplicate open_time_ms in batch")
        seen.add(row["open_time_ms"])
        if row["open_time_ms"] < 0 or row["close_time_ms"] < row["open_time_ms"]:
            raise ValueError("invalid candle timestamps")
        if int(row["open_time_utc"].timestamp() * 1000) != row["open_time_ms"]:
            raise ValueError("open_time_ms and open_time_utc disagree")
        if not (Decimal(0) < row["low"] <= row["open"] <= row["high"]
                and row["low"] <= row["close"] <= row["high"]):
            raise ValueError("OHLC invariant violated")
        if min(row[k] for k in (
            "volume_base", "quote_volume", "taker_buy_base_volume",
            "taker_buy_quote_volume",
        )) < 0:
            raise ValueError("volume fields must be non-negative")
        if row["taker_buy_base_volume"] > row["volume_base"]:
            raise ValueError("taker base volume exceeds total")
        if row["taker_buy_quote_volume"] > row["quote_volume"]:
            raise ValueError("taker quote volume exceeds total")
        if row["trade_count"] < 0:
            raise ValueError("trade_count must be non-negative")
        normalized.append(row)
    if not normalized:
        raise ValueError("batch must contain at least one candle")
    normalized.sort(key=lambda item: item["open_time_ms"])
    return normalized


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    raise TypeError(f"unsupported canonical JSON value: {type(value).__name__}")


def payload_digest(provider: str, market_type: str, symbol: str, interval: str,
                   rows: list[dict[str, Any]]) -> str:
    payload = {
        "provider": provider, "market_type": market_type, "symbol": symbol,
        "interval": interval, "rows": rows,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                         default=_jsonable).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def write_candle_batch(
    conn: psycopg.Connection,
    *,
    provider: str,
    market_type: str,
    symbol: str,
    interval: str,
    rows: Iterable[dict[str, Any]],
    idempotency_key: str,
    actor: str,
) -> dict[str, Any]:
    """Persist a batch and its audit event in one PostgreSQL transaction.

    No permission row, denied permission, or expired retention window means
    deny-by-default. A repeated key with the same digest returns the prior run;
    a repeated key with different content is rejected.
    """
    for name, value in (("provider", provider), ("market_type", market_type),
                        ("symbol", symbol), ("interval", interval),
                        ("idempotency_key", idempotency_key), ("actor", actor)):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a non-empty string")
    normalized = canonicalize_rows(rows)
    digest = payload_digest(provider, market_type, symbol, interval, normalized)
    columns = (
        "provider", "market_type", "symbol", "interval", *CANDLE_FIELDS,
        "ingestion_run_id",
    )
    placeholders = ", ".join(["%s"] * len(columns))
    insert_candle = (
        f"INSERT INTO cci.market_candles ({', '.join(columns)}) "
        f"VALUES ({placeholders})"
    )
    with conn.transaction():
        permission = conn.execute(
            """SELECT storage_allowed, retention_until, evidence_ref
               FROM cci.source_permissions
               WHERE provider = %s AND market_type = %s AND symbol = %s
               FOR SHARE""",
            (provider, market_type, symbol),
        ).fetchone()
        now = datetime.now(timezone.utc)
        if (permission is None or not permission[0] or permission[1] is None
                or permission[1] <= now or not permission[2].strip()):
            raise StoragePermissionDenied(
                f"durable storage is not authorized for {provider}/{market_type}/{symbol}"
            )

        # Serialize retries sharing the same key; the UNIQUE constraint remains the final guard.
        conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (idempotency_key,))
        existing = conn.execute(
            """SELECT run_id, payload_sha256, row_count
               FROM cci.ingestion_runs WHERE idempotency_key = %s""",
            (idempotency_key,),
        ).fetchone()
        if existing:
            if existing[1].strip() != digest:
                raise IdempotencyConflict("idempotency key already belongs to another payload")
            return {"run_id": existing[0], "row_count": existing[2],
                    "payload_sha256": digest, "replayed": True}

        run = conn.execute(
            """INSERT INTO cci.ingestion_runs
               (idempotency_key, provider, market_type, symbol, interval,
                row_count, payload_sha256, actor)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
               RETURNING run_id""",
            (idempotency_key, provider, market_type, symbol, interval,
             len(normalized), digest, actor),
        ).fetchone()
        run_id = run[0]
        for row in normalized:
            values = (provider, market_type, symbol, interval,
                      *(row[field] for field in CANDLE_FIELDS), run_id)
            conn.execute(insert_candle, values)

        audit_payload = {
            "provider": provider, "market_type": market_type, "symbol": symbol,
            "interval": interval, "row_count": len(normalized),
            "payload_sha256": digest, "permission_evidence_ref": permission[2],
        }
        conn.execute(
            """INSERT INTO cci.audit_events
               (event_type, entity_type, entity_key, actor, payload,
                payload_sha256, correlation_id)
               VALUES ('market_data.batch_written', 'ingestion_run', %s, %s,
                       %s, %s, %s)""",
            (str(run_id), actor, Jsonb(audit_payload), digest, idempotency_key),
        )
    return {"run_id": run_id, "row_count": len(normalized),
            "payload_sha256": digest, "replayed": False}


def purge_expired_market_data(
    conn: psycopg.Connection, *, actor: str
) -> dict[str, Any]:
    """Delete candles whose storage permission is denied or has expired.

    Deletion and its metadata-only audit event commit atomically. Permission
    rows are locked so a concurrent writer cannot race the retention decision.
    """
    if not isinstance(actor, str) or not actor.strip():
        raise ValueError("actor must be a non-empty string")
    deleted_sources: list[dict[str, Any]] = []
    with conn.transaction():
        permissions = conn.execute(
            """SELECT provider, market_type, symbol, retention_until, evidence_ref
               FROM cci.source_permissions
               WHERE storage_allowed = FALSE OR retention_until <= clock_timestamp()
               ORDER BY provider, market_type, symbol
               FOR UPDATE"""
        ).fetchall()
        for provider, market_type, symbol, retention_until, evidence_ref in permissions:
            result = conn.execute(
                """DELETE FROM cci.market_candles
                   WHERE provider = %s AND market_type = %s AND symbol = %s""",
                (provider, market_type, symbol),
            )
            deleted_count = result.rowcount
            if not deleted_count:
                continue
            audit_payload = {
                "provider": provider,
                "market_type": market_type,
                "symbol": symbol,
                "deleted_rows": deleted_count,
                "retention_until": retention_until,
                "permission_evidence_ref": evidence_ref,
            }
            encoded = json.dumps(
                audit_payload, sort_keys=True, separators=(",", ":"), default=_jsonable
            ).encode("utf-8")
            digest = hashlib.sha256(encoded).hexdigest()
            entity_key = f"{provider}:{market_type}:{symbol}"
            correlation_id = f"retention-purge:{entity_key}:{retention_until.isoformat()}"
            conn.execute(
                """INSERT INTO cci.audit_events
                   (event_type, entity_type, entity_key, actor, payload,
                    payload_sha256, correlation_id)
                   VALUES ('market_data.retention_purged', 'market_source',
                           %s, %s, %s, %s, %s)""",
                (entity_key, actor, Jsonb(audit_payload), digest, correlation_id),
            )
            deleted_sources.append({
                "provider": provider, "market_type": market_type,
                "symbol": symbol, "deleted_rows": deleted_count,
            })
    return {
        "deleted_rows": sum(item["deleted_rows"] for item in deleted_sources),
        "deleted_sources": deleted_sources,
    }
