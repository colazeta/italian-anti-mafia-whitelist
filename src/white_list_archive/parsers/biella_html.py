from __future__ import annotations

import re
from collections import Counter
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _clean, _record

_PARSER_VERSION = "1"
_APPLICANT_TITLE = "ELENCO DELLE IMPRESE RICHIEDENTI L'ISCRIZIONE"
_LISTED_TITLE = "ELENCO DEI FORNITORI, PRESTATORI DI SERVIZI ED ESECUTORI DI LAVORI"
_APPLICANT_HEADER = (
    "ragione sociale",
    "sede legale",
    "sede secondaria con rappresentanza stabile in italia",
    "codice fiscale/partita iva",
    "attività per cui è richiesta l'iscrizione",
    "data di presentazione dell'istanza",
    "esito",
)
_LISTED_HEADER = (
    "ragione sociale",
    "sede legale",
    "sede secondaria con rappresentanza stabile in italia",
    "codice fiscale/partita iva",
    "data di iscrizione",
    "data scadenza iscrizione",
    "aggiornamento in corso",
)
_MONTHS = {
    "gen": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "mag": 5,
    "giu": 6,
    "lug": 7,
    "ago": 8,
    "set": 9,
    "sett": 9,
    "ott": 10,
    "nov": 11,
    "dic": 12,
}


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell_parts: list[str] | None = None
        self._cell_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        tag = tag.casefold()
        if tag == "table":
            if self._table is not None:
                raise ValueError("Nested tables are not supported in the Biella source")
            self._table = []
        elif tag == "tr" and self._table is not None:
            if self._row is not None:
                raise ValueError("Nested table rows are not supported in the Biella source")
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            if self._cell_parts is not None:
                self._cell_depth += 1
            else:
                self._cell_parts = []
                self._cell_depth = 0
        elif tag == "br" and self._cell_parts is not None:
            self._cell_parts.append(" ")

    def handle_data(self, data: str) -> None:
        if self._cell_parts is not None:
            self._cell_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if tag in {"td", "th"} and self._cell_parts is not None:
            if self._cell_depth:
                self._cell_depth -= 1
                return
            if self._row is None:
                raise ValueError("Cell closed outside a row")
            self._row.append(_clean("".join(self._cell_parts)))
            self._cell_parts = None
        elif tag == "tr" and self._row is not None:
            if self._cell_parts is not None:
                raise ValueError("Table row ended inside a cell")
            if self._table is None:
                raise ValueError("Table row closed outside a table")
            if any(self._row):
                self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            if self._row is not None or self._cell_parts is not None:
                raise ValueError("Table ended with an open row or cell")
            if self._table:
                self.tables.append(self._table)
            self._table = None


def _tables(path: Path) -> list[list[list[str]]]:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Biella HTML is not UTF-8") from exc
    parser = _TableParser()
    parser.feed(text)
    parser.close()
    if parser._table is not None or parser._row is not None or parser._cell_parts is not None:
        raise ValueError("Biella HTML ended with an incomplete table structure")
    return parser.tables


def _row_fold(row: list[str]) -> tuple[str, ...]:
    return tuple(_clean(value).casefold() for value in row)


def _find_applicant_table(tables: list[list[list[str]]]) -> list[list[str]]:
    candidates = [
        table
        for table in tables
        if _APPLICANT_TITLE.casefold() in " ".join(" ".join(row) for row in table[:5]).casefold()
        and any(_row_fold(row)[:7] == _APPLICANT_HEADER for row in table if len(row) >= 7)
    ]
    if len(candidates) != 1:
        raise ValueError(f"Expected exactly one Biella applicant table, found {len(candidates)}")
    return candidates[0]


def _find_listed_table(tables: list[list[list[str]]]) -> list[list[str]]:
    candidates = [
        table
        for table in tables
        if _LISTED_TITLE.casefold() in " ".join(" ".join(row) for row in table[:8]).casefold()
        and any(_row_fold(row)[:7] == _LISTED_HEADER for row in table if len(row) >= 7)
    ]
    if len(candidates) != 1:
        raise ValueError(f"Expected exactly one Biella listed table, found {len(candidates)}")
    return candidates[0]


def _source_identity(name: str, identifier: str) -> tuple[str, str]:
    identifier_key = re.sub(r"[^A-Za-z0-9]", "", _clean(identifier)).upper()
    return (_clean(name).casefold(), identifier_key)


def _year(value: str) -> int:
    year = int(value)
    return year + 2000 if year < 100 else year


def _slash_date_prefix(raw: str) -> str:
    raw = _clean(raw)
    if not raw:
        return ""
    match = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})(?:\b|\s|\()", raw)
    if not match:
        raise ValueError(f"Unsupported Biella applicant date: {raw!r}")
    day, month, year = map(int, match.groups())
    try:
        parsed = date(year, month, day)
    except ValueError as exc:
        raise ValueError(f"Invalid Biella applicant date: {raw!r}") from exc
    return parsed.isoformat()


def _listed_date(raw: str, *, allow_blank: bool = False) -> str:
    raw = _clean(raw)
    if not raw and allow_blank:
        return ""
    if not raw:
        raise ValueError("Missing required Biella listed date")

    slash = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{2}|\d{4})", raw)
    numeric_dash = re.fullmatch(r"(\d{1,2})-(\d{1,2})-(\d{2}|\d{4})", raw)
    month_dash = re.fullmatch(r"(\d{1,2})-([A-Za-z]+)-(\d{2}|\d{4})", raw)
    if slash:
        day = int(slash.group(1))
        month = int(slash.group(2))
        year = _year(slash.group(3))
    elif numeric_dash:
        day = int(numeric_dash.group(1))
        month = int(numeric_dash.group(2))
        year = _year(numeric_dash.group(3))
    elif month_dash:
        day = int(month_dash.group(1))
        month_name = month_dash.group(2).casefold()
        if month_name not in _MONTHS:
            raise ValueError(f"Unsupported Biella month abbreviation: {raw!r}")
        month = _MONTHS[month_name]
        year = _year(month_dash.group(3))
    else:
        raise ValueError(f"Unsupported Biella listed date: {raw!r}")

    try:
        parsed = date(year, month, day)
    except ValueError as exc:
        raise ValueError(f"Invalid Biella listed date: {raw!r}") from exc
    return parsed.isoformat()


def _applicant_status(raw: str) -> str:
    folded = _clean(raw).casefold()
    if not folded or folded == "in lavorazione":
        return "pending"
    if "aggiorn.to" in folded or "aggiornamento" in folded:
        return "renewal_update_in_progress"
    if folded in {"iscritto", "iscritta"}:
        return "listed"
    raise ValueError(f"Unsupported Biella applicant outcome: {raw!r}")


def _listed_status(raw: str) -> str:
    folded = _clean(raw).casefold()
    if not folded:
        return "listed"
    if folded in {"aggiornamento", "in aggiorn.to"}:
        return "renewal_update_in_progress"
    raise ValueError(f"Unsupported Biella listed update marker: {raw!r}")


def parse_biella_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    table = _find_applicant_table(_tables(path))
    rows: list[list[str]] = []
    for row in table:
        if len(row) != 8:
            continue
        folded = _row_fold(row)
        if folded[:7] == _APPLICANT_HEADER:
            continue
        if not row[0] and not row[3]:
            continue
        if not row[0] or not row[3]:
            raise ValueError(f"Incomplete Biella applicant identity row: {row!r}")
        rows.append(row)
    if not rows:
        raise ValueError("No Biella applicant observations found")

    records: list[dict[str, Any]] = []
    for row in rows:
        application_date = _slash_date_prefix(row[5])
        status = _applicant_status(row[6])
        activity = _clean(row[4])
        records.append(
            _record(
                cfg,
                len(records) + 1,
                name=row[0], office=row[1], secondary=row[2], identifier_raw=row[3],
                activities=[activity] if activity else [], status=status, outcome_raw=row[6],
                application_date=application_date, primary_date_label="Data presentazione istanza",
                source_fields={
                    "application_date_raw": _clean(row[5]),
                    "outcome_raw": _clean(row[6]),
                    "source_table": "applicants",
                },
            )
        )
    diagnostics = {
        "parser": "biella_html_applicants", "parser_version": _PARSER_VERSION,
        "sector_rows": len(rows), "public_records": len(records),
        "status_counts": dict(Counter(record["source_status"] for record in records)),
        "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
        "raw_identifier_only": sum(bool(record["identifier_field_raw"]) and not record["identifiers"] for record in records),
        "missing_application_dates": sum(not record["application_date"] for record in records),
        "unique_source_identities": len({_source_identity(row[0], row[3]) for row in rows}),
        "dropped_date_rows": 0,
    }
    return ParsedBatch(records, diagnostics)


def _listed_rows(table: list[list[str]]) -> list[tuple[str, str, list[str]]]:
    rows: list[tuple[str, str, list[str]]] = []
    current_section = ""
    current_activity = ""
    awaiting_activity = False
    section_count = 0
    for row in table:
        first = _clean(row[0]) if row else ""
        rest = [_clean(value) for value in row[1:]]
        if first.casefold().startswith("sezione ") and not any(rest):
            current_section = first
            current_activity = ""
            awaiting_activity = True
            section_count += 1
            continue
        if awaiting_activity and len(row) == 1 and first:
            current_activity = first
            awaiting_activity = False
            continue
        if len(row) == 7 and _row_fold(row)[:7] == _LISTED_HEADER:
            if not current_section or not current_activity:
                raise ValueError("Biella listed header encountered before section/activity context")
            continue
        if len(row) != 7:
            continue
        if not row[0] and not row[3]:
            continue
        if not current_section or not current_activity:
            raise ValueError(f"Biella listed company row lacks section context: {row!r}")
        if not row[0] or not row[3]:
            raise ValueError(f"Incomplete Biella listed identity row: {row!r}")
        rows.append((current_section, current_activity, row))
    if section_count != 10:
        raise ValueError(f"Expected ten Biella White List sections, found {section_count}")
    return rows


def parse_biella_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    table = _find_listed_table(_tables(path))
    sector_rows = _listed_rows(table)
    if not sector_rows:
        raise ValueError("No Biella listed observations found")

    grouped: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    for section, activity, row in sector_rows:
        listing_date = _listed_date(row[4])
        expiry_date = _listed_date(row[5], allow_blank=True)
        status = _listed_status(row[6])
        key = (*_source_identity(row[0], row[3]), listing_date, expiry_date, status)
        group = grouped.setdefault(key, {
            "row": row, "listing_date": listing_date, "expiry_date": expiry_date, "status": status,
            "sections": [], "activities": [], "offices": [], "secondary_offices": [],
            "identifier_raw_variants": [], "source_row_count": 0,
        })
        group["source_row_count"] += 1
        for field, value in (
            ("sections", section), ("activities", activity), ("offices", row[1]),
            ("secondary_offices", row[2]), ("identifier_raw_variants", row[3]),
        ):
            value = _clean(value)
            if value and value not in group[field]:
                group[field].append(value)

    records: list[dict[str, Any]] = []
    for group in grouped.values():
        row = group["row"]
        records.append(
            _record(
                cfg, len(records) + 1, name=row[0],
                office=group["offices"][0] if group["offices"] else row[1],
                secondary=group["secondary_offices"][0] if group["secondary_offices"] else row[2],
                identifier_raw=row[3], activities=group["activities"], status=group["status"], outcome_raw=row[6],
                listing_date=group["listing_date"], expiry_date=group["expiry_date"], primary_date_label="Data iscrizione",
                source_fields={
                    "sections": group["sections"], "registered_office_variants": group["offices"],
                    "secondary_office_variants": group["secondary_offices"],
                    "identifier_raw_variants": group["identifier_raw_variants"],
                    "listing_date_raw": _clean(row[4]), "expiry_date_raw": _clean(row[5]),
                    "update_marker_raw": _clean(row[6]), "source_sector_row_count": group["source_row_count"],
                    "source_table": "listed",
                },
            )
        )
    diagnostics = {
        "parser": "biella_html_listed", "parser_version": _PARSER_VERSION,
        "sector_rows": len(sector_rows), "public_records": len(records),
        "status_counts": dict(Counter(record["source_status"] for record in records)),
        "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
        "raw_identifier_only": sum(bool(record["identifier_field_raw"]) and not record["identifiers"] for record in records),
        "missing_expiry_dates": sum(not record["observed_expiry_date"] for record in records),
        "grouped_sector_repetitions": len(sector_rows) - len(records), "dropped_date_rows": 0,
    }
    return ParsedBatch(records, diagnostics)


PARSERS = {
    "biella_html_applicants": parse_biella_applicants,
    "biella_html_listed": parse_biella_listed,
}
