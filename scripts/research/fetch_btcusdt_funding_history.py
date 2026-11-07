"""Download and audit historical Binance USD-M BTCUSDT funding settlements.

Funding is a futures-market covariate. This tool never writes market data into the
repository: outputs are local JSONL/JSON paths supplied by the operator.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from bisect import bisect_right
from statistics import median
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from scripts.research.analyze_btcusdt_multifactor import load_cohorts

API_URL = "https://fapi.binance.com/fapi/v1/fundingRate"
ARCHIVE_BASE_URL = "https://data.binance.vision/data/futures/um/monthly/fundingRate"
_ARCHIVE_CACHE: dict[str, list[dict[str, Any]]] = {}
MAX_LIMIT = 1000
HOUR_MS = 3_600_000


def _finite_number(value: Any, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid {field}") from exc
    if not math.isfinite(number):
        raise ValueError(f"non-finite {field}")
    return number


def _archive_month(symbol: str, year: int, month: int, timeout: float = 30.0) -> list[dict[str, Any]]:
    """Read Binance Vision's official monthly USD-M fundingRate archive."""
    filename = f"{symbol}-fundingRate-{year:04d}-{month:02d}.zip"
    base = f"{ARCHIVE_BASE_URL}/{symbol}/{filename}"
    if filename in _ARCHIVE_CACHE:
        return _ARCHIVE_CACHE[filename]
    try:
        with urlopen(base, timeout=timeout) as response:
            archive_bytes = response.read()
        with urlopen(base + ".CHECKSUM", timeout=timeout) as response:
            checksum_text = response.read().decode("utf-8").strip()
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"Binance Vision funding archive unavailable ({filename}): {exc}") from exc
    expected = checksum_text.split()[0] if checksum_text else ""
    actual = hashlib.sha256(archive_bytes).hexdigest()
    if len(expected) != 64 or actual.lower() != expected.lower():
        raise ValueError(f"Binance Vision checksum mismatch for {filename}")
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as zipped:
        csv_names = [name for name in zipped.namelist() if name.lower().endswith(".csv")]
        if len(csv_names) != 1:
            raise ValueError(f"unexpected CSV members in {filename}")
        with zipped.open(csv_names[0]) as raw:
            reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8", newline=""))
            required = {"calc_time", "funding_interval_hours", "last_funding_rate"}
            if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
                raise ValueError(f"unexpected funding archive schema in {filename}")
            rows = []
            for row in reader:
                timestamp = int(row["calc_time"])
                rate = _finite_number(row["last_funding_rate"], "last_funding_rate")
                rows.append({
                    "symbol": symbol,
                    "fundingTime": timestamp,
                    "fundingRate": str(rate),
                    "markPrice": "",
                    "rateType": None,
                    "_source_endpoint": "Binance Vision monthly fundingRate archive",
                    "_funding_interval_hours": int(row["funding_interval_hours"]),
                })
    rows.sort(key=lambda item: int(item["fundingTime"]))
    _ARCHIVE_CACHE[filename] = rows
    return rows


def _request_archive_range(params: dict[str, Any], timeout: float = 30.0) -> list[dict[str, Any]]:
    symbol = str(params["symbol"])
    start_ms, end_ms = int(params["startTime"]), int(params["endTime"])
    first = datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc)
    last = datetime.fromtimestamp(end_ms / 1000, tz=timezone.utc)
    year, month = first.year, first.month
    records = []
    while (year, month) <= (last.year, last.month):
        records.extend(
            row for row in _archive_month(symbol, year, month, timeout)
            if start_ms <= int(row["fundingTime"]) <= end_ms
        )
        if month == 12:
            year, month = year + 1, 1
        else:
            month += 1
    return sorted(records, key=lambda item: int(item["fundingTime"]))


def _request_page(params: dict[str, Any], timeout: float = 20.0) -> list[dict[str, Any]]:
    url = API_URL + "?" + urlencode(params)
    request = Request(url, headers={"User-Agent": "Crypto-Causality-Intelligence/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 451:
            return _request_archive_range(params, timeout=timeout)
        raise RuntimeError(f"Binance funding API request failed: {exc}") from exc
    except (URLError, TimeoutError) as exc:
        raise RuntimeError(f"Binance funding API request failed: {exc}") from exc
    if not isinstance(payload, list):
        raise ValueError("Binance funding API returned a non-list response")
    return payload


def fetch_funding_history(
    symbol: str,
    start_time_ms: int,
    end_time_ms: int,
    *,
    page_fetcher: Callable[[dict[str, Any]], list[dict[str, Any]]] = _request_page,
    limit: int = MAX_LIMIT,
) -> list[dict[str, Any]]:
    """Fetch the inclusive interval, paginating without timestamp overlap."""
    if not symbol or start_time_ms < 0 or end_time_ms < start_time_ms:
        raise ValueError("invalid symbol or time range")
    if not 1 <= limit <= MAX_LIMIT:
        raise ValueError("limit must be between 1 and 1000")

    cursor = start_time_ms
    records: list[dict[str, Any]] = []
    seen: set[int] = set()
    while cursor <= end_time_ms:
        page = page_fetcher({
            "symbol": symbol,
            "startTime": cursor,
            "endTime": end_time_ms,
            "limit": limit,
        })
        if not page:
            break
        page_times = []
        for raw in page:
            if raw.get("symbol") not in (None, symbol):
                raise ValueError("funding response contains an unexpected symbol")
            try:
                timestamp = int(raw["fundingTime"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("funding response contains invalid fundingTime") from exc
            if timestamp < start_time_ms or timestamp > end_time_ms:
                raise ValueError("funding response contains a timestamp outside requested bounds")
            _finite_number(raw.get("fundingRate"), "fundingRate")
            if raw.get("markPrice") not in (None, ""):
                _finite_number(raw["markPrice"], "markPrice")
            page_times.append(timestamp)
            if timestamp not in seen:
                records.append({
                    "provider": "binance",
                    "market_type": "USD_M_FUTURES",
                    "symbol": symbol,
                    "funding_time_ms": timestamp,
                    "funding_rate": float(raw["fundingRate"]),
                    "mark_price": (
                        float(raw["markPrice"]) if raw.get("markPrice") not in (None, "") else None
                    ),
                    "rate_type": raw.get("rateType"),
                    "source_endpoint": raw.get("_source_endpoint", "/fapi/v1/fundingRate"),
                    "funding_interval_hours": raw.get("_funding_interval_hours"),
                })
                seen.add(timestamp)
        if page_times != sorted(page_times):
            raise ValueError("funding API page is not in ascending timestamp order")
        next_cursor = max(page_times) + 1
        if next_cursor <= cursor:
            raise ValueError("funding API pagination did not advance")
        if len(page) < limit:
            break
        cursor = next_cursor
    return sorted(records, key=lambda item: item["funding_time_ms"])


def _coverage_summary(rows: list[dict[str, Any]], start_ms: int, end_ms: int) -> dict:
    timestamps = [row["funding_time_ms"] for row in rows]
    deltas = [b - a for a, b in zip(timestamps, timestamps[1:])]
    typical = median(deltas) if deltas else None
    gaps = [
        {"from_ms": a, "to_ms": b, "gap_hours": (b - a) / HOUR_MS}
        for a, b in zip(timestamps, timestamps[1:])
        if typical is not None and b - a > 1.5 * typical
    ]
    return {
        "requested_start_time_ms": start_ms,
        "requested_end_time_ms": end_ms,
        "first_funding_time_ms": timestamps[0] if timestamps else None,
        "last_funding_time_ms": timestamps[-1] if timestamps else None,
        "leading_partial_interval_hours": (
            (timestamps[0] - start_ms) / HOUR_MS if timestamps else None
        ),
        "trailing_partial_interval_hours": (
            (end_ms - timestamps[-1]) / HOUR_MS if timestamps else None
        ),
        "settlement_count": len(timestamps),
        "median_settlement_interval_hours": typical / HOUR_MS if typical is not None else None,
        "maximum_settlement_interval_hours": max(deltas) / HOUR_MS if deltas else None,
        "internal_gap_count": len(gaps),
        "gaps_above_1_5x_median": gaps,
        "status": (
            "no_records_returned" if not timestamps
            else "records_found_internal_gaps_detected" if gaps
            else "records_found_no_internal_gaps"
        ),
    }


def collect_for_spot_cohorts(
    spot_input: str | Path,
    *,
    page_fetcher: Callable[[dict[str, Any]], list[dict[str, Any]]] = _request_page,
) -> tuple[list[dict[str, Any]], dict]:
    cohorts = load_cohorts(spot_input)
    all_funding: dict[int, dict[str, Any]] = {}
    coverage = {}
    for name, rows in sorted(cohorts.items()):
        start_ms = min(row["_ts"] for row in rows)
        end_ms = max(row["_ts"] for row in rows) + HOUR_MS - 1
        funding = fetch_funding_history(
            "BTCUSDT", start_ms, end_ms, page_fetcher=page_fetcher
        )
        for item in funding:
            all_funding[item["funding_time_ms"]] = item
        coverage[name] = _coverage_summary(funding, start_ms, end_ms)
        time.sleep(0.05)
    ordered = sorted(all_funding.values(), key=lambda item: item["funding_time_ms"])
    asof_alignment = {}
    for name, rows in sorted(cohorts.items()):
        aligned = attach_funding_asof(rows, ordered)
        available = [
            row["funding_latest_age_hours"] for row in aligned
            if row["funding_latest_rate_asof"] is not None
        ]
        asof_alignment[name] = {
            "spot_candles": len(aligned),
            "candles_with_fresh_funding": len(available),
            "fresh_funding_availability_pct": (
                100 * len(available) / len(aligned) if aligned else None
            ),
            "maximum_funding_age_hours": max(available) if available else None,
        }
    report = {
        "status": "funding_history_coverage_audit",
        "provider": "binance",
        "market_type": "USD_M_FUTURES",
        "symbol": "BTCUSDT",
        "endpoint": API_URL,
        "archive_source": "https://data.binance.vision/data/futures/um/monthly/fundingRate/BTCUSDT/",
        "source_is_spot": False,
        "retrieval_policy": "REST first; verified Binance Vision monthly archive fallback when REST is geographically unavailable",
        "cohort_count": len(coverage),
        "cohorts": coverage,
        "asof_alignment": asof_alignment,
        "funding_records_total_deduplicated": len(ordered),
        "limitations": [
            "coverage is established only for the queried cohort windows",
            "observed settlement gaps are reported, not imputed",
            "funding is a futures-market covariate, not a Spot-native field",
            "a historical funding rate is admissible only at or after funding_time_ms",
        ],
    }
    return ordered, report



def attach_funding_asof(
    spot_rows: list[dict[str, Any]],
    funding_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Attach only settlements known by each Spot candle's close timestamp.

    Missing prior settlements remain null; they are never replaced by zero.
    """
    ordered = sorted(funding_rows, key=lambda item: int(item["funding_time_ms"]))
    times = [int(item["funding_time_ms"]) for item in ordered]
    attached = []
    for row in spot_rows:
        origin_time = int(row["_ts"]) + HOUR_MS - 1
        position = bisect_right(times, origin_time)
        prior = ordered[max(0, position - 3):position]
        latest = prior[-1] if prior else None
        # Do not carry a settlement across a long gap between disjoint cohorts.
        # Binance's usual interval is 8h; archive rows provide the effective
        # interval where available, while REST-only rows use the conservative default.
        if latest is not None:
            interval_hours = float(latest.get("funding_interval_hours") or 8)
            max_age_ms = (interval_hours + 1 / 60) * HOUR_MS
            if origin_time - int(latest["funding_time_ms"]) > max_age_ms:
                prior = []
                latest = None
        enriched = dict(row)
        enriched["funding_latest_rate_asof"] = (
            float(latest["funding_rate"]) if latest is not None else None
        )
        enriched["funding_latest_age_hours"] = (
            (origin_time - int(latest["funding_time_ms"])) / HOUR_MS
            if latest is not None else None
        )
        enriched["funding_mean_last_3_asof"] = (
            sum(float(item["funding_rate"]) for item in prior) / len(prior)
            if prior else None
        )
        enriched["funding_settlements_available_asof"] = len(prior)
        attached.append(enriched)
    return attached


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spot-input", required=True, help="existing Spot cohort JSONL; not copied")
    parser.add_argument("--funding-output", required=True, help="local funding JSONL output path")
    parser.add_argument("--coverage-report", required=True, help="local JSON coverage report path")
    parser.add_argument("--aligned-output", help="optional local Spot + as-of Funding JSONL path")
    args = parser.parse_args()

    records, report = collect_for_spot_cohorts(args.spot_input)
    funding_path = Path(args.funding_output)
    report_path = Path(args.coverage_report)
    funding_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    funding_path.write_text(
        "".join(json.dumps(item, sort_keys=True) + "\n" for item in records),
        encoding="utf-8",
    )
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
