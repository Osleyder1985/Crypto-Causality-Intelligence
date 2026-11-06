"""Validación pura del contrato de activos, redes y representaciones.

No consulta redes ni proveedores, no normaliza direcciones y no aprueba mappings.
Los tiempos de observación se reciben desde la capa de captura; recorded_at se
asigna exclusivamente en PostgreSQL al persistir el registro.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping


RELATIONSHIP_TYPES = {
    "wrapped_representation_of",
    "bridged_representation_of",
    "redeemable_for",
    "backed_by",
    "tracks_price_of",
    "migrated_to",
}
REPRESENTATION_KINDS = {"native", "token_contract", "other"}
RELATIONSHIP_DIRECTIONALITY = "directed"


def _required_text(record: Mapping[str, Any], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} debe ser un texto no vacío")
    return value


def _optional_text(record: Mapping[str, Any], field: str) -> str | None:
    value = record.get(field)
    if value is not None and (not isinstance(value, str) or not value.strip()):
        raise ValueError(f"{field} debe ser NULL o un texto no vacío")
    return value


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


def _validity(record: Mapping[str, Any], prefix: str = "") -> tuple[datetime | None, datetime | None]:
    from_field = f"{prefix}valid_from"
    until_field = f"{prefix}valid_until"
    valid_from = record.get("valid_from")
    valid_until = record.get("valid_until")
    if valid_from is not None:
        valid_from = _aware_timestamp(valid_from, from_field)
    if valid_until is not None:
        valid_until = _aware_timestamp(valid_until, until_field)
        if valid_from is None or valid_until <= valid_from:
            raise ValueError(f"{until_field} requiere {from_field} anterior")
    return valid_from, valid_until


def validate_asset_representation(
    representation: Mapping[str, Any],
) -> dict[str, Any]:
    """Valida una representación individual sin mutar ni normalizar el input."""
    if not isinstance(representation, Mapping):
        raise ValueError("Cada representación debe ser un objeto/mapping")

    representation_key = _required_text(representation, "representation_key")
    asset_key = _required_text(representation, "asset_key")
    network_key = _required_text(representation, "network_key")
    kind = _required_text(representation, "representation_kind")
    if kind not in REPRESENTATION_KINDS:
        raise ValueError(f"representation_kind no admitido: {kind}")

    native_key = _optional_text(representation, "native_asset_key")
    contract = _optional_text(representation, "contract_address")
    if kind == "native":
        if native_key is None or contract is not None:
            raise ValueError(
                "Una representación native requiere native_asset_key y no admite contract_address"
            )
    elif kind == "token_contract":
        if contract is None or native_key is not None:
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

    valid_from, valid_until = _validity(representation)
    observed_at = _aware_timestamp(representation.get("observed_at"), "observed_at")
    evidence_reference = _required_text(representation, "evidence_reference")

    return {
        "representation_key": representation_key,
        "asset_key": asset_key,
        "network_key": network_key,
        "representation_kind": kind,
        "native_asset_key": native_key,
        "contract_address": contract,
        "address_normalization": _optional_text(representation, "address_normalization"),
        "token_standard": _optional_text(representation, "token_standard"),
        "decimals": decimals,
        "issuer_key": _optional_text(representation, "issuer_key"),
        "valid_from": valid_from,
        "valid_until": valid_until,
        "observed_at": observed_at,
        "evidence_reference": evidence_reference,
    }


def _catalog_keys(items: Any, field: str, label: str) -> set[str]:
    if not isinstance(items, list):
        raise ValueError(f"{label} debe ser una lista")
    keys = []
    for item in items:
        if not isinstance(item, Mapping):
            raise ValueError(f"Cada elemento de {label} debe ser un objeto/mapping")
        keys.append(_required_text(item, field))
    if len(keys) != len(set(keys)):
        raise ValueError(f"{field} ausente o duplicado")
    return set(keys)


def validate_asset_representation_catalog(
    catalog: Mapping[str, Any],
) -> dict[str, Any]:
    """Valida un catálogo y devuelve representaciones y relaciones normalizadas."""
    if not isinstance(catalog, Mapping):
        raise ValueError("catalog debe ser un objeto/mapping")

    asset_set = _catalog_keys(catalog.get("assets"), "asset_key", "assets")
    network_set = _catalog_keys(catalog.get("networks"), "network_key", "networks")
    representations = catalog.get("representations")
    relationships = catalog.get("relationships", [])
    if not isinstance(representations, list) or not isinstance(relationships, list):
        raise ValueError("representations y relationships deben ser listas")

    validated_representations = []
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
            deployment_key = (item["network_key"], "native", item["native_asset_key"])
        elif item["representation_kind"] == "token_contract":
            # La dirección se conserva literalmente; la normalización depende de la red.
            deployment_key = (item["network_key"], "token_contract", item["contract_address"])
        else:
            deployment_key = (
                item["network_key"], "other", item["native_asset_key"],
                item["contract_address"], item["representation_key"],
            )
        if deployment_key in deployment_keys:
            raise ValueError("Representación/despliegue duplicado dentro de la misma red")
        deployment_keys.add(deployment_key)
        validated_representations.append(item)

    validated_relationships = []
    relationship_keys = set()
    for relation in relationships:
        if not isinstance(relation, Mapping):
            raise ValueError("Cada relación debe ser un objeto/mapping")
        subject = _required_text(relation, "subject_asset_key")
        object_ = _required_text(relation, "object_asset_key")
        kind = _required_text(relation, "relationship_type")
        if subject not in asset_set or object_ not in asset_set:
            raise ValueError("La relación referencia un activo inexistente")
        if subject == object_:
            raise ValueError("No se permiten autorrelaciones entre activos")
        if kind not in RELATIONSHIP_TYPES:
            raise ValueError(f"relationship_type no admitido: {kind}")
        directionality = relation.get("directionality", RELATIONSHIP_DIRECTIONALITY)
        if directionality != RELATIONSHIP_DIRECTIONALITY:
            raise ValueError("directionality debe ser 'directed'")
        valid_from, valid_until = _validity(relation, "relationship.")
        observed_at = _aware_timestamp(relation.get("observed_at"), "relationship.observed_at")
        evidence = _required_text(relation, "evidence_reference")
        key = (subject, object_, kind, valid_from, valid_until)
        if key in relationship_keys:
            raise ValueError("Relación duplicada")
        relationship_keys.add(key)
        validated_relationships.append({
            "subject_asset_key": subject,
            "object_asset_key": object_,
            "relationship_type": kind,
            "directionality": RELATIONSHIP_DIRECTIONALITY,
            "valid_from": valid_from,
            "valid_until": valid_until,
            "observed_at": observed_at,
            "evidence_reference": evidence,
        })

    return {
        "assets_count": len(asset_set),
        "networks_count": len(network_set),
        "representations_count": len(validated_representations),
        "relationships_count": len(validated_relationships),
        "representations": validated_representations,
        "relationships": validated_relationships,
    }
