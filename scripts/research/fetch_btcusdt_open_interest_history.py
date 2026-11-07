"""Download and audit historical Binance USD-M BTCUSDT Open Interest metrics."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import zipfile
from bisect import bisect_right
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from typing import Any

from scripts.research.analyze_btcusdt_multifactor import load_cohorts

ARCHIVE_BASE = "https://data.binance.vision/data/futures/um/daily/metrics"
HOUR_MS = 3_600_000
MINUTE_MS = 60_000
SNAPSHOT_LABEL_CHANGE = date(2026, 6, 25)
MAX_SNAPSHOT_AGE_MS = 10 * MINUTE_MS
REQUIRED_COLUMNS = {
    "create_time", "symbol", "sum_open_interest", "sum_open_interest_value"
}


def _finite(value: Any, field: str, allow_zero: bool = True) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid {field}") from exc
    if not math.isfinite(result) or result < 0 or (not allow_zero and result == 0):
        raise ValueError(f"invalid {field}")
    return result


def effective_snapshot_time_ms(label_ms: int, archive_day: date) -> int:
    """Normalize Binance UM metrics labels to the effective snapshot timestamp."""
    # Conservative availability time: delay every snapshot by one full 5-minute
    # bucket. Before the reported transition this is intentionally later than
    # the observed snapshot label; after it, it matches the reported T+5 rule.
    # This avoids look-ahead even if the historical convention is ambiguous.
    return int(label_ms) + 5 * MINUTE_MS


def _download(url: str, timeout: float = 30.0) -> bytes:
    request = Request(url, headers={"User-Agent": "Crypto-Causality-Intelligence/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.read()
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"Binance Vision download failed: {url}: {exc}") from exc


def _parse_metrics_archive(symbol: str, day: date, timeout: float = 30.0) -> tuple[list[dict[str, Any]], str]:
    filename = f"{symbol}-metrics-{day.isoformat()}.zip"
    url = f"{ARCHIVE_BASE}/{symbol}/{filename}"
    archive_bytes = _download(url, timeout)
    checksum_text = _download(url + ".CHECKSUM", timeout).decode("utf-8").strip()
    expected = checksum_text.split()[0] if checksum_text else ""
    actual = hashlib.sha256(archive_bytes).hexdigest()
    if len(expected) != 64 or actual.lower() != expected.lower():
        raise ValueError(f"SHA-256 checksum mismatch for {filename}")
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(members) != 1:
            raise ValueError(f"unexpected CSV member count in {filename}")
        with archive.open(members[0]) as raw:
            reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8", newline=""))
            if not reader.fieldnames or not REQUIRED_COLUMNS.issubset(reader.fieldnames):
                raise ValueError(f"unexpected metrics schema in {filename}")
            rows = []
            for line, row in enumerate(reader, 2):
                if row.get("symbol") != symbol:
                    raise ValueError(f"{filename}:{line}: unexpected symbol")
                try:
                    labelled = datetime.strptime(row["create_time"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"{filename}:{line}: invalid create_time") from exc
                label_ms = int(labelled.timestamp() * 1000)
                # Binance's UM metrics labels changed on 2026-06-25:
                # before that date create_time is the snapshot instant;
                # from that date it labels the start of a 5-minute bucket,
                # and the snapshot is effective five minutes later.
                effective_ms = effective_snapshot_time_ms(label_ms, day)
                oi = _finite(row["sum_open_interest"], "sum_open_interest")
                oi_value = _finite(row["sum_open_interest_value"], "sum_open_interest_value")
                rows.append({
                    "symbol": symbol,
                    "create_time_label_ms": label_ms,
                    "snapshot_time_ms": effective_ms,
                    "sum_open_interest": oi,
                    "sum_open_interest_value": oi_value,
                    "source_file": filename,
                    "timestamp_convention": (
                        "bucket_start_snapshot_plus_5m"
                        if day >= SNAPSHOT_LABEL_CHANGE else "conservative_label_plus_5m_semantics_unverified"
                    ),
                })
    rows.sort(key=lambda item: item["snapshot_time_ms"])
    return rows, actual


def collect_for_cohorts(cohorts: dict[str, list[dict[str, Any]]],
                        timeout: float = 30.0) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    required_days: set[date] = set()
    windows = {}
    for name, rows in cohorts.items():
        if not rows:
            continue
        start_ms = rows[0]["_ts"]
        end_ms = rows[-1]["_ts"] + HOUR_MS - 1
        start_dt = datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc)
        end_dt = datetime.fromtimestamp(end_ms / 1000, tz=timezone.utc)
        start, end = start_dt.date(), end_dt.date()
        windows[name] = {
            "start_date_utc": start.isoformat(),
            "end_date_utc": end.isoformat(),
            "start_time_utc": start_dt.isoformat(),
            "end_time_utc": end_dt.isoformat(),
        }
        current = start
        while current <= end:
            required_days.add(current)
            current += timedelta(days=1)

    all_rows: list[dict[str, Any]] = []
    checksums = {}
    missing_days = []
    for day in sorted(required_days):
        try:
            rows, digest = _parse_metrics_archive("BTCUSDT", day, timeout)
        except RuntimeError as exc:
            # A 404 means the exchange did not publish the file for this date;
            # transport failures and other HTTP statuses remain hard failures.
            if "HTTP Error 404" in str(exc):
                missing_days.append(day.isoformat())
                continue
            raise
        all_rows.extend(rows)
        checksums[day.isoformat()] = digest

    # Same effective snapshot can be repeated at a file boundary. Preserve the
    # row from the later daily file only when the normalized timestamps match.
    by_timestamp: dict[int, dict[str, Any]] = {}
    duplicate_timestamps = 0
    conflicting_duplicates = 0
    for row in sorted(all_rows, key=lambda item: (item["snapshot_time_ms"], item["source_file"])):
        timestamp = row["snapshot_time_ms"]
        previous = by_timestamp.get(timestamp)
        if previous is not None:
            duplicate_timestamps += 1
            if (previous["sum_open_interest"], previous["sum_open_interest_value"]) != (
                row["sum_open_interest"], row["sum_open_interest_value"]
            ):
                conflicting_duplicates += 1
        by_timestamp[timestamp] = row
    records = [by_timestamp[key] for key in sorted(by_timestamp)]
    file_label_ranges = {}
    for day_text, digest in checksums.items():
        filename = f"BTCUSDT-metrics-{day_text}.zip"
        file_rows = [row for row in all_rows if row["source_file"] == filename]
        if file_rows:
            labels = sorted(row["create_time_label_ms"] for row in file_rows)
            file_label_ranges[day_text] = {
                "rows": len(labels),
                "first_create_time_label_utc": datetime.fromtimestamp(labels[0] / 1000, tz=timezone.utc).isoformat(),
                "last_create_time_label_utc": datetime.fromtimestamp(labels[-1] / 1000, tz=timezone.utc).isoformat(),
            }
    report = {
        "symbol": "BTCUSDT",
        "market_type": "USD_M_FUTURES",
        "source": "Binance Vision daily metrics",
        "windows": windows,
        "requested_daily_files": len(required_days),
        "downloaded_daily_files": len(checksums),
        "missing_daily_files": missing_days,
        "sha256_verified_files": len(checksums),
        "unique_snapshots": len(records),
        "duplicate_effective_timestamps": duplicate_timestamps,
        "conflicting_duplicate_effective_timestamps": conflicting_duplicates,
        "timestamp_convention_change_utc": SNAPSHOT_LABEL_CHANGE.isoformat(),
        "timestamp_semantics_fully_verified": False,
        "timestamp_convention_note": (
            "Community issue #491 reports a change at 2026-06-25 00:00 UTC. However, the "
            "downloaded 2026-06-24 BTCUSDT file currently labels 00:00-23:55, not the "
            "reported 00:05-next-day 00:00 range. To prevent look-ahead, all labels are "
            "conservatively delayed by 5 minutes. Raw labels are retained; exact semantics "
            "remain unverified pending publisher clarification."
        ),
        "file_checksums_sha256": checksums,
        "archive_file_label_ranges": file_label_ranges,
        "cohorts": {},
    }
    return records, report


def audit_and_align(cohorts: dict[str, list[dict[str, Any]]],
                    records: list[dict[str, Any]], report: dict[str, Any]) -> list[dict[str, Any]]:
    times = [row["snapshot_time_ms"] for row in records]
    aligned = []
    for name, spot_rows in sorted(cohorts.items()):
        fresh = 0
        missing = 0
        stale = 0
        for spot in spot_rows:
            close_ms = spot["_ts"] + HOUR_MS - 1
            position = bisect_right(times, close_ms) - 1
            result = dict(spot)
            snapshot = records[position] if position >= 0 else None
            age_ms = close_ms - snapshot["snapshot_time_ms"] if snapshot else None
            if snapshot is None or age_ms > MAX_SNAPSHOT_AGE_MS:
                result.update({
                    "open_interest_base_asof": None,
                    "open_interest_quote_asof": None,
                    "open_interest_age_minutes": None if snapshot is None else age_ms / MINUTE_MS,
                    "open_interest_snapshot_time_ms": None if snapshot is None else snapshot["snapshot_time_ms"],
                    "open_interest_change_1h_pct": None,
                    "open_interest_change_4h_pct": None,
                    "open_interest_change_24h_pct": None,
                })
                if snapshot is None:
                    missing += 1
                else:
                    stale += 1
            else:
                fresh += 1
                result.update({
                    "open_interest_base_asof": snapshot["sum_open_interest"],
                    "open_interest_quote_asof": snapshot["sum_open_interest_value"],
                    "open_interest_age_minutes": age_ms / MINUTE_MS,
                    "open_interest_snapshot_time_ms": snapshot["snapshot_time_ms"],
                })
                for hours in (1, 4, 24):
                    prior_pos = bisect_right(times, snapshot["snapshot_time_ms"] - hours * HOUR_MS) - 1
                    prior = records[prior_pos] if prior_pos >= 0 else None
                    key = f"open_interest_change_{hours}h_pct"
                    target_prior_ms = snapshot["snapshot_time_ms"] - hours * HOUR_MS
                    prior_is_fresh = (
                        prior is not None
                        and target_prior_ms - MAX_SNAPSHOT_AGE_MS <= prior["snapshot_time_ms"] <= target_prior_ms
                    )
                    if prior_is_fresh and prior["sum_open_interest"] > 0:
                        result[key] = (
                            snapshot["sum_open_interest"] / prior["sum_open_interest"] - 1
                        ) * 100
                    else:
                        result[key] = None
            aligned.append(result)
        window_start_ms = spot_rows[0]["_ts"] if spot_rows else 0
        window_end_ms = spot_rows[-1]["_ts"] + HOUR_MS - 1 if spot_rows else -1
        # Audit every raw 5-minute observation, not only the hourly as-of selections.
        cohort_snapshots = [
            row for row in records
            if window_start_ms <= row["snapshot_time_ms"] <= window_end_ms
        ]
        unique_times = sorted({r["snapshot_time_ms"] for r in cohort_snapshots})
        intervals = [(b - a) / MINUTE_MS for a, b in zip(unique_times, unique_times[1:])]
        anomalous_gaps = [
            {
                "from_snapshot_utc": datetime.fromtimestamp(a / 1000, tz=timezone.utc).isoformat(),
                "to_snapshot_utc": datetime.fromtimestamp(b / 1000, tz=timezone.utc).isoformat(),
                "gap_minutes": (b - a) / MINUTE_MS,
            }
            for a, b in zip(unique_times, unique_times[1:])
            if b - a > 5 * MINUTE_MS
        ]
        report["cohorts"][name] = {
            "spot_candles": len(spot_rows),
            "fresh_asof_candles": fresh,
            "fresh_asof_pct": 100 * fresh / len(spot_rows) if spot_rows else None,
            "missing_before_first_snapshot": missing,
            "stale_snapshot_candles": stale,
            "raw_unique_5m_snapshots_in_window": len(unique_times),
            "expected_snapshot_interval_minutes": 5,
            "median_snapshot_interval_minutes": median(intervals) if intervals else None,
            "max_snapshot_gap_minutes": max(intervals) if intervals else None,
            "gaps_over_5_minutes": anomalous_gaps,
            "gap_count_over_5_minutes": len(anomalous_gaps),
            "zero_open_interest_snapshots": sum(r["sum_open_interest"] == 0 for r in cohort_snapshots),
            "zero_open_interest_value_snapshots": sum(r["sum_open_interest_value"] == 0 for r in cohort_snapshots),
        }
    aligned.sort(key=lambda row: (row.get("cohort_window", ""), row["_ts"]))
    report["aligned_spot_candles"] = len(aligned)
    return aligned


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spot-input", required=True)
    parser.add_argument("--open-interest-output", required=True)
    parser.add_argument("--coverage-report", required=True)
    parser.add_argument("--aligned-output", required=True)
    args = parser.parse_args()
    cohorts = load_cohorts(args.spot_input)
    records, report = collect_for_cohorts(cohorts)
    aligned = audit_and_align(cohorts, records, report)
    for path in (args.open_interest_output, args.coverage_report, args.aligned_output):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(args.open_interest_output).write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in records), encoding="utf-8"
    )
    Path(args.coverage_report).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    Path(args.aligned_output).write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in aligned), encoding="utf-8"
    )
    print(json.dumps({
        "unique_snapshots": len(records),
        "cohorts": len(report["cohorts"]),
        "aligned_spot_candles": len(aligned),
        "missing_daily_files": len(report["missing_daily_files"]),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
