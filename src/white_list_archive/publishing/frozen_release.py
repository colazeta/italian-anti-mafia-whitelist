"""Replay an approved release from immutable archived captures, never live source URLs."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlparse

from white_list_archive.publishing import public_national_registry as registry
from white_list_archive.storage.capture_catalogue import CaptureCatalogue
from white_list_archive.storage.evidence import EvidenceStore, freeze_capture_manifest

SCHEMA_VERSION = 1
PUBLIC_PROJECTOR_REVISION = "public-national-registry@1"
ResourceIdentity = tuple[str, str]


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


def _resource_identity(source_key: str, label: str) -> ResourceIdentity:
    return source_key, label


def validate_release_manifest(manifest: dict, config: dict) -> dict[ResourceIdentity, dict]:
    """Validate exact release/config/capture bindings without dereferencing source URLs.

    Every resource pins both an immutable ContentObject identity and the separate
    durable capture/check catalogue receipt. The returned mapping is keyed by the
    logical configured source/resource identity. A URL remains verified locator
    metadata and is deliberately not used to route archived bytes.
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

    by_resource: dict[ResourceIdentity, dict] = {}
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

            identity = _resource_identity(source_key, label)
            if identity in by_resource:
                raise ValueError(f"Duplicate frozen logical resource binding: {source_key}/{label}")
            by_resource[identity] = {"capture": capture, "catalogue": catalogue}
    return by_resource


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


def _verified_payloads_by_resource(
    manifest: dict,
    config: dict,
    store: EvidenceStore,
) -> dict[ResourceIdentity, bytes]:
    """Verify every selected capture/check and return bytes by logical resource identity."""
    bindings = validate_release_manifest(manifest, config)
    catalogue = CaptureCatalogue(store)
    payload_by_resource: dict[ResourceIdentity, bytes] = {}
    verified_capture_ids: set[str] = set()

    for source in manifest["sources"]:
        source_key = source["source_key"]
        for resource in source["resources"]:
            label = resource["label"]
            identity = _resource_identity(source_key, label)
            capture = freeze_capture_manifest(resource["capture"])
            capture_id = capture.get("capture_id")
            if not isinstance(capture_id, str) or not capture_id:
                raise ValueError("Frozen release resource lacks capture identity")
            if capture_id in verified_capture_ids:
                raise ValueError("Frozen release cannot reuse one capture/check for multiple configured resources")
            if identity not in bindings:
                raise ValueError(f"Frozen release lacks logical resource binding: {source_key}/{label}")

            catalogue.verify_receipt(capture, resource["catalogue"])
            data = store.read_verified(capture)
            if len(data) != capture["byte_size"] or hashlib.sha256(data).hexdigest() != capture["sha256"]:
                raise ValueError("Archived release input failed size/SHA-256 verification")

            payload_by_resource[identity] = data
            verified_capture_ids.add(capture_id)

    if set(payload_by_resource) != set(bindings):
        raise ValueError("Frozen release did not verify every and only logical resource binding")
    return payload_by_resource


def _verified_payloads_by_url(manifest: dict, config: dict, store: EvidenceStore) -> dict[str, bytes]:
    """Compatibility helper for callers that still require an unambiguous URL map.

    Frozen replay itself no longer uses this adapter. If two logical resources share a
    locator but pin different bytes, a URL-only view is intrinsically ambiguous and is
    rejected here rather than collapsing either capture.
    """
    bindings = validate_release_manifest(manifest, config)
    payload_by_resource = _verified_payloads_by_resource(manifest, config, store)
    payload_by_url: dict[str, bytes] = {}
    for identity, data in payload_by_resource.items():
        url = bindings[identity]["capture"]["resource_url"]
        prior = payload_by_url.get(url)
        if prior is not None and prior != data:
            raise ValueError("URL-only compatibility view cannot represent conflicting archived bytes")
        payload_by_url[url] = data
    return payload_by_url


def _write_archived_payload(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(data)


@contextmanager
def archived_downloads(manifest: dict, config: dict, store: EvidenceStore) -> Iterator[None]:
    """Make parser acquisition read only fully verified release-pinned captures.

    Authoritative routing is keyed by ``(source_key, resource_label)`` rather than URL.
    The temporary `_download` adapter is retained only for unambiguous legacy callers;
    it never falls back to the network and rejects locators that represent conflicting
    archived bytes. Every selected capture/check and ContentObject is independently
    read back before either parser-facing adapter becomes available.
    """
    bindings = validate_release_manifest(manifest, config)
    payload_by_resource = _verified_payloads_by_resource(manifest, config, store)
    original_acquire = registry._acquire_source_input
    original_download = registry._download

    compatibility_payload_by_url: dict[str, bytes | None] = {}
    for identity, data in payload_by_resource.items():
        url = bindings[identity]["capture"]["resource_url"]
        if url not in compatibility_payload_by_url:
            compatibility_payload_by_url[url] = data
        elif compatibility_payload_by_url[url] != data:
            compatibility_payload_by_url[url] = None

    def archived_download(url: str, destination: Path) -> str:
        if url not in compatibility_payload_by_url:
            raise RuntimeError(f"Frozen release has no archived capture for URL: {url}")
        data = compatibility_payload_by_url[url]
        if data is None:
            raise RuntimeError(
                "Frozen release URL is ambiguous across logical resources; use logical resource acquisition"
            )
        _write_archived_payload(destination, data)
        return hashlib.sha256(data).hexdigest()

    def archived_acquire_source_input(cfg: dict[str, Any], work_dir: Path) -> tuple[Path | dict[str, Path], str]:
        source_key = cfg["source_key"]
        resources = cfg.get("resources")
        if resources is None:
            identity = _resource_identity(source_key, "primary")
            resource = bindings.get(identity)
            data = payload_by_resource.get(identity)
            if resource is None or data is None:
                raise RuntimeError(f"Frozen release has no archived capture for logical resource: {source_key}/primary")
            capture = resource["capture"]
            suffix = Path(urlparse(cfg["resource_url"]).path).suffix or ".pdf"
            local_path = work_dir / f"{source_key}{suffix}"
            _write_archived_payload(local_path, data)
            return local_path, capture["sha256"]

        if not isinstance(resources, dict) or not resources:
            raise RuntimeError(f"{source_key}: resources must be a non-empty mapping")
        paths: dict[str, Path] = {}
        member_hashes: dict[str, str] = {}
        for label in sorted(resources):
            identity = _resource_identity(source_key, label)
            resource = bindings.get(identity)
            data = payload_by_resource.get(identity)
            if resource is None or data is None:
                raise RuntimeError(f"Frozen release has no archived capture for logical resource: {source_key}/{label}")
            capture = resource["capture"]
            url = resources[label]["resource_url"]
            suffix = Path(urlparse(url).path).suffix or ".bin"
            local_path = work_dir / f"{source_key}-{label}{suffix}"
            _write_archived_payload(local_path, data)
            paths[label] = local_path
            member_hashes[label] = capture["sha256"]

        actual_bundle_sha = registry._bundle_digest(member_hashes)
        expected_bundle_sha = cfg.get("sha256")
        if actual_bundle_sha != expected_bundle_sha:
            raise RuntimeError(
                f"{source_key}: bundle manifest SHA mismatch; expected {expected_bundle_sha}, got {actual_bundle_sha}"
            )
        return paths, actual_bundle_sha

    registry._download = archived_download
    registry._acquire_source_input = archived_acquire_source_input
    try:
        yield
    finally:
        registry._acquire_source_input = original_acquire
        registry._download = original_download


def build_registry_from_release(
    config: dict,
    work_dir: Path,
    release_manifest: dict,
    store: EvidenceStore,
) -> dict:
    """Build registry rows from exact durable inputs with live source access disabled."""
    with archived_downloads(release_manifest, config, store):
        return registry.build_registry(config, work_dir)
