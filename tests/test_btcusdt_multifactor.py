import json
import tempfile
import unittest
from pathlib import Path

from scripts.research.analyze_btcusdt_multifactor import analyze_cohorts, load_cohorts


def row(ts, close, open_="100", high="102", low="99", volume="1000", trades="20", buy="600"):
    return {"provider":"binance","market_type":"SPOT","symbol":"BTCUSDT","interval":"1h",
            "cohort_window":"test","open_time_ms":ts,"open":open_,"high":high,"low":low,
            "close":close,"quote_volume":volume,"trade_count":trades,"taker_buy_quote_volume":buy}


class MultifactorTests(unittest.TestCase):
    def test_forward_horizons_are_cohort_local(self):
        cohorts = {"a":[{"_ts":i*3600000,"_open":100.0,"_high":102.0,"_low":99.0,"_close":100.0+i,
                         "_quote_volume":1000.0,"_trade_count":20.0,"_taker_buy_quote":600.0} for i in range(4)]}
        report=analyze_cohorts(cohorts)
        self.assertEqual(report["cohorts"]["a"]["forward_return_associations"]["1"]["log_quote_volume"]["observations"],3)
        self.assertEqual(report["cohorts"]["a"]["forward_return_associations"]["24"]["log_quote_volume"]["observations"],0)
        self.assertFalse(report["causal_claim"])

    def test_loader_rejects_invalid_ohlc(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"data.jsonl"
            p.write_text(json.dumps(row(0,"98",high="97")),encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"OHLC relationship"): load_cohorts(p)

    def test_loader_rejects_taker_volume_above_total(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"data.jsonl"
            p.write_text(json.dumps(row(0,"100",buy="1001")),encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"outside total"): load_cohorts(p)

    def test_loader_rejects_hourly_gap(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"data.jsonl"
            p.write_text(json.dumps(row(0,"100")) + chr(10) + json.dumps(row(7200000,"101")),encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"non-contiguous"): load_cohorts(p)


if __name__=="__main__": unittest.main()
