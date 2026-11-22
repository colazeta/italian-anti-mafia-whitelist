"""Stage only the 10 unresolved Catania 20 November listed rows in the existing private R2 review store.

An immutable private review packet does not approve any row, document date,
legal effect or public edition. Only aggregate proof is printed.
"""
from __future__ import annotations

import json

from white_list_archive.acquisition.catania_november20_archive_qa import PINS
from white_list_archive.acquisition.catania_tail_private_review import (
    NOV20_SCOPE,
    prepare_and_verify_repeat,
)

EXPECTED_ANCHORED = 1901
EXPECTED_UNCLASSIFIED = 10


def stage_immutable_review(store) -> dict:
    """Same exact already-preserved source, packet bytes, and key on every retry."""
    return prepare_and_verify_repeat(
        store, source_sha=PINS[0][2], expected_full=EXPECTED_ANCHORED,
        expected_ambiguous=EXPECTED_UNCLASSIFIED, review_scope=NOV20_SCOPE,
    )


def main() -> int:
    from white_list_archive.storage.evidence import EvidenceStore, StoreConfig, client_for
    try:
        cfg = StoreConfig.from_env()
        report = stage_immutable_review(EvidenceStore(client_for(cfg), cfg))
    except Exception:
        # Workbook rows, coordinates, raw identifier values and storage paths
        # must never appear in workflow logs, even on a failed provider read.
        print(json.dumps({
            "scope": NOV20_SCOPE,
            "private_review_packet_verified": False,
            "state": "blocked_review",
            "source_edition_approved": False,
            "public_promotions": 0,
        }, sort_keys=True))
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
