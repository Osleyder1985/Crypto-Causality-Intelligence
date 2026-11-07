"""Cohort-safe descriptive multi-factor diagnostics for BTCUSDT Spot hourly candles."""
from __future__ import annotations
import argparse, json, math
from collections import defaultdict
from pathlib import Path
from typing import Any

HORIZONS_HOURS = (1, 3, 6, 12, 24)

def _pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 2: return None
    mx, my = sum(xs)/len(xs), sum(ys)/len(ys)
    dx, dy = [x-mx for x in xs], [y-my for y in ys]
    vx, vy = sum(x*x for x in dx), sum(y*y for y in dy)
    return sum(x*y for x,y in zip(dx,dy))/math.sqrt(vx*vy) if vx and vy else None

def _num(row: dict, key: str, line: int) -> float:
    try: value = float(row[key])
    except (KeyError, TypeError, ValueError) as exc: raise ValueError(f"line {line}: invalid {key}") from exc
    if not math.isfinite(value): raise ValueError(f"line {line}: non-finite {key}")
    return value

def load_cohorts(path: str | Path) -> dict[str, list[dict[str, Any]]]:
    cohorts = defaultdict(list)
    with Path(path).open(encoding="utf-8") as stream:
        for line, raw in enumerate(stream, 1):
            if not raw.strip(): continue
            row = json.loads(raw)
            for key, expected in {"provider":"binance","market_type":"SPOT","symbol":"BTCUSDT","interval":"1h"}.items():
                if row.get(key) != expected: raise ValueError(f"line {line}: expected {key}={expected}")
            name = row.get("cohort_window")
            if not isinstance(name, str) or not name: raise ValueError(f"line {line}: missing cohort_window")
            try: row["_ts"] = int(row["open_time_ms"])
            except (KeyError, TypeError, ValueError) as exc: raise ValueError(f"line {line}: invalid open_time_ms") from exc
            vals = {k:_num(row,k,line) for k in ("open","high","low","close","quote_volume","trade_count","taker_buy_quote_volume")}
            o,h,l,c,qv,trades,buy = (vals[k] for k in ("open","high","low","close","quote_volume","trade_count","taker_buy_quote_volume"))
            if min(o,h,l,c,qv,trades) <= 0: raise ValueError(f"line {line}: OHLCV and trade_count must be positive")
            if l > min(o,c) or h < max(o,c) or l > h: raise ValueError(f"line {line}: invalid OHLC relationship")
            if buy < 0 or buy > qv: raise ValueError(f"line {line}: taker buy quote volume outside total")
            row.update(_open=o,_high=h,_low=l,_close=c,_quote_volume=qv,_trade_count=trades,_taker_buy_quote=buy)
            cohorts[name].append(row)
    for name, rows in cohorts.items():
        rows.sort(key=lambda r:r["_ts"]); times=[r["_ts"] for r in rows]
        if len(times)!=len(set(times)): raise ValueError(f"{name}: duplicate hourly timestamps")
        if any(b-a != 3_600_000 for a,b in zip(times,times[1:])): raise ValueError(f"{name}: non-contiguous hourly timestamps")
    return dict(cohorts)

def _assoc(xs: list[float], ys: list[float]) -> dict:
    return {"observations":len(xs),"pearson_correlation":_pearson(xs,ys)}

def analyze_cohorts(cohorts: dict[str, list[dict]]) -> dict:
    report={"status":"descriptive_multifactor_baseline","provider":"binance","market_type":"SPOT","symbol":"BTCUSDT","interval":"1h",
            "horizons_hours":list(HORIZONS_HOURS),"causal_claim":False,
            "interpretation":"Descriptive correlations only; no causal effect or out-of-sample predictability is established.","cohorts":{}}
    total=0
    for name, rows in sorted(cohorts.items()):
        total += len(rows); closes=[r["_close"] for r in rows]
        features={k:[] for k in ("signed_taker_buy_quote_imbalance","log_quote_volume","log_trade_count","normalized_candle_range","candle_body_return","close_location_value")}
        for r in rows:
            span=r["_high"]-r["_low"]
            features["signed_taker_buy_quote_imbalance"].append((2*r["_taker_buy_quote"]-r["_quote_volume"])/r["_quote_volume"])
            features["log_quote_volume"].append(math.log(r["_quote_volume"]))
            features["log_trade_count"].append(math.log(r["_trade_count"]))
            features["normalized_candle_range"].append(span/r["_open"])
            features["candle_body_return"].append(math.log(r["_close"]/r["_open"]))
            features["close_location_value"].append((2*r["_close"]-r["_high"]-r["_low"])/span if span else 0.0)
        returns=[math.log(closes[i]/closes[i-1]) for i in range(1,len(rows))]
        contemporaneous={}
        for key, values in features.items():
            contemporaneous[key]={"return":_assoc(values[1:],returns),"absolute_return":_assoc(values[1:],[abs(x) for x in returns])}
        forward={}
        for horizon in HORIZONS_HOURS:
            targets=[math.log(closes[i+horizon]/closes[i]) for i in range(len(rows)-horizon)]
            forward[str(horizon)]={key:_assoc(values[:len(targets)],targets) for key,values in features.items()}
        report["cohorts"][name]={"candles":len(rows),"start_open_time_ms":rows[0]["_ts"],"end_open_time_ms":rows[-1]["_ts"],
          "price_change_pct":(closes[-1]/rows[0]["_open"]-1)*100,"contemporaneous_associations":contemporaneous,"forward_return_associations":forward}
    report["total_candles"]=total
    return report

def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument("--input",required=True); parser.add_argument("--output")
    args=parser.parse_args(); rendered=json.dumps(analyze_cohorts(load_cohorts(args.input)),indent=2,sort_keys=True)+"\\n"
    if args.output: Path(args.output).write_text(rendered,encoding="utf-8")
    else: print(rendered,end="")
    return 0
if __name__=="__main__": raise SystemExit(main())
