#!/usr/bin/env python3
"""Descarga reproducible de muestras BTC/ETH para Issue #11."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BINANCE = "https://data-api.binance.vision/api/v3/klines"
BINANCE_METADATA = "https://data-api.binance.vision/api/v3/exchangeInfo"
KRAKEN = "https://api.kraken.com/0/public/OHLC"
KRAKEN_METADATA = "https://api.kraken.com/0/public/AssetPairs"
COINGECKO = "https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart/range"
ASSETS = {
    "BTC": {"binance": "BTCUSDT", "kraken": "XBTUSD", "coingecko": "bitcoin"},
    "ETH": {"binance": "ETHUSDT", "kraken": "ETHUSD", "coingecko": "ethereum"},
}
INTERVALS = {
    "1h": {"binance": "1h", "kraken": 60, "seconds": 3600},
    "1d": {"binance": "1d", "kraken": 1440, "seconds": 86400},
}


def utc_epoch(value: str) -> int:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("Los límites deben incluir zona horaria UTC (Z).")
    return int(dt.astimezone(timezone.utc).timestamp())


def request_json(url: str, attempts: int = 5):
    headers = {"User-Agent": "Crypto-Causality-Intelligence/0.1 (research PoC)"}
    started = time.monotonic()
    for attempt in range(attempts):
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=45) as response:
                body = response.read()
                metadata = {
                    "url": url,
                    "http_status": response.status,
                    "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
                    "attempts": attempt + 1,
                    "retries": attempt,
                    "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                }
                return json.loads(body), body, metadata
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == attempts - 1:
                raise
            time.sleep(min(2 ** attempt, 30))
        except (urllib.error.URLError, TimeoutError):
            if attempt == attempts - 1:
                raise
            time.sleep(min(2 ** attempt, 30))
    raise RuntimeError("No fue posible completar la solicitud.")


def save_raw(out: Path, name: str, body: bytes):
    path = out / "raw" / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return {"path": str(path), "sha256": hashlib.sha256(body).hexdigest(),
            "bytes": len(body)}


def metadata_record(provider, endpoint, request_meta, raw, parameters, status="captured"):
    return {
        "provider": provider, "endpoint": endpoint, "request": request_meta,
        "query_parameters": parameters, "raw": raw, "status": status,
    }


def fetch_binance_metadata(out: Path):
    data, body, request_meta = request_json(BINANCE_METADATA)
    raw = save_raw(out, "binance_exchange_info", body)
    wanted = {ids["binance"] for ids in ASSETS.values()}
    selected = []
    for symbol in data.get("symbols", []):
        if symbol.get("symbol") not in wanted:
            continue
        selected.append({
            key: symbol.get(key) for key in (
                "symbol", "status", "baseAsset", "quoteAsset",
                "baseAssetPrecision", "quoteAssetPrecision",
                "isSpotTradingAllowed", "permissionSets", "filters"
            ) if key in symbol
        })
    return metadata_record("binance", BINANCE_METADATA, request_meta, raw, {}), selected


def fetch_kraken_metadata(out: Path):
    data, body, request_meta = request_json(KRAKEN_METADATA)
    if data.get("error"):
        raise RuntimeError(f"Kraken AssetPairs API error: {data['error']}")
    raw = save_raw(out, "kraken_asset_pairs", body)
    wanted = {ids["kraken"] for ids in ASSETS.values()}
    selected = []
    for key, pair in data.get("result", {}).items():
        aliases = {key, pair.get("altname"), pair.get("wsname")}
        if not aliases.intersection(wanted):
            continue
        selected.append({
            "result_key": key,
            **{name: pair.get(name) for name in (
                "altname", "wsname", "aclass_base", "base", "aclass_quote",
                "quote", "status", "pair_decimals", "lot_decimals",
                "lot_multiplier", "ordermin", "costmin"
            ) if name in pair}
        })
    return metadata_record("kraken", KRAKEN_METADATA, request_meta, raw, {}), selected


def write_csv(path: Path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def validate_candles(rows, interval_seconds, start_s, end_s):
    timestamps = [int(r["open_time_utc"]) for r in rows]
    duplicates = len(timestamps) - len(set(timestamps))
    ordered = all(a < b for a, b in zip(timestamps, timestamps[1:]))
    invalid, gaps = [], []

    for row in rows:
        o, h, low, c = (float(row[k]) for k in ("open", "high", "low", "close"))
        volume = float(row.get("base_volume", row.get("volume", 0)))
        if not (low <= min(o, c) <= max(o, c) <= h):
            invalid.append({"timestamp": row["open_time_utc"], "type": "ohlc"})
        if volume < 0:
            invalid.append({"timestamp": row["open_time_utc"], "type": "negative_base_volume"})

    # El diagnóstico de huecos se calcula sobre timestamps únicos y ordenados.
    # La secuencia original se conserva para detectar desorden por separado.
    sorted_timestamps = sorted(set(timestamps))
    for previous, current in zip(sorted_timestamps, sorted_timestamps[1:]):
        delta = current - previous
        if delta != interval_seconds:
            gaps.append({
                "from": previous, "to": current,
                "missing_intervals": max(0, delta // interval_seconds - 1),
            })

    expected = (end_s - start_s) // interval_seconds
    in_window = [t for t in timestamps if start_s <= t < end_s]
    outside_window = [t for t in timestamps if not start_s <= t < end_s]
    misaligned = [t for t in in_window if t % interval_seconds != 0]
    zero_volume = sum(float(r.get("base_volume", r.get("volume", 0))) == 0 for r in rows)
    trade_counts = [int(r["trade_count"]) for r in rows if r.get("trade_count") not in (None, "")]
    critical = []
    if not rows:
        critical.append("empty_response")
    if duplicates:
        critical.append("duplicate_timestamps")
    if not ordered and len(rows) > 1:
        critical.append("timestamps_not_strictly_ordered")
    if invalid:
        critical.append("ohlc_or_volume_violations")
    if outside_window:
        critical.append("timestamps_outside_window")
    if misaligned:
        critical.append("misaligned_timestamps")

    return {
        "records_received": len(rows), "records_in_window": len(in_window),
        "records_outside_window": len(outside_window),
        "records_expected_if_continuous": expected,
        "coverage_pct_if_continuous": round(100 * len(set(in_window)) / expected, 4) if expected else None,
        "duplicate_timestamps": duplicates, "strictly_ordered": ordered,
        "misaligned_timestamps": misaligned, "zero_base_volume_records": zero_volume,
        "trade_count_records": len(trade_counts),
        "zero_trade_count_records": sum(value == 0 for value in trade_counts),
        "ohlc_or_volume_violations": invalid, "gaps": gaps,
        "critical_violations": critical, "validation_passed": not critical,
        "gap_interpretation": "Un intervalo ausente no se clasifica automáticamente como pérdida de datos; contrastar la semántica y el conteo de operaciones del proveedor.",
    }


def metadata_validation_issues(provider, selected):
    """Comprueba presencia y estado de los mercados BTC/ETH esperados."""
    issues = []
    if provider == "binance":
        expected = {"BTCUSDT", "ETHUSDT"}
        found = {item.get("symbol"): item for item in selected}
        for symbol in sorted(expected):
            if symbol not in found:
                issues.append(f"missing_market:{symbol}")
            elif found[symbol].get("status") != "TRADING":
                issues.append(f"market_not_trading:{symbol}")
    elif provider == "kraken":
        expected = {"XBTUSD": "XBT/USD", "ETHUSD": "ETH/USD"}
        for altname, wsname in expected.items():
            match = next((item for item in selected
                          if item.get("altname") == altname or item.get("wsname") == wsname), None)
            if match is None:
                issues.append(f"missing_market:{altname}")
            elif match.get("status") != "online":
                issues.append(f"market_not_online:{altname}")
    return issues


def fetch_binance(asset, symbol, interval, start_s, end_s, out):
    params = urllib.parse.urlencode({
        "symbol": symbol, "interval": interval,
        "startTime": start_s * 1000, "endTime": end_s * 1000 - 1, "limit": 1000
    })
    data, body, request_meta = request_json(f"{BINANCE}?{params}")
    rows = []
    for k in data:
        rows.append({
            "provider": "binance", "asset": asset, "market_id": symbol,
            "base_asset": asset, "quote_asset": "USDT", "interval": interval,
            "open_time_utc": int(k[0]) // 1000, "close_time_utc": int(k[6]) // 1000,
            "open": k[1], "high": k[2], "low": k[3], "close": k[4],
            "volume": k[5], "base_volume": k[5], "base_volume_unit": asset,
            "quote_volume": k[7], "quote_volume_unit": "USDT",
            "trade_count": k[8], "taker_buy_base_volume": k[9],
            "taker_buy_base_volume_unit": asset, "taker_buy_quote_volume": k[10],
            "taker_buy_quote_volume_unit": "USDT",
        })
    raw = save_raw(out, f"binance_{asset}_{interval}", body)
    return rows, raw, request_meta


def fetch_kraken(asset, pair, interval, start_s, end_s, out):
    params = urllib.parse.urlencode({"pair": pair, "interval": interval, "since": start_s})
    data, body, request_meta = request_json(f"{KRAKEN}?{params}")
    if data.get("error"):
        raise RuntimeError(f"Kraken API error: {data['error']}")
    result = data["result"]
    pair_key = next(k for k in result if k != "last")
    base_unit = "XBT" if asset == "BTC" else "ETH"
    rows = []
    for k in result[pair_key]:
        ts = int(k[0])
        if start_s <= ts < end_s:
            rows.append({
                "provider": "kraken", "asset": asset, "market_id": pair_key,
                "base_asset": base_unit, "quote_asset": "USD",
                "interval": "1h" if interval == 60 else "1d",
                "open_time_utc": ts, "close_time_utc": ts + (3600 if interval == 60 else 86400) - 1,
                "open": k[1], "high": k[2], "low": k[3], "close": k[4],
                "volume": k[6], "base_volume": k[6], "base_volume_unit": base_unit,
                "quote_volume": "", "quote_volume_unit": "",
                "vwap": k[5], "trade_count": k[7],
                "taker_buy_base_volume": "", "taker_buy_quote_volume": "",
            })
    raw = save_raw(out, f"kraken_{asset}_{interval}", body)
    return rows, raw, pair_key, request_meta


def fetch_coingecko(asset, coin_id, start_s, end_s, interval):
    params = urllib.parse.urlencode({"vs_currency": "usd", "from": start_s, "to": end_s})
    data, body, request_meta = request_json(f"{COINGECKO.format(coin_id=coin_id)}?{params}")
    counts = {
        metric: sum(1 for timestamp_ms, _ in data.get(metric, [])
                    if start_s <= int(timestamp_ms) // 1000 < end_s)
        for metric in ("prices", "market_caps", "total_volumes")
    }
    response_info = {"sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)}
    return counts, response_info, request_meta


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hourly-start", default="2026-10-07T00:00:00Z")
    parser.add_argument("--hourly-end", default="2026-11-06T00:00:00Z",
                        help="Límite horario exclusivo en UTC.")
    parser.add_argument("--daily-start", default="2025-11-21T00:00:00Z")
    parser.add_argument("--daily-end", default="2026-11-06T00:00:00Z",
                        help="Límite diario exclusivo en UTC.")
    parser.add_argument("--out", default="artifacts/issue-11")
    args = parser.parse_args()
    windows = {
        "1h": (utc_epoch(args.hourly_start), utc_epoch(args.hourly_end), args.hourly_start, args.hourly_end),
        "1d": (utc_epoch(args.daily_start), utc_epoch(args.daily_end), args.daily_start, args.daily_end),
    }
    for label, (start_s, end_s, _, _) in windows.items():
        if end_s <= start_s or (end_s - start_s) % INTERVALS[label]["seconds"]:
            raise SystemExit(f"Ventana UTC inválida o desalineada para {label}.")
    out = Path(args.out)
    manifest = {
        "experiment": "issue-11",
        "windows_utc": {k: {"start_inclusive": v[2], "end_exclusive": v[3]} for k, v in windows.items()},
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "metadata": [], "metadata_selected_markets": {},
        "intervals": {}, "results": [],
        "limitations": [
            "Binance usa pares USDT; Kraken y CoinGecko usan USD. No comparar precios absolutos sin conversión documentada.",
            "CoinGecko market_chart/range entrega series agregadas, no velas OHLCV equivalentes.",
            "Kraken OHLC limita la respuesta a 720 observaciones; verificar conteo y cobertura.",
            "Una vela ausente en Kraken no implica automáticamente pérdida de datos: considerar intervalos sin operaciones.",
        ],
    }
    execution_failed = False
    manifest["metadata_validation"] = {}
    for provider, fetcher in (("binance", fetch_binance_metadata), ("kraken", fetch_kraken_metadata)):
        try:
            record, selected = fetcher(out)
            issues = metadata_validation_issues(provider, selected)
            record["validation_issues"] = issues
            if issues:
                record["status"] = "validation_error"
                execution_failed = True
            manifest["metadata"].append(record)
            manifest["metadata_selected_markets"][provider] = selected
            manifest["metadata_validation"][provider] = {
                "passed": not issues, "issues": issues,
            }
        except Exception as exc:
            execution_failed = True
            manifest["metadata"].append({"provider": provider, "status": "error", "error": str(exc)})
            manifest["metadata_selected_markets"][provider] = []
            manifest["metadata_validation"][provider] = {
                "passed": False, "issues": [str(exc)],
            }
    for label, spec in INTERVALS.items():
        start_s, end_s, _, _ = windows[label]
        manifest["intervals"][label] = {
            "seconds": spec["seconds"],
            "expected_continuous_records": (end_s - start_s) // spec["seconds"],
        }
        for asset, ids in ASSETS.items():
            for provider in ("binance", "kraken"):
                try:
                    if provider == "binance":
                        rows, raw, request_meta = fetch_binance(asset, ids["binance"], spec["binance"], start_s, end_s, out)
                        market_id = ids["binance"]
                    else:
                        rows, raw, market_id, request_meta = fetch_kraken(asset, ids["kraken"], spec["kraken"], start_s, end_s, out)
                    fields = [
                        "provider", "asset", "market_id", "base_asset", "quote_asset", "interval",
                        "open_time_utc", "close_time_utc", "open", "high", "low", "close",
                        "volume", "base_volume", "base_volume_unit", "quote_volume", "quote_volume_unit",
                        "vwap", "trade_count", "taker_buy_base_volume", "taker_buy_base_volume_unit",
                        "taker_buy_quote_volume", "taker_buy_quote_volume_unit",
                    ]
                    write_csv(out / "normalized" / f"{provider}_{asset}_{label}.csv", fields, rows)
                    report = validate_candles(rows, spec["seconds"], start_s, end_s)
                    result_status = "downloaded" if report["validation_passed"] else "validation_error"
                    if not report["validation_passed"]:
                        execution_failed = True
                    manifest["results"].append({
                        "provider": provider, "asset": asset, "interval": label,
                        "market_id": market_id, "endpoint": request_meta["url"].split("?")[0],
                        "request": request_meta,
                        "source_timestamp_unit": "milliseconds" if provider == "binance" else "seconds",
                        "query_parameters": urllib.parse.parse_qs(urllib.parse.urlsplit(request_meta["url"]).query),
                        "raw": raw, "validation": report, "status": result_status,
                    })
                except Exception as exc:
                    execution_failed = True
                    manifest["results"].append({
                        "provider": provider, "asset": asset, "interval": label,
                        "endpoint": BINANCE if provider == "binance" else KRAKEN,
                        "status": "error", "error": str(exc),
                    })
            try:
                counts, response_info, request_meta = fetch_coingecko(
                    asset, ids["coingecko"], start_s, end_s, label
                )
                manifest["results"].append({
                    "provider": "coingecko", "asset": asset, "interval": label,
                    "market_id": ids["coingecko"], "endpoint": request_meta["url"].split("?")[0],
                    "request": request_meta,
                    "query_parameters": urllib.parse.parse_qs(urllib.parse.urlsplit(request_meta["url"]).query),
                    "source_timestamp_unit": "milliseconds", "volume_unit": "USD",
                    "observations_by_metric": counts, "response_sha256": response_info["sha256"],
                    "response_bytes": response_info["bytes"], "status": "counted_in_memory_not_archived",
                })
            except Exception as exc:
                execution_failed = True
                manifest["results"].append({
                    "provider": "coingecko", "asset": asset, "interval": label,
                    "endpoint": COINGECKO.format(coin_id=ids["coingecko"]),
                    "status": "error", "error": str(exc),
                })
    out.mkdir(parents=True, exist_ok=True)
    manifest["execution_status"] = "failed" if execution_failed else "success"
    manifest["execution_exit_code"] = 1 if execution_failed else 0
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps({"manifest": str(out / "manifest.json"),
                      "execution_status": manifest["execution_status"],
                      "results": manifest["results"]},
                     indent=2, ensure_ascii=False))
    if execution_failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
