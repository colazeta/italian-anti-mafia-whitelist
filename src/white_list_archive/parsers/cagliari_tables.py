from __future__ import annotations

import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

import pdfplumber

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _clean, _record

PARSER_VERSION = "1"
_REFERENCE_DATE = "2026-09-06"
_LISTED_PAGES = 24
_APPLICANT_PAGES = 2
_EXPECTED_SECTOR_ROWS = 1832
_EXPECTED_SECTOR_COUNTS = {1: 263, 2: 117, 3: 297, 4: 125, 5: 348, 6: 266, 7: 53, 8: 33, 9: 62, 10: 268}
_EXPECTED_SECTOR_STATUS_COUNTS = {"listed": 1723, "renewal_update_in_progress": 109}
_EXPECTED_LISTED_RECORDS = 750
_EXPECTED_LISTED_STATUS_COUNTS = {"listed": 713, "renewal_update_in_progress": 37}
_EXPECTED_APPLICANT_PAGE_COUNTS = (40, 11)
_EXPECTED_APPLICANT_RECORDS = 51
_EXPECTED_APPLICANT_STATUS_COUNTS = {"pending": 51}
_EXPECTED_LISTED_IDENTIFIER_COVERAGE = 749
_EXPECTED_APPLICANT_IDENTIFIER_COVERAGE = 50

_DATE = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")
_SECTION = re.compile(r"^sez\.\s*0?(10|[1-9])$", re.I)
_STRICT_IDENTIFIER = re.compile(r"^(?:\d{11}|[A-Za-z0-9]{16})$", re.I)
_ROMAN_TO_SECTION = {
    "I": 1,
    "II": 2,
    "III": 3,
    "IV": 4,
    "V": 5,
    "VI": 6,
    "VII": 7,
    "VIII": 8,
    "IX": 9,
    "X": 10,
}


def _strict_identifiers(value: str) -> list[str]:
    raw = _clean(value).upper()
    return [raw] if _STRICT_IDENTIFIER.fullmatch(raw) else []


def _parse_source_date(value: str) -> str:
    raw = _clean(value)
    match = _DATE.fullmatch(raw)
    if not match:
        raise RuntimeError(f"Cagliari unreviewed date typography: {raw!r}")
    day, month, year = map(int, match.groups())
    try:
        return date(year, month, day).isoformat()
    except ValueError as exc:
        raise RuntimeError(f"Cagliari invalid calendar date: {raw!r}") from exc


def _section_number(value: str) -> int | None:
    match = _SECTION.fullmatch(_clean(value))
    return int(match.group(1)) if match else None


def _listed_status(note: str) -> str:
    folded = _clean(note).casefold()
    if "aggiornamento in corso" in folded or "rinnovo" in folded:
        return "renewal_update_in_progress"
    return "listed"


def _requested_sections(raw: str) -> list[str]:
    value = _clean(raw)
    if not value:
        return []
    result: list[str] = []
    for token in [item.strip().upper() for item in value.split(",") if item.strip()]:
        if token not in _ROMAN_TO_SECTION:
            raise RuntimeError(f"Cagliari unknown requested section token: {token!r}")
        label = f"Sezione {_ROMAN_TO_SECTION[token]}"
        if label not in result:
            result.append(label)
    return result


def _validate_cfg(cfg: dict[str, Any], expected_source_key: str) -> None:
    if cfg.get("source_key") != expected_source_key:
        raise RuntimeError(f"Cagliari parser/source mismatch: {cfg.get('source_key')!r} != {expected_source_key!r}")
    if cfg.get("authority_key") != "cagliari":
        raise RuntimeError("Cagliari parser bound to a non-Cagliari authority")
    if cfg.get("reference_date") != _REFERENCE_DATE:
        raise RuntimeError(f"Cagliari reference date drift: {cfg.get('reference_date')!r}")


def parse_cagliari_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(cfg, "cagliari-listed")
    sector_rows: list[dict[str, Any]] = []

    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _LISTED_PAGES:
            raise RuntimeError(f"Cagliari listed page-count drift: {len(pdf.pages)} != {_LISTED_PAGES}")
        for page_number, page in enumerate(pdf.pages, start=1):
            for table_number, table in enumerate(page.extract_tables(), start=1):
                for row_number, row in enumerate(table or [], start=1):
                    cells = [_clean(cell) for cell in row]
                    if len(cells) != 9:
                        continue
                    ordinal, section_raw, name, office, secondary, identifier_raw, listing_raw, expiry_raw, note = cells
                    section = _section_number(section_raw)
                    if not ordinal.isdigit() or section is None:
                        continue
                    if not (_DATE.fullmatch(listing_raw) and _DATE.fullmatch(expiry_raw)):
                        continue
                    sector_rows.append(
                        {
                            "page": page_number,
                            "table": table_number,
                            "row": row_number,
                            "ordinal": int(ordinal),
                            "section": section,
                            "section_raw": section_raw,
                            "name": name,
                            "office": office,
                            "secondary": secondary,
                            "identifier_raw": identifier_raw,
                            "listing_raw": listing_raw,
                            "expiry_raw": expiry_raw,
                            "note": note,
                            "status": _listed_status(note),
                        }
                    )

    if len(sector_rows) != _EXPECTED_SECTOR_ROWS:
        raise RuntimeError(f"Cagliari listed source-row drift: {len(sector_rows)} != {_EXPECTED_SECTOR_ROWS}")
    section_counts = dict(Counter(row["section"] for row in sector_rows))
    if section_counts != _EXPECTED_SECTOR_COUNTS:
        raise RuntimeError(f"Cagliari listed section-count drift: {section_counts!r}")
    sector_status_counts = dict(Counter(row["status"] for row in sector_rows))
    if sector_status_counts != _EXPECTED_SECTOR_STATUS_COUNTS:
        raise RuntimeError(f"Cagliari listed source-status drift: {sector_status_counts!r}")

    grouped: dict[tuple[str, ...], dict[str, Any]] = {}
    for row in sector_rows:
        # Cagliari repeats the same company observation in every applicable section.
        # Group only source rows whose identity, address, dates, status and note are
        # identical after whitespace/case normalisation. A dedicated evidence audit
        # established that this conservative key and broader identity/date grouping
        # both produce 750 groups with zero name/address conflicts.
        key = (
            row["name"].casefold(),
            row["identifier_raw"].casefold(),
            row["office"].casefold(),
            row["secondary"].casefold(),
            row["listing_raw"],
            row["expiry_raw"],
            row["status"],
            row["note"].casefold(),
        )
        group = grouped.setdefault(key, {"row": row, "sections": [], "locators": []})
        if row["section"] in group["sections"]:
            raise RuntimeError(
                f"Cagliari duplicate same-section row in one source observation: {row['name']!r}, section {row['section']}"
            )
        group["sections"].append(row["section"])
        group["locators"].append(f"p{row['page']}:t{row['table']}:r{row['row']}")

    if len(grouped) != _EXPECTED_LISTED_RECORDS:
        raise RuntimeError(f"Cagliari listed grouping drift: {len(grouped)} != {_EXPECTED_LISTED_RECORDS}")

    records: list[dict[str, Any]] = []
    for group in grouped.values():
        row = group["row"]
        listing_date = _parse_source_date(row["listing_raw"])
        expiry_date = _parse_source_date(row["expiry_raw"])
        sections = sorted(group["sections"])
        record = _record(
            cfg,
            len(records) + 1,
            name=row["name"],
            office=row["office"],
            secondary=row["secondary"],
            identifier_raw=row["identifier_raw"],
            activities=[f"Sezione {section}" for section in sections],
            status=row["status"],
            outcome_raw=row["note"],
            listing_date=listing_date,
            expiry_date=expiry_date,
            primary_date_label="Data iscrizione",
            source_fields={
                "sections_raw": [f"sez.{section:02d}" for section in sections],
                "source_row_locators": group["locators"],
                "listing_date_raw_variants": [row["listing_raw"]],
                "expiry_date_raw_variants": [row["expiry_raw"]],
                "status_note_raw": row["note"],
            },
        )
        # Keep identifier validation explicitly fail-closed: malformed source values
        # remain visible in identifier_field_raw but never become canonical IDs.
        record["identifiers"] = _strict_identifiers(row["identifier_raw"])
        records.append(record)

    status_counts = dict(Counter(record["source_status"] for record in records))
    if status_counts != _EXPECTED_LISTED_STATUS_COUNTS:
        raise RuntimeError(f"Cagliari listed grouped-status drift: {status_counts!r}")
    identifier_coverage = sum(bool(record["identifiers"]) for record in records)
    if identifier_coverage != _EXPECTED_LISTED_IDENTIFIER_COVERAGE:
        raise RuntimeError(
            f"Cagliari listed identifier-coverage drift: {identifier_coverage} != {_EXPECTED_LISTED_IDENTIFIER_COVERAGE}"
        )

    diagnostics = {
        "parser": "cagliari_listed",
        "parser_version": PARSER_VERSION,
        "source_pages": _LISTED_PAGES,
        "sector_rows": len(sector_rows),
        "section_counts": section_counts,
        "source_status_counts": sector_status_counts,
        "public_records": len(records),
        "status_counts": status_counts,
        "identifier_coverage": identifier_coverage,
        "dropped_date_rows": 0,
    }
    return ParsedBatch(records=records, diagnostics=diagnostics)


def parse_cagliari_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(cfg, "cagliari-applicants")
    source_rows: list[dict[str, Any]] = []
    page_counts: list[int] = []

    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _APPLICANT_PAGES:
            raise RuntimeError(f"Cagliari applicant page-count drift: {len(pdf.pages)} != {_APPLICANT_PAGES}")
        for page_number, page in enumerate(pdf.pages, start=1):
            page_rows = 0
            for table_number, table in enumerate(page.extract_tables(), start=1):
                for row_number, row in enumerate(table or [], start=1):
                    cells = [_clean(cell) for cell in row]
                    if len(cells) == 8:
                        ordinal, name, office, secondary, identifier_raw, requested_raw, application_raw, outcome = cells
                    elif len(cells) == 7:
                        ordinal, name, office, identifier_raw, requested_raw, application_raw, outcome = cells
                        secondary = ""
                    else:
                        continue
                    if not ordinal.isdigit() or "istruttoria" not in outcome.casefold():
                        continue
                    if not _DATE.fullmatch(application_raw):
                        raise RuntimeError(
                            f"Cagliari applicant unreviewed application date at page {page_number}, row {row_number}: {application_raw!r}"
                        )
                    source_rows.append(
                        {
                            "page": page_number,
                            "table": table_number,
                            "row": row_number,
                            "ordinal": int(ordinal),
                            "name": name,
                            "office": office,
                            "secondary": secondary,
                            "identifier_raw": identifier_raw,
                            "requested_raw": requested_raw,
                            "application_raw": application_raw,
                            "outcome": outcome,
                        }
                    )
                    page_rows += 1
            page_counts.append(page_rows)

    if tuple(page_counts) != _EXPECTED_APPLICANT_PAGE_COUNTS:
        raise RuntimeError(f"Cagliari applicant page-row drift: {tuple(page_counts)!r} != {_EXPECTED_APPLICANT_PAGE_COUNTS!r}")
    if len(source_rows) != _EXPECTED_APPLICANT_RECORDS:
        raise RuntimeError(f"Cagliari applicant row drift: {len(source_rows)} != {_EXPECTED_APPLICANT_RECORDS}")
    if len({row["ordinal"] for row in source_rows}) != len(source_rows):
        raise RuntimeError("Cagliari applicant duplicate source ordinal")

    records: list[dict[str, Any]] = []
    for row in source_rows:
        activities = _requested_sections(row["requested_raw"])
        record = _record(
            cfg,
            len(records) + 1,
            name=row["name"],
            office=row["office"],
            secondary=row["secondary"],
            identifier_raw=row["identifier_raw"],
            activities=activities,
            status="pending",
            outcome_raw=row["outcome"],
            application_date=_parse_source_date(row["application_raw"]),
            primary_date_label="Data presentazione istanza",
            source_fields={
                "requested_sections_raw": row["requested_raw"],
                "application_date_raw": row["application_raw"],
                "outcome_raw": row["outcome"],
                "source_row_locator": f"p{row['page']}:t{row['table']}:r{row['row']}",
            },
        )
        record["identifiers"] = _strict_identifiers(row["identifier_raw"])
        records.append(record)

    status_counts = dict(Counter(record["source_status"] for record in records))
    if status_counts != _EXPECTED_APPLICANT_STATUS_COUNTS:
        raise RuntimeError(f"Cagliari applicant status drift: {status_counts!r}")
    identifier_coverage = sum(bool(record["identifiers"]) for record in records)
    if identifier_coverage != _EXPECTED_APPLICANT_IDENTIFIER_COVERAGE:
        raise RuntimeError(
            f"Cagliari applicant identifier-coverage drift: {identifier_coverage} != {_EXPECTED_APPLICANT_IDENTIFIER_COVERAGE}"
        )

    diagnostics = {
        "parser": "cagliari_applicants",
        "parser_version": PARSER_VERSION,
        "source_pages": _APPLICANT_PAGES,
        "page_row_counts": page_counts,
        "public_records": len(records),
        "status_counts": status_counts,
        "identifier_coverage": identifier_coverage,
        "dropped_date_rows": 0,
    }
    return ParsedBatch(records=records, diagnostics=diagnostics)


PARSERS = {
    "cagliari_listed": parse_cagliari_listed,
    "cagliari_applicants": parse_cagliari_applicants,
}
