import csv, io, zipfile
from datetime import datetime, timezone
from decimal import Decimal
import pytest
from scripts.research.download_binance_btcusdt_aggtrades import aggregate, checksum_value, parse_bool, parse_zip

def zipped(rows):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,"w",zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("trades.csv","\n".join(",".join(map(str,row)) for row in rows)+"\n")
    return stream.getvalue()

def start_ms():
    return int(datetime(2026,10,6,tzinfo=timezone.utc).timestamp()*1000)

def test_spot_microseconds_and_aggressor_sign():
    start=start_ms()
    payload=zipped([
      [1,"60000","0.1",1,1,start*1000+123000,"True","True"],
      [2,"60001","0.2",2,2,start*1000+456000,"False","True"]])
    rows,_=parse_zip(payload,"spot",start)
    assert rows[0]["timestamp_unit"]=="microseconds"
    assert rows[0]["signed_taker_notional_usdt"]=="-6000.0"
    assert rows[1]["signed_taker_notional_usdt"]=="12000.2"

def test_usdm_milliseconds_and_one_second_aggregation():
    start=start_ms()
    rows,_=parse_zip(zipped([[9,"60000","0.5",9,9,start+999,"true"]]),"usd_m",start)
    series=aggregate(rows,1000)
    assert series[0]["bucket_start_ms"]==start
    assert series[0]["signed_taker_notional_usdt"]=="-30000.0"

def test_invalid_boolean_checksum_and_duplicate_ids_rejected():
    with pytest.raises(ValueError): parse_bool("unknown")
    with pytest.raises(ValueError): checksum_value(b"not a checksum")
    start=start_ms()
    row=[4,"60000","0.1",4,4,start*1000,"True","True"]
    with pytest.raises(ValueError,match="duplicate"): parse_zip(zipped([row,row]),"spot",start)
