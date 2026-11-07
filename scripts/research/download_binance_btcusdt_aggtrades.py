#!/usr/bin/env python3
"""Acquire auditable Binance BTCUSDT Spot and USD-M daily aggTrades."""
from __future__ import annotations
import argparse, csv, hashlib, io, json, time, urllib.error, urllib.request, zipfile
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

BASE = "https://data.binance.vision/data"
SPECS = {
    "spot": ("spot", "microseconds", 1000, 8),
    "usd_m": ("futures/um", "milliseconds", 1, 7),
}

def fetch(url):
    error = None
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers={"User-Agent":"Crypto-Causality-Intelligence/aggtrades-audit"})
            with urllib.request.urlopen(req, timeout=60) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            error = exc
            if exc.code not in (408,429,500,502,503,504): raise
            time.sleep(min(2**attempt,30))
        except (urllib.error.URLError, TimeoutError) as exc:
            error = exc
            time.sleep(min(2**attempt,30))
    raise RuntimeError(f"Download failed: {url}: {error}")

def checksum_value(payload):
    value = payload.decode("ascii").strip().split()[0].lower()
    if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("Invalid SHA-256 checksum file")
    return value

def parse_bool(value):
    value = value.strip().lower()
    if value in ("true","1"): return True
    if value in ("false","0"): return False
    raise ValueError(f"Invalid isBuyerMaker value: {value!r}")

def parse_zip(payload, market, day_start_ms):
    _, unit, divisor, expected_columns = SPECS[market]
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        members = [name for name in archive.namelist() if name.endswith(".csv")]
        if len(members) != 1: raise ValueError(f"Expected one CSV, found {members}")
        text = archive.read(members[0]).decode("utf-8-sig")
    result, ids = [], set()
    previous_id = previous_ts = None
    for line, row in enumerate(csv.reader(io.StringIO(text)), 1):
        if not row: continue
        if row[0].lower() in ("agg_trade_id","aggregatetradeid"): continue
        if len(row) != expected_columns: raise ValueError(f"{market}:{line}: invalid column count")
        trade_id, price, qty, timestamp = int(row[0]), Decimal(row[1]), Decimal(row[2]), int(row[5])
        buyer_maker = parse_bool(row[6])
        timestamp_ms = timestamp // divisor
        if not day_start_ms <= timestamp_ms < day_start_ms + 86_400_000:
            raise ValueError(f"{market}:{line}: timestamp outside UTC date")
        if trade_id in ids or (previous_id is not None and trade_id <= previous_id):
            raise ValueError(f"{market}:{line}: duplicate or unordered aggregate trade ID")
        if previous_ts is not None and timestamp < previous_ts:
            raise ValueError(f"{market}:{line}: unordered timestamp")
        if price <= 0 or qty <= 0: raise ValueError(f"{market}:{line}: invalid price or quantity")
        ids.add(trade_id); previous_id = trade_id; previous_ts = timestamp
        notional = price * qty
        signed = -notional if buyer_maker else notional
        result.append({"market":market,"agg_trade_id":trade_id,"timestamp_original":timestamp,
            "timestamp_unit":unit,"timestamp_ms":timestamp_ms,"price":str(price),
            "quantity_btc":str(qty),"quote_notional_usdt":str(notional),
            "aggressor_side":"sell" if buyer_maker else "buy",
            "signed_taker_notional_usdt":str(signed)})
    if not result: raise ValueError(f"{market}: empty daily archive")
    return result, members[0]

def aggregate(rows, width_ms):
    buckets = defaultdict(lambda: {"buy":Decimal(0),"sell":Decimal(0),"net":Decimal(0),"count":0})
    for row in rows:
        key = row["timestamp_ms"] // width_ms * width_ms
        value = Decimal(row["quote_notional_usdt"])
        side = row["aggressor_side"]
        buckets[key][side] += value
        buckets[key]["net"] += Decimal(row["signed_taker_notional_usdt"])
        buckets[key]["count"] += 1
    return [{"bucket_start_ms":key,"bucket_ms":width_ms,
        "aggressive_buy_usdt":str(value["buy"]),"aggressive_sell_usdt":str(value["sell"]),
        "signed_taker_notional_usdt":str(value["net"]),"agg_trade_count":value["count"]}
        for key,value in sorted(buckets.items())]

def run(day_text, output):
    day = date.fromisoformat(day_text)
    start = int(datetime(day.year,day.month,day.day,tzinfo=timezone.utc).timestamp()*1000)
    output.mkdir(parents=True,exist_ok=True); raw_dir=output/"raw"; raw_dir.mkdir(exist_ok=True)
    report={"provider":"Binance Vision","symbol":"BTCUSDT","date_utc":day_text,
        "interval_utc":{"start_inclusive_ms":start,"end_exclusive_ms":start+86_400_000},"markets":{}}
    for market,(path,unit,_,_) in SPECS.items():
        base=f"{BASE}/{path}/daily/aggTrades/BTCUSDT/BTCUSDT-aggTrades-{day_text}.zip"
        archive=fetch(base); checksum=fetch(base+".CHECKSUM")
        digest=hashlib.sha256(archive).hexdigest()
        if digest != checksum_value(checksum): raise ValueError(f"{market}: ZIP checksum mismatch")
        zip_name=f"{market}-aggTrades-{day_text}.zip"
        checksum_name=zip_name+".CHECKSUM"
        (raw_dir/zip_name).write_bytes(archive); (raw_dir/checksum_name).write_bytes(checksum)
        events,member=parse_zip(archive,market,start)
        event_name=f"{market}_aggtrades.jsonl"
        with (output/event_name).open("w",encoding="utf-8") as f:
            for event in events: f.write(json.dumps(event,separators=(",",":"))+"\n")
        series={}
        for label,width in (("1ms",1),("1s",1000),("1m",60000)):
            values=aggregate(events,width); filename=f"{market}_flow_{label}.jsonl"
            with (output/filename).open("w",encoding="utf-8") as f:
                for item in values: f.write(json.dumps(item,separators=(",",":"))+"\n")
            series[label]={"rows":len(values),"file":filename}
        report["markets"][market]={"rows":len(events),"csv_member":member,
            "timestamp_unit":unit,"zip_bytes":len(archive),"zip_sha256":digest,
            "raw_zip":f"raw/{zip_name}","checksum_file":f"raw/{checksum_name}",
            "events_file":event_name,"aggregates":series}
    report["status"]="acquired_and_checksum_verified"
    (output/"aggtrades_acquisition_report.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    return report

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date",default="2026-10-06")
    parser.add_argument("--output",type=Path,default=Path("artifacts/btcusdt_aggtrades"))
    args=parser.parse_args()
    result=run(args.date,args.output)
    print(json.dumps({"status":result["status"],"markets":result["markets"]},indent=2))
