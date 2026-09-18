from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from urllib.request import Request, urlopen

import pdfplumber

OUT = Path("tmp/lecce-semantic2")
USER_AGENT = "italian-anti-mafia-whitelist/0.1 (+Lecce semantic source audit)"
LISTED_URL = "https://prefettura.interno.gov.it/sites/default/files/49/2026-09/elenco-white-list-per-categoria-aggiornato-9-settembre-2026.pdf"
LISTED_SHA = "acbe7b735107d48735bc8d01902fc73d49f00e6d8d6ef11dc0c1f9dfd344765d"
APPLICANTS_URL = "https://prefettura.interno.gov.it/sites/default/files/49/2026-09/elenco-richiedenti-iscrizione-aggiornato-9-settembre-2026.pdf"
APPLICANTS_SHA = "9d94226065ea80c35a140da93c74ed404ceea79018a725f755768b1a55a30124"
ID_RE = re.compile(r"(?<![A-Za-z0-9])(?:\d{11}|[A-Za-z0-9]{16})(?![A-Za-z0-9])")
DATE_RE = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")
SECTION_RE = re.compile(r"SEZIONE\s+([IVX]+)\s*[–—-]", re.I)


def clean(value: object) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split())


def fetch_twice(url: str, expected_sha: str, name: str) -> Path:
    req = lambda: Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/pdf,*/*", "Cache-Control": "no-cache"})
    with urlopen(req(), timeout=90) as response:  # noqa: S310 - fixed official source
        one = response.read()
    with urlopen(req(), timeout=90) as response:  # noqa: S310 - fixed official source
        two = response.read()
    if one != two:
        raise RuntimeError(f"{name}: independent captures differ")
    digest = hashlib.sha256(one).hexdigest()
    if digest != expected_sha:
        raise RuntimeError(f"{name}: raw source changed to {digest}")
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.pdf"
    path.write_bytes(one)
    return path


def valid_date(raw: str) -> bool:
    match = DATE_RE.fullmatch(clean(raw))
    if match is None:
        return False
    day, month, year = map(int, match.groups())
    try:
        date(year, month, day)
    except ValueError:
        return False
    return True


def identifiers(raw: str) -> tuple[str, ...]:
    found: list[str] = []
    for match in ID_RE.finditer(clean(raw)):
        value = match.group(0).upper()
        if value not in found:
            found.append(value)
    return tuple(found)


def key(name: str, office: str, raw_identifier: str) -> str:
    found = identifiers(raw_identifier)
    if found:
        return "ids:" + "|".join(sorted(found))
    return f"fallback:{clean(name).casefold()}|{clean(office).casefold()}"


def table_rows(page: pdfplumber.page.Page) -> list[list[str]]:
    tables = page.find_tables()
    if len(tables) != 1:
        raise RuntimeError(f"page {page.page_number}: expected exactly one table; got {len(tables)}")
    return [[clean(cell) for cell in row] for row in (tables[0].extract() or []) if any(clean(cell) for cell in row)]


def is_listed_data(row: list[str]) -> bool:
    if len(row) != 7 or not clean(row[0]):
        return False
    # The audited source uses fixed columns: name, registered office, secondary office,
    # identifier, listing date, expiry date, update marker. Require visible date digits in
    # the two date columns so malformed source dates are retained rather than silently lost.
    return bool(re.search(r"\d", clean(row[4]) + clean(row[5])))


def audit_listed(path: Path) -> dict[str, object]:
    by_identity: dict[str, list[dict[str, object]]] = defaultdict(list)
    section_rows: Counter[str] = Counter()
    update_values: Counter[str] = Counter()
    nondata_first_cells: Counter[str] = Counter()
    invalid_dates: list[dict[str, object]] = []
    raw_rows = structured_ids = raw_only = blanks = multi_ids = 0
    current_section = ""
    page_sections: dict[int, str] = {}

    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            hits = SECTION_RE.findall(text)
            if len(hits) > 1:
                raise RuntimeError(f"listed page {page.page_number}: multiple section headings {hits!r}")
            if hits:
                current_section = hits[0].upper()
            if not current_section:
                raise RuntimeError(f"listed page {page.page_number}: no section context")
            page_sections[page.page_number] = current_section
            for row_number, row in enumerate(table_rows(page), 1):
                if not is_listed_data(row):
                    nondata_first_cells[clean(row[0])[:100]] += 1
                    continue
                raw_rows += 1
                section_rows[current_section] += 1
                name, office, secondary, raw_id, listing, expiry, update = row
                found = identifiers(raw_id)
                if found:
                    structured_ids += 1
                    multi_ids += len(found) > 1
                elif raw_id:
                    raw_only += 1
                else:
                    blanks += 1
                if listing and not valid_date(listing):
                    invalid_dates.append({"page": page.page_number, "row": row_number, "field": "listing", "raw": listing})
                if expiry and not valid_date(expiry):
                    invalid_dates.append({"page": page.page_number, "row": row_number, "field": "expiry", "raw": expiry})
                update_values[update] += 1
                by_identity[key(name, office, raw_id)].append(
                    {
                        "page": page.page_number,
                        "section": current_section,
                        "name": name,
                        "office": office,
                        "secondary": secondary,
                        "raw_identifier": raw_id,
                        "listing": listing,
                        "expiry": expiry,
                        "update": update,
                    }
                )

    conflict_counts: Counter[str] = Counter()
    conflict_examples: list[dict[str, object]] = []
    section_cardinality: Counter[int] = Counter()
    for identity, observations in by_identity.items():
        section_cardinality[len({str(row["section"]) for row in observations})] += 1
        fields = {
            "name": {str(row["name"]) for row in observations},
            "office": {str(row["office"]) for row in observations},
            "secondary": {str(row["secondary"]) for row in observations},
            "listing": {str(row["listing"]) for row in observations},
            "expiry": {str(row["expiry"]) for row in observations},
            "update": {str(row["update"]) for row in observations},
        }
        changed = [field for field, values in fields.items() if len(values) > 1]
        for field in changed:
            conflict_counts[field] += 1
        if changed and len(conflict_examples) < 10:
            conflict_examples.append({"identity": identity, "changed": changed, "observations": observations})

    return {
        "pdf_pages": len(page_sections),
        "page_sections": page_sections,
        "raw_sector_rows": raw_rows,
        "section_raw_rows": dict(section_rows),
        "unique_identity_count": len(by_identity),
        "cross_section_duplicate_rows": raw_rows - len(by_identity),
        "section_cardinality_per_identity": {str(k): v for k, v in sorted(section_cardinality.items())},
        "structured_identifier_rows": structured_ids,
        "raw_identifier_only_rows": raw_only,
        "blank_identifier_rows": blanks,
        "multi_identifier_rows": multi_ids,
        "update_value_counts": dict(update_values),
        "invalid_date_count": len(invalid_dates),
        "invalid_date_examples": invalid_dates[:20],
        "cross_section_conflict_counts": dict(conflict_counts),
        "cross_section_conflict_examples": conflict_examples,
        "nondata_first_cell_counts": dict(nondata_first_cells),
    }


def is_applicant_data(row: list[str]) -> bool:
    if len(row) != 4 or not clean(row[0]):
        return False
    return bool(re.search(r"\d", clean(row[3])))


def audit_applicants(path: Path) -> dict[str, object]:
    identities: Counter[str] = Counter()
    raw_rows = structured_ids = raw_only = blanks = multi_ids = 0
    invalid_dates: list[dict[str, object]] = []
    nondata_first_cells: Counter[str] = Counter()
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for row_number, row in enumerate(table_rows(page), 1):
                if not is_applicant_data(row):
                    nondata_first_cells[clean(row[0])[:100]] += 1
                    continue
                raw_rows += 1
                name, office, raw_id, application = row
                found = identifiers(raw_id)
                if found:
                    structured_ids += 1
                    multi_ids += len(found) > 1
                elif raw_id:
                    raw_only += 1
                else:
                    blanks += 1
                if not valid_date(application):
                    invalid_dates.append({"page": page.page_number, "row": row_number, "raw": application})
                identities[key(name, office, raw_id)] += 1
    return {
        "pdf_pages": 10,
        "rows": raw_rows,
        "unique_identity_count": len(identities),
        "duplicate_identity_count": sum(count > 1 for count in identities.values()),
        "duplicate_identity_occurrences": sum(count - 1 for count in identities.values() if count > 1),
        "structured_identifier_rows": structured_ids,
        "raw_identifier_only_rows": raw_only,
        "blank_identifier_rows": blanks,
        "multi_identifier_rows": multi_ids,
        "invalid_date_count": len(invalid_dates),
        "invalid_date_examples": invalid_dates[:20],
        "nondata_first_cell_counts": dict(nondata_first_cells),
    }


def main() -> None:
    listed = fetch_twice(LISTED_URL, LISTED_SHA, "lecce_listed")
    applicants = fetch_twice(APPLICANTS_URL, APPLICANTS_SHA, "lecce_applicants")
    result = {
        "listed_url": LISTED_URL,
        "listed_sha256": LISTED_SHA,
        "applicants_url": APPLICANTS_URL,
        "applicants_sha256": APPLICANTS_SHA,
        "listed": audit_listed(listed),
        "applicants": audit_applicants(applicants),
    }
    (OUT / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
