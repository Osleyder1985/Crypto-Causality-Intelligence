"""Cross-engine storage conformance for the canonical Binance candle JSONL."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
import psycopg
from psycopg.types.json import Jsonb

DECIMAL = pa.decimal128(38, 18)
DECIMAL_FIELDS = (
    "open", "high", "low", "close", "volume_base", "quote_volume",
    "taker_buy_base_volume", "taker_buy_quote_volume",
)
REQUIRED = (
    "cohort_window", "provider", "market_type", "symbol", "interval",
    "open_time_ms", "open_time_utc", *DECIMAL_FIELDS, "close_time_ms",
    "trade_count", "source_ignore_field",
)
COHORT_COUNTS = {
    "decline_2025_10_06_2025_11_21": 1099,
    "decline_2026_01_14_2026_02_05": 532,
    "rise_2026_02_05_2026_05_06": 2145,
    "decline_2026_05_06_2026_06_30": 1336,
    "rise_2026_08_16_2026_09_21": 864,
}


def _decimal(value: Any, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"{field} is not a decimal") from exc
    if not result.is_finite():
        raise ValueError(f"{field} must be finite")
    quantized = result.quantize(Decimal("0.000000000000000001"))
    if quantized != result or len(quantized.as_tuple().digits) > 38:
        raise ValueError(f"{field} exceeds DECIMAL(38,18)")
    return quantized


def _utc(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("open_time_utc must be an ISO-8601 string")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    result = datetime.fromisoformat(normalized)
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("open_time_utc must be timezone-aware")
    return result.astimezone(timezone.utc)


def validate_row(row: dict[str, Any]) -> dict[str, Any]:
    missing = set(REQUIRED) - row.keys()
    if missing:
        raise ValueError(f"missing required fields: {sorted(missing)}")
    result = dict(row)
    for field in ("cohort_window", "provider", "market_type", "symbol", "interval", "source_ignore_field"):
        if not isinstance(result[field], str) or not result[field]:
            raise ValueError(f"{field} must be a non-empty string")
    if result["provider"] != "binance" or result["market_type"] != "SPOT" or result["symbol"] != "BTCUSDT" or result["interval"] != "1h":
        raise ValueError("unexpected market identity")
    for field in ("open_time_ms", "close_time_ms", "trade_count"):
        if isinstance(result[field], bool) or not isinstance(result[field], int) or result[field] < 0:
            raise ValueError(f"{field} must be a non-negative integer")
    timestamp = _utc(result["open_time_utc"])
    epoch_ms = int(timestamp.timestamp() * 1000)
    if epoch_ms != result["open_time_ms"]:
        raise ValueError("open_time_ms and open_time_utc disagree")
    for field in DECIMAL_FIELDS:
        result[field] = _decimal(result[field], field)
    if not (result["low"] <= result["open"] <= result["high"] and result["low"] <= result["close"] <= result["high"]):
        raise ValueError("OHLC invariant violated")
    if min(result[f] for f in DECIMAL_FIELDS[4:]) < 0:
        raise ValueError("volume fields must be non-negative")
    if result["taker_buy_base_volume"] > result["volume_base"]:
        raise ValueError("taker buy base volume exceeds total base volume")
    result["open_time_utc"] = timestamp
    return result


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if line.strip():
                try:
                    rows.append(validate_row(json.loads(line)))
                except Exception as exc:
                    raise ValueError(f"{path}:{line_number}: {exc}") from exc
    if len(rows) != 5976:
        raise ValueError(f"expected 5976 rows, found {len(rows)}")
    keys = [(r["provider"], r["market_type"], r["symbol"], r["interval"], r["open_time_ms"]) for r in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate natural candle key")
    counts = {name: sum(r["cohort_window"] == name for r in rows) for name in COHORT_COUNTS}
    if counts != COHORT_COUNTS:
        raise ValueError(f"cohort counts mismatch: {counts}")
    if any(r["cohort_window"] not in COHORT_COUNTS for r in rows):
        raise ValueError("unknown cohort_window")
    return sorted(rows, key=lambda r: (r["cohort_window"], r["open_time_ms"]))


def to_arrow(rows: list[dict[str, Any]]) -> pa.Table:
    schema = pa.schema([
        ("cohort_window", pa.string()), ("provider", pa.string()),
        ("market_type", pa.string()), ("symbol", pa.string()), ("interval", pa.string()),
        ("open_time_ms", pa.int64()), ("open_time_utc", pa.timestamp("us", tz="UTC")),
        *[(name, DECIMAL) for name in DECIMAL_FIELDS],
        ("close_time_ms", pa.int64()), ("trade_count", pa.int64()),
        ("source_ignore_field", pa.string()),
    ])
    return pa.Table.from_pylist(rows, schema=schema)


def _canonical(rows: list[dict[str, Any]]) -> list[tuple]:
    fields = ("cohort_window", "provider", "market_type", "symbol", "interval",
              "open_time_ms", "open_time_utc", *DECIMAL_FIELDS, "close_time_ms",
              "trade_count", "source_ignore_field")
    return [tuple(row[f] for f in fields) for row in rows]


def _rows_from_arrow(table: pa.Table) -> list[dict[str, Any]]:
    return table.to_pylist()


def _postgres_ddl(schema: str) -> str:
    return f"""
    CREATE SCHEMA {schema};
    CREATE TABLE {schema}.candles (
      cohort_window TEXT NOT NULL CHECK (cohort_window IN ({','.join(repr(x) for x in COHORT_COUNTS)})),
      provider TEXT NOT NULL CHECK (provider = 'binance'),
      market_type TEXT NOT NULL CHECK (market_type = 'SPOT'),
      symbol TEXT NOT NULL CHECK (symbol = 'BTCUSDT'),
      interval TEXT NOT NULL CHECK (interval = '1h'),
      open_time_ms BIGINT NOT NULL,
      open_time_utc TIMESTAMPTZ NOT NULL,
      open NUMERIC(38,18) NOT NULL, high NUMERIC(38,18) NOT NULL,
      low NUMERIC(38,18) NOT NULL, close NUMERIC(38,18) NOT NULL,
      volume_base NUMERIC(38,18) NOT NULL,
      close_time_ms BIGINT NOT NULL,
      quote_volume NUMERIC(38,18) NOT NULL,
      trade_count BIGINT NOT NULL CHECK (trade_count >= 0),
      taker_buy_base_volume NUMERIC(38,18) NOT NULL CHECK (taker_buy_base_volume >= 0),
      taker_buy_quote_volume NUMERIC(38,18) NOT NULL CHECK (taker_buy_quote_volume >= 0),
      source_ignore_field TEXT NOT NULL,
      PRIMARY KEY (provider, market_type, symbol, interval, open_time_ms),
      CHECK (low <= open AND open <= high AND low <= close AND close <= high),
      CHECK (volume_base >= 0 AND quote_volume >= 0),
      CHECK (taker_buy_base_volume <= volume_base)
    )
    """


def run_conformance(input_path: Path, output_dir: Path, postgres_url: str) -> dict[str, Any]:
    rows = load_jsonl(input_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = output_dir / "btc_usdt_1h.parquet"
    table = to_arrow(rows)
    pq.write_table(table, parquet_path, compression="zstd")
    parquet_rows = _rows_from_arrow(pq.read_table(parquet_path))
    if _canonical(parquet_rows) != _canonical(rows):
        raise AssertionError("Parquet round-trip differs from JSONL reference")

    db_path = output_dir / "btc_usdt_1h.duckdb"
    if db_path.exists():
        db_path.unlink()
    con = duckdb.connect(str(db_path))
    try:
        con.execute("""CREATE TABLE candles (
          cohort_window VARCHAR NOT NULL, provider VARCHAR NOT NULL,
          market_type VARCHAR NOT NULL, symbol VARCHAR NOT NULL, interval VARCHAR NOT NULL,
          open_time_ms BIGINT NOT NULL, open_time_utc TIMESTAMPTZ NOT NULL,
          open DECIMAL(38,18), high DECIMAL(38,18), low DECIMAL(38,18), close DECIMAL(38,18),
          volume_base DECIMAL(38,18), close_time_ms BIGINT NOT NULL,
          quote_volume DECIMAL(38,18), trade_count BIGINT NOT NULL,
          taker_buy_base_volume DECIMAL(38,18), taker_buy_quote_volume DECIMAL(38,18),
          source_ignore_field VARCHAR NOT NULL,
          PRIMARY KEY(provider, market_type, symbol, interval, open_time_ms),
          CHECK (trade_count >= 0), CHECK (volume_base >= 0 AND quote_volume >= 0),
          CHECK (low <= open AND open <= high AND low <= close AND close <= high),
          CHECK (taker_buy_base_volume <= volume_base)
        )""")
        insert_columns = ("cohort_window", "provider", "market_type", "symbol", "interval",
                          "open_time_ms", "open_time_utc", *DECIMAL_FIELDS[:5],
                          "close_time_ms", "quote_volume", "trade_count",
                          "taker_buy_base_volume", "taker_buy_quote_volume", "source_ignore_field")
        con.execute(
            f"INSERT INTO candles ({','.join(insert_columns)}) "
            f"SELECT {','.join(insert_columns)} FROM read_parquet(?)",
            [str(parquet_path)],
        )
        duck_rows = con.execute("SELECT * FROM candles ORDER BY cohort_window, open_time_ms").fetch_arrow_table().to_pylist()
        if _canonical(duck_rows) != _canonical(rows):
            raise AssertionError("DuckDB round-trip differs from JSONL reference")
        con.execute("CREATE TEMP TABLE parquet_view AS SELECT * FROM read_parquet(?)", [str(parquet_path)])
        parquet_count = con.execute("SELECT count(*) FROM parquet_view").fetchone()[0]
        duck_count = con.execute("SELECT count(*) FROM candles").fetchone()[0]
        if parquet_count != duck_count or duck_count != 5976:
            raise AssertionError("DuckDB table and Parquet counts differ")
        try:
            con.execute("INSERT INTO candles SELECT * FROM candles LIMIT 1")
        except duckdb.ConstraintException:
            pass
        else:
            raise AssertionError("DuckDB primary key did not reject duplicate")
    finally:
        con.close()

    schema = "cci_storage_conformance"
    with psycopg.connect(postgres_url, autocommit=True) as pg:
        pg.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
        pg.execute(_postgres_ddl(schema))
        columns = ("cohort_window", "provider", "market_type", "symbol", "interval",
                   "open_time_ms", "open_time_utc", *DECIMAL_FIELDS[:5], "close_time_ms",
                   "quote_volume", "trade_count", "taker_buy_base_volume",
                   "taker_buy_quote_volume", "source_ignore_field")
        insert_sql = f"INSERT INTO {schema}.candles ({','.join(columns)}) VALUES ({','.join(['%s']*len(columns))})"
        values = [tuple(row[c] for c in columns) for row in rows]
        with pg.transaction():
            with pg.cursor() as cur:
                cur.executemany(insert_sql, values)
        with pg.cursor() as cur:
            cur.execute(f"SELECT {','.join(columns)} FROM {schema}.candles ORDER BY cohort_window, open_time_ms")
            pg_rows = cur.fetchall()
        if len(pg_rows) != len(rows):
            raise AssertionError("PostgreSQL row count differs")
        # Normalize driver-returned Decimal and timezone-aware datetime to the same Python representation.
        if _canonical([dict(zip(columns, record)) for record in pg_rows]) != _canonical(rows):
            raise AssertionError("PostgreSQL round-trip differs from JSONL reference")
        try:
            with pg.transaction():
                pg.execute(insert_sql, values[:1])
        except psycopg.errors.UniqueViolation:
            pass
        else:
            raise AssertionError("PostgreSQL primary key did not reject duplicate")
        # A rejected invalid row must not leave a partial transaction behind.
        before = pg.execute(f"SELECT count(*) FROM {schema}.candles").fetchone()[0]
        try:
            with pg.transaction():
                bad = list(values[0])
                bad[columns.index("volume_base")] = Decimal("-1")
                pg.execute(insert_sql, tuple(bad))
        except psycopg.errors.CheckViolation:
            pass
        else:
            raise AssertionError("PostgreSQL CHECK did not reject negative volume")
        after = pg.execute(f"SELECT count(*) FROM {schema}.candles").fetchone()[0]
        if before != after:
            raise AssertionError("PostgreSQL rollback did not preserve row count")
        pg.execute(f"DROP SCHEMA {schema} CASCADE")

    digest = hashlib.sha256(parquet_path.read_bytes()).hexdigest()
    report = {
        "status": "passed",
        "reference_rows": len(rows),
        "parquet_rows": len(parquet_rows),
        "duckdb_rows": 5976,
        "postgresql_rows": len(pg_rows),
        "cohort_counts": COHORT_COUNTS,
        "parquet_sha256": digest,
        "parquet_bytes": parquet_path.stat().st_size,
        "duckdb_bytes": db_path.stat().st_size,
        "negative_tests": {"duckdb_duplicate_pk": "passed", "postgresql_duplicate_pk": "passed",
                           "postgresql_negative_volume_check": "passed", "postgresql_rollback": "passed"},
    }
    (output_dir / "storage_conformance_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--postgres-url", default=os.environ.get("DATABASE_URL"))
    args = parser.parse_args()
    if not args.postgres_url:
        parser.error("--postgres-url or DATABASE_URL is required")
    print(json.dumps(run_conformance(args.input, args.output, args.postgres_url), indent=2))


if __name__ == "__main__":
    main()
