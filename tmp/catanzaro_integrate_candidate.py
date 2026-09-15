from __future__ import annotations

import csv
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = "https://prefettura.interno.gov.it/it/prefetture/catanzaro/provvedimenti-whitelist-elenchi"
LISTED_URL = "https://prefettura.interno.gov.it/sites/default/files/0/2026-09/elencoditteiscritteinwhitelistal10092026.pdf"
APPLICANT_URL = "https://prefettura.interno.gov.it/sites/default/files/0/2026-09/elencoditterichiedentiiscrizioneinwhitelistal10092026.pdf"
LISTED_SHA = "8578a1b2d3ef0e2d71f1133381082d63d131182fd1b74c456cffe708ed94df7f"
APPLICANT_SHA = "8c5b0ea684b20f0893016e4a528bac57fb2b05c40aa9669340bdf7bd7dab115c"


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
        "verified-primary-pages,source_registry,data/source_registry/verified_primary_pages.csv,csv,national,in_progress,verified_primary_page,45,false,internal_research,Independently verified primary White List landing pages.",
        "verified-primary-pages,source_registry,data/source_registry/verified_primary_pages.csv,csv,national,in_progress,verified_primary_page,46,false,internal_research,Independently verified primary White List landing pages.",
    )
    replace_exact(
        path,
        "source-series-inventory,source_registry,data/source_registry/source_series_inventory.csv,csv,national,in_progress,source_series,86,false,internal_research,Qualified recurring White List publication series and publication models.",
        "source-series-inventory,source_registry,data/source_registry/source_series_inventory.csv,csv,national,in_progress,source_series,88,false,internal_research,Qualified recurring White List publication series and publication models.",
    )


def update_source_registry() -> None:
    pages = ROOT / "data/source_registry/verified_primary_pages.csv"
    append_csv_row(
        pages,
        ["catanzaro", PAGE, "2026-09-15", "verified"],
        unique_key="catanzaro,",
    )

    series = ROOT / "data/source_registry/source_series_inventory.csv"
    append_csv_row(
        series,
        [
            "catanzaro-listed",
            "catanzaro",
            "WL-REGIME-L190-2012",
            "listed",
            "all",
            "periodic_attachment",
            PAGE,
            "landing_page_resolved",
            "2026-09-15",
            "Current official Catanzaro publication surface and 82-page listed PDF directly revalidated 15 September 2026. The byte-pinned 10 September edition yields 610 grouped listed-side observations from 1,556 section memberships (377 listed; 233 renewal/update in progress). Raw malformed dates and identifiers remain fail-closed and uninferred; exact boundaries are documented in docs/sources/catanzaro-operational-check-2026-09-15.md.",
        ],
        unique_key="catanzaro-listed,",
    )
    append_csv_row(
        series,
        [
            "catanzaro-applicants",
            "catanzaro",
            "WL-REGIME-L190-2012",
            "applicant",
            "all",
            "periodic_attachment",
            PAGE,
            "landing_page_resolved",
            "2026-09-15",
            "Current official Catanzaro publication surface and 46-page applicant PDF directly revalidated 15 September 2026. The byte-pinned 10 September edition yields exactly 277 positive applicant observations; two blank source dates, one malformed source date and sparse source rows are preserved without inference. Exact boundaries are documented in docs/sources/catanzaro-operational-check-2026-09-15.md.",
        ],
        unique_key="catanzaro-applicants,",
    )


def update_monitoring() -> None:
    path = ROOT / "data/monitoring/national_coverage.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    matches = [item for item in data["prefectures"] if item.get("authority_key") == "catanzaro"]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one Catanzaro monitoring entry, found {len(matches)}")
    item = matches[0]
    if item.get("public_export_enabled") or item.get("parser_validated"):
        raise RuntimeError("Catanzaro monitoring entry is already promoted; refusing duplicate transaction")
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
            "latest_source_reference_date": "2026-09-10",
            "last_successful_investigation_on": "2026-09-15",
            "unresolved_issue": [
                "Canonical hosted-database integration and independent durable-evidence verification remain governed under #16; public source observations are validated independently of that infrastructure."
            ],
            "actionable_issue": False,
            "coverage_status": "VALIDATED",
            "terminal_reason": None,
            "completion_evidence": [
                "docs/sources/catanzaro-operational-check-2026-09-15.md",
                "src/white_list_archive/parsers/catanzaro_tables.py",
                "tests/test_catanzaro_parser_semantics.py",
                "data/publication/multi_prefecture_pilot.json",
            ],
            "known_content_sha256": [LISTED_SHA, APPLICANT_SHA],
            "evidence": [
                "data/source_registry/verified_primary_pages.csv",
                "data/source_registry/source_series_inventory.csv",
                "data/publication/multi_prefecture_pilot.json",
                "docs/sources/catanzaro-operational-check-2026-09-15.md",
            ],
            "last_completed_coverage_stage": "VALIDATED",
        }
    )
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_publication_config() -> None:
    path = ROOT / "data/publication/multi_prefecture_pilot.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    sources = data["sources"]
    if any(item.get("authority_key") == "catanzaro" for item in sources):
        raise RuntimeError("Catanzaro already exists in publication configuration")
    common = {
        "authority_key": "catanzaro",
        "authority_name": "Prefettura di Catanzaro",
        "register_key": "catanzaro-ordinary",
        "register_name": "White List — Prefettura di Catanzaro",
        "reference_date": "2026-09-10",
        "last_source_update": "2026-09-10",
        "last_source_update_basis": "edition date explicitly stated by the current official attachment labels and listed PDF; the page-level 11 September update marker is retained separately and neither value is treated as an inferred company decision or legal-effect date",
        "source_page_url": PAGE,
    }
    sources.extend(
        [
            {
                **common,
                "source_key": "catanzaro-listed",
                "parser": "catanzaro_listed",
                "population_scope": "listed",
                "resource_url": LISTED_URL,
                "sha256": LISTED_SHA,
                "expected_source_rows": 610,
                "notes": "Current official 82-page listed PDF revalidated 15 September 2026 by independent byte-identical GETs. The fail-closed parser groups 1,556 section memberships into exactly 610 observations (377 listed; 233 renewal/update in progress), preserving malformed raw dates/identifiers without inference. Exact evidence is documented in docs/sources/catanzaro-operational-check-2026-09-15.md.",
            },
            {
                **common,
                "source_key": "catanzaro-applicants",
                "parser": "catanzaro_applicants",
                "population_scope": "applicant",
                "resource_url": APPLICANT_URL,
                "sha256": APPLICANT_SHA,
                "expected_source_rows": 277,
                "notes": "Current official 46-page applicant PDF revalidated 15 September 2026 by independent byte-identical GETs. The fail-closed parser yields exactly 277 positive pending observations and preserves the reviewed blank/malformed source-date and identifier exceptions without inference. Exact evidence is documented in docs/sources/catanzaro-operational-check-2026-09-15.md.",
            },
        ]
    )
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def bind_parser() -> None:
    path = ROOT / "src/white_list_archive/publishing/public_national_registry.py"
    replace_exact(
        path,
        "from white_list_archive.parsers.pisa_tables import PARSERS as PISA_PARSERS\n",
        "from white_list_archive.parsers.pisa_tables import PARSERS as PISA_PARSERS\nfrom white_list_archive.parsers.catanzaro_tables import PARSERS as CATANZARO_PARSERS\n",
    )
    replace_exact(
        path,
        '        or PISA_PARSERS.get(cfg["parser"])\n',
        '        or PISA_PARSERS.get(cfg["parser"])\n        or CATANZARO_PARSERS.get(cfg["parser"])\n',
    )


def update_governance_tests() -> None:
    replace_exact(
        ROOT / "tests/test_source_registry.py",
        "    assert len(pages) == 45\n",
        "    assert len(pages) == 46\n",
    )
    path = ROOT / "tests/test_source_population_coverage.py"
    replace_exact(path, '    assert report["verified_authority_count"] == 45\n', '    assert report["verified_authority_count"] == 46\n')
    replace_exact(path, '    assert report["register_scope_count"] == 46\n', '    assert report["register_scope_count"] == 47\n')
    replace_exact(path, '    assert report["complete_register_scope_count"] == 44\n', '    assert report["complete_register_scope_count"] == 45\n')


def main() -> None:
    update_catalog()
    update_source_registry()
    update_monitoring()
    update_publication_config()
    bind_parser()
    update_governance_tests()
    print("Catanzaro national candidate transaction applied to working tree")


if __name__ == "__main__":
    main()
