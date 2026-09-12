from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANDING = "https://prefettura.interno.gov.it/it/prefetture/brescia/evidenza/white-list"
LISTED_URL = "https://prefettura.interno.gov.it/sites/default/files/0/2026-09/elenco-ditte-iscritte-10-settembre-2026.xlsx"
APPLICANT_URL = "https://prefettura.interno.gov.it/sites/default/files/0/2026-09/elenco-ditte-richiedenti-l-iscrizione-10-settembre-2026.xlsx"
LISTED_SHA = "509e6724de2d4d63f403e254236ec2c5b77077d676ee8c17382464d5c9da07a7"
APPLICANT_SHA = "0ab15af0f0f2838aa162177cbc07b91f3d7d80b561ca490611b8ec368c595f34"
VERIFY_AT = "2026-09-12T04:21:21Z"


def rewrite_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def publication() -> None:
    path = ROOT / "data/publication/multi_prefecture_pilot.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if any(item.get("authority_key") == "brescia" for item in data["sources"]):
        raise SystemExit("Brescia already present in publication config; refusing duplicate integration")
    common = {
        "authority_key": "brescia",
        "authority_name": "Prefettura di Brescia",
        "register_key": "brescia-ordinary",
        "register_name": "White List ordinaria",
        "reference_date": "2026-09-10",
        "source_page_url": LANDING,
        "last_source_update": "2026-09-10",
        "last_source_update_basis": "current official landing page and both current attachments directly verified 12 September 2026; attachment names and HTTP Last-Modified values identify the 10 September 2026 edition",
    }
    data["sources"].extend(
        [
            {
                **common,
                "source_key": "brescia-listed",
                "parser": "brescia_listed",
                "population_scope": "listed",
                "resource_url": LISTED_URL,
                "sha256": LISTED_SHA,
                "expected_source_rows": 2071,
                "expected_sector_rows": 3380,
                "notes": "Current byte-pinned XLSX listed-company publication. Ten statutory sections contain 3,380 reviewed source rows and yield 2,071 semantic observations (1,859 listed; 212 renewal/update in progress). The parser admits only the exact audited 72-row company-name layout-shift fingerprint, separately freezes one non-company noise row, preserves the reviewed ADMG structural shift, and resolves only two malformed date tokens from exact clean peers. No fuzzy matching or identifier reconstruction is used. Exact evidence is documented in docs/sources/brescia-operational-check-2026-09-12.md.",
            },
            {
                **common,
                "source_key": "brescia-applicants",
                "parser": "brescia_applicants",
                "population_scope": "applicant",
                "resource_url": APPLICANT_URL,
                "sha256": APPLICANT_SHA,
                "expected_source_rows": 1263,
                "notes": "Current byte-pinned XLSX applicant publication. 1,264 reviewed source rows yield 1,263 pending applicant observations after one exact duplicate group. Missing or malformed application dates remain uninferred; source identifiers remain raw unless they satisfy the strict parser format. Exact evidence is documented in docs/sources/brescia-operational-check-2026-09-12.md.",
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
    matches = [row for row in rows if row["authority_key"] == "brescia"]
    if len(matches) != 1:
        raise SystemExit(f"Expected one Brescia verified primary page, found {len(matches)}")
    row = matches[0]
    if row["landing_url"] != LANDING or row["verification_status"] != "verified":
        raise SystemExit(f"Unexpected Brescia primary-page row: {row!r}")
    row["verification_date"] = "2026-09-12"
    rows.sort(key=lambda item: item["authority_key"])
    rewrite_csv(path, rows, fields)

    path = ROOT / "data/source_registry/source_series_inventory.csv"
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        fields = list(reader.fieldnames or [])
    by_key = {row["source_series_key"]: row for row in rows}
    expected = {"brescia-listed", "brescia-applicants"}
    if not expected <= set(by_key):
        raise SystemExit(f"Missing Brescia source-series rows: {expected - set(by_key)}")
    listed = by_key["brescia-listed"]
    applicants = by_key["brescia-applicants"]
    for row in (listed, applicants):
        if row["authority_key"] != "brescia" or row["series_url"] != LANDING:
            raise SystemExit(f"Unexpected Brescia source-series row: {row!r}")
        row["verified_date"] = "2026-09-12"
        row["resource_resolution_status"] = "landing_page_resolved"
    listed["notes"] = (
        "Current official landing page directly reverified 12 September 2026 and exposes the registered-company XLSX dated 10 September 2026. "
        "The byte-pinned edition contains 3,380 statutory-section rows yielding 2,071 conflict-audited observations; exact source identity, layout fingerprints and conservative parser exceptions are documented in docs/sources/brescia-operational-check-2026-09-12.md."
    )
    applicants["notes"] = (
        "Current official landing page directly reverified 12 September 2026 and exposes the applicant XLSX dated 10 September 2026. "
        "The byte-pinned edition contains 1,264 reviewed source rows yielding 1,263 pending observations; exact source identity, duplicate handling and raw-date policy are documented in docs/sources/brescia-operational-check-2026-09-12.md."
    )
    rows.sort(key=lambda item: item["source_series_key"])
    rewrite_csv(path, rows, fields)


def coverage() -> None:
    path = ROOT / "data/monitoring/national_coverage.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    matches = [item for item in data["prefectures"] if item["authority_key"] == "brescia"]
    if len(matches) != 1:
        raise SystemExit("Brescia coverage row is not unique")
    row = matches[0]
    if row["coverage_status"] != "SOURCE_IDENTIFIED":
        raise SystemExit(f"Unexpected prior Brescia coverage state: {row['coverage_status']}")
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
            "latest_source_reference_date": "2026-09-10",
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
                "docs/sources/brescia-operational-check-2026-09-12.md",
                "src/white_list_archive/parsers/brescia_openxml.py",
                "tests/test_brescia_parser_semantics.py",
                "data/publication/multi_prefecture_pilot.json",
            ],
            "known_content_sha256": [LISTED_SHA, APPLICANT_SHA],
            "evidence": [
                "data/source_registry/verified_primary_pages.csv",
                "data/source_registry/source_series_inventory.csv",
                "data/publication/multi_prefecture_pilot.json",
                "docs/sources/brescia-operational-check-2026-09-12.md",
            ],
            "last_completed_coverage_stage": "VALIDATED",
        }
    )
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def publication_code() -> None:
    path = ROOT / "src/white_list_archive/publishing/public_national_registry.py"
    text = path.read_text(encoding="utf-8")
    import_anchor = "from white_list_archive.parsers.campobasso_openxml import PARSERS as CAMPOBASSO_PARSERS\n"
    if text.count(import_anchor) != 1:
        raise SystemExit("national parser import anchor drift")
    text = text.replace(
        import_anchor,
        import_anchor + "from white_list_archive.parsers.brescia_openxml import PARSERS as BRESCIA_PARSERS\n",
        1,
    )
    dispatch_anchor = '        or CAMPOBASSO_PARSERS.get(cfg["parser"])\n'
    if text.count(dispatch_anchor) != 1:
        raise SystemExit("national parser dispatch anchor drift")
    text = text.replace(
        dispatch_anchor,
        dispatch_anchor + '        or BRESCIA_PARSERS.get(cfg["parser"])\n',
        1,
    )
    path.write_text(text, encoding="utf-8")


def browser_acceptance() -> None:
    path = ROOT / "tests/public_portal_browser.cjs"
    text = path.read_text(encoding="utf-8")
    label = "      assert.ok(labels.includes('White List ordinaria · Prefettura di Campobasso'));\n"
    if text.count(label) != 1:
        raise SystemExit("browser label anchor drift")
    text = text.replace(label, label + "      assert.ok(labels.includes('White List ordinaria · Prefettura di Brescia'));\n", 1)
    if text.count("assert.equal(stats.total,20168);") != 1:
        raise SystemExit("browser total anchor drift")
    text = text.replace("assert.equal(stats.total,20168);", "assert.equal(stats.total,23502);", 1)
    old = "'cagliari','caltanissetta','crotone','campobasso'].includes(r.authority_key)"
    new = "'cagliari','caltanissetta','crotone','campobasso','brescia'].includes(r.authority_key)"
    if text.count(old) != 1:
        raise SystemExit("browser previous-baseline anchor drift")
    text = text.replace(old, new, 1)
    anchor = "      assert.ok(campobasso.some(r=>r.identifier_field_raw==='880470703'&&r.identifiers.length===0));\n"
    block = (
        "      const brescia=registry.records.filter(r=>r.authority_key==='brescia');\n"
        "      assert.equal(brescia.length,3334);\n"
        "      assert.equal(brescia.filter(r=>r.source_key==='brescia-listed').length,2071);\n"
        "      assert.equal(brescia.filter(r=>r.source_key==='brescia-applicants').length,1263);\n"
        "      assert.deepEqual(statusCounts(brescia),{listed:1859,pending:1263,renewal_update_in_progress:212});\n"
        "      assert.equal(brescia.filter(r=>r.name==='EDIL EUROPA S.R.L.').length,1);\n"
    )
    if text.count(anchor) != 1:
        raise SystemExit("browser Campobasso anomaly anchor drift")
    text = text.replace(anchor, anchor + block, 1)
    path.write_text(text, encoding="utf-8")


def pages_gate() -> None:
    path = ROOT / ".github/workflows/public-pages.yml"
    text = path.read_text(encoding="utf-8")
    parser_path = "      - 'src/white_list_archive/parsers/campobasso_openxml.py'\n"
    if text.count(parser_path) != 1:
        raise SystemExit("public-pages parser path anchor drift")
    text = text.replace(parser_path, parser_path + "      - 'src/white_list_archive/parsers/brescia_openxml.py'\n", 1)
    replacements = [
        ("assert reg['meta']['record_count'] == 20168", "assert reg['meta']['record_count'] == 23502"),
        ("'caltanissetta','crotone','campobasso'}", "'caltanissetta','crotone','campobasso','brescia'}"),
        ("'caltanissetta-ordinary','crotone-ordinary','campobasso-ordinary'", "'caltanissetta-ordinary','crotone-ordinary','campobasso-ordinary','brescia-ordinary'"),
        ("assert reg['meta']['authority_count'] == 25", "assert reg['meta']['authority_count'] == 26"),
        ("assert reg['meta']['register_count'] == 26", "assert reg['meta']['register_count'] == 27"),
        ("assert pref['meta']['published_count'] == 25", "assert pref['meta']['published_count'] == 26"),
    ]
    for old, new in replacements:
        if text.count(old) != 1:
            raise SystemExit(f"public-pages denominator anchor drift: {old}")
        text = text.replace(old, new, 1)
    anchor = "          campobasso = [x for x in pref['prefectures'] if x['authority_key'] == 'campobasso']\n          assert len(campobasso) == 1 and campobasso[0]['mapped'] and campobasso[0]['published']\n"
    if text.count(anchor) != 1:
        raise SystemExit("public-pages Campobasso prefecture anchor drift")
    text = text.replace(
        anchor,
        anchor + "          brescia = [x for x in pref['prefectures'] if x['authority_key'] == 'brescia']\n          assert len(brescia) == 1 and brescia[0]['mapped'] and brescia[0]['published']\n",
        1,
    )
    path.write_text(text, encoding="utf-8")


def docs() -> None:
    path = ROOT / "docs/sources/brescia-operational-check-2026-09-12.md"
    if path.exists():
        raise SystemExit("Brescia source-check doc already exists")
    path.write_text(
        """# Brescia operational source check — 12 September 2026

## Current official evidence

The current official Prefettura di Brescia White List landing page was directly verified on 12 September 2026. It returned HTTP 200 and positively exposed separate registered-company and applicant-company XLSX attachments for the **10 September 2026** edition. Both attachments were independently fetched twice and produced identical SHA-256 values on both requests.

- Landing page: https://prefettura.interno.gov.it/it/prefetture/brescia/evidenza/white-list
- Landing-page SHA-256 at verification: `432bdbf9f1ac00e30ebc1c82685799192fac3dd99839ef7a2bd4a3d19a1d7225`.
- Listed XLSX: 285,910 bytes; SHA-256 `509e6724de2d4d63f403e254236ec2c5b77077d676ee8c17382464d5c9da07a7`; HTTP Last-Modified 10 September 2026 12:14:29 GMT.
- Applicant XLSX: 125,330 bytes; SHA-256 `0ab15af0f0f2838aa162177cbc07b91f3d7d80b561ca490611b8ec368c595f34`; HTTP Last-Modified 10 September 2026 12:15:40 GMT.

No publication identity, completeness or legal status is inferred from search failure. The public candidate uses only these positively identified official resources.

## Listed population

The listed workbook contains ten stacked statutory White List sections. The reviewed physical denominator is **3,380 section rows**: I 426; II 222; III 576; IV 448; V 598; VI 467; VII 70; VIII 35; IX 81; X 457. Conservative semantic grouping yields **2,071 public observations**: **1,859 `listed`** and **212 `renewal_update_in_progress`**.

The real workbook contains an audited layout class in which the company name is placed in column A while the labelled company-name column is blank. The full audit found exactly **72** such company-like source rows, frozen by SHA-256 fingerprint `f6d55887c3f4e45e46217447100e5e896e509c5daa50f603a9ab48a53c5a41c2`. They touch 58 semantic groups, including 39 groups that would otherwise be absent. The parser accepts only that exact reviewed fingerprint and fails closed if the class changes. One separate non-company noise row is frozen by fingerprint `494b0d0d6944b0c006f0a103889004950b190070ee36f2cdfa8d7d9e8c63e610` and excluded from company observations.

One `ADMG SRL` row has a separately reviewed structural field shift. Two malformed source date tokens are normalised only because an exact same-company/same-identifier peer in another statutory section supplies a unique clean date. Other malformed date values remain raw. No fuzzy company matching, address reconstruction or identifier reconstruction is used.

## Applicant population

The applicant workbook contains **1,264 reviewed source rows** and yields **1,263 public observations**, all represented as `pending`, after one exact duplicate group. The parser records 841 missing application dates and one malformed application date without inventing replacements. Identifiers are normalised only when they satisfy the strict accepted format; otherwise the source value remains available as raw evidence.

## Publication decision

The two current source populations are distinct and positively identified by the official authority. The parser has passed semantic tests, two-fetch byte verification against both pinned resources, real-source validation and the full repository test suite. Brescia is therefore eligible for the public national candidate subject to the normal national-build, browser, official-link, CI and deployment gates. Durable independent evidence-store verification and canonical hosted-database integration remain governed separately under issue #16 and are not inferred here.
""",
        encoding="utf-8",
    )


def main() -> None:
    publication()
    source_registry()
    coverage()
    publication_code()
    browser_acceptance()
    pages_gate()
    docs()


if __name__ == "__main__":
    main()
