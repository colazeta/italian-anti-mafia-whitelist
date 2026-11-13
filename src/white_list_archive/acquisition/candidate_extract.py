"""Private automatic extraction of *unbound* documents discovered by Prefecture robots.

A parser candidate is a review hypothesis, not a SourceSeries assignment. Only
immutable, catalogue-verified robot-discovery captures are read. No new official
edition date, accepted business record, canonical relationship or public release
is produced here. Full extracted rows stay in the protected evidence store.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import unquote, urlsplit

from .auto_transform import (
    _HEX40, _HEX64, _capture_timestamp_utc, _parser_revision, _quality_flags,
    _verified_capture, persist_operational_report,
)
from .prefecture_robots import allowed

SUPPORTED = frozenset({".pdf", ".xlsx", ".xls", ".csv", ".docx", ".doc"})
RELEVANT = re.compile(r"white[\s_-]*list|elenc|iscritt|richied|imprese|ditte", re.I)
EXCLUDE = re.compile(r"modul|modell|fac.?simil|informativ|privacy|autocertific|"
                     r"dichiaraz|comunicaz|sequestrat|domanda-di-iscrizione", re.I)
MAX_RECORD_BYTES = 40_000_000
MAX_NEW_PER_SHARD = 6


def _scope_hint(url: str) -> str | None:
    name = unquote(urlsplit(url).path.rsplit("/", 1)[-1]).casefold()
    if re.search(r"richied|istanze|in.istruttoria|domande", name):
        return "applicant"
    if re.search(r"iscritt|registrat", name):
        return "listed"
    return None


def _suffix(url: str) -> str:
    return Path(urlsplit(url).path).suffix.lower()


def _candidate_filename(url: str) -> bool:
    name = unquote(urlsplit(url).path.rsplit("/", 1)[-1])
    return bool(_suffix(url) in SUPPORTED and RELEVANT.search(name)
                and not EXCLUDE.search(name))


def _resource_urls(config: dict) -> list[str]:
    if config.get("resources") is None:
        return [config["resource_url"]]
    return [part["resource_url"] for part in config["resources"].values()]


def select_candidate_jobs(state: dict, config: dict, catalog: dict, *,
                          shard: int = 0, shards: int = 1) -> tuple[list[dict], list[dict]]:
    """Return uniquely routed parser *hypotheses*, never approved source bindings."""
    if shards < 1 or shard < 0 or shard >= shards:
        raise ValueError("Invalid shard")
    if state.get("schema_version") != 1 or not isinstance(state.get("robots"), dict):
        raise ValueError("Invalid robot check-state contract")
    if catalog.get("schema_version") != 1 or not isinstance(catalog.get("robots"), list):
        raise ValueError("Invalid reviewed robot catalogue")
    if not isinstance(config.get("sources"), list):
        raise ValueError("Invalid reviewed publication config")
    robots = {r["authority_key"]: r for r in catalog["robots"]}
    if len(robots) != len(catalog["robots"]):
        raise ValueError("Duplicate reviewed authority")
    configs: dict[str, list[dict]] = {}
    published_urls: dict[str, set[str]] = {}
    for cfg in config["sources"]:
        authority = cfg["authority_key"]
        configs.setdefault(authority, []).append(cfg)
        published_urls.setdefault(authority, set()).update(_resource_urls(cfg))
    jobs: list[dict] = []
    deferred: list[dict] = []
    for authority, report in sorted(state["robots"].items()):
        if int(hashlib.sha256(authority.encode()).hexdigest(), 16) % shards != shard:
            continue
        reviewed = robots.get(authority)
        if not reviewed or not report.get("population_mapping_reviewed"):
            continue
        hosts = reviewed["allowed_hosts"]
        sources = configs.get(authority, [])
        if not sources:
            continue
        for url, resource in sorted(report.get("resources", {}).items()):
            if (not isinstance(resource, dict) or resource.get("role") != "candidate"
                    or url in published_urls[authority] or url in reviewed["landing_pages"]):
                continue
            if not allowed(url, hosts) or not _candidate_filename(url):
                continue
            suffix = _suffix(url)
            hint = _scope_hint(url)
            routes = [
                cfg for cfg in sources
                if cfg.get("resources") is None
                and _suffix(cfg["resource_url"]) == suffix
                and (hint is None or cfg.get("population_scope") == hint)
            ]
            # No filename, extension or URL can *approve* a new SourceSeries.
            # One unambiguous *candidate* parser is the maximum permitted claim.
            if len(routes) != 1:
                deferred.append({"authority_key": authority, "candidate_url": url,
                                 "reason": "no_unique_parser_hypothesis"})
                continue
            history = resource.get("capture_history", [])
            valid = [
                h for h in history if isinstance(h, dict)
                and h.get("source_key") == authority + "-robot-discovery"
                and isinstance(h.get("capture_id"), str)
                and isinstance(h.get("sha256"), str)
                and _HEX64.fullmatch(h["sha256"])
                and type(h.get("byte_size")) is int and 0 < h["byte_size"] <= 100_000_000
                and _capture_timestamp_utc(h.get("captured_at")) is not None
            ] if isinstance(history, list) else []
            if not valid:
                deferred.append({"authority_key": authority, "candidate_url": url,
                                 "reason": "missing_verified_discovery_capture"})
                continue
            latest = max(valid, key=lambda h: (_capture_timestamp_utc(h["captured_at"]),
                                               h["capture_id"]))
            jobs.append({"authority_key": authority, "url": url,
                         "source_key_hypothesis": routes[0]["source_key"],
                         "config": routes[0], "capture": latest})
    # Handle the newest incoming candidates first; already staged identities
    # are skipped cheaply and never consume the bounded parsing budget.
    jobs.sort(key=lambda j: (_capture_timestamp_utc(j["capture"]["captured_at"]),
                             j["authority_key"], j["url"]), reverse=True)
    return jobs, deferred


def _identity(job: dict, code_revision: str) -> dict:
    cfg = job["config"]
    return {
        "schema_version": 1,
        "capture_source_key": job["authority_key"] + "-robot-discovery",
        "document_url": job["url"],
        "document_sha256": job["capture"]["sha256"],
        "parser_hypothesis": cfg["parser"],
        "source_series_hypothesis": cfg["source_key"],
        "parser_config_sha256": hashlib.sha256(json.dumps(
            cfg, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
            allow_nan=False).encode("utf-8")).hexdigest(),
        "code_revision": code_revision,
        "source_reference_date": None,
        "publication_approved": False,
    }


def _key(identity: dict) -> str:
    raw = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(raw).hexdigest()
    return f"operations/v1/candidate-extract/{digest[:2]}/{digest}.json"


def _read_existing(store, key: str, identity: dict) -> dict | None:
    try:
        response = store.client.get_object(Bucket=store.config.bucket, Key=key)
    except Exception as exc:
        code = str(getattr(exc, "response", {}).get("Error", {}).get("Code", ""))
        if code in {"NoSuchKey", "404", "NotFound"}:
            return None
        raise
    stream = response["Body"]
    try:
        raw = stream.read(MAX_RECORD_BYTES + 1)
    finally:
        stream.close()
    if len(raw) > MAX_RECORD_BYTES:
        raise ValueError("Private extracted candidate exceeds size cap")
    payload = json.loads(raw)
    if (not isinstance(payload, dict) or payload.get("identity") != identity
            or not isinstance(payload.get("records"), list)
            or not payload["records"]
            or payload.get("review_status") != "unapproved_candidate_extraction"
            or not isinstance(payload.get("diagnostics"), dict)
            or not isinstance(payload.get("qa_flags"), list)):
        raise ValueError("Conflicting or damaged immutable candidate extraction")
    return payload


def _persist(store, key: str, payload: dict) -> dict:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                     allow_nan=False).encode("utf-8")
    if not raw or len(raw) > MAX_RECORD_BYTES:
        raise ValueError("Extracted candidate JSON exceeds private storage cap")
    try:
        store.client.put_object(Bucket=store.config.bucket, Key=key, Body=raw,
                                ContentType="application/json", IfNoneMatch="*")
    except Exception as exc:
        code = str(getattr(exc, "response", {}).get("Error", {}).get("Code", ""))
        if code not in {"PreconditionFailed", "412", "ObjectLockedByBucketPolicy", "10069"}:
            raise
    verified = _read_existing(store, key, payload["identity"])
    if verified != payload:
        raise RuntimeError("Immutable candidate extraction failed exact readback")
    return verified


def extract_one(job: dict, *, store, code_revision: str) -> dict:
    """Extract verified bytes, stage full rows privately, never rebind capture."""
    from white_list_archive.publishing import public_national_registry as registry
    identity = _identity(job, code_revision)
    key = _key(identity)
    old = _read_existing(store, key, identity)
    if old is not None:
        return {"status": "reused_candidate_extraction",
                "records": len(old["records"]), "qa_flags": old["qa_flags"],
                "private_readback": True, "publication_approved": False}
    capture = {"url": job["url"], "state": job["capture"]}
    manifest, receipt, content = _verified_capture(store, capture)
    if manifest["source_key"] != identity["capture_source_key"]:
        raise ValueError("Unbound discovery capture identity was changed")
    with tempfile.TemporaryDirectory(prefix="white-list-candidate-") as directory:
        path = Path(directory) / ("candidate" + _suffix(job["url"]))
        path.write_bytes(content)
        cfg = deepcopy(job["config"])
        cfg["reference_date"] = ""  # A download timestamp is not a source date.
        cfg["sha256"] = manifest["sha256"]
        batch = registry._parse_source(path, cfg)
    if not isinstance(batch.records, list) or not batch.records:
        raise ValueError("Candidate parser returned no rows")
    revision = _parser_revision(batch, cfg["parser"])
    flags = _quality_flags(job["config"], batch.records, batch.diagnostics)
    # A candidate may legitimately differ from approved row totals. This is
    # highlighted for review, not silently normalised or declared approved.
    payload = {
        "identity": identity,
        "review_status": "unapproved_candidate_extraction",
        "capture_id": manifest["capture_id"],
        "capture_manifest_sha256": hashlib.sha256(json.dumps(
            manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()).hexdigest(),
        "parser_revision": revision,
        "qa_flags": flags,
        "records": batch.records,
        "diagnostics": batch.diagnostics,
    }
    _persist(store, key, payload)
    return {"status": "extracted_candidate_for_review", "records": len(batch.records),
            "qa_flags": flags, "private_readback": True, "publication_approved": False}


def _public(report: dict) -> dict:
    """Closed and aggregate-only GitHub artifact; no identities or source rows."""
    return {k: report[k] for k in (
        "schema_version", "shard", "shards", "candidate_files",
        "extracted", "reused", "quarantined", "blocked", "deferred",
        "private_readback_verified", "source_quality_flags", "publications"
    )}


def main(argv: list[str] | None = None) -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--state", type=Path, required=True)
    cli.add_argument("--source-config", type=Path, required=True)
    cli.add_argument("--robot-catalog", type=Path, required=True)
    cli.add_argument("--code-revision", required=True)
    cli.add_argument("--shard", type=int, default=0)
    cli.add_argument("--shards", type=int, default=1)
    cli.add_argument("--report", type=Path, required=True)
    cli.add_argument("--public-report", type=Path, required=True)
    args = cli.parse_args(argv)
    if not _HEX40.fullmatch(args.code_revision):
        raise SystemExit("Pinned exact code revision required")
    state = json.loads(args.state.read_text())
    cfg = json.loads(args.source_config.read_text())
    robots = json.loads(args.robot_catalog.read_text())
    jobs, deferred = select_candidate_jobs(state, cfg, robots,
                                             shard=args.shard, shards=args.shards)
    store = None
    blocked = False
    if jobs:
        from white_list_archive.storage.evidence import EvidenceStore, StoreConfig, client_for
        try:
            settings = StoreConfig.from_env()
            store = EvidenceStore(client_for(settings), settings)
        except (ValueError, RuntimeError):
            blocked = True
    outcomes = []
    new_attempts = 0
    for job in jobs:
        if blocked:
            outcomes.append({"status": "blocked", "reason": "private_archive_unavailable",
                             "candidate_url": job["url"], "source_series_hypothesis": job["source_key_hypothesis"]})
            continue
        if new_attempts >= MAX_NEW_PER_SHARD:
            deferred.append({"authority_key": job["authority_key"], "candidate_url": job["url"],
                             "reason": "bounded_parsing_backlog"})
            continue
        try:
            outcome = extract_one(job, store=store, code_revision=args.code_revision)
            outcomes.append({**outcome, "candidate_url": job["url"],
                             "source_series_hypothesis": job["source_key_hypothesis"]})
            if outcome["status"] != "reused_candidate_extraction":
                new_attempts += 1
        except Exception as exc:
            # Safe diagnostic classes only; no provider messages, original rows,
            # source URLs, object keys or identifiers cross this boundary.
            outcomes.append({"status": "quarantined", "error_type": type(exc).__name__,
                             "candidate_url": job["url"],
                             "source_series_hypothesis": job["source_key_hypothesis"]})
            new_attempts += 1
    report = {
        "schema_version": 1, "run_at": datetime.now(timezone.utc).isoformat(),
        "shard": args.shard, "shards": args.shards, "candidate_files": len(jobs),
        "extracted": sum(r["status"] == "extracted_candidate_for_review" for r in outcomes),
        "reused": sum(r["status"] == "reused_candidate_extraction" for r in outcomes),
        "quarantined": sum(r["status"] == "quarantined" for r in outcomes),
        "blocked": sum(r["status"] == "blocked" for r in outcomes),
        "deferred": len(deferred), "deferred_reasons": dict(
            sorted(Counter(x["reason"] for x in deferred).items())),
        "private_readback_verified": sum(bool(r.get("private_readback")) for r in outcomes),
        "source_quality_flags": sum(bool(r.get("qa_flags")) for r in outcomes),
        "publications": 0,
        "outcomes": outcomes, "deferred_candidates": deferred,
    }
    failed_receipt = False
    if store is not None:
        try:
            persist_operational_report(store, report)
        except Exception:
            failed_receipt = True
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    args.public_report.parent.mkdir(parents=True, exist_ok=True)
    args.public_report.write_text(json.dumps(_public(report), sort_keys=True, indent=2) + "\n")
    print(json.dumps(_public(report), sort_keys=True))
    # Candidate parser incompatibilities should be visible failures but cannot
    # ever prevent another shard from collecting or parsing approved sources.
    return int(blocked or failed_receipt or report["quarantined"] > 0)


if __name__ == "__main__":
    raise SystemExit(main())
