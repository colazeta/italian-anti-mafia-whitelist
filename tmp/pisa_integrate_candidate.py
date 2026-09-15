from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one replacement anchor, found {count}: {old!r}")
    write(path, text.replace(old, new, 1))


def append_csv_rows(path: str, rows_to_add: list[dict[str, str]], *, unique_field: str) -> None:
    csv_path = ROOT / path
    with csv_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise RuntimeError(f"{path}: missing CSV header")
        fieldnames = list(reader.fieldnames)
        rows = list(reader)
    existing = {row.get(unique_field) for row in rows}
    incoming = [row[unique_field] for row in rows_to_add]
    if len(incoming) != len(set(incoming)):
        raise RuntimeError(f"{path}: duplicate incoming {unique_field} values: {incoming!r}")
    overlap = sorted(set(incoming) & existing)
    if overlap:
        raise RuntimeError(f"{path}: rows already exist for {unique_field}: {overlap!r}")
    for row in rows_to_add:
        unknown = set(row) - set(fieldnames)
        missing = set(fieldnames) - set(row)
        if unknown or missing:
            raise RuntimeError(
                f"{path}: row schema mismatch for {row.get(unique_field)!r}; "
                f"unknown={sorted(unknown)!r} missing={sorted(missing)!r}"
            )
        rows.append(row)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


PAGE = "https://prefettura.interno.gov.it/it/prefetture/pisa/white-list-elenco-imprese-iscritte-e-richiedenti-iscrizione"
LISTED_URL = "https://prefettura.interno.gov.it/sites/default/files/0/2026-09/iscritte.pdf"
APPLICANT_URL = "https://prefettura.interno.gov.it/sites/default/files/0/2026-09/richiedente-iscrizione.pdf"
RENEWAL_URL = "https://prefettura.interno.gov.it/sites/default/files/0/2026-09/in-aggiornamento.pdf"
LISTED_SHA = "30eea93e542aea6ceb13bcfd4e3f1358e1c3f9cfb274b23e738dfb304b1dea23"
APPLICANT_SHA = "ed3bbf19670dbed899f6386836f4723898e4c20f9315e4d4297156fd1dcd6b12"
RENEWAL_SHA = "8658cd2e6048c44de18687b3933980778dd36bbf3721cd944063f61c0e2ceedb"
REFERENCE_DATE = "2026-09-08"
VERIFIED_DATE = "2026-09-15"

# 1. Add the three byte-pinned official Pisa publication inputs under one ordinary register.
config_path = ROOT / "data/publication/multi_prefecture_pilot.json"
config = json.loads(config_path.read_text(encoding="utf-8"))
sources = config["sources"]
if any(source.get("authority_key") == "pisa" for source in sources):
    raise RuntimeError("Pisa is already present in publication config")

common = {
    "authority_key": "pisa",
    "authority_name": "Prefettura di Pisa",
    "register_key": "pisa-white-list",
    "register_name": "White List — Prefettura di Pisa",
    "reference_date": REFERENCE_DATE,
    "last_source_update": REFERENCE_DATE,
    "last_source_update_basis": (
        "page-level 'Ultimo aggiornamento' marker on the official Pisa publication page; "
        "used only as the current source-edition boundary and not as an inferred company decision, "
        "registration, legal-effect or attachment-publication date"
    ),
    "source_page_url": PAGE,
}
sources.extend(
    [
        {
            **common,
            "source_key": "pisa-listed",
            "parser": "pisa_listed",
            "population_scope": "listed",
            "resource_url": LISTED_URL,
            "sha256": LISTED_SHA,
            "expected_source_rows": 398,
            "notes": (
                "Official Allegato A revalidated 15 September 2026 by two byte-identical independent GETs. "
                "The fail-closed six-page table parser yields exactly 398 current listed observations; "
                "397 carry a strict source identifier and the genuinely blank identifier for ROHDE NIELSEN A/S "
                "is preserved without inference. Exact evidence is documented in "
                "docs/sources/pisa-operational-check-2026-09-15.md."
            ),
        },
        {
            **common,
            "source_key": "pisa-applicants",
            "parser": "pisa_applicants",
            "population_scope": "applicant",
            "resource_url": APPLICANT_URL,
            "sha256": APPLICANT_SHA,
            "expected_source_rows": 18,
            "notes": (
                "Official Allegato B revalidated 15 September 2026 by two byte-identical independent GETs. "
                "The fail-closed one-page table parser yields exactly 18 current applicant observations, all "
                "with strict source identifiers. Exact evidence is documented in "
                "docs/sources/pisa-operational-check-2026-09-15.md."
            ),
        },
        {
            **common,
            "source_key": "pisa-renewal-update",
            "parser": "pisa_renewal_update",
            "population_scope": "listed",
            "resource_url": RENEWAL_URL,
            "sha256": RENEWAL_SHA,
            "expected_source_rows": 33,
            "notes": (
                "Separate official 'Elenco Imprese in Aggiornamento' revalidated 15 September 2026 by two "
                "byte-identical independent GETs. It is supplementary current evidence on the listed/renewal "
                "side of the same ordinary Pisa White List register, not a separate legal register. The "
                "fail-closed parser yields exactly 33 renewal/update observations. Exact evidence is documented "
                "in docs/sources/pisa-operational-check-2026-09-15.md."
            ),
        },
    ]
)
config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# 2. Add the three positively verified source series. No NOT_PUBLISHED or completeness state is inferred.
series_path = "data/source_registry/source_series_inventory.csv"
append_csv_rows(
    series_path,
    [
        {
            "source_series_key": "pisa-listed",
            "authority_key": "pisa",
            "regime_code": "WL-REGIME-L190-2012",
            "population_scope": "listed",
            "sector_scope": "all",
            "publication_model": "periodic_attachment",
            "series_url": PAGE,
            "resource_resolution_status": "landing_page_resolved",
            "verified_date": VERIFIED_DATE,
            "notes": (
                "Current official page and Allegato A directly reverified 15 September 2026. The page marker "
                "is 8 September 2026; the byte-pinned six-page PDF yields 398 listed observations. Exact source "
                "identity and parser boundaries are documented in docs/sources/pisa-operational-check-2026-09-15.md."
            ),
        },
        {
            "source_series_key": "pisa-applicants",
            "authority_key": "pisa",
            "regime_code": "WL-REGIME-L190-2012",
            "population_scope": "applicant",
            "sector_scope": "all",
            "publication_model": "periodic_attachment",
            "series_url": PAGE,
            "resource_resolution_status": "landing_page_resolved",
            "verified_date": VERIFIED_DATE,
            "notes": (
                "Current official page and Allegato B directly reverified 15 September 2026. The page marker "
                "is 8 September 2026; the byte-pinned one-page PDF yields 18 applicant observations. Exact source "
                "identity and parser boundaries are documented in docs/sources/pisa-operational-check-2026-09-15.md."
            ),
        },
        {
            "source_series_key": "pisa-renewal-update",
            "authority_key": "pisa",
            "regime_code": "WL-REGIME-L190-2012",
            "population_scope": "listed",
            "sector_scope": "all",
            "publication_model": "periodic_attachment",
            "series_url": PAGE,
            "resource_resolution_status": "landing_page_resolved",
            "verified_date": VERIFIED_DATE,
            "notes": (
                "Current official page directly reverified 15 September 2026 and separately exposes the "
                "byte-pinned 'in aggiornamento' attachment with 33 observations. It is supplementary evidence "
                "for the listed/renewal side of the ordinary register. Exact boundaries are documented in "
                "docs/sources/pisa-operational-check-2026-09-15.md."
            ),
        },
    ],
    unique_field="source_series_key",
)

# 3. Add the positively verified primary page. Pisa has no prior row on the canonical main baseline.
append_csv_rows(
    "data/source_registry/verified_primary_pages.csv",
    [
        {
            "authority_key": "pisa",
            "landing_url": PAGE,
            "verification_date": VERIFIED_DATE,
            "verification_status": "verified",
        }
    ],
    unique_field="authority_key",
)

# 4. Keep exact governance denominators in lockstep with the positively verified additions.
replace_once(
    "data/catalog.csv",
    "verified-primary-pages,source_registry,data/source_registry/verified_primary_pages.csv,csv,national,in_progress,verified_primary_page,44,false,internal_research,Independently verified primary White List landing pages.",
    "verified-primary-pages,source_registry,data/source_registry/verified_primary_pages.csv,csv,national,in_progress,verified_primary_page,45,false,internal_research,Independently verified primary White List landing pages.",
)
replace_once(
    "data/catalog.csv",
    "source-series-inventory,source_registry,data/source_registry/source_series_inventory.csv,csv,national,in_progress,source_series,83,false,internal_research,Qualified recurring White List publication series and publication models.",
    "source-series-inventory,source_registry,data/source_registry/source_series_inventory.csv,csv,national,in_progress,source_series,86,false,internal_research,Qualified recurring White List publication series and publication models.",
)
replace_once(
    "tests/test_source_population_coverage.py",
    "    assert report[\"verified_authority_count\"] == 44\n    assert report[\"register_scope_count\"] == 45\n    assert report[\"complete_register_scope_count\"] == 43\n    assert report[\"incomplete_register_scope_count\"] == 2\n",
    "    assert report[\"verified_authority_count\"] == 45\n    assert report[\"register_scope_count\"] == 46\n    assert report[\"complete_register_scope_count\"] == 44\n    assert report[\"incomplete_register_scope_count\"] == 2\n",
)
replace_once(
    "tests/test_source_registry.py",
    "    assert len(pages) == 44\n",
    "    assert len(pages) == 45\n",
)

# 5. Promote only the validated public-source observation layer. Hosted DB and durable evidence remain separate controls.
coverage_path = ROOT / "data/monitoring/national_coverage.json"
coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
matches = [item for item in coverage["prefectures"] if item.get("authority_key") == "pisa"]
if len(matches) != 1:
    raise RuntimeError(f"Expected one Pisa coverage row, found {len(matches)}")
row = matches[0]
for key in (
    "source_verified",
    "capture_implemented",
    "parser_implemented",
    "parser_validated",
    "company_observations_loaded",
    "public_export_enabled",
    "population_scopes_complete",
):
    if row.get(key) is not False:
        raise RuntimeError(f"Pisa pre-integration {key} drifted: {row.get(key)!r}")
if row.get("current_edition_identified") is not None:
    raise RuntimeError(f"Pisa pre-integration current_edition_identified drifted: {row.get('current_edition_identified')!r}")
if row.get("canonical_integration_validated") is not False or row.get("durable_evidence_verified") is not False:
    raise RuntimeError("Pisa infrastructure boundary drifted before public integration")
row.update(
    {
        "source_verified": True,
        "current_edition_identified": True,
        "capture_implemented": True,
        "parser_implemented": True,
        "parser_validated": True,
        "company_observations_loaded": True,
        "observation_layer": "public_source_observations",
        "public_export_enabled": True,
        "population_scopes_complete": True,
        "latest_source_reference_date": REFERENCE_DATE,
        "last_successful_investigation_on": VERIFIED_DATE,
        "unresolved_issue": [
            "Canonical hosted-database integration and independent durable-evidence verification remain governed under #16; public source observations are validated independently of that infrastructure."
        ],
        "actionable_issue": False,
        "coverage_status": "VALIDATED",
        "completion_evidence": [
            "docs/sources/pisa-operational-check-2026-09-15.md",
            "src/white_list_archive/parsers/pisa_tables.py",
            "tests/test_pisa_parser_semantics.py",
            "data/publication/multi_prefecture_pilot.json",
        ],
        "known_content_sha256": [LISTED_SHA, APPLICANT_SHA, RENEWAL_SHA],
        "evidence": [
            "data/source_registry/verified_primary_pages.csv",
            "data/source_registry/source_series_inventory.csv",
            "data/publication/multi_prefecture_pilot.json",
            "docs/sources/pisa-operational-check-2026-09-15.md",
        ],
        "last_completed_coverage_stage": "VALIDATED",
    }
)
coverage_path.write_text(json.dumps(coverage, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# 6. Bind the already public-contract-valid Pisa parsers into the national publication registry.
registry_path = "src/white_list_archive/publishing/public_national_registry.py"
replace_once(
    registry_path,
    "from white_list_archive.parsers.roma_positioned import PARSERS as ROMA_PARSERS\n",
    "from white_list_archive.parsers.roma_positioned import PARSERS as ROMA_PARSERS\nfrom white_list_archive.parsers.pisa_tables import PARSERS as PISA_PARSERS\n",
)
replace_once(
    registry_path,
    '        or ROMA_PARSERS.get(cfg["parser"])\n',
    '        or ROMA_PARSERS.get(cfg["parser"])\n        or PISA_PARSERS.get(cfg["parser"])\n',
)

print("Pisa candidate production integration applied fail-closed")
