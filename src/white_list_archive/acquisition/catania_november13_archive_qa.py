"""Source-only, read-only qualification of the two frozen Catania 13 November XLSX pins.

Runs inside the existing protected transform worker. An original retrieved from
primary storage is not a verified capture catalogue, approved SourceEdition or
public release. No URLs, individual observations, exception text or private
storage coordinates are included in the aggregate report.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import tempfile
from typing import Any

from white_list_archive.parsers.catania_candidate import PARSERS, parse_candidate_xlsx

# Source identities recorded in the reviewed operational issue #267.
# In particular, these are NOT the approved Catania 6 November originals.
PINS = (
    ("catania-listed", "listed",
     "90bbbc4af8542ee9c2f15368a4adc1c0916f6277867702fbb72f4d1d23831a11"),
    ("catania-applicants", "applicant",
     "65c630bc4b12741f0a3848a73efb104a61ef8fe7cf41d0c65f69d44c8f900033"),
)
MAX_SOURCE_BYTES = 10_000_000
_ALLOWED_FLAGS = frozenset({
    "sector_anomalies", "unrecognised_identifiers", "unparsed_source_dates",
    "formula_without_cached_date", "unclassified_status_notes",
    "unclassified_source_outcomes",
})


def _candidate_config(source_key: str, population: str, digest: str) -> dict[str, Any]:
    # Deliberately no document URL and no edition date. The parser output is
    # discarded after aggregation, never attributed to the approved series.
    return {
        "source_key": source_key,
        "authority_key": "catania",
        "authority_name": "Prefettura di Catania",
        "register_key": "catania-ordinary",
        "register_name": "White List ordinaria",
        "population_scope": population,
        "reference_date": "",
        "parser": PARSERS[population],
        "source_page_url": "",
        "resource_url": "",
        "sha256": digest,
    }


def _unknown(source_key: str, population: str) -> dict[str, Any]:
    return {
        "source_key": source_key,
        "population": population,
        "primary_bytes": "unknown",
        "candidate_schema": "not_tested",
        "source_rows_for_review": None,
        "source_status_counts": {},
        "candidate_quality_counts": {},
    }


def audit_primary_archive(store: Any, *, pins=PINS, parser=parse_candidate_xlsx) -> dict[str, Any]:
    """Read only exact already-pinned bytes; failures cannot fabricate a date."""
    if (len(pins) != 2
            or {(key, pop) for key, pop, _ in pins}
            != {("catania-listed", "listed"), ("catania-applicants", "applicant")}
            or any(not isinstance(sha, str) or len(sha) != 64
                   or any(ch not in "0123456789abcdef" for ch in sha)
                   for _, _, sha in pins)
            or len({sha for _, _, sha in pins}) != 2):
        raise ValueError("Catania 13 November source-pin contract must remain closed")
    results = []
    for key, population, sha in pins:
        row = _unknown(key, population)
        try:
            raw = store.read_digest_verified(sha)
            if type(raw) is not bytes or not (0 < len(raw) <= MAX_SOURCE_BYTES):
                raise ValueError("Unverified original length")
            if hashlib.sha256(raw).hexdigest() != sha:
                raise ValueError("Original source digest mismatch")
        except Exception:
            # Unknown covers missing, damaged, inaccessible and transport errors;
            # never disclose provider exceptions or equate a failed read with loss.
            results.append(row)
            continue
        row["primary_bytes"] = "sha256_verified"
        try:
            with tempfile.TemporaryDirectory(prefix="catania-private-qa-") as directory:
                path = Path(directory) / "candidate.xlsx"
                path.write_bytes(raw)
                batch = parser(path, _candidate_config(key, population, sha))
            if not isinstance(batch.records, list) or not batch.records:
                raise ValueError("No candidate records")
            if (batch.diagnostics.get("publication_approved") is not False
                    or batch.diagnostics.get("source_date_assigned") is not False
                    or batch.diagnostics.get("source_rows_represented") != len(batch.records)):
                raise ValueError("Provisional parser review contract mismatch")
            flags = batch.diagnostics.get("candidate_quality_flags")
            counts = batch.diagnostics.get("counts")
            if (not isinstance(flags, list) or not set(flags) <= _ALLOWED_FLAGS
                    or not isinstance(counts, dict)
                    or any(name not in _ALLOWED_FLAGS or type(value) is not int
                           or value < 0 for name, value in counts.items())):
                raise ValueError("Unexpected candidate diagnostics")
            status_counts = Counter()
            for record in batch.records:
                status = record.get("source_status")
                if status not in {
                    "listed", "pending", "renewal_update_in_progress",
                    "other_or_unknown",
                }:
                    raise ValueError("Unknown source-status taxonomy")
                if record.get("reference_date"):
                    raise ValueError("Candidate unexpectedly assigned source date")
                status_counts[status] += 1
            row["candidate_schema"] = "provisional_extraction_for_review"
            row["source_rows_for_review"] = len(batch.records)
            row["source_status_counts"] = dict(sorted(status_counts.items()))
            row["candidate_quality_counts"] = {
                name: counts.get(name, 0) for name in sorted(_ALLOWED_FLAGS)
            }
        except Exception:
            # Positive primary-byte proof survives failed layout/parser QA.
            # A quarantined format is not retroactively erased or approved.
            row["candidate_schema"] = "layout_or_parser_review_required"
        results.append(row)
    return {
        "schema_version": 1,
        "scope": "catania_2026_11_13_source_candidates",
        "review_only": True,
        "checked_pins": 2,
        "primary_originals_verified": sum(
            r["primary_bytes"] == "sha256_verified" for r in results),
        "provisional_extractions": sum(
            r["candidate_schema"] == "provisional_extraction_for_review"
            for r in results),
        "results": results,
        "capture_catalogue_verified_by_this_probe": False,
        "date_attribution_or_edition_approved": False,
        "postgresql_writes": 0,
        "public_promotions": 0,
    }


def main() -> int:
    from white_list_archive.storage.evidence import EvidenceStore, StoreConfig, client_for
    try:
        config = StoreConfig.from_env()
        result = audit_primary_archive(EvidenceStore(client_for(config), config))
    except Exception:
        # Infrastructure failure is unknown, not evidence of a missing file.
        result = {
            "schema_version": 1,
            "scope": "catania_2026_11_13_source_candidates",
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
    print(json.dumps(result, sort_keys=True))
    # This is diagnostic only. Other protected worker lanes remain independent.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
