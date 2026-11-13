"""Bounded, read-only matching of historical pins to immutable capture provenance.

Primary R2 byte availability alone does not identify an acquisition. Search only
the pre-existing, source-specific private CaptureCatalogue prefixes for already
recorded capture IDs. A positive result requires the complete immutable manifest,
canonical catalogue receipt and independently verified exact original bytes.
A negative or incomplete listing is *never* evidence of absence or loss.
No source value, provider key, URL, capture UUID or exception text is logged.
"""
from __future__ import annotations

import json
from uuid import UUID
from typing import Any

from white_list_archive.acquisition.historical_object_audit import PINS
from white_list_archive.storage.capture_catalogue import CaptureCatalogue, capture_record_key
from white_list_archive.storage.catalogue_recovery import load_catalogued_capture

TARGETS = (
    ("lodi-listed", PINS[0][0], PINS[0][1]),
    ("lodi-applicants", PINS[1][0], PINS[1][1]),
    ("milano-combined", PINS[2][0], PINS[2][1]),
    ("milano-combined", PINS[3][0], PINS[3][1]),
)
MAX_KEYS_PER_SOURCE = 64


def _valid_capture_key(key: Any, *, source_key: str) -> str | None:
    prefix = f"captures/v1/{source_key}/"
    if not isinstance(key, str) or not key.startswith(prefix) or not key.endswith(".json"):
        return None
    capture_id = key[len(prefix):-5]
    try:
        if str(UUID(capture_id)) != capture_id:
            return None
        if capture_record_key({"source_key": source_key, "capture_id": capture_id}) != key:
            return None
    except (ValueError, TypeError):
        return None
    return capture_id


def audit_historical_catalogue(
    store: Any, *, targets: tuple = TARGETS, max_keys: int = MAX_KEYS_PER_SOURCE,
) -> dict[str, Any]:
    """Return bounded positive attestations; uncertainty survives all failed reads."""
    if type(max_keys) is not int or not 1 <= max_keys <= MAX_KEYS_PER_SOURCE:
        raise ValueError("Catalogue metadata lookup exceeds reviewed bound")
    if (not isinstance(targets, tuple) or not targets or
            any(not isinstance(row, tuple) or len(row) != 3 for row in targets) or
            len({(s, scope) for s, scope, _ in targets}) != len(targets)):
        raise ValueError("Invalid closed historical capture targets")
    groups: dict[str, dict[str, str]] = {}
    for source_key, scope, sha in targets:
        if not isinstance(source_key, str) or not isinstance(scope, str):
            raise ValueError("Invalid historical target")
        if not isinstance(sha, str) or len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
            raise ValueError("Invalid frozen source digest")
        if scope in groups.setdefault(source_key, {}):
            raise ValueError("Duplicate historical scope")
        groups[source_key][scope] = sha

    # Store only counts. The capture IDs are retained in-memory for deduplication.
    matches = {scope: set() for _, scope, _ in targets}
    listing_complete = {key: False for key in groups}
    catalogue = CaptureCatalogue(store)
    for source_key, source_targets in groups.items():
        try:
            prefix = f"captures/v1/{source_key}/"
            response = store.client.list_objects_v2(
                Bucket=store.config.bucket, Prefix=prefix, MaxKeys=max_keys,
            )
            entries = response.get("Contents", [])
            if not isinstance(entries, list) or len(entries) > max_keys:
                continue
            listing_complete[source_key] = response.get("IsTruncated") is False
            for item in entries:
                if not isinstance(item, dict):
                    listing_complete[source_key] = False
                    continue
                capture_id = _valid_capture_key(item.get("Key"), source_key=source_key)
                if capture_id is None:
                    listing_complete[source_key] = False
                    continue
                try:
                    _, candidate = catalogue._read_record(item["Key"])
                    digest = candidate.get("sha256")
                    if digest not in source_targets.values():
                        continue
                    manifest, _ = load_catalogued_capture(
                        catalogue, source_key=source_key, capture_id=capture_id,
                    )
                    if manifest["sha256"] != digest or manifest["source_key"] != source_key:
                        continue
                    # A catalogue record without the actual matching original is
                    # still not a verified historical acquisition.
                    store.read_verified(manifest)
                    for scope, expected_sha in source_targets.items():
                        if digest == expected_sha:
                            matches[scope].add(capture_id)
                except Exception:
                    # Provider exceptions or malformed legacy provenance can leak
                    # source coordinates; they remain unverified without logging.
                    continue
        except Exception:
            # List permission/provider errors never establish missing originals.
            listing_complete[source_key] = False

    results = [
        {
            "scope": scope,
            "status": "verified_immutable_capture_provenance" if matches[scope] else "unknown",
            "verified_capture_checks": len(matches[scope]),
            "bounded_catalogue_listing_complete": listing_complete[source_key],
        }
        for source_key, scope, _ in targets
    ]
    return {
        "schema_version": 1,
        "checked_historical_pins": len(results),
        "pins_with_verified_capture_provenance": sum(bool(matches[scope]) for _, scope, _ in targets),
        "results": results,
        "capture_or_database_writes": 0,
        "administrative_editions_approved": 0,
        "independent_restore_verified": False,
        "public_promotions": 0,
    }


def main() -> int:
    from white_list_archive.storage.evidence import EvidenceStore, StoreConfig, client_for
    try:
        config = StoreConfig.from_env()
        store = EvidenceStore(client_for(config), config)
        result = audit_historical_catalogue(store)
    except Exception:
        result = {
            "schema_version": 1, "checked_historical_pins": len(TARGETS),
            "pins_with_verified_capture_provenance": 0,
            "results": [
                {
                    "scope": scope, "status": "unknown",
                    "verified_capture_checks": 0,
                    "bounded_catalogue_listing_complete": False,
                }
                for _, scope, _ in TARGETS
            ],
            "capture_or_database_writes": 0,
            "administrative_editions_approved": 0,
            "independent_restore_verified": False,
            "public_promotions": 0,
        }
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0  # Read-only diagnostics must not block independent source processing.


if __name__ == "__main__":
    raise SystemExit(main())
