"""Create a reviewed frozen-release manifest only from provider-verified captures.

Selection is deliberately separate from acquisition. The caller supplies an explicit
reviewed selection of already archived capture manifests and catalogue receipts. This
module verifies every selected ContentObject and immutable capture record against the
approved private store before writing a release manifest. No live source URL is fetched.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
from typing import Any

from white_list_archive.publishing.frozen_release import (
    configuration_sha256,
    validate_release_manifest,
)
from white_list_archive.storage.capture_catalogue import CaptureCatalogue
from white_list_archive.storage.evidence import (
    EvidenceStore,
    StoreConfig,
    client_for,
    freeze_capture_manifest,
)

_HEX40 = re.compile(r"^[0-9a-f]{40}$")


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def _selection_sources(selection: dict[str, Any]) -> dict[str, dict[str, Any]]:
    # Processing time and executing code revision are deliberately not operator fields:
    # the selector binds them at execution time after the private inputs are chosen.
    required = {"schema_version", "release_id", "sources"}
    if set(selection) != required or selection.get("schema_version") != 1:
        raise ValueError("Unapproved frozen-release selection envelope")
    sources = selection.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("Selection must contain at least one source")
    by_key: dict[str, dict[str, Any]] = {}
    for item in sources:
        expected = {"source_key", "parser_revision", "projector_revision", "resources"}
        if not isinstance(item, dict) or set(item) != expected:
            raise ValueError("Unapproved frozen-release source selection shape")
        source_key = item.get("source_key")
        if not isinstance(source_key, str) or not source_key.strip():
            raise ValueError("Selection source_key is required")
        if source_key in by_key:
            raise ValueError(f"Duplicate selected source_key: {source_key}")
        for field in ("parser_revision", "projector_revision"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise ValueError(f"{source_key}: {field} is required")
        resources = item.get("resources")
        if not isinstance(resources, list) or not resources:
            raise ValueError(f"{source_key}: at least one selected resource is required")
        by_key[source_key] = item
    return by_key


def select_verified_release(
    config: dict[str, Any],
    selection: dict[str, Any],
    store: EvidenceStore,
    *,
    code_revision: str,
    created_at: str,
    catalogue: CaptureCatalogue | None = None,
) -> dict[str, Any]:
    """Return a frozen release manifest after complete private-provider readback.

    The selection must cover every and only configured publication source. Each resource
    retains its exact capture manifest and catalogue receipt. Bytes and capture provenance
    are independently read back before the returned manifest becomes eligible for review.
    ``code_revision`` and ``created_at`` describe this selector execution, not a source
    publication or capture event, and are kept outside the operator-authored selection.
    """
    if not isinstance(code_revision, str) or _HEX40.fullmatch(code_revision) is None:
        raise ValueError("Frozen release code_revision must be an exact 40-character Git SHA")

    config_sources = config.get("sources")
    if not isinstance(config_sources, list) or not config_sources:
        raise ValueError("Publication configuration must contain sources")
    config_by_key: dict[str, dict[str, Any]] = {}
    for item in config_sources:
        if not isinstance(item, dict) or not isinstance(item.get("source_key"), str):
            raise ValueError("Publication configuration contains an invalid source")
        key = item["source_key"]
        if key in config_by_key:
            raise ValueError(f"Publication configuration contains duplicate source_key: {key}")
        config_by_key[key] = item

    selected = _selection_sources(selection)
    if set(selected) != set(config_by_key):
        missing = sorted(set(config_by_key) - set(selected))
        extra = sorted(set(selected) - set(config_by_key))
        raise ValueError(f"Selection must cover every and only configured source; missing={missing}, extra={extra}")

    manifest_sources: list[dict[str, Any]] = []
    for source_key in sorted(config_by_key):
        cfg = config_by_key[source_key]
        chosen = selected[source_key]
        parser = cfg.get("parser")
        if not isinstance(parser, str) or not parser.strip():
            raise ValueError(f"{source_key}: configured parser is required")
        manifest_sources.append(
            {
                "source_key": source_key,
                "parser": parser,
                "parser_revision": chosen["parser_revision"],
                "projector_revision": chosen["projector_revision"],
                "configuration_sha256": configuration_sha256(cfg),
                "resources": chosen["resources"],
            }
        )

    candidate: dict[str, Any] = {
        "schema_version": 1,
        "release_id": selection["release_id"],
        "created_at": created_at,
        "code_revision": code_revision,
        "source_config_sha256": configuration_sha256(config),
        "sources": manifest_sources,
    }

    # Structural/configuration binding is checked before any provider access. This also
    # validates each capture manifest, including its distinct temporal provenance.
    validate_release_manifest(candidate, config)
    catalogue = catalogue or CaptureCatalogue(store)
    verified_capture_ids: set[str] = set()
    expected_resource_count = 0
    for source in candidate["sources"]:
        for resource in source["resources"]:
            expected_resource_count += 1
            capture = freeze_capture_manifest(resource["capture"])
            receipt = resource["catalogue"]
            # Provenance and original bytes are distinct acceptance conditions. Both must
            # read back successfully for a source to be eligible for a frozen release.
            catalogue.verify_receipt(capture, receipt)
            store.read_verified(capture)
            capture_id = capture.get("capture_id")
            if not isinstance(capture_id, str) or not capture_id:
                raise ValueError("Verified release resource lacks capture_id")
            if capture_id in verified_capture_ids:
                raise ValueError("Frozen release must bind one distinct capture/check per configured resource")
            verified_capture_ids.add(capture_id)

    if len(verified_capture_ids) != expected_resource_count:
        raise ValueError("Frozen release capture verification did not cover every configured resource")
    return candidate


def write_new_release(path: Path, manifest: dict[str, Any]) -> None:
    if path.suffix.lower() != ".json":
        raise ValueError("Frozen release output must be JSON")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, sort_keys=True, indent=2)
        handle.write("\n")


def _head_revision() -> str:
    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        text=True,
        stderr=subprocess.DEVNULL,
    ).strip()
    if _HEX40.fullmatch(revision) is None:
        raise ValueError("Unable to bind frozen release to an exact Git HEAD revision")
    return revision


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-config", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True, help="Private reviewed capture selection JSON")
    parser.add_argument("--output", type=Path, required=True, help="New frozen release manifest to review")
    args = parser.parse_args()

    config = _load_json(args.source_config)
    selection = _load_json(args.selection)
    store_config = StoreConfig.from_env()
    store = EvidenceStore(client_for(store_config), store_config)
    manifest = select_verified_release(
        config,
        selection,
        store,
        code_revision=_head_revision(),
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    write_new_release(args.output, manifest)
    print(json.dumps({
        "release_id": manifest["release_id"],
        "code_revision": manifest["code_revision"],
        "source_count": len(manifest["sources"]),
        "resource_count": sum(len(item["resources"]) for item in manifest["sources"]),
        "status": "verified_private_inputs_selected_for_review",
    }, sort_keys=True))


if __name__ == "__main__":
    main()
