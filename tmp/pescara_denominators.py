from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_exact(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text and old not in text:
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected exactly one occurrence in {path}: {old!r}; found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_monitoring() -> None:
    path = ROOT / "data/monitoring/national_coverage.json"
    ledger = json.loads(path.read_text(encoding="utf-8"))
    rows = [row for row in ledger["prefectures"] if row["authority_key"] == "pescara"]
    if len(rows) != 1:
        raise RuntimeError(f"Expected one Pescara monitoring row, found {len(rows)}")
    row = rows[0]
    row.update(
        {
            "official_landing_page": "https://prefettura.interno.gov.it/it/prefetture/pescara/evidenza/white-list",
            "source_verified": True,
            "current_edition_identified": True,
            "capture_implemented": True,
            "parser_implemented": True,
            "parser_validated": True,
            "company_observations_loaded": True,
            "observation_layer": "public_source_observations",
            "canonical_integration_validated": False,
            "public_export_enabled": True,
            "durable_evidence_verified": False,
            "population_scopes_complete": True,
            "latest_source_reference_date": "2026-09-16",
            "last_successful_investigation_on": "2026-09-21",
            "monitoring_status": "CURRENT",
            "unresolved_issue": [
                "Canonical hosted-database integration and independent durable-evidence verification remain governed under #16; public source observations are validated independently of that infrastructure."
            ],
            "actionable_issue": False,
            "coverage_status": "VALIDATED",
            "terminal_reason": None,
            "completion_evidence": [
                "docs/sources/pescara-operational-check-2026-09-21.md",
                "src/white_list_archive/parsers/pescara_legacy_doc.py",
                "tests/test_pescara_legacy_doc.py",
                "data/publication/multi_prefecture_pilot.json",
            ],
            "known_content_sha256": [
                "6a8aa832db7d0f55c17d9ed1f8179d9ed46a7c927b5b88d85319f79a1da92239",
                "2a0f74ab6548ad2418f539aba7fc2eaf0d23998b709b0bc247e512d7b46a578c",
            ],
            "evidence": [
                "data/source_registry/verified_primary_pages.csv",
                "data/source_registry/source_series_inventory.csv",
                "data/publication/multi_prefecture_pilot.json",
                "docs/sources/pescara-operational-check-2026-09-21.md",
            ],
            "last_completed_coverage_stage": "VALIDATED",
        }
    )
    path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def patch_catalog() -> None:
    path = ROOT / "data/catalog.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    wanted = {"verified-primary-pages": "71", "source-series-inventory": "141"}
    seen: set[str] = set()
    for row in rows:
        dataset_id = row["dataset_id"]
        if dataset_id in wanted:
            old = row["record_count"]
            if old not in ({"verified-primary-pages": "70", "source-series-inventory": "139"}[dataset_id], wanted[dataset_id]):
                raise RuntimeError(f"Unexpected catalog baseline for {dataset_id}: {old}")
            row["record_count"] = wanted[dataset_id]
            seen.add(dataset_id)
    if seen != set(wanted):
        raise RuntimeError(f"Missing catalog rows: {set(wanted) - seen}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def patch_tests() -> None:
    replace_exact(
        ROOT / "tests/test_source_population_coverage.py",
        '    assert report["verified_authority_count"] == 70\n    assert report["register_scope_count"] == 73\n    assert report["complete_register_scope_count"] == 73\n',
        '    assert report["verified_authority_count"] == 71\n    assert report["register_scope_count"] == 74\n    assert report["complete_register_scope_count"] == 74\n',
    )
    replace_exact(
        ROOT / "tests/test_source_registry.py",
        "    assert len(pages) == 70\n",
        "    assert len(pages) == 71\n",
    )


if __name__ == "__main__":
    patch_monitoring()
    patch_catalog()
    patch_tests()
