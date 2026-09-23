"""Select exact archived inputs for independent recovery of a frozen release."""
from __future__ import annotations

from typing import Any

from white_list_archive.publishing.frozen_release import validate_release_manifest
from white_list_archive.storage.evidence import freeze_capture_manifest


def selected_release_captures(manifest: dict[str, Any], config: dict[str, Any]) -> list[dict[str, Any]]:
    """Return every capture/check selected by one validated frozen release.

    Capture identity is deliberately retained even when several captures resolve to the
    same content-addressed object.  The returned rows are an independent-recovery input
    plan, not a publication projection: no live URL is dereferenced and no administrative
    edition identity is inferred.
    """
    validate_release_manifest(manifest, config)

    selected: list[dict[str, Any]] = []
    seen_capture_ids: set[str] = set()
    content_shapes: dict[str, tuple[int, str | None]] = {}

    for source in manifest["sources"]:
        source_key = source["source_key"]
        for resource in source["resources"]:
            label = resource["label"]
            capture = freeze_capture_manifest(resource["capture"])
            capture_id = capture.get("capture_id")
            if not isinstance(capture_id, str) or not capture_id:
                raise ValueError(f"{source_key}/{label}: frozen recovery input lacks capture identity")
            if capture_id in seen_capture_ids:
                raise ValueError("Frozen release cannot reuse one capture/check for multiple resources")
            seen_capture_ids.add(capture_id)

            sha256 = capture["sha256"]
            shape = (capture["byte_size"], capture.get("mime_type"))
            prior = content_shapes.get(sha256)
            if prior is not None and prior != shape:
                raise ValueError("One ContentObject identity cannot have conflicting frozen metadata")
            content_shapes[sha256] = shape

            selected.append(
                {
                    "source_key": source_key,
                    "label": label,
                    "capture": capture,
                    "catalogue": dict(resource["catalogue"]),
                }
            )
    return selected


def distinct_content_object_inputs(selected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return one representative input per byte-distinct ContentObject.

    Every capture/check must be verified separately before this deduplication is used.
    Recovery storage itself is content-addressed, so repeated unchanged bytes need one
    backup object while their distinct capture identities remain part of the release.
    """
    representatives: dict[str, dict[str, Any]] = {}
    for item in selected:
        capture = item["capture"]
        sha256 = capture["sha256"]
        prior = representatives.get(sha256)
        if prior is None:
            representatives[sha256] = item
            continue
        prior_capture = prior["capture"]
        if (
            prior_capture["byte_size"] != capture["byte_size"]
            or prior_capture.get("mime_type") != capture.get("mime_type")
        ):
            raise ValueError("One ContentObject identity cannot have conflicting frozen metadata")
    return list(representatives.values())
