from __future__ import annotations

import json
from pathlib import Path

LISTED_URL = "https://prefettura.interno.gov.it/it/prefetture/como/elenco-ditte-iscritte-white-list"
APPLICANT_URL = "https://prefettura.interno.gov.it/it/prefetture/como/elenco-ditte-fase-iscrizione-white-list"
LISTED_SHA = "276fcec3a27893b0b57af24ff8d69ebb64338fd5bc955e4722bd48eb33535413"
APPLICANT_SHA = "a4ed63b8e04a277af0221288c40552027437c31064d89ddbc44da432eada42c7"
LISTED_SEMANTIC = "653dc491b25dd4afdd88c7848a42e0ea5b997b51cc2fdc4ef71dcf63bc9c9ad4"
APPLICANT_SEMANTIC = "fe4dcf2b862696df0aac87b43af0037b272c26285b87360f0d5a75cee613a24b"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise SystemExit(f"{label} drift: expected one exact anchor, got {text.count(old)}")
    return text.replace(old, new, 1)


# Publication configuration: preserve historical order and append only Como.
config_path = Path("data/publication/multi_prefecture_pilot.json")
config = json.loads(config_path.read_text(encoding="utf-8"))
if any(s.get("authority_key") == "como" for s in config["sources"]):
    raise SystemExit("Como already present in publication config; reconcile instead of duplicating")
config["sources"].extend(
    [
        {
            "source_key": "como-listed",
            "parser": "como_html_listed",
            "authority_key": "como",
            "authority_name": "Prefettura di Como",
            "register_key": "como-ordinary",
            "register_name": "White List ordinaria",
            "population_scope": "listed",
            "reference_date": "2026-09-10",
            "source_page_url": LISTED_URL,
            "resource_url": LISTED_URL,
            "sha256": LISTED_SHA,
            "semantic_sha256": LISTED_SEMANTIC,
            "approval_mode": "semantic_sha256",
            "expected_source_rows": 391,
            "last_source_update": "2026-09-10",
            "last_source_update_basis": "dedicated official HTML table source date/update; independently reverified 17 September 2026",
            "notes": "Mutable official HTML table. The physical table contains 391 company observations while the source counter states 388; no hidden rows were found. Raw capture SHA remains observation provenance and approved parsed semantics fail closed on drift. Exact evidence is documented in docs/sources/como-operational-check-2026-09-17.md.",
        },
        {
            "source_key": "como-applicants",
            "parser": "como_html_applicants",
            "authority_key": "como",
            "authority_name": "Prefettura di Como",
            "register_key": "como-ordinary",
            "register_name": "White List ordinaria",
            "population_scope": "applicant",
            "reference_date": "2026-09-10",
            "source_page_url": APPLICANT_URL,
            "resource_url": APPLICANT_URL,
            "sha256": APPLICANT_SHA,
            "semantic_sha256": APPLICANT_SEMANTIC,
            "approval_mode": "semantic_sha256",
            "expected_source_rows": 18,
            "last_source_update": "2026-09-10",
            "last_source_update_basis": "dedicated official HTML table source date/update; independently reverified 17 September 2026",
            "notes": "Mutable official applicant HTML table. The physical table contains 18 positive applicant observations while the source counter states 12; no hidden rows were found. Month-only application evidence remains raw and is never expanded to an invented date. Exact evidence is documented in docs/sources/como-operational-check-2026-09-17.md.",
        },
    ]
)
config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# Bind only the Como parser family into the national publication resolver.
registry_path = Path("src/white_list_archive/publishing/public_national_registry.py")
registry = registry_path.read_text(encoding="utf-8")
import_anchor = "from white_list_archive.parsers.modena_tables import PARSERS as MODENA_PARSERS\n"
como_import = "from white_list_archive.parsers.como_html import PARSERS as COMO_PARSERS\n"
if como_import not in registry:
    registry = replace_once(registry, import_anchor, import_anchor + como_import, "Como import anchor")
resolver_anchor = '        or MODENA_PARSERS.get(cfg["parser"])\n'
como_resolver = '        or COMO_PARSERS.get(cfg["parser"])\n'
if como_resolver not in registry:
    registry = replace_once(registry, resolver_anchor, resolver_anchor + como_resolver, "Como resolver anchor")
registry_path.write_text(registry, encoding="utf-8")

# Verified primary page: listed is the primary current surface; applicants remain a distinct series.
primary_path = Path("data/source_registry/verified_primary_pages.csv")
primary_lines = primary_path.read_text(encoding="utf-8").splitlines()
header, rows = primary_lines[0], [line for line in primary_lines[1:] if not line.startswith("como,")]
rows.append(f"como,{LISTED_URL},2026-09-17,verified")
rows.sort(key=lambda line: line.split(",", 1)[0])
primary_path.write_text("\n".join([header, *rows]) + "\n", encoding="utf-8")

# Two positively identified populations, one ordinary register.
series_path = Path("data/source_registry/source_series_inventory.csv")
series_lines = series_path.read_text(encoding="utf-8").splitlines()
header, rows = series_lines[0], [line for line in series_lines[1:] if not line.startswith("como-")]
rows.extend(
    [
        "como-applicants,como,WL-REGIME-L190-2012,applicant,all,html_table,"
        + APPLICANT_URL
        + ",direct_series_page_resolved,2026-09-17,Current dedicated official applicant HTML table directly verified 17 September 2026. It contains 18 positive pending observations although its displayed counter states 12. Complete source boundary and conservative month-only date handling are documented in docs/sources/como-operational-check-2026-09-17.md.",
        "como-listed,como,WL-REGIME-L190-2012,listed,all,html_table,"
        + LISTED_URL
        + ",direct_series_page_resolved,2026-09-17,Current dedicated official registered-company HTML table directly verified 17 September 2026. It contains 391 observations although its displayed counter states 388. Exact status semantics identifier anomalies and malformed-date handling are documented in docs/sources/como-operational-check-2026-09-17.md.",
    ]
)
rows.sort(key=lambda line: line.split(",", 1)[0])
series_path.write_text("\n".join([header, *rows]) + "\n", encoding="utf-8")

# Coverage state: source/public-observation validation is separate from hosted DB/durable evidence.
coverage_path = Path("data/monitoring/national_coverage.json")
coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
matches = [p for p in coverage["prefectures"] if p.get("authority_key") == "como"]
if len(matches) != 1:
    raise SystemExit(f"Expected one Como coverage object, got {len(matches)}")
p = matches[0]
p.update(
    {
        "official_landing_page": LISTED_URL,
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
        "last_successful_source_check_at": "2026-09-17T10:27:10Z",
        "last_attempted_source_check_at": "2026-09-17T10:27:10Z",
        "last_successful_investigation_on": "2026-09-17",
        "monitoring_status": "CURRENT",
        "unresolved_issue": ["Canonical hosted-database integration and independent durable-evidence verification remain governed under #16; public source observations are validated independently of that infrastructure."],
        "actionable_issue": False,
        "coverage_status": "VALIDATED",
        "terminal_reason": None,
        "completion_evidence": [
            "docs/sources/como-operational-check-2026-09-17.md",
            "src/white_list_archive/parsers/como_html.py",
            "tests/test_como_parser_semantics.py",
            "data/publication/multi_prefecture_pilot.json",
        ],
        "known_content_sha256": [
            LISTED_SHA,
            APPLICANT_SHA,
            "f4273fc06277244db3380ec3c7d2bf450b85c3820be3a7b9a04360873ff5323e",
            "475d6cb07b1e73479e6bc5398a61e43dfdb8764a305696a0f9ec0084b8b978cf",
        ],
        "evidence": [
            "data/source_registry/verified_primary_pages.csv",
            "data/source_registry/source_series_inventory.csv",
            "data/publication/multi_prefecture_pilot.json",
            "docs/sources/como-operational-check-2026-09-17.md",
        ],
        "last_completed_coverage_stage": "VALIDATED",
    }
)
coverage_path.write_text(json.dumps(coverage, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# Governance counts must advance atomically with the two expanded CSV registries.
catalog_path = Path("data/catalog.csv")
catalog = catalog_path.read_text(encoding="utf-8")
catalog = replace_once(
    catalog,
    "verified-primary-pages,source_registry,data/source_registry/verified_primary_pages.csv,csv,national,in_progress,verified_primary_page,48,false,internal_research,",
    "verified-primary-pages,source_registry,data/source_registry/verified_primary_pages.csv,csv,national,in_progress,verified_primary_page,49,false,internal_research,",
    "verified-primary-pages catalog count",
)
catalog = replace_once(
    catalog,
    "source-series-inventory,source_registry,data/source_registry/source_series_inventory.csv,csv,national,in_progress,source_series,95,false,internal_research,",
    "source-series-inventory,source_registry,data/source_registry/source_series_inventory.csv,csv,national,in_progress,source_series,97,false,internal_research,",
    "source-series catalog count",
)
catalog_path.write_text(catalog, encoding="utf-8")

coverage_test_path = Path("tests/test_source_population_coverage.py")
coverage_test = coverage_test_path.read_text(encoding="utf-8")
coverage_test = replace_once(coverage_test, 'assert report["verified_authority_count"] == 48', 'assert report["verified_authority_count"] == 49', "verified authority test boundary")
coverage_test = replace_once(coverage_test, 'assert report["register_scope_count"] == 50', 'assert report["register_scope_count"] == 51', "register scope test boundary")
coverage_test = replace_once(coverage_test, 'assert report["complete_register_scope_count"] == 50', 'assert report["complete_register_scope_count"] == 51', "complete scope test boundary")
coverage_test_path.write_text(coverage_test, encoding="utf-8")

registry_test_path = Path("tests/test_source_registry.py")
registry_test = registry_test_path.read_text(encoding="utf-8")
registry_test = replace_once(registry_test, "assert len(pages) == 48", "assert len(pages) == 49", "verified page count test boundary")
registry_test_path.write_text(registry_test, encoding="utf-8")
