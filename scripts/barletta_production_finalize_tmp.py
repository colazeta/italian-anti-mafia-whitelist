from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

from white_list_archive.parsers.barletta_andria_trani_tables import (
    parse_barletta_andria_trani_applicants,
    parse_barletta_andria_trani_listed,
)

AUTH = "barletta-andria-trani"
AUTH_NAME = "Prefettura di Barletta-Andria-Trani"
REGISTER = "barletta-andria-trani-ordinary"
LISTED_PAGE = "https://prefettura.interno.gov.it/it/prefetture/barletta-andria-trani/white-list-elenco-imprese-iscritte"
APPLICANT_PAGE = "https://prefettura.interno.gov.it/it/prefetture/barletta-andria-trani/white-list-elenco-imprese-richiedenti-liscrizione"
LISTED_URL = "https://prefettura.interno.gov.it/sites/default/files/104/2026-09/white-list-prefettura-di-barletta-andria-trani_1.pdf"
APPLICANT_URL = "https://prefettura.interno.gov.it/sites/default/files/104/2026-09/elenco-imprese-rich-iscriz-white-list-prefettura-di-barletta-andria-trani_0.pdf"
LISTED_SHA = "d3c0e61942cbdefd03cfa7d99f71b2abbfc430f25ff86b8693d44ef14de07e13"
APPLICANT_SHA = "ce460ca66f2d996784ac28d559af5fe702ae8a1d72ed80affeb70a0cb36b0d57"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ItalianAntiMafiaWhitelistArchive/1.0; source-verification)"}


def fetch(url: str, timeout: int = 90) -> tuple[int, bytes]:
    request = Request(url, headers=HEADERS)
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed official URLs
        return int(getattr(response, "status", 200)), response.read()


def verify_sources() -> tuple[Path, Path]:
    evidence: dict[str, dict[str, object]] = {}
    for kind, page_url, resource_url in (
        ("listed", LISTED_PAGE, LISTED_URL),
        ("applicants", APPLICANT_PAGE, APPLICANT_URL),
    ):
        status, body = fetch(page_url, 45)
        assert status == 200, (kind, status)
        soup = BeautifulSoup(body.decode("utf-8", "replace"), "html.parser")
        links = {urljoin(page_url, a["href"]): " ".join(a.stripped_strings) for a in soup.find_all("a", href=True)}
        assert resource_url in links, (kind, resource_url)
        evidence[kind] = {"page_status": status, "attachment_label": links[resource_url]}

    output: dict[str, Path] = {}
    for kind, url, expected in (
        ("listed", LISTED_URL, LISTED_SHA),
        ("applicants", APPLICANT_URL, APPLICANT_SHA),
    ):
        status, body = fetch(url)
        assert status == 200, (kind, status)
        observed = hashlib.sha256(body).hexdigest()
        assert observed == expected, (kind, observed)
        path = Path("/tmp", f"barletta-{kind}.pdf")
        path.write_bytes(body)
        output[kind] = path

    base = {
        "authority_key": AUTH,
        "authority_name": AUTH_NAME,
        "register_key": REGISTER,
        "register_name": "White List ordinaria",
        "reference_date": "2026-09-11",
    }
    listed_cfg = base | {
        "source_key": "barletta-andria-trani-listed",
        "population_scope": "listed",
        "source_page_url": LISTED_PAGE,
        "resource_url": LISTED_URL,
        "sha256": LISTED_SHA,
    }
    applicant_cfg = base | {
        "source_key": "barletta-andria-trani-applicants",
        "population_scope": "applicant",
        "source_page_url": APPLICANT_PAGE,
        "resource_url": APPLICANT_URL,
        "sha256": APPLICANT_SHA,
    }
    listed = parse_barletta_andria_trani_listed(output["listed"], listed_cfg)
    applicants = parse_barletta_andria_trani_applicants(output["applicants"], applicant_cfg)
    assert listed.diagnostics["sector_rows"] == 1013
    assert listed.diagnostics["sector_status_counts"] == {"listed": 883, "renewal_update_in_progress": 130}
    assert listed.diagnostics["public_records"] == 493
    assert listed.diagnostics["status_counts"] == {"listed": 437, "renewal_update_in_progress": 56}
    assert applicants.diagnostics["public_records"] == 81
    assert applicants.diagnostics["status_counts"] == {"pending": 81}
    assert len(listed.records) + len(applicants.records) == 574
    print("Barletta source/parser boundary verified", evidence, listed.diagnostics, applicants.diagnostics)
    return output["listed"], output["applicants"]


def update_dispatch() -> None:
    path = Path("src/white_list_archive/publishing/public_national_registry.py")
    text = path.read_text()
    import_anchor = "from white_list_archive.parsers.bergamo_positioned import PARSERS as BERGAMO_PARSERS\n"
    dispatch_anchor = '        or BERGAMO_PARSERS.get(cfg["parser"])\n'
    assert import_anchor in text and dispatch_anchor in text
    if "BARLETTA_ANDRIA_TRANI_PARSERS" not in text:
        text = text.replace(
            import_anchor,
            import_anchor
            + "from white_list_archive.parsers.barletta_andria_trani_tables import PARSERS as BARLETTA_ANDRIA_TRANI_PARSERS\n",
        )
        text = text.replace(
            dispatch_anchor,
            dispatch_anchor + '        or BARLETTA_ANDRIA_TRANI_PARSERS.get(cfg["parser"])\n',
        )
    path.write_text(text)


def update_publication_config() -> None:
    path = Path("data/publication/multi_prefecture_pilot.json")
    config = json.loads(path.read_text())
    assert not [
        item
        for item in config["sources"]
        if item["source_key"] in {"barletta-andria-trani-listed", "barletta-andria-trani-applicants"}
    ]
    config["sources"].extend(
        [
            {
                "source_key": "barletta-andria-trani-listed",
                "parser": "barletta_andria_trani_listed",
                "authority_key": AUTH,
                "authority_name": AUTH_NAME,
                "register_key": REGISTER,
                "register_name": "White List ordinaria",
                "population_scope": "listed",
                "reference_date": "2026-09-11",
                "source_page_url": LISTED_PAGE,
                "resource_url": LISTED_URL,
                "sha256": LISTED_SHA,
                "expected_source_rows": 493,
                "expected_sector_rows": 1013,
                "notes": "Current byte-pinned registered-company publication, reverified on its dedicated official page on 11 September 2026. The source repeats firms across White List sections: 1,013 reviewed sector rows are grouped only when identity, dates, status and note agree, yielding 493 public source-backed observations. Exact exceptions are documented in docs/sources/barletta-andria-trani-operational-check-2026-09-11.md.",
            },
            {
                "source_key": "barletta-andria-trani-applicants",
                "parser": "barletta_andria_trani_applicants",
                "authority_key": AUTH,
                "authority_name": AUTH_NAME,
                "register_key": REGISTER,
                "register_name": "White List ordinaria",
                "population_scope": "applicant",
                "reference_date": "2026-09-11",
                "source_page_url": APPLICANT_PAGE,
                "resource_url": APPLICANT_URL,
                "sha256": APPLICANT_SHA,
                "expected_source_rows": 81,
                "notes": "Current byte-pinned applicant publication, positively identified by the dedicated official page and in-document applicant-list title and reverified on 11 September 2026. It yields 81 source-backed pending observations. Exact parser boundaries are documented in docs/sources/barletta-andria-trani-operational-check-2026-09-11.md.",
            },
        ]
    )
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n")


def update_series_registry() -> None:
    path = Path("data/source_registry/source_series_inventory.csv")
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames
        rows = list(reader)
    assert fields
    replacements = {
        "barletta-andria-trani-listed": {
            "source_series_key": "barletta-andria-trani-listed",
            "authority_key": AUTH,
            "regime_code": "WL-REGIME-L190-2012",
            "population_scope": "listed",
            "sector_scope": "all",
            "publication_model": "periodic_attachment",
            "series_url": LISTED_PAGE,
            "resource_resolution_status": "direct_series_page_resolved",
            "verified_date": "2026-09-11",
            "notes": "Dedicated current official registered-company page and attachment reverified 11 September 2026. Byte identity, 1,013 source-sector-row denominator, 493 grouped public observations and reviewed exceptions are documented in docs/sources/barletta-andria-trani-operational-check-2026-09-11.md.",
        },
        "barletta-andria-trani-applicants": {
            "source_series_key": "barletta-andria-trani-applicants",
            "authority_key": AUTH,
            "regime_code": "WL-REGIME-L190-2012",
            "population_scope": "applicant",
            "sector_scope": "all",
            "publication_model": "periodic_attachment",
            "series_url": APPLICANT_PAGE,
            "resource_resolution_status": "direct_series_page_resolved",
            "verified_date": "2026-09-11",
            "notes": "Dedicated current official applicant page and attachment reverified 11 September 2026; the in-document title positively identifies the applicant population and the parser yields 81 observations. Exact evidence is documented in docs/sources/barletta-andria-trani-operational-check-2026-09-11.md.",
        },
    }
    found: set[str] = set()
    for index, row in enumerate(rows):
        key = row["source_series_key"]
        if key in replacements:
            rows[index] = {field: replacements[key].get(field, "") for field in fields}
            found.add(key)
    assert found == set(replacements), found
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def update_verified_pages() -> None:
    path = Path("data/source_registry/verified_primary_pages.csv")
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames
        rows = list(reader)
    assert fields
    matches = [row for row in rows if row["authority_key"] == AUTH]
    assert len(matches) == 1
    matches[0].update(
        {
            "landing_url": LISTED_PAGE,
            "verification_date": "2026-09-11",
            "verification_status": "verified",
        }
    )
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def update_coverage() -> None:
    path = Path("data/monitoring/national_coverage.json")
    coverage = json.loads(path.read_text())
    authority = next(item for item in coverage["prefectures"] if item["authority_key"] == AUTH)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    authority.update(
        {
            "official_landing_page": LISTED_PAGE,
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
            "last_successful_source_check_at": now,
            "last_attempted_source_check_at": now,
            "last_successful_investigation_on": "2026-09-11",
            "monitoring_status": "CURRENT",
            "unresolved_issue": [
                "Canonical hosted-database integration and independent durable-evidence verification remain governed under #16; public source observations are validated independently of that infrastructure."
            ],
            "actionable_issue": False,
            "coverage_status": "VALIDATED",
            "terminal_reason": None,
            "completion_evidence": [
                "docs/sources/barletta-andria-trani-operational-check-2026-09-11.md",
                "src/white_list_archive/parsers/barletta_andria_trani_tables.py",
                "tests/test_barletta_andria_trani_parser_semantics.py",
                "data/publication/multi_prefecture_pilot.json",
            ],
            "known_content_sha256": [LISTED_SHA, APPLICANT_SHA],
            "evidence": [
                "data/source_registry/verified_primary_pages.csv",
                "data/source_registry/source_series_inventory.csv",
                "data/publication/multi_prefecture_pilot.json",
                "docs/sources/barletta-andria-trani-operational-check-2026-09-11.md",
            ],
            "last_completed_coverage_stage": "VALIDATED",
        }
    )
    path.write_text(json.dumps(coverage, ensure_ascii=False, indent=2) + "\n")


def write_operational_doc() -> None:
    path = Path("docs/sources/barletta-andria-trani-operational-check-2026-09-11.md")
    path.write_text(
        f"""# Barletta-Andria-Trani operational source check — 11 September 2026

## Current official publications

The current White List populations were independently reverified on the Prefettura di Barletta Andria Trani website on 11 September 2026. The authority publishes separate dedicated official pages for registered companies and applicants; each page directly exposes one current PDF attachment.

- Registered-company page: `{LISTED_PAGE}`.
- Registered-company PDF: `{LISTED_URL}`; 211 pages; SHA-256 `{LISTED_SHA}`.
- Applicant page: `{APPLICANT_PAGE}`.
- Applicant PDF: `{APPLICANT_URL}`; 15 pages; SHA-256 `{APPLICANT_SHA}`.

The applicant PDF is positively population-bounded by its in-document title, `ELENCO DELLE IMPRESE RICHIEDENTI L’ISCRIZIONE`; applicant status is therefore not inferred from discovery failure or from an unlabeled document.

The archive reference date `2026-09-11` records this verified current-edition checkpoint; it is not presented as an inferred legal effective date for an individual firm.

## Registered-company parser boundary

The registered-company PDF is organised into the ten White List sections. The parser freezes both page boundaries and the exact reviewed sector-row denominators: I 148, II 68, III 211, IV 84, V 205, VI 136, VII 8, VIII 12, IX 23 and X 118, for **1,013 source sector rows**.

Because the official document repeats the same firm across sections, the public archive groups rows only when the source-backed identity, semantic listing/expiry dates, procedural status and note agree. This yields **493 public registered-population observations**, while preserving all contributing sections. The current grouped status distribution is **437 `listed`** and **56 `renewal_update_in_progress`**. At the ungrouped source-row layer the frozen distribution is **883 listed + 130 update-in-progress = 1,013**.

Two rows for `EDIL AGRESTI SRL` (page 167, source row 4, section VI; page 210, source row 2, section X) contain the visibly split source typography `Aggiornament o in corso`. That exact reviewed source token is treated as positive update-in-progress evidence and is preserved raw; the parser does not generalise this repair to arbitrary near-matches.

Seven malformed date strings are retained verbatim in provenance and are never reconstructed: `14/072026`, `21/05/20259`, `30/06 /2027`, `17/11/20255`, `17/07/202 6`, `01/09/20267`, and `2/6/09/2025`. The reviewed embedded string `31/07/2026 Aggiornamento in corso` contributes the explicit date `31/07/2026` while preserving the procedural text. Any new unsupported date typography fails closed.

Identifiers are normalised only when an exact contiguous 11-digit numeric or 16-character alphanumeric token is present. The parser does not pad, truncate or reconstruct identifiers.

## Applicant parser boundary

The current applicant edition yields exactly **81 public observations**, all mapped to `pending` because they occur in the positively identified applicant publication. The parser freezes the reviewed 15-page geometry and two page-leading continuations needed to preserve split source rows; any new unresolved structural drift fails closed.

## Publication boundary

The two current populations contribute **574 source-backed public observations**. Canonical hosted-database integration and independent durable-evidence verification remain separately governed under issue #16 and are not implied by this public-source validation.
""",
        encoding="utf-8",
    )


def update_pages_gate() -> None:
    path = Path(".github/workflows/public-pages.yml")
    text = path.read_text()
    trigger = "      - 'src/white_list_archive/parsers/bergamo_positioned.py'\n"
    assert trigger in text
    if "barletta_andria_trani_tables.py" not in text:
        text = text.replace(trigger, trigger + "      - 'src/white_list_archive/parsers/barletta_andria_trani_tables.py'\n")
    replacements = {
        "assert reg['meta']['record_count'] == 16729": "assert reg['meta']['record_count'] == 17303",
        "'udine','bergamo'}": "'udine','bergamo','barletta-andria-trani'}",
        "'udine-ordinary','bergamo-ordinary'": "'udine-ordinary','bergamo-ordinary','barletta-andria-trani-ordinary'",
        "assert reg['meta']['authority_count'] == 19": "assert reg['meta']['authority_count'] == 20",
        "assert reg['meta']['register_count'] == 20": "assert reg['meta']['register_count'] == 21",
        "assert pref['meta']['published_count'] == 19": "assert pref['meta']['published_count'] == 20",
    }
    for old, new in replacements.items():
        assert old in text, old
        text = text.replace(old, new, 1)
    bergamo = "          bergamo = [x for x in pref['prefectures'] if x['authority_key'] == 'bergamo']\n          assert len(bergamo) == 1 and bergamo[0]['mapped'] and bergamo[0]['published']\n"
    assert bergamo in text
    text = text.replace(
        bergamo,
        bergamo
        + "          barletta = [x for x in pref['prefectures'] if x['authority_key'] == 'barletta-andria-trani']\n          assert len(barletta) == 1 and barletta[0]['mapped'] and barletta[0]['published']\n",
        1,
    )
    path.write_text(text)


def update_browser_gate() -> None:
    path = Path("tests/public_portal_browser.cjs")
    text = path.read_text()
    label = "      assert.ok(labels.includes('White List ordinaria · Prefettura di Bergamo'));\n"
    assert label in text
    text = text.replace(
        label,
        label + "      assert.ok(labels.includes('White List ordinaria · Prefettura di Barletta-Andria-Trani'));\n",
        1,
    )
    assert "assert.equal(stats.total,16729);" in text
    text = text.replace("assert.equal(stats.total,16729);", "assert.equal(stats.total,17303);", 1)
    old_exclusion = "'ancona','bari','udine','bergamo'].includes(r.authority_key)"
    new_exclusion = "'ancona','bari','udine','bergamo','barletta-andria-trani'].includes(r.authority_key)"
    assert old_exclusion in text
    text = text.replace(old_exclusion, new_exclusion, 1)
    bergamo = "      const bergamo=registry.records.filter(r=>r.authority_key==='bergamo');\n      assert.equal(bergamo.length,2046);\n      assert.equal(bergamo.filter(r=>r.source_key==='bergamo-listed').length,1434);\n      assert.equal(bergamo.filter(r=>r.source_key==='bergamo-applicants').length,612);\n      assert.deepEqual(statusCounts(bergamo),{listed:626,pending:612,renewal_update_in_progress:808});\n"
    assert bergamo in text
    barletta = "      const barletta=registry.records.filter(r=>r.authority_key==='barletta-andria-trani');\n      assert.equal(barletta.length,574);\n      assert.equal(barletta.filter(r=>r.source_key==='barletta-andria-trani-listed').length,493);\n      assert.equal(barletta.filter(r=>r.source_key==='barletta-andria-trani-applicants').length,81);\n      assert.deepEqual(statusCounts(barletta),{listed:437,pending:81,renewal_update_in_progress:56});\n"
    text = text.replace(bergamo, bergamo + barletta, 1)
    path.write_text(text)


def main() -> None:
    verify_sources()
    update_dispatch()
    update_publication_config()
    update_series_registry()
    update_verified_pages()
    update_coverage()
    write_operational_doc()
    update_pages_gate()
    update_browser_gate()
    print("Barletta production files materialized for validation")


if __name__ == "__main__":
    main()
