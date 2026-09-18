from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from urllib.request import Request, urlopen

import pdfplumber

OUT = Path("tmp/lecce-semantic")
USER_AGENT = "italian-anti-mafia-whitelist/0.1 (+Lecce semantic source audit)"
SOURCES = {
    "listed": {
        "url": "https://prefettura.interno.gov.it/sites/default/files/49/2026-09/elenco-white-list-per-categoria-aggiornato-9-settembre-2026.pdf",
        "sha256": "acbe7b735107d48735bc8d01902fc73d49f00e6d8d6ef11dc0c1f9dfd344765d",
    },
    "applicants": {
        "url": "https://prefettura.interno.gov.it/sites/default/files/49/2026-09/elenco-richiedenti-iscrizione-aggiornato-9-settembre-2026.pdf",
        "sha256": "9d94226065ea80c35a140da93c74ed404ceea79018a725f755768b1a55a30124",
    },
}
ID_RE = re.compile(r"(?<![A-Za-z0-9])(?:\d{11}|[A-Za-z0-9]{16})(?![A-Za-z0-9])")
DATE_RE = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")
SECTION_RE = re.compile(r"SEZIONE\s+([IVX]+)\s*[–—-]\s*([^\n]+)", re.I)


def clean(value: object) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split())


def fetch(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/pdf,*/*", "Cache-Control": "no-cache"})
    with urlopen(request, timeout=90) as response:  # noqa: S310 - fixed official sources
        return response.read()


def download(kind: str) -> Path:
    spec = SOURCES[kind]
    body1 = fetch(spec["url"])
    body2 = fetch(spec["url"])
    if body1 != body2:
        raise RuntimeError(f"{kind}: independent captures differ")
    digest = hashlib.sha256(body1).hexdigest()
    if digest != spec["sha256"]:
        raise RuntimeError(f"{kind}: source changed: {digest}")
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"lecce_{kind}.pdf"
    path.write_bytes(body1)
    return path


def ids(raw: str) -> tuple[str, ...]:
    found: list[str] = []
    for match in ID_RE.finditer(clean(raw)):
        value = match.group(0).upper()
        if value not in found:
            found.append(value)
    return tuple(found)


def valid_date(raw: str) -> bool:
    match = DATE_RE.fullmatch(clean(raw))
    if not match:
        return False
    day, month, year = map(int, match.groups())
    try:
        date(year, month, day)
    except ValueError:
        return False
    return True


def identity(row: list[str], name_i: int, office_i: int, id_i: int) -> str:
    found = ids(row[id_i])
    if found:
        return "ids:" + "|".join(sorted(found))
    return f"fallback:{clean(row[name_i]).casefold()}|{clean(row[office_i]).casefold()}"


def find_header(rows: list[list[str]], required: tuple[str, ...]) -> tuple[int, list[str]]:
    matches: list[tuple[int, list[str]]] = []
    for index, row in enumerate(rows):
        folded = [clean(cell).casefold() for cell in row]
        if all(any(token in cell for cell in folded) for token in required):
            matches.append((index, row))
    if len(matches) != 1:
        raise RuntimeError(f"expected one evidence header; found {len(matches)}: {matches[:3]!r}")
    return matches[0]


def listed_summary(path: Path) -> dict[str, object]:
    headers: Counter[tuple[str, ...]] = Counter()
    sections: Counter[str] = Counter()
    section_pages: dict[str, list[int]] = defaultdict(list)
    update_values: Counter[str] = Counter()
    rows_by_identity: dict[str, list[dict[str, str | int]]] = defaultdict(list)
    invalid_dates: list[dict[str, object]] = []
    nondata_after_header: list[dict[str, object]] = []
    raw_rows = 0
    rows_with_ids = 0
    raw_only_ids = 0
    blank_id_rows = 0
    multi_id_rows = 0
    current_section = ""

    with pdfplumber.open(path) as pdf:
        for page_number, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            hits = SECTION_RE.findall(text)
            if len(hits) > 1:
                raise RuntimeError(f"page {page_number}: multiple section headings: {hits!r}")
            if hits:
                current_section = hits[0][0].upper()
            if not current_section:
                raise RuntimeError(f"page {page_number}: no section context")
            section_pages[current_section].append(page_number)

            tables = page.find_tables()
            if len(tables) != 1:
                raise RuntimeError(f"page {page_number}: expected one table, got {len(tables)}")
            rows = [[clean(cell) for cell in row] for row in (tables[0].extract() or []) if any(clean(cell) for cell in row)]
            header_index, header = find_header(
                rows,
                ("denominazione", "sede legale", "codice fiscale", "data iscrizione", "data scadenza", "aggiornamento in corso"),
            )
            headers[tuple(header)] += 1
            folded = [cell.casefold() for cell in header]
            name_i = next(i for i, cell in enumerate(folded) if "denominazione" in cell)
            office_i = next(i for i, cell in enumerate(folded) if "sede legale" in cell)
            id_i = next(i for i, cell in enumerate(folded) if "codice fiscale" in cell)
            listing_i = next(i for i, cell in enumerate(folded) if "data iscrizione" in cell)
            expiry_i = next(i for i, cell in enumerate(folded) if "data scadenza" in cell)
            update_i = next(i for i, cell in enumerate(folded) if "aggiornamento in corso" in cell)
            if len(header) != 7:
                raise RuntimeError(f"page {page_number}: header width {len(header)}")

            for table_row, row in enumerate(rows[header_index + 1 :], header_index + 2):
                if len(row) != 7:
                    raise RuntimeError(f"page {page_number} row {table_row}: width {len(row)}")
                name = clean(row[name_i])
                listing = clean(row[listing_i])
                expiry = clean(row[expiry_i])
                update = clean(row[update_i])
                if not name or (not valid_date(listing) and not valid_date(expiry)):
                    nondata_after_header.append({"page": page_number, "row": table_row, "cells": row})
                    continue
                raw_rows += 1
                sections[current_section] += 1
                found = ids(row[id_i])
                if found:
                    rows_with_ids += 1
                    multi_id_rows += len(found) > 1
                elif clean(row[id_i]):
                    raw_only_ids += 1
                else:
                    blank_id_rows += 1
                if listing and not valid_date(listing):
                    invalid_dates.append({"page": page_number, "row": table_row, "field": "listing", "raw": listing})
                if expiry and not valid_date(expiry):
                    invalid_dates.append({"page": page_number, "row": table_row, "field": "expiry", "raw": expiry})
                update_values[update] += 1
                key = identity(row, name_i, office_i, id_i)
                rows_by_identity[key].append(
                    {
                        "page": page_number,
                        "section": current_section,
                        "name": name,
                        "office": clean(row[office_i]),
                        "identifier_raw": clean(row[id_i]),
                        "listing": listing,
                        "expiry": expiry,
                        "update": update,
                    }
                )

    conflict_counts: Counter[str] = Counter()
    conflict_examples: list[dict[str, object]] = []
    cardinality: Counter[int] = Counter()
    for key, observations in rows_by_identity.items():
        cardinality[len({str(item["section"]) for item in observations})] += 1
        fields = {
            "name": {str(item["name"]) for item in observations},
            "office": {str(item["office"]) for item in observations},
            "listing": {str(item["listing"]) for item in observations},
            "expiry": {str(item["expiry"]) for item in observations},
            "update": {str(item["update"]) for item in observations},
        }
        changed = [field for field, values in fields.items() if len(values) > 1]
        for field in changed:
            conflict_counts[field] += 1
        if changed and len(conflict_examples) < 12:
            conflict_examples.append({"identity": key, "changed_fields": changed, "observations": observations})

    return {
        "pdf_pages": len(section_pages.get("I", [])) + len(section_pages.get("II", [])) + len(section_pages.get("III", [])) + len(section_pages.get("IV", [])) + len(section_pages.get("V", [])) + len(section_pages.get("VI", [])) + len(section_pages.get("VII", [])) + len(section_pages.get("VIII", [])) + len(section_pages.get("IX", [])) + len(section_pages.get("X", [])),
        "header_variants": [{"count": count, "header": list(header)} for header, count in headers.items()],
        "section_pages": dict(section_pages),
        "raw_data_rows": raw_rows,
        "section_raw_rows": dict(sections),
        "unique_identity_count": len(rows_by_identity),
        "cross_section_duplicate_rows": raw_rows - len(rows_by_identity),
        "section_cardinality_per_identity": {str(k): v for k, v in sorted(cardinality.items())},
        "rows_with_structured_identifiers": rows_with_ids,
        "raw_identifier_only_rows": raw_only_ids,
        "blank_identifier_rows": blank_id_rows,
        "multi_identifier_rows": multi_id_rows,
        "update_value_counts": dict(update_values),
        "invalid_date_count": len(invalid_dates),
        "invalid_date_examples": invalid_dates[:20],
        "nondata_after_header_count": len(nondata_after_header),
        "nondata_after_header_examples": nondata_after_header[:12],
        "cross_section_conflict_counts": dict(conflict_counts),
        "cross_section_conflict_examples": conflict_examples,
    }


def applicants_summary(path: Path) -> dict[str, object]:
    headers: Counter[tuple[str, ...]] = Counter()
    identities: Counter[str] = Counter()
    invalid_dates: list[dict[str, object]] = []
    rows_total = 0
    rows_with_ids = 0
    raw_only_ids = 0
    blank_id_rows = 0
    multi_id_rows = 0
    with pdfplumber.open(path) as pdf:
        for page_number, page in enumerate(pdf.pages, 1):
            tables = page.find_tables()
            if len(tables) != 1:
                raise RuntimeError(f"applicant page {page_number}: expected one table")
            rows = [[clean(cell) for cell in row] for row in (tables[0].extract() or []) if any(clean(cell) for cell in row)]
            header_index, header = find_header(rows, ("ragione sociale", "sede legale", "codice fiscale", "data di presentazione"))
            headers[tuple(header)] += 1
            folded = [cell.casefold() for cell in header]
            name_i = next(i for i, cell in enumerate(folded) if "ragione sociale" in cell)
            office_i = next(i for i, cell in enumerate(folded) if "sede legale" in cell)
            id_i = next(i for i, cell in enumerate(folded) if "codice fiscale" in cell)
            date_i = next(i for i, cell in enumerate(folded) if "data di presentazione" in cell)
            for table_row, row in enumerate(rows[header_index + 1 :], header_index + 2):
                if len(row) != 4 or not clean(row[name_i]):
                    raise RuntimeError(f"applicant page {page_number} row {table_row}: row drift {row!r}")
                rows_total += 1
                found = ids(row[id_i])
                if found:
                    rows_with_ids += 1
                    multi_id_rows += len(found) > 1
                elif clean(row[id_i]):
                    raw_only_ids += 1
                else:
                    blank_id_rows += 1
                raw_date = clean(row[date_i])
                if not valid_date(raw_date):
                    invalid_dates.append({"page": page_number, "row": table_row, "raw": raw_date})
                identities[identity(row, name_i, office_i, id_i)] += 1
    return {
        "pdf_pages": 10,
        "header_variants": [{"count": count, "header": list(header)} for header, count in headers.items()],
        "rows": rows_total,
        "unique_identity_count": len(identities),
        "duplicate_identity_count": sum(count > 1 for count in identities.values()),
        "duplicate_identity_occurrences": sum(count - 1 for count in identities.values() if count > 1),
        "rows_with_structured_identifiers": rows_with_ids,
        "raw_identifier_only_rows": raw_only_ids,
        "blank_identifier_rows": blank_id_rows,
        "multi_identifier_rows": multi_id_rows,
        "invalid_date_count": len(invalid_dates),
        "invalid_date_examples": invalid_dates[:20],
    }


def main() -> None:
    listed = download("listed")
    applicants = download("applicants")
    result = {
        "listed_sha256": SOURCES["listed"]["sha256"],
        "applicants_sha256": SOURCES["applicants"]["sha256"],
        "listed": listed_summary(listed),
        "applicants": applicants_summary(applicants),
    }
    path = OUT / "lecce_semantic_summary.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
