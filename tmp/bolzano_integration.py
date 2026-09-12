from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANDING = "https://prefettura.interno.gov.it/it/prefetture/bolzano/evidenza/white-list"
LISTED_URL = "https://prefettura.interno.gov.it/sites/default/files/0/2026-09/2026.09.11-elenco-white-list-da-sez-1-a-sez-10_iscritti-rinnovi.docx"
APPLICANT_URL = "https://prefettura.interno.gov.it/sites/default/files/0/2026-09/2026.09.11-elenco-richiesta-iscrizione-wl.docx"
LISTED_SHA = "96992db4caac16200fbebfa573bb602e1e396961ff854bbf006cb42e011c1e04"
APPLICANT_SHA = "8b7321745edb19db688a001b9a1a706e84bee95cb457f9fdca1af144521ef3ae"
VERIFY_AT = "2026-09-12T08:26:56Z"
AUTHORITY_NAME = "Commissariato del Governo per la Provincia di Bolzano"


def rewrite_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def publication() -> None:
    path = ROOT / "data/publication/multi_prefecture_pilot.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if any(item.get("authority_key") == "bolzano-bozen" for item in data["sources"]):
        raise SystemExit("Bolzano already present in publication config; refusing duplicate integration")
    common = {
        "authority_key": "bolzano-bozen",
        "authority_name": AUTHORITY_NAME,
        "register_key": "bolzano-bozen-ordinary",
        "register_name": "White List ordinaria",
        "reference_date": "2026-09-11",
        "source_page_url": LANDING,
        "last_source_update": "2026-09-11",
        "last_source_update_basis": "current official Bolzano White List landing and both distinct current DOCX series directly verified 12 September 2026; attachment names and HTTP metadata identify the 11 September 2026 edition",
    }
    data["sources"].extend(
        [
            {
                **common,
                "source_key": "bolzano-bozen-listed",
                "parser": "bolzano_listed",
                "population_scope": "listed",
                "resource_url": LISTED_URL,
                "sha256": LISTED_SHA,
                "expected_source_rows": 871,
                "expected_sector_rows": 1706,
                "notes": "Current byte-pinned DOCX listed/renewal publication. Ten statutory sections contain 1,706 reviewed source rows and yield 871 exact semantic observations (620 listed; 251 renewal/update in progress). The parser freezes section-row counts, update lexemes, exact grouping and the reviewed malformed-date vocabulary; malformed source dates, including the audited invalid calendar token 16/19/2026, remain raw and uninferred. Identifiers are normalised only when they satisfy strict 11-digit numeric or 16-character alphanumeric forms. No fuzzy matching is used. Exact evidence is documented in docs/sources/bolzano-operational-check-2026-09-12.md.",
            },
            {
                **common,
                "source_key": "bolzano-bozen-applicants",
                "parser": "bolzano_applicants",
                "population_scope": "applicant",
                "resource_url": APPLICANT_URL,
                "sha256": APPLICANT_SHA,
                "expected_source_rows": 351,
                "notes": "Current byte-pinned DOCX applicant publication. One current table yields exactly 351 applicant observations, all represented as pending. The reviewed malformed application token 14/032025 remains raw and uninferred; non-conforming identifiers remain raw. No fuzzy matching or inferred legal status is used. Exact evidence is documented in docs/sources/bolzano-operational-check-2026-09-12.md.",
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
    matches = [row for row in rows if row["authority_key"] == "bolzano-bozen"]
    if len(matches) != 1:
        raise SystemExit(f"Expected one Bolzano verified primary page, found {len(matches)}")
    row = matches[0]
    if row["landing_url"] != LANDING or row["verification_status"] != "verified":
        raise SystemExit(f"Unexpected Bolzano primary-page row: {row!r}")
    row["verification_date"] = "2026-09-12"
    rows.sort(key=lambda item: item["authority_key"])
    rewrite_csv(path, rows, fields)

    path = ROOT / "data/source_registry/source_series_inventory.csv"
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        fields = list(reader.fieldnames or [])
    by_key = {row["source_series_key"]: row for row in rows}
    expected = {"bolzano-bozen-listed", "bolzano-bozen-applicants"}
    if not expected <= set(by_key):
        raise SystemExit(f"Missing Bolzano source-series rows: {expected - set(by_key)}")
    listed = by_key["bolzano-bozen-listed"]
    applicants = by_key["bolzano-bozen-applicants"]
    for row in (listed, applicants):
        if row["authority_key"] != "bolzano-bozen" or row["series_url"] != LANDING:
            raise SystemExit(f"Unexpected Bolzano source-series row: {row!r}")
        row["verified_date"] = "2026-09-12"
        row["resource_resolution_status"] = "landing_page_resolved"
    listed["notes"] = (
        "Current official landing and linked registered/renewal consultation path directly reverified 12 September 2026. "
        "The byte-pinned 11 September 2026 DOCX contains 1,706 statutory-section source rows yielding 871 exact semantic observations; source identity, update lexemes and reviewed raw-date exceptions are documented in docs/sources/bolzano-operational-check-2026-09-12.md."
    )
    applicants["notes"] = (
        "Current official landing and linked applicant consultation path directly reverified 12 September 2026. "
        "The byte-pinned 11 September 2026 DOCX yields 351 pending applicant observations; source identity and conservative raw-date/identifier handling are documented in docs/sources/bolzano-operational-check-2026-09-12.md."
    )
    rows.sort(key=lambda item: item["source_series_key"])
    rewrite_csv(path, rows, fields)


def coverage() -> None:
    path = ROOT / "data/monitoring/national_coverage.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    matches = [item for item in data["prefectures"] if item["authority_key"] == "bolzano-bozen"]
    if len(matches) != 1:
        raise SystemExit("Bolzano coverage row is not unique")
    row = matches[0]
    if row["coverage_status"] != "SOURCE_IDENTIFIED":
        raise SystemExit(f"Unexpected prior Bolzano coverage state: {row['coverage_status']}")
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
            "latest_source_reference_date": "2026-09-11",
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
                "docs/sources/bolzano-operational-check-2026-09-12.md",
                "src/white_list_archive/parsers/bolzano_docx.py",
                "tests/test_bolzano_parser_semantics.py",
                "data/publication/multi_prefecture_pilot.json",
            ],
            "known_content_sha256": [LISTED_SHA, APPLICANT_SHA],
            "evidence": [
                "data/source_registry/verified_primary_pages.csv",
                "data/source_registry/source_series_inventory.csv",
                "data/publication/multi_prefecture_pilot.json",
                "docs/sources/bolzano-operational-check-2026-09-12.md",
            ],
            "last_completed_coverage_stage": "VALIDATED",
        }
    )
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def publication_code() -> None:
    path = ROOT / "src/white_list_archive/publishing/public_national_registry.py"
    text = path.read_text(encoding="utf-8")
    import_anchor = "from white_list_archive.parsers.brescia_openxml import PARSERS as BRESCIA_PARSERS\n"
    import_block = (
        "from white_list_archive.parsers.bolzano_docx import (\n"
        "    parse_bolzano_applicants,\n"
        "    parse_bolzano_listed,\n"
        ")\n"
    )
    if text.count(import_anchor) != 1 or import_block in text:
        raise SystemExit("national parser import anchor drift")
    text = text.replace(import_anchor, import_anchor + import_block, 1)
    user_agent = 'USER_AGENT = "italian-anti-mafia-whitelist/0.1 (+public national archive)"\n'
    parser_map = (
        "BOLZANO_PARSERS = {\n"
        '    "bolzano_listed": parse_bolzano_listed,\n'
        '    "bolzano_applicants": parse_bolzano_applicants,\n'
        "}\n"
    )
    if text.count(user_agent) != 1 or parser_map in text:
        raise SystemExit("national parser map anchor drift")
    text = text.replace(user_agent, user_agent + parser_map, 1)
    dispatch_anchor = '        or BRESCIA_PARSERS.get(cfg["parser"])\n'
    if text.count(dispatch_anchor) != 1:
        raise SystemExit("national parser dispatch anchor drift")
    text = text.replace(
        dispatch_anchor,
        dispatch_anchor + '        or BOLZANO_PARSERS.get(cfg["parser"])\n',
        1,
    )
    path.write_text(text, encoding="utf-8")


def browser_acceptance() -> None:
    path = ROOT / "tests/public_portal_browser.cjs"
    text = path.read_text(encoding="utf-8")
    label = "      assert.ok(labels.includes('White List ordinaria · Prefettura di Brescia'));\n"
    new_label = "      assert.ok(labels.includes('White List ordinaria · Commissariato del Governo per la Provincia di Bolzano'));\n"
    if text.count(label) != 1 or new_label in text:
        raise SystemExit("browser register-label anchor drift")
    text = text.replace(label, label + new_label, 1)
    if text.count("assert.equal(stats.total,23502);") != 1:
        raise SystemExit("browser total anchor drift")
    text = text.replace("assert.equal(stats.total,23502);", "assert.equal(stats.total,24724);", 1)
    old = "'caltanissetta','crotone','campobasso','brescia'].includes(r.authority_key)"
    new = "'caltanissetta','crotone','campobasso','brescia','bolzano-bozen'].includes(r.authority_key)"
    if text.count(old) != 1:
        raise SystemExit("browser previous-baseline anchor drift")
    text = text.replace(old, new, 1)
    anchor = "      assert.equal(brescia.filter(r=>r.name==='EDIL EUROPA S.R.L.').length,1);\n"
    block = (
        "      const bolzano=registry.records.filter(r=>r.authority_key==='bolzano-bozen');\n"
        "      assert.equal(bolzano.length,1222);\n"
        "      assert.equal(bolzano.filter(r=>r.source_key==='bolzano-bozen-listed').length,871);\n"
        "      assert.equal(bolzano.filter(r=>r.source_key==='bolzano-bozen-applicants').length,351);\n"
        "      assert.deepEqual(statusCounts(bolzano),{listed:620,pending:351,renewal_update_in_progress:251});\n"
        "      assert.equal(bolzano.filter(r=>r.source_fields&&r.source_fields.expiry_date_raw==='16/19/2026'&&r.observed_expiry_date==='').length,1);\n"
    )
    if text.count(anchor) != 1:
        raise SystemExit("browser Brescia anchor drift")
    text = text.replace(anchor, anchor + block, 1)
    path.write_text(text, encoding="utf-8")


def docs() -> None:
    path = ROOT / "docs/sources/bolzano-operational-check-2026-09-12.md"
    if path.exists():
        raise SystemExit("Bolzano source-check doc already exists")
    path.write_text(
        """# Bolzano/Bozen operational source check — 12 September 2026

## Current official evidence

The current official White List landing of the Commissariato del Governo per la Provincia di Bolzano was directly resolved on 12 September 2026. It positively exposes distinct consultation surfaces for companies registered/under renewal and for companies requesting registration. The current attachments are both dated **11 September 2026**. Each attachment was independently fetched twice during the source audit and produced the same SHA-256 on both requests.

- Landing page: https://prefettura.interno.gov.it/it/prefetture/bolzano/evidenza/white-list
- Listed/renewal DOCX: https://prefettura.interno.gov.it/sites/default/files/0/2026-09/2026.09.11-elenco-white-list-da-sez-1-a-sez-10_iscritti-rinnovi.docx
- Listed/renewal SHA-256: `96992db4caac16200fbebfa573bb602e1e396961ff854bbf006cb42e011c1e04`.
- Applicant DOCX: https://prefettura.interno.gov.it/sites/default/files/0/2026-09/2026.09.11-elenco-richiesta-iscrizione-wl.docx
- Applicant SHA-256: `8b7321745edb19db688a001b9a1a706e84bee95cb457f9fdca1af144521ef3ae`.

## Population boundary and parser result

The listed/renewal DOCX contains ten statutory section tables. The reviewed denominator is 1,706 section rows: 307, 144, 219, 158, 269, 226, 21, 10, 165 and 187 rows across sections 1–10 respectively. Exact grouping across sections yields **871 company observations**: **620 `listed`** and **251 `renewal_update_in_progress`**.

The applicant DOCX contains **351 source rows**, yielding **351 applicant observations**, all represented as **`pending`**. No applicant outcome is inferred from absence or search behaviour.

The combined Bolzano public candidate therefore contains **1,222 observations**.

## Conservative exceptions and fail-closed behaviour

The parser freezes the current table count, section-row vector, semantic observation counts, status counts and the complete observed update-status lexicon. Unknown update tokens, new table layouts, row-count drift, same-section exact duplicates and unreviewed date typography fail closed.

Nine malformed listing-date strings and eleven malformed expiry-date strings are explicitly reviewed and preserved raw rather than repaired. The expiry set includes the syntactically complete but impossible calendar value `16/19/2026`, independently identified by the calendar audit. The applicant file contains the reviewed malformed application-date token `14/032025`; it also remains raw and uninferred.

Identifiers are promoted only when the source value is exactly an 11-digit numeric identifier or a 16-character alphanumeric identifier. Other source strings remain available in the raw identifier field and are not reconstructed. Grouping is exact; there is no fuzzy company matching or address-based deduplication.

## Verification state

The parser was validated against the two byte-pinned official documents on 12 September 2026. The real-source validation yields 871 listed-population observations and 351 applicant observations with the expected status distribution. The national public build remains a separate integration gate and must pass before Bolzano/Bozen is marked live.
""",
        encoding="utf-8",
    )


def main() -> None:
    publication()
    source_registry()
    coverage()
    publication_code()
    browser_acceptance()
    docs()


if __name__ == "__main__":
    main()
