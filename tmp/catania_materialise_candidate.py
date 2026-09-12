from __future__ import annotations

import copy
import csv
import json
from pathlib import Path

PAGE = "https://prefettura.interno.gov.it/it/prefetture/catania/comunicazioni/white-list-provinciale"
LISTED_URL = "https://prefettura.interno.gov.it/sites/default/files/18/2026-09/white-list-iscritti-aggiornato-11-settembre-2026.xlsx"
APPLICANT_URL = "https://prefettura.interno.gov.it/sites/default/files/18/2026-09/white-list-richiedenti-aggiornato-11-settembre-2026.xlsx"
LISTED_SHA = "1d2cbba0751998da03ed7335c6525a8392bd3ec12513e81ee5f3f020e498a291"
APPLICANT_SHA = "4e0cb83a5718cd54b284847a0746fe52fc48bb81be201b758d55024662cb2c27"


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one baseline occurrence for {old!r}; got {count}")
    p.write_text(text.replace(old, new), encoding="utf-8")


# Positive primary-page evidence only.
p = Path("data/source_registry/verified_primary_pages.csv")
lines = p.read_text(encoding="utf-8").splitlines()
if any(line.startswith("catania,") for line in lines):
    raise SystemExit("Catania verified page already present")
pos = next(i for i, line in enumerate(lines) if line.startswith("caserta,")) + 1
lines.insert(pos, f"catania,{PAGE},2026-09-12,verified")
p.write_text("\n".join(lines) + "\n", encoding="utf-8")

# Two separately evidenced logical source series. Use the CSV writer rather than
# string concatenation so punctuation in evidence notes cannot create phantom
# columns or unnamed DictReader keys.
p = Path("data/source_registry/source_series_inventory.csv")
with p.open("r", encoding="utf-8", newline="") as handle:
    reader = csv.DictReader(handle)
    fieldnames = reader.fieldnames
    series_rows = list(reader)
expected_fields = [
    "source_series_key",
    "authority_key",
    "regime_code",
    "population_scope",
    "sector_scope",
    "publication_model",
    "series_url",
    "resource_resolution_status",
    "verified_date",
    "notes",
]
if fieldnames != expected_fields:
    raise SystemExit(f"Source-series schema drift: {fieldnames!r}")
if any(row.get(None) for row in series_rows):
    raise SystemExit("Baseline source-series inventory already contains unnamed overflow fields")
if any(row["source_series_key"].startswith("catania-") for row in series_rows):
    raise SystemExit("Catania source series already present")
caserta = [i for i, row in enumerate(series_rows) if row["source_series_key"].startswith("caserta-")]
if len(caserta) != 2:
    raise SystemExit(f"Expected two Caserta anchor series, got {len(caserta)}")
new_series = [
    {
        "source_series_key": "catania-applicants",
        "authority_key": "catania",
        "regime_code": "WL-REGIME-L190-2012",
        "population_scope": "applicant",
        "sector_scope": "all",
        "publication_model": "periodic_attachment",
        "series_url": PAGE,
        "resource_resolution_status": "landing_page_resolved",
        "verified_date": "2026-09-12",
        "notes": "Current official landing page directly verified 12 September 2026 and exposes a dedicated applicant XLSX explicitly updated 11 September 2026; the byte-pinned workbook yields 324 pending applicant observations and is documented in docs/sources/catania-operational-check-2026-09-12.md.",
    },
    {
        "source_series_key": "catania-listed",
        "authority_key": "catania",
        "regime_code": "WL-REGIME-L190-2012",
        "population_scope": "listed",
        "sector_scope": "all",
        "publication_model": "periodic_attachment",
        "series_url": PAGE,
        "resource_resolution_status": "landing_page_resolved",
        "verified_date": "2026-09-12",
        "notes": "Current official landing page directly verified 12 September 2026 and exposes a dedicated registered-company XLSX explicitly updated 11 September 2026; the byte-pinned workbook yields 1,632 listed-population observations and is documented in docs/sources/catania-operational-check-2026-09-12.md.",
    },
]
insert = max(caserta) + 1
series_rows[insert:insert] = new_series
with p.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(series_rows)

replace_once(
    "data/catalog.csv",
    "verified-primary-pages,source_registry,data/source_registry/verified_primary_pages.csv,csv,national,in_progress,verified_primary_page,38,false,internal_research,Independently verified primary White List landing pages.",
    "verified-primary-pages,source_registry,data/source_registry/verified_primary_pages.csv,csv,national,in_progress,verified_primary_page,39,false,internal_research,Independently verified primary White List landing pages.",
)
replace_once(
    "data/catalog.csv",
    "source-series-inventory,source_registry,data/source_registry/source_series_inventory.csv,csv,national,in_progress,source_series,72,false,internal_research,Qualified recurring White List publication series and publication models.",
    "source-series-inventory,source_registry,data/source_registry/source_series_inventory.csv,csv,national,in_progress,source_series,74,false,internal_research,Qualified recurring White List publication series and publication models.",
)

# Publication input is hash-pinned and parser-bound.
p = Path("data/publication/multi_prefecture_pilot.json")
cfg = json.loads(p.read_text(encoding="utf-8"))
if len(cfg["sources"]) != 53:
    raise SystemExit(f"Unexpected baseline source count {len(cfg['sources'])}")
if any(x["authority_key"] == "catania" for x in cfg["sources"]):
    raise SystemExit("Catania already in publication config")
cfg["sources"].extend(
    [
        {
            "source_key": "catania-listed",
            "parser": "catania_listed",
            "authority_key": "catania",
            "authority_name": "Prefettura di Catania",
            "register_key": "catania-ordinary",
            "register_name": "White List ordinaria",
            "population_scope": "listed",
            "reference_date": "2026-09-11",
            "source_page_url": PAGE,
            "resource_url": LISTED_URL,
            "sha256": LISTED_SHA,
            "expected_source_rows": 1632,
            "last_source_update": "2026-09-11",
            "last_source_update_basis": "dated official resource",
            "notes": "Source formulas and reviewed malformed strings remain provenance; canonical values are emitted only under explicit fail-closed parser rules documented in the Catania operational check.",
        },
        {
            "source_key": "catania-applicants",
            "parser": "catania_applicants",
            "authority_key": "catania",
            "authority_name": "Prefettura di Catania",
            "register_key": "catania-ordinary",
            "register_name": "White List ordinaria",
            "population_scope": "applicant",
            "reference_date": "2026-09-11",
            "source_page_url": PAGE,
            "resource_url": APPLICANT_URL,
            "sha256": APPLICANT_SHA,
            "expected_source_rows": 324,
            "last_source_update": "2026-09-11",
            "last_source_update_basis": "dated official resource",
            "notes": "Applicant status is grounded in the separately identified official applicant population; nonstandard identifiers remain raw and are never repaired.",
        },
    ]
)
p.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# Reconcile the exact seeded Catania monitoring placeholder rather than adding a duplicate.
p = Path("data/monitoring/national_coverage.json")
cov = json.loads(p.read_text(encoding="utf-8"))
matches = [(i, x) for i, x in enumerate(cov["prefectures"]) if x["authority_key"] == "catania"]
if len(matches) != 1:
    raise SystemExit(f"Unexpected Catania coverage multiplicity: {len(matches)}")
idx, placeholder = matches[0]
expected_placeholder = {
    "prefecture": "Catania",
    "region": "Sicilia",
    "national_index_key": "catania",
    "official_landing_page": "https://prefettura.interno.gov.it/it/prefetture/catania/evidenza/white-list",
    "source_verified": False,
    "current_edition_identified": None,
    "capture_implemented": False,
    "parser_implemented": False,
    "parser_validated": False,
    "company_observations_loaded": False,
    "observation_layer": None,
    "public_export_enabled": False,
    "population_scopes_complete": False,
    "coverage_status": "SOURCE_IDENTIFIED",
    "completion_evidence": [],
    "known_content_sha256": [],
}
for key, value in expected_placeholder.items():
    if placeholder.get(key) != value:
        raise SystemExit(f"Catania placeholder drift for {key}: {placeholder.get(key)!r} != {value!r}")
row = copy.deepcopy(placeholder)
row.update(
    {
        "official_landing_page": PAGE,
        "source_verified": True,
        "current_edition_identified": True,
        "historical_editions_identified": None,
        "capture_implemented": True,
        "parser_implemented": True,
        "parser_validated": True,
        "company_observations_loaded": True,
        "observation_layer": "public_source_observations",
        "canonical_integration_validated": False,
        "public_export_enabled": True,
        "durable_evidence_verified": False,
        "population_scopes_complete": True,
        "latest_source_reference_date": "2026-09-11",
        "latest_archived_edition": None,
        "archived_evidence_storage_status": "not_documented",
        "last_successful_source_check_at": None,
        "last_attempted_source_check_at": None,
        "last_content_change_at": None,
        "last_successful_investigation_on": "2026-09-12",
        "monitoring_status": "NEVER_CHECKED",
        "unresolved_issue": [
            "Canonical hosted-database integration and independent durable-evidence verification remain governed under #16; public source observations are validated independently of that infrastructure."
        ],
        "actionable_issue": False,
        "coverage_status": "VALIDATED",
        "terminal_reason": None,
        "completion_evidence": [
            "docs/sources/catania-operational-check-2026-09-12.md",
            "src/white_list_archive/parsers/catania_openxml.py",
            "tests/test_catania_parser_semantics.py",
            "data/publication/multi_prefecture_pilot.json",
        ],
        "known_content_sha256": [LISTED_SHA, APPLICANT_SHA],
        "evidence": [
            "data/source_registry/verified_primary_pages.csv",
            "data/source_registry/source_series_inventory.csv",
            "data/publication/multi_prefecture_pilot.json",
            "docs/sources/catania-operational-check-2026-09-12.md",
        ],
        "last_completed_coverage_stage": "VALIDATED",
    }
)
cov["prefectures"][idx] = row
p.write_text(json.dumps(cov, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# Bind parser into public dispatcher.
replace_once(
    "src/white_list_archive/publishing/public_national_registry.py",
    "from white_list_archive.parsers.caserta_tables import PARSERS as CASERTA_PARSERS\n",
    "from white_list_archive.parsers.caserta_tables import PARSERS as CASERTA_PARSERS\nfrom white_list_archive.parsers.catania_openxml import PARSERS as CATANIA_PARSERS\n",
)
replace_once(
    "src/white_list_archive/publishing/public_national_registry.py",
    '        or CASERTA_PARSERS.get(cfg["parser"])\n',
    '        or CASERTA_PARSERS.get(cfg["parser"])\n        or CATANIA_PARSERS.get(cfg["parser"])\n',
)

# Governance denominators.
replace_once("tests/test_source_registry.py", "assert len(pages) == 38", "assert len(pages) == 39")
replace_once(
    "tests/test_source_population_coverage.py",
    'assert report["verified_authority_count"] == 38',
    'assert report["verified_authority_count"] == 39',
)
replace_once(
    "tests/test_source_population_coverage.py",
    'assert report["register_scope_count"] == 39',
    'assert report["register_scope_count"] == 40',
)
replace_once(
    "tests/test_source_population_coverage.py",
    'assert report["complete_register_scope_count"] == 37',
    'assert report["complete_register_scope_count"] == 38',
)

# Browser acceptance freezes the Catania contribution and resulting national denominator.
replace_once(
    "tests/public_portal_browser.cjs",
    "      assert.ok(labels.includes('White List ordinaria · Prefettura di Caserta'));\n",
    "      assert.ok(labels.includes('White List ordinaria · Prefettura di Caserta'));\n      assert.ok(labels.includes('White List ordinaria · Prefettura di Catania'));\n",
)
replace_once("tests/public_portal_browser.cjs", "      assert.equal(stats.total,26882);", "      assert.equal(stats.total,28838);")
replace_once(
    "tests/public_portal_browser.cjs",
    "'campobasso','brescia','bolzano-bozen','caserta'].includes(r.authority_key)",
    "'campobasso','brescia','bolzano-bozen','caserta','catania'].includes(r.authority_key)",
)
caserta_tail = "      assert.equal(caserta.filter(r=>r.source_fields&&Array.isArray(r.source_fields.application_date_raw_variants)&&r.source_fields.application_date_raw_variants.includes('28/25/2025')&&r.application_date==='').length,1);\n"
catania_tail = caserta_tail + """      const catania=registry.records.filter(r=>r.authority_key==='catania');
      assert.equal(catania.length,1956);
      assert.equal(catania.filter(r=>r.source_key==='catania-listed').length,1632);
      assert.equal(catania.filter(r=>r.source_key==='catania-applicants').length,324);
      assert.deepEqual(statusCounts(catania),{listed:1281,pending:324,renewal_update_in_progress:351});
      assert.equal(catania.filter(r=>r.source_fields&&Array.isArray(r.source_fields.listing_date_raw_variants)&&r.source_fields.listing_date_raw_variants.includes('16/072026')&&r.observed_listing_date==='').length,1);
"""
replace_once("tests/public_portal_browser.cjs", caserta_tail, catania_tail)
