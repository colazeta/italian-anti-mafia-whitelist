from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import pdfplumber

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _clean, _record


LISTED_PARSER_NAME = "lecce_listed"
APPLICANT_PARSER_NAME = "lecce_applicants"
PARSER_VERSION = "1"

_EXPECTED_LISTED_PAGES = 78
_EXPECTED_LISTED_PAGE_ROWS = [
    35, 36, 36, 37, 37, 36, 36, 36, 27, 21, 22, 22, 22, 22, 21, 6, 0, 25, 26, 21,
    26, 26, 27, 26, 26, 26, 26, 26, 26, 26, 22, 22, 22, 22, 18, 0, 0, 23, 24, 24,
    24, 24, 24, 22, 24, 24, 24, 24, 24, 23, 24, 7, 24, 24, 24, 24, 22, 24, 24, 23,
    20, 7, 28, 20, 23, 22, 21, 21, 22, 21, 21, 19, 21, 21, 22, 22, 21, 12,
]
_EXPECTED_SECTION_ROWS = {
    "SEZIONE I – ESTRAZIONE, FORNITURA E TRASPORTO DI TERRA E MATERIALI INERTI": 316,
    "SEZIONE II – CONFEZIONAMENTO, FORNITURA E TRASPORTO DI CALCESTRUZZO E BITUME": 136,
    "SEZIONE III – NOLI A FREDDO DI MACCHINARI": 333,
    "SEZIONE IV – FORNITURA DI FERRO LAVORATO": 106,
    "SEZIONE V – NOLI A CALDO": 339,
    "SEZIONE VI – AUTOTRASPORTI PER CONTO TERZI": 209,
    "SEZIONE VII – GUARDIANIA AI CANTIERI": 7,
    "SEZIONE VIII - SERVIZI FUNERARI E CIMITERIALI": 48,
    "SEZIONE IX - RISTORAZIONE, GESTIONE DELLE MENSE E CATERING": 45,
    "SEZIONE X - SERVIZI AMBIENTALI ( EX SEZ. I E SEZ. II )": 244,
}
_EXPECTED_LISTED_SECTOR_ROWS = 1783
_EXPECTED_LISTED_RECORDS = 825
_EXPECTED_LISTED_STATUS = {"listed": 582, "renewal_update_in_progress": 243}
_EXPECTED_LISTED_IDENTIFIERS = 804
_EXPECTED_LISTED_RAW_ONLY = 20
_EXPECTED_LISTED_BLANK_IDENTIFIER = 1
_EXPECTED_MALFORMED_DATE_ROWS = 6

_EXPECTED_APPLICANT_PAGES = 10
_EXPECTED_APPLICANT_PAGE_ROWS = [9, 10, 10, 10, 10, 10, 10, 9, 9, 3]
_EXPECTED_APPLICANT_RECORDS = 90
_EXPECTED_APPLICANT_IDENTIFIERS = 90

_ADMIN_PREFIXES = (
    "Gestione Documentazione",
    "ELENCO DEI FORNITORI",
    "(art.",
    "Denominazione /",
)
_DATE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
_IDENTIFIER = re.compile(r"(?<![A-Za-z0-9])(?:\d{11}|[A-Za-z0-9]{16})(?![A-Za-z0-9])")
_SOURCE_UPDATE_MARKER = "09/09/2026"

_ALLOWED_UPDATE_RAW = {
    "AGGIORNAMENTO IN CORSO",
    "AGGIORNAMENTO IN CORSO PER VARIAZIONE COMPAGINE",
    "AGGIORNAMENTO I N CORSO",
    "AGGIORANMENTO IN CORSO",
    "AGGIORNAMENTO PER VARIAZIONE COMPAGINE",
    "AGGIORNAMENTO IN CORSO (richiesta rinnovo tramite PortaleWL del 3.8.2026)",
}
_ALLOWED_NON_UPDATE_NOTES = {
    "(Consorzio sottoposto alla misura del CONTROLLO GIUDIZIARIO ex art. 34 bis del D.Lgs n.159/2011, per la DURATA DI ANNI 1, a decorrere dal 24.7.2023, come da decreto del Tribunale di Lecce - Sezione Misure di Prevenzione depositato il 24.7.2023)",
    "L’iscrizioneèstataeffettuatainvirtùdella prorogadel controllogiudiziarioexart.34 bis del D.Lgs. 159/2011 disposta dal Tribunale di Lecce – Sezione Misure di Prevenzione con provvedimento del 6.7.2023, depositato in cancelleria il 19.7.2023 per la durata di un anno a decorrere dal 26.7.2023.",
}
_REVIEWED_MALFORMED_DATES = {
    (2, 22, "CONE S.r.l.", "expiry", "16/101/2026"),
    (5, 22, "G.M.T. SUD S.r.l.", "listing", "09-apr"),
    (8, 39, "SITE - Società Impianti Telefonici Elettrrici S.r.l.", "listing", "0 9/09/2026"),
    (23, 18, "FALP COSTRUZIONI S.R.L.", "listing", "2 8 / 0 8 /2026"),
    (43, 22, "FALP COSTRUZIONI S.R.L.", "listing", "2 8 / 0 8 / 2 026"),
    (71, 5, "ECOMETAL SOCIETA' COOPERATIVA", "expiry", "14//04/2025"),
}
_REVIEWED_BRI_SHIFT = [
    "BRI.ECO S.r.l.",
    "TAVIANO",
    "",
    "01/07/2026",
    "30/06/2027",
    "",
    "AGGIORNAMENTO IN CORSO",
]


def _iso_if_valid(raw: str) -> str:
    raw = _clean(raw)
    if not raw:
        return ""
    if not _DATE.fullmatch(raw):
        return ""
    try:
        return datetime.strptime(raw, "%d/%m/%Y").date().isoformat()
    except ValueError:
        return ""


def _strict_identifiers(raw: str) -> list[str]:
    values: list[str] = []
    for match in _IDENTIFIER.finditer(_clean(raw)):
        value = match.group(0).upper()
        if value not in values:
            values.append(value)
    return values


def _status(update_raw: str) -> str:
    update_raw = _clean(update_raw)
    if not update_raw or update_raw in _ALLOWED_NON_UPDATE_NOTES:
        return "listed"
    if update_raw in _ALLOWED_UPDATE_RAW:
        return "renewal_update_in_progress"
    raise RuntimeError(f"Lecce unreviewed listed status/note: {update_raw!r}")


def _listed_rows(path: Path) -> tuple[list[dict[str, Any]], list[int], Counter[str], set[tuple[int, int, str, str, str]]]:
    source_rows: list[dict[str, Any]] = []
    page_counts: list[int] = []
    section_counts: Counter[str] = Counter()
    malformed: set[tuple[int, int, str, str, str]] = set()
    current_section = ""

    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _EXPECTED_LISTED_PAGES:
            raise RuntimeError(
                f"Lecce listed page denominator drift: expected {_EXPECTED_LISTED_PAGES}, got {len(pdf.pages)}"
            )

        for page_number, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            if _SOURCE_UPDATE_MARKER not in text:
                raise RuntimeError(
                    f"Lecce listed page {page_number}: approved source-update marker {_SOURCE_UPDATE_MARKER!r} missing"
                )
            tables = page.find_tables()
            if len(tables) != 1:
                raise RuntimeError(
                    f"Lecce listed page {page_number}: expected one reviewed table, got {len(tables)}"
                )
            table = tables[0].extract()
            page_rows = 0
            for table_row, raw_row in enumerate(table):
                cells = [_clean(value) for value in raw_row]
                if len(cells) != 7:
                    raise RuntimeError(
                        f"Lecce listed page {page_number} table row {table_row}: expected 7 cells, got {len(cells)}"
                    )
                first = cells[0]
                if first.startswith("SEZIONE"):
                    current_section = first
                    continue
                if not any(cells) or any(first.startswith(prefix) for prefix in _ADMIN_PREFIXES):
                    continue

                if page_number == 1 and table_row == 31:
                    if cells != _REVIEWED_BRI_SHIFT:
                        raise RuntimeError(
                            f"Lecce reviewed BRI.ECO positional repair drift: {cells!r}"
                        )
                    cells = [cells[0], cells[1], cells[2], "", cells[3], cells[4], cells[6]]

                if not current_section:
                    raise RuntimeError(
                        f"Lecce listed page {page_number} row {table_row}: company row without reviewed section"
                    )

                name, office, secondary, identifier_raw, listing_raw, expiry_raw, update_raw = cells
                if not name:
                    raise RuntimeError(
                        f"Lecce listed page {page_number} row {table_row}: blank company name"
                    )
                for label, value in (("listing", listing_raw), ("expiry", expiry_raw)):
                    if value and not _iso_if_valid(value):
                        malformed.add((page_number, table_row, name, label, value))

                source_rows.append(
                    {
                        "page": page_number,
                        "table_row": table_row,
                        "section": current_section,
                        "name": name,
                        "office": office,
                        "secondary": secondary,
                        "identifier_raw": identifier_raw,
                        "listing_raw": listing_raw,
                        "expiry_raw": expiry_raw,
                        "update_raw": update_raw,
                    }
                )
                page_rows += 1
                section_counts[current_section] += 1
            page_counts.append(page_rows)

    return source_rows, page_counts, section_counts, malformed


def parse_lecce_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    source_rows, page_counts, section_counts, malformed = _listed_rows(path)
    if page_counts != _EXPECTED_LISTED_PAGE_ROWS:
        raise RuntimeError(
            f"Lecce listed page-row boundary drift: expected {_EXPECTED_LISTED_PAGE_ROWS!r}, got {page_counts!r}"
        )
    if dict(section_counts) != _EXPECTED_SECTION_ROWS:
        raise RuntimeError(
            f"Lecce listed section denominator drift: expected {_EXPECTED_SECTION_ROWS!r}, got {dict(section_counts)!r}"
        )
    if len(source_rows) != _EXPECTED_LISTED_SECTOR_ROWS:
        raise RuntimeError(
            f"Lecce listed sector-row denominator drift: expected {_EXPECTED_LISTED_SECTOR_ROWS}, got {len(source_rows)}"
        )
    if malformed != _REVIEWED_MALFORMED_DATES:
        raise RuntimeError(
            f"Lecce reviewed malformed-date boundary drift: expected {sorted(_REVIEWED_MALFORMED_DATES)!r}, got {sorted(malformed)!r}"
        )

    grouped: dict[tuple[str, ...], dict[str, Any]] = {}
    for row in source_rows:
        key = (
            row["name"],
            row["office"],
            row["secondary"],
            row["identifier_raw"],
            row["listing_raw"],
            row["expiry_raw"],
            row["update_raw"],
        )
        group = grouped.setdefault(
            key,
            {
                "sections": [],
                "source_locations": [],
            },
        )
        if row["section"] not in group["sections"]:
            group["sections"].append(row["section"])
        group["source_locations"].append([row["page"], row["table_row"]])

    if len(grouped) != _EXPECTED_LISTED_RECORDS:
        raise RuntimeError(
            f"Lecce listed public-record denominator drift: expected {_EXPECTED_LISTED_RECORDS}, got {len(grouped)}"
        )

    records: list[dict[str, Any]] = []
    for ordinal, (key, group) in enumerate(grouped.items(), 1):
        name, office, secondary, identifier_raw, listing_raw, expiry_raw, update_raw = key
        status = _status(update_raw)
        outcome_raw = update_raw if update_raw in _ALLOWED_NON_UPDATE_NOTES else ""
        record = _record(
            cfg,
            ordinal,
            name=name,
            office=office,
            secondary=secondary,
            identifier_raw=identifier_raw,
            activities=list(group["sections"]),
            status=status,
            outcome_raw=outcome_raw,
            listing_date=_iso_if_valid(listing_raw),
            expiry_date=_iso_if_valid(expiry_raw),
            primary_date_label="Data iscrizione",
            source_fields={
                "sections": list(group["sections"]),
                "registered_office_variants": [office] if office else [],
                "secondary_office_variants": [secondary] if secondary else [],
                "listing_date_raw_variants": [listing_raw] if listing_raw else [],
                "expiry_date_raw_variants": [expiry_raw] if expiry_raw else [],
                "in_aggiornamento": update_raw if update_raw in _ALLOWED_UPDATE_RAW else "",
            },
        )
        record["identifiers"] = _strict_identifiers(identifier_raw)
        records.append(record)

    statuses = Counter(record["source_status"] for record in records)
    identifier_coverage = sum(bool(record["identifiers"]) for record in records)
    raw_identifier_only = sum(
        bool(record["identifier_field_raw"]) and not record["identifiers"] for record in records
    )
    blank_identifier = sum(not record["identifier_field_raw"] for record in records)
    if dict(statuses) != _EXPECTED_LISTED_STATUS:
        raise RuntimeError(
            f"Lecce listed status boundary drift: expected {_EXPECTED_LISTED_STATUS!r}, got {dict(statuses)!r}"
        )
    if (
        identifier_coverage != _EXPECTED_LISTED_IDENTIFIERS
        or raw_identifier_only != _EXPECTED_LISTED_RAW_ONLY
        or blank_identifier != _EXPECTED_LISTED_BLANK_IDENTIFIER
    ):
        raise RuntimeError(
            "Lecce listed identifier boundary drift: "
            f"structured={identifier_coverage}, raw_only={raw_identifier_only}, blank={blank_identifier}"
        )

    diagnostics = {
        "parser": LISTED_PARSER_NAME,
        "parser_version": PARSER_VERSION,
        "pages": _EXPECTED_LISTED_PAGES,
        "page_rows": page_counts,
        "sector_rows": len(source_rows),
        "section_rows": dict(section_counts),
        "public_records": len(records),
        "status_counts": dict(statuses),
        "identifier_coverage": identifier_coverage,
        "raw_identifier_only": raw_identifier_only,
        "blank_identifier": blank_identifier,
        "malformed_date_rows_preserved": len(malformed),
    }
    return ParsedBatch(records, diagnostics)


def parse_lecce_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    extracted: list[tuple[int, int, list[str]]] = []
    page_counts: list[int] = []
    expected_header = [
        "RAGIONE SOCIALE",
        "SEDE LEGALE",
        "CODICE FISCALE",
        "DATA DI PRESENTAZIONE DELL'ISTANZA",
    ]

    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _EXPECTED_APPLICANT_PAGES:
            raise RuntimeError(
                f"Lecce applicant page denominator drift: expected {_EXPECTED_APPLICANT_PAGES}, got {len(pdf.pages)}"
            )
        for page_number, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            if _SOURCE_UPDATE_MARKER not in text:
                raise RuntimeError(
                    f"Lecce applicant page {page_number}: approved source-update marker {_SOURCE_UPDATE_MARKER!r} missing"
                )
            tables = page.find_tables()
            if len(tables) != 1:
                raise RuntimeError(
                    f"Lecce applicant page {page_number}: expected one reviewed table, got {len(tables)}"
                )
            table = tables[0].extract()
            if not table:
                raise RuntimeError(f"Lecce applicant page {page_number}: empty reviewed table")
            header = [_clean(value) for value in table[0]]
            if header != expected_header:
                raise RuntimeError(
                    f"Lecce applicant page {page_number}: header drift: expected {expected_header!r}, got {header!r}"
                )

            page_rows = 0
            for table_row, raw_row in enumerate(table[1:], 1):
                cells = [_clean(value) for value in raw_row]
                if not any(cells):
                    continue
                if len(cells) != 4:
                    raise RuntimeError(
                        f"Lecce applicant page {page_number} row {table_row}: expected 4 cells, got {len(cells)}"
                    )
                name, office, identifier_raw, application_raw = cells
                if not name or not identifier_raw:
                    raise RuntimeError(
                        f"Lecce applicant page {page_number} row {table_row}: blank company identity field"
                    )
                if not _iso_if_valid(application_raw):
                    raise RuntimeError(
                        f"Lecce applicant page {page_number} row {table_row}: application-date drift {application_raw!r}"
                    )
                extracted.append((page_number, table_row, cells))
                page_rows += 1
            page_counts.append(page_rows)

    if page_counts != _EXPECTED_APPLICANT_PAGE_ROWS:
        raise RuntimeError(
            f"Lecce applicant page-row boundary drift: expected {_EXPECTED_APPLICANT_PAGE_ROWS!r}, got {page_counts!r}"
        )
    if len(extracted) != _EXPECTED_APPLICANT_RECORDS:
        raise RuntimeError(
            f"Lecce applicant denominator drift: expected {_EXPECTED_APPLICANT_RECORDS}, got {len(extracted)}"
        )

    records: list[dict[str, Any]] = []
    for ordinal, (_page_number, _table_row, cells) in enumerate(extracted, 1):
        name, office, identifier_raw, application_raw = cells
        record = _record(
            cfg,
            ordinal,
            name=name,
            office=office,
            identifier_raw=identifier_raw,
            status="pending",
            application_date=application_raw,
            primary_date_label="Data presentazione istanza",
            source_fields={
                "application_date_raw_variants": [application_raw],
            },
        )
        record["identifiers"] = _strict_identifiers(identifier_raw)
        records.append(record)

    statuses = Counter(record["source_status"] for record in records)
    identifier_coverage = sum(bool(record["identifiers"]) for record in records)
    if statuses != Counter({"pending": _EXPECTED_APPLICANT_RECORDS}):
        raise RuntimeError(f"Lecce applicant status boundary drift: {dict(statuses)!r}")
    if identifier_coverage != _EXPECTED_APPLICANT_IDENTIFIERS:
        raise RuntimeError(
            f"Lecce applicant identifier boundary drift: expected {_EXPECTED_APPLICANT_IDENTIFIERS}, got {identifier_coverage}"
        )

    diagnostics = {
        "parser": APPLICANT_PARSER_NAME,
        "parser_version": PARSER_VERSION,
        "pages": _EXPECTED_APPLICANT_PAGES,
        "page_rows": page_counts,
        "source_rows": len(extracted),
        "public_records": len(records),
        "status_counts": dict(statuses),
        "identifier_coverage": identifier_coverage,
        "raw_identifier_only": 0,
    }
    return ParsedBatch(records, diagnostics)


PARSERS = {
    LISTED_PARSER_NAME: parse_lecce_listed,
    APPLICANT_PARSER_NAME: parse_lecce_applicants,
}
