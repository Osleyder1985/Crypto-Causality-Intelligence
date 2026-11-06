"""Parsers puros para validar contratos canónicos de datos de mercado.

Este módulo no realiza solicitudes HTTP ni persiste datos. Los parsers reciben
payloads ya obtenidos y devuelven valores normalizados usando Decimal y UTC.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence


def _decimal(value: Any, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"Campo decimal inválido: {field}") from exc
    if not result.is_finite():
        raise ValueError(f"Campo decimal no finito: {field}")
    return result


def _epoch_datetime(value: Any, unit: str) -> datetime:
    try:
        stamp = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Timestamp inválido") from exc
    if unit == "ms":
        seconds, remainder = divmod(stamp, 1_000)
        micros = remainder * 1_000
    elif unit == "us":
        seconds, remainder = divmod(stamp, 1_000_000)
        micros = remainder
    elif unit == "s":
        seconds, micros = stamp, 0
    else:
        raise ValueError("Unidad temporal no admitida; use s, ms o us")
    try:
        return datetime.fromtimestamp(seconds, tz=timezone.utc).replace(microsecond=micros)
    except (OverflowError, OSError, ValueError) as exc:
        raise ValueError("Timestamp fuera de rango") from exc


def parse_binance_kline(
    row: Sequence[Any], *, timestamp_unit: str = "ms"
) -> dict[str, Any]:
    """Convierte la tupla REST Klines de 12 posiciones al contrato OHLCV."""
    if len(row) != 12:
        raise ValueError("Binance Kline debe contener exactamente 12 posiciones")
    open_time = _epoch_datetime(row[0], timestamp_unit)
    close_inclusive = _epoch_datetime(row[6], timestamp_unit)
    unit_delta = {"ms": timedelta(milliseconds=1), "us": timedelta(microseconds=1)}.get(
        timestamp_unit
    )
    if unit_delta is None:
        raise ValueError("Binance Klines requiere timestamps ms o us")
    close_exclusive = close_inclusive + unit_delta
    if close_exclusive <= open_time:
        raise ValueError("El cierre debe ser posterior a la apertura")

    return {
        "open_time": open_time,
        "close_time_exclusive": close_exclusive,
        "open": _decimal(row[1], "open"),
        "high": _decimal(row[2], "high"),
        "low": _decimal(row[3], "low"),
        "close": _decimal(row[4], "close"),
        "volume_base": _decimal(row[5], "volume_base"),
        "volume_quote": _decimal(row[7], "volume_quote"),
        "trade_count": int(row[8]),
        "taker_buy_base_volume": _decimal(row[9], "taker_buy_base_volume"),
        "taker_buy_quote_volume": _decimal(row[10], "taker_buy_quote_volume"),
        # REST Klines no declara un booleano de vela final.
        "is_final": None,
        "source_open_time_raw": str(row[0]),
        "source_close_time_raw": str(row[6]),
        "source_timestamp_unit": timestamp_unit,
    }


def parse_kraken_ohlc_row(
    row: Sequence[Any], *, interval_minutes: int, is_last_row: bool
) -> dict[str, Any]:
    """Convierte una fila REST OHLC de Kraken (8 posiciones)."""
    if len(row) != 8:
        raise ValueError("Kraken OHLC debe contener exactamente 8 posiciones")
    if not isinstance(interval_minutes, int) or interval_minutes <= 0:
        raise ValueError("interval_minutes debe ser un entero positivo")
    open_time = _epoch_datetime(row[0], "s")
    close_exclusive = open_time + timedelta(minutes=interval_minutes)
    return {
        "open_time": open_time,
        "close_time_exclusive": close_exclusive,
        "open": _decimal(row[1], "open"),
        "high": _decimal(row[2], "high"),
        "low": _decimal(row[3], "low"),
        "close": _decimal(row[4], "close"),
        "vwap": _decimal(row[5], "vwap"),
        "volume_base": _decimal(row[6], "volume_base"),
        "volume_quote": None,
        "trade_count": int(row[7]),
        # La documentación de Kraken identifica la última fila como provisional.
        "is_final": not is_last_row,
        "source_open_time_raw": str(row[0]),
        "source_close_time_raw": None,
        "source_timestamp_unit": "s",
    }


def map_binance_instrument_metadata(symbol: Mapping[str, Any]) -> dict[str, Any]:
    """Mapea campos comunes y filtros relevantes de exchangeInfo."""
    filters = {
        item.get("filterType"): item
        for item in symbol.get("filters", [])
        if isinstance(item, Mapping) and item.get("filterType")
    }
    price = filters.get("PRICE_FILTER", {})
    lot = filters.get("LOT_SIZE", {})
    notional = filters.get("NOTIONAL") or filters.get("MIN_NOTIONAL") or {}
    result = {
        "source_key": "binance_spot",
        "source_instrument_id": symbol.get("symbol"),
        "native_symbol": symbol.get("symbol"),
        "base_asset_code_native": symbol.get("baseAsset"),
        "quote_asset_code_native": symbol.get("quoteAsset"),
        "instrument_status": symbol.get("status"),
        "price_tick": _decimal(price["tickSize"], "tickSize") if price.get("tickSize") else None,
        "price_minimum": _decimal(price["minPrice"], "minPrice") if price.get("minPrice") else None,
        "price_maximum": _decimal(price["maxPrice"], "maxPrice") if price.get("maxPrice") else None,
        "quantity_step": _decimal(lot["stepSize"], "stepSize") if lot.get("stepSize") else None,
        "min_quantity": _decimal(lot["minQty"], "minQty") if lot.get("minQty") else None,
        "quantity_maximum": _decimal(lot["maxQty"], "maxQty") if lot.get("maxQty") else None,
        "min_notional": None,
        "max_notional": None,
        "provider_extensions": {
            "baseAssetPrecision": symbol.get("baseAssetPrecision"),
            "quoteAssetPrecision": symbol.get("quoteAssetPrecision"),
            "isSpotTradingAllowed": symbol.get("isSpotTradingAllowed"),
            "permissionSets": symbol.get("permissionSets"),
            "filters": list(symbol.get("filters", [])),
            "notional_filter_type": notional.get("filterType"),
            "applyMinToMarket": notional.get("applyMinToMarket", notional.get("applyToMarket")),
            "applyMaxToMarket": notional.get("applyMaxToMarket"),
            "avgPriceMins": notional.get("avgPriceMins"),
        },
    }
    if notional.get("minNotional") is not None:
        result["min_notional"] = _decimal(notional["minNotional"], "minNotional")
    if notional.get("maxNotional") is not None:
        result["max_notional"] = _decimal(notional["maxNotional"], "maxNotional")
    return result


def map_kraken_instrument_metadata(
    result_key: str, pair: Mapping[str, Any]
) -> dict[str, Any]:
    """Mapea AssetPairs sin inferir quantity_step desde lot_decimals."""
    return {
        "source_key": "kraken_spot",
        "source_instrument_id": result_key,
        "native_symbol": pair.get("altname") or result_key,
        "native_aliases": {
            "result_key": result_key,
            "altname": pair.get("altname"),
            "wsname": pair.get("wsname"),
        },
        "base_asset_code_native": pair.get("base"),
        "quote_asset_code_native": pair.get("quote"),
        "instrument_status": pair.get("status"),
        "price_tick": _decimal(pair["tick_size"], "tick_size") if pair.get("tick_size") else None,
        "price_precision": pair.get("pair_decimals"),
        "quantity_precision": pair.get("lot_decimals"),
        "min_quantity": _decimal(pair["ordermin"], "ordermin") if pair.get("ordermin") else None,
        "min_notional": _decimal(pair["costmin"], "costmin") if pair.get("costmin") else None,
        "quantity_step": None,
        "provider_extensions": {
            key: pair.get(key)
            for key in ("aclass_base", "aclass_quote", "lot_multiplier", "cost_decimals")
            if key in pair
        },
    }
