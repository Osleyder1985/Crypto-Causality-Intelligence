#!/usr/bin/env python3
"""Acquire checksum-verified Binance BTCUSDT 1-minute Spot and USD-M klines."""
from __future__ import annotations
import argparse, csv, hashlib, io, json, time, urllib.error, urllib.request, zipfile
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

BASE = "https://data.binance.vision/data"
MARKETS = {"spot": "spot", "usd_m": "futures/um"}

def fetch(url: str) -> bytes:
    error = None
    for attempt in range(5):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "Crypto-Causality-Intelligence/klines-audit"})
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            error = exc
            if exc.code not in (408, 429, 500, 502, 503, 504):
                raise
            time.sleep(min(2 ** attempt, 30))
        except (urllib.error.URLError, TimeoutError) as exc:
            error = exc
            time.sleep(min(2 ** attempt, 30))
    raise RuntimeError(f"Download failed: {url}: {error}")

def checksum_value(payload: bytes) -> str:
    value = payload.decode("ascii").strip().split()[0].lower()
    if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("Invalid SHA-256 checksum file")
    return value

def parse_zip(payload: bytes, market: str, day_start_ms: int) -> tuple[list[dict], str]:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        members = [name for name in archive.namelist() if name.endswith(".csv")]
        if len(members) != 1:
            raise ValueError(f"Expected one CSV, found {members}")
        content = archive.read(members[0]).decode("utf-8-sig")
    result, seen = [], set()
    previous = None
    for line, row in enumerate(csv.reader(io.StringIO(content)), 1):
        if not row:
            continue
        if row[0].lower() in ("open_time", "open time"):
            continue
        if len(row) != 12:
            raise ValueError(f"{market}:{line}: expected 12 kline columns, got {len(row)}")
        timestamp_original = int(row[0])
        timestamp_divisor = 1000 if market == "spot" else 1
        timestamp = timestamp_original // timestamp_divisor
        if not day_start_ms <= timestamp < day_start_ms + 86_400_000:
            raise ValueError(f"{market}:{line}: open timestamp outside UTC date")
        if timestamp in seen or (previous is not None and timestamp <= previous):
            raise ValueError(f"{market}:{line}: duplicate or unordered open timestamp")
        seen.add(timestamp)
        previous = timestamp
        open_, high, low, close = map(Decimal, row[1:5])
        volume, quote_volume = Decimal(row[5]), Decimal(row[7])
        trade_count = int(row[8])
        taker_base, taker_quote = Decimal(row[9]), Decimal(row[10])
        if min(open_, high, low, close) <= 0 or volume < 0 or quote_volume < 0:
            raise ValueError(f"{market}:{line}: invalid price or volume")
        if not (low <= open_ <= high and low <= close <= high):
            raise ValueError(f"{market}:{line}: inconsistent OHLC")
        if trade_count < 0 or not (0 <= taker_base <= volume) or not (0 <= taker_quote <= quote_volume):
            raise ValueError(f"{market}:{line}: inconsistent trade/taker volumes")
        result.append({
            "market": market, "open_time_ms": timestamp, "open_time_original": timestamp_original,
            "timestamp_unit": "microseconds" if market == "spot" else "milliseconds", "interval": "1m",
            "open": str(open_), "high": str(high), "low": str(low), "close": str(close),
            "volume_base": str(volume), "quote_volume_usdt": str(quote_volume),
            "trade_count": trade_count, "taker_buy_base_volume": str(taker_base),
            "taker_buy_quote_volume_usdt": str(taker_quote),
            "close_time_ms": int(row[6]) // timestamp_divisor, "source_ignore_field": row[11],
        })
    if not result:
        raise ValueError(f"{market}: empty kline archive")
    return result, members[0]

def run(day_text: str, output: Path) -> dict:
    day = date.fromisoformat(day_text)
    start = int(datetime(day.year, day.month, day.day, tzinfo=timezone.utc).timestamp() * 1000)
    raw = output / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    report = {"provider": "Binance Vision", "symbol": "BTCUSDT", "date_utc": day_text, "interval": "1m", "markets": {}}
    for market, path in MARKETS.items():
        base = f"{BASE}/{path}/daily/klines/BTCUSDT/1m/BTCUSDT-1m-{day_text}.zip"
        archive, checksum = fetch(base), fetch(base + ".CHECKSUM")
        digest = hashlib.sha256(archive).hexdigest()
        if digest != checksum_value(checksum):
            raise ValueError(f"{market}: ZIP checksum mismatch")
        zip_name = f"{market}-1m-klines-{day_text}.zip"
        (raw / zip_name).write_bytes(archive)
        (raw / (zip_name + ".CHECKSUM")).write_bytes(checksum)
        rows, member = parse_zip(archive, market, start)
        filename = f"{market}_klines_1m.jsonl"
        with (output / filename).open("w", encoding="utf-8") as stream:
            for item in rows:
                stream.write(json.dumps(item, separators=(",", ":")) + "\n")
        expected = 1440
        report["markets"][market] = {
            "rows": len(rows), "expected_rows": expected, "missing_minutes": expected - len(rows),
            "csv_member": member, "zip_bytes": len(archive), "zip_sha256": digest,
            "raw_zip": f"raw/{zip_name}", "checksum_file": f"raw/{zip_name}.CHECKSUM",
            "events_file": filename, "start_open_time_ms": rows[0]["open_time_ms"],
            "end_open_time_ms": rows[-1]["open_time_ms"],
        }
    report["status"] = "acquired_and_checksum_verified"
    (output / "klines_acquisition_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default="2026-10-06")
    parser.add_argument("--output", type=Path, default=Path("artifacts/btcusdt_aggtrades"))
    args = parser.parse_args()
    result = run(args.date, args.output)
    print(json.dumps({"status": result["status"], "markets": result["markets"]}, indent=2))
