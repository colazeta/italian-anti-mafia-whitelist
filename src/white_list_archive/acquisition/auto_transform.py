"""Automatically interpret archived, reviewed White List source captures.

This is a *private interpretation* worker. It never discovers, fetches a live
source URL, approves an edition, updates a publication config or deploys Pages.
A changed document has an unknown administrative reference date until reviewed.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import tempfile
from typing import Any
from urllib.parse import urlsplit

_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_MAX_BYTES = 100_000_000


def _resource_urls(cfg: dict) -> dict[str, str]:
    if cfg.get("resources") is None:
        return {"primary": cfg["resource_url"]}
    resources = cfg["resources"]
    if not isinstance(resources, dict) or not resources:
        raise ValueError("Reviewed source bundle has no labelled resources")
    return {label: resource["resource_url"] for label, resource in resources.items()}


def select_reviewed_jobs(
    state: dict[str, Any],
    config: dict[str, Any],
    *,
    shard: int = 0,
    shards: int = 1,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Select complete latest *captured* inputs, never discover by filename.

    Robot/check metadata is only a candidate index: both private-store objects
    are independently read and verified before a parser sees source bytes.
    """
    if shards < 1 or not 0 <= shard < shards:
        raise ValueError("Invalid shard")
    if state.get("schema_version") != 1 or not isinstance(state.get("robots"), dict):
        raise ValueError("Unsupported robot-state shape")
    sources = config.get("sources")
    if not isinstance(sources, list):
        raise ValueError("Invalid reviewed-source configuration")
    jobs, deferred = [], []
    keys = set()
    for cfg in sources:
        key = cfg.get("source_key")
        if not isinstance(key, str) or key in keys:
            raise ValueError("Missing or duplicate reviewed source key")
        keys.add(key)
        authority_key = cfg.get("authority_key")
        if not isinstance(authority_key, str):
            raise ValueError("Reviewed source has no authority key")
        # All resources of one authority stay together; do not split bundles.
        if int(hashlib.sha256(authority_key.encode()).hexdigest(), 16) % shards != shard:
            continue
        robot = state["robots"].get(authority_key, {})
        if not robot.get("population_mapping_reviewed"):
            deferred.append({"source_key": key, "reason": "unreviewed_authority"})
            continue
        resources = robot.get("resources", {})
        if not isinstance(resources, dict):
            deferred.append({"source_key": key, "reason": "invalid_robot_resources"})
            continue
        captures = {}
        for label, url in _resource_urls(cfg).items():
            item = resources.get(url, {})
            history = item.get("capture_history", []) if isinstance(item, dict) else []
            eligible = [
                h for h in history
                if isinstance(h, dict) and h.get("source_key") == key
                and isinstance(h.get("capture_id"), str)
                and isinstance(h.get("sha256"), str)
                and _HEX64.fullmatch(h["sha256"])
                and isinstance(h.get("captured_at"), str)
                and isinstance(h.get("byte_size"), int)
                and 0 < h["byte_size"] <= _MAX_BYTES
            ]
            if not eligible:
                deferred.append({"source_key": key, "reason": "missing_verified_capture"})
                captures = {}
                break
            captures[label] = {
                "url": url,
                "state": max(eligible, key=lambda h: (h["captured_at"], h["capture_id"])),
            }
        if not captures:
            continue
        if cfg.get("resources") is None:
            changed = captures["primary"]["state"]["sha256"] != cfg.get("sha256")
        else:
            changed = any(
                captures[label]["state"]["sha256"] != cfg["resources"][label].get("sha256")
                for label in captures
            )
        if changed:
            jobs.append({"source_key": key, "config": cfg, "captures": captures})
    return jobs, deferred


def _parse_config(job: dict[str, Any]) -> dict[str, Any]:
    """Never reuse the approved edition date for newly changed source bytes."""
    cfg = deepcopy(job["config"])
    captures = job["captures"]
    if cfg.get("resources") is None:
        cfg["sha256"] = captures["primary"]["state"]["sha256"]
    else:
        for label, part in captures.items():
            cfg["resources"][label]["sha256"] = part["state"]["sha256"]
        # The established bundle digest is over labelled hashes in sorted order.
        hashes = {label: part["state"]["sha256"] for label, part in captures.items()}
        cfg["sha256"] = "bundle:" + hashlib.sha256(
            "".join(hashes[label] for label in sorted(hashes)).encode("ascii")
        ).hexdigest()
    cfg["reference_date"] = ""  # Unknown until the publication-date evidence is reviewed.
    return cfg


def _verified_capture(store: Any, entry: dict[str, Any]):
    """Reconstruct a receipt from *read-back* immutable catalogue bytes.

    Never treat the Git robot-state as an authority for provenance or storage.
    Legacy catalogue entries without their original manifest fail closed.
    """
    from white_list_archive.storage.capture_catalogue import (
        CaptureCatalogue, capture_record_key,
    )
    from white_list_archive.storage.evidence import freeze_capture_manifest, object_key

    state = entry["state"]
    source_key = state["source_key"]
    capture_id = state["capture_id"]
    catalogue = CaptureCatalogue(store)
    key = capture_record_key({"source_key": source_key, "capture_id": capture_id})
    body, record = catalogue._read_record(key)
    raw_manifest = record.get("capture_manifest")
    if not isinstance(raw_manifest, dict):
        raise ValueError("Legacy capture lacks a complete immutable manifest")
    manifest = freeze_capture_manifest(raw_manifest)
    if (manifest.get("capture_id") != capture_id
            or manifest.get("source_key") != source_key
            or manifest.get("resource_url") != entry["url"]
            or manifest["sha256"] != state["sha256"]
            or manifest["byte_size"] != state["byte_size"]):
        raise ValueError("Robot-state and immutable capture metadata disagree")
    receipt = {
        "schema_version": 1,
        "capture_id": capture_id,
        "source_key": source_key,
        "sha256": manifest["sha256"],
        "byte_size": manifest["byte_size"],
        "catalogue_key": key,
        "catalogue_record_sha256": hashlib.sha256(body).hexdigest(),
        "created": False,
        "content_object_key": object_key(manifest),
    }
    catalogue.verify_receipt(manifest, receipt)
    data = store.read_verified(manifest)
    if len(data) != manifest["byte_size"] or hashlib.sha256(data).hexdigest() != manifest["sha256"]:
        raise ValueError("Archived source failed independent byte integrity check")
    return manifest, receipt, data


def _parser_revision(batch: Any, parser_name: str) -> str:
    revisions = {
        (r.get("parser_name"), str(r.get("parser_version") or ""))
        for r in batch.records
    }
    if len(revisions) == 1:
        name, version = next(iter(revisions))
        if name == parser_name and version:
            return f"{name}@{version}"
    if parser_name == "cosenza_combined_v2":
        from white_list_archive.publishing.public_national_registry import COSENZA_PARSER_VERSION
        return f"{parser_name}@{COSENZA_PARSER_VERSION}"
    raise ValueError("Parser output lacks consistent versioned lineage")


def transform_one(
    job: dict[str, Any],
    *,
    store: Any,
    dsn: str,
    code_revision: str,
    authority_registry: Path,
    series_registry: Path,
) -> dict[str, Any]:
    """Persist capture provenance, then parser observations in separate transactions."""
    import psycopg
    from white_list_archive.acquisition.archive_first import ArchivedCapture
    from white_list_archive.persistence.archived_capture import persist_archived_capture
    from white_list_archive.persistence.parse_snapshot import persist_parse_snapshot
    from white_list_archive.persistence.source_series_registration import ensure_registered_source_series
    from white_list_archive.publishing import public_national_registry as registry
    from white_list_archive.publishing.frozen_release import configuration_sha256
    from white_list_archive.storage.evidence import object_key

    if not dsn or _HEX40.fullmatch(code_revision) is None:
        raise ValueError("Private database and exact source code revision are required")
    cfg = _parse_config(job)
    captures = job["captures"]
    with tempfile.TemporaryDirectory(prefix="white-list-private-transform-") as temp:
        directory = Path(temp)
        verified = {}
        paths = {}
        # Require every member before registering/parsing any part of the bundle.
        for label in sorted(captures):
            manifest, receipt, data = _verified_capture(store, captures[label])
            suffix = Path(urlsplit(captures[label]["url"]).path).suffix.lower()
            if not re.fullmatch(r"\.[a-z0-9]{1,6}", suffix):
                suffix = ".bin"
            path = directory / f"source-{label}{suffix}"
            path.write_bytes(data)
            verified[label] = (manifest, receipt)
            paths[label] = path

        for label in sorted(verified):
            manifest, receipt = verified[label]
            content_receipt = {
                "sha256": manifest["sha256"],
                "byte_size": manifest["byte_size"],
                "content_type": manifest["content_type"],
                "storage_uri": (
                    f"{store.config.endpoint.rstrip('/')}/{store.config.bucket}/{object_key(manifest)}"
                ),
            }
            archived = ArchivedCapture(
                path=paths[label],
                manifest=manifest,
                content_receipt=content_receipt,
                catalogue_receipt=receipt,
            )
            with psycopg.connect(dsn) as conn:
                ensure_registered_source_series(
                    conn,
                    source_key=job["source_key"],
                    authority_csv=authority_registry,
                    series_csv=series_registry,
                )
                persist_archived_capture(conn, archived, store)
                conn.commit()

        source_input = paths["primary"] if job["config"].get("resources") is None else paths
        started_at = datetime.now(timezone.utc)
        batch = registry._parse_source(source_input, cfg)
        completed_at = datetime.now(timezone.utc)
        if not isinstance(batch.records, list) or not batch.records:
            raise ValueError("Parser returned no source observations")
        version = _parser_revision(batch, cfg["parser"])
        capture_inputs = [
            {"label": label, "capture_id": verified[label][0]["capture_id"]}
            for label in sorted(verified)
        ]
        with psycopg.connect(dsn) as conn:
            result = persist_parse_snapshot(
                conn,
                capture_inputs=capture_inputs,
                parser_name=cfg["parser"],
                parser_revision=version,
                code_revision=code_revision,
                configuration_hash=configuration_sha256(cfg),
                started_at=started_at,
                completed_at=completed_at,
                records=batch.records,
                diagnostics=batch.diagnostics,
            )
            conn.commit()
        diagnostics = batch.diagnostics
        expected = job["config"].get("expected_source_rows")
        count_matches = expected is None or int(expected) == len(batch.records)
        return {
            "source_key": job["source_key"],
            "status": "parsed_private_review_required",
            "records": len(batch.records),
            "approved_row_count_matches": count_matches,
            "dropped_date_rows": diagnostics.get("dropped_date_rows", 0),
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--source-config", required=True, type=Path)
    parser.add_argument("--authority-registry", type=Path, default=Path("data/source_registry/territorial_authorities.csv"))
    parser.add_argument("--series-registry", type=Path, default=Path("data/source_registry/source_series_inventory.csv"))
    parser.add_argument("--shard", type=int, default=0)
    parser.add_argument("--shards", type=int, default=1)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--code-revision", required=True)
    args = parser.parse_args(argv)

    state = json.loads(args.state.read_text(encoding="utf-8"))
    config = json.loads(args.source_config.read_text(encoding="utf-8"))
    jobs, deferred = select_reviewed_jobs(state, config, shard=args.shard, shards=args.shards)
    import os
    from white_list_archive.storage.evidence import EvidenceStore, StoreConfig, client_for
    dsn = os.environ.get("EVIDENCE_DATABASE_URL", "")
    if jobs and not dsn:
        raise SystemExit("Private observation database is unavailable; no transformations were attempted")
    if _HEX40.fullmatch(args.code_revision) is None:
        raise SystemExit("An exact checked-out Git revision is required")
    store_config = StoreConfig.from_env() if jobs else None
    store = EvidenceStore(client_for(store_config), store_config) if store_config else None

    outcomes = []
    for job in jobs:
        try:
            outcomes.append(transform_one(
                job, store=store, dsn=dsn,
                code_revision=args.code_revision,
                authority_registry=args.authority_registry,
                series_registry=args.series_registry,
            ))
        except Exception as exc:
            # Provider/parser exceptions can contain row-level or private coordinates.
            # Retain only a bounded error *class*, never its message.
            outcomes.append({
                "source_key": job["source_key"],
                "status": "quarantined",
                "error_type": type(exc).__name__,
            })
    report = {
        "schema_version": 1,
        "run_at": datetime.now(timezone.utc).isoformat(),
        "shard": args.shard,
        "shards": args.shards,
        "changed_sources": len(jobs),
        "transformed": sum(row["status"] == "parsed_private_review_required" for row in outcomes),
        "quarantined": sum(row["status"] == "quarantined" for row in outcomes),
        "deferred": len(deferred),
        "outcomes": outcomes,
        "deferred_reasons": {
            name: sum(row["reason"] == name for row in deferred)
            for name in sorted({row["reason"] for row in deferred})
        },
        "publications": 0,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "changed_sources": report["changed_sources"],
        "transformed_private": report["transformed"],
        "quarantined": report["quarantined"],
        "deferred": report["deferred"],
        "publications": 0,
    }, sort_keys=True))
    return 1 if report["quarantined"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
