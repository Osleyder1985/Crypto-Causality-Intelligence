from datetime import timezone
import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts/research/download_binance_btcusdt_intraday.py"
spec = importlib.util.spec_from_file_location("intraday", SCRIPT)
intraday = importlib.util.module_from_spec(spec)
spec.loader.exec_module(intraday)


def test_windows_are_utc_aligned_and_nonempty():
    for _, start, end in intraday.WINDOWS:
        start_ms, end_ms = intraday.to_ms(start), intraday.to_ms(end)
        assert start_ms < end_ms
        assert start_ms % intraday.INTERVAL_MS == 0
        assert end_ms % intraday.INTERVAL_MS == 0


def test_timezone_conversion_preserves_instant():
    assert intraday.to_ms("2026-08-16T16:00:00-05:00") == intraday.to_ms("2026-08-16T21:00:00Z")


def test_candle_validation_accepts_valid_kline():
    row = [0, "100", "102", "99", "101", "10", 59999, "1005", 12, "4", "402", "0"]
    assert intraday.validate(row) == []


def test_candle_validation_rejects_invalid_ohlc():
    row = [0, "103", "102", "99", "101", "10", 59999, "1005", 12, "4", "402", "0"]
    assert "invalid_ohlc" in intraday.validate(row)
