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



def _identity_timestamp(value: Any, field: str) -> datetime:
    """Valida timestamps ISO-8601 con zona horaria para resolución temporal."""
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"Timestamp inválido: {field}") from exc
    else:
        raise ValueError(f"Timestamp obligatorio: {field}")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"Timestamp debe incluir zona horaria: {field}")
    return parsed.astimezone(timezone.utc)


def resolve_asset_identity(
    namespace: str,
    native_code: str,
    mappings: Sequence[Mapping[str, Any]],
    *,
    network: str | None = None,
    valid_at: datetime | str | None = None,
    known_at: datetime | str | None = None,
) -> dict[str, Any]:
    """Resuelve correspondencias exactas, con consulta bitemporal opcional.

    valid_at selecciona el periodo de validez en el dominio del proveedor.
    known_at limita la decisión a lo que CCI ya había registrado en ese instante.
    En modo temporal, solo se consideran filas con valid_from y recorded_at
    explícitos; valid_until es exclusivo y puede ser NULL (sin fin conocido).
    """
    if not namespace or not native_code:
        raise ValueError("namespace y native_code son obligatorios")
    temporal_mode = valid_at is not None or known_at is not None
    if temporal_mode and (valid_at is None or known_at is None):
        raise ValueError("valid_at y known_at deben proporcionarse juntos")
    query_valid_at = (
        _identity_timestamp(valid_at, "valid_at") if temporal_mode else None
    )
    query_known_at = (
        _identity_timestamp(known_at, "known_at") if temporal_mode else None
    )

    matches = []
    for item in mappings:
        if not (
            item.get("namespace") == namespace
            and item.get("native_code") == native_code
            and item.get("network") == network
        ):
            continue
        if temporal_mode:
            # Sin inicio de validez o tiempo de registro no hay base para
            # afirmar que la decisión aplicaba y era conocida en la consulta.
            if item.get("valid_from") is None or item.get("recorded_at") is None:
                continue
            valid_from = _identity_timestamp(item["valid_from"], "valid_from")
            recorded_at = _identity_timestamp(item["recorded_at"], "recorded_at")
            valid_until = (
                _identity_timestamp(item["valid_until"], "valid_until")
                if item.get("valid_until") is not None else None
            )
            if valid_until is not None and valid_until <= valid_from:
                raise ValueError("valid_until debe ser posterior a valid_from")
            if not (valid_from <= query_valid_at and
                    (valid_until is None or query_valid_at < valid_until)):
                continue
            if recorded_at > query_known_at:
                continue
        matches.append(item)

    if temporal_mode and matches:
        latest_recorded_at = max(
            _identity_timestamp(item["recorded_at"], "recorded_at")
            for item in matches
        )
        # Una corrección posterior sustituye el conocimiento anterior para
        # esa misma clave exacta, sin borrar lo que se conocía en known_at.
        matches = [
            item for item in matches
            if _identity_timestamp(item["recorded_at"], "recorded_at")
            == latest_recorded_at
        ]

    accepted = [item for item in matches if item.get("status") == "accepted"]
    accepted_targets = {item.get("canonical_asset_key") for item in accepted}
    if "ambiguous" in {item.get("status") for item in matches}:
        resolution_status = "ambiguous"
        canonical_asset_key = None
        evidence_reference = None
    elif len(accepted_targets) > 1:
        raise ValueError("Correspondencias aceptadas en conflicto para el mismo identificador")
    elif accepted:
        item = accepted[0]
        if not item.get("canonical_asset_key") or not item.get("evidence_reference"):
            raise ValueError("Una correspondencia accepted requiere destino y evidencia")
        resolution_status = "resolved"
        canonical_asset_key = item["canonical_asset_key"]
        evidence_reference = item["evidence_reference"]
    else:
        statuses = {item.get("status") for item in matches}
        resolution_status = "ambiguous" if "ambiguous" in statuses else (
            "pending_review" if matches else "unresolved"
        )
        canonical_asset_key = None
        evidence_reference = None

    return {
        "resolution_status": resolution_status,
        "canonical_asset_key": canonical_asset_key,
        "evidence_reference": evidence_reference,
        "matched_namespace": namespace,
        "matched_native_code": native_code,
        "matched_network": network,
    }


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
    """Mapea exchangeInfo sin descartar filtros ni confundir sus ámbitos."""
    raw_filters = symbol.get("filters", [])
    if not isinstance(raw_filters, Sequence) or isinstance(raw_filters, (str, bytes)):
        raise ValueError("Binance filters debe ser una secuencia")

    filters: dict[str, Mapping[str, Any]] = {}
    trading_rules: list[dict[str, Any]] = []
    for item in raw_filters:
        if not isinstance(item, Mapping) or not item.get("filterType"):
            raise ValueError("Filtro Binance inválido o sin filterType")
        filter_type = str(item["filterType"])
        if filter_type in filters:
            raise ValueError(f"Filtro Binance duplicado: {filter_type}")
        filters[filter_type] = item
        # Conservar el objeto nativo completo, incluso filtros aún no mapeados.
        trading_rules.append({
            "rule_namespace": "binance_spot",
            "rule_scope": filter_type,
            "parameters": dict(item),
        })

    price = filters.get("PRICE_FILTER", {})
    lot = filters.get("LOT_SIZE", {})
    market_lot = filters.get("MARKET_LOT_SIZE", {})
    notional = filters.get("NOTIONAL") or filters.get("MIN_NOTIONAL") or {}

    def optional_decimal(container: Mapping[str, Any], key: str) -> Decimal | None:
        value = container.get(key)
        return _decimal(value, key) if value is not None and value != "" else None

    known_symbol_fields = {
        "symbol", "status", "baseAsset", "quoteAsset", "filters",
        "baseAssetPrecision", "quoteAssetPrecision", "isSpotTradingAllowed",
        "permissionSets",
    }
    return {
        "source_key": "binance_spot",
        "source_instrument_id": symbol.get("symbol"),
        "native_symbol": symbol.get("symbol"),
        "base_asset_code_native": symbol.get("baseAsset"),
        "quote_asset_code_native": symbol.get("quoteAsset"),
        "instrument_status": symbol.get("status"),
        "price_tick": optional_decimal(price, "tickSize"),
        "price_minimum": optional_decimal(price, "minPrice"),
        "price_maximum": optional_decimal(price, "maxPrice"),
        "quantity_step": optional_decimal(lot, "stepSize"),
        "min_quantity": optional_decimal(lot, "minQty"),
        "quantity_maximum": optional_decimal(lot, "maxQty"),
        "market_quantity_step": optional_decimal(market_lot, "stepSize"),
        "market_min_quantity": optional_decimal(market_lot, "minQty"),
        "market_quantity_maximum": optional_decimal(market_lot, "maxQty"),
        "min_notional": optional_decimal(notional, "minNotional"),
        "max_notional": optional_decimal(notional, "maxNotional"),
        "trading_rules": trading_rules,
        "provider_extensions": {
            **{key: value for key, value in symbol.items() if key not in known_symbol_fields},
            "baseAssetPrecision": symbol.get("baseAssetPrecision"),
            "quoteAssetPrecision": symbol.get("quoteAssetPrecision"),
            "isSpotTradingAllowed": symbol.get("isSpotTradingAllowed"),
            "permissionSets": symbol.get("permissionSets"),
            "unknown_filter_types": [
                name for name in filters
                if name not in {
                    "PRICE_FILTER", "LOT_SIZE", "MARKET_LOT_SIZE",
                    "MIN_NOTIONAL", "NOTIONAL",
                }
            ],
        },
    }


def map_kraken_instrument_metadata(
    result_key: str, pair: Mapping[str, Any]
) -> dict[str, Any]:
    """Mapea AssetPairs y conserva campos nativos no reconocidos."""
    known_fields = {
        "altname", "wsname", "base", "quote", "status", "tick_size",
        "pair_decimals", "lot_decimals", "ordermin", "costmin",
    }
    def optional_decimal(key: str) -> Decimal | None:
        value = pair.get(key)
        return _decimal(value, key) if value is not None and value != "" else None

    rule_parameters = {
        key: pair[key]
        for key in ("tick_size", "ordermin", "costmin", "pair_decimals", "lot_decimals")
        if key in pair
    }
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
        "price_tick": optional_decimal("tick_size"),
        "price_precision": pair.get("pair_decimals"),
        "quantity_precision": pair.get("lot_decimals"),
        "min_quantity": optional_decimal("ordermin"),
        "min_notional": optional_decimal("costmin"),
        "quantity_step": None,
        "trading_rules": [{
            "rule_namespace": "kraken_spot",
            "rule_scope": "asset_pair",
            "parameters": rule_parameters,
        }],
        "provider_extensions": {
            key: value for key, value in pair.items() if key not in known_fields
        },
    }
