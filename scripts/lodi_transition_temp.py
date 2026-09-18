from __future__ import annotations

import csv
import hashlib
import json
import time
from collections import Counter
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

OLD_SHA = "c3695018c56ba754614eff988011e0f9b2f6cb2d8e0f22a9823275c8659da613"
NEW_SHA = "a9f6a0977ce0d1a26a6a86450643496cc70f2a1a3eba017e89812eb6f203276e"
APP_SHA = "55aeab7e809cb90cc1ebd1ad9c1f08db78e91648a2c2e1a2b603188c77846228"
DATE = "2026-09-18"


def cache_bust(url: str, token: str) -> str:
    parts = urlsplit(url)
    query = parse_qsl(parts.query, keep_blank_values=True)
    query.append(("wl_transition", token))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def fetch(url: str, token: str) -> bytes:
    request = Request(
        cache_bust(url, token),
        headers={
            "User-Agent": "italian-anti-mafia-whitelist/1.0 (+source-verification)",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )
    with urlopen(request, timeout=60) as response:
        return response.read()


def fetch_stable_sources() -> tuple[Path, Path]:
    pilot = json.loads(Path("data/publication/multi_prefecture_pilot.json").read_text(encoding="utf-8"))
    sources = {x["source_key"]: x for x in pilot["sources"]}
    out = Path("/tmp/lodi-transition")
    out.mkdir(parents=True, exist_ok=True)
    results: dict[str, Path] = {}
    for key, expected in (("lodi-listed", NEW_SHA), ("lodi-applicants", APP_SHA)):
        url = sources[key]["resource_url"]
        first = fetch(url, f"20260918-{key}-A")
        time.sleep(3)
        second = fetch(url, f"20260918-{key}-B")
        if first != second:
            raise SystemExit(f"{key}: independent live captures disagree")
        digest = hashlib.sha256(first).hexdigest()
        if digest != expected:
            raise SystemExit(f"{key}: source moved again: {digest} != {expected}")
        path = out / f"{key}.csv"
        path.write_bytes(first)
        results[key] = path
        print(f"{key}: stable SHA-256 {digest}; {len(first)} bytes")
    return results["lodi-listed"], results["lodi-applicants"]


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one token {old!r}; got {count}")
    return text.replace(old, new)


def apply_transition() -> None:
    parser = Path("src/white_list_archive/parsers/lodi_sheets.py")
    text = parser.read_text(encoding="utf-8")
    for old, new in (
        ('PARSER_VERSION = "2"', 'PARSER_VERSION = "3"'),
        ('_REFERENCE_DATE = "2026-09-16"', '_REFERENCE_DATE = "2026-09-18"'),
        (f'_LISTED_SHA256 = "{OLD_SHA}"', f'_LISTED_SHA256 = "{NEW_SHA}"'),
        ('    "listed": 254,\n    "renewal_update_in_progress": 37,', '    "listed": 251,\n    "renewal_update_in_progress": 40,'),
        ('    "listed": 146,\n    "renewal_update_in_progress": 23,', '    "listed": 144,\n    "renewal_update_in_progress": 25,'),
    ):
        text = replace_once(text, old, new, "parser")
    parser.write_text(text, encoding="utf-8")

    test = Path("tests/test_lodi_parser_semantics.py")
    text = test.read_text(encoding="utf-8")
    text = replace_once(text, 'assert lodi._REFERENCE_DATE == "2026-09-16"', 'assert lodi._REFERENCE_DATE == "2026-09-18"', "test")
    text = replace_once(text, f'assert lodi._LISTED_SHA256 == "{OLD_SHA}"', f'assert lodi._LISTED_SHA256 == "{NEW_SHA}"', "test")
    test.write_text(text, encoding="utf-8")

    pilot_path = Path("data/publication/multi_prefecture_pilot.json")
    pilot = json.loads(pilot_path.read_text(encoding="utf-8"))
    sources = {x["source_key"]: x for x in pilot["sources"]}
    listed = sources["lodi-listed"]
    applicants = sources["lodi-applicants"]
    if (listed["sha256"], listed["reference_date"], listed["expected_source_rows"]) != (OLD_SHA, "2026-09-16", 169):
        raise SystemExit("unexpected pre-transition lodi-listed config")
    if (applicants["sha256"], applicants["reference_date"], applicants["expected_source_rows"]) != (APP_SHA, "2026-09-16", 4):
        raise SystemExit("unexpected pre-transition lodi-applicants config")
    listed.update(
        reference_date=DATE,
        last_source_update=DATE,
        sha256=NEW_SHA,
        notes=(
            "Official mutable Google Sheet linked by the Prefettura di Lodi. Two independent no-cache GETs on 18 September 2026 were byte-identical at the approved SHA-256. "
            "The physical, section-membership and grouped-record denominators remain 324, 291 and 169. Exact comparison with the preserved 16 September capture identifies exactly three changed membership rows and no insertions/removals: "
            "two F.LLI BORCHIA memberships and one CENTRO EDILE LODI membership become explicitly in aggiornamento. Consequently the source-row split becomes 251 listed / 40 renewal-update and the grouped public split becomes 144 listed / 25 renewal-update. "
            "Exact evidence is documented in docs/sources/lodi-operational-check-2026-09-18.md."
        ),
    )
    applicants.update(
        reference_date=DATE,
        last_source_update=DATE,
        notes=(
            "Official applicant tab linked by the Prefettura di Lodi. Two independent no-cache GETs on 18 September 2026 are byte-identical to each other and to the approved 16 September capture. "
            "The four positively identified observations remain unchanged: two explicit denials and two records explicitly in istruttoria. No applicant status or completeness is inferred from failed search. "
            "Exact evidence is documented in docs/sources/lodi-operational-check-2026-09-18.md."
        ),
    )
    pilot_path.write_text(json.dumps(pilot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    inv_path = Path("data/source_registry/source_series_inventory.csv")
    with inv_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fields = reader.fieldnames
    found: set[str] = set()
    for row in rows:
        if row["source_series_key"] == "lodi-listed":
            row["verified_date"] = DATE
            row["notes"] = (
                "Official Lodi landing page remains the positive publication surface for the registered-company Google Sheet. Two independent no-cache CSV exports on 18 September 2026 are byte-identical at SHA-256 a9f6a0977ce0d1a26a6a86450643496cc70f2a1a3eba017e89812eb6f203276e. "
                "Exact comparison with the approved 16 September capture shows three status-marker changes only; 291 statutory-section memberships still group to 169 public observations. Exact evidence is documented in docs/sources/lodi-operational-check-2026-09-18.md."
            )
            found.add("listed")
        elif row["source_series_key"] == "lodi-applicants":
            row["verified_date"] = DATE
            row["notes"] = (
                "Official Lodi landing page remains the positive publication surface for the requesting-company Google Sheet. Two independent no-cache CSV exports on 18 September 2026 remain byte-identical to SHA-256 55aeab7e809cb90cc1ebd1ad9c1f08db78e91648a2c2e1a2b603188c77846228; "
                "the four source-backed applicant observations are unchanged. Exact evidence is documented in docs/sources/lodi-operational-check-2026-09-18.md."
            )
            found.add("applicants")
    if found != {"listed", "applicants"}:
        raise SystemExit(f"Lodi inventory rows not found: {found}")
    assert fields is not None
    with inv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    coverage_path = Path("data/monitoring/national_coverage.json")
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    matches = [x for x in coverage["prefectures"] if x["authority_key"] == "lodi"]
    if len(matches) != 1:
        raise SystemExit("expected one Lodi monitoring entry")
    entry = matches[0]
    if entry["known_content_sha256"] != [OLD_SHA, APP_SHA]:
        raise SystemExit(f"unexpected Lodi monitoring hashes: {entry['known_content_sha256']!r}")
    entry["latest_source_reference_date"] = DATE
    entry["last_successful_investigation_on"] = DATE
    entry["known_content_sha256"] = [NEW_SHA, APP_SHA]
    entry["unresolved_issue"] = [
        "The official Google Sheet is mutable and exposes no reliable edition date; 2026-09-18 is the current byte-pinned observation/capture boundary, not an inferred publication date.",
        "Canonical hosted-database integration and independent durable-evidence verification remain governed under #16; public source observations are validated independently of that infrastructure.",
    ]
    new_doc = "docs/sources/lodi-operational-check-2026-09-18.md"
    if new_doc not in entry["completion_evidence"]:
        entry["completion_evidence"].append(new_doc)
    if new_doc not in entry["evidence"]:
        entry["evidence"].append(new_doc)
    coverage_path.write_text(json.dumps(coverage, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    doc = Path(new_doc)
    if doc.exists():
        raise SystemExit(f"unexpected pre-existing evidence note: {new_doc}")
    doc.write_text(
        """# Lodi operational source transition — 18 September 2026

## Scope

This note records the evidence review required after the mutable official Lodi registered-company Google Sheet changed after the 16 September approval. The observation date is not treated as an inferred publication date.

## Positive official-source evidence

The Prefettura di Lodi White List publication surface remains `https://prefettura.interno.gov.it/it/prefetture/lodi/evidenza/white-list`, which positively exposes separate registered-company and requesting-company Google Sheet populations. The source exports themselves were independently fetched twice with cache bypass on 18 September 2026.

## Registered-company transition

The two current listed captures are byte-identical at SHA-256 `a9f6a0977ce0d1a26a6a86450643496cc70f2a1a3eba017e89812eb6f203276e` and size 36,420 bytes. The approved 16 September capture is SHA-256 `c3695018c56ba754614eff988011e0f9b2f6cb2d8e0f22a9823275c8659da613` and size 36,372 bytes. The preserved 16 September workflow artifact (`Lodi source drift audit (temporary)`, run `35112659448`) permits an exact historical comparison.

The current structure is unchanged: 324 physical CSV rows, seven columns per row, and 291 positively identifiable statutory-section memberships. Exact old/new comparison identifies three changed membership rows and no insertions or removals:

1. `F.LLI BORCHIA DI FRANCO E IVANO BORCHIA & C. S.n.c.` — identifier `01495270157`, source rows 62 and 169: dates remain `21/10/2025`–`21/10/2026`; both blank status markers become `in aggiornamento`.
2. `CENTRO EDILE LODI S.r.l.` — identifier `04301190965`, source row 103: dates remain `28/10/2025`–`28/10/2026`; the blank status marker becomes `in aggiornamento`.

The source-row status denominators therefore move from 254 listed / 37 renewal-update to 251 listed / 40 renewal-update. Conservative grouping by exact identifier/date/status remains 169 observations with the same occurrence distribution; the grouped status split moves from 146 listed / 23 renewal-update to 144 listed / 25 renewal-update because the two BORCHIA memberships represent one grouped observation and the CENTRO EDILE membership represents another.

No legal consequence is inferred beyond the source-explicit `in aggiornamento` marker.

## Applicant population

The applicant export is unchanged. Both 18 September captures are byte-identical to the approved boundary at SHA-256 `55aeab7e809cb90cc1ebd1ad9c1f08db78e91648a2c2e1a2b603188c77846228`, size 1,388 bytes. The four positively identified observations remain two explicit denials and two records explicitly in istruttoria. No applicant status or completeness is inferred from failed search.

## Approval boundary

The Lodi public-source record denominator remains 173 observations: 169 registered-company observations plus 4 applicant observations. Only two grouped registered-company statuses change, so the national record count is unchanged. Parser version 3 freezes the new raw SHA-256 and the new source/grouped status denominators while retaining all existing structural, date, grouping and identifier checks. Durable evidence verification remains a separate governance control under issue #16.
""",
        encoding="utf-8",
    )


def validate_live_parse(listed_path: Path, applicant_path: Path) -> None:
    from white_list_archive.parsers.lodi_sheets import parse_lodi_applicants, parse_lodi_listed

    pilot = json.loads(Path("data/publication/multi_prefecture_pilot.json").read_text(encoding="utf-8"))
    sources = {x["source_key"]: x for x in pilot["sources"]}
    listed_batch = parse_lodi_listed(listed_path, sources["lodi-listed"])
    applicant_batch = parse_lodi_applicants(applicant_path, sources["lodi-applicants"])
    if len(listed_batch.records) != 169 or len(applicant_batch.records) != 4:
        raise SystemExit("unexpected Lodi record denominator after transition")
    if Counter(x["source_status"] for x in listed_batch.records) != {"listed": 144, "renewal_update_in_progress": 25}:
        raise SystemExit("unexpected Lodi grouped status split after transition")
    if Counter(x["source_status"] for x in applicant_batch.records) != {"rejected_or_denied": 2, "pending": 2}:
        raise SystemExit("unexpected Lodi applicant status split after transition")
    print("Lodi reviewed transition validated: 173 observations; listed 144/25; applicants 2/2")


if __name__ == "__main__":
    listed_file, applicant_file = fetch_stable_sources()
    apply_transition()
    # Parser runtime is installed by the workflow before this script runs.
    validate_live_parse(listed_file, applicant_file)
