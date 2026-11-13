"""Reconcile *existing* immutable historical capture checks into source tables.

Three known historical byte pins have verified complete CaptureCatalogue entries.
Persist their exact provenance with the existing append-only writer. Never acquire a
mutable URL, fabricate an edition/date, parse a row, or publish any record.
Every operational report contains closed aggregate counters only.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import json
import os
from pathlib import Path
from typing import Any

from white_list_archive.acquisition.historical_object_audit import MAX_EXPECTED_SOURCE_BYTES
from white_list_archive.storage.capture_catalogue import CaptureCatalogue
from white_list_archive.storage.catalogue_recovery import load_catalogued_capture
from white_list_archive.storage.evidence import object_key
from white_list_archive.storage.historical_capture_provenance_audit import (
    MAX_KEYS_PER_SOURCE, TARGETS, _valid_capture_key,
)

_REQUIRED = ("origin_type", "authority_rank_code", "resource_type_code")
_ALLOWED_SERIES = frozenset({"lodi-listed", "lodi-applicants", "milano-combined"})


def select_verified_historical_checks(
    store: Any, *, targets: tuple = TARGETS, limit: int = MAX_KEYS_PER_SOURCE,
) -> tuple[list[tuple[dict, dict]], dict]:
    """Select only positively verified, complete archive provenance; fail closed."""
    if (type(limit) is not int or not 1 <= limit <= MAX_KEYS_PER_SOURCE
            or not isinstance(targets, tuple) or not targets
            or len({scope for _, scope, _ in targets}) != len(targets)
            or any(
                not isinstance(scope, str) or not scope
                or series not in _ALLOWED_SERIES
                or not isinstance(sha, str) or len(sha) != 64
                or any(c not in "0123456789abcdef" for c in sha)
                for series, scope, sha in targets
            )):
        raise ValueError("Invalid closed historical selection")
    by_series: dict[str, dict[str, str]] = defaultdict(dict)
    for series, scope, sha in targets:
        if sha in by_series[series]:
            raise ValueError("Duplicate historical digest in one series")
        by_series[series][sha] = scope

    catalogue = CaptureCatalogue(store)
    selected = []
    positives = {scope: set() for _, scope, _ in targets}
    incomplete = 0
    metadata_blocked = 0
    for series, pinned in by_series.items():
        try:
            listing = store.client.list_objects_v2(
                Bucket=store.config.bucket, Prefix=f"captures/v1/{series}/",
                MaxKeys=limit,
            )
            objects = listing.get("Contents")
            if (listing.get("IsTruncated") is not False or
                    not isinstance(objects, list) or len(objects) > limit):
                incomplete += 1
                continue
        except Exception:
            incomplete += 1
            continue
        # A complete listing is a bounded candidate index, not an approval.
        for item in objects:
            if not isinstance(item, dict):
                continue
            capture_id = _valid_capture_key(item.get("Key"), source_key=series)
            if capture_id is None:
                continue
            try:
                manifest, receipt = load_catalogued_capture(
                    catalogue, source_key=series, capture_id=capture_id,
                )
                sha = manifest["sha256"]
                if (sha not in pinned or manifest["source_key"] != series
                        or manifest["capture_id"] != capture_id
                        or manifest["byte_size"] > MAX_EXPECTED_SOURCE_BYTES):
                    continue
                # This re-reads original bytes and checks the manifest SHA/size.
                store.read_verified(manifest)
                if not all(isinstance(manifest.get(f), str) and manifest[f].strip()
                           for f in _REQUIRED):
                    metadata_blocked += 1
                    continue
                positives[pinned[sha]].add(capture_id)
                selected.append((manifest, receipt))
            except Exception:
                # Never include an exception that may carry a private key or URL.
                continue

    summary = {
        "historical_pins_checked": len(targets),
        "pins_with_eligible_capture_provenance": sum(bool(s) for s in positives.values()),
        "historical_pins_unknown_or_unverified": sum(not s for s in positives.values()),
        "eligible_capture_checks": len(selected),
        "missing_writer_metadata_checks": metadata_blocked,
        "incomplete_or_unavailable_prefix_listings": incomplete,
    }
    return selected, summary


def persist_and_independently_readback(store: Any, manifest: dict, receipt: dict, dsn: str) -> tuple[bool, bool]:
    """Append via current writer, commit, then independently verify on new TLS hop."""
    from white_list_archive.acquisition.archive_first import ArchivedCapture
    from white_list_archive.acquisition.auto_transform import private_connection
    from white_list_archive.persistence.archived_capture import persist_archived_capture

    content_receipt = {
        "sha256": manifest["sha256"], "byte_size": manifest["byte_size"],
        "content_type": manifest["content_type"],
        "storage_uri": f"{store.config.endpoint.rstrip('/')}/{store.config.bucket}/{object_key(manifest)}",
    }
    archived = ArchivedCapture(
        path=Path("."), manifest=manifest,
        content_receipt=content_receipt, catalogue_receipt=receipt,
    )
    with private_connection(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM source.source_capture WHERE capture_id=%s",
                        (manifest["capture_id"],))
            already_captured = cur.fetchone() is not None
            cur.execute("SELECT 1 FROM source.content_object WHERE sha256=%s",
                        (manifest["sha256"],))
            already_registered = cur.fetchone() is not None
        # Existing writer independently checks ContentObject and catalogue again.
        # It refuses conflicting immutable capture UUID/provenance and never
        # creates a SourceEdition, parser run or canonical entity.
        persist_archived_capture(conn, archived, store)
        conn.commit()

    with private_connection(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT ss.series_code, co.sha256, co.file_size,
                          co.storage_status_code, c.captured_at,
                          sr.canonical_locator, c.origin_type_code,
                          c.authority_rank_code, c.declared_reference_date
                   FROM source.source_capture c
                   JOIN source.source_series ss ON ss.series_id=c.series_id
                   JOIN source.content_object co ON co.content_object_id=c.content_object_id
                   JOIN source.source_resource sr ON sr.resource_id=c.resource_id
                   WHERE c.capture_id=%s""",
                (manifest["capture_id"],),
            )
            row = cur.fetchone()
    frozen_date = manifest.get("reference_date")
    expected = (
        manifest["source_key"], manifest["sha256"], manifest["byte_size"],
        "durable", datetime.fromisoformat(manifest["captured_at"].replace("Z", "+00:00")),
        manifest["resource_url"], manifest["origin_type"],
        manifest["authority_rank_code"],
        None if frozen_date in (None, "") else datetime.fromisoformat(frozen_date).date(),
    )
    if row is None or tuple(row) != expected:
        raise RuntimeError("Historical capture post-commit provenance readback failed")
    return not already_captured, not already_registered


def reconcile_historical_capture_checks(
    store: Any, dsn: str, *, targets: tuple = TARGETS,
) -> dict:
    checked, report = select_verified_historical_checks(store, targets=targets)
    new_captures = 0
    new_originals = 0
    readbacks = 0
    errors = 0
    if dsn:
        for manifest, receipt in checked:
            try:
                capture_created, original_created = persist_and_independently_readback(
                    store, manifest, receipt, dsn,
                )
                new_captures += int(capture_created)
                new_originals += int(original_created)
                readbacks += 1
            except Exception:
                errors += 1
    return {
        **report,
        "writer_configured": bool(dsn),
        "source_capture_checks_postcommit_verified": readbacks,
        "new_source_capture_checks": new_captures,
        "new_content_objects": new_originals,
        "relational_reconciliation_failures": errors,
        "editions_approved": 0,
        "semantic_or_canonical_writes": 0,
        "public_promotions": 0,
        "independent_restore_verified": False,
    }


def main() -> int:
    from white_list_archive.storage.evidence import EvidenceStore, StoreConfig, client_for
    try:
        config = StoreConfig.from_env()
        store = EvidenceStore(client_for(config), config)
        result = reconcile_historical_capture_checks(
            store, os.environ.get("EVIDENCE_DATABASE_URL", ""),
        )
    except Exception:
        result = {
            "historical_pins_checked": 4, "pins_with_eligible_capture_provenance": 0,
            "historical_pins_unknown_or_unverified": 4,
            "eligible_capture_checks": 0, "writer_configured": False,
            "source_capture_checks_postcommit_verified": 0,
            "new_source_capture_checks": 0, "new_content_objects": 0,
            "relational_reconciliation_failures": 0,
            "status": "unavailable_or_unverified",
            "editions_approved": 0, "semantic_or_canonical_writes": 0,
            "public_promotions": 0, "independent_restore_verified": False,
        }
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    # Local recovery failure does not abort the independent current-source lane.
    # Only nonzero real post-commit readbacks count as completed recovery.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
