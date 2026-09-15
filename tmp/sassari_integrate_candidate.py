from __future__ import annotations

import csv
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = "https://prefettura.interno.gov.it/it/prefetture/sassari/evidenza/white-list"
RESOURCE = "https://prefettura.interno.gov.it/sites/default/files/93/2026-08/2026-elenco-provinciale-aggiornato-al-31.08.2026.xlsx"
SHA256 = "e5cf9776971e4c0b46b97c56e2764f906bd07e3d573ac07b59fcd6605ab9c370"


def replace_exact(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected exactly one replacement in {path}: {old!r}; found {count}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def update_verified_page() -> None:
    path = ROOT / "data/source_registry/verified_primary_pages.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames
        if fieldnames is None:
            raise RuntimeError("Missing verified-page header")
        rows = list(reader)
    matches = [row for row in rows if row["authority_key"] == "sassari"]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one Sassari verified-page row, found {len(matches)}")
    row = matches[0]
    if row["landing_url"] != PAGE or row["verification_status"] != "verified":
        raise RuntimeError(f"Unexpected Sassari verified-page state: {row!r}")
    row["verification_date"] = "2026-09-15"
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(out.getvalue(), encoding="utf-8")


def update_source_registry() -> None:
    path = ROOT / "data/source_registry/source_series_inventory.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames
        if fieldnames is None:
            raise RuntimeError("Missing source-series header")
        rows = list(reader)
    matches = [row for row in rows if row["authority_key"] == "sassari"]
    if matches:
        raise RuntimeError(f"Sassari source series already exist: {[row['source_series_key'] for row in matches]!r}")
    rows.append(
        {
            "source_series_key": "sassari-combined",
            "authority_key": "sassari",
            "regime_code": "WL-REGIME-L190-2012",
            "population_scope": "listed_and_applicant",
            "sector_scope": "all",
            "publication_model": "periodic_attachment",
            "series_url": PAGE,
            "resource_resolution_status": "landing_page_resolved",
            "verified_date": "2026-09-15",
            "notes": (
                "Current official Sassari White List page and combined workbook directly revalidated 15 September 2026 by two byte-identical no-cache GETs. "
                "The byte-pinned 31 August edition exposes listed, first-time applicant and renewal/update semantics in one physical table and yields exactly 478 source observations. "
                "Malformed dates, malformed identifiers, the reviewed apparent office/identifier column swap and nonstandard source statuses remain source-faithful and uninferred; exact evidence is documented in docs/sources/sassari-operational-check-2026-09-15.md."
            ),
        }
    )
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(out.getvalue(), encoding="utf-8")


def update_monitoring() -> None:
    path = ROOT / "data/monitoring/national_coverage.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    matches = [item for item in data["prefectures"] if item.get("authority_key") == "sassari"]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one Sassari monitoring entry, found {len(matches)}")
    item = matches[0]
    if item.get("public_export_enabled") or item.get("parser_validated"):
        raise RuntimeError("Sassari monitoring entry is already promoted; refusing duplicate transaction")
    item.update(
        {
            "official_landing_page": PAGE,
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
            "latest_source_reference_date": "2026-08-31",
            "last_successful_investigation_on": "2026-09-15",
            "unresolved_issue": [
                "Canonical hosted-database integration and independent durable-evidence verification remain governed under #16; public source observations are validated independently of that infrastructure."
            ],
            "actionable_issue": False,
            "coverage_status": "VALIDATED",
            "terminal_reason": None,
            "completion_evidence": [
                "docs/sources/sassari-operational-check-2026-09-15.md",
                "src/white_list_archive/parsers/sassari_openxml.py",
                "tests/test_sassari_parser_semantics.py",
                "data/publication/multi_prefecture_pilot.json",
            ],
            "known_content_sha256": [SHA256],
            "evidence": [
                "data/source_registry/verified_primary_pages.csv",
                "data/source_registry/source_series_inventory.csv",
                "data/publication/multi_prefecture_pilot.json",
                "docs/sources/sassari-operational-check-2026-09-15.md",
            ],
            "last_completed_coverage_stage": "VALIDATED",
        }
    )
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_publication_config() -> None:
    path = ROOT / "data/publication/multi_prefecture_pilot.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    sources = data["sources"]
    if any(item.get("authority_key") == "sassari" for item in sources):
        raise RuntimeError("Sassari already exists in publication configuration")
    sources.append(
        {
            "source_key": "sassari-combined",
            "parser": "sassari_combined",
            "authority_key": "sassari",
            "authority_name": "Prefettura di Sassari",
            "register_key": "sassari-ordinary",
            "register_name": "White List — Prefettura di Sassari",
            "population_scope": "listed_and_applicant",
            "reference_date": "2026-08-31",
            "source_page_url": PAGE,
            "resource_url": RESOURCE,
            "sha256": SHA256,
            "expected_source_rows": 478,
            "last_source_update": "2026-08-31",
            "last_source_update_basis": "date embedded in the current official workbook filename; used only as the source-edition boundary and not as an inferred company decision, registration, application or legal-effect date",
            "notes": (
                "Official combined workbook revalidated 15 September 2026 by two byte-identical no-cache GETs. "
                "The fail-closed parser yields exactly 478 observations: 335 listed, 129 pending, 12 renewal/update in progress, one source-explicit expired observation and one other/unknown observation with no inferred status. "
                "Strict identifier coverage is 472/478; reviewed malformed identifier/date fields and the apparent office/identifier column swap are preserved without repair."
            ),
        }
    )
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def bind_parser() -> None:
    path = ROOT / "src/white_list_archive/publishing/public_national_registry.py"
    replace_exact(
        path,
        "from white_list_archive.parsers.lecco_rect_tables import PARSERS as LECCO_PARSERS\n",
        "from white_list_archive.parsers.lecco_rect_tables import PARSERS as LECCO_PARSERS\nfrom white_list_archive.parsers.sassari_openxml import PARSERS as SASSARI_PARSERS\n",
    )
    replace_exact(
        path,
        '        or LECCO_PARSERS.get(cfg["parser"])\n',
        '        or LECCO_PARSERS.get(cfg["parser"])\n        or SASSARI_PARSERS.get(cfg["parser"])\n',
    )


def update_population_regression() -> None:
    path = ROOT / "tests/test_source_population_coverage.py"
    replace_exact(path, '    assert report["complete_register_scope_count"] == 46\n', '    assert report["complete_register_scope_count"] == 47\n')
    replace_exact(path, '    assert report["incomplete_register_scope_count"] == 2\n', '    assert report["incomplete_register_scope_count"] == 1\n')
    replace_exact(path, '    assert unresolved == {"milano", "sassari"}\n', '    assert unresolved == {"milano"}\n')
    marker = "    assert all(row[\"covering_series_keys\"] == [\"forli-cesena-combined\"] for row in forli)\n"
    addition = marker + "\n    sassari = [\n        row\n        for row in report[\"rows\"]\n        if row[\"authority_key\"] == \"sassari\"\n        and row[\"regime_code\"] == \"WL-REGIME-L190-2012\"\n    ]\n    assert {row[\"coverage_status\"] for row in sassari} == {\"COVERED_COMBINED_SERIES\"}\n    assert all(row[\"covering_series_keys\"] == [\"sassari-combined\"] for row in sassari)\n"
    replace_exact(path, marker, addition)


def main() -> None:
    update_verified_page()
    update_source_registry()
    update_monitoring()
    update_publication_config()
    bind_parser()
    update_population_regression()
    print("Sassari national candidate transaction applied to working tree")


if __name__ == "__main__":
    main()
