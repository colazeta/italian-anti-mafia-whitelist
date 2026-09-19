from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import pdfplumber

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _record

_LISTED_PAGE_COUNT = 41
_APPLICANT_PAGE_COUNT = 44
_PAGE_GEOMETRY = (841.92, 595.32)
_LISTED_TABLE_COUNTS = [0,1,1,1,1,1,2,1,1,1,1,1,1,1,1,1,1,2,1,2,1,1,1,1,1,1,1,2,1,1,1,1,2,1,1,1,1,1,1,1,0]
_APPLICANT_ROW_COUNTS = [3,9,4,3,2,8,8,6,7,6,7,2,5,7,1,4,1,8,7,4,6,4,6,5,11,5,4,5,6,4,6,7,3,1,4,8,3,5,3,4,6,3,7,4]
_EXPECTED_SECTIONS = tuple(f"Sezione {value}" for value in ("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"))
_ALLOWED_UPDATE_MARKERS = {"", "In aggiornamento per rinnovo", "In aggiornamento", "*", "*-"}
_ALLOWED_APPLICANT_OUTCOMES = {"In istruttoria", "In Istruttoria"}
_ID_RE = re.compile(r"^(?:\d{11}|[A-Za-z0-9]{16})$")
_DATE_RE = re.compile(r"^(\d{1,2})\s*/\s*(\d{1,2})\s*/\s*(\d{4})$")
_ROMAN = {value: index for index, value in enumerate(("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"), 1)}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split())


def _ordered_unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def _strict_date(value: str) -> str:
    """Parse source dates without repairing digits or truncated years."""
    value = _clean(value)
    match = _DATE_RE.fullmatch(value)
    if match is None:
        return ""
    day, month, year = map(int, match.groups())
    try:
        parsed = datetime(year, month, day)
    except ValueError:
        return ""
    return parsed.strftime("%d/%m/%Y")


def _section_headings(page: Any) -> list[tuple[float, str]]:
    words = page.extract_words() or []
    headings: list[tuple[float, str]] = []
    for index, word in enumerate(words[:-1]):
        if _clean(word.get("text")).casefold() != "sezione":
            continue
        roman = re.sub(r"[^IVX]", "", _clean(words[index + 1].get("text")).upper())
        if roman in _ROMAN:
            headings.append((float(word.get("top", 0.0)), f"Sezione {roman}"))
    # De-duplicate line-token repeats while preserving geometric order.
    unique: list[tuple[float, str]] = []
    for top, section in sorted(headings):
        if not unique or section != unique[-1][1] or abs(top - unique[-1][0]) > 2:
            unique.append((top, section))
    return unique


def _section_for_table(current: str, headings: list[tuple[float, str]], table_top: float) -> str:
    section = current
    for top, candidate in headings:
        if top <= table_top + 1:
            section = candidate
        else:
            break
    return section


def _normalise_listed_row(raw: list[Any]) -> list[str]:
    row = [_clean(value) for value in raw]
    if len(row) == 6:
        row.append("")
    if len(row) != 7:
        raise RuntimeError(f"Trapani listed table-width drift: {len(row)} columns")
    return row


def _is_header(row: list[str]) -> bool:
    joined = " ".join(row).casefold()
    return "ragione sociale" in joined and "codice fiscale" in joined


def _group_status(markers: list[str]) -> str:
    marker_set = set(markers)
    unexpected = marker_set - _ALLOWED_UPDATE_MARKERS
    if unexpected:
        raise RuntimeError(f"Trapani unapproved update marker(s): {sorted(unexpected)!r}")
    nonblank = [marker for marker in markers if marker]
    if nonblank and len(nonblank) != len(markers):
        raise RuntimeError("Trapani listed group mixes blank and non-blank update evidence")
    return "renewal_update_in_progress" if nonblank else "listed"


def _activities(raw: str) -> list[str]:
    value = _clean(raw)
    if not value:
        return []
    if value.startswith("-"):
        parts = [_clean(part) for part in re.split(r"\s*-\s*", value) if _clean(part)]
        return parts
    return [value]


def parse_trapani_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    memberships: list[dict[str, Any]] = []
    seen_sections: list[str] = []
    continuation_rows: list[list[str]] = []
    wrapped_renewal_rows = 0
    full_text: list[str] = []
    current_section = ""
    table_counts: list[int] = []

    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _LISTED_PAGE_COUNT:
            raise RuntimeError(f"Trapani listed page-count drift: {len(pdf.pages)}")
        for page_number, page in enumerate(pdf.pages, 1):
            geometry = (round(float(page.width), 2), round(float(page.height), 2))
            if geometry != _PAGE_GEOMETRY:
                raise RuntimeError(f"Trapani listed page-geometry drift on page {page_number}: {geometry}")
            full_text.append(page.extract_text() or "")
            headings = _section_headings(page)
            tables = sorted(page.find_tables(), key=lambda table: float(table.bbox[1]))
            table_counts.append(len(tables))
            for table_number, table in enumerate(tables, 1):
                section = _section_for_table(current_section, headings, float(table.bbox[1]))
                extracted = table.extract() or []
                for row_number, raw in enumerate(extracted, 1):
                    row = _normalise_listed_row(raw)
                    if not any(row) or _is_header(row):
                        continue
                    # One company name and its renewal marker are wrapped across the
                    # page 14/15 boundary in the pinned source. Bind that evidence to
                    # the immediately preceding membership only under the exact,
                    # source-observed shape; any drift still fails closed below.
                    if row == ["SILVESTRO", "", "", "", "", "", "per rinnovo"]:
                        if (page_number, table_number, row_number) != (15, 1, 1):
                            raise RuntimeError(
                                f"Trapani wrapped renewal row moved unexpectedly: page={page_number}, table={table_number}, row={row_number}"
                            )
                        if not memberships:
                            raise RuntimeError("Trapani wrapped renewal row has no preceding membership")
                        previous = memberships[-1]
                        expected_previous = {
                            "page": 14,
                            "name": "IMPRESA EDILE DI MANGANO",
                            "identifier": "02249310810",
                            "update_raw": "In aggiornamento",
                        }
                        observed_previous = {key: previous[key] for key in expected_previous}
                        if observed_previous != expected_previous:
                            raise RuntimeError(
                                f"Trapani wrapped renewal predecessor drift: {observed_previous!r}"
                            )
                        previous["name"] = "IMPRESA EDILE DI MANGANO SILVESTRO"
                        previous["update_raw"] = "In aggiornamento per rinnovo"
                        wrapped_renewal_rows += 1
                        continue
                    if not row[0] and not row[3]:
                        if any(row):
                            continuation_rows.append(row)
                        continue
                    if not row[0] or not _ID_RE.fullmatch(row[3]):
                        raise RuntimeError(
                            f"Trapani listed unexpected non-data row at page {page_number}, table {table_number}, row {row_number}: {row!r}"
                        )
                    if not section:
                        raise RuntimeError(f"Trapani listed row lacks section at page {page_number}")
                    if section not in seen_sections:
                        seen_sections.append(section)
                    memberships.append(
                        {
                            "source_row": len(memberships) + 1,
                            "page": page_number,
                            "section": section,
                            "name": row[0],
                            "office": row[1],
                            "secondary": row[2],
                            "identifier": row[3].upper(),
                            "listing_raw": row[4],
                            "expiry_raw": row[5],
                            "update_raw": row[6],
                        }
                    )
            if headings:
                current_section = headings[-1][1]

    if table_counts != _LISTED_TABLE_COUNTS:
        raise RuntimeError(f"Trapani listed table-count drift: {table_counts!r}")
    if seen_sections != list(_EXPECTED_SECTIONS):
        raise RuntimeError(f"Trapani listed section drift: {seen_sections!r}")
    if len(memberships) != 658:
        raise RuntimeError(f"Trapani listed sector-row drift: {len(memberships)}")
    if wrapped_renewal_rows != 1:
        raise RuntimeError(f"Trapani wrapped-renewal row drift: {wrapped_renewal_rows}")
    if len(continuation_rows) != 1 or continuation_rows[0] != ["", "", "", "", "", "", "per rinnovo"]:
        raise RuntimeError(f"Trapani listed continuation-row drift: {continuation_rows!r}")
    if "presentato istanza di permanenza" not in _clean(" ".join(full_text)).casefold():
        raise RuntimeError("Trapani listed permanence-request footnote disappeared")

    grouped: dict[str, list[dict[str, Any]]] = {}
    for membership in memberships:
        grouped.setdefault(membership["identifier"], []).append(membership)
    if len(grouped) != 333:
        raise RuntimeError(f"Trapani listed grouped-identifier drift: {len(grouped)}")

    records: list[dict[str, Any]] = []
    for identifier, rows in grouped.items():
        name_variants = _ordered_unique([row["name"] for row in rows])
        if len(name_variants) != 1:
            raise RuntimeError(f"Trapani listed name drift within identifier {identifier}: {name_variants!r}")
        office_variants = _ordered_unique([row["office"] for row in rows if row["office"]])
        secondary_variants = _ordered_unique([row["secondary"] for row in rows if row["secondary"]])
        listing_raw_variants = _ordered_unique([row["listing_raw"] for row in rows if row["listing_raw"]])
        expiry_raw_variants = _ordered_unique([row["expiry_raw"] for row in rows if row["expiry_raw"]])
        valid_listing_dates = _ordered_unique([value for raw in listing_raw_variants if (value := _strict_date(raw))])
        valid_expiry_dates = _ordered_unique([value for raw in expiry_raw_variants if (value := _strict_date(raw))])
        if len(valid_listing_dates) != 1 or len(valid_expiry_dates) != 1:
            raise RuntimeError(
                f"Trapani listed date evidence drift for {identifier}: listing={listing_raw_variants!r}, expiry={expiry_raw_variants!r}"
            )
        markers = [row["update_raw"] for row in rows]
        status = _group_status(markers)
        marker_variants = _ordered_unique([marker for marker in markers if marker])
        sections = _ordered_unique([row["section"] for row in rows])
        records.append(
            _record(
                cfg,
                len(records) + 1,
                name=name_variants[0],
                office=office_variants[0] if office_variants else "",
                secondary=secondary_variants[0] if secondary_variants else "",
                identifier_raw=identifier,
                activities=sections,
                status=status,
                listing_date=valid_listing_dates[0],
                expiry_date=valid_expiry_dates[0],
                primary_date_label="Data iscrizione",
                source_fields={
                    "sections": sections,
                    "registered_office_variants": office_variants,
                    "secondary_office_variants": secondary_variants,
                    "listing_date_raw_variants": listing_raw_variants,
                    "expiry_date_raw_variants": expiry_raw_variants,
                    "in_aggiornamento": " · ".join(marker_variants),
                    "notes": ["* = ditta che ha già presentato istanza di permanenza"] if any("*" in marker for marker in marker_variants) else [],
                },
            )
        )

    status_counts = dict(Counter(record["source_status"] for record in records))
    if status_counts != {"listed": 177, "renewal_update_in_progress": 156}:
        raise RuntimeError(f"Trapani listed status-boundary drift: {status_counts!r}")
    diagnostics = {
        "parser": "trapani_listed",
        "sector_rows": len(memberships),
        "public_records": len(records),
        "status_counts": status_counts,
        "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
        "source_sections": seen_sections,
        "continuation_rows": len(continuation_rows),
        "wrapped_renewal_rows": wrapped_renewal_rows,
    }
    return ParsedBatch(records=records, diagnostics=diagnostics)


def parse_trapani_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    rows: list[list[str]] = []
    per_page: list[int] = []
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _APPLICANT_PAGE_COUNT:
            raise RuntimeError(f"Trapani applicant page-count drift: {len(pdf.pages)}")
        for page_number, page in enumerate(pdf.pages, 1):
            geometry = (round(float(page.width), 2), round(float(page.height), 2))
            if geometry != _PAGE_GEOMETRY:
                raise RuntimeError(f"Trapani applicant page-geometry drift on page {page_number}: {geometry}")
            tables = page.find_tables()
            if len(tables) != 1:
                raise RuntimeError(f"Trapani applicant table-count drift on page {page_number}: {len(tables)}")
            page_rows: list[list[str]] = []
            for raw in tables[0].extract() or []:
                row = [_clean(value) for value in raw]
                if not any(row) or _is_header(row):
                    continue
                if len(row) != 7 or not row[0] or not _ID_RE.fullmatch(row[3]):
                    raise RuntimeError(f"Trapani applicant row-shape drift on page {page_number}: {row!r}")
                if row[6] not in _ALLOWED_APPLICANT_OUTCOMES:
                    raise RuntimeError(f"Trapani applicant outcome drift on page {page_number}: {row[6]!r}")
                if not _strict_date(row[5]):
                    raise RuntimeError(f"Trapani applicant application-date drift on page {page_number}: {row[5]!r}")
                page_rows.append(row)
            per_page.append(len(page_rows))
            rows.extend(page_rows)
    if per_page != _APPLICANT_ROW_COUNTS:
        raise RuntimeError(f"Trapani applicant per-page row drift: {per_page!r}")
    if len(rows) != 222 or len({row[3].upper() for row in rows}) != 222:
        raise RuntimeError("Trapani applicant identifier/cardinality drift")

    records: list[dict[str, Any]] = []
    for row in rows:
        records.append(
            _record(
                cfg,
                len(records) + 1,
                name=row[0],
                office=row[1],
                secondary=row[2],
                identifier_raw=row[3].upper(),
                activities=_activities(row[4]),
                status="pending",
                outcome_raw=row[6],
                application_date=_strict_date(row[5]),
                primary_date_label="Data presentazione istanza",
                source_fields={
                    "requested_activities_source": row[4],
                    "application_date_raw_variants": [row[5]],
                },
            )
        )
    diagnostics = {
        "parser": "trapani_applicants",
        "sector_rows": len(rows),
        "public_records": len(records),
        "status_counts": {"pending": len(records)},
        "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
        "outcome_counts": dict(Counter(record["outcome_raw"] for record in records)),
    }
    return ParsedBatch(records=records, diagnostics=diagnostics)


PARSERS = {
    "trapani_listed": parse_trapani_listed,
    "trapani_applicants": parse_trapani_applicants,
}
