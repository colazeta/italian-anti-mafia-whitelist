"""Read-only immutable capture provenance audit for the two pinned Catania 13 Nov originals.

A positive primary-R2 SHA check (and a sealed review packet) does not
establish acquisition/check provenance. The existing bounded, private
catalogue verifier is reused unchanged; only closed aggregate counters reach
Actions logs. Unknown remains unknown and does not block independent lanes.
"""
from __future__ import annotations

import json
from typing import Any

from white_list_archive.acquisition.catania_november13_archive_qa import PINS
from white_list_archive.storage.historical_capture_provenance_audit import (
    audit_historical_catalogue,
)

SCOPE = "catania_2026_11_13_exact_capture_provenance"
TARGETS = tuple(
    (series, f"{series}-13-november-2026", digest)
    for series, _population, digest in PINS
)


def audit_catania_capture_provenance(store: Any) -> dict:
    """Verify only pre-existing capture manifests and original bytes.

    This does not create a capture, register a ContentObject, approve an
    edition or enable publishing. The underlying bounded catalogue reader
    verifies manifest, receipt and exact original SHA/size independently.
    """
    report = audit_historical_catalogue(store, targets=TARGETS)
    return {"scope": SCOPE, **report}


def _unavailable_report() -> dict:
    """Closed, non-sensitive unknown verdict when the provider is unavailable."""
    return {
        "scope": SCOPE,
        "schema_version": 1,
        "checked_historical_pins": len(TARGETS),
        "pins_with_verified_capture_provenance": 0,
        "explicit_writer_provenance_ready_checks": 0,
        "missing_writer_provenance_checks": 0,
        "postgresql_writer_or_commit_verified_here": False,
        "results": [
            {
                "scope": scope,
                "status": "unknown",
                "verified_capture_checks": 0,
                "explicit_writer_provenance_ready_checks": 0,
                "missing_writer_provenance_checks": 0,
                "bounded_catalogue_listing_complete": False,
            }
            for _series, scope, _digest in TARGETS
        ],
        "capture_or_database_writes": 0,
        "administrative_editions_approved": 0,
        "independent_restore_verified": False,
        "public_promotions": 0,
    }


def main() -> int:
    from white_list_archive.storage.evidence import EvidenceStore, StoreConfig, client_for
    try:
        config = StoreConfig.from_env()
        result = audit_catania_capture_provenance(
            EvidenceStore(client_for(config), config)
        )
    except Exception:
        # Provider exceptions could carry sensitive paths or endpoints.
        result = _unavailable_report()
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0  # This diagnostic must not block other source processing.


if __name__ == "__main__":
    raise SystemExit(main())
