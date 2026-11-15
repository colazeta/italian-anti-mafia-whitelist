"""Materialise one already-reviewed Ascoli original as a private source snapshot.

The public publication key and the immutable registered CaptureCatalogue series
have different names. This exact-source adapter may persist parser observations
only after three independent gates: frozen selection, physical parser QA and
authentic complete capture provenance. No capture is relabelled or fabricated.
It never creates SourceEdition, semantic/canonical facts or a public release.
"""
from __future__ import annotations

from copy import deepcopy
import csv
import json
import os
from pathlib import Path
import subprocess
from typing import Any

from white_list_archive.acquisition import auto_transform as transform
from white_list_archive.acquisition import ascoli_private_source_qa as qa
from white_list_archive.acquisition.approved_snapshot_backfill import existing_snapshot
from white_list_archive.acquisition.approved_source_alias_audit import (
    APPROVED_SHA256, EXPECTED_ROWS, REGISTERED_KEY,
)
from white_list_archive.storage.capture_catalogue import CaptureCatalogue
from white_list_archive.storage.catalogue_recovery import load_catalogued_capture
from white_list_archive.storage.historical_capture_provenance_audit import (
    MAX_KEYS_PER_SOURCE, _valid_capture_key,
)


def _exact_catalogued_manifest(store: Any) -> dict:
    """Read exactly one genuine registered capture; never infer identity from SHA."""
    prefix = f"captures/v1/{REGISTERED_KEY}/"
    response = store.client.list_objects_v2(
        Bucket=store.config.bucket, Prefix=prefix, MaxKeys=MAX_KEYS_PER_SOURCE,
    )
    items = response.get("Contents")
    if (response.get("IsTruncated") is not False or not isinstance(items, list)
            or len(items) > MAX_KEYS_PER_SOURCE):
        raise ValueError("Ascoli registered capture listing is incomplete")
    catalogue = CaptureCatalogue(store)
    matches = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Unexpected registered capture catalogue entry")
        capture_id = _valid_capture_key(item.get("Key"), source_key=REGISTERED_KEY)
        if capture_id is None:
            raise ValueError("Malformed registered capture catalogue key")
        # Other revisions may be old catalogue formats: they do not need to
        # pass a modern manifest gate to identify the ONE frozen SHA target.
        # Never infer absence from an unreadable listing or candidate record.
        _, record = catalogue._read_record(item["Key"])
        if record.get("sha256") != APPROVED_SHA256:
            continue
        manifest, _ = load_catalogued_capture(
            catalogue, source_key=REGISTERED_KEY, capture_id=capture_id,
        )
        if manifest["sha256"] != APPROVED_SHA256:
            raise ValueError("Stored catalogue target digest changed")
        matches.append(manifest)
    if len(matches) != 1:
        raise ValueError("Exactly one immutable Ascoli original is required")
    return matches[0]


def build_exact_job(store: Any, config: dict, inventory: list[dict]) -> dict:
    """Construct a source-only job from the reviewed source and real manifest."""
    selected = qa._selected(config, inventory)
    if selected is None:
        raise ValueError("Frozen publication/source-series selection changed")
    audit = qa.inspect_ascoli_original(store, config, inventory)
    if (audit["status"] != "strict_parser_compatible_source_only"
            or audit["source_occurrences_strict_qa"] != EXPECTED_ROWS
            or audit["immutable_capture_catalogue_status"] != "verified_immutable_capture_provenance"
            or audit["catalogue_listing_complete"] is not True
            or audit["verified_immutable_capture_checks"] != 1
            or audit["explicit_writer_provenance_ready_checks"] != 1):
        raise ValueError("Independent original, parser or catalogue QA incomplete")
    manifest = _exact_catalogued_manifest(store)
    if (manifest.get("source_key") != REGISTERED_KEY
            or manifest.get("sha256") != APPROVED_SHA256
            or manifest.get("byte_size") != qa.EXPECTED_BYTES
            or manifest.get("resource_url") != selected["resource_url"]
            or manifest.get("reference_date") not in (None, "")
            or manifest.get("http_status") != 200
            or manifest.get("origin_type") != "official_current"
            or manifest.get("authority_rank_code") != "primary_official"
            or not isinstance(manifest.get("resource_type_code"), str)
            or not manifest["resource_type_code"].strip()):
        raise ValueError("Ascoli source identity or capture provenance changed")
    # The document's explicitly reviewed date is source observation metadata.
    # It does NOT populate the unknown date of the historical capture.
    source_config = deepcopy(selected)
    source_config["source_key"] = REGISTERED_KEY
    return {
        "source_key": REGISTERED_KEY,
        "config": source_config,
        "captures": {"primary": {
            "url": manifest["resource_url"],
            "state": {
                "source_key": REGISTERED_KEY,
                "capture_id": manifest["capture_id"],
                "sha256": manifest["sha256"],
                "byte_size": manifest["byte_size"],
            },
        }},
    }


def materialise_exact_source(
    store: Any, dsn: str, revision: str, config: dict, inventory: list[dict],
    *, authority_registry: Path, series_registry: Path,
) -> dict:
    if not dsn or transform._HEX40.fullmatch(revision) is None:
        raise ValueError("Frozen code revision and TLS database writer required")
    job = build_exact_job(store, config, inventory)
    # Read across ALL previous code revisions: this is a missing snapshot
    # backfill, not an excuse to store an interpretation on every code push.
    with transform.private_connection(dsn) as conn:
        exists = existing_snapshot(conn, job)
    if exists:
        return {
            "status": "existing_verified", "existing_verified": 1,
            "materialised": 0, "source_occurrences_verified": EXPECTED_ROWS,
            "publications": 0, "administrative_editions_approved": 0,
        }
    outcome = transform.transform_one(
        job, store=store, dsn=dsn, code_revision=revision,
        authority_registry=authority_registry, series_registry=series_registry,
    )
    if (outcome.get("status") not in {
                "parsed_private_review_required", "reused_private_interpretation"}
            or outcome.get("database_readback") != "verified"
            or outcome.get("database_tls_verified") is not True
            or outcome.get("publication_approved") is not False
            or outcome.get("records") != EXPECTED_ROWS
            or outcome.get("qa_flags")):
        raise ValueError("Ascoli private snapshot failed strict readback/row QA")
    # Recheck the committed snapshot through the cross-revision verifier.
    with transform.private_connection(dsn) as conn:
        if not existing_snapshot(conn, job):
            raise ValueError("Ascoli persisted interpretation not found on readback")
    return {
        "status": "source_snapshot_verified", "existing_verified": 0,
        "materialised": int(outcome["status"] == "parsed_private_review_required"),
        "source_occurrences_verified": EXPECTED_ROWS,
        "publications": 0, "administrative_editions_approved": 0,
    }


def main() -> int:
    try:
        from white_list_archive.storage.evidence import EvidenceStore, StoreConfig, client_for
        config = json.loads(Path("data/publication/multi_prefecture_pilot.json").read_text())
        with Path("data/source_registry/source_series_inventory.csv").open(newline="") as handle:
            inventory = list(csv.DictReader(handle))
        storage = StoreConfig.from_env()
        store = EvidenceStore(client_for(storage), storage)
        outcome = materialise_exact_source(
            store, os.environ["EVIDENCE_DATABASE_URL"],
            subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
            config, inventory,
            authority_registry=Path("data/source_registry/territorial_authorities.csv"),
            series_registry=Path("data/source_registry/source_series_inventory.csv"),
        )
    except Exception:
        # Original PDFs, person/company rows, provider keys and exception text
        # must never enter public workflow logs.
        outcome = {"status": "source_snapshot_blocked", "existing_verified": 0,
                   "materialised": 0, "source_occurrences_verified": 0,
                   "publications": 0, "administrative_editions_approved": 0}
        print(json.dumps(outcome, sort_keys=True))
        return 1
    print(json.dumps(outcome, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
