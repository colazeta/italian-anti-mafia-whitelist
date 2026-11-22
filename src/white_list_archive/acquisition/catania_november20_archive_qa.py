"""Read-only source preflight for two archived Catania XLSX candidates labelled 20 November.

The filename date is a discovery hint, not an approved edition/reference date.
Reuse the reviewed provisional physical parser and its fail-closed, aggregate-only
diagnostic, but never modify the 13 November pins or approved 6 November release.
No new writer, network acquisition, SourceEdition or public promotion.
"""
from __future__ import annotations

import json

from white_list_archive.acquisition.catania_november13_archive_qa import (
    _unknown,
    audit_primary_archive,
)

# Both bytes were captured in the existing robot pipeline and have matching
# sha256 / archived_sha256 in robot-state@afa527939c05a18eaa6ed431f5d50f8ca75dbc2a.
# The protected reader must independently retrieve and SHA-verify both originals.
PINS = (
    ("catania-listed", "listed",
     "f5715c1f2ec8a07e4cc1a4a3c76db9c2c5d257241114851d6f0881496c352c6f"),
    ("catania-applicants", "applicant",
     "adaab921db2b42f2f30818635010580d4ec99abd5ecdd3a9e207f2ec8cc1ffd3"),
)
ROBOT_STATE_REVISION = "afa527939c05a18eaa6ed431f5d50f8ca75dbc2a"
SCOPE = "catania_2026_11_20_filename_candidate_source_only"


def audit_archived_pair(store, *, parser=None):
    """Retain the original contract, replacing only the two candidate byte pins."""
    kwargs = {"pins": PINS}
    if parser is not None:
        kwargs["parser"] = parser
    result = audit_primary_archive(store, **kwargs)
    if (
        result.get("checked_pins") != 2
        or result.get("review_only") is not True
        or result.get("capture_catalogue_verified_by_this_probe") is not False
        or result.get("date_attribution_or_edition_approved") is not False
        or result.get("postgresql_writes") != 0
        or result.get("public_promotions") != 0
        or {(item.get("source_key"), item.get("population")) for item
            in result.get("results", [])}
        != {(key, pop) for key, pop, _ in PINS}
    ):
        raise ValueError("Catania archived-pair review boundary mismatch")
    result["scope"] = SCOPE
    result["robot_discovery_revision"] = ROBOT_STATE_REVISION
    return result


def _unavailable():
    return {
        "schema_version": 1,
        "scope": SCOPE,
        "robot_discovery_revision": ROBOT_STATE_REVISION,
        "review_only": True,
        "checked_pins": 2,
        "primary_originals_verified": 0,
        "provisional_extractions": 0,
        "results": [_unknown(key, population) for key, population, _ in PINS],
        "capture_catalogue_verified_by_this_probe": False,
        "date_attribution_or_edition_approved": False,
        "postgresql_writes": 0,
        "public_promotions": 0,
    }


def main():
    from white_list_archive.storage.evidence import EvidenceStore, StoreConfig, client_for
    try:
        config = StoreConfig.from_env()
        report = audit_archived_pair(EvidenceStore(client_for(config), config))
    except Exception:
        # Never emit original values, provider paths or source exception strings.
        report = _unavailable()
    print(json.dumps(report, sort_keys=True))
    # Source-only diagnostic; other transform shards report failures separately.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
