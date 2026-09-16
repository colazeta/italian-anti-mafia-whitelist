from __future__ import annotations

import csv
import json
from pathlib import Path

OLD_SHA = "ad64ab8669084bc31b80938a384b41849be4db28b448e9b2c0ce199f6af1d6ec"
NEW_SHA = "c3695018c56ba754614eff988011e0f9b2f6cb2d8e0f22a9823275c8659da613"
APP_SHA = "55aeab7e809cb90cc1ebd1ad9c1f08db78e91648a2c2e1a2b603188c77846228"
NEW_DOC = "docs/sources/lodi-operational-check-2026-09-16.md"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise SystemExit(f"{label}: expected exactly one token {old!r}, found {text.count(old)}")
    return text.replace(old, new)


def main() -> None:
    parser = Path("src/white_list_archive/parsers/lodi_sheets.py")
    text = parser.read_text(encoding="utf-8")
    text = replace_once(text, 'PARSER_VERSION = "1"', 'PARSER_VERSION = "2"', "parser version")
    text = replace_once(text, '_REFERENCE_DATE = "2026-09-15"', '_REFERENCE_DATE = "2026-09-16"', "reference date")
    text = replace_once(text, f'_LISTED_SHA256 = "{OLD_SHA}"', f'_LISTED_SHA256 = "{NEW_SHA}"', "listed SHA")
    parser.write_text(text, encoding="utf-8")

    test = Path("tests/test_lodi_parser_semantics.py")
    text = test.read_text(encoding="utf-8")
    text = replace_once(text, 'assert lodi._REFERENCE_DATE == "2026-09-15"', 'assert lodi._REFERENCE_DATE == "2026-09-16"', "test reference date")
    text = replace_once(text, f'assert lodi._LISTED_SHA256 == "{OLD_SHA}"', f'assert lodi._LISTED_SHA256 == "{NEW_SHA}"', "test listed SHA")
    test.write_text(text, encoding="utf-8")

    pilot_path = Path("data/publication/multi_prefecture_pilot.json")
    pilot = json.loads(pilot_path.read_text(encoding="utf-8"))
    sources = {item["source_key"]: item for item in pilot["sources"]}
    listed = sources["lodi-listed"]
    applicants = sources["lodi-applicants"]
    if listed["sha256"] != OLD_SHA or listed["expected_source_rows"] != 169:
        raise SystemExit("unexpected pre-transition lodi-listed config")
    if applicants["sha256"] != APP_SHA or applicants["expected_source_rows"] != 4:
        raise SystemExit("unexpected pre-transition lodi-applicants config")
    listed.update(
        reference_date="2026-09-16",
        last_source_update="2026-09-16",
        sha256=NEW_SHA,
        notes=(
            "Official mutable Google Sheet linked by the Prefettura di Lodi. Two independent no-cache GETs on 16 September 2026 were byte-identical at the approved SHA-256. "
            "The physical, section-membership and grouped-record denominators remain 324, 291 and 169 (146 listed; 23 renewal/update in progress). "
            "Exact comparison with the preserved 15 September capture identifies only two row-level semantic transitions: KUMAR S.n.c. di Kumar Devinder e C. (03030560969) is now explicitly in aggiornamento with unchanged 23/10/2025–23/10/2026 dates; "
            "Z.A. AUTOTRASPORTI S.r.l. (04220560967) is now ordinarily listed with source dates 16/09/2026–16/09/2027 instead of the previous in-aggiornamento 13/08/2025–13/08/2026 row. "
            f"Exact evidence is documented in {NEW_DOC}."
        ),
    )
    applicants.update(
        reference_date="2026-09-16",
        last_source_update="2026-09-16",
        notes=(
            "Official applicant tab linked by the Prefettura di Lodi. Two independent no-cache GETs on 16 September 2026 are byte-identical to each other and to the approved 15 September capture. "
            "The four positively identified observations remain unchanged: two explicit denials with source-explicit decision dates and two records explicitly in istruttoria. "
            "No applicant status or completeness is inferred from failed search. "
            f"Exact evidence is documented in {NEW_DOC}."
        ),
    )
    pilot_path.write_text(json.dumps(pilot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    inv_path = Path("data/source_registry/source_series_inventory.csv")
    with inv_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames
        rows = list(reader)
    found: set[str] = set()
    for row in rows:
        if row["source_series_key"] == "lodi-listed":
            row["verified_date"] = "2026-09-16"
            row["notes"] = (
                "Official Lodi landing page revalidated 16 September 2026 and positively exposes the registered-company Google Sheet tab. "
                f"Two independent no-cache CSV exports are byte-identical at SHA-256 {NEW_SHA}. Structure and grouped denominator remain 291 statutory-section memberships and 169 public observations; "
                f"two exact semantic row changes versus the preserved 15 September capture are documented in {NEW_DOC}."
            )
            found.add("listed")
        elif row["source_series_key"] == "lodi-applicants":
            row["verified_date"] = "2026-09-16"
            row["notes"] = (
                "Official Lodi landing page revalidated 16 September 2026 and positively exposes the requesting-company Google Sheet tab. "
                f"Two independent no-cache CSV exports remain byte-identical to the approved SHA-256 {APP_SHA}; the four source-backed applicant observations are unchanged. "
                f"Exact evidence is documented in {NEW_DOC}."
            )
            found.add("applicants")
    if found != {"listed", "applicants"}:
        raise SystemExit(f"Lodi inventory rows not found: {found}")
    with inv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    cov_path = Path("data/monitoring/national_coverage.json")
    cov = json.loads(cov_path.read_text(encoding="utf-8"))
    matches = [item for item in cov["prefectures"] if item["authority_key"] == "lodi"]
    if len(matches) != 1:
        raise SystemExit("expected one Lodi monitoring entry")
    entry = matches[0]
    if entry["known_content_sha256"] != [OLD_SHA, APP_SHA]:
        raise SystemExit(f"unexpected Lodi monitoring hashes: {entry['known_content_sha256']}")
    entry["latest_source_reference_date"] = "2026-09-16"
    entry["last_successful_investigation_on"] = "2026-09-16"
    entry["known_content_sha256"] = [NEW_SHA, APP_SHA]
    entry["unresolved_issue"] = [
        "The official Google Sheet is mutable and exposes no reliable edition date; 2026-09-16 is the current byte-pinned observation/capture boundary, not an inferred publication date.",
        "Canonical hosted-database integration and independent durable-evidence verification remain governed under #16; public source observations are validated independently of that infrastructure.",
    ]
    if NEW_DOC not in entry["completion_evidence"]:
        entry["completion_evidence"].append(NEW_DOC)
    if NEW_DOC not in entry["evidence"]:
        entry["evidence"].append(NEW_DOC)
    cov_path.write_text(json.dumps(cov, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    doc = Path(NEW_DOC)
    doc.write_text(
        """# Lodi operational source transition — 16 September 2026

## Scope

This note records the evidence review required after the mutable official Lodi registered-company Google Sheet changed after the 15 September approval. It does not infer a legal publication date from the observation date.

## Official publication surface

- Authority: Prefettura di Lodi.
- Official White List page: `https://prefettura.interno.gov.it/it/prefetture/lodi/evidenza/white-list`.
- The page continues to positively expose separate registered-company and requesting-company Google Sheet tabs.
- Both populations were fetched twice independently with cache-bypass parameters on 16 September 2026.

## Registered-company transition

The two current captures are byte-identical:

- SHA-256: `c3695018c56ba754614eff988011e0f9b2f6cb2d8e0f22a9823275c8659da613`.
- Size: 36,372 bytes.
- Physical CSV rows: 324, all exactly seven columns.
- Positively identifiable statutory-section membership rows: 291.
- Section denominators are unchanged: I 44; II 24; III 47; IV 18; V 55; VI 54; VII 6; VIII 1; IX 3; X 39.
- Source-row status totals are unchanged: 254 ordinary listed memberships and 37 explicitly in aggiornamento.
- Conservative grouping remains exactly 169 public observations: 146 `listed` and 23 `renewal_update_in_progress`.

Exact comparison with the preserved 15 September approved capture (`ad64ab8669084bc31b80938a384b41849be4db28b448e9b2c0ce199f6af1d6ec`) yields exactly two changed CSV rows and no insertions or removals:

1. `KUMAR S.n.c. di Kumar Devinder e C.` — identifier `03030560969`: dates remain `23/10/2025` to `23/10/2026`; the status marker changes from blank to `in aggiornamento`, so the source status becomes `renewal_update_in_progress`.
2. `Z.A. AUTOTRASPORTI S.r.l.` — identifier `04220560967`: the previous `13/08/2025` to `13/08/2026` row marked `in aggiornamento` is replaced by an ordinary listed row dated `16/09/2026` to `16/09/2027`.

The two changes offset in the aggregate status counts; therefore the 169-record listed-series denominator and its 146/23 status split remain unchanged. The project nevertheless approves the new raw byte identity explicitly rather than treating equal denominators as evidence of unchanged content.

## Applicant population

The two current applicant captures are byte-identical and also identical to the 15 September approved capture:

- SHA-256: `55aeab7e809cb90cc1ebd1ad9c1f08db78e91648a2c2e1a2b603188c77846228`.
- Size: 1,388 bytes.
- Physical CSV rows: 8.
- Positively identifiable observations: 4.
- Statuses remain two explicit denials and two `pending` / `IN ISTRUTTORIA` observations.

No applicant transition is inferred because none is observed.

## Approval boundary

The current Lodi public-source boundary remains 173 observations: 169 registered-series observations plus 4 applicant-series observations. The registered-series bytes are promoted only after the two independent captures, exact historical comparison, parser tests and national publication build pass. `durable_evidence_verified` remains a separate control and is not promoted by this source transition.
""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
