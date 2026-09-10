from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

source = {
    "source_key": "belluno-combined",
    "parser": "belluno_combined",
    "authority_key": "belluno",
    "authority_name": "Prefettura di Belluno",
    "register_key": "belluno-ordinary",
    "register_name": "White List ordinaria",
    "population_scope": "listed_and_applicant",
    "reference_date": "2026-09-02",
    "source_page_url": "https://prefettura.interno.gov.it/it/prefetture/belluno/evidenza/white-list",
    "resource_url": "https://prefettura.interno.gov.it/sites/default/files/29/2026-09/white_list_02_09_2026-1.pdf",
    "sha256": "65203c633f261deec31bba00be6c4893f90c8a40cd293b832066d20520ff8b58",
    "expected_source_rows": 402,
    "last_source_update": "2026-09-02",
    "last_source_update_basis": "document heading and current official landing-page attachment",
    "notes": "The official landing page currently resolves to a single 44-page combined PDF explicitly dated 2 September 2026. It contains 402 source rows across 42 data pages: 392 listed-population rows and 10 rows explicitly in fase istruttoria. Legal-state mapping uses only explicit source text; malformed dates and identifiers are never repaired.",
}

config_path = Path("data/publication/multi_prefecture_pilot.json")
config = json.loads(config_path.read_text(encoding="utf-8"))
existing = [s for s in config["sources"] if s["source_key"] == source["source_key"]]
if existing and existing != [source]:
    raise SystemExit(f"Conflicting Belluno source config: {existing}")
if not existing:
    config["sources"].append(source)
config["verified_at"] = "2026-09-10"
config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

pages_registry = Path("data/source_registry/verified_primary_pages.csv")
verified = list(csv.DictReader(pages_registry.open(encoding="utf-8", newline="")))
vr = [r for r in verified if r["authority_key"] == "belluno"]
if len(vr) != 1:
    raise SystemExit(f"Expected one Belluno verified-page row, found {len(vr)}")
vr[0]["verification_date"] = "2026-09-10"
vr[0]["verification_status"] = "verified"
with pages_registry.open("w", encoding="utf-8", newline="") as h:
    w = csv.DictWriter(h, fieldnames=verified[0].keys(), lineterminator="\n")
    w.writeheader()
    w.writerows(verified)

series_path = Path("data/source_registry/source_series_inventory.csv")
rows = list(csv.DictReader(series_path.open(encoding="utf-8", newline="")))
match = [r for r in rows if r["source_series_key"] == "belluno-combined"]
if len(match) != 1:
    raise SystemExit(f"Expected one Belluno series row, found {len(match)}")
r = match[0]
r["resource_resolution_status"] = "landing_page_resolved"
r["verified_date"] = "2026-09-10"
r["notes"] = (
    "Official landing page re-resolved on 10 September 2026 to a single combined PDF explicitly dated 2 September 2026. "
    "The byte-pinned 44-page attachment has 402 source rows: 392 listed-population rows and 10 rows explicitly in fase istruttoria. "
    "Exact parser boundaries and conservative anomaly handling are documented in docs/sources/belluno-operational-check-2026-09-10.md."
)
with series_path.open("w", encoding="utf-8", newline="") as h:
    w = csv.DictWriter(h, fieldnames=rows[0].keys(), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)

catalog_path = Path("data/catalog.csv")
cat = list(csv.DictReader(catalog_path.open(encoding="utf-8", newline="")))
m = [r for r in cat if r["dataset_id"] == "multi-prefecture-publication-pilot"]
if len(m) != 1 or m[0]["record_count"] != "19":
    raise SystemExit(f"Unexpected publication config baseline: {m}")
m[0]["record_count"] = "20"
with catalog_path.open("w", encoding="utf-8", newline="") as h:
    w = csv.DictWriter(h, fieldnames=cat[0].keys(), lineterminator="\n")
    w.writeheader()
    w.writerows(cat)

cov_path = Path("data/monitoring/national_coverage.json")
cov = json.loads(cov_path.read_text(encoding="utf-8"))
b = [p for p in cov["prefectures"] if p["authority_key"] == "belluno"]
if len(b) != 1:
    raise SystemExit("Belluno monitoring row missing/duplicated")
item = b[0]
if item.get("public_export_enabled"):
    raise SystemExit("Belluno unexpectedly already public")
now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
item.update(
    {
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
        "latest_source_reference_date": "2026-09-02",
        "last_successful_source_check_at": now,
        "last_attempted_source_check_at": now,
        "last_successful_investigation_on": "2026-09-10",
        "monitoring_status": "CURRENT",
        "unresolved_issue": ["Canonical hosted-database integration and independent durable-evidence verification remain governed under #16; public source observations are validated independently of that infrastructure."],
        "actionable_issue": False,
        "coverage_status": "VALIDATED",
        "terminal_reason": None,
        "completion_evidence": ["docs/sources/belluno-operational-check-2026-09-10.md", "src/white_list_archive/parsers/belluno_combined.py", "tests/test_belluno_parser_semantics.py", "data/publication/multi_prefecture_pilot.json"],
        "known_content_sha256": [source["sha256"]],
        "evidence": ["data/source_registry/verified_primary_pages.csv", "data/source_registry/source_series_inventory.csv", "docs/sources/belluno-operational-check-2026-09-10.md", "src/white_list_archive/parsers/belluno_combined.py", "tests/test_belluno_parser_semantics.py", "data/publication/multi_prefecture_pilot.json"],
    }
)
cov_path.write_text(json.dumps(cov, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

registry_path = Path("src/white_list_archive/publishing/public_national_registry.py")
txt = registry_path.read_text(encoding="utf-8")
old = "from white_list_archive.parsers.agrigento_positioned import PARSERS as AGRIGENTO_PARSERS\n"
new = old + "from white_list_archive.parsers.belluno_combined import PARSERS as BELLUNO_PARSERS\n"
if txt.count(old) != 1:
    raise SystemExit("Unexpected registry import baseline")
txt = txt.replace(old, new)
old = '        or AGRIGENTO_PARSERS.get(cfg["parser"])\n'
new = old + '        or BELLUNO_PARSERS.get(cfg["parser"])\n'
if txt.count(old) != 1:
    raise SystemExit("Unexpected parser dispatch baseline")
registry_path.write_text(txt.replace(old, new), encoding="utf-8")

pages_path = Path(".github/workflows/public-pages.yml")
pages = pages_path.read_text(encoding="utf-8")
reps = {
    "      - 'src/white_list_archive/parsers/agrigento_positioned.py'\n": "      - 'src/white_list_archive/parsers/agrigento_positioned.py'\n      - 'src/white_list_archive/parsers/belluno_combined.py'\n",
    "assert reg['meta']['record_count'] == 9983": "assert reg['meta']['record_count'] == 10385",
    "'pesaro-e-urbino','biella','benevento','asti','agrigento'}": "'pesaro-e-urbino','biella','benevento','asti','agrigento','belluno'}",
    "'biella-ordinary','benevento-ordinary','asti-ordinary','agrigento-ordinary'": "'biella-ordinary','benevento-ordinary','asti-ordinary','agrigento-ordinary','belluno-ordinary'",
    "assert reg['meta']['authority_count'] == 13": "assert reg['meta']['authority_count'] == 14",
    "assert reg['meta']['register_count'] == 14": "assert reg['meta']['register_count'] == 15",
    "assert pref['meta']['published_count'] == 13": "assert pref['meta']['published_count'] == 14",
    "          assert len(agrigento) == 1 and agrigento[0]['mapped'] and agrigento[0]['published']\n": "          assert len(agrigento) == 1 and agrigento[0]['mapped'] and agrigento[0]['published']\n          belluno = [x for x in pref['prefectures'] if x['authority_key'] == 'belluno']\n          assert len(belluno) == 1 and belluno[0]['mapped'] and belluno[0]['published']\n",
}
for old, new in reps.items():
    if pages.count(old) != 1:
        raise SystemExit(f"Unexpected public-pages baseline: {old!r} count={pages.count(old)}")
    pages = pages.replace(old, new)
pages_path.write_text(pages, encoding="utf-8")

browser_path = Path("tests/public_portal_browser.cjs")
browser = browser_path.read_text(encoding="utf-8")
reps = {
    "      assert.ok(labels.includes('White List ordinaria · Prefettura di Agrigento'));\n": "      assert.ok(labels.includes('White List ordinaria · Prefettura di Agrigento'));\n      assert.ok(labels.includes('White List ordinaria · Prefettura di Belluno'));\n",
    "assert.equal(stats.total,9983);": "assert.equal(stats.total,10385);",
    "['alessandria','aosta','arezzo','avellino','pesaro-e-urbino','biella','benevento','asti','agrigento']": "['alessandria','aosta','arezzo','avellino','pesaro-e-urbino','biella','benevento','asti','agrigento','belluno']",
    "      assert.equal(agrigento.filter(r=>r.source_key==='agrigento-applicants').length,306);\n": "      assert.equal(agrigento.filter(r=>r.source_key==='agrigento-applicants').length,306);\n      const belluno=registry.records.filter(r=>r.authority_key==='belluno');\n      assert.equal(belluno.length,402);\n      assert.equal(belluno.filter(r=>r.source_key==='belluno-combined').length,402);\n      assert.deepEqual(statusCounts(belluno),{expired_observed:49,listed:281,pending:10,renewal_update_in_progress:62});\n",
}
for old, new in reps.items():
    if browser.count(old) != 1:
        raise SystemExit(f"Unexpected browser baseline: {old!r} count={browser.count(old)}")
    browser = browser.replace(old, new)
browser_path.write_text(browser, encoding="utf-8")

Path("docs/sources/belluno-operational-check-2026-09-10.md").write_text(
    """# Belluno White List operational check — 10 September 2026

## Current official source

- Official landing page: `https://prefettura.interno.gov.it/it/prefetture/belluno/evidenza/white-list`.
- Re-resolved current attachment: `https://prefettura.interno.gov.it/sites/default/files/29/2026-09/white_list_02_09_2026-1.pdf`.
- A GitHub-hosted source audit on 10 September resolved exactly one official attachment from the landing page. The PDF itself identifies enterprises enrolled in and requesting enrolment in the provincial Belluno White Lists and carries the explicit source date **2 September 2026**. Search-result labels that surfaced 1 September are not used as edition evidence because the live landing page resolves the dated 2 September PDF.
- Verified byte SHA-256: `65203c633f261deec31bba00be6c4893f90c8a40cd293b832066d20520ff8b58`.
- The source has 44 pages: page 1 is the ten-section legend, pages 2–43 contain one stable eight-column data table each, and page 44 has no data table.

## Population and parser boundary

The audited edition contains **402 source rows**: **392** listed-population rows with explicit listing and expiry dates and **10** rows explicitly marked `IN FASE ISTRUTTORIA`. Observed source-status counts are **281 listed**, **62 renewal/update in progress**, **49 expired observed**, and **10 pending/in istruttoria**. Status mapping uses only source-explicit notes and fails closed on unrecognised non-blank legal-status text.

Dates are normalised only from complete valid `DD/MM/YYYY` tokens. One visibly truncated source application date, `07/04/202`, is not reconstructed and remains canonically blank. Identifiers are preserved verbatim: **388/402** rows yield a strict canonical CF/PIVA token, **13/402** contain a non-empty raw identifier that does not satisfy the canonical rule, and **1/402** has a blank source identifier. No identifier is padded, truncated or repaired.

## Validation and publication boundary

`belluno_combined` requires 44 pages, the ten-section legend, 42 exact data-page headers, one table per data page, exactly eight columns and exactly 402 source rows. Publication requires the pinned source SHA-256 and confirms the full identifier partition and source-backed status counts. Public records stay inside public contract v3. Canonical hosted-database integration and independent durable-evidence verification are **not** claimed by this expansion and remain governed separately under issue #16.
""",
    encoding="utf-8",
)
