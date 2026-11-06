"""Validation of the versioned, auditable BTC/USDT episode manifest."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


class ManifestError(ValueError):
    """The episode manifest is incomplete, inconsistent, or not executable."""


def _timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise ManifestError(f"{field}: se requiere timestamp ISO-8601 con offset")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ManifestError(f"{field}: timestamp ISO-8601 inválido") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ManifestError(f"{field}: falta el offset horario explícito")
    return parsed


def validate_manifest(document: Any, *, require_approved: bool = True) -> list[dict[str, Any]]:
    """Validate metadata and return the study's normalized episode records.

    Local bounds are retained in the manifest for audit, while UTC bounds are
    checked against their exact conversion. Execution is fail-closed.
    """
    if not isinstance(document, dict):
        raise ManifestError("El manifiesto debe ser un objeto JSON versionado")
    required = {
        "schema_version", "manifest_status", "experiment_key", "market",
        "venue", "market_type", "interval_seconds", "input_timezone",
        "data_source", "data_usage_authorization", "episodes",
    }
    missing = sorted(required - document.keys())
    if missing:
        raise ManifestError(f"Faltan campos del manifiesto: {', '.join(missing)}")
    if document["schema_version"] != "cci.episode-manifest.v1":
        raise ManifestError("schema_version no soportada")
    if document["manifest_status"] not in ("pending_confirmation", "approved"):
        raise ManifestError("manifest_status debe ser pending_confirmation o approved")
    if require_approved and document["manifest_status"] != "approved":
        raise ManifestError("El manifiesto está pendiente; no se permite ejecutar el estudio")
    if not isinstance(document["experiment_key"], str) or not document["experiment_key"].strip():
        raise ManifestError("experiment_key debe ser texto no vacío")
    if document["market"] != "BTC/USDT":
        raise ManifestError("El mercado debe ser BTC/USDT")
    if document["market_type"] != "spot":
        raise ManifestError("El experimento preregistrado exige BTC/USDT spot")

    if not isinstance(document["venue"], str) or not document["venue"].strip():
        raise ManifestError("venue debe identificar un exchange único")
    if document["input_timezone"] != "UTC-05:00":
        raise ManifestError("input_timezone debe coincidir con la zona declarada UTC-05:00")
    interval = document["interval_seconds"]
    if not isinstance(interval, int) or isinstance(interval, bool) or interval != 3600:
        raise ManifestError("El experimento preregistrado exige velas de 3600 segundos (1 hora)")
    source = document["data_source"]
    if not isinstance(source, dict) or not all(
        isinstance(source.get(k), str) and source[k].strip()
        for k in ("provider", "dataset_id", "acquisition_method")
    ):
        raise ManifestError("data_source requiere provider, dataset_id y acquisition_method")
    authorization = document["data_usage_authorization"]
    if not isinstance(authorization, dict) or authorization.get("status") not in (
        "pending", "authorized", "not_authorized"
    ):
        raise ManifestError("data_usage_authorization.status inválido")
    if require_approved and authorization["status"] != "authorized":
        raise ManifestError("El uso/retención del dataset no está autorizado")
    if authorization["status"] == "authorized" and not (
        isinstance(authorization.get("evidence_ref"), str) and authorization["evidence_ref"].strip()
    ):
        raise ManifestError("La autorización requiere evidence_ref no vacío")
    episodes = document["episodes"]
    if not isinstance(episodes, list) or not episodes:
        raise ManifestError("episodes debe contener al menos un episodio confirmado")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(episodes):
        prefix = f"episodes[{index}]"
        if not isinstance(item, dict):
            raise ManifestError(f"{prefix}: debe ser un objeto")
        for key in ("episode_id", "direction", "status", "start_local", "end_local", "start_utc", "end_utc"):
            if key not in item:
                raise ManifestError(f"{prefix}: falta {key}")
        episode_id = item["episode_id"]
        if not isinstance(episode_id, str) or not episode_id.strip() or episode_id in seen:
            raise ManifestError(f"{prefix}: episode_id debe ser texto único y no vacío")
        if item["direction"] not in ("bullish", "bearish"):
            raise ManifestError(f"{episode_id}: direction debe ser bullish o bearish")
        if item["status"] != "confirmed":
            raise ManifestError(f"{episode_id}: episodio no confirmado")
        start_local = _timestamp(item["start_local"], f"{episode_id}.start_local")
        end_local = _timestamp(item["end_local"], f"{episode_id}.end_local")
        if start_local.utcoffset() != timedelta(hours=-5) or end_local.utcoffset() != timedelta(hours=-5):
            raise ManifestError(f"{episode_id}: límites locales deben tener offset -05:00")
        start_utc = _timestamp(item["start_utc"], f"{episode_id}.start_utc")
        end_utc = _timestamp(item["end_utc"], f"{episode_id}.end_utc")
        if start_utc.utcoffset() != timedelta(0) or end_utc.utcoffset() != timedelta(0):
            raise ManifestError(f"{episode_id}: límites normalizados deben estar en UTC")
        if start_local.astimezone(timezone.utc) != start_utc.astimezone(timezone.utc):
            raise ManifestError(f"{episode_id}: start_utc no corresponde a start_local")
        if end_local.astimezone(timezone.utc) != end_utc.astimezone(timezone.utc):
            raise ManifestError(f"{episode_id}: end_utc no corresponde a end_local")
        if end_utc <= start_utc:
            raise ManifestError(f"{episode_id}: end debe ser posterior a start")
        epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
        for name, stamp in (("start_utc", start_utc), ("end_utc", end_utc)):
            if (stamp - epoch).total_seconds() % interval:
                raise ManifestError(f"{episode_id}: {name} no está alineado con interval_seconds")
        seen.add(episode_id)
        normalized.append({
            "episode_id": episode_id,
            "direction": item["direction"],
            "start": start_utc.astimezone(timezone.utc),
            "end": end_utc.astimezone(timezone.utc),
        })
    if {episode["direction"] for episode in normalized} != {"bullish", "bearish"}:
        raise ManifestError("La cohorte debe incluir episodios bullish y bearish")
    ordered = sorted(normalized, key=lambda e: e["start"])
    for previous, current in zip(ordered, ordered[1:]):
        if current["start"] < previous["end"]:
            raise ManifestError(
                f"Episodios solapados: {previous['episode_id']} y {current['episode_id']}"
            )
    return normalized


def load_manifest_episodes(path: str | Path) -> list[dict[str, Any]]:
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError(f"No se pudo leer el manifiesto: {exc}") from exc
    return validate_manifest(document, require_approved=True)
