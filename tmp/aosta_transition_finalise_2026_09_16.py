from __future__ import annotations

import hashlib
import json
import subprocess
import time
from collections import Counter
from pathlib import Path
from urllib.request import Request, urlopen

from white_list_archive.parsers.multi_prefecture_tables import (
    parse_aosta_applicants,
    parse_aosta_listed,
)
from white_list_archive.publishing.public_national_registry import _semantic_digest

CONFIG = Path("data/publication/multi_prefecture_pilot.json")
COVERAGE = Path("data/monitoring/national_coverage.json")
NOTE = Path("docs/sources/aosta-operational-check-2026-09-10.md")
PAGES = Path(".github/workflows/public-pages.yml")
BROWSER = Path("tests/public_portal_browser.cjs")
CAPTURE_AT = "2026-09-16T08:05:59Z"
REFERENCE_DATE = "2026-09-16"
EXPECTED = {
    "aosta-listed": {
        "raw": "49b94a13c20354cd1c0c29c0b8ec7551813e5ec4d87ab51a1da1227ba05b298c",
        "old_semantic": "bba98e9ff1c3a165f7dfc908f6c4797bd52f735a21f052c8e71508b21b33222b",
        "new_semantic": "1105371866a74157a427b0e885817d5446a8a7a51d9c59a8bed3ad5b62eeb50a",
        "rows": 243,
        "status_counts": {"listed": 222, "renewal_update_in_progress": 21},
    },
    "aosta-applicants": {
        "raw": "0132bd120fd34208b8f07556bcc44a2731db390d799a72c365db952481f09344",
        "old_semantic": "12fbe76183ba19fce4155731763f5668509558e53b16138164951743692a5a65",
        "new_semantic": "09901d8ea7caa54b6ca4509611e9312b54051d8ebab116bd065838d3d005ab1b",
        "rows": 139,
        "status_counts": {"listed": 115, "pending": 24},
    },
}
PARSERS = {
    "aosta-listed": parse_aosta_listed,
    "aosta-applicants": parse_aosta_applicants,
}


def capture_current(cfgs: dict[str, dict]) -> dict[str, tuple[Path, object]]:
    captures: dict[str, tuple[Path, object]] = {}
    for source_key in ("aosta-listed", "aosta-applicants"):
        cfg = cfgs[source_key]
        observed: list[tuple[str, str]] = []
        for attempt in (1, 2):
            req = Request(
                cfg["resource_url"],
                headers={
                    "User-Agent": "italian-anti-mafia-whitelist/0.1 (+Aosta source transition verification)",
                    "Accept": "application/pdf,*/*",
                    "Cache-Control": "no-cache, no-store, max-age=0",
                    "Pragma": "no-cache",
                    "X-Audit-Attempt": str(attempt),
                },
            )
            with urlopen(req, timeout=90) as response:  # noqa: S310 - configured official source
                body = response.read()
            path = Path(f"/tmp/{source_key}-{attempt}.pdf")
            path.write_bytes(body)
            raw = hashlib.sha256(body).hexdigest()
            parse_cfg = dict(cfg)
            parse_cfg["sha256"] = raw
            batch = PARSERS[source_key](path, parse_cfg)
            semantic = _semantic_digest(batch.records)
            statuses = dict(sorted(Counter(r["source_status"] for r in batch.records).items()))
            exp = EXPECTED[source_key]
            assert raw == exp["raw"], (source_key, "raw", raw)
            assert semantic == exp["old_semantic"], (source_key, "old_semantic", semantic)
            assert len(batch.records) == exp["rows"], (source_key, "rows", len(batch.records))
            assert batch.diagnostics["public_records"] == exp["rows"]
            assert batch.diagnostics["dropped_date_rows"] == 0
            assert batch.diagnostics["identifier_coverage"] == exp["rows"]
            assert statuses == exp["status_counts"], (source_key, "statuses", statuses)
            observed.append((raw, semantic))
            if attempt == 1:
                captures[source_key] = (path, batch)
            time.sleep(2)
        assert observed[0] == observed[1], f"{source_key}: independent captures diverged"
    return captures


def assert_row_transition(captures: dict[str, tuple[Path, object]]) -> None:
    listed = captures["aosta-listed"][1].records
    applicants = captures["aosta-applicants"][1].records

    dema_listed = [r for r in listed if r["name"] == "DEMA Srl" and "01191640075" in r["identifiers"]]
    dema_app = [r for r in applicants if r["name"] == "DEMA Srl" and "01191640075" in r["identifiers"]]
    assert not dema_listed
    assert len(dema_app) == 1
    assert dema_app[0]["source_status"] == "pending"
    assert dema_app[0]["application_date"] == "2026-09-04"
    assert dema_app[0]["requested_activities"] == ["E-F-G"]
    assert dema_app[0]["outcome_raw"] == "Istruttoria in corso"

    defazio_listed = [r for r in listed if "01227090071" in r["identifiers"]]
    defazio_app = [r for r in applicants if "01227090071" in r["identifiers"]]
    assert len(defazio_listed) == 1 and not defazio_app
    assert defazio_listed[0]["source_status"] == "renewal_update_in_progress"
    assert defazio_listed[0]["outcome_raw"] == "In corso istruttoria per rinnovo iscrizione"

    for tax_id in ("01060840079", "00611790072", "00035670074"):
        rows = [r for r in listed if tax_id in r["identifiers"]]
        assert len(rows) == 1
        assert rows[0]["source_status"] == "renewal_update_in_progress"
        assert rows[0]["outcome_raw"] == "In corso istruttoria per rinnovo iscrizione"


def update_source_approval(config: dict, cfgs: dict[str, dict], captures: dict[str, tuple[Path, object]]) -> None:
    cfgs["aosta-listed"].update(
        {
            "reference_date": REFERENCE_DATE,
            "sha256": EXPECTED["aosta-listed"]["raw"],
            "expected_source_rows": 243,
            "last_source_update": REFERENCE_DATE,
            "last_source_update_basis": "current official attachment verified on this date; attachment itself is undated",
            "notes": "The official listed-company attachment is a mutable current resource. On 16 September 2026 two independent no-cache captures were byte-identical and exposed 243 complete source rows: 222 listed and 21 with explicit update/renewal text. Compared with the 10 September approved state, DEMA Srl (01191640075) is no longer present; DE FAZIO CRISTIAN (01227090071), PIETRA DI MORGEX Srl (01060840079), URBANIA HABITAT DI STEFANO MATTIOLI & C. Sas (00611790072) and V.I.T.A. S.P.A. (00035670074) now carry explicit renewal-in-progress text. Raw capture SHA-256 remains observation provenance; publication fails closed unless parsed source semantics match this separately approved digest.",
            "approval_mode": "semantic_sha256",
            "semantic_sha256": EXPECTED["aosta-listed"]["new_semantic"],
        }
    )
    cfgs["aosta-applicants"].update(
        {
            "reference_date": REFERENCE_DATE,
            "sha256": EXPECTED["aosta-applicants"]["raw"],
            "expected_source_rows": 139,
            "last_source_update": REFERENCE_DATE,
            "last_source_update_basis": "current official attachment verified on this date; attachment itself is undated",
            "notes": "The official applicant attachment is a mutable current resource. On 16 September 2026 two independent no-cache captures were byte-identical and exposed 139 request observations: 115 with a source outcome indicating subsequent White List enrolment and 24 pending. Compared with the 10 September approved state, DEMA Srl (01191640075) now appears with a 4 September 2026 application for activity E-F-G and explicit outcome Istruttoria in corso, while DE FAZIO CRISTIAN (01227090071) no longer appears in the applicant series and is retained in the listed series with explicit renewal-in-progress text. Raw capture SHA-256 remains observation provenance; publication fails closed unless parsed source semantics match this separately approved digest.",
            "approval_mode": "semantic_sha256",
            "semantic_sha256": EXPECTED["aosta-applicants"]["new_semantic"],
        }
    )
    CONFIG.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for source_key in ("aosta-listed", "aosta-applicants"):
        batch = PARSERS[source_key](captures[source_key][0], cfgs[source_key])
        digest = _semantic_digest(batch.records)
        assert digest == EXPECTED[source_key]["new_semantic"], (source_key, "new_semantic", digest)
        assert len(batch.records) == EXPECTED[source_key]["rows"]
        assert all(r["reference_date"] == REFERENCE_DATE for r in batch.records)
        assert all(f":{REFERENCE_DATE}:" in r["record_locator"] for r in batch.records)


def update_coverage() -> None:
    coverage = json.loads(COVERAGE.read_text(encoding="utf-8"))
    prefectures = coverage.get("prefectures")
    assert isinstance(prefectures, list), sorted(coverage)
    matches = [r for r in prefectures if r.get("authority_key") == "aosta"]
    assert len(matches) == 1
    aosta = matches[0]
    aosta["latest_source_reference_date"] = REFERENCE_DATE
    aosta["last_successful_source_check_at"] = CAPTURE_AT
    aosta["last_attempted_source_check_at"] = CAPTURE_AT
    aosta["last_content_change_at"] = CAPTURE_AT
    aosta["last_successful_investigation_on"] = REFERENCE_DATE
    aosta["monitoring_status"] = "CURRENT"
    known = aosta.setdefault("known_content_sha256", [])
    for raw in (EXPECTED["aosta-listed"]["raw"], EXPECTED["aosta-applicants"]["raw"]):
        if raw not in known:
            known.append(raw)
    COVERAGE.write_text(json.dumps(coverage, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_note() -> None:
    note = NOTE.read_text(encoding="utf-8")
    heading = "## Verified current-source transition — 16 September 2026"
    assert heading not in note
    appendix = f"""

{heading}

The two mutable official attachments were independently captured twice without cache on 16 September 2026 in GitHub Actions run `35071860118` (retained audit artifact `10437035495`). Each pair was byte-identical and parser-identical. This is a new source-content transition and therefore required a new reviewed semantic approval; it is not treated as harmless wrapper-byte drift.

- Listed: current witnessed SHA-256 `{EXPECTED['aosta-listed']['raw']}`; 243 complete observations = 222 `listed` + 21 `renewal_update_in_progress`; identifier coverage 243/243. With the verified-current reference date set to 16 September 2026, approved semantic SHA-256 `{EXPECTED['aosta-listed']['new_semantic']}`.
- Applicants: current witnessed SHA-256 `{EXPECTED['aosta-applicants']['raw']}`; 139 complete observations = 115 with source-explicit subsequent enrolment + 24 `pending`; identifier coverage 139/139. With the verified-current reference date set to 16 September 2026, approved semantic SHA-256 `{EXPECTED['aosta-applicants']['new_semantic']}`.

A row-level comparison against the last live-verified public artifact isolates the transition. `DEMA Srl` (`01191640075`) leaves the listed series and appears in the applicant series with application date 4 September 2026, activity `E-F-G` and explicit outcome `Istruttoria in corso`. `DE FAZIO CRISTIAN (impresa individuale)` (`01227090071`) leaves the applicant series and remains listed with explicit `In corso istruttoria per rinnovo iscrizione`. Three further existing listed identities — `PIETRA DI MORGEX Srl` (`01060840079`), `URBANIA HABITAT DI STEFANO MATTIOLI & C. Sas` (`00611790072`) and `V.I.T.A. S.P.A.` (`00035670074`) — newly carry the same explicit renewal-in-progress text. No other listed identity is added or removed and no other common listed identity changes in the audited public semantic fields; the applicant row count remains 139.

The attachment PDFs remain undated mutable current resources. `2026-09-16` is therefore a verified-current/capture reference date, not an asserted administrative publication or decision date. Raw capture SHA-256 remains attached to observations as provenance. Publication remains fail-closed on any future semantic change. Canonical hosted-database integration and independent durable-evidence verification remain separately governed and are not claimed by this source transition.
"""
    NOTE.write_text(note.rstrip() + appendix + "\n", encoding="utf-8")


def update_gates() -> None:
    pages = PAGES.read_text(encoding="utf-8")
    old_pages = "assert reg['meta']['record_count'] == 51566"
    assert pages.count(old_pages) == 1
    PAGES.write_text(pages.replace(old_pages, "assert reg['meta']['record_count'] == 51565"), encoding="utf-8")

    browser = BROWSER.read_text(encoding="utf-8")
    replacements = {
        "assert.equal(stats.total,51566);": "assert.equal(stats.total,51565);",
        "assert.equal(aosta.length,383);": "assert.equal(aosta.length,382);",
        "assert.equal(aosta.filter(r=>r.source_key==='aosta-listed').length,244);": "assert.equal(aosta.filter(r=>r.source_key==='aosta-listed').length,243);",
        "assert.deepEqual(statusCounts(aosta),{listed:343,pending:23,renewal_update_in_progress:17});": "assert.deepEqual(statusCounts(aosta),{listed:337,pending:24,renewal_update_in_progress:21});",
    }
    for old, new in replacements.items():
        assert browser.count(old) == 1, old
        browser = browser.replace(old, new)
    BROWSER.write_text(browser, encoding="utf-8")


def validate_repository_and_national_build() -> None:
    subprocess.run(["pytest", "-q"], check=True)
    work = Path("/tmp/aosta-transition-public")
    subprocess.run(
        [
            "white-list-public-national-build",
            "--source-config", str(CONFIG),
            "--verified-pages", "data/source_registry/verified_primary_pages.csv",
            "--source-series", "data/source_registry/source_series_inventory.csv",
            "--authority-aliases", "data/source_registry/national_index_authority_aliases.csv",
            "--work-dir", "/tmp/aosta-transition-national-sources",
            "--registry-json", str(work / "data/registry.json"),
            "--registry-csv", str(work / "data/registry.csv"),
            "--prefectures-json", str(work / "data/prefectures.json"),
            "--prefectures-csv", str(work / "data/prefectures.csv"),
        ],
        check=True,
    )
    registry = json.loads((work / "data/registry.json").read_text(encoding="utf-8"))
    prefectures = json.loads((work / "data/prefectures.json").read_text(encoding="utf-8"))
    assert registry["meta"]["record_count"] == 51565
    assert registry["meta"]["authority_count"] == 46
    assert registry["meta"]["register_count"] == 47
    assert prefectures["meta"]["mapped_count"] == 47
    assert prefectures["meta"]["published_count"] == 46
    aosta = [r for r in registry["records"] if r["authority_key"] == "aosta"]
    assert len(aosta) == 382
    assert len({r["record_locator"] for r in aosta}) == 382
    assert sum(r["source_key"] == "aosta-listed" for r in aosta) == 243
    assert sum(r["source_key"] == "aosta-applicants" for r in aosta) == 139
    assert dict(sorted(Counter(r["source_status"] for r in aosta).items())) == {
        "listed": 337,
        "pending": 24,
        "renewal_update_in_progress": 21,
    }
    dema = [r for r in aosta if r["name"] == "DEMA Srl" and "01191640075" in r["identifiers"]]
    assert len(dema) == 1 and dema[0]["source_key"] == "aosta-applicants"
    assert dema[0]["source_status"] == "pending" and dema[0]["application_date"] == "2026-09-04"
    defazio = [r for r in aosta if "01227090071" in r["identifiers"]]
    assert len(defazio) == 1 and defazio[0]["source_key"] == "aosta-listed"
    assert defazio[0]["source_status"] == "renewal_update_in_progress"
    print(
        "validated national boundary",
        registry["meta"]["record_count"],
        registry["meta"]["authority_count"],
        registry["meta"]["register_count"],
        prefectures["meta"]["mapped_count"],
    )
    print("validated Aosta boundary", len(aosta), dict(sorted(Counter(r["source_status"] for r in aosta).items())))


def main() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    cfgs = {row["source_key"]: row for row in config["sources"] if row["source_key"] in EXPECTED}
    assert set(cfgs) == set(EXPECTED)
    captures = capture_current(cfgs)
    assert_row_transition(captures)
    update_source_approval(config, cfgs, captures)
    update_coverage()
    update_note()
    update_gates()
    validate_repository_and_national_build()


if __name__ == "__main__":
    main()
