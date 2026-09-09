"""Build deliberately public GitHub Actions verification records.

The repository is public.  Workflow artifacts are therefore publication surfaces,
not a place to retain internal review bundles or source-evidence bytes.  This
module converts richer ephemeral validation outputs into small aggregate records
that are safe to upload while retaining cryptographic bindings to the internal
material that was actually checked during the job.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
PUBLICATION_CLASS = "public_operational_verification"


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _file_binding(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "sha256": hashlib.sha256(data).hexdigest(),
        "byte_size": len(data),
    }


def _base(workflow: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "publication_class": PUBLICATION_CLASS,
        "workflow": workflow,
        "status": "VERIFIED",
    }


def cosenza_content_verification(
    *,
    capture_manifest: Path,
    v2_summary: Path,
    semantic: Path,
    population: Path,
    coverage: Path,
) -> dict[str, Any]:
    captures = _read_json(capture_manifest)
    if not isinstance(captures, list) or not captures:
        raise ValueError("Cosenza capture manifest must contain a non-empty edition list")
    editions = []
    for item in sorted(captures, key=lambda row: str(row.get("reference_date", ""))):
        required = ("reference_date", "sha256", "text_sha256", "schema_fingerprint", "page_count")
        if any(key not in item for key in required):
            raise ValueError("Cosenza capture identity is incomplete")
        editions.append({key: item[key] for key in required})

    v2 = _read_json(v2_summary)
    sem = _read_json(semantic)
    cov = _read_json(coverage)
    record = _base("cosenza-content-capture")
    record.update(
        {
            "source_editions": editions,
            "parser_v2": {
                "records": v2.get("records"),
                "structured_field_coverage": v2.get("structured_field_coverage"),
            },
            "semantic_pipeline": {
                "semantic_projection": sem.get("semantic_projection"),
                "canonicalisation": sem.get("canonicalisation"),
            },
            "source_population_coverage": {
                key: cov.get(key)
                for key in (
                    "required_populations",
                    "verified_authority_count",
                    "register_scope_count",
                    "complete_register_scope_count",
                    "incomplete_register_scope_count",
                )
            },
            "internal_output_bindings": {
                "model_population": _file_binding(population),
                "coverage_ledger": _file_binding(coverage),
                "parser_v2_summary": _file_binding(v2_summary),
                "semantic_pipeline": _file_binding(semantic),
            },
            "internal_bundle_uploaded": False,
            "source_pdf_uploaded": False,
        }
    )
    return record


def cosenza_address_verification(
    *,
    summary: Path,
    review_sample: Path,
    address_results: Path,
    frozen_review_summary: Path,
) -> dict[str, Any]:
    current = _read_json(summary)
    frozen = _read_json(frozen_review_summary)
    record = _base("cosenza-address-validation")
    record.update(
        {
            "operational": {
                key: current.get(key)
                for key in (
                    "total_canonical_addresses",
                    "addresses_with_provider_match",
                    "match_rate_pct",
                    "not_found",
                    "not_found_rate_pct",
                    "errors",
                    "error_rate_pct",
                    "unprocessed",
                    "unprocessed_rate_pct",
                    "status_counts",
                    "precision_counts",
                    "country_route_counts",
                    "source_country_counts",
                    "derived_country_counts",
                    "effective_country_counts",
                    "source_provider_country_conflicts",
                )
            },
            "frozen_review": {
                key: frozen.get(key)
                for key in (
                    "review_rows",
                    "population",
                    "candidate_population",
                    "candidate_sample_rows",
                    "candidate_review_complete",
                    "candidate_weighted_precision_pct",
                    "candidate_coverage_pct",
                    "estimated_validated_yield_pct",
                    "precision_excludes_not_found",
                    "strata",
                )
            },
            "internal_output_bindings": {
                "validation_summary": _file_binding(summary),
                "review_sample": _file_binding(review_sample),
                "full_address_results": _file_binding(address_results),
                "frozen_review_summary": _file_binding(frozen_review_summary),
            },
            "internal_review_rows_uploaded": False,
            "source_pdf_uploaded": False,
        }
    )
    return record


def pistoia_verification(*, manifest: Path, review_sample: Path) -> dict[str, Any]:
    value = _read_json(manifest)
    orchestration = value.get("orchestration") or {}
    sources = value.get("source_evidence") or {}
    source_identities: dict[str, Any] = {}
    for key, item in sorted(sources.items()):
        source_identities[key] = {
            field: item.get(field)
            for field in (
                "population_scope",
                "reference_date",
                "capture_sha256",
                "parsed_records",
                "exact_toscana_address_occurrences",
                "non_exact_or_non_toscana_occurrences",
            )
        }
    regions = []
    for item in orchestration.get("regions") or []:
        regions.append(
            {
                key: item.get(key)
                for key in (
                    "dataset_code",
                    "provider_version",
                    "zip_sha256",
                    "csv_sha256",
                    "planned_address_count",
                    "processed_address_count",
                    "candidate",
                    "not_found",
                    "skipped_existing_count",
                )
            }
        )
    review = value.get("review") or {}
    validation = value.get("validation") or {}
    record = _base("pistoia-address-replication")
    record.update(
        {
            "prefecture": value.get("prefecture"),
            "region": value.get("region"),
            "dataset_code": value.get("dataset_code"),
            "source_identities": source_identities,
            "unique_source_backed_addresses": value.get("unique_source_backed_addresses"),
            "orchestration": {
                "candidate": orchestration.get("candidate"),
                "not_found": orchestration.get("not_found"),
                "processed_address_count": orchestration.get("processed_address_count"),
                "all_processed_addresses_accounted_for": orchestration.get(
                    "all_processed_addresses_accounted_for"
                ),
                "public_nominatim_used": orchestration.get("public_nominatim_used"),
                "regions": regions,
            },
            "review": {
                "review_rows": review.get("review_rows"),
                "rows_with_source_evidence": review.get("rows_with_source_evidence"),
                "sample_sha256": review.get("sample_sha256"),
                "database_uuid_independent": review.get("database_uuid_independent"),
                "review_strata": validation.get("review_strata"),
                "review_status": value.get("review_status"),
            },
            "internal_output_bindings": {
                "review_manifest": _file_binding(manifest),
                "review_sample": _file_binding(review_sample),
            },
            "internal_review_rows_uploaded": False,
            "source_pdf_uploaded": False,
        }
    )
    return record


def anncsu_verification(*, summary: Path) -> dict[str, Any]:
    value = _read_json(summary)
    allowed = (
        "catalogue_dataset_codes_verified",
        "validated_prefectures",
        "validated_regions",
        "provider_datasets",
        "run_count",
        "first_run_processed",
        "same_version_second_run_processed",
        "new_address_third_run_processed",
        "public_nominatim_used",
    )
    record = _base("national-anncsu-orchestration-validation")
    record.update({key: value.get(key) for key in allowed})
    record["internal_output_bindings"] = {"live_validation_summary": _file_binding(summary)}
    record["internal_fixture_uploaded"] = False
    return record


def fallback_verification(*, summary: Path) -> dict[str, Any]:
    value = _read_json(summary)
    if value.get("status") != "VERIFIED":
        raise ValueError("Fallback verification summary is not VERIFIED")
    record = _base("fallback-geocoding-validation")
    record.update(
        {
            key: value.get(key)
            for key in (
                "routing_reasons_tested",
                "same_version_cache_reuse_verified",
                "new_address_incremental_refresh_verified",
                "provider_version_refresh_verified",
                "stale_fallback_expiration_verified",
                "public_osmf_used",
                "automatic_acceptance",
                "database",
                "network",
            )
        }
    )
    record["fixture_class"] = "synthetic_deterministic"
    record["internal_output_bindings"] = {"verification_summary": _file_binding(summary)}
    record["request_log_uploaded"] = False
    return record


def _write(output: Path, record: dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(record, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="profile", required=True)

    p = sub.add_parser("cosenza-content")
    p.add_argument("--capture-manifest", type=Path, required=True)
    p.add_argument("--v2-summary", type=Path, required=True)
    p.add_argument("--semantic", type=Path, required=True)
    p.add_argument("--population", type=Path, required=True)
    p.add_argument("--coverage", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)

    p = sub.add_parser("cosenza-address")
    p.add_argument("--summary", type=Path, required=True)
    p.add_argument("--review-sample", type=Path, required=True)
    p.add_argument("--address-results", type=Path, required=True)
    p.add_argument("--frozen-review-summary", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)

    p = sub.add_parser("pistoia")
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--review-sample", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)

    p = sub.add_parser("anncsu")
    p.add_argument("--summary", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)

    p = sub.add_parser("fallback")
    p.add_argument("--summary", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)

    args = parser.parse_args()
    if args.profile == "cosenza-content":
        record = cosenza_content_verification(
            capture_manifest=args.capture_manifest,
            v2_summary=args.v2_summary,
            semantic=args.semantic,
            population=args.population,
            coverage=args.coverage,
        )
    elif args.profile == "cosenza-address":
        record = cosenza_address_verification(
            summary=args.summary,
            review_sample=args.review_sample,
            address_results=args.address_results,
            frozen_review_summary=args.frozen_review_summary,
        )
    elif args.profile == "pistoia":
        record = pistoia_verification(manifest=args.manifest, review_sample=args.review_sample)
    elif args.profile == "anncsu":
        record = anncsu_verification(summary=args.summary)
    else:
        record = fallback_verification(summary=args.summary)
    _write(args.output, record)
    print(json.dumps(record, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
