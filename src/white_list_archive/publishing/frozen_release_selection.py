"""Select an exact frozen-release candidate from governed temporal captures.

Selection is deliberately SourceSeries/resource based rather than URL-as-identity.
For raw-approved inputs and bundle members, bytes must match the reviewed digest.
For semantic-approved single resources, selection may use a newer raw wrapper, but the
normal archived replay must still pass the configured semantic digest before the
candidate can be accepted.

The selector chooses the latest *verified catalogue capture* among eligible captures.
Equal-time captures with identical bytes remain separate checks; a stable capture-id
tie-break chooses one without collapsing history. Equal-time distinct payloads are
ambiguous and fail selection rather than silently imposing an order.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from datetime import datetime
from typing import Any

from white_list_archive.publishing.frozen_release import (
    PUBLIC_PROJECTOR_REVISION,
    configuration_sha256,
    validate_release_manifest,
)
from white_list_archive.storage.capture_catalogue import CaptureCatalogue
from white_list_archive.storage.evidence import EvidenceStore, freeze_capture_manifest

PREFLIGHT_PARSER_REVISION = "selection-preflight"


class FrozenReleaseSelectionError(ValueError):
    """Fail-closed selection or provider-verification error."""


def _aware_capture_time(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise FrozenReleaseSelectionError("Candidate capture has no acquisition time")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise FrozenReleaseSelectionError("Candidate capture has invalid acquisition time") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise FrozenReleaseSelectionError("Candidate capture acquisition time requires timezone")
    return parsed


def _resource_specs(cfg: dict[str, Any]) -> dict[str, tuple[str, str | None]]:
    resources = cfg.get("resources")
    if resources is not None:
        if not isinstance(resources, dict) or not resources:
            raise FrozenReleaseSelectionError(f"{cfg.get('source_key')}: invalid resource bundle")
        return {
            label: (item["resource_url"], item.get("sha256"))
            for label, item in resources.items()
        }

    mode = str(cfg.get("approval_mode") or "raw_sha256")
    if mode == "raw_sha256":
        return {"primary": (cfg["resource_url"], cfg.get("sha256"))}
    if mode == "semantic_sha256":
        # Wrapper bytes may legitimately change while parsed semantics remain the
        # reviewed edition. The archive-only replay is the acceptance gate.
        return {"primary": (cfg["resource_url"], None)}
    raise FrozenReleaseSelectionError(
        f"{cfg.get('source_key')}: unsupported approval mode {mode!r}"
    )


def _normalise_recovered(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    identities: set[tuple[str, str]] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise FrozenReleaseSelectionError("Recovered capture row must be a mapping")
        capture = freeze_capture_manifest(row.get("capture"))
        catalogue = row.get("catalogue")
        if not isinstance(catalogue, dict):
            raise FrozenReleaseSelectionError("Recovered capture lacks catalogue provenance")
        source_key = capture.get("source_key")
        capture_id = capture.get("capture_id")
        if not isinstance(source_key, str) or not source_key:
            raise FrozenReleaseSelectionError("Recovered capture lacks SourceSeries identity")
        if not isinstance(capture_id, str) or not capture_id:
            raise FrozenReleaseSelectionError("Recovered capture lacks capture/check identity")
        identity = (source_key, capture_id)
        if identity in identities:
            raise FrozenReleaseSelectionError("Recovered capture denominator contains a duplicate identity")
        identities.add(identity)
        by_source[source_key].append({"capture": capture, "catalogue": catalogue})
    return by_source


def _select_latest(
    candidates: list[dict[str, Any]],
    *,
    source_key: str,
    label: str,
) -> dict[str, Any]:
    timed = [(_aware_capture_time(row["capture"]["captured_at"]), row) for row in candidates]
    latest_time = max(item[0] for item in timed)
    latest = [row for when, row in timed if when == latest_time]
    if len(latest) == 1:
        return latest[0]

    digests = {(row["capture"]["sha256"], row["capture"]["byte_size"]) for row in latest}
    if len(digests) != 1:
        raise FrozenReleaseSelectionError(
            f"{source_key}/{label}: equal-time distinct payloads require explicit selection"
        )
    return min(latest, key=lambda row: row["capture"]["capture_id"])


def plan_frozen_release_candidate(
    config: dict[str, Any],
    recovered_captures: list[dict[str, Any]],
    *,
    release_id: str,
    created_at: str,
    code_revision: str,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Plan one exact candidate, returning safe gap metadata when coverage is incomplete.

    This function does not list storage and does not infer missing bytes. Its denominator
    is the reviewed publication configuration and the explicit governed captures supplied
    by the caller.
    """
    if not isinstance(config, dict) or not isinstance(config.get("sources"), list):
        raise FrozenReleaseSelectionError("Publication configuration lacks sources")
    if not all(isinstance(value, str) and value.strip() for value in (release_id, created_at, code_revision)):
        raise FrozenReleaseSelectionError("Release id, created_at and code revision are required")

    by_source = _normalise_recovered(recovered_captures)
    source_keys = [cfg.get("source_key") for cfg in config["sources"]]
    if any(not isinstance(key, str) or not key for key in source_keys):
        raise FrozenReleaseSelectionError("Publication configuration has invalid source identity")
    if len(set(source_keys)) != len(source_keys):
        raise FrozenReleaseSelectionError("Publication configuration contains duplicate source_key")

    frozen_sources: list[dict[str, Any]] = []
    gaps: list[dict[str, str]] = []
    selected_content: set[str] = set()
    unknown_capture_reference_dates = 0
    selected_resources = 0

    for cfg in config["sources"]:
        source_key = cfg["source_key"]
        resources: list[dict[str, Any]] = []
        for label, (expected_url, required_sha) in _resource_specs(cfg).items():
            # SourceSeries + logical resource is the identity. The configured URL is
            # only the currently reviewed locator; older captures from a prior locator
            # remain eligible when immutable provenance/digest constraints still match.
            source_candidates = by_source.get(source_key, [])
            configured_reference = cfg.get("reference_date")
            compatible = []
            known_conflict = False
            for row in source_candidates:
                capture_reference = row["capture"].get("reference_date")
                if (
                    capture_reference is not None
                    and configured_reference is not None
                    and capture_reference != configured_reference
                ):
                    known_conflict = True
                    continue
                if required_sha is not None and row["capture"]["sha256"] != required_sha:
                    continue
                compatible.append(row)

            if not compatible:
                reason = "no_eligible_capture"
                if known_conflict and source_candidates:
                    reason = "known_reference_date_conflict"
                elif required_sha is not None and source_candidates:
                    reason = "approved_raw_digest_not_captured"
                elif not source_candidates:
                    reason = "no_catalogued_capture_for_source"
                gaps.append({"source_key": source_key, "label": label, "reason": reason})
                continue

            try:
                selected = _select_latest(compatible, source_key=source_key, label=label)
            except FrozenReleaseSelectionError as exc:
                gaps.append({"source_key": source_key, "label": label, "reason": str(exc).split(": ", 1)[-1]})
                continue

            capture = selected["capture"]
            if capture.get("reference_date") is None:
                unknown_capture_reference_dates += 1
            selected_content.add(capture["sha256"])
            selected_resources += 1
            resources.append(
                {
                    "label": label,
                    "reviewed_resource_url": expected_url,
                    "source_reference_date": cfg.get("reference_date"),
                    "capture": capture,
                    "catalogue": selected["catalogue"],
                }
            )

        expected_count = len(_resource_specs(cfg))
        if len(resources) != expected_count:
            continue
        frozen_sources.append(
            {
                "source_key": source_key,
                "parser": cfg["parser"],
                "parser_revision": PREFLIGHT_PARSER_REVISION,
                "projector_revision": PUBLIC_PROJECTOR_REVISION,
                "configuration_sha256": configuration_sha256(cfg),
                "resources": resources,
            }
        )

    report = {
        "configured_sources": len(config["sources"]),
        "configured_resources": sum(len(_resource_specs(cfg)) for cfg in config["sources"]),
        "selected_sources": len(frozen_sources),
        "selected_resources": selected_resources,
        "selected_distinct_content_objects": len(selected_content),
        "unknown_capture_reference_dates": unknown_capture_reference_dates,
        "selection_complete": not gaps and len(frozen_sources) == len(config["sources"]),
        "gaps": sorted(gaps, key=lambda row: (row["source_key"], row["label"], row["reason"])),
    }
    if not report["selection_complete"]:
        return None, report

    manifest = {
        "schema_version": 2,
        "release_id": release_id,
        "created_at": created_at,
        "code_revision": code_revision,
        "source_config_sha256": configuration_sha256(config),
        "sources": frozen_sources,
    }
    validate_release_manifest(manifest, config)
    return manifest, report


def verify_frozen_release_candidate(
    manifest: dict[str, Any],
    config: dict[str, Any],
    store: EvidenceStore,
) -> dict[str, int]:
    """Read back every selected capture record and ContentObject before replay."""
    validate_release_manifest(manifest, config)
    catalogue = CaptureCatalogue(store)
    captures = 0
    content: set[str] = set()
    for source in manifest["sources"]:
        for resource in source["resources"]:
            capture = freeze_capture_manifest(resource["capture"])
            try:
                catalogue.verify_receipt(capture, resource["catalogue"])
                body = store.read_verified(capture)
            except Exception:
                raise FrozenReleaseSelectionError(
                    f"{source['source_key']}/{resource['label']}: governed archive readback failed"
                ) from None
            if len(body) != capture["byte_size"]:
                raise FrozenReleaseSelectionError(
                    f"{source['source_key']}/{resource['label']}: governed archive size mismatch"
                )
            captures += 1
            content.add(capture["sha256"])
    return {
        "verified_selected_captures": captures,
        "verified_selected_content_objects": len(content),
    }


def finalise_parser_revisions(manifest: dict[str, Any], built_registry: dict[str, Any]) -> dict[str, Any]:
    """Replace preflight parser placeholders with revisions actually produced by replay."""
    result = deepcopy(manifest)
    bindings = {item["source_key"]: item for item in result.get("sources", [])}
    if len(bindings) != len(result.get("sources", [])):
        raise FrozenReleaseSelectionError("Frozen release contains duplicate source bindings")

    observed: dict[str, str] = {}
    for record in built_registry.get("records", []):
        source_key = record.get("source_key")
        parser_name = record.get("parser_name")
        parser_version = record.get("parser_version")
        if not isinstance(source_key, str) or source_key not in bindings:
            raise FrozenReleaseSelectionError("Replay produced an unpinned source")
        if not isinstance(parser_name, str) or not parser_name.strip() or parser_version is None:
            raise FrozenReleaseSelectionError(f"{source_key}: replay lacks parser revision metadata")
        revision = f"{parser_name}@{parser_version}"
        prior = observed.get(source_key)
        if prior is not None and prior != revision:
            raise FrozenReleaseSelectionError(f"{source_key}: replay produced inconsistent parser revisions")
        observed[source_key] = revision

    if set(observed) != set(bindings):
        missing = sorted(set(bindings) - set(observed))
        raise FrozenReleaseSelectionError(
            "Replay did not produce every selected source: " + ", ".join(missing)
        )
    for source_key, revision in observed.items():
        bindings[source_key]["parser_revision"] = revision
    return result
