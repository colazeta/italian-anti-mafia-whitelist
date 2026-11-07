"""Bounded reconciliation of the two already reviewed historical Cosenza captures.

Legacy catalogue provenance is never rewritten. Technical classifications absent
from the original capture are explicit subsequent assessments in a private,
conditional-write sidecar, bound to the exact reviewed legacy manifest.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile

from white_list_archive.acquisition.archive_first import ArchivedCapture
from white_list_archive.acquisition.auto_transform import (
    _check_capture_relational_readback, _parser_revision,
    persist_operational_report, private_connection, read_snapshot_verified,
)
from white_list_archive.persistence.archived_capture import (
    _capture_id, _content_object_id, _resource_id, _series_id, _verify_archived_boundary,
)
from white_list_archive.persistence.parse_snapshot import persist_parse_snapshot
from white_list_archive.persistence.source_series_registration import ensure_registered_source_series
from white_list_archive.storage.capture_catalogue import CaptureCatalogue
from white_list_archive.storage.catalogue_recovery import load_catalogued_capture
from white_list_archive.storage.evidence import EvidenceStore, StoreConfig, client_for, object_key
from white_list_archive.publishing.frozen_release import configuration_sha256

SPECS = (
    ("combined_2026-06-28.json", "9e769f09-3d3c-5d2a-b0f7-1b53ee5895c0", 1327),
    ("combined_2026-08-03.json", "32f713a4-2106-5c58-8256-6f3c02c133c3", 1334),
)
_EXISTING_CODES = {"PreconditionFailed", "412", "ObjectLockedByBucketPolicy", "10069"}


def classification_for(manifest: dict, historical: dict, *, filename: str) -> dict:
    """Allow no generic default: only the exact two reviewed legacy captures."""
    expected_ids = {name: cid for name, cid, _ in SPECS}
    if (filename not in expected_ids or manifest.get("capture_id") != expected_ids[filename]
            or manifest.get("source_key") != "cosenza-combined"
            or historical.get("source_series_key") != "cosenza-combined"
            or historical.get("authority_key") != "cosenza"):
        raise ValueError("Unreviewed legacy capture identity")
    fields = ("sha256", "byte_size", "captured_at", "reference_date", "resource_url",
              "content_type", "http_status", "etag", "last_modified", "origin_type")
    if any(manifest.get(field) != historical.get(field) for field in fields):
        raise ValueError("Legacy catalogue conflicts with reviewed historical provenance")
    if manifest.get("resolved_url") != historical.get("final_url"):
        raise ValueError("Historical resolved locator differs")
    if historical.get("content_type") != "application/pdf":
        raise ValueError("Reviewed legacy resource is not PDF")
    assessed = {"authority_rank_code": "primary_official", "resource_type_code": "pdf"}
    for field, value in assessed.items():
        if manifest.get(field) not in (None, value):
            raise ValueError("Legacy classification conflicts with captured metadata")
    return {
        "schema_version": 1,
        "policy": "reviewed-legacy-cosenza-classification-v1",
        "capture_id": manifest["capture_id"],
        "source_key": manifest["source_key"],
        "sha256": manifest["sha256"],
        "reviewed_manifest": "data/captures/cosenza/" + filename,
        "reviewed_manifest_sha256": configuration_sha256(historical),
        "assessment": assessed,
        "assessment_basis": "reviewed official frozen Cosenza PDF provenance",
    }


def retain_classification(store, classification: dict) -> None:
    body = json.dumps(classification, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")
    key = f"operations/v1/legacy-classification/{classification['capture_id']}.json"
    try:
        store.client.put_object(Bucket=store.config.bucket, Key=key, Body=body,
                                ContentType="application/json", IfNoneMatch="*")
    except Exception as exc:
        code = str(getattr(exc, "response", {}).get("Error", {}).get("Code"))
        if code not in _EXISTING_CODES:
            raise
    stream = store.client.get_object(Bucket=store.config.bucket, Key=key)["Body"]
    try:
        actual = stream.read(len(body) + 1)
    finally:
        stream.close()
    if actual != body:
        raise ValueError("Legacy classification failed exact immutable readback")


def reconcile_one(store, dsn: str, root: Path, cfg: dict, spec: tuple,
                  revision: str, progress: dict) -> dict:
    filename, capture_id, expected_rows = spec
    historical = json.loads((root / "data/captures/cosenza" / filename).read_text())
    progress["stage"] = "legacy_archive_integrity"
    manifest, receipt = load_catalogued_capture(
        CaptureCatalogue(store), source_key="cosenza-combined", capture_id=capture_id,
    )
    classification = classification_for(manifest, historical, filename=filename)
    data = store.read_verified(manifest)
    if len(data) != historical["byte_size"] or hashlib.sha256(data).hexdigest() != historical["sha256"]:
        raise ValueError("Frozen legacy bytes failed historical identity verification")
    progress["stage"] = "legacy_classification"
    retain_classification(store, classification)
    with tempfile.TemporaryDirectory(prefix="private-legacy-cosenza-") as temp:
        path = Path(temp) / "original.pdf"
        path.write_bytes(data)
        archived = ArchivedCapture(path, manifest, {
            "sha256": manifest["sha256"], "byte_size": manifest["byte_size"],
            "content_type": manifest["content_type"],
            "storage_uri": f"{store.config.endpoint.rstrip('/')}/{store.config.bucket}/{object_key(manifest)}",
        }, receipt)
        # Verify ORIGINAL provenance. Never pass an amended manifest to the
        # catalogue or relabel missing capture fields as originally observed.
        original = _verify_archived_boundary(archived, store)
        progress["stage"] = "legacy_capture_persistence"
        with private_connection(dsn) as conn:
            ensure_registered_source_series(conn, source_key="cosenza-combined",
                authority_csv=root / "data/source_registry/territorial_authorities.csv",
                series_csv=root / "data/source_registry/source_series_inventory.csv")
            with conn.cursor() as cur:
                # Serialize this known identity for concurrent/repeated recovery.
                cur.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (capture_id,))
                series = _series_id(cur, "cosenza-combined")
                resource = _resource_id(cur, original, classification["assessment"]["resource_type_code"])
                content = _content_object_id(cur, original, store)
                _capture_id(cur, manifest=original, series_id=series,
                    resource_id=resource, content_object_id=content,
                    origin_type=original["origin_type"],
                    authority_rank_code=classification["assessment"]["authority_rank_code"])
            conn.commit()
        with private_connection(dsn) as conn:
            _check_capture_relational_readback(conn, capture_id, original["sha256"])
        progress["stage"] = "legacy_parsing"
        from white_list_archive.publishing.public_national_registry import _adapt_cosenza
        parse_cfg = deepcopy(cfg)
        # These dates are documented in the matching historical manifest; no
        # date of a newly changed or unreviewed edition is being guessed.
        parse_cfg.update(sha256=original["sha256"], reference_date=historical["reference_date"],
            resource_url=original["resource_url"], source_page_url=historical["page_url"],
            expected_source_rows=expected_rows, last_source_update=historical["reference_date"])
        start = datetime.now(timezone.utc)
        batch = _adapt_cosenza(path, parse_cfg)
        end = datetime.now(timezone.utc)
        if len(batch.records) != expected_rows:
            raise ValueError("Frozen Cosenza interpretation differs from reviewed pilot denominator")
        progress["stage"] = "legacy_snapshot_persistence"
        with private_connection(dsn) as conn:
            result = persist_parse_snapshot(conn, capture_id=capture_id,
                parser_name=cfg["parser"], parser_revision=_parser_revision(batch, cfg["parser"]),
                code_revision=revision, configuration_hash=configuration_sha256(parse_cfg),
                started_at=start, completed_at=end, records=batch.records, diagnostics=batch.diagnostics)
            conn.commit()
        progress["stage"] = "legacy_snapshot_readback"
        with private_connection(dsn) as conn:
            records, _ = read_snapshot_verified(conn, result["parse_run_id"])
    return {"capture_id": capture_id, "records": len(records),
            "capture_readback": True, "snapshot_rehash": True,
            "snapshot_reused": result["snapshot_reused"], "publications": 0}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code-revision", required=True)
    args = parser.parse_args(argv)
    import re
    if not re.fullmatch(r"[0-9a-f]{40}", args.code_revision):
        raise SystemExit("Exact executing revision is required")
    root = Path(__file__).resolve().parents[3]
    config = json.loads((root / "data/publication/multi_prefecture_pilot.json").read_text())
    cfg = next(c for c in config["sources"] if c["source_key"] == "cosenza-combined")
    settings = StoreConfig.from_env()
    store = EvidenceStore(client_for(settings), settings)
    dsn = os.environ.get("EVIDENCE_DATABASE_URL", "")
    if not dsn:
        raise SystemExit("Dedicated relational writer is unavailable")
    outcomes = []
    for spec in SPECS:
        progress = {"stage": "preflight"}
        try:
            outcomes.append(reconcile_one(store, dsn, root, cfg, spec, args.code_revision, progress))
        except Exception as exc:
            outcomes.append({"capture_id": spec[1], "stage": progress["stage"],
                             "error_type": type(exc).__name__, "publications": 0})
    report = {"kind": "frozen-cosenza-reconciliation", "code_revision": args.code_revision,
              "run_at": datetime.now(timezone.utc).isoformat(), "outcomes": outcomes}
    try:
        persist_operational_report(store, report)
    except Exception:
        print('{"private_report_verified":false,"publications":0}')
        return 1
    succeeded = sum(o.get("snapshot_rehash") is True for o in outcomes)
    print(json.dumps({"selected_captures": len(SPECS), "verified_snapshots": succeeded,
        "records": sum(o.get("records", 0) for o in outcomes),
        "reused_snapshots": sum(o.get("snapshot_reused") is True for o in outcomes),
        "private_report_verified": True, "publications": 0}, sort_keys=True))
    return int(succeeded != len(SPECS))


if __name__ == "__main__":
    raise SystemExit(main())
