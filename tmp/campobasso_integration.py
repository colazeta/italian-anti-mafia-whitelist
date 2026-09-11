from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANDING = "https://prefettura.interno.gov.it/it/prefetture/campobasso/evidenza/white-list"
LISTED_URL = "https://prefettura.interno.gov.it/sites/default/files/21/2026-08/11-agosto-2026-elenco-delle-imprese-non-soggette-a-tentativo-di-infilt.xlsx"
APPLICANT_URL = "https://prefettura.interno.gov.it/sites/default/files/21/2026-08/11-agosto-2026-elenco-delle-imprese-richiedenti-l-iscrizione.docx"
LISTED_SHA = "9d07423eb023025e1dd318c610a205f287a4bee165e4f7fe34e2448f8d91d2a1"
APPLICANT_SHA = "6b1b1f877a0ae5fe68d2472034975914723626a553257d4978296b3632a635ba"


def rewrite_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def publication() -> None:
    path = ROOT / "data/publication/multi_prefecture_pilot.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if any(item.get("authority_key") == "campobasso" for item in data["sources"]):
        raise SystemExit("Campobasso already present in publication config; refusing duplicate integration")
    common = {
        "authority_key": "campobasso",
        "authority_name": "Prefettura di Campobasso",
        "register_key": "campobasso-ordinary",
        "register_name": "White List ordinaria",
        "reference_date": "2026-08-11",
        "source_page_url": LANDING,
        "last_source_update": "2026-08-11",
        "last_source_update_basis": "current official landing page directly verified 11 September 2026; both attachments are explicitly dated 11 August 2026",
    }
    data["sources"].extend(
        [
            {
                **common,
                "source_key": "campobasso-listed",
                "parser": "campobasso_listed",
                "population_scope": "listed",
                "resource_url": LISTED_URL,
                "sha256": LISTED_SHA,
                "expected_source_rows": 323,
                "expected_sector_rows": 882,
                "notes": "Current byte-pinned XLSX listed-company publication. Ten statutory White List sections contain 882 reviewed section rows, conservatively grouped to 323 observations (276 listed; 47 renewal/update in progress). Province-only source placeholders such as ==/CB/blank are not treated as identity changes; substantive registered-office differences remain separate. Malformed source identifiers remain raw and are never reconstructed. Exact evidence is documented in docs/sources/campobasso-operational-check-2026-09-11.md.",
            },
            {
                **common,
                "source_key": "campobasso-applicants",
                "parser": "campobasso_applicants",
                "population_scope": "applicant",
                "resource_url": APPLICANT_URL,
                "sha256": APPLICANT_SHA,
                "expected_source_rows": 19,
                "notes": "Current byte-pinned DOCX applicant publication positively identified by the official landing page. One table with a repeated header contains exactly 19 applicant observations, all represented as pending. Italian written-month dates are accepted only through the audited strict month map; malformed or absent values are never inferred. Exact evidence is documented in docs/sources/campobasso-operational-check-2026-09-11.md.",
            },
        ]
    )
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def source_registry() -> None:
    path = ROOT / "data/source_registry/verified_primary_pages.csv"
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        fields = list(reader.fieldnames or [])
    if any(row["authority_key"] == "campobasso" for row in rows):
        raise SystemExit("Campobasso verified primary page already exists")
    rows.append(
        {
            "authority_key": "campobasso",
            "landing_url": LANDING,
            "verification_date": "2026-09-11",
            "verification_status": "verified",
        }
    )
    rows.sort(key=lambda row: row["authority_key"])
    rewrite_csv(path, rows, fields)

    path = ROOT / "data/source_registry/source_series_inventory.csv"
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        fields = list(reader.fieldnames or [])
    if any(row["authority_key"] == "campobasso" for row in rows):
        raise SystemExit("Campobasso source series already exists; refusing ambiguous upsert")
    rows.extend(
        [
            {
                "source_series_key": "campobasso-applicants",
                "authority_key": "campobasso",
                "regime_code": "WL-REGIME-L190-2012",
                "population_scope": "applicant",
                "sector_scope": "all",
                "publication_model": "periodic_attachment",
                "series_url": LANDING,
                "resource_resolution_status": "landing_page_resolved",
                "verified_date": "2026-09-11",
                "notes": "Current official landing page directly verified 11 September 2026; it positively exposes the applicant DOCX explicitly dated 11 August 2026. Exact byte identity and parser boundary are documented in docs/sources/campobasso-operational-check-2026-09-11.md.",
            },
            {
                "source_series_key": "campobasso-listed",
                "authority_key": "campobasso",
                "regime_code": "WL-REGIME-L190-2012",
                "population_scope": "listed",
                "sector_scope": "all",
                "publication_model": "periodic_attachment",
                "series_url": LANDING,
                "resource_resolution_status": "landing_page_resolved",
                "verified_date": "2026-09-11",
                "notes": "Current official landing page directly verified 11 September 2026; it positively exposes the listed-company XLSX explicitly dated 11 August 2026. Exact byte identity, 882 section-row denominator and conservative grouping boundary are documented in docs/sources/campobasso-operational-check-2026-09-11.md.",
            },
        ]
    )
    rows.sort(key=lambda row: row["source_series_key"])
    rewrite_csv(path, rows, fields)


def catalogue_and_governance_tests() -> None:
    path = ROOT / "data/catalog.csv"
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        fields = list(reader.fieldnames or [])
    by_id = {row["dataset_id"]: row for row in rows}
    assert by_id["verified-primary-pages"]["record_count"] == "36"
    assert by_id["source-series-inventory"]["record_count"] == "68"
    by_id["verified-primary-pages"]["record_count"] = "37"
    by_id["source-series-inventory"]["record_count"] = "70"
    rewrite_csv(path, rows, fields)

    path = ROOT / "tests/test_source_registry.py"
    text = path.read_text(encoding="utf-8")
    old = "assert len(pages) == 36"
    if text.count(old) != 1:
        raise SystemExit("source-registry denominator anchor drift")
    path.write_text(text.replace(old, "assert len(pages) == 37", 1), encoding="utf-8")

    path = ROOT / "tests/test_source_population_coverage.py"
    text = path.read_text(encoding="utf-8")
    changes = [
        ('verified_authority_count"] == 36', 'verified_authority_count"] == 37'),
        ('register_scope_count"] == 37', 'register_scope_count"] == 38'),
        ('complete_register_scope_count"] == 35', 'complete_register_scope_count"] == 36'),
    ]
    for old, new in changes:
        if text.count(old) != 1:
            raise SystemExit(f"population denominator anchor drift: {old}")
        text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")


def coverage() -> None:
    path = ROOT / "data/monitoring/national_coverage.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    matches = [item for item in data["prefectures"] if item["authority_key"] == "campobasso"]
    if len(matches) != 1:
        raise SystemExit("Campobasso coverage row is not unique")
    row = matches[0]
    if row["coverage_status"] != "SOURCE_IDENTIFIED":
        raise SystemExit(f"Unexpected prior Campobasso coverage state: {row['coverage_status']}")
    row.update(
        {
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
            "latest_source_reference_date": "2026-08-11",
            "latest_archived_edition": None,
            "archived_evidence_storage_status": "not_documented",
            "last_successful_source_check_at": "2026-09-11T21:22:38Z",
            "last_attempted_source_check_at": "2026-09-11T21:22:38Z",
            "last_content_change_at": None,
            "last_successful_investigation_on": "2026-09-11",
            "monitoring_status": "CURRENT",
            "unresolved_issue": [
                "Canonical hosted-database integration and independent durable-evidence verification remain governed under #16; public source observations are validated independently of that infrastructure."
            ],
            "actionable_issue": False,
            "coverage_status": "VALIDATED",
            "terminal_reason": None,
            "completion_evidence": [
                "docs/sources/campobasso-operational-check-2026-09-11.md",
                "src/white_list_archive/parsers/campobasso_openxml.py",
                "tests/test_campobasso_parser_semantics.py",
                "data/publication/multi_prefecture_pilot.json",
            ],
            "known_content_sha256": [LISTED_SHA, APPLICANT_SHA],
            "evidence": [
                "data/source_registry/verified_primary_pages.csv",
                "data/source_registry/source_series_inventory.csv",
                "data/publication/multi_prefecture_pilot.json",
                "docs/sources/campobasso-operational-check-2026-09-11.md",
            ],
            "last_completed_coverage_stage": "VALIDATED",
        }
    )
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def publication_code() -> None:
    path = ROOT / "src/white_list_archive/publishing/public_national_registry.py"
    text = path.read_text(encoding="utf-8")
    import_anchor = "from white_list_archive.parsers.crotone_tables import PARSERS as CROTONE_PARSERS\n"
    if text.count(import_anchor) != 1:
        raise SystemExit("national parser import anchor drift")
    text = text.replace(
        import_anchor,
        import_anchor + "from white_list_archive.parsers.campobasso_openxml import PARSERS as CAMPOBASSO_PARSERS\n",
        1,
    )
    dispatch_anchor = '        or CROTONE_PARSERS.get(cfg["parser"])\n'
    if text.count(dispatch_anchor) != 1:
        raise SystemExit("national parser dispatch anchor drift")
    text = text.replace(
        dispatch_anchor,
        dispatch_anchor + '        or CAMPOBASSO_PARSERS.get(cfg["parser"])\n',
        1,
    )
    path.write_text(text, encoding="utf-8")


def browser_acceptance() -> None:
    path = ROOT / "tests/public_portal_browser.cjs"
    text = path.read_text(encoding="utf-8")
    label = "      assert.ok(labels.includes('White List ordinaria · Prefettura di Crotone'));\n"
    if text.count(label) != 1:
        raise SystemExit("browser label anchor drift")
    text = text.replace(
        label,
        label + "      assert.ok(labels.includes('White List ordinaria · Prefettura di Campobasso'));\n",
        1,
    )
    if text.count("assert.equal(stats.total,19826);") != 1:
        raise SystemExit("browser total anchor drift")
    text = text.replace("assert.equal(stats.total,19826);", "assert.equal(stats.total,20168);", 1)
    old = "'cagliari','caltanissetta','crotone'].includes(r.authority_key)"
    new = "'cagliari','caltanissetta','crotone','campobasso'].includes(r.authority_key)"
    if text.count(old) != 1:
        raise SystemExit("browser previous-baseline anchor drift")
    text = text.replace(old, new, 1)
    anchor = "      const pm=crotone.filter(r=>r.name==='PM COSTRUZIONI S.R.L.');\n"
    block = (
        "      const campobasso=registry.records.filter(r=>r.authority_key==='campobasso');\n"
        "      assert.equal(campobasso.length,342);\n"
        "      assert.equal(campobasso.filter(r=>r.source_key==='campobasso-listed').length,323);\n"
        "      assert.equal(campobasso.filter(r=>r.source_key==='campobasso-applicants').length,19);\n"
        "      assert.deepEqual(statusCounts(campobasso),{listed:276,pending:19,renewal_update_in_progress:47});\n"
        "      assert.ok(campobasso.some(r=>r.identifier_field_raw==='880470703'&&r.identifiers.length===0));\n"
    )
    if text.count(anchor) != 1:
        raise SystemExit("browser Crotone anomaly anchor drift")
    path.write_text(text.replace(anchor, block + anchor, 1), encoding="utf-8")


def docs() -> None:
    path = ROOT / "docs/sources/campobasso-operational-check-2026-09-11.md"
    if path.exists():
        raise SystemExit("Campobasso source-check doc already exists")
    path.write_text(
        """# Campobasso operational source check — 11 September 2026

## Current official evidence

The current official Prefettura di Campobasso White List landing page was directly verified on 11 September 2026. It positively exposes two distinct current populations, both explicitly dated **11 August 2026**: the registered-company list and the applicant-company list. No absence or completeness claim is inferred from search failure.

- Landing page: https://prefettura.interno.gov.it/it/prefetture/campobasso/evidenza/white-list
- Listed XLSX SHA-256: `9d07423eb023025e1dd318c610a205f287a4bee165e4f7fe34e2448f8d91d2a1` (380,550 bytes).
- Applicant DOCX SHA-256: `6b1b1f877a0ae5fe68d2472034975914723626a553257d4978296b3632a635ba` (28,695 bytes).

## Listed population

The XLSX contains one worksheet with ten stacked statutory White List sections. The frozen physical denominator is **882 section rows**: I 134; II 60; III 199; IV 51; V 179; VI 107; VII 31; VIII 19; IX 19; X 83.

Conservative grouping on exact company name, registered office, secondary office, raw identifier, registration date and expiry date yields **323 company observations**: **276 `listed`** and **47 `renewal_update_in_progress`**. Province is deliberately excluded from the grouping key only because the audited source uses `==`, `CB` and blank province cells inconsistently for otherwise exact repeated observations. Registered-office differences remain identity-relevant and are never fuzzy-merged.

The update column contains 741 blank row values, 132 exact `SI` values and 9 `SI (non richiesto per questa sezione)` values. No semantic group is classified as update-in-progress solely from the scoped note: every grouped observation carrying that note also contains an explicit plain `SI` occurrence.

Malformed source identifiers remain raw. The audit observed 53 malformed-identifier row occurrences (51 ten-digit and 2 nine-digit); examples include `1933960708`, `1910940707`, `1821800701`, `880470703` and `895390706`. No digit is added, removed or guessed.

## Applicant population

The current DOCX contains one table and exactly **19 applicant company rows**, with the header repeated twice. The population is positively identified by the official page as companies requesting registration; all 19 observations are therefore represented as `pending`. No duplicate applicant rows were found and no applicant identifier required reconstruction.

Application dates use Italian written month names (for example `14 novembre 2025` and `07 agosto 2026`). The parser accepts only the explicitly reviewed Italian month-name mapping and fails closed on unreviewed date typography or invalid calendar dates.

## Publication and validation boundary

The parser freezes the current worksheet/table structure, ten section denominators, semantic-group count, status counts, repeated applicant headers and exact source hashes. Unknown status text, duplicate rows within a statutory section, source hash drift, unexpected worksheet/table structure, unreviewed dates or denominator drift fail closed. Address normalisation is conservative and no missing identity, address, legal status or population evidence is inferred.

The resulting public candidate contributes **342 source observations**: 323 listed-population observations and 19 applicant observations. Canonical hosted-database integration and independently durable evidence remain governed separately under issue #16 and are not claimed by this source/publication validation.
""",
        encoding="utf-8",
    )


def main() -> None:
    publication()
    source_registry()
    catalogue_and_governance_tests()
    coverage()
    publication_code()
    browser_acceptance()
    docs()


if __name__ == "__main__":
    main()
