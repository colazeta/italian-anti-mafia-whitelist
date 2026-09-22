"""Replay an approved release from immutable archived captures, never live source URLs."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any, Iterator

from white_list_archive.publishing import public_national_registry as registry
from white_list_archive.storage.evidence import EvidenceStore, freeze_capture_manifest

SCHEMA_VERSION = 1


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def configuration_sha256(value: dict) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _validate_time(value: str, field: str) -> None:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO timestamp with timezone")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Invalid {field}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} requires an explicit timezone")


def _expected_resources(cfg: dict) -> dict[str, tuple[str, str | None]]:
    resources = cfg.get("resources")
    if resources is None:
        return {"primary": (cfg["resource_url"], cfg.get("sha256"))}
    result: dict[str, tuple[str, str | None]] = {}
    for label, item in resources.items():
        result[label] = (item["resource_url"], item.get("sha256"))
    return result


def validate_release_manifest(manifest: dict, config: dict) -> dict[str, dict]:
    """Validate exact release/config/capture binding and return URL→capture lookup.

    The config itself remains a versioned repository input and its canonical digest is
    pinned in the release.  The release additionally pins code and parser/projector
    lineage text.  No source URL is dereferenced here.
    """
    if not isinstance(manifest, dict):
        raise ValueError("Frozen release manifest must be a mapping")
    required = {
        "schema_version",
        "release_id",
        "created_at",
        "code_revision",
        "source_config_sha256",
        "sources",
    }
    if set(manifest) != required or manifest["schema_version"] != SCHEMA_VERSION:
        raise ValueError("Unapproved frozen release manifest envelope")
    if not isinstance(manifest["release_id"], str) or not manifest["release_id"].strip():
        raise ValueError("Frozen release id is required")
    if not isinstance(manifest["code_revision"], str) or not manifest["code_revision"].strip():
        raise ValueError("Frozen release code revision is required")
    _validate_time(manifest["created_at"], "release created_at")
    if manifest["source_config_sha256"] != configuration_sha256(config):
        raise ValueError("Frozen release source configuration digest does not match")
    if not isinstance(manifest["sources"], list):
        raise ValueError("Frozen release sources must be a list")

    config_by_key = {item["source_key"]: item for item in config["sources"]}
    if len(config_by_key) != len(config["sources"]):
        raise ValueError("Publication source configuration contains duplicate source_key")
    manifest_by_key: dict[str, dict] = {}
    for item in manifest["sources"]:
        expected_keys = {
            "source_key",
            "parser",
            "parser_revision",
            "projector_revision",
            "configuration_sha256",
            "resources",
        }
        if not isinstance(item, dict) or set(item) != expected_keys:
            raise ValueError("Unapproved frozen source binding shape")
        source_key = item["source_key"]
        if source_key in manifest_by_key:
            raise ValueError(f"Duplicate frozen source binding: {source_key}")
        manifest_by_key[source_key] = item
    if set(manifest_by_key) != set(config_by_key):
        raise ValueError("Frozen release must bind every and only configured source")

    by_url: dict[str, dict] = {}
    for source_key, cfg in config_by_key.items():
        binding = manifest_by_key[source_key]
        if binding["parser"] != cfg["parser"]:
            raise ValueError(f"{source_key}: frozen parser name does not match configuration")
        if not isinstance(binding["parser_revision"], str) or not binding["parser_revision"].strip():
            raise ValueError(f"{source_key}: parser revision is required")
        if not isinstance(binding["projector_revision"], str) or not binding["projector_revision"].strip():
            raise ValueError(f"{source_key}: projector revision is required")
        if binding["configuration_sha256"] != configuration_sha256(cfg):
            raise ValueError(f"{source_key}: frozen per-source configuration digest does not match")

        expected = _expected_resources(cfg)
        resources = binding["resources"]
        if not isinstance(resources, list):
            raise ValueError(f"{source_key}: frozen resources must be a list")
        resource_by_label = {}
        for resource in resources:
            if not isinstance(resource, dict) or set(resource) != {"label", "capture"}:
                raise ValueError(f"{source_key}: unapproved frozen resource binding")
            label = resource["label"]
            if label in resource_by_label:
                raise ValueError(f"{source_key}: duplicate frozen resource label {label!r}")
            resource_by_label[label] = resource["capture"]
        if set(resource_by_label) != set(expected):
            raise ValueError(f"{source_key}: frozen resource labels do not match configuration")

        for label, (expected_url, expected_raw_sha) in expected.items():
            capture = freeze_capture_manifest(resource_by_label[label])
            if capture.get("source_key") != source_key:
                raise ValueError(f"{source_key}/{label}: capture belongs to another source")
            if capture["resource_url"] != expected_url:
                raise ValueError(f"{source_key}/{label}: release locator differs from pinned configuration")
            if capture["reference_date"] != cfg.get("reference_date"):
                raise ValueError(f"{source_key}/{label}: source reference date differs from pinned configuration")
            approval_mode = str(cfg.get("approval_mode") or "raw_sha256")
            # Raw approvals pin the exact bytes in the publication config. Semantic
            # approvals deliberately allow byte changes but the release still pins the
            # exact archived ContentObject used for this release.
            if approval_mode == "raw_sha256" and expected_raw_sha and not cfg.get("resources"):
                if capture["sha256"] != expected_raw_sha:
                    raise ValueError(f"{source_key}: frozen raw capture SHA differs from approval")
            if cfg.get("resources") and expected_raw_sha and capture["sha256"] != expected_raw_sha:
                raise ValueError(f"{source_key}/{label}: frozen bundle member SHA differs from approval")

            prior = by_url.get(expected_url)
            if prior is not None and (
                prior["sha256"] != capture["sha256"] or prior["byte_size"] != capture["byte_size"]
            ):
                raise ValueError("One frozen release cannot bind the same locator to conflicting bytes")
            by_url[expected_url] = capture
    return by_url


@contextmanager
def archived_downloads(manifest: dict, config: dict, store: EvidenceStore) -> Iterator[None]:
    """Make legacy parser plumbing read only release-pinned archived ContentObjects.

    This transitional adapter is process-local and intended for the existing serial
    release worker.  Unknown URLs fail closed; there is deliberately no live fallback.
    """
    by_url = validate_release_manifest(manifest, config)
    original = registry._download

    def archived_download(url: str, path: Path) -> str:
        capture = by_url.get(url)
        if capture is None:
            raise RuntimeError(f"Frozen release has no archived capture for requested URL: {url}")
        data = store.read_verified(capture)
        if len(data) != capture["byte_size"] or hashlib.sha256(data).hexdigest() != capture["sha256"]:
            raise ValueError("Archived release input failed size/SHA-256 verification")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as handle:
            handle.write(data)
        return capture["sha256"]

    registry._download = archived_download
    try:
        yield
    finally:
        registry._download = original


def build_registry_from_release(
    config: dict,
    work_dir: Path,
    release_manifest: dict,
    store: EvidenceStore,
) -> dict:
    """Build registry rows from exact durable inputs with live source access disabled."""
    with archived_downloads(release_manifest, config, store):
        return registry.build_registry(config, work_dir)
