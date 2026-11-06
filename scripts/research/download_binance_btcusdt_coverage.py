#!/usr/bin/env python3
"""Download and audit the BTCUSDT Binance Spot hourly cohort.

Uses only the Python standard library. It preserves every raw API page and emits
normalized JSONL plus a machine-readable audit report. No credentials are needed
for this public market-data endpoint.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_URL = "https://data-api.binance.vision/api/v3/klines"
SYMBOL = "BTCUSDT"
INTERVAL = "1h"
INTERVAL_MS = 3_600_000
LIMIT = 1000

WINDOWS = [
    ("decline_2025_10_06_2025_11_21", "2025-10-06T17:00:00+00:00", "2025-11-21T12:00:00+00:00", 1099),
    ("decline_2026_01_14_2026_02_05", "2026-01-14T20:00:00+00:00", "2026-02-06T00:00:00+00:00", 532),
    ("rise_2026_02_05_2026_05_06", "2026-02-06T00:00:00+00:00", "2026-05-06T09:00:00+00:00", 2145),
    ("decline_2026_05_06_2026_06_30", "2026-05-06T09:00:00+00:00", "2026-07-01T01:00:00+00:00", 1336),
    ("rise_2026_08_16_2026_09_21", "2026-08-16T21:00:00+00:00", "2026-09-21T21:00:00+00:00", 864),
]


def epoch_ms(value: str) -> int:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError(f"Timestamp must include timezone: {value}")
    return int(dt.astimezone(timezone.utc).timestamp() * 1000)


def iso_ms(value: int) -> str:
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def fetch_page(start_ms: int, end_exclusive_ms: int, timeout: int = 20) -> tuple[bytes, list]:
    params = urllib.parse.urlencode({
        "symbol": SYMBOL,
        "interval": INTERVAL,
        "startTime": start_ms,
        "endTime": end_exclusive_ms - 1,
        "limit": LIMIT,
    })
    request = urllib.request.Request(
        f"{BASE_URL}?{params}",
        headers={"User-Agent": "Crypto-Causality-Intelligence/coverage-audit"},
    )
    last_error: Exception | None = None
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read()
            payload = json.loads(body)
            if not isinstance(payload, list):
                raise ValueError(f"Unexpected Binance response: {payload!r}")
            return body, payload
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code not in (418, 429, 500, 502, 503, 504):
                raise
            retry_after = exc.headers.get("Retry-After")
            delay = float(retry_after) if retry_after else min(2 ** attempt, 30)
            time.sleep(delay)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            time.sleep(min(2 ** attempt, 30))
    raise RuntimeError(f"Binance request failed after retries: {last_error}") from last_error


def validate_candle(row: list) -> list[str]:
    problems: list[str] = []
    if len(row) != 12:
        return ["invalid_field_count"]
    try:
        open_price, high, low, close, volume = map(float, (row[1], row[2], row[3], row[4], row[5]))
    except (TypeError, ValueError):
        return ["non_numeric_ohlcv"]
    if not (low <= open_price <= high and low <= close <= high and low <= high):
        problems.append("ohlc_invariant_violation")
    if volume < 0:
        problems.append("negative_volume")
    if not isinstance(row[0], int) or not isinstance(row[6], int):
        problems.append("invalid_timestamp_type")
    return problems


def download(output: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    raw_dir = output / "raw_pages"
    raw_dir.mkdir(exist_ok=True)
    normalized_path = output / "btc_usdt_1h.jsonl"
    report: dict[str, Any] = {
        "symbol": SYMBOL,
        "market_type": "SPOT",
        "interval": INTERVAL,
        "timestamp_unit": "milliseconds",
        "boundary_convention": "[start_inclusive, end_exclusive)",
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "windows": [],
    }
    all_rows: list[dict[str, Any]] = []

    for name, start_text, end_text, expected_count in WINDOWS:
        start_ms, end_ms = epoch_ms(start_text), epoch_ms(end_text)
        cursor = start_ms
        rows: list[list] = []
        pages: list[dict[str, Any]] = []
        page_no = 0
        while cursor < end_ms:
            page_no += 1
            started = time.monotonic()
            body, payload = fetch_page(cursor, end_ms)
            elapsed = time.monotonic() - started
            digest = hashlib.sha256(body).hexdigest()
            raw_file = raw_dir / f"{name}_page_{page_no:03d}.json"
            raw_file.write_bytes(body)
            pages.append({
                "page": page_no,
                "request_start_time_ms": cursor,
                "request_end_time_ms_exclusive": end_ms,
                "rows": len(payload),
                "sha256": digest,
                "raw_file": str(raw_file.relative_to(output)),
                "elapsed_seconds": round(elapsed, 6),
            })
            if not payload:
                break
            page_opens = [r[0] for r in payload if isinstance(r, list) and len(r) == 12]
            if len(page_opens) != len(payload):
                raise ValueError(f"{name}: malformed candle in page {page_no}")
            if page_opens != sorted(page_opens) or len(page_opens) != len(set(page_opens)):
                raise ValueError(f"{name}: unordered or duplicate open times in page {page_no}")
            if page_opens[0] < cursor or page_opens[-1] >= end_ms:
                raise ValueError(f"{name}: API returned candle outside requested window")
            rows.extend(payload)
            next_cursor = page_opens[-1] + INTERVAL_MS
            if next_cursor <= cursor:
                raise RuntimeError(f"{name}: pagination cursor did not advance")
            cursor = next_cursor
            if len(payload) < LIMIT:
                break

        opens = [r[0] for r in rows]
        expected_opens = list(range(start_ms, end_ms, INTERVAL_MS))
        missing = sorted(set(expected_opens) - set(opens))
        unexpected = sorted(set(opens) - set(expected_opens))
        duplicate_count = len(opens) - len(set(opens))
        row_problems = [
            {"open_time": iso_ms(row[0]), "problems": validate_candle(row)}
            for row in rows if validate_candle(row)
        ]
        gaps = []
        for missing_ms in missing:
            gaps.append({
                "open_time": iso_ms(missing_ms),
                "classification": "unknown_gap",
                "note": "Requires investigation; do not impute.",
            })

        for row in rows:
            all_rows.append({
                "cohort_window": name,
                "provider": "binance",
                "market_type": "SPOT",
                "symbol": SYMBOL,
                "interval": INTERVAL,
                "open_time_ms": row[0],
                "open_time_utc": iso_ms(row[0]),
                "open": row[1],
                "high": row[2],
                "low": row[3],
                "close": row[4],
                "volume_base": row[5],
                "close_time_ms": row[6],
                "quote_volume": row[7],
                "trade_count": row[8],
                "taker_buy_base_volume": row[9],
                "taker_buy_quote_volume": row[10],
                "source_ignore_field": row[11],
            })

        report["windows"].append({
            "name": name,
            "start_time_utc": start_text,
            "end_time_utc_exclusive": end_text,
            "expected_candles": expected_count,
            "received_candles": len(rows),
            "coverage_pct": round(100 * len(set(opens) & set(expected_opens)) / expected_count, 6),
            "missing_open_times": len(missing),
            "unexpected_open_times": len(unexpected),
            "duplicate_open_times": duplicate_count,
            "ohlcv_violations": row_problems,
            "gaps": gaps,
            "pages": pages,
            "status": "pending_review" if missing or unexpected or duplicate_count or row_problems else "candidate_complete",
        })

    with normalized_path.open("w", encoding="utf-8") as stream:
        for row in all_rows:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")

    total_expected = sum(w[3] for w in WINDOWS)
    total_received = sum(len(set(
        row["open_time_ms"] for row in all_rows if row["cohort_window"] == w[0]
    )) for w in WINDOWS)
    report["summary"] = {
        "expected_candles": total_expected,
        "received_unique_candles": total_received,
        "normalized_rows": len(all_rows),
        "normalized_file": normalized_path.name,
        "status": "candidate_complete" if total_received == total_expected and all(
            w["status"] == "candidate_complete" for w in report["windows"]
        ) else "pending_review",
    }
    (output / "coverage_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/binance_btcusdt_coverage"))
    args = parser.parse_args()
    report = download(args.output)
    print(json.dumps(report["summary"], indent=2))
    if report["summary"]["status"] != "candidate_complete":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
