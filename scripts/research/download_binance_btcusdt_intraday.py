#!/usr/bin/env python3
"""Acquire auditable Binance Spot BTCUSDT 1-minute candles for five 2026 research windows.

Raw API pages are retained verbatim and SHA-256 hashed. Windows use UTC boundaries
and the half-open convention [start, end). Missing candles are reported, never imputed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE_URL = "https://data-api.binance.vision/api/v3/klines"
SYMBOL = "BTCUSDT"
INTERVAL = "1m"
INTERVAL_MS = 60_000
LIMIT = 1000

# User-facing research clock is UTC-5. August starts one hour before the user-defined\n# 16:00 UTC-5 boundary to provide a pre-event baseline; the analytical anchor\n# remains 2026-08-16T21:00:00Z. Boundaries use UTC.
WINDOWS = [
    ("august_rally_2026", "2026-08-16T20:00:00Z", "2026-09-21T21:00:00Z"),
    ("september_vote_reaction_2026", "2026-09-15T17:00:00Z", "2026-09-21T21:00:00Z"),
    ("october_selloff_2026", "2026-10-06T05:00:00Z", "2026-10-07T05:00:00Z"),
    ("binance_incident_2026", "2026-10-29T05:00:00Z", "2026-10-31T05:00:00Z"),
    ("midterm_election_2026", "2026-11-03T05:00:00Z", "2026-11-05T05:00:00Z"),
]


def to_ms(value: str) -> int:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError(f"Timezone required: {value}")
    return int(dt.astimezone(timezone.utc).timestamp() * 1000)


def iso_ms(value: int) -> str:
    return datetime.fromtimestamp(value / 1000, timezone.utc).isoformat().replace("+00:00", "Z")


def fetch_page(start_ms: int, end_ms: int, timeout: int = 25) -> tuple[bytes, list]:
    query = urllib.parse.urlencode({
        "symbol": SYMBOL, "interval": INTERVAL,
        "startTime": start_ms, "endTime": end_ms - 1, "limit": LIMIT,
    })
    request = urllib.request.Request(
        f"{BASE_URL}?{query}",
        headers={"User-Agent": "Crypto-Causality-Intelligence/intraday-audit"},
    )
    last_error = None
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read()
            rows = json.loads(raw)
            if not isinstance(rows, list):
                raise ValueError(f"Unexpected Binance payload: {rows!r}")
            return raw, rows
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code not in (418, 429, 500, 502, 503, 504):
                raise
            delay = exc.headers.get("Retry-After")
            time.sleep(float(delay) if delay else min(2 ** attempt, 30))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            time.sleep(min(2 ** attempt, 30))
    raise RuntimeError(f"Binance request failed after retries: {last_error}") from last_error


def validate(row: list) -> list[str]:
    if not isinstance(row, list) or len(row) != 12:
        return ["invalid_field_count"]
    issues = []
    if not isinstance(row[0], int) or row[0] % INTERVAL_MS:
        issues.append("invalid_open_time")
    if not isinstance(row[6], int) or row[6] != row[0] + INTERVAL_MS - 1:
        issues.append("invalid_close_time")
    try:
        o, h, low, c, base, quote = map(float, (row[1], row[2], row[3], row[4], row[5], row[7]))
        taker_base, taker_quote = float(row[9]), float(row[10])
        if not all(math.isfinite(v) for v in (o, h, low, c, base, quote, taker_base, taker_quote)):
            issues.append("non_finite_value")
        if not (0 < low <= o <= h and low <= c <= h):
            issues.append("invalid_ohlc")
        if min(base, quote, taker_base, taker_quote) < 0:
            issues.append("negative_volume")
        if taker_base > base or taker_quote > quote:
            issues.append("taker_volume_exceeds_total")
    except (TypeError, ValueError, OverflowError):
        issues.append("non_numeric_value")
    if not isinstance(row[8], int) or row[8] < 0:
        issues.append("invalid_trade_count")
    return issues


def run(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    raw_dir = output / "raw_pages"
    raw_dir.mkdir(exist_ok=True)
    all_rows = []
    report = {
        "provider": "binance", "market_type": "SPOT", "symbol": SYMBOL,
        "interval": INTERVAL, "timestamp_unit": "milliseconds",
        "boundary_convention": "[start_inclusive, end_exclusive)",
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(), "windows": [],
    }

    for name, start_text, end_text in WINDOWS:
        start, end = to_ms(start_text), to_ms(end_text)
        cursor = start
        rows, pages = [], []
        page_number = 0
        while cursor < end:
            page_number += 1
            raw, payload = fetch_page(cursor, end)
            digest = hashlib.sha256(raw).hexdigest()
            raw_name = f"{name}_page_{page_number:04d}.json"
            (raw_dir / raw_name).write_bytes(raw)
            pages.append({"page": page_number, "rows": len(payload), "sha256": digest, "raw_file": f"raw_pages/{raw_name}"})
            if not payload:
                break
            opens = [r[0] for r in payload if isinstance(r, list) and len(r) == 12]
            if len(opens) != len(payload) or opens != sorted(opens) or len(opens) != len(set(opens)):
                raise ValueError(f"{name}: malformed, unordered, or duplicate page")
            if opens[0] < cursor or opens[-1] >= end:
                raise ValueError(f"{name}: out-of-window candle")
            rows.extend(payload)
            next_cursor = opens[-1] + INTERVAL_MS
            if next_cursor <= cursor:
                raise RuntimeError(f"{name}: pagination did not advance")
            cursor = next_cursor

        actual = {r[0] for r in rows}
        expected = set(range(start, end, INTERVAL_MS))
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        violations = [{"open_time_utc": iso_ms(r[0]), "problems": validate(r)} for r in rows if validate(r)]
        for r in rows:
            all_rows.append({
                "cohort_window": name, "provider": "binance", "market_type": "SPOT",
                "symbol": SYMBOL, "interval": INTERVAL,
                "open_time_ms": r[0], "open_time_utc": iso_ms(r[0]),
                "open": r[1], "high": r[2], "low": r[3], "close": r[4],
                "volume_base": r[5], "close_time_ms": r[6], "quote_volume": r[7],
                "trade_count": r[8], "taker_buy_base_volume": r[9],
                "taker_buy_quote_volume": r[10],
            })
        report["windows"].append({
            "name": name, "start_time_utc": start_text, "end_time_utc_exclusive": end_text,
            "expected_candles": len(expected), "received_candles": len(rows),
            "missing_candles": len(missing), "unexpected_candles": len(unexpected),
            "ohlcv_violations": violations,
            "missing_open_times_utc": [iso_ms(v) for v in missing],
            "pages": pages,
            "status": "candidate_complete" if not missing and not unexpected and not violations and len(rows) == len(actual) else "pending_review",
        })

    data_path = output / "btc_usdt_1m.jsonl"
    with data_path.open("w", encoding="utf-8") as stream:
        for row in all_rows:
            stream.write(json.dumps(row, separators=(",", ":"), ensure_ascii=False) + "\n")
    report["summary"] = {
        "normalized_file": data_path.name, "normalized_rows": len(all_rows),
        "expected_candles": sum(w["expected_candles"] for w in report["windows"]),
        "status": "candidate_complete" if all(w["status"] == "candidate_complete" for w in report["windows"]) else "pending_review",
    }
    (output / "intraday_coverage_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/binance_btcusdt_intraday"))
    args = parser.parse_args()
    result = run(args.output)
    print(json.dumps(result["summary"], indent=2))
    if result["summary"]["status"] != "candidate_complete":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
