"""Replay an approved release from immutable archived captures, never live source URLs."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any, Iterator

from white_list_archive.publishing import public_national_registry as registry
from white_list_archive.storage.capture_catalogue import CaptureCatalogue
from white_list_archive.storage.evidence import EvidenceStore, freeze_capture_manifest

SCHEMA_VERSION = 1
PUBLIC_PROJECTOR_REVISION = "public-national-registry@1"


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
    """Validate exact release/config/capture bindings without dereferencing source URLs.

    Every resource pins both an immutable ContentObject identity and the separate
    durable capture/check catalogue receipt. Provider readback happens in
    ``archived_downloads`` before parsers can receive the bytes. The returned URL map is
    only a compatibility adapter for legacy parser plumbing; it is not capture identity.
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
        resource_by_label: dict[str, dict] = {}
        for resource in resources:
            if not isinstance(resource, dict) or set(resource) != {"label", "capture", "catalogue"}:
                raise ValueError(f"{source_key}: unapproved frozen resource binding")
            label = resource["label"]
            if label in resource_by_label:
                raise ValueError(f"{source_key}: duplicate frozen resource label {label!r}")
            if not isinstance(resource["catalogue"], dict):
                raise ValueError(f"{source_key}/{label}: capture catalogue receipt must be a mapping")
            resource_by_label[label] = resource
        if set(resource_by_label) != set(expected):
            raise ValueError(f"{source_key}: frozen resource labels do not match configuration")

        for label, (expected_url, expected_raw_sha) in expected.items():
            resource = resource_by_label[label]
            capture = freeze_capture_manifest(resource["capture"])
            catalogue = resource["catalogue"]
            if capture.get("source_key") != source_key:
                raise ValueError(f"{source_key}/{label}: capture belongs to another source")
            if capture["resource_url"] != expected_url:
                raise ValueError(f"{source_key}/{label}: release locator differs from pinned configuration")
            if capture["reference_date"] != cfg.get("reference_date"):
                raise ValueError(f"{source_key}/{label}: source reference date differs from pinned configuration")
            if catalogue.get("capture_id") != capture.get("capture_id"):
                raise ValueError(f"{source_key}/{label}: catalogue receipt belongs to another capture")
            if catalogue.get("sha256") != capture["sha256"] or catalogue.get("byte_size") != capture["byte_size"]:
                raise ValueError(f"{source_key}/{label}: catalogue receipt disagrees with capture bytes")
            approval_mode = str(cfg.get("approval_mode") or "raw_sha256")
            if approval_mode == "raw_sha256" and expected_raw_sha and not cfg.get("resources"):
                if capture["sha256"] != expected_raw_sha:
                    raise ValueError(f"{source_key}: frozen raw capture SHA differs from approval")
            if cfg.get("resources") and expected_raw_sha and capture["sha256"] != expected_raw_sha:
                raise ValueError(f"{source_key}/{label}: frozen bundle member SHA differs from approval")

            # Locator reuse is allowed only when the selected payload bytes agree. The
            # URL remains a parser-routing key; each capture/check is still independently
            # verified later and never collapsed into this map as an archival identity.
            prior = by_url.get(expected_url)
            if prior is not None and (
                prior["capture"]["sha256"] != capture["sha256"]
                or prior["capture"]["byte_size"] != capture["byte_size"]
            ):
                raise ValueError("One frozen release cannot bind the same locator to conflicting bytes")
            by_url[expected_url] = {"capture": capture, "catalogue": catalogue}
    return by_url


def validate_release_runtime(
    manifest: dict,
    built_registry: dict,
    *,
    runtime_code_revision: str,
    projector_revision: str = PUBLIC_PROJECTOR_REVISION,
) -> None:
    """Fail closed unless replay actually used the revisions pinned by the release.

    The manifest is not merely descriptive metadata: code, projector and parser
    revisions are executable release inputs. Parser revisions use the canonical
    ``<parser_name>@<parser_version>`` form after parser-specific diagnostics have
    been restored onto public records.
    """
    if not isinstance(runtime_code_revision, str) or not runtime_code_revision.strip():
        raise ValueError("Runtime code revision is required for frozen release replay")
    if manifest.get("code_revision") != runtime_code_revision:
        raise ValueError("Frozen release code revision does not match replay runtime")
    if not isinstance(projector_revision, str) or not projector_revision.strip():
        raise ValueError("Runtime projector revision is required for frozen release replay")

    bindings = {item["source_key"]: item for item in manifest.get("sources", [])}
    observed: dict[str, str] = {}
    for record in built_registry.get("records", []):
        source_key = record.get("source_key")
        parser_name = record.get("parser_name")
        parser_version = record.get("parser_version")
        if not all(isinstance(value, str) and value.strip() for value in (source_key, parser_name, str(parser_version) if parser_version is not None else None)):
            raise ValueError("Frozen release replay produced incomplete parser revision metadata")
        revision = f"{parser_name}@{parser_version}"
        prior = observed.get(source_key)
        if prior is not None and prior != revision:
            raise ValueError(f"{source_key}: replay produced inconsistent parser revisions")
        observed[source_key] = revision

    if set(observed) != set(bindings):
        raise ValueError("Frozen release replay did not produce every and only pinned source")
    for source_key, binding in bindings.items():
        if binding.get("projector_revision") != projector_revision:
            raise ValueError(f"{source_key}: frozen projector revision does not match replay runtime")
        if binding.get("parser_revision") != observed[source_key]:
            raise ValueError(f"{source_key}: frozen parser revision does not match replay runtime")


def _verified_payloads_by_url(manifest: dict, config: dict, store: EvidenceStore) -> dict[str, bytes]:
    """Verify every selected capture/check, then expose bytes by locator for legacy parsers.

    The URL-keyed result is deliberately only a transitional parser adapter. Two source
    scopes may point at the same locator and even the same ContentObject while retaining
    distinct capture identities; both immutable catalogue records are verified and both
    selected captures are read back before a single parser is allowed to consume bytes.
    """
    validate_release_manifest(manifest, config)
    catalogue = CaptureCatalogue(store)
    payload_by_url: dict[str, bytes] = {}
    verified_capture_ids: set[str] = set()

    for source in manifest["sources"]:
        for resource in source["resources"]:
            capture = freeze_capture_manifest(resource["capture"])
            capture_id = capture.get("capture_id")
            if not isinstance(capture_id, str) or not capture_id:
                raise ValueError("Frozen release resource lacks capture identity")
            if capture_id in verified_capture_ids:
                raise ValueError("Frozen release cannot reuse one capture/check for multiple configured resources")

            catalogue.verify_receipt(capture, resource["catalogue"])
            data = store.read_verified(capture)
            if len(data) != capture["byte_size"] or hashlib.sha256(data).hexdigest() != capture["sha256"]:
                raise ValueError("Archived release input failed size/SHA-256 verification")

            url = capture["resource_url"]
            prior = payload_by_url.get(url)
            if prior is not None and prior != data:
                raise ValueError("One frozen release cannot route conflicting archived bytes through the same locator")
            payload_by_url[url] = data
            verified_capture_ids.add(capture_id)

    return payload_by_url


@contextmanager
def archived_downloads(manifest: dict, config: dict, store: EvidenceStore) -> Iterator[None]:
    """Make legacy parser plumbing read only fully verified release-pinned captures.

    This transitional adapter is process-local and intended for the existing serial
    release worker. Unknown URLs fail closed; there is deliberately no live fallback.
    Every selected capture/check and original ContentObject is independently read back
    from the approved private backend before the parser-facing path is created, even
    when multiple scopes reuse the same source locator.
    """
    payload_by_url = _verified_payloads_by_url(manifest, config, store)
    by_url = validate_release_manifest(manifest, config)
    original = registry._download

    def archived_download(url: str, path: Path) -> str:
        resource = by_url.get(url)
        data = payload_by_url.get(url)
        if resource is None or data is None:
            raise RuntimeError(f"Frozen release has no archived capture for requested URL: {url}")
        capture = resource["capture"]
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
