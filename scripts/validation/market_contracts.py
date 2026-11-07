"""Provider-to-canonical market contract adapters.

These functions preserve provider semantics and Decimal precision. They do not
infer asset equivalence, finality, or exchange trading rules that the provider
did not explicitly publish.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable


def _decimal(value: Any, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"invalid decimal for {field}") from exc
    if not result.is_finite():
        raise ValueError(f"non-finite decimal for {field}")
    return result


def _aware_utc(value: Any, field: str) -> datetime:
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, str):
        text = value[:-1] + "+00:00" if value.endswith("Z") else value
        try:
            result = datetime.fromisoformat(text)
        except ValueError as exc:
            raise ValueError(f"invalid timestamp for {field}") from exc
    else:
        raise ValueError(f"invalid timestamp for {field}")
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return result.astimezone(timezone.utc)


def _epoch_datetime(value: Any, unit: str, field: str) -> datetime:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer epoch timestamp")
    if unit == "ms":
        micros = value * 1000
    elif unit == "us":
        micros = value
    else:
        raise ValueError("timestamp_unit must be 'ms' or 'us'")
    return datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=micros)


def parse_binance_kline(row: Iterable[Any], timestamp_unit: str = "ms") -> dict:
    values = list(row)
    if len(values) != 12:
        raise ValueError("Binance kline must contain exactly 12 fields")
    if timestamp_unit not in {"ms", "us"}:
        raise ValueError("timestamp_unit must be 'ms' or 'us'")
    open_time = _epoch_datetime(values[0], timestamp_unit, "open_time")
    close_time = _epoch_datetime(values[6], timestamp_unit, "close_time")
    result = {
        "open_time": open_time,
        "open": _decimal(values[1], "open"),
        "high": _decimal(values[2], "high"),
        "low": _decimal(values[3], "low"),
        "close": _decimal(values[4], "close"),
        "volume_base": _decimal(values[5], "volume_base"),
        "close_time": close_time,
        "close_time_exclusive": close_time + (timedelta(milliseconds=1) if timestamp_unit == "ms" else timedelta(microseconds=1)),
        "volume_quote": _decimal(values[7], "volume_quote"),
        "trade_count": _nonnegative_int(values[8], "trade_count"),
        "taker_buy_base_volume": _decimal(values[9], "taker_buy_base_volume"),
        "taker_buy_quote_volume": _decimal(values[10], "taker_buy_quote_volume"),
        "source_ignore_field": str(values[11]),
        "is_final": None,
    }
    if not (result["low"] <= result["open"] <= result["high"] and
            result["low"] <= result["close"] <= result["high"]):
        raise ValueError("OHLC values are inconsistent")
    if min(result["volume_base"], result["volume_quote"],
           result["taker_buy_base_volume"], result["taker_buy_quote_volume"]) < 0:
        raise ValueError("volumes must be non-negative")
    if result["taker_buy_base_volume"] > result["volume_base"]:
        raise ValueError("taker buy base volume exceeds total base volume")
    return result


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a non-negative integer")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a non-negative integer") from exc
    if str(result) != str(value) and not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    if result < 0:
        raise ValueError(f"{field} must be non-negative")
    return result


def parse_kraken_ohlc_row(row: Iterable[Any], interval_minutes: int,
                          is_last_row: bool) -> dict:
    values = list(row)
    if len(values) != 8:
        raise ValueError("Kraken OHLC row must contain exactly 8 fields")
    if isinstance(interval_minutes, bool) or not isinstance(interval_minutes, int) or interval_minutes <= 0:
        raise ValueError("interval_minutes must be a positive integer")
    if not isinstance(is_last_row, bool):
        raise ValueError("is_last_row must be boolean")
    try:
        seconds = int(values[0])
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid Kraken OHLC timestamp") from exc
    open_time = datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=seconds)
    result = {
        "open_time": open_time,
        "open": _decimal(values[1], "open"),
        "high": _decimal(values[2], "high"),
        "low": _decimal(values[3], "low"),
        "close": _decimal(values[4], "close"),
        "vwap": _decimal(values[5], "vwap"),
        "volume_base": _decimal(values[6], "volume_base"),
        "trade_count": _nonnegative_int(values[7], "trade_count"),
        "volume_quote": None,
        "close_time_exclusive": open_time + timedelta(minutes=interval_minutes),
        "is_final": not is_last_row,
    }
    if not (result["low"] <= result["open"] <= result["high"] and
            result["low"] <= result["close"] <= result["high"]):
        raise ValueError("OHLC values are inconsistent")
    if result["volume_base"] < 0:
        raise ValueError("volume must be non-negative")
    return result


def _filter_decimal(filter_map: dict, key: str, filter_name: str):
    value = filter_map.get(key)
    return None if value is None else _decimal(value, f"{filter_name}.{key}")


def map_binance_instrument_metadata(symbol: dict) -> dict:
    if not isinstance(symbol, dict):
        raise ValueError("Binance symbol metadata must be an object")
    source_id = symbol.get("symbol")
    if not isinstance(source_id, str) or not source_id:
        raise ValueError("Binance symbol metadata requires symbol")
    filters = symbol.get("filters", [])
    if not isinstance(filters, list):
        raise ValueError("filters must be a list")
    by_type = {}
    trading_rules = []
    unknown_types = []
    known = {"PRICE_FILTER", "LOT_SIZE", "MARKET_LOT_SIZE", "MIN_NOTIONAL", "NOTIONAL"}
    for item in filters:
        if not isinstance(item, dict) or not isinstance(item.get("filterType"), str):
            raise ValueError("each Binance filter requires filterType")
        kind = item["filterType"]
        if kind in by_type:
            raise ValueError(f"duplicate Binance filter: {kind}")
        by_type[kind] = item
        trading_rules.append({"rule_type": kind, "parameters": dict(item)})
        if kind not in known:
            unknown_types.append(kind)
    price = by_type.get("PRICE_FILTER", {})
    lot = by_type.get("LOT_SIZE", {})
    market_lot = by_type.get("MARKET_LOT_SIZE", {})
    notional = by_type.get("NOTIONAL", by_type.get("MIN_NOTIONAL", {}))
    min_notional_key = "minNotional" if "minNotional" in notional else None
    max_notional_key = "maxNotional" if "maxNotional" in notional else None
    extensions = {
        key: value for key, value in symbol.items()
        if key not in {"symbol", "status", "baseAsset", "quoteAsset", "filters"}
    }
    if "baseAssetPrecision" in symbol:
        extensions["baseAssetPrecision"] = symbol["baseAssetPrecision"]
    if "quoteAssetPrecision" in symbol:
        extensions["quoteAssetPrecision"] = symbol["quoteAssetPrecision"]
    if unknown_types:
        extensions["unknown_filter_types"] = unknown_types
    return {
        "source_instrument_id": source_id,
        "status": symbol.get("status"),
        "base_asset": symbol.get("baseAsset"),
        "quote_asset": symbol.get("quoteAsset"),
        "price_tick": _filter_decimal(price, "tickSize", "PRICE_FILTER"),
        "min_price": _filter_decimal(price, "minPrice", "PRICE_FILTER"),
        "max_price": _filter_decimal(price, "maxPrice", "PRICE_FILTER"),
        "quantity_step": _filter_decimal(lot, "stepSize", "LOT_SIZE"),
        "min_quantity": _filter_decimal(lot, "minQty", "LOT_SIZE"),
        "max_quantity": _filter_decimal(lot, "maxQty", "LOT_SIZE"),
        "market_quantity_step": _filter_decimal(market_lot, "stepSize", "MARKET_LOT_SIZE"),
        "market_min_quantity": _filter_decimal(market_lot, "minQty", "MARKET_LOT_SIZE"),
        "market_max_quantity": _filter_decimal(market_lot, "maxQty", "MARKET_LOT_SIZE"),
        "min_notional": _filter_decimal(notional, "minNotional", "NOTIONAL") if min_notional_key else None,
        "max_notional": _filter_decimal(notional, "maxNotional", "NOTIONAL") if max_notional_key else None,
        "trading_rules": trading_rules,
        "provider_extensions": extensions,
    }


def map_kraken_instrument_metadata(source_instrument_id: str, pair: dict) -> dict:
    if not isinstance(source_instrument_id, str) or not source_instrument_id:
        raise ValueError("Kraken source instrument id is required")
    if not isinstance(pair, dict):
        raise ValueError("Kraken pair metadata must be an object")
    known = {"altname", "wsname", "base", "quote", "status", "tick_size",
             "pair_decimals", "lot_decimals", "ordermin", "costmin",
             "lot_multiplier"}
    extensions = {k: v for k, v in pair.items() if k not in known}
    rules = []
    for key in ("tick_size", "pair_decimals", "lot_decimals", "ordermin",
                "costmin", "lot_multiplier"):
        if key in pair:
            rules.append({"rule_type": key, "parameters": {key: pair[key]}})
    return {
        "source_instrument_id": source_instrument_id,
        "native_aliases": {k: pair[k] for k in ("altname", "wsname") if k in pair},
        "base_asset": pair.get("base"),
        "quote_asset": pair.get("quote"),
        "status": pair.get("status"),
        "price_tick": _decimal(pair["tick_size"], "tick_size") if pair.get("tick_size") is not None else None,
        "quantity_precision": pair.get("lot_decimals"),
        "min_quantity": _decimal(pair["ordermin"], "ordermin") if pair.get("ordermin") is not None else None,
        "min_notional": _decimal(pair["costmin"], "costmin") if pair.get("costmin") is not None else None,
        "quantity_step": None,
        "trading_rules": rules,
        "provider_extensions": extensions,
    }


def _mapping_status(mapping: dict) -> str:
    status = mapping.get("status", "unresolved")
    if status == "accepted" and not mapping.get("evidence_reference"):
        raise ValueError("accepted asset mapping requires evidence_reference")
    return status


def resolve_asset_identity(namespace: str, native_code: str,
                           mappings: Iterable[dict], network=None,
                           valid_at=None, known_at=None) -> dict:
    if not namespace or not native_code:
        raise ValueError("namespace and native_code are required")
    candidates = [m for m in mappings if
                  m.get("namespace") == namespace and
                  m.get("native_code") == native_code and
                  m.get("network") == network]
    temporal_query = valid_at is not None or known_at is not None
    if temporal_query and (valid_at is None or known_at is None):
        raise ValueError("valid_at and known_at must be supplied together")
    if temporal_query:
        valid_clock = _aware_utc(valid_at, "valid_at")
        known_clock = _aware_utc(known_at, "known_at")
        selected = []
        for mapping in candidates:
            if not mapping.get("valid_from"):
                continue
            start = _aware_utc(mapping["valid_from"], "valid_from")
            end = _aware_utc(mapping["valid_until"], "valid_until") if mapping.get("valid_until") else None
            recorded = _aware_utc(mapping["recorded_at"], "recorded_at") if mapping.get("recorded_at") else start
            if start <= valid_clock and (end is None or valid_clock < end) and recorded <= known_clock:
                selected.append((recorded, mapping))
        if not selected:
            return {"resolution_status": "unresolved", "canonical_asset_key": None,
                    "evidence_reference": None}
        latest = max(item[0] for item in selected)
        candidates = [m for recorded, m in selected if recorded == latest]
    statuses = [_mapping_status(m) for m in candidates]
    if "ambiguous" in statuses:
        return {"resolution_status": "ambiguous", "canonical_asset_key": None,
                "evidence_reference": None}
    accepted = [m for m in candidates if m.get("status") == "accepted"]
    keys = {m.get("canonical_asset_key") for m in accepted}
    if len(keys) > 1:
        raise ValueError("conflicting accepted asset mappings")
    if accepted:
        mapping = accepted[0]
        return {"resolution_status": "resolved",
                "canonical_asset_key": mapping.get("canonical_asset_key"),
                "evidence_reference": mapping.get("evidence_reference")}
    if "pending_review" in statuses:
        return {"resolution_status": "pending_review", "canonical_asset_key": None,
                "evidence_reference": None}
    return {"resolution_status": "unresolved", "canonical_asset_key": None,
            "evidence_reference": None}
