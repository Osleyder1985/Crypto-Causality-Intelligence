#!/usr/bin/env python3
"""Acquire consecutive checksum-verified Binance BTCUSDT daily flows.

The output contains concatenated one-second Spot and USD-M flow grids over
consecutive UTC dates, plus each original ZIP and a SHA-256 manifest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from datetime import date, timedelta
from pathlib import Path

from scripts.research.download_binance_btcusdt_aggtrades import run as acquire_day


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(start_date: str, days: int, output: Path) -> dict:
    if days < 1 or days > 31:
        raise ValueError("days must be between 1 and 31")
    first = date.fromisoformat(start_date)
    output.mkdir(parents=True, exist_ok=True)
    spot_path = output / "spot_flow_1s.jsonl"
    futures_path = output / "usd_m_flow_1s.jsonl"
    manifest_path = output / "multiday_acquisition_manifest.json"
    if any(path.exists() for path in (spot_path, futures_path, manifest_path)):
        raise FileExistsError("output already contains a multiday acquisition; use a fresh directory")

    raw_root = output / "raw"
    raw_root.mkdir(exist_ok=True)
    manifest = {
        "provider": "Binance Vision",
        "symbol": "BTCUSDT",
        "start_date_utc": first.isoformat(),
        "days": days,
        "end_date_utc_exclusive": (first + timedelta(days=days)).isoformat(),
        "markets": {"spot": [], "usd_m": []},
        "flow_files": {
            "spot": spot_path.name,
            "usd_m": futures_path.name,
            "bucket_ms": 1000,
        },
        "status": "acquiring",
    }

    with spot_path.open("w", encoding="utf-8") as spot_out, futures_path.open("w", encoding="utf-8") as futures_out:
        for offset in range(days):
            day = first + timedelta(days=offset)
            with tempfile.TemporaryDirectory(prefix=f"cci-{day.isoformat()}-") as temporary:
                day_dir = Path(temporary)
                report = acquire_day(day.isoformat(), day_dir)
                for market, destination in (("spot", spot_out), ("usd_m", futures_out)):
                    source = day_dir / f"{market}_flow_1s.jsonl"
                    with source.open(encoding="utf-8") as source_handle:
                        shutil.copyfileobj(source_handle, destination)
                    raw_name = f"{market}-aggTrades-{day.isoformat()}.zip"
                    checksum_name = raw_name + ".CHECKSUM"
                    raw_destination = raw_root / day.isoformat()
                    raw_destination.mkdir(exist_ok=True)
                    shutil.copy2(day_dir / "raw" / raw_name, raw_destination / raw_name)
                    shutil.copy2(day_dir / "raw" / checksum_name, raw_destination / checksum_name)
                    market_report = report["markets"][market]
                    manifest["markets"][market].append({
                        "date_utc": day.isoformat(),
                        "trade_rows": market_report["rows"],
                        "zip": f"raw/{day.isoformat()}/{raw_name}",
                        "zip_sha256": sha256_file(raw_destination / raw_name),
                        "checksum_file": f"raw/{day.isoformat()}/{checksum_name}",
                        "flow_rows": market_report["aggregates"]["1s"]["rows"],
                    })

    manifest["status"] = "all_days_acquired_and_checksum_verified"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", required=True, help="first UTC date, YYYY-MM-DD")
    parser.add_argument("--days", type=int, default=6)
    parser.add_argument("--output", type=Path, default=Path("artifacts/btcusdt_multiday"))
    args = parser.parse_args()
    result = run(args.start_date, args.days, args.output)
    print(json.dumps({
        "status": result["status"],
        "start_date_utc": result["start_date_utc"],
        "days": result["days"],
        "end_date_utc_exclusive": result["end_date_utc_exclusive"],
        "market_trade_rows": {
            market: sum(day["trade_rows"] for day in result["markets"][market])
            for market in ("spot", "usd_m")
        },
    }, indent=2))
