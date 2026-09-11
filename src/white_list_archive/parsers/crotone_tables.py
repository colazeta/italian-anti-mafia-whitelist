from __future__ import annotations

import re
import unicodedata
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

import pdfplumber

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _clean, _record

PARSER_VERSION = "1"
_REFERENCE_DATE = "2026-09-11"
_LISTED_PAGES = 130
_APPLICANT_PAGES = 46
_EXPECTED_LISTED_SECTOR_ROWS = 743
_EXPECTED_LISTED_RECORDS = 328
_EXPECTED_LISTED_STATUS_COUNTS = {"listed": 73, "renewal_update_in_progress": 255}
_EXPECTED_APPLICANT_RECORDS = 180
_EXPECTED_APPLICANT_STATUS_COUNTS = {"pending": 180}
_EXPECTED_APPLICANT_CONTINUATIONS = 25

_MONTHS = {
    "gennaio": 1,
    "febbraio": 2,
    "marzo": 3,
    "aprile": 4,
    "maggio": 5,
    "giugno": 6,
    "luglio": 7,
    "agosto": 8,
    "settembre": 9,
    "ottobre": 10,
    "novembre": 11,
    "dicembre": 12,
}
_MONTH_ALT = "|".join(_MONTHS)
_DATE = re.compile(rf"^(\d{{1,2}})(?:°|º)?\s+({_MONTH_ALT})\s+(\d{{4}})$", re.I)
_DATE_PREFIX = re.compile(rf"^(\d{{1,2}})(?:°|º)?\s+({_MONTH_ALT})\s+(\d{{4}})(.*)$", re.I)
_REVIEWED_DATE_TYPOGRAPHY = {
    "23 giungo 2025": "23 giugno 2025",
}
_REVIEWED_AMBIGUOUS_DATE_RAW = {
    "17 febbraio 2015 15 febbraio 2022",
}
_REVIEWED_EXPIRY_TYPOGRAPHY = {
    "7 dicembre2022 Richiesta rinnovo": "7 dicembre 2022 Richiesta rinnovo",
    "14 giungo 2022 Richiesta rinnovo": "14 giugno 2022 Richiesta rinnovo",
}
_SECTION = re.compile(r"(?:SEZIONE|SEZ\.?)\s*(10|[1-9])\b", re.I)
_STRICT_IDENTIFIER = re.compile(r"^(?:\d{11}|[A-Za-z0-9]{16})$", re.I)


def _strict_identifiers(value: str) -> list[str]:
    raw = _clean(value).upper()
    return [raw] if _STRICT_IDENTIFIER.fullmatch(raw) else []


def _iso_date(day: str, month: str, year: str, *, raw: str) -> str:
    try:
        return date(int(year), _MONTHS[month.casefold()], int(day)).isoformat()
    except (KeyError, ValueError) as exc:
        raise RuntimeError(f"Crotone invalid calendar date: {raw!r}") from exc


def _parse_date(value: str, *, allow_blank: bool = False) -> str:
    raw = _clean(value)
    if not raw and allow_blank:
        return ""
    if raw in _REVIEWED_AMBIGUOUS_DATE_RAW:
        return ""
    parse_value = _REVIEWED_DATE_TYPOGRAPHY.get(raw, raw)
    match = _DATE.fullmatch(parse_value)
    if not match:
        raise RuntimeError(f"Crotone unreviewed date typography: {raw!r}")
    return _iso_date(*match.groups(), raw=raw)


def _parse_expiry(value: str) -> tuple[str, str]:
    raw = _clean(value)
    if not raw:
        return "", ""
    parse_value = _REVIEWED_EXPIRY_TYPOGRAPHY.get(raw, raw)
    match = _DATE_PREFIX.fullmatch(parse_value)
    if not match:
        raise RuntimeError(f"Crotone unreviewed expiry typography: {raw!r}")
    day, month, year, tail = match.groups()
    return _iso_date(day, month, year, raw=raw), _clean(tail)


def _status(expiry_tail: str, note: str) -> str:
    folded = f"{_clean(expiry_tail)} {_clean(note)}".casefold()
    if any(token in folded for token in ("rinnovo", "istruttoria", "aggiornamento")):
        return "renewal_update_in_progress"
    return "listed"


def _normalise_text(value: str) -> str:
    return _clean(unicodedata.normalize("NFKC", value or "")).casefold()


def _normalise_address(value: str) -> str:
    text = _normalise_text(value).replace("–", "-").replace("—", "-").replace("−", "-")
    text = re.sub(r"\s*([,;:/.-])\s*", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def _date_key(raw: str, parsed: str) -> str:
    return parsed or f"RAW:{_normalise_text(raw)}"


def _unique(values: list[str]) -> list[str]:
    out: list[str] = []
    for value in values:
        value = _clean(value)
        if value not in out:
            out.append(value)
    return out


def _validate_cfg(cfg: dict[str, Any], expected_source_key: str) -> None:
    if cfg.get("source_key") != expected_source_key:
        raise RuntimeError(f"Crotone parser/source mismatch: {cfg.get('source_key')!r} != {expected_source_key!r}")
    if cfg.get("authority_key") != "crotone":
        raise RuntimeError("Crotone parser bound to a non-Crotone authority")
    if cfg.get("reference_date") != _REFERENCE_DATE:
        raise RuntimeError(f"Crotone reference date drift: {cfg.get('reference_date')!r}")


def _is_header(cells: list[str]) -> bool:
    return bool(cells) and (
        cells[0].casefold() == "ragione sociale"
        or (len(cells) > 1 and not cells[0] and cells[1].casefold() == "partita iva")
    )


def parse_crotone_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(cfg, "crotone-listed")
    sector_rows: list[dict[str, Any]] = []
    current_section: int | None = None
    carried_identity_rows = 0

    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _LISTED_PAGES:
            raise RuntimeError(f"Crotone listed page-count drift: {len(pdf.pages)} != {_LISTED_PAGES}")
        for page_number, page in enumerate(pdf.pages, start=1):
            hits = [int(value) for value in _SECTION.findall(page.extract_text() or "")]
            if len(set(hits)) > 1:
                raise RuntimeError(f"Crotone ambiguous section headings on page {page_number}: {hits!r}")
            page_section = hits[0] if hits else None
            tables = page.extract_tables() or []
            nonempty = [
                [_clean(cell) for cell in row]
                for table in tables
                for row in (table or [])
                if any(_clean(cell) for cell in row)
            ]
            if page_section is not None:
                current_section = page_section

            for table_number, table in enumerate(tables, start=1):
                previous_data: list[str] | None = None
                for row_number, row in enumerate(table or [], start=1):
                    cells = [_clean(cell) for cell in row]
                    if not any(cells):
                        continue
                    if len(cells) != 6:
                        raise RuntimeError(f"Crotone unreviewed listed table width p{page_number} r{row_number}: {len(cells)}")
                    if _is_header(cells):
                        if page_section is not None:
                            current_section = page_section
                        continue
                    if current_section is None:
                        raise RuntimeError(f"Crotone listed observation before a section heading p{page_number} r{row_number}")
                    if not cells[0]:
                        if previous_data is None or any(cells[:3]) or not (cells[3] or cells[4] or cells[5]):
                            raise RuntimeError(f"Crotone unresolved blank-identity row p{page_number} r{row_number}: {cells!r}")
                        cells = previous_data[:3] + cells[3:]
                        carried_identity_rows += 1
                    listing_date = _parse_date(cells[3], allow_blank=True)
                    expiry_date, expiry_tail = _parse_expiry(cells[4])
                    sector_rows.append(
                        {
                            "page": page_number,
                            "table": table_number,
                            "row": row_number,
                            "section": current_section,
                            "name": cells[0],
                            "identifier_raw": cells[1],
                            "office": cells[2],
                            "listing_raw": cells[3],
                            "listing_date": listing_date,
                            "expiry_raw": cells[4],
                            "expiry_date": expiry_date,
                            "expiry_tail": expiry_tail,
                            "note": cells[5],
                            "status": _status(expiry_tail, cells[5]),
                        }
                    )
                    previous_data = cells

    if carried_identity_rows != 1:
        raise RuntimeError(f"Crotone listed structural-carry drift: {carried_identity_rows} != 1")
    if len(sector_rows) != _EXPECTED_LISTED_SECTOR_ROWS:
        raise RuntimeError(f"Crotone listed sector-row drift: {len(sector_rows)} != {_EXPECTED_LISTED_SECTOR_ROWS}")

    grouped: dict[tuple[str, ...], dict[str, Any]] = {}
    for row in sector_rows:
        key = (
            _normalise_text(row["name"]),
            _normalise_text(row["identifier_raw"]),
            _normalise_address(row["office"]),
            _date_key(row["listing_raw"], row["listing_date"]),
            _date_key(row["expiry_raw"], row["expiry_date"]),
            row["status"],
        )
        group = grouped.setdefault(key, {"row": row, "sections": [], "rows": []})
        if row["section"] in group["sections"]:
            raise RuntimeError(
                f"Crotone duplicate same-section observation after conservative normalisation: {row['name']!r}, section {row['section']}"
            )
        group["sections"].append(row["section"])
        group["rows"].append(row)

    if len(grouped) != _EXPECTED_LISTED_RECORDS:
        raise RuntimeError(f"Crotone listed grouping drift: {len(grouped)} != {_EXPECTED_LISTED_RECORDS}")

    records: list[dict[str, Any]] = []
    for group in grouped.values():
        row = group["row"]
        sections = sorted(group["sections"])
        rows = group["rows"]
        notes = _unique([item["note"] for item in rows if item["note"]])
        office_variants = _unique([item["office"] for item in rows])
        listing_variants = _unique([item["listing_raw"] for item in rows])
        expiry_variants = _unique([item["expiry_raw"] for item in rows])
        record = _record(
            cfg,
            len(records) + 1,
            name=row["name"],
            office=row["office"],
            identifier_raw=row["identifier_raw"],
            activities=[f"Sezione {section}" for section in sections],
            status=row["status"],
            outcome_raw=" · ".join(notes),
            listing_date=row["listing_date"],
            expiry_date=row["expiry_date"],
            primary_date_label="Data iscrizione",
            source_fields={
                "sections": [f"Sezione {section}" for section in sections],
                "registered_office_variants": office_variants,
                "listing_date_raw_variants": listing_variants,
                "expiry_date_raw_variants": expiry_variants,
                "in_aggiornamento": " · ".join(notes) if row["status"] == "renewal_update_in_progress" else "",
            },
        )
        record["identifiers"] = _strict_identifiers(row["identifier_raw"])
        records.append(record)

    status_counts = dict(Counter(record["source_status"] for record in records))
    if status_counts != _EXPECTED_LISTED_STATUS_COUNTS:
        raise RuntimeError(f"Crotone listed grouped-status drift: {status_counts!r}")

    return ParsedBatch(
        records=records,
        diagnostics={
            "parser": "crotone_listed",
            "parser_version": PARSER_VERSION,
            "source_pages": _LISTED_PAGES,
            "sector_rows": len(sector_rows),
            "carried_identity_rows": carried_identity_rows,
            "public_records": len(records),
            "status_counts": status_counts,
            "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
        },
    )


def parse_crotone_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(cfg, "crotone-applicants")
    logical: list[dict[str, Any]] = []
    continuation_fragments = 0

    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _APPLICANT_PAGES:
            raise RuntimeError(f"Crotone applicant page-count drift: {len(pdf.pages)} != {_APPLICANT_PAGES}")
        for page_number, page in enumerate(pdf.pages, start=1):
            page_rows: list[tuple[int, int, list[str]]] = []
            for table_number, table in enumerate(page.extract_tables() or [], start=1):
                for row_number, row in enumerate(table or [], start=1):
                    cells = [_clean(cell) for cell in row]
                    if not any(cells):
                        continue
                    if len(cells) != 6:
                        raise RuntimeError(f"Crotone unreviewed applicant table width p{page_number} r{row_number}: {len(cells)}")
                    if "codice fiscale" in cells[0].casefold() or cells[1].casefold() == "ragione sociale":
                        continue
                    page_rows.append((table_number, row_number, cells))

            for index, (table_number, row_number, cells) in enumerate(page_rows):
                application_date = _parse_date(cells[5], allow_blank=True)
                locator = f"p{page_number}:t{table_number}:r{row_number}"
                first_on_page = index == 0
                last_on_page = index == len(page_rows) - 1

                if application_date and cells[0] and cells[1]:
                    logical.append(
                        {
                            "identifier_raw": cells[0],
                            "name": cells[1],
                            "office": cells[2],
                            "secondary": cells[3],
                            "activities_raw": cells[4],
                            "application_raw": cells[5],
                            "application_date": application_date,
                            "locators": [locator],
                        }
                    )
                    continue

                if first_on_page and not cells[0] and logical:
                    previous = logical[-1]
                    if application_date and not previous["application_date"]:
                        pass
                    elif not application_date and previous["application_date"]:
                        pass
                    else:
                        raise RuntimeError(f"Crotone ambiguous page continuation at {locator}: {cells!r}")
                    for key, value in zip(("name", "office", "secondary", "activities_raw"), cells[1:5]):
                        if value:
                            previous[key] = _clean(f"{previous[key]} {value}")
                    if application_date:
                        previous["application_raw"] = cells[5]
                        previous["application_date"] = application_date
                    previous["locators"].append(locator)
                    continuation_fragments += 1
                    continue

                if not application_date and cells[0] and cells[1] and last_on_page:
                    logical.append(
                        {
                            "identifier_raw": cells[0],
                            "name": cells[1],
                            "office": cells[2],
                            "secondary": cells[3],
                            "activities_raw": cells[4],
                            "application_raw": "",
                            "application_date": "",
                            "locators": [locator],
                        }
                    )
                    continue

                raise RuntimeError(f"Crotone unreviewed applicant fragment at {locator}: {cells!r}")

    unresolved = [row for row in logical if not row["application_date"]]
    if unresolved:
        raise RuntimeError(f"Crotone unresolved applicant page splits: {unresolved!r}")
    if continuation_fragments != _EXPECTED_APPLICANT_CONTINUATIONS:
        raise RuntimeError(
            f"Crotone applicant continuation drift: {continuation_fragments} != {_EXPECTED_APPLICANT_CONTINUATIONS}"
        )
    if len(logical) != _EXPECTED_APPLICANT_RECORDS:
        raise RuntimeError(f"Crotone applicant row drift: {len(logical)} != {_EXPECTED_APPLICANT_RECORDS}")

    keys = {
        (
            row["identifier_raw"].casefold(),
            row["name"].casefold(),
            row["office"].casefold(),
            row["secondary"].casefold(),
            row["activities_raw"].casefold(),
            row["application_raw"].casefold(),
        )
        for row in logical
    }
    if len(keys) != len(logical):
        raise RuntimeError("Crotone duplicate reviewed applicant observation")

    records: list[dict[str, Any]] = []
    for row in logical:
        activities = [_clean(row["activities_raw"])] if _clean(row["activities_raw"]) else []
        record = _record(
            cfg,
            len(records) + 1,
            name=row["name"],
            office=row["office"],
            secondary=row["secondary"],
            identifier_raw=row["identifier_raw"],
            activities=activities,
            status="pending",
            outcome_raw="",
            application_date=row["application_date"],
            primary_date_label="Data presentazione istanza",
            source_fields={
                "application_date_raw_variants": [row["application_raw"]],
                "requested_activities_source": row["activities_raw"],
            },
        )
        record["identifiers"] = _strict_identifiers(row["identifier_raw"])
        records.append(record)

    status_counts = dict(Counter(record["source_status"] for record in records))
    if status_counts != _EXPECTED_APPLICANT_STATUS_COUNTS:
        raise RuntimeError(f"Crotone applicant status drift: {status_counts!r}")

    return ParsedBatch(
        records=records,
        diagnostics={
            "parser": "crotone_applicants",
            "parser_version": PARSER_VERSION,
            "source_pages": _APPLICANT_PAGES,
            "continuation_fragments": continuation_fragments,
            "public_records": len(records),
            "status_counts": status_counts,
            "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
        },
    )


PARSERS = {
    "crotone_listed": parse_crotone_listed,
    "crotone_applicants": parse_crotone_applicants,
}
