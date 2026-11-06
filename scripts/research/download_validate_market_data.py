#!/usr/bin/env python3
"""Descarga reproducible de muestras BTC/ETH para Issue #11.

Solo usa la biblioteca estándar. No convierte USDT a USD ni mezcla series
de candles con observaciones agregadas de CoinGecko.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

BINANCE = "https://data-api.binance.vision/api/v3/klines"
KRAKEN = "https://api.kraken.com/0/public/OHLC"
COINGECKO = "https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart/range"
ASSETS = {
    "BTC": {"binance": "BTCUSDT", "kraken": "XBTUSD", "coingecko": "bitcoin"},
    "ETH": {"binance": "ETHUSDT", "kraken": "ETHUSD", "coingecko": "ethereum"},
}
INTERVALS = {"1h": {"binance": "1h", "kraken": 60, "seconds": 3600},
             "1d": {"binance": "1d", "kraken": 1440, "seconds": 86400}}


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
    invalid = []
    gaps = []
    for i, row in enumerate(rows):
        o, h, low, c, v = (float(row[k]) for k in ("open", "high", "low", "close", "volume"))
        if not (low <= min(o, c) <= max(o, c) <= h and low <= h):
            invalid.append({"timestamp": row["open_time_utc"], "type": "ohlc"})
        if v < 0:
            invalid.append({"timestamp": row["open_time_utc"], "type": "negative_volume"})
        if i and timestamps[i] - timestamps[i - 1] != interval_seconds:
            gaps.append({"from": timestamps[i - 1], "to": timestamps[i],
                         "missing_intervals": (timestamps[i] - timestamps[i - 1]) // interval_seconds - 1})
    expected = (end_s - start_s) // interval_seconds
    in_window = [t for t in timestamps if start_s <= t < end_s]
    outside_window = [t for t in timestamps if not start_s <= t < end_s]
    misaligned = [t for t in in_window if t % interval_seconds != 0]
    zero_volume = sum(float(r["volume"]) == 0 for r in rows)
    return {
        "records_received": len(rows), "records_in_window": len(in_window),
        "records_outside_window": len(outside_window),
        "records_expected_if_continuous": expected,
        "coverage_pct_if_continuous": round(100 * len(set(in_window)) / expected, 4) if expected else None,
        "duplicate_timestamps": duplicates, "strictly_ordered": ordered,
        "misaligned_timestamps": misaligned, "zero_volume_records": zero_volume,
        "ohlc_or_volume_violations": invalid, "gaps": gaps,
        "note": "La cobertura continua es una referencia; huecos por ausencia de operaciones requieren semántica del proveedor."
    }


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
            "volume": k[5], "volume_unit": asset, "quote_volume": k[7],
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
    rows = []
    for k in result[pair_key]:
        ts = int(k[0])
        # Kraken incluye la vela en curso; solo conservar aperturas en la ventana cerrada.
        if start_s <= ts < end_s:
            rows.append({
                "provider": "kraken", "asset": asset, "market_id": pair_key,
                "base_asset": "XBT" if asset == "BTC" else "ETH", "quote_asset": "USD",
                "interval": "1h" if interval == 60 else "1d",
                "open_time_utc": ts, "close_time_utc": ts + (3600 if interval == 60 else 86400) - 1,
                "open": k[1], "high": k[2], "low": k[3], "close": k[4],
                "volume": k[6], "volume_unit": "XBT" if asset == "BTC" else "ETH",
                "vwap": k[5], "trades": k[7],
            })
    raw = save_raw(out, f"kraken_{asset}_{interval}", body)
    return rows, raw, pair_key, request_meta


def fetch_coingecko(asset, coin_id, start_s, end_s, interval, out):
    params = urllib.parse.urlencode({"vs_currency": "usd", "from": start_s, "to": end_s})
    data, body, request_meta = request_json(f"{COINGECKO.format(coin_id=coin_id)}?{params}")
    raw = save_raw(out, f"coingecko_{asset}_{interval}", body)
    series = []
    for metric in ("prices", "market_caps", "total_volumes"):
        for timestamp_ms, value in data.get(metric, []):
            timestamp_s = int(timestamp_ms) // 1000
            # CoinGecko puede incluir la observación exacta del límite final.
            # La ventana experimental es [inicio, fin), igual que en los exchanges.
            if start_s <= timestamp_s < end_s:
                series.append({"metric": metric, "timestamp_utc": timestamp_s,
                               "value": value, "asset": asset, "provider": "coingecko",
                               "coin_id": coin_id, "vs_currency": "usd"})
    # Se conserva el formato largo: precios/volumen/capitalización no son velas OHLC.
    write_csv(out / "normalized" / f"coingecko_{asset}_{interval}.csv",
              ["provider", "asset", "coin_id", "vs_currency", "metric", "timestamp_utc", "value"], series)
    return len(series), raw, request_meta


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
    manifest = {"experiment": "issue-11",
                "windows_utc": {k: {"start_inclusive": v[2], "end_exclusive": v[3]} for k, v in windows.items()},
                "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                "intervals": {}, "results": [], "limitations": [
                    "Binance usa pares USDT; Kraken y CoinGecko usan USD. No comparar precios absolutos sin conversión documentada.",
                    "CoinGecko market_chart/range entrega series agregadas, no velas OHLCV equivalentes.",
                    "Kraken OHLC limita la respuesta a 720 observaciones; verificar conteo y cobertura.",
                    "CoinGecko puede aplicar granularidad automática y límites por plan/rango."
                ]}
    for label, spec in INTERVALS.items():
        start_s, end_s, _, _ = windows[label]
        seconds = spec["seconds"]
        manifest["intervals"][label] = {"seconds": seconds,
            "expected_continuous_records": (end_s - start_s) // seconds}
        for asset, ids in ASSETS.items():
            for provider in ("binance", "kraken"):
                try:
                    if provider == "binance":
                        rows, raw, request_meta = fetch_binance(asset, ids["binance"], spec["binance"], start_s, end_s, out)
                        market_id = ids["binance"]
                    else:
                        rows, raw, market_id, request_meta = fetch_kraken(asset, ids["kraken"], spec["kraken"], start_s, end_s, out)
                    filename = f"{provider}_{asset}_{label}.csv"
                    fields = list(rows[0].keys()) if rows else [
                        "provider", "asset", "market_id", "base_asset", "quote_asset", "interval",
                        "open_time_utc", "close_time_utc", "open", "high", "low", "close", "volume", "volume_unit"]
                    write_csv(out / "normalized" / filename, fields, rows)
                    report = validate_candles(rows, seconds, start_s, end_s)
                    manifest["results"].append({"provider": provider, "asset": asset, "interval": label,
                        "market_id": market_id, "endpoint": request_meta["url"].split("?")[0],
                        "request": request_meta, "source_timestamp_unit": "milliseconds" if provider == "binance" else "seconds",
                        "query_parameters": urllib.parse.parse_qs(urllib.parse.urlsplit(request_meta["url"]).query),
                        "raw": raw, "validation": report, "status": "downloaded"})
                except Exception as exc:
                    manifest["results"].append({"provider": provider, "asset": asset, "interval": label,
                        "endpoint": BINANCE if provider == "binance" else KRAKEN,
                        "status": "error", "error": str(exc)})
            try:
                count, raw, request_meta = fetch_coingecko(asset, ids["coingecko"], start_s, end_s, label, out)
                manifest["results"].append({"provider": "coingecko", "asset": asset, "interval": label,
                    "market_id": ids["coingecko"], "endpoint": request_meta["url"].split("?")[0],
                    "request": request_meta,
                    "query_parameters": urllib.parse.parse_qs(urllib.parse.urlsplit(request_meta["url"]).query),
                    "source_timestamp_unit": "milliseconds", "volume_unit": "USD",
                    "observations_long_format": count, "raw": raw, "status": "downloaded_non_ohlcv"})
            except Exception as exc:
                manifest["results"].append({"provider": "coingecko", "asset": asset, "interval": label,
                    "endpoint": COINGECKO.format(coin_id=ids["coingecko"]),
                    "status": "error", "error": str(exc)})
    out.mkdir(parents=True, exist_ok=True)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"manifest": str(out / "manifest.json"), "results": manifest["results"]},
                     indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
