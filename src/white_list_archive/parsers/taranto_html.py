from __future__ import annotations

import re
from collections import Counter
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _clean, _record

PARSER_VERSION = "1"

_LISTED_HEADER = (
    "ragione sociale",
    "sede legale",
    "codice fiscale - partita iva",
    "data iscrizione",
    "data scadenza iscrizione",
    "sezioni",
    "note",
)
_APPLICANT_HEADER = (
    "ragione sociale",
    "sede legale",
    "codice fiscale/partita iva",
    "sezioni",
    "data di presentazione dell'istanza",
)
_ALLOWED_LISTED_NOTES = {
    "": "listed",
    "in fase di rinnovo": "renewal_update_in_progress",
    "in fase di aggiornamento": "renewal_update_in_progress",
}
_ROMAN_SECTIONS = frozenset({"I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"})


class _NestedTableParser(HTMLParser):
    """Collect each physical HTML table independently, including nested tables.

    The current Taranto pages contain layout tables around the substantive White
    List table.  A stack prevents outer layout markup from being conflated with
    the inner evidence table while preserving the inner rows byte-for-byte at the
    text-cell level.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._stack: list[dict[str, Any]] = []

    def _ctx(self) -> dict[str, Any] | None:
        return self._stack[-1] if self._stack else None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        tag = tag.casefold()
        if tag == "table":
            self._stack.append({"table": [], "row": None, "parts": None, "cell_depth": 0})
            return
        ctx = self._ctx()
        if ctx is None:
            return
        if tag == "tr":
            if ctx["row"] is not None:
                raise ValueError("Nested row inside one Taranto table context")
            ctx["row"] = []
        elif tag in {"td", "th"} and ctx["row"] is not None:
            if ctx["parts"] is None:
                ctx["parts"] = []
                ctx["cell_depth"] = 0
            else:
                ctx["cell_depth"] += 1
        elif tag == "br" and ctx["parts"] is not None:
            ctx["parts"].append(" ")

    def handle_data(self, data: str) -> None:
        ctx = self._ctx()
        if ctx is not None and ctx["parts"] is not None:
            ctx["parts"].append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        ctx = self._ctx()
        if ctx is None:
            return
        if tag in {"td", "th"} and ctx["parts"] is not None:
            if ctx["cell_depth"]:
                ctx["cell_depth"] -= 1
                return
            if ctx["row"] is None:
                raise ValueError("Taranto cell closed outside a row")
            ctx["row"].append(_clean("".join(ctx["parts"])))
            ctx["parts"] = None
        elif tag == "tr" and ctx["row"] is not None:
            if ctx["parts"] is not None:
                raise ValueError("Taranto row ended inside a cell")
            if any(ctx["row"]):
                ctx["table"].append(ctx["row"])
            ctx["row"] = None
        elif tag == "table":
            if ctx["row"] is not None or ctx["parts"] is not None:
                raise ValueError("Taranto table ended with an incomplete row or cell")
            table = ctx["table"]
            self._stack.pop()
            if table:
                self.tables.append(table)


def _tables(path: Path) -> list[list[list[str]]]:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Taranto HTML is not UTF-8") from exc
    parser = _NestedTableParser()
    parser.feed(text)
    parser.close()
    if parser._stack:
        raise ValueError("Taranto HTML ended with an open table context")
    return parser.tables


def _fold(row: list[str]) -> tuple[str, ...]:
    return tuple(_clean(value).casefold() for value in row)


def _find_rows(tables: list[list[list[str]]], *, applicant: bool) -> list[list[str]]:
    header = _APPLICANT_HEADER if applicant else _LISTED_HEADER
    matches: list[list[list[str]]] = []
    for table in tables:
        for index, row in enumerate(table):
            if _fold(row) == header:
                matches.append(table[index + 1 :])
    if len(matches) != 1:
        label = "applicant" if applicant else "listed"
        raise ValueError(f"Expected exactly one Taranto {label} evidence table, found {len(matches)}")
    width = len(header)
    malformed = [row for row in matches[0] if any(row) and len(row) != width]
    if malformed:
        raise ValueError(f"Taranto table row-width drift: {malformed[:3]!r}")
    rows = [row for row in matches[0] if any(row)]
    if not rows:
        raise ValueError("No Taranto source observations found")
    for row in rows:
        if not row[0]:
            raise ValueError(f"Taranto observation lacks company name: {row!r}")
    return rows


def _date(raw: str) -> str:
    raw = _clean(raw)
    match = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", raw)
    if match is None:
        return ""
    try:
        return date(int(match.group(3)), int(match.group(2)), int(match.group(1))).isoformat()
    except ValueError:
        return ""


def _sections(raw: str) -> list[str]:
    raw = _clean(raw)
    if not raw:
        return []
    tokens = [token.upper() for token in re.findall(r"\b[IVX]+\b", raw, flags=re.I)]
    if not tokens or any(token not in _ROMAN_SECTIONS for token in tokens):
        raise ValueError(f"Unsupported Taranto statutory-section value: {raw!r}")
    return [f"Sezione {token}" for token in tokens]


def parse_taranto_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    rows = _find_rows(_tables(path), applicant=False)
    records: list[dict[str, Any]] = []
    malformed_date_rows = 0
    for row in rows:
        note = _clean(row[6])
        folded_note = note.casefold()
        if folded_note not in _ALLOWED_LISTED_NOTES:
            raise ValueError(f"Unapproved Taranto listed note/status: {note!r}")
        listing_date = _date(row[3])
        expiry_date = _date(row[4])
        malformed: list[str] = []
        if row[3] and not listing_date:
            malformed.append(f"listing={row[3]}")
        if row[4] and not expiry_date:
            malformed.append(f"expiry={row[4]}")
        malformed_date_rows += bool(malformed)
        sections = _sections(row[5])
        records.append(
            _record(
                cfg,
                len(records) + 1,
                name=row[0],
                office=row[1],
                identifier_raw=row[2],
                activities=sections,
                status=_ALLOWED_LISTED_NOTES[folded_note],
                outcome_raw=note,
                listing_date=listing_date,
                expiry_date=expiry_date,
                primary_date_label="Data iscrizione",
                source_fields={
                    "sections": sections,
                    "notes": [note] if note else [],
                    "listing_date_raw_variants": [row[3]] if row[3] else [],
                    "expiry_date_raw_variants": [row[4]] if row[4] else [],
                    "malformed_date_pairs": malformed,
                },
            )
        )
    diagnostics = {
        "parser": "taranto_html_listed",
        "parser_version": PARSER_VERSION,
        "source_rows": len(rows),
        "public_records": len(records),
        "status_counts": dict(Counter(record["source_status"] for record in records)),
        "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
        "raw_identifier_only": sum(bool(record["identifier_field_raw"]) and not record["identifiers"] for record in records),
        "blank_identifier_rows": sum(not bool(record["identifier_field_raw"]) for record in records),
        "malformed_date_rows": malformed_date_rows,
    }
    return ParsedBatch(records, diagnostics)


def parse_taranto_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    rows = _find_rows(_tables(path), applicant=True)
    records: list[dict[str, Any]] = []
    malformed_date_rows = 0
    for row in rows:
        application_date = _date(row[4])
        malformed = bool(row[4] and not application_date)
        malformed_date_rows += malformed
        sections = _sections(row[3])
        records.append(
            _record(
                cfg,
                len(records) + 1,
                name=row[0],
                office=row[1],
                identifier_raw=row[2],
                activities=sections,
                status="pending",
                outcome_raw="",
                application_date=application_date,
                primary_date_label="Data presentazione istanza",
                source_fields={
                    "sections": sections,
                    "application_date_raw_variants": [row[4]] if row[4] else [],
                    "malformed_application_date_raw": row[4] if malformed else "",
                },
            )
        )
    diagnostics = {
        "parser": "taranto_html_applicants",
        "parser_version": PARSER_VERSION,
        "source_rows": len(rows),
        "public_records": len(records),
        "status_counts": dict(Counter(record["source_status"] for record in records)),
        "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
        "raw_identifier_only": sum(bool(record["identifier_field_raw"]) and not record["identifiers"] for record in records),
        "blank_identifier_rows": sum(not bool(record["identifier_field_raw"]) for record in records),
        "malformed_date_rows": malformed_date_rows,
    }
    return ParsedBatch(records, diagnostics)


PARSERS = {
    "taranto_html_listed": parse_taranto_listed,
    "taranto_html_applicants": parse_taranto_applicants,
}
