"""Read-only QA of the exact Ascoli comprehensive listed PDF already archived.

A primary-store byte read, strict physical parser pass and an authentic
CaptureCatalogue check are three independent gates. None can create an
administrative SourceEdition, relabel the registered series or authorise release.
Only closed, aggregate counters may cross the protected Actions log boundary.
"""
from __future__ import annotations

from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Mapping

from white_list_archive.acquisition.approved_source_alias_audit import (
    APPROVED_SHA256, APPROVED_DATE, EXPECTED_ROWS, LEGACY_KEY, REGISTERED_KEY,
)
from white_list_archive.parsers.ascoli_piceno_labels import parse_ascoli_piceno_listed
from white_list_archive.storage.historical_capture_provenance_audit import (
    audit_historical_catalogue,
)

SCOPE = "ascoli_comprehensive_2026_08_11_review_only"
EXPECTED_BYTES = 474484
TARGETS = ((REGISTERED_KEY, SCOPE, APPROVED_SHA256),)
EXPECTED_STATUSES = {"listed": 448, "renewal_update_in_progress": 96}


def _selected(source_config: Mapping[str, Any], inventory: list[dict]) -> dict | None:
    sources = source_config.get("sources")
    if not isinstance(sources, list):
        return None
    matches = [row for row in sources
               if isinstance(row, dict) and row.get("source_key") == LEGACY_KEY]
    if len(matches) != 1:
        return None
    source = matches[0]
    expected = {
        "source_key": LEGACY_KEY,
        "authority_key": "ascoli-piceno",
        "register_key": "ascoli-piceno-ordinary",
        "population_scope": "listed",
        "parser": "ascoli_piceno_listed",
        "reference_date": APPROVED_DATE,
        "sha256": APPROVED_SHA256,
        "expected_source_rows": EXPECTED_ROWS,
    }
    if any(source.get(k) != v for k, v in expected.items()):
        return None
    registered = [row for row in inventory if row.get("source_series_key") == REGISTERED_KEY]
    if len(registered) != 1:
        return None
    expected_inventory = {
        "authority_key": "ascoli-piceno",
        "regime_code": "WL-REGIME-L190-2012",
        "population_scope": "listed",
        "sector_scope": "all",
    }
    if any(registered[0].get(k) != v for k, v in expected_inventory.items()):
        return None
    return source


def _strict_batch_qa(batch: Any) -> bool:
    """Reject record/field, sector, date or denominator drift without logging rows."""
    try:
        records = batch.records
        diagnostics = batch.diagnostics
        if len(records) != EXPECTED_ROWS or diagnostics.get("public_records") != EXPECTED_ROWS:
            return False
        if diagnostics.get("status_counts") != EXPECTED_STATUSES:
            return False
        if diagnostics.get("identifier_raw_coverage") != EXPECTED_ROWS:
            return False
        if diagnostics.get("dropped_date_rows") != 0:
            return False
        if Counter(row["source_status"] for row in records) != Counter(EXPECTED_STATUSES):
            return False
        return all(
            isinstance(row.get("requested_activities"), list)
            and bool(row["requested_activities"])
            and bool(row.get("decision_date"))
            and bool(row.get("observed_expiry_date"))
            and bool(row.get("identifier_field_raw"))
            for row in records
        )
    except (TypeError, KeyError, AttributeError, ValueError):
        return False


def inspect_ascoli_original(store: Any, source_config: dict, inventory: list[dict]) -> dict:
    """Run independent source-only QA against the pinned original, never a live URL."""
    result = {
        "schema_version": 1, "scope": SCOPE, "status": "selection_unverified",
        "frozen_selection_accepted": False,
        "primary_original_sha256_verified": False,
        "strict_parser_compatible_source_only": False,
        "source_occurrences_strict_qa": None,
        "immutable_capture_catalogue_status": "unknown",
        "catalogue_listing_complete": False,
        "verified_immutable_capture_checks": 0,
        "explicit_writer_provenance_ready_checks": 0,
        "capture_or_database_writes": 0, "parse_snapshot_created": False,
        "administrative_editions_approved": 0, "public_promotions": 0,
    }
    cfg = _selected(source_config, inventory)
    if cfg is None:
        return result
    result["frozen_selection_accepted"] = True
    result["status"] = "primary_bytes_unknown"

    # The catalogue check is independent of physical parser QA. A missing receipt
    # is unknown, not proof of missing bytes or permission to reconstruct identity.
    try:
        catalogue = audit_historical_catalogue(store, targets=TARGETS)
        item = catalogue["results"][0]
        result["immutable_capture_catalogue_status"] = item["status"]
        result["catalogue_listing_complete"] = bool(item["bounded_catalogue_listing_complete"])
        result["verified_immutable_capture_checks"] = int(item["verified_capture_checks"])
        result["explicit_writer_provenance_ready_checks"] = int(
            item["explicit_writer_provenance_ready_checks"]
        )
    except Exception:
        pass

    try:
        raw = store.read_digest_verified(APPROVED_SHA256)
        if (type(raw) is not bytes or len(raw) != EXPECTED_BYTES
                or hashlib.sha256(raw).hexdigest() != APPROVED_SHA256):
            return result
    except Exception:
        return result

    result["primary_original_sha256_verified"] = True
    result["status"] = "parser_review_required"
    try:
        with TemporaryDirectory(prefix="ascoli-frozen-source-qa-") as directory:
            source = Path(directory) / "original.pdf"
            source.write_bytes(raw)
            batch = parse_ascoli_piceno_listed(source, cfg)
        if not _strict_batch_qa(batch):
            return result
    except Exception:
        # Parser exceptions can include private source cells and file coordinates.
        return result

    result["status"] = "strict_parser_compatible_source_only"
    result["strict_parser_compatible_source_only"] = True
    result["source_occurrences_strict_qa"] = EXPECTED_ROWS
    return result


def main() -> int:
    from white_list_archive.storage.evidence import EvidenceStore, StoreConfig, client_for
    try:
        config = json.loads(
            Path("data/publication/multi_prefecture_pilot.json").read_text(encoding="utf-8")
        )
        with Path("data/source_registry/source_series_inventory.csv").open(
                encoding="utf-8", newline="") as handle:
            inventory = list(csv.DictReader(handle))
        storage = StoreConfig.from_env()
        result = inspect_ascoli_original(
            EvidenceStore(client_for(storage), storage), config, inventory,
        )
    except Exception:
        # Do not disclose provider exceptions or source rows in public job logs.
        result = inspect_ascoli_original(None, {}, [])
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0  # A read-only source audit cannot block independent source lanes.


if __name__ == "__main__":
    raise SystemExit(main())
