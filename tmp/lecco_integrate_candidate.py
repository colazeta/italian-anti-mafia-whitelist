from __future__ import annotations

import csv
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = "https://prefettura.interno.gov.it/it/prefetture/lecco/white-list-elenco-imprese-iscritte"
LISTED_URL = "https://prefettura.interno.gov.it/sites/default/files/56/2026-09/all_a-attivita-elenco-ditte-non-soggette-a-tentativo-infiltr_mafiosa_2.pdf"
APPLICANT_URL = "https://prefettura.interno.gov.it/sites/default/files/56/2026-09/all_b-attivita-elenco-ditte-richiedenti-iscrizione_2.pdf"
LISTED_SHA = "80c439521cf2bd4062b54fff3646666487367f0f8b47c1a91a6c8f62bcf8e5bc"
APPLICANT_SHA = "7c24e015342cc2cb61cf4b5bf726621c8b3b90b195cd91c40942fc3ef6b6ba5b"


def replace_exact(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected exactly one replacement in {path}: {old!r}; found {count}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def append_csv_row(path: Path, row: list[str], *, unique_key: str) -> None:
    text = path.read_text(encoding="utf-8")
    if unique_key in text:
        raise RuntimeError(f"Refusing duplicate candidate row in {path}: {unique_key}")
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(row)
    if text and not text.endswith("\n"):
        text += "\n"
    path.write_text(text + out.getvalue(), encoding="utf-8")


def update_catalog() -> None:
    path = ROOT / "data/catalog.csv"
    replace_exact(
        path,
        "verified-primary-pages,source_registry,data/source_registry/verified_primary_pages.csv,csv,national,in_progress,verified_primary_page,46,false,internal_research,Independently verified primary White List landing pages.",
        "verified-primary-pages,source_registry,data/source_registry/verified_primary_pages.csv,csv,national,in_progress,verified_primary_page,47,false,internal_research,Independently verified primary White List landing pages.",
    )
    replace_exact(
        path,
        "source-series-inventory,source_registry,data/source_registry/source_series_inventory.csv,csv,national,in_progress,source_series,88,false,internal_research,Qualified recurring White List publication series and publication models.",
        "source-series-inventory,source_registry,data/source_registry/source_series_inventory.csv,csv,national,in_progress,source_series,90,false,internal_research,Qualified recurring White List publication series and publication models.",
    )


def update_source_registry() -> None:
    pages = ROOT / "data/source_registry/verified_primary_pages.csv"
    append_csv_row(
        pages,
        ["lecco", PAGE, "2026-09-15", "verified"],
        unique_key="lecco,",
    )

    series = ROOT / "data/source_registry/source_series_inventory.csv"
    append_csv_row(
        series,
        [
            "lecco-listed",
            "lecco",
            "WL-REGIME-L190-2012",
            "listed",
            "all",
            "periodic_attachment",
            PAGE,
            "landing_page_resolved",
            "2026-09-15",
            "Current official Lecco page and Allegato A directly revalidated 15 September 2026. The byte-pinned 14 September edition yields exactly 230 listed-side observations: 201 listed and 29 renewal/update in progress. Two malformed source identifiers and the single genuinely blank activity cell for Termoidraulica are preserved without inferential repair; exact evidence is documented in docs/sources/lecco-operational-check-2026-09-15.md.",
        ],
        unique_key="lecco-listed,",
    )
    append_csv_row(
        series,
        [
            "lecco-applicants",
            "lecco",
            "WL-REGIME-L190-2012",
            "applicant",
            "all",
            "periodic_attachment",
            PAGE,
            "landing_page_resolved",
            "2026-09-15",
            "Current official Lecco page and Allegato B directly revalidated 15 September 2026. The byte-pinned 14 September edition yields exactly 26 applicant-event observations: 22 pending and 4 rejected/denied. Repeated Edilnord applications remain three distinct positively evidenced events; exact evidence is documented in docs/sources/lecco-operational-check-2026-09-15.md.",
        ],
        unique_key="lecco-applicants,",
    )


def update_monitoring() -> None:
    path = ROOT / "data/monitoring/national_coverage.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    matches = [item for item in data["prefectures"] if item.get("authority_key") == "lecco"]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one Lecco monitoring entry, found {len(matches)}")
    item = matches[0]
    if item.get("public_export_enabled") or item.get("parser_validated"):
        raise RuntimeError("Lecco monitoring entry is already promoted; refusing duplicate transaction")
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
            "latest_source_reference_date": "2026-09-14",
            "last_successful_investigation_on": "2026-09-15",
            "unresolved_issue": [
                "Canonical hosted-database integration and independent durable-evidence verification remain governed under #16; public source observations are validated independently of that infrastructure."
            ],
            "actionable_issue": False,
            "coverage_status": "VALIDATED",
            "terminal_reason": None,
            "completion_evidence": [
                "docs/sources/lecco-operational-check-2026-09-15.md",
                "src/white_list_archive/parsers/lecco_rect_tables.py",
                "tests/test_lecco_parser_semantics.py",
                "data/publication/multi_prefecture_pilot.json",
            ],
            "known_content_sha256": [LISTED_SHA, APPLICANT_SHA],
            "evidence": [
                "data/source_registry/verified_primary_pages.csv",
                "data/source_registry/source_series_inventory.csv",
                "data/publication/multi_prefecture_pilot.json",
                "docs/sources/lecco-operational-check-2026-09-15.md",
            ],
            "last_completed_coverage_stage": "VALIDATED",
        }
    )
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_publication_config() -> None:
    path = ROOT / "data/publication/multi_prefecture_pilot.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    sources = data["sources"]
    if any(item.get("authority_key") == "lecco" for item in sources):
        raise RuntimeError("Lecco already exists in publication configuration")
    common = {
        "authority_key": "lecco",
        "authority_name": "Prefettura di Lecco",
        "register_key": "lecco-ordinary",
        "register_name": "White List — Prefettura di Lecco",
        "reference_date": "2026-09-14",
        "last_source_update": "2026-09-14",
        "last_source_update_basis": "edition date explicitly stated by the two current official attachment labels; used only as the current source-edition boundary and not as an inferred company decision, registration or legal-effect date",
        "source_page_url": PAGE,
    }
    sources.extend(
        [
            {
                **common,
                "source_key": "lecco-listed",
                "parser": "lecco_listed",
                "population_scope": "listed",
                "resource_url": LISTED_URL,
                "sha256": LISTED_SHA,
                "expected_source_rows": 230,
                "notes": "Official Allegato A revalidated 15 September 2026 by two byte-identical independent GETs. The fail-closed 19-page geometry parser yields exactly 230 listed-side observations: 201 listed and 29 renewal/update in progress. Strict identifier coverage is 228/230; malformed source identifiers and the reviewed blank Termoidraulica activity cell remain raw and uninferred.",
            },
            {
                **common,
                "source_key": "lecco-applicants",
                "parser": "lecco_applicants",
                "population_scope": "applicant",
                "resource_url": APPLICANT_URL,
                "sha256": APPLICANT_SHA,
                "expected_source_rows": 26,
                "notes": "Official Allegato B revalidated 15 September 2026 by two byte-identical independent GETs. The fail-closed four-page geometry parser yields exactly 26 applicant-event observations: 22 pending and 4 rejected/denied, all with strict identifiers. Edilnord SRL remains three distinct source-backed application/denial events rather than being collapsed by identifier.",
            },
        ]
    )
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def bind_parser() -> None:
    path = ROOT / "src/white_list_archive/publishing/public_national_registry.py"
    replace_exact(
        path,
        "from white_list_archive.parsers.catanzaro_tables import PARSERS as CATANZARO_PARSERS\n",
        "from white_list_archive.parsers.catanzaro_tables import PARSERS as CATANZARO_PARSERS\nfrom white_list_archive.parsers.lecco_rect_tables import PARSERS as LECCO_PARSERS\n",
    )
    replace_exact(
        path,
        '        or CATANZARO_PARSERS.get(cfg["parser"])\n',
        '        or CATANZARO_PARSERS.get(cfg["parser"])\n        or LECCO_PARSERS.get(cfg["parser"])\n',
    )


def update_governance_tests() -> None:
    replace_exact(
        ROOT / "tests/test_source_registry.py",
        "    assert len(pages) == 46\n",
        "    assert len(pages) == 47\n",
    )
    path = ROOT / "tests/test_source_population_coverage.py"
    replace_exact(path, '    assert report["verified_authority_count"] == 46\n', '    assert report["verified_authority_count"] == 47\n')
    replace_exact(path, '    assert report["register_scope_count"] == 47\n', '    assert report["register_scope_count"] == 48\n')
    replace_exact(path, '    assert report["complete_register_scope_count"] == 45\n', '    assert report["complete_register_scope_count"] == 46\n')


def main() -> None:
    update_catalog()
    update_source_registry()
    update_monitoring()
    update_publication_config()
    bind_parser()
    update_governance_tests()
    print("Lecco national candidate transaction applied to working tree")


if __name__ == "__main__":
    main()
