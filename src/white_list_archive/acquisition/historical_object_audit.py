"""Read-only verification of four public, historically pinned source digests.

This is a primary R2 *byte availability* check. It neither recovers catalogue
provenance nor establishes an independent backup or a reviewed edition. No URLs,
private object keys, source rows, names or exception messages leave the runner.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

# Historical identities already recorded in reviewed parser tests and PR #162.
# A later live URL response must never replace any of these frozen digests.
PINS = (
    ("lodi-listed-september", "0cb78eec4e7c902a9ec9e6fa3b64ef52c276a2de32cd86cba3e59cf68775d945"),
    ("lodi-applicants-september", "c200e90a0410ba23fddee9d3ad0a5ac1532fec8dedfe0ec983eb2e94d0601a16"),
    ("milano-combined-22-september", "09cdc0bf9a9cb5ee4df661d25972b9d1730f5a2158c052a75e42802960c44f46"),
    ("milano-combined-27-september", "e656d98e49b0e5838cc8841d78ab6537b0be6ae18cc96252ba1e22993329e9cc"),
)

MAX_EXPECTED_SOURCE_BYTES = 8_000_000


def inspect_primary_store(store: Any, pins=PINS) -> dict[str, Any]:
    """Hash the exact stored bytes; absence, transport failure and corruption stay unknown."""
    if len(pins) != 4 or len({name for name, _ in pins}) != 4:
        raise ValueError("Exactly four distinct reviewed historical source pins are required")
    if len({sha for _, sha in pins}) != 4:
        raise ValueError("Historical source pins must be byte-distinct")
    outcomes = []
    for name, sha in pins:
        if not isinstance(name, str) or not isinstance(sha, str) or len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
            raise ValueError("Invalid reviewed historical source identity")
        verified = False
        try:
            raw = store.read_digest_verified(sha)
            verified = (
                type(raw) is bytes and 0 < len(raw) <= MAX_EXPECTED_SOURCE_BYTES
                and hashlib.sha256(raw).hexdigest() == sha
            )
        except Exception:
            # A provider exception may carry private endpoint/object coordinates.
            # Missing/corrupt/unavailable are *not* distinguished by this probe.
            verified = False
        outcomes.append({"scope": name, "primary_bytes_verified": verified,
                         "verification": "verified_primary_r2" if verified else "unknown"})
    total = sum(int(row["primary_bytes_verified"]) for row in outcomes)
    return {
        "schema_version": 1,
        "checked_source_versions": len(outcomes),
        "verified_primary_r2": total,
        "unknown_or_unverified": len(outcomes) - total,
        "results": outcomes,
        "catalogue_provenance_verified": False,
        "postgresql_persistence_verified_by_this_check": False,
        "independent_backup_or_restore_verified": False,
        "parser_or_edition_approved": False,
        "source_captures_created": 0,
        "database_writes": 0,
        "public_promotions": 0,
    }


def main() -> int:
    # Executed only within an existing protected evidence-archive worker.
    from white_list_archive.storage.evidence import EvidenceStore, StoreConfig, client_for
    try:
        config = StoreConfig.from_env()
        store = EvidenceStore(client_for(config), config)
        safe = inspect_primary_store(store)
    except Exception:
        # An unavailable credential, provider or read-only probe must not block
        # the independent normal transformation lane or leak provider details.
        safe = {
            "schema_version": 1, "checked_source_versions": 4,
            "verified_primary_r2": 0, "unknown_or_unverified": 4,
            "results": [{"scope": name, "primary_bytes_verified": False, "verification": "unknown"}
                        for name, _ in PINS],
            "catalogue_provenance_verified": False,
            "postgresql_persistence_verified_by_this_check": False,
            "independent_backup_or_restore_verified": False,
            "parser_or_edition_approved": False,
            "source_captures_created": 0, "database_writes": 0, "public_promotions": 0,
        }
    print(json.dumps(safe, sort_keys=True))
    # This is a non-mutating diagnostic, not a new parser acceptance gate.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
