from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import Counter
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _clean, _record

PARSER_VERSION = "2"
PARSER_NAME = "milano_combined"

_REFERENCE_DATE = "2026-09-17"
_SOURCE_KEY = "milano-combined"
_EXPECTED_TABLES = 10
_EXPECTED_SECTOR_ROWS = 4213
_EXPECTED_RECORDS = 2612
_EXPECTED_STATUS_COUNTS = {
    "listed": 933,
    "renewal_update_in_progress": 517,
    "pending": 1162,
}
_EXPECTED_IDENTIFIER_COVERAGE = 2612
_EXPECTED_NONBLANK_NOTES = 1

_EXPECTED_SECTION_PREFIXES = (
    "Sezione 1 ESTRAZIONE, FORNITURA E TRASPORTO DI TERRA E MATERIALI INERTI",
    "Sezione 2 CONFENZIONAMENTO, FORNITURA E TRASPORTO CALCESTRUZZO E DI BITUME",
    "Sezione 3 NOLI A FREDDO DI MACCHINARI",
    "Sezione 4 FORNITURA DI FERRO LAVORATO",
    "Sezione 5 NOLI A CALDO",
    "Sezione 6 AUTOTRASPORTI PER CONTO TERZI",
    "Sezione 7 GUARDIANIA AI CANTIERI",
    "Sezione 8 SERVIZI FUNERARI E CIMITERIALI",
    "Sezione 9 RISTORAZIONE, GESTIONE DELLE MENSE E CATERING",
    "Sezione 10 SERVIZI AMBIENTALI, COMPRESE LE ATTIVITA’ DI RACCOLTA, DI TRASPORTO NAZIONALE E TRANSFRONTALIERO, ANCHE PER CONTO DI TERZI, DI TRATTAMENTO E DI SMALTIMENTO DEI RIFIUTI, NONCHE’ LE ATTIVITA’ DI RISANAMENTO E DI BONIFICA E GLI ALTRI SERVIZI CONNESSI ALLA GESTIONE DEI RIFIUTI",
)
_HEADER = (
    "RAGIONE SOCIALE",
    "SEDE LEGALE",
    "PARTITA IVA",
    "DATA DI ISCRIZIONE",
    "DATA SCADENZA ISCRIZIONE",
    "NOTE",
)
_REQUEST = re.compile(r"^RICHIESTA\s+ISCRIZIONE\s*\((\d{2}/\d{2}/\d{4})\)$", re.I)
_UPDATE = re.compile(r"^IN\s+AGGIORNAMENTO$", re.I)
_DMY = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")
_STRICT_IDENTIFIER = re.compile(r"^(?:\d{11}|[A-Za-z0-9]{16})$", re.I)
_SHA256 = re.compile(r"^[0-9a-f]{64}$", re.I)


class _TableParser(HTMLParser):
    """Small HTML 4 table reader that preserves source colspan geometry."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self._colspan = 1

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        if tag == "table":
            if self._table is not None:
                raise RuntimeError("Milano source contains nested tables")
            self._table = []
            self.tables.append(self._table)
        elif tag == "tr" and self._table is not None:
            if self._row is not None:
                raise RuntimeError("Milano source contains nested rows")
            self._row = []
            self._table.append(self._row)
        elif tag in {"td", "th"} and self._row is not None:
            if self._cell is not None:
                raise RuntimeError("Milano source contains nested cells")
            self._cell = []
            raw_colspan = attr.get("colspan") or "1"
            if not raw_colspan.isdigit() or int(raw_colspan) < 1:
                raise RuntimeError(f"Milano unsupported colspan: {raw_colspan!r}")
            self._colspan = int(raw_colspan)
        elif tag == "br" and self._cell is not None:
            self._cell.append(" ")

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._cell is not None and self._row is not None:
            value = _clean("".join(self._cell))
            self._row.extend([value] + [""] * (self._colspan - 1))
            self._cell = None
            self._colspan = 1
        elif tag == "tr":
            self._row = None
        elif tag == "table":
            self._table = None


def _source_date(raw: str) -> str:
    match = _DMY.fullmatch(_clean(raw))
    if not match:
        return ""
    day, month, year = map(int, match.groups())
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return ""


def _normalise_text(value: str) -> str:
    return _clean(unicodedata.normalize("NFKC", value)).casefold()


def _normalise_address(value: str) -> str:
    text = _normalise_text(value).replace("–", "-").replace("—", "-").replace("−", "-")
    text = re.sub(r"\s*([,;:/.-])\s*", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def _decode(path: Path) -> str:
    raw = path.read_bytes()
    # The source declares ISO-8859-1 but uses Windows-1252 punctuation bytes.
    # HTML browsers treat that legacy label as Windows-1252; doing the same
    # preserves the source characters rather than guessing replacements.
    try:
        return raw.decode("cp1252")
    except UnicodeDecodeError as exc:
        raise RuntimeError("Milano source is not valid Windows-1252/HTML legacy text") from exc


def _validate_cfg(path: Path, cfg: dict[str, Any]) -> None:
    expected = {
        "source_key": _SOURCE_KEY,
        "authority_key": "milano",
        "population_scope": "listed_and_applicant",
        "reference_date": _REFERENCE_DATE,
    }
    for key, value in expected.items():
        if cfg.get(key) != value:
            raise RuntimeError(f"Milano configuration drift for {key}: {cfg.get(key)!r} != {value!r}")
    configured_sha = str(cfg.get("sha256") or "").strip().lower()
    if _SHA256.fullmatch(configured_sha):
        actual_sha = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual_sha != configured_sha:
            raise RuntimeError(f"Milano byte identity drift: {actual_sha!r} != {configured_sha!r}")


def _status_and_dates(first: str, second: str) -> tuple[str, str, str, str]:
    first = _clean(first)
    second = _clean(second)
    request = _REQUEST.fullmatch(first)
    if request:
        if second:
            raise RuntimeError(f"Milano pending row unexpectedly has an expiry cell: {second!r}")
        application = _source_date(request.group(1))
        if not application:
            raise RuntimeError(f"Milano invalid application date: {request.group(1)!r}")
        return "pending", application, "", ""
    if _UPDATE.fullmatch(first):
        if second:
            raise RuntimeError(f"Milano update row unexpectedly has an expiry cell: {second!r}")
        return "renewal_update_in_progress", "", "", ""
    listing = _source_date(first)
    expiry = _source_date(second)
    if listing and expiry:
        return "listed", "", listing, expiry
    raise RuntimeError(f"Milano unreviewed status/date pair: {first!r}, {second!r}")


def _parse_tables(text: str) -> list[list[list[str]]]:
    parser = _TableParser()
    try:
        parser.feed(text)
        parser.close()
    except (RuntimeError, ValueError) as exc:
        raise RuntimeError(f"Milano HTML table parsing failed: {exc}") from exc
    return parser.tables


def _activity(section_heading: str, section_number: int) -> str:
    return re.sub(rf"^Sezione\s+{section_number}\s+", "", section_heading, flags=re.I).strip()


def parse_milano_combined(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(path, cfg)
    tables = _parse_tables(_decode(path))
    if len(tables) != _EXPECTED_TABLES:
        raise RuntimeError(f"Milano table-count drift: {len(tables)} != {_EXPECTED_TABLES}")

    sector_rows: list[dict[str, Any]] = []
    section_headings: list[str] = []
    for section_number, table in enumerate(tables, start=1):
        if len(table) < 3:
            raise RuntimeError(f"Milano section {section_number} contains fewer than three rows")
        heading = _clean(table[0][0] if table[0] else "")
        if heading != _EXPECTED_SECTION_PREFIXES[section_number - 1]:
            raise RuntimeError(
                f"Milano section-heading drift for section {section_number}: {heading!r} != "
                f"{_EXPECTED_SECTION_PREFIXES[section_number - 1]!r}"
            )
        if tuple(_clean(value) for value in table[1]) != _HEADER:
            raise RuntimeError(f"Milano table-header drift in section {section_number}: {table[1]!r}")
        section_headings.append(heading)

        for physical_row, cells in enumerate(table[2:], start=3):
            if not any(_clean(value) for value in cells):
                continue
            if len(cells) != 6:
                raise RuntimeError(
                    f"Milano table-width drift in section {section_number}, row {physical_row}: {len(cells)}"
                )
            name, office, identifier_raw, first, second, note = [_clean(value) for value in cells]
            if not name or not office or not identifier_raw:
                raise RuntimeError(
                    f"Milano blank identity field in section {section_number}, row {physical_row}: {cells!r}"
                )
            if not _STRICT_IDENTIFIER.fullmatch(identifier_raw):
                raise RuntimeError(
                    f"Milano malformed identifier in section {section_number}, row {physical_row}: {identifier_raw!r}"
                )
            status, application_date, listing_date, expiry_date = _status_and_dates(first, second)
            sector_rows.append(
                {
                    "section": section_number,
                    "physical_row": physical_row,
                    "heading": heading,
                    "name": name,
                    "office": office,
                    "identifier_raw": identifier_raw,
                    "first_raw": first,
                    "second_raw": second,
                    "note": note,
                    "status": status,
                    "application_date": application_date,
                    "listing_date": listing_date,
                    "expiry_date": expiry_date,
                }
            )

    if len(sector_rows) != _EXPECTED_SECTOR_ROWS:
        raise RuntimeError(f"Milano sector-row drift: {len(sector_rows)} != {_EXPECTED_SECTOR_ROWS}")

    grouped: dict[tuple[str, ...], dict[str, Any]] = {}
    for row in sector_rows:
        key = (
            _normalise_text(row["name"]),
            row["identifier_raw"].upper(),
            _normalise_address(row["office"]),
            row["status"],
            row["application_date"],
            row["listing_date"],
            row["expiry_date"],
            _normalise_text(row["note"]),
        )
        group = grouped.setdefault(key, {"row": row, "sections": [], "locators": []})
        if row["section"] in group["sections"]:
            raise RuntimeError(
                "Milano duplicate same-section observation after conservative normalisation: "
                f"{row['name']!r}, section {row['section']}"
            )
        group["sections"].append(row["section"])
        group["locators"].append(f"section-{row['section']}:row-{row['physical_row']}")

    if len(grouped) != _EXPECTED_RECORDS:
        raise RuntimeError(f"Milano grouped-record drift: {len(grouped)} != {_EXPECTED_RECORDS}")

    records: list[dict[str, Any]] = []
    seen_identifiers: set[str] = set()
    for group in grouped.values():
        row = group["row"]
        identifier = row["identifier_raw"].upper()
        if identifier in seen_identifiers:
            raise RuntimeError(f"Milano identifier maps to multiple logical observations: {identifier}")
        seen_identifiers.add(identifier)
        sections = sorted(group["sections"])
        activities = [_activity(section_headings[number - 1], number) for number in sections]
        status = row["status"]
        record = _record(
            cfg,
            len(records) + 1,
            name=row["name"],
            office=row["office"],
            identifier_raw=row["identifier_raw"],
            activities=activities,
            status=status,
            outcome_raw=row["first_raw"] if status != "listed" else row["note"],
            application_date=row["application_date"],
            listing_date=row["listing_date"],
            expiry_date=row["expiry_date"],
            primary_date_label="Data presentazione istanza" if status == "pending" else ("Data iscrizione" if status == "listed" else ""),
            source_fields={
                "sections": [f"Sezione {number}" for number in sections],
                "section_headings": [section_headings[number - 1] for number in sections],
                "physical_locators": group["locators"],
                "status_or_listing_raw": row["first_raw"],
                "expiry_raw": row["second_raw"],
                "note": row["note"],
            },
        )
        # The audited current source has one logical observation per identifier.
        # Use that source-published identifier for a stable locator instead of
        # table position, which may change when firms move between sections.
        record["record_locator"] = f"{cfg['source_key']}:{cfg['reference_date']}:id-{identifier}"
        records.append(record)

    statuses = dict(Counter(record["source_status"] for record in records))
    if statuses != _EXPECTED_STATUS_COUNTS:
        raise RuntimeError(f"Milano status-count drift: {statuses!r} != {_EXPECTED_STATUS_COUNTS!r}")
    identifier_coverage = sum(bool(record["identifiers"]) for record in records)
    if identifier_coverage != _EXPECTED_IDENTIFIER_COVERAGE:
        raise RuntimeError(
            f"Milano identifier-coverage drift: {identifier_coverage} != {_EXPECTED_IDENTIFIER_COVERAGE}"
        )
    nonblank_notes = sum(bool(record["source_fields"]["note"]) for record in records)
    if nonblank_notes != _EXPECTED_NONBLANK_NOTES:
        raise RuntimeError(f"Milano note-denominator drift: {nonblank_notes} != {_EXPECTED_NONBLANK_NOTES}")

    return ParsedBatch(
        records=records,
        diagnostics={
            "parser": PARSER_NAME,
            "parser_version": PARSER_VERSION,
            "source_tables": len(tables),
            "sector_rows": len(sector_rows),
            "public_records": len(records),
            "status_counts": statuses,
            "identifier_coverage": identifier_coverage,
            "distinct_identifiers": len(seen_identifiers),
            "nonblank_notes": nonblank_notes,
            "requested_activity_coverage": sum(bool(record["requested_activities"]) for record in records),
            "application_date_coverage": sum(bool(record["application_date"]) for record in records),
            "listing_date_coverage": sum(bool(record["observed_listing_date"]) for record in records),
            "expiry_date_coverage": sum(bool(record["observed_expiry_date"]) for record in records),
        },
    )


PARSERS = {PARSER_NAME: parse_milano_combined}
