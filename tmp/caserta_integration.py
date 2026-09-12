from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANDING = "https://prefettura.interno.gov.it/it/prefetture/caserta/elenco-white-list"
LISTED_URL = "https://prefettura.interno.gov.it/sites/default/files/30/2026-09/elenco-iscritti-31082026_white-list.pdf"
APPLICANT_URL = "https://prefettura.interno.gov.it/sites/default/files/30/2026-08/elenco_imprese_richiedenti_iscrizione_white_list-al-31.08.2026.pdf"
LISTED_SHA = "d323335641b3a84a2e13c047e403030b5bb6a98ec6d034c8648d1286d703585a"
APPLICANT_SHA = "90f4bfbedd6c2e4794330066df83bfce834bb3a2707902fe2705430439d1ffc5"
VERIFY_AT = "2026-09-12T11:18:03Z"
AUTHORITY_NAME = "Prefettura di Caserta"


def rewrite_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def publication() -> None:
    path = ROOT / "data/publication/multi_prefecture_pilot.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if any(item.get("authority_key") == "caserta" for item in data["sources"]):
        raise SystemExit("Caserta already present in publication config; refusing duplicate integration")
    common = {
        "authority_key": "caserta",
        "authority_name": AUTHORITY_NAME,
        "register_key": "caserta-ordinary",
        "register_name": "White List ordinaria",
        "reference_date": "2026-08-31",
        "source_page_url": LANDING,
        "last_source_update": "2026-08-31",
        "last_source_update_basis": "current official Caserta White List landing and separate listed/applicant PDFs directly verified 12 September 2026; both files identify the 31 August 2026 population boundary",
    }
    data["sources"].extend([
        {
            **common,
            "source_key": "caserta-listed",
            "parser": "caserta_listed",
            "population_scope": "listed",
            "resource_url": LISTED_URL,
            "sha256": LISTED_SHA,
            "expected_source_rows": 950,
            "notes": "Current byte-pinned 89-page listed-company PDF. Exactly 950 indexed source rows yield 950 observations: 395 listed, 548 renewal/update in progress and 7 other_or_unknown source conditions. The parser freezes page/table geometry, row sequence, identifier-token distributions, update vocabulary and reviewed malformed source values; malformed dates remain raw and uninferred. No fuzzy matching is used. Exact evidence is documented in docs/sources/caserta-operational-check-2026-09-12.md.",
        },
        {
            **common,
            "source_key": "caserta-applicants",
            "parser": "caserta_applicants",
            "population_scope": "applicant",
            "resource_url": APPLICANT_URL,
            "sha256": APPLICANT_SHA,
            "expected_source_rows": 1208,
            "notes": "Current byte-pinned 68-page applicant PDF. Exactly 1,208 indexed source rows yield 1,208 pending observations. Reviewed noncanonical application-date tokens, including the invalid calendar value 28/25/2025, remain raw with no inferred canonical date. Identifier and section parsing is strict and fail-closed; no fuzzy matching is used. Exact evidence is documented in docs/sources/caserta-operational-check-2026-09-12.md.",
        },
    ])
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def source_registry() -> None:
    path = ROOT / "data/source_registry/verified_primary_pages.csv"
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        fields = list(reader.fieldnames or [])
    if any(row["authority_key"] == "caserta" for row in rows):
        raise SystemExit("Caserta verified-primary-page row already exists; refusing duplicate integration")
    rows.append({
        "authority_key": "caserta",
        "landing_url": LANDING,
        "verification_date": "2026-09-12",
        "verification_status": "verified",
    })
    rows.sort(key=lambda item: item["authority_key"])
    rewrite_csv(path, rows, fields)

    path = ROOT / "data/source_registry/source_series_inventory.csv"
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        fields = list(reader.fieldnames or [])
    existing = {row["source_series_key"] for row in rows}
    keys = {"caserta-listed", "caserta-applicants"}
    if existing & keys:
        raise SystemExit(f"Caserta source-series key already exists: {sorted(existing & keys)}")
    rows.extend([
        {
            "source_series_key": "caserta-listed",
            "authority_key": "caserta",
            "regime_code": "WL-REGIME-L190-2012",
            "population_scope": "listed",
            "sector_scope": "all",
            "publication_model": "periodic_attachment",
            "series_url": LANDING,
            "resource_resolution_status": "landing_page_resolved",
            "verified_date": "2026-09-12",
            "notes": "Current official Caserta landing directly verified 12 September 2026; the separate listed-company PDF is the 31 August 2026 edition. The byte-pinned 89-page document yields 950 observations under the fail-closed parser; exact identity and reviewed source anomalies are documented in docs/sources/caserta-operational-check-2026-09-12.md.",
        },
        {
            "source_series_key": "caserta-applicants",
            "authority_key": "caserta",
            "regime_code": "WL-REGIME-L190-2012",
            "population_scope": "applicant",
            "sector_scope": "all",
            "publication_model": "periodic_attachment",
            "series_url": LANDING,
            "resource_resolution_status": "landing_page_resolved",
            "verified_date": "2026-09-12",
            "notes": "Current official Caserta landing directly verified 12 September 2026; the separate applicant-company PDF is the 31 August 2026 edition. The byte-pinned 68-page document yields 1,208 pending observations; malformed dates remain raw and uninferred as documented in docs/sources/caserta-operational-check-2026-09-12.md.",
        },
    ])
    rows.sort(key=lambda item: item["source_series_key"])
    rewrite_csv(path, rows, fields)


def coverage() -> None:
    path = ROOT / "data/monitoring/national_coverage.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if any(item["authority_key"] == "caserta" for item in data["prefectures"]):
        raise SystemExit("Caserta coverage row already exists; refusing duplicate integration")
    data["prefectures"].append({
        "authority_key": "caserta",
        "prefecture": "Caserta",
        "region": "Campania",
        "national_index_key": "caserta",
        "official_landing_page": LANDING,
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
        "latest_source_reference_date": "2026-08-31",
        "latest_archived_edition": None,
        "archived_evidence_storage_status": "not_documented",
        "last_successful_source_check_at": VERIFY_AT,
        "last_attempted_source_check_at": VERIFY_AT,
        "last_content_change_at": None,
        "last_successful_investigation_on": "2026-09-12",
        "monitoring_status": "CURRENT",
        "unresolved_issue": [
            "Canonical hosted-database integration and independent durable-evidence verification remain governed under #16; public source observations are validated independently of that infrastructure."
        ],
        "actionable_issue": False,
        "coverage_status": "VALIDATED",
        "terminal_reason": None,
        "completion_evidence": [
            "docs/sources/caserta-operational-check-2026-09-12.md",
            "src/white_list_archive/parsers/caserta_tables.py",
            "tests/test_caserta_parser_semantics.py",
            "data/publication/multi_prefecture_pilot.json",
        ],
        "known_content_sha256": [LISTED_SHA, APPLICANT_SHA],
        "evidence": [
            "data/source_registry/verified_primary_pages.csv",
            "data/source_registry/source_series_inventory.csv",
            "data/publication/multi_prefecture_pilot.json",
            "docs/sources/caserta-operational-check-2026-09-12.md",
        ],
        "last_completed_coverage_stage": "VALIDATED",
    })
    data["prefectures"].sort(key=lambda item: item["authority_key"])
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def publication_code() -> None:
    path = ROOT / "src/white_list_archive/publishing/public_national_registry.py"
    text = path.read_text(encoding="utf-8")
    import_anchor = "from white_list_archive.parsers.bolzano_docx import (\n    parse_bolzano_applicants,\n    parse_bolzano_listed,\n)\n"
    import_line = "from white_list_archive.parsers.caserta_tables import PARSERS as CASERTA_PARSERS\n"
    if text.count(import_anchor) != 1 or import_line in text:
        raise SystemExit("Caserta national parser import anchor drift")
    text = text.replace(import_anchor, import_anchor + import_line, 1)
    dispatch_anchor = '        or BOLZANO_PARSERS.get(cfg["parser"])\n'
    if text.count(dispatch_anchor) != 1:
        raise SystemExit("Caserta national parser dispatch anchor drift")
    text = text.replace(dispatch_anchor, dispatch_anchor + '        or CASERTA_PARSERS.get(cfg["parser"])\n', 1)
    path.write_text(text, encoding="utf-8")


def browser_acceptance() -> None:
    path = ROOT / "tests/public_portal_browser.cjs"
    text = path.read_text(encoding="utf-8")
    label = "      assert.ok(labels.includes('White List ordinaria · Commissariato del Governo per la Provincia di Bolzano'));\n"
    new_label = "      assert.ok(labels.includes('White List ordinaria · Prefettura di Caserta'));\n"
    if text.count(label) != 1 or new_label in text:
        raise SystemExit("Caserta browser register-label anchor drift")
    text = text.replace(label, label + new_label, 1)
    if text.count("assert.equal(stats.total,24724);") != 1:
        raise SystemExit("Caserta browser total anchor drift")
    text = text.replace("assert.equal(stats.total,24724);", "assert.equal(stats.total,26882);", 1)
    old = "'caltanissetta','crotone','campobasso','brescia','bolzano-bozen'].includes(r.authority_key)"
    new = "'caltanissetta','crotone','campobasso','brescia','bolzano-bozen','caserta'].includes(r.authority_key)"
    if text.count(old) != 1:
        raise SystemExit("Caserta browser previous-baseline anchor drift")
    text = text.replace(old, new, 1)
    anchor = "      assert.equal(bolzano.filter(r=>r.source_fields&&Array.isArray(r.source_fields.expiry_date_raw_variants)&&r.source_fields.expiry_date_raw_variants.includes('16/19/2026')&&r.observed_expiry_date==='').length,1);\n"
    block = (
        "      const caserta=registry.records.filter(r=>r.authority_key==='caserta');\n"
        "      assert.equal(caserta.length,2158);\n"
        "      assert.equal(caserta.filter(r=>r.source_key==='caserta-listed').length,950);\n"
        "      assert.equal(caserta.filter(r=>r.source_key==='caserta-applicants').length,1208);\n"
        "      assert.deepEqual(statusCounts(caserta),{listed:395,other_or_unknown:7,pending:1208,renewal_update_in_progress:548});\n"
        "      assert.equal(caserta.filter(r=>r.source_fields&&Array.isArray(r.source_fields.application_date_raw_variants)&&r.source_fields.application_date_raw_variants.includes('28/25/2025')&&r.application_date==='').length,1);\n"
    )
    if text.count(anchor) != 1:
        raise SystemExit("Caserta browser Bolzano anchor drift")
    text = text.replace(anchor, anchor + block, 1)
    path.write_text(text, encoding="utf-8")


def docs() -> None:
    path = ROOT / "docs/sources/caserta-operational-check-2026-09-12.md"
    if path.exists():
        raise SystemExit("Caserta source-check doc already exists")
    path.write_text("""# Caserta operational source check — 12 September 2026

## Current official evidence

The current official Caserta White List landing was directly resolved on 12 September 2026. It exposes separate current PDFs for registered companies and companies requesting registration, both with a **31 August 2026** population boundary. During the source audit each resource was independently fetched twice and returned identical bytes across both requests.

- Landing page: https://prefettura.interno.gov.it/it/prefetture/caserta/elenco-white-list
- Listed PDF: https://prefettura.interno.gov.it/sites/default/files/30/2026-09/elenco-iscritti-31082026_white-list.pdf
- Listed SHA-256: `d323335641b3a84a2e13c047e403030b5bb6a98ec6d034c8648d1286d703585a`.
- Applicant PDF: https://prefettura.interno.gov.it/sites/default/files/30/2026-08/elenco_imprese_richiedenti_iscrizione_white_list-al-31.08.2026.pdf
- Applicant SHA-256: `90f4bfbedd6c2e4794330066df83bfce834bb3a2707902fe2705430439d1ffc5`.

## Population boundary and parser result

The listed PDF has 89 pages with exactly one nine-column table per page. After excluding one repeated header row on every page, the source indices are contiguous 1–950 and yield **950 observations**: **395 `listed`**, **548 `renewal_update_in_progress`**, and **7 `other_or_unknown`** observations preserving special source conditions without reinterpretation.

The applicant PDF has 68 pages with exactly one eight-column table per page. After excluding repeated headers, source indices are contiguous 1–1,208 and yield **1,208 applicant observations**, all represented as **`pending`**. The combined Caserta public candidate therefore contains **2,158 observations**.

## Conservative exceptions and fail-closed behaviour

The parser freezes page count, one-table-per-page geometry, table widths, source-index sequences, source-status vocabularies, identifier-token distributions, blank-date counts and the complete reviewed anomaly vocabulary. Identifiers are extracted only as explicit strict 11-digit numeric or 16-character alphanumeric tokens. A single reviewed listed row (source index 7) contains its otherwise strict identifier in the secondary-office column; this exact row/value pair is allowlisted and no generic column-shift fallback exists.

Reviewed malformed/noncanonical source date strings remain raw and their canonical date is left blank. This includes the applicant source token **`28/25/2025`** at source index 188, which is an invalid calendar date and is not corrected or inferred. Three listed registration-date tokens and five listed expiry-date/source-condition strings are likewise frozen as reviewed raw exceptions. Source-section anomalies are accepted only for the exact reviewed index/value pairs; unexpected values fail closed.

No fuzzy matching, inferred applicant outcome, inferred identifier, or speculative date correction is used.

## Publication interpretation

Rows are public-source observations, not an independently adjudicated statement of present legal status. `other_or_unknown` is used where the source carries a special condition that cannot defensibly be collapsed into `listed` or renewal/update status. Canonical hosted-database integration and independent durable-evidence verification remain governed separately under issue #16.
""", encoding="utf-8")


def main() -> None:
    publication()
    source_registry()
    coverage()
    publication_code()
    browser_acceptance()
    docs()


if __name__ == "__main__":
    main()
