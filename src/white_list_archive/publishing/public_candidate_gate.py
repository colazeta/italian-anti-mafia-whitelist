"""Manifest-based public candidate acceptance, independent of September record totals.

This gate is additive to strict per-source parser QA, pinned source verification,
the public schema, privacy checks and browser/link acceptance. It does not approve
a candidate or select a live Pages release.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

SEPTEMBER_PUBLIC_CONFIG_BLOB = "ee2e56c86796326d2a91d7b218d987d464c62c53"


def _approved_manifest(path: Path) -> tuple[dict, bool]:
    raw = path.read_bytes()
    blob = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
    config = json.loads(raw)
    return config, blob == SEPTEMBER_PUBLIC_CONFIG_BLOB


def validate_public_candidate(registry: dict, prefectures: dict, approved_path: Path) -> bool:
    """Validate a candidate against the *reviewed* manifest, not historical totals.

    Return True only for the exact old manifest, whose detailed 2026-09 regression
    matrix should continue to run in the caller.
    """
    config, is_september = _approved_manifest(approved_path)
    sources = config.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("Approved source manifest is empty or malformed")
    if any(not isinstance(s, dict) or not isinstance(s.get("source_key"), str) or not s["source_key"] for s in sources):
        raise ValueError("Invalid approved source key")
    by_key = {s["source_key"]: s for s in sources}
    if len(by_key) != len(sources):
        raise ValueError("Duplicate approved source key")
    if any(type(s.get("expected_source_rows")) is not int or s["expected_source_rows"] <= 0 for s in sources):
        raise ValueError("Missing approved per-source record count")
    if any(not isinstance(s.get("reference_date"), str) or not s["reference_date"] for s in sources):
        raise ValueError("Missing approved document reference date")

    records = registry["records"]
    if not isinstance(records, list):
        raise ValueError("Invalid public records")
    counts = Counter(r["source_key"] for r in records)
    expected = {k: s["expected_source_rows"] for k, s in by_key.items()}
    if dict(counts) != expected:
        raise ValueError("Public per-source record counts differ from reviewed manifest")
    locators = set()
    for row in records:
        source = by_key[row["source_key"]]
        for key in ("authority_key", "register_key", "population_scope", "reference_date"):
            if row.get(key) != source.get(key):
                raise ValueError(f"{row['source_key']}: public row {key} differs from approved source")
        for key in ("source_page_url", "resource_url"):
            if source.get(key) is not None and row.get(key) != source[key]:
                raise ValueError(f"{row['source_key']}: public row {key} differs from approved source")
        locator = row.get("record_locator")
        if not isinstance(locator, str) or not locator or locator in locators:
            raise ValueError("Missing or duplicate public record locator")
        locators.add(locator)

    reports = registry["meta"]["sources"]
    if not isinstance(reports, list) or len(reports) != len(sources):
        raise ValueError("Incomplete public source reports")
    report_by_key = {s["source_key"]: s for s in reports}
    if len(report_by_key) != len(reports) or set(report_by_key) != set(by_key):
        raise ValueError("Public source reports do not cover the manifest exactly")
    for key, source in by_key.items():
        report = report_by_key[key]
        for field in ("source_key", "authority_key", "register_key", "population_scope", "reference_date", "parser"):
            if report.get(field) != source.get(field):
                raise ValueError(f"{key}: public source report {field} mismatch")
        if source.get("approval_mode", "raw_sha256") == "raw_sha256" and report.get("sha256") != source.get("sha256"):
            raise ValueError(f"{key}: source SHA mismatch")
        if not report.get("document_checked_at"):
            raise ValueError(f"{key}: source check provenance missing")

    meta = registry["meta"]
    dimensions = {"authority": "authority_key", "register": "register_key", "status": "source_status"}
    if meta.get("record_count") != len(records) or meta.get("source_count") != len(sources):
        raise ValueError("Public record/source metadata count mismatch")
    for dimension, field in dimensions.items():
        expected_counts = dict(Counter(r[field] for r in records))
        if meta.get(f"{dimension}_counts") != expected_counts:
            raise ValueError(f"Public {dimension} counts mismatch")
        if dimension != "status" and meta.get(f"{dimension}_count") != len(expected_counts):
            raise ValueError(f"Public {dimension} distinct count mismatch")

    items = prefectures["prefectures"]
    pmeta = prefectures["meta"]
    if pmeta.get("authority_count") != len(items):
        raise ValueError("Prefecture directory count mismatch")
    names = [p["authority_key"] for p in items]
    if len(names) != len(set(names)):
        raise ValueError("Duplicate Prefecture in directory")
    published = {p["authority_key"] for p in items if p.get("published")}
    expected_authorities = {s["authority_key"] for s in sources}
    if published != expected_authorities or pmeta.get("published_count") != len(expected_authorities):
        raise ValueError("Published authorities differ from the approved manifest")
    if pmeta.get("mapped_count", 0) < pmeta["published_count"]:
        raise ValueError("Mapped Prefecture count below published count")

    return is_september
