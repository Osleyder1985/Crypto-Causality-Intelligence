"""Validación pura del contrato de activos, redes y representaciones.

No consulta redes ni proveedores, no normaliza direcciones y no aprueba mappings.
Las direcciones y referencias se validan estructuralmente; su formato canónico
depende de la familia de red y queda fuera de este contrato inicial.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence


RELATIONSHIP_TYPES = {
    "wrapped_representation_of",
    "bridged_representation_of",
    "redeemable_for",
    "backed_by",
    "tracks_price_of",
    "migrated_to",
}
REPRESENTATION_KINDS = {"native", "token_contract", "other"}


def _aware_timestamp(value: Any, field: str) -> datetime:
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


def validate_asset_representation(
    representation: Mapping[str, Any],
) -> dict[str, Any]:
    """Valida una representación individual sin mutar ni normalizar el input."""
    required = ("representation_key", "asset_key", "network_key", "representation_kind")
    missing = [field for field in required if not representation.get(field)]
    if missing:
        raise ValueError(f"Campos obligatorios ausentes: {', '.join(missing)}")

    kind = representation["representation_kind"]
    if kind not in REPRESENTATION_KINDS:
        raise ValueError(f"representation_kind no admitido: {kind}")

    native_key = representation.get("native_asset_key")
    contract = representation.get("contract_address")
    if kind == "native":
        if not native_key or contract is not None:
            raise ValueError(
                "Una representación native requiere native_asset_key y no admite contract_address"
            )
    elif kind == "token_contract":
        if not contract or native_key is not None:
            raise ValueError(
                "Una representación token_contract requiere contract_address y no admite native_asset_key"
            )
    elif native_key is not None and contract is not None:
        raise ValueError("Una representación other no puede mezclar claves nativas y contratos")

    decimals = representation.get("decimals")
    if decimals is not None and (
        not isinstance(decimals, int) or isinstance(decimals, bool) or decimals < 0
    ):
        raise ValueError("decimals debe ser un entero no negativo o NULL")

    valid_from = representation.get("valid_from")
    valid_until = representation.get("valid_until")
    if valid_from is not None:
        valid_from = _aware_timestamp(valid_from, "valid_from")
    if valid_until is not None:
        valid_until = _aware_timestamp(valid_until, "valid_until")
        if valid_from is None or valid_until <= valid_from:
            raise ValueError("valid_until requiere valid_from anterior")

    if not representation.get("evidence_reference"):
        raise ValueError("evidence_reference es obligatorio")

    return {
        "representation_key": representation["representation_key"],
        "asset_key": representation["asset_key"],
        "network_key": representation["network_key"],
        "representation_kind": kind,
        "native_asset_key": native_key,
        "contract_address": contract,
        "decimals": decimals,
        "valid_from": valid_from,
        "valid_until": valid_until,
        "evidence_reference": representation["evidence_reference"],
    }


def validate_asset_representation_catalog(
    catalog: Mapping[str, Any],
) -> dict[str, Any]:
    """Valida relaciones y unicidad dentro de un catálogo sintético/declarativo."""
    assets = catalog.get("assets")
    networks = catalog.get("networks")
    representations = catalog.get("representations")
    relationships = catalog.get("relationships", [])
    if not isinstance(assets, list) or not isinstance(networks, list):
        raise ValueError("assets y networks deben ser listas")
    if not isinstance(representations, list) or not isinstance(relationships, list):
        raise ValueError("representations y relationships deben ser listas")

    asset_keys = [item.get("asset_key") for item in assets]
    network_keys = [item.get("network_key") for item in networks]
    if any(not key for key in asset_keys) or len(asset_keys) != len(set(asset_keys)):
        raise ValueError("asset_key ausente o duplicado")
    if any(not key for key in network_keys) or len(network_keys) != len(set(network_keys)):
        raise ValueError("network_key ausente o duplicado")
    asset_set, network_set = set(asset_keys), set(network_keys)

    validated = []
    representation_keys = set()
    deployment_keys = set()
    for raw in representations:
        item = validate_asset_representation(raw)
        if item["asset_key"] not in asset_set:
            raise ValueError(f"Activo inexistente: {item['asset_key']}")
        if item["network_key"] not in network_set:
            raise ValueError(f"Red inexistente: {item['network_key']}")
        if item["representation_key"] in representation_keys:
            raise ValueError("representation_key duplicada")
        representation_keys.add(item["representation_key"])

        if item["representation_kind"] == "native":
            deployment_key = (
                item["network_key"], "native", item["native_asset_key"]
            )
        elif item["representation_kind"] == "token_contract":
            # Se conserva la dirección literal. No se aplica lower(), checksum
            # ni normalización global antes de definir reglas por familia.
            deployment_key = (
                item["network_key"], "token_contract", item["contract_address"]
            )
        else:
            deployment_key = (
                item["network_key"], "other",
                item["native_asset_key"], item["contract_address"],
                item["representation_key"],
            )
        if deployment_key in deployment_keys:
            raise ValueError("Representación/despliegue duplicado dentro de la misma red")
        deployment_keys.add(deployment_key)
        validated.append(item)

    relationship_keys = set()
    for relation in relationships:
        subject = relation.get("subject_asset_key")
        object_ = relation.get("object_asset_key")
        kind = relation.get("relationship_type")
        evidence = relation.get("evidence_reference")
        if subject not in asset_set or object_ not in asset_set:
            raise ValueError("La relación referencia un activo inexistente")
        if subject == object_:
            raise ValueError("No se permiten autorrelaciones entre activos")
        if kind not in RELATIONSHIP_TYPES:
            raise ValueError(f"relationship_type no admitido: {kind}")
        if not evidence:
            raise ValueError("Toda relación requiere evidence_reference")
        valid_from = relation.get("valid_from")
        valid_until = relation.get("valid_until")
        if valid_from is not None:
            valid_from = _aware_timestamp(valid_from, "relationship.valid_from")
        if valid_until is not None:
            valid_until = _aware_timestamp(valid_until, "relationship.valid_until")
            if valid_from is None or valid_until <= valid_from:
                raise ValueError("relationship.valid_until requiere valid_from anterior")
        key = (subject, object_, kind, valid_from, valid_until)
        if key in relationship_keys:
            raise ValueError("Relación duplicada")
        relationship_keys.add(key)

    return {
        "assets_count": len(assets),
        "networks_count": len(networks),
        "representations_count": len(validated),
        "relationships_count": len(relationships),
        "representations": validated,
    }
