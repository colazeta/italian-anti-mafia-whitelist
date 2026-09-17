from __future__ import annotations

import re
from collections import Counter
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _clean, _record

PARSER_VERSION = "1"
_LISTED_TITLE = (
    "ELENCO DEI FORNITORI, PRESTATORI DI SERVIZI ED ESECUTORI DI LAVORI "
    "NON SOGGETTI A TENTATIVO DI INFILTRAZIONE MAFIOSA"
)
_APPLICANT_TITLE = "ELENCO DELLE IMPRESE RICHIEDENTI L'ISCRIZIONE"
_LISTED_HEADER = (
    "ragione sociale",
    "sede legale",
    "c.f./p.i.",
    "data iscrizione",
    "scadenza iscrizione",
    "settori di attività",
    "note",
    "mese di presentazione rinnovo",
)
_APPLICANT_HEADER = (
    "ragione sociale",
    "sede legale",
    "c.f./p.i.",
    "note",
    "",
    "settori di attività",
    "",
    "mese di presentazione della domanda",
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
    "ott": 10,
    "nov": 11,
    "dic": 12,
}
_RENEWAL_MARKER = "fase di rinnovo"


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
                raise ValueError("Nested tables are not supported in the Como source")
            self._table = []
        elif tag == "tr" and self._table is not None:
            if self._row is not None:
                raise ValueError("Nested table rows are not supported in the Como source")
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
                raise ValueError("Cell closed outside a Como table row")
            self._row.append(_clean("".join(self._cell_parts)))
            self._cell_parts = None
        elif tag == "tr" and self._row is not None:
            if self._cell_parts is not None:
                raise ValueError("Como table row ended inside a cell")
            if self._table is None:
                raise ValueError("Como table row closed outside a table")
            if any(self._row):
                self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            if self._row is not None or self._cell_parts is not None:
                raise ValueError("Como HTML table ended with an incomplete row or cell")
            if self._table:
                self.tables.append(self._table)
            self._table = None


def _tables(path: Path) -> list[list[list[str]]]:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Como HTML is not UTF-8") from exc
    parser = _TableParser()
    parser.feed(text)
    parser.close()
    if parser._table is not None or parser._row is not None or parser._cell_parts is not None:
        raise ValueError("Como HTML ended with an incomplete table structure")
    return parser.tables


def _fold(row: list[str]) -> tuple[str, ...]:
    return tuple(_clean(value).casefold() for value in row)


def _find_table(tables: list[list[list[str]]], *, applicant: bool) -> list[list[str]]:
    title = _APPLICANT_TITLE if applicant else _LISTED_TITLE
    header = _APPLICANT_HEADER if applicant else _LISTED_HEADER
    candidates = []
    for table in tables:
        text = " ".join(" ".join(row) for row in table[:10]).casefold()
        if title.casefold() not in text:
            continue
        if any(_fold(row) == header for row in table if len(row) == 8):
            candidates.append(table)
    if len(candidates) != 1:
        label = "applicant" if applicant else "listed"
        raise ValueError(f"Expected exactly one Como {label} table, found {len(candidates)}")
    return candidates[0]


def _declared_count(table: list[list[str]], label: str) -> int:
    matches = []
    folded_label = label.casefold()
    for row in table:
        if len(row) == 8 and _clean(row[0]).casefold() == folded_label:
            raw = _clean(row[1])
            if not raw.isdigit():
                raise ValueError(f"Como declared count is not numeric: {raw!r}")
            matches.append(int(raw))
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one Como declared-count row for {label!r}, found {len(matches)}")
    return matches[0]


def _source_date(raw: str) -> str:
    """Normalise only explicit valid Como dates; retain malformed source values elsewhere."""
    raw = _clean(raw)
    if not raw:
        return ""
    slash = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", raw)
    month_name = re.fullmatch(r"(\d{1,2})-([A-Za-z]+)-(\d{4})", raw)
    if slash:
        day = int(slash.group(1))
        month = int(slash.group(2))
        year = int(slash.group(3))
    elif month_name:
        day = int(month_name.group(1))
        month_token = month_name.group(2).casefold()
        if month_token not in _MONTHS:
            return ""
        month = _MONTHS[month_token]
        year = int(month_name.group(3))
    else:
        return ""
    try:
        parsed = date(year, month, day)
    except ValueError:
        return ""
    return parsed.isoformat()


def _sections(raw: str) -> list[str]:
    raw = _clean(raw)
    if not raw:
        return []
    sections = re.findall(r"Sez\.\s*([IVX]+)", raw, flags=re.I)
    if not sections:
        return [raw]
    return [f"Sez. {section.upper()}" for section in sections]


def _listed_rows(table: list[list[str]]) -> list[list[str]]:
    rows = []
    for row in table:
        if len(row) != 8:
            continue
        folded = _fold(row)
        if folded == _LISTED_HEADER or folded[0] == "numero aziende iscritte:":
            continue
        if not row[0] and not row[2]:
            continue
        if not row[0]:
            raise ValueError(f"Como listed row lacks company name: {row!r}")
        rows.append(row)
    if not rows:
        raise ValueError("No Como listed observations found")
    return rows


def _applicant_rows(table: list[list[str]]) -> list[list[str]]:
    rows = []
    for row in table:
        if len(row) != 8:
            continue
        folded = _fold(row)
        if folded == _APPLICANT_HEADER or folded[0] == "numero aziende in fase iscrizione:":
            continue
        if not row[0] and not row[2]:
            continue
        if not row[0] or not row[2]:
            raise ValueError(f"Incomplete Como applicant identity row: {row!r}")
        rows.append(row)
    if not rows:
        raise ValueError("No Como applicant observations found")
    return rows


def parse_como_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    table = _find_table(_tables(path), applicant=False)
    rows = _listed_rows(table)
    declared = _declared_count(table, "NUMERO AZIENDE ISCRITTE:")
    records: list[dict[str, Any]] = []
    malformed_date_rows = 0
    for row in rows:
        listing_date = _source_date(row[3])
        expiry_date = _source_date(row[4])
        malformed: list[str] = []
        if row[3] and not listing_date:
            malformed.append(f"listing={row[3]}")
        if row[4] and not expiry_date:
            malformed.append(f"expiry={row[4]}")
        malformed_date_rows += bool(malformed)
        note = _clean(row[6])
        renewal_month = _clean(row[7])
        status = "renewal_update_in_progress" if _RENEWAL_MARKER in note.casefold() else "listed"
        notes = [note] if note else []
        if renewal_month:
            notes.append(f"Mese di presentazione rinnovo: {renewal_month}")
        records.append(
            _record(
                cfg,
                len(records) + 1,
                name=row[0],
                office=row[1],
                identifier_raw=row[2],
                activities=_sections(row[5]),
                status=status,
                outcome_raw=note,
                listing_date=listing_date,
                expiry_date=expiry_date,
                primary_date_label="Data iscrizione",
                source_fields={
                    "sections": _sections(row[5]),
                    "notes": notes,
                    "listing_date_raw_variants": [row[3]] if row[3] else [],
                    "expiry_date_raw_variants": [row[4]] if row[4] else [],
                    "malformed_date_pairs": malformed,
                },
            )
        )
    diagnostics = {
        "parser": "como_html_listed",
        "parser_version": PARSER_VERSION,
        "source_rows": len(rows),
        "public_records": len(records),
        "declared_count": declared,
        "declared_count_delta": len(rows) - declared,
        "status_counts": dict(Counter(record["source_status"] for record in records)),
        "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
        "raw_identifier_only": sum(bool(record["identifier_field_raw"]) and not record["identifiers"] for record in records),
        "blank_identifier_rows": sum(not record["identifier_field_raw"] for record in records),
        "malformed_date_rows": malformed_date_rows,
    }
    return ParsedBatch(records, diagnostics)


def parse_como_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    table = _find_table(_tables(path), applicant=True)
    rows = _applicant_rows(table)
    declared = _declared_count(table, "NUMERO AZIENDE IN FASE ISCRIZIONE:")
    records: list[dict[str, Any]] = []
    for row in rows:
        month_raw = _clean(row[7])
        if not re.fullmatch(r"[A-Za-z]{3}-\d{2}", month_raw):
            raise ValueError(f"Unsupported Como applicant month: {month_raw!r}")
        records.append(
            _record(
                cfg,
                len(records) + 1,
                name=row[0],
                office=row[1],
                identifier_raw=row[2],
                activities=_sections(row[5]),
                status="pending",
                outcome_raw=row[3],
                primary_date_label="",
                source_fields={
                    "sections": _sections(row[5]),
                    "notes": [row[3]] if row[3] else [],
                    "application_date_raw": month_raw,
                },
            )
        )
    diagnostics = {
        "parser": "como_html_applicants",
        "parser_version": PARSER_VERSION,
        "source_rows": len(rows),
        "public_records": len(records),
        "declared_count": declared,
        "declared_count_delta": len(rows) - declared,
        "status_counts": dict(Counter(record["source_status"] for record in records)),
        "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
        "raw_identifier_only": sum(bool(record["identifier_field_raw"]) and not record["identifiers"] for record in records),
    }
    return ParsedBatch(records, diagnostics)


PARSERS = {
    "como_html_listed": parse_como_listed,
    "como_html_applicants": parse_como_applicants,
}
