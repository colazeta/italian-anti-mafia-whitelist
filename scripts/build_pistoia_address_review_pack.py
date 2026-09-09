from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse

import psycopg

from white_list_archive.geocoding.italian_address import MunicipalityPrefixMatcher
from white_list_archive.geocoding.national_anncsu import orchestrate
from white_list_archive.geocoding.validation import build_validation_pack
from white_list_archive.publishing.public_national_registry import (
    _download,
    _parse_source,
    _validate_batch,
)

RETRYABLE_HTTP = {408, 425, 429, 500, 502, 503, 504}
TARGET_KEYS = ("pistoia-listed", "pistoia-applicants")
TARGET_REGION = "Toscana"
TARGET_DATASET = "INDIR_TOSC"


def _download_with_retry(url: str, destination: Path, attempts: int = 4) -> str:
    for attempt in range(1, attempts + 1):
        try:
            return _download(url, destination)
        except BaseException as exc:
            if destination.exists():
                destination.unlink()
            retryable = (
                isinstance(exc, HTTPError) and exc.code in RETRYABLE_HTTP
            ) or isinstance(exc, (URLError, TimeoutError, ConnectionError, OSError))
            if not retryable or attempt == attempts:
                raise
            time.sleep(2 ** (attempt - 1))
    raise AssertionError("unreachable")


def _fingerprint_rows(rows: list[dict[str, str]], fields: list[str]) -> str:
    material = "\n".join(
        "\x1f".join(str(row.get(field, "")) for field in fields)
        for row in rows
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _load_sources(config_path: Path) -> dict[str, dict[str, object]]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    selected = {
        str(item["source_key"]): item
        for item in config["sources"]
        if item["source_key"] in TARGET_KEYS
    }
    missing = set(TARGET_KEYS) - set(selected)
    if missing:
        raise RuntimeError(f"Missing Pistoia source config: {sorted(missing)}")
    return selected


def _source_population(
    *,
    sources: dict[str, dict[str, object]],
    istat_csv: Path,
    source_dir: Path,
) -> tuple[list[str], dict[str, list[dict[str, str]]], dict[str, object]]:
    matcher = MunicipalityPrefixMatcher.from_istat_csv(istat_csv)
    occurrences: dict[str, list[dict[str, str]]] = defaultdict(list)
    source_evidence: dict[str, object] = {}
    source_dir.mkdir(parents=True, exist_ok=True)

    for source_key in TARGET_KEYS:
        cfg = sources[source_key]
        suffix = Path(urlparse(str(cfg["resource_url"])).path).suffix or ".pdf"
        local_path = source_dir / f"{source_key}{suffix}"
        observed_sha = _download_with_retry(str(cfg["resource_url"]), local_path)
        if observed_sha != str(cfg["sha256"]):
            raise RuntimeError(
                f"{source_key}: approved source SHA mismatch: {observed_sha} != {cfg['sha256']}"
            )
        batch = _parse_source(local_path, cfg)
        _validate_batch(cfg, batch)
        exact_toscana = 0
        unresolved = 0
        for record in batch.records:
            for field in ("registered_office", "secondary_office"):
                address = " ".join(str(record.get(field) or "").split())
                if not address:
                    continue
                split = matcher.split(address)
                if not split.split or split.status != "exact" or split.split.municipality.region_name != TARGET_REGION:
                    unresolved += 1
                    continue
                exact_toscana += 1
                occurrences[address].append(
                    {
                        "source_key": source_key,
                        "population_scope": str(cfg["population_scope"]),
                        "record_locator": str(record.get("record_locator") or ""),
                        "entity_name": str(record.get("name") or ""),
                        "address_field": field,
                        "source_page_url": str(cfg["source_page_url"]),
                        "resource_url": str(cfg["resource_url"]),
                        "capture_sha256": observed_sha,
                    }
                )
        source_evidence[source_key] = {
            "authority_key": cfg["authority_key"],
            "population_scope": cfg["population_scope"],
            "reference_date": cfg["reference_date"],
            "resource_url": cfg["resource_url"],
            "capture_sha256": observed_sha,
            "parsed_records": len(batch.records),
            "exact_toscana_address_occurrences": exact_toscana,
            "non_exact_or_non_toscana_occurrences": unresolved,
        }

    addresses = sorted(occurrences)
    if not addresses:
        raise RuntimeError("Pistoia source-backed address population is empty")
    return addresses, occurrences, source_evidence


def _insert_population(dsn: str, addresses: list[str]) -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO provenance.processing_activity(
                activity_type_code,software_name,software_version,
                configuration_hash,started_at,completed_at
            ) VALUES ('normalise','pistoia-address-review-fixture','1',%s,%s,%s)
            RETURNING processing_activity_id
            """,
            (hashlib.sha256("\n".join(addresses).encode()).hexdigest(), now, now),
        )
        activity_id = cur.fetchone()[0]
        for address in addresses:
            cur.execute(
                "INSERT INTO core.address(full_address,country_code,processing_activity_id) VALUES (%s,NULL,%s)",
                (address, activity_id),
            )
        conn.commit()


def _write_review_evidence(
    *,
    validation_dir: Path,
    occurrences: dict[str, list[dict[str, str]]],
    output: Path,
) -> dict[str, object]:
    sample_path = validation_dir / "manual_review_sample.csv"
    with sample_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    extra_fields = [
        "source_occurrence_count",
        "source_keys",
        "population_scopes",
        "record_locators",
        "entity_names",
        "address_fields",
        "source_page_urls",
        "resource_urls",
        "capture_sha256s",
    ]
    fieldnames = list(rows[0]) + extra_fields if rows else extra_fields
    enriched: list[dict[str, str]] = []
    missing = []
    for row in rows:
        evidence = occurrences.get(row["source_address"], [])
        if not evidence:
            missing.append(row["source_address"])
        item = dict(row)
        item.update(
            {
                "source_occurrence_count": str(len(evidence)),
                "source_keys": " | ".join(sorted({x["source_key"] for x in evidence})),
                "population_scopes": " | ".join(sorted({x["population_scope"] for x in evidence})),
                "record_locators": " | ".join(x["record_locator"] for x in evidence),
                "entity_names": " | ".join(x["entity_name"] for x in evidence),
                "address_fields": " | ".join(x["address_field"] for x in evidence),
                "source_page_urls": " | ".join(sorted({x["source_page_url"] for x in evidence})),
                "resource_urls": " | ".join(sorted({x["resource_url"] for x in evidence})),
                "capture_sha256s": " | ".join(sorted({x["capture_sha256"] for x in evidence})),
            }
        )
        enriched.append(item)
    if missing:
        raise RuntimeError(f"Review rows lack deterministic source provenance: {missing[:5]}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(enriched)
    return {
        "review_rows": len(enriched),
        "rows_with_source_evidence": sum(int(x["source_occurrence_count"]) > 0 for x in enriched),
        "sample_sha256": _fingerprint_rows(
            enriched,
            ["address_id", "source_address", "review_stratum", "sampling_weight", "capture_sha256s"],
        ),
    }


def build_pack(args: argparse.Namespace) -> dict[str, object]:
    sources = _load_sources(args.source_config)
    addresses, occurrences, source_evidence = _source_population(
        sources=sources,
        istat_csv=args.istat_csv,
        source_dir=args.output_dir / "source-pdfs",
    )
    _insert_population(args.dsn, addresses)
    orchestration = orchestrate(
        dsn=args.dsn,
        istat_csv=args.istat_csv,
        istat_manifest=args.istat_manifest,
        cache_dir=args.cache_dir,
    )
    regions = orchestration["regions"]
    if len(regions) != 1 or regions[0]["dataset_code"] != TARGET_DATASET:
        raise RuntimeError(f"Pistoia replication must require only {TARGET_DATASET}: {regions}")
    if orchestration["plan"]["assignable_addresses"] != len(addresses):
        raise RuntimeError(f"Not all Pistoia exact addresses were region-assigned: {orchestration['plan']}")
    if orchestration["candidate"] + orchestration["not_found"] != len(addresses):
        raise RuntimeError("Pistoia ANNCSU accounting does not reconcile")
    if orchestration["public_nominatim_used"]:
        raise RuntimeError("Pistoia replication unexpectedly used public Nominatim")

    provider_endpoint = regions[0]["source_url"]
    validation_dir = args.output_dir / "validation"
    validation = build_validation_pack(
        dsn=args.dsn,
        output_dir=validation_dir,
        provider_name="anncsu",
        provider_endpoint=provider_endpoint,
        sample_size=args.sample_size,
    )
    evidence_summary = _write_review_evidence(
        validation_dir=validation_dir,
        occurrences=occurrences,
        output=args.output_dir / "pistoia-review-sample.csv",
    )

    with (args.output_dir / "source-occurrences.csv").open("w", encoding="utf-8", newline="") as handle:
        fields = ["source_address", "source_key", "population_scope", "record_locator", "entity_name", "address_field", "source_page_url", "resource_url", "capture_sha256"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for address in sorted(occurrences):
            for evidence in occurrences[address]:
                writer.writerow({"source_address": address, **evidence})

    payload: dict[str, object] = {
        "prefecture": "Pistoia",
        "region": TARGET_REGION,
        "dataset_code": TARGET_DATASET,
        "policy": "frozen exact Istat municipality + ANNCSU typed-street/civic linkage; no local hand tuning",
        "source_evidence": source_evidence,
        "unique_source_backed_addresses": len(addresses),
        "source_occurrences": sum(len(values) for values in occurrences.values()),
        "orchestration": orchestration,
        "validation": validation,
        "review": evidence_summary,
        "review_status": "PACK_READY_REQUIRES_SUBSTANTIVE_REVIEW",
        "automatic_acceptance_changed": False,
    }
    (args.output_dir / "pistoia-review-manifest.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the source-backed Pistoia/Toscana ANNCSU replication review pack.")
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--istat-csv", type=Path, required=True)
    parser.add_argument("--istat-manifest", type=Path, required=True)
    parser.add_argument("--source-config", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--sample-size", type=int, default=150)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    payload = build_pack(args)
    print(json.dumps({
        "prefecture": payload["prefecture"],
        "addresses": payload["unique_source_backed_addresses"],
        "candidate": payload["orchestration"]["candidate"],
        "not_found": payload["orchestration"]["not_found"],
        "review": payload["review"],
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
