from __future__ import annotations

import re
from collections import Counter, OrderedDict
from datetime import date
from pathlib import Path
from typing import Any

import pdfplumber

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _clean, _record

PARSER_VERSION = "1"
_LISTED_SOURCE_KEY = "foggia-listed"
_APPLICANT_SOURCE_KEY = "foggia-applicants"
_LISTED_REFERENCE_DATE = "2026-09-08"
_APPLICANT_REFERENCE_DATE = "2026-09-10"
_LISTED_PAGES = 44
_APPLICANT_PAGES = 46
_EXPECTED_LISTED_SECTOR_ROWS = 942
_EXPECTED_LISTED_RECORDS = 330
_EXPECTED_LISTED_STATUS_COUNTS = {"listed": 85, "renewal_update_in_progress": 245}
_EXPECTED_APPLICANT_RECORDS = 628
_EXPECTED_APPLICANT_STATUS_COUNTS = {"pending": 628}
_EXPECTED_APPLICANT_STRICT_IDENTIFIER_ROWS = 621
_EXPECTED_APPLICANT_RAW_IDENTIFIER_ROWS = 6
_EXPECTED_APPLICANT_EMPTY_IDENTIFIER_ROWS = 1

_STRICT_IDENTIFIER = re.compile(r"(?<![A-Za-z0-9])(?:\d{11}|[A-Za-z]{6}[0-9A-Za-z]{10})(?![A-Za-z0-9])")
_DATE = re.compile(r"^(\d{1,2})[./](\d{1,2})[./](\d{4})$")
_YEAR = re.compile(r"20\d{2}")
_SECTION = re.compile(r"\bSezione\s+([IVX]+)\s*[:.-]?\s*([^\n]*)", re.I)
_STATUS_LIKE_NAME = {"in corso"}
_ROMAN_TO_INT = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10}

# Exact source lexemes observed on the byte-pinned 8 September 2026 listed PDF.
# These notes do not negate registration; they are preserved verbatim while the
# canonical record remains listed. No unknown nonblank lexeme is accepted.
_REVIEWED_LISTED_NOTES = {
    "n. B. Iscrizione effettuata limitatamente alla sussistenza dell’applicazione della misura amministrativa di prevenzione collaborativa ex art. 94 bis del Codice Antimafia per un periodo di 12 mesi a decorrere dal 09.09.2025",
    "N. B. Iscrizione effettuata in esecuzione del provvedimento del Tribunale di Bari sez. III n. 08/2024 del 26.02.2025, depositata in cancelleria in data 11.04.2025, che ha disposto il controllo giudiziario nei confronti della società per la durata di anni 2 (due). In applicazione dell’art. art. 34 bis, comma 6. In applicazione dell’art. 34-bis, comma 7 sono sospesi gli effetti di cui all’art. 94 D. Lgs. 159/2011",
    "N. B. Iscrizione effettuata in esecuzione del provvedimento del tribunale di Bari sez. III n. 94/24 A.G., depositato in data 27.09.2024 che ha disposto la misura di prevenzione dell’Amministrazione Giudiziaria nei confronti della società per la durata di anni 1 (uno) ai sensi dell’art. 34 del d.lgs. 159/2011. *Proroga ulteriori 6 mesi",
    "N. B. Iscrizione effettuata in esecuzione del provvedimento del Tribunale di Bari sez. III n. 08/2024 del 26.02.2025, depositata in cancelleria in data 11.04.2025, che ha disposto il controllo giudiziario nei confronti della società per la durata di anni 2 (due). In applicazione dell’art. art. 34 bis, comma 6.In applicazione dell’art. 34-bis, comma 7 sono sospesi gli effetti di cui all’art. 94 D. Lgs. 159/2011",
    "N. B. Iscrizione effettuata in esecuzione del provvedimento del Tribunale di Bari sez. III n. 03/2023 del 19.09.2023 che ha disposto il controllo giudiziario nei confronti della società per la durata di anni 2 (due). In applicazione dell’art. art. 34 bis, comma 2, lett. b) è stato nominato Amministratore giudiziario l’avv. Luca D’Amore con studio in Roma alla via Maestro Gaetano Capocci n. 6 (numero iscr. Albo 691).",
    "n. B. Iscrizione effettuata limitatamente alla sussistenza dell’applicazione delle misure straordinarie, previste dall’art. 32, comma 10, del d.l. n. 90/2014, convertito nella L. 114/2014 per un periodo di 180 giorni a decorrere dal 02.04.2026",
}

# Only these three strict-identity/date/status groups contain multiple source
# name spellings on the pinned listed PDF. Representative names are evidence-
# backed and raw variants remain in source_fields.
_REVIEWED_NAME_GROUPS: dict[tuple[str, str, str, str], tuple[frozenset[str], str, str]] = {
    (
        "03935050710",
        "2026-06-03",
        "2027-06-03",
        "listed",
    ): (
        frozenset(
            {
                "COOPERATIVA AGROFORESTALE S. MARCO DI PRODUZIONE E LAVORO A R.L.",
                "COOPERATIVA AGROFORESTALE S. MARCO DI PRODUZIONE E LAVORO A R. L.",
            }
        ),
        "COOPERATIVA AGROFORESTALE S. MARCO DI PRODUZIONE E LAVORO A R.L.",
        "reviewed_source_name_spacing_variant",
    ),
    (
        "03570730717",
        "2025-06-11",
        "2026-06-11",
        "listed",
    ): (
        frozenset({"In corso", "LUISI COSTRUZIONI DI LUISI CARMINE"}),
        "LUISI COSTRUZIONI DI LUISI CARMINE",
        "reviewed_source_name_column_inconsistency",
    ),
    (
        "01132870716",
        "2016-06-17",
        "2017-06-17",
        "renewal_update_in_progress",
    ): (
        frozenset(
            {
                "IMPRESA EDILE E STRADALE MEDITERRANEA DI GRITTANI GEOM. CIRO",
                "IMPRESA EDILE E STRADALE MDITERRANEA DI GRITTANI GEOM. CIRO",
            }
        ),
        "IMPRESA EDILE E STRADALE MEDITERRANEA DI GRITTANI GEOM. CIRO",
        "reviewed_source_name_typography_variant",
    ),
}


def _validate_cfg(cfg: dict[str, Any], *, source_key: str, reference_date: str) -> None:
    if cfg.get("source_key") != source_key:
        raise RuntimeError(f"Foggia parser/source mismatch: {cfg.get('source_key')!r} != {source_key!r}")
    if cfg.get("authority_key") != "foggia":
        raise RuntimeError("Foggia parser bound to a non-Foggia authority")
    if cfg.get("reference_date") != reference_date:
        raise RuntimeError(f"Foggia reference-date drift: {cfg.get('reference_date')!r} != {reference_date!r}")


def _strict_identifiers(value: str) -> list[str]:
    return list(dict.fromkeys(match.group(0).upper() for match in _STRICT_IDENTIFIER.finditer(_clean(value))))


def _parse_date(value: str) -> str:
    raw = _clean(value)
    match = _DATE.fullmatch(raw)
    if not match:
        return ""
    day, month, year = map(int, match.groups())
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return ""


def _date_key(value: str) -> str:
    parsed = _parse_date(value)
    return f"ISO::{parsed}" if parsed else f"RAW::{_clean(value)}"


def _status_group(raw: str) -> str:
    value = _clean(raw)
    compact = re.sub(r"\s+", "", value).casefold()
    if not compact:
        return "listed"
    if compact in {"incorso", "iincorso"}:
        return "renewal_update_in_progress"
    if value in _REVIEWED_LISTED_NOTES:
        return "listed_note"
    raise RuntimeError(f"Foggia unreviewed listed status/note: {value!r}")


def _public_status(group_status: str) -> str:
    if group_status == "renewal_update_in_progress":
        return group_status
    if group_status in {"listed", "listed_note"}:
        return "listed"
    raise RuntimeError(f"Foggia unsupported internal status group: {group_status!r}")


def _section_from_page(text: str) -> tuple[str, str]:
    match = _SECTION.search(text or "")
    if not match:
        raise RuntimeError("Foggia listed page without a recognised White List section heading")
    roman = match.group(1).upper()
    if roman not in _ROMAN_TO_INT:
        raise RuntimeError(f"Foggia unsupported section numeral: {roman!r}")
    return f"Sezione {_ROMAN_TO_INT[roman]}", _clean(match.group(2))


def _activity_parts(value: str) -> list[str]:
    raw = _clean(value)
    if not raw:
        return []
    parts = [_clean(part).rstrip(".") for part in re.split(r"\s*;\s*", raw) if _clean(part)]
    return parts or [raw]


def _is_header(row: list[str]) -> bool:
    folded = " | ".join(row).casefold()
    return any(token in folded for token in ("ragione sociale", "codice fiscale", "partita iva", "data presentazione"))


def _representative_name(group: dict[str, Any], key: tuple[str, ...]) -> tuple[str, str]:
    names = group["name_variants"]
    if len(names) == 1:
        return names[0], ""
    if key[0] != "id":
        raise RuntimeError(f"Foggia unreviewed multi-name raw-identifier group: {key!r}: {names!r}")
    identity = key[1]
    listing = key[2].removeprefix("ISO::") if key[2].startswith("ISO::") else ""
    expiry = key[3].removeprefix("ISO::") if key[3].startswith("ISO::") else ""
    public_status = _public_status(key[4])
    reviewed = _REVIEWED_NAME_GROUPS.get((identity, listing, expiry, public_status))
    if reviewed is None:
        raise RuntimeError(f"Foggia unreviewed multi-name strict-identity group: {key!r}: {names!r}")
    expected, representative, reason = reviewed
    if frozenset(names) != expected:
        raise RuntimeError(f"Foggia reviewed name variants drifted for {identity}: {names!r}")
    if representative.casefold() in _STATUS_LIKE_NAME:
        raise RuntimeError(f"Foggia reviewed representative is status-like for {identity}")
    return representative, reason


def parse_foggia_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(cfg, source_key=_LISTED_SOURCE_KEY, reference_date=_LISTED_REFERENCE_DATE)
    sector_rows: list[dict[str, Any]] = []
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _LISTED_PAGES:
            raise RuntimeError(f"Foggia listed page-count drift: {len(pdf.pages)} != {_LISTED_PAGES}")
        for page_number, page in enumerate(pdf.pages, start=1):
            section, section_label_raw = _section_from_page(page.extract_text() or "")
            tables = page.extract_tables() or []
            if len(tables) != 1:
                raise RuntimeError(f"Foggia listed page {page_number} table-count drift: {len(tables)} != 1")
            for row_number, raw_row in enumerate(tables[0] or [], start=1):
                row = [_clean(cell) for cell in (raw_row or [])]
                if not any(row) or _is_header(row):
                    continue
                if len(row) != 7:
                    raise RuntimeError(f"Foggia listed row-width drift p{page_number}:r{row_number}: {len(row)}")
                # Repeated page boilerplate has no company/date semantics. Company rows
                # have a name, an identifier field, and at least one year-bearing date.
                if not row[0] or not row[3] or not (_YEAR.search(row[4]) or _YEAR.search(row[5])):
                    continue
                group_status = _status_group(row[6])
                sector_rows.append(
                    {
                        "page": page_number,
                        "row": row_number,
                        "cells": row,
                        "section": section,
                        "section_label_raw": section_label_raw,
                        "status_group": group_status,
                    }
                )

    if len(sector_rows) != _EXPECTED_LISTED_SECTOR_ROWS:
        raise RuntimeError(f"Foggia listed sector-row drift: {len(sector_rows)} != {_EXPECTED_LISTED_SECTOR_ROWS}")

    groups: OrderedDict[tuple[str, ...], dict[str, Any]] = OrderedDict()
    for item in sector_rows:
        row = item["cells"]
        identifiers = _strict_identifiers(row[3])
        if len(identifiers) == 1:
            key = ("id", identifiers[0], _date_key(row[4]), _date_key(row[5]), item["status_group"])
        else:
            key = ("raw", row[0], row[3], _date_key(row[4]), _date_key(row[5]), item["status_group"])
        group = groups.setdefault(
            key,
            {
                "name_variants": [],
                "office_variants": [],
                "secondary_office_variants": [],
                "identifier_raw_variants": [],
                "sections": [],
                "section_label_raw_variants": [],
                "listing_raw_variants": [],
                "expiry_raw_variants": [],
                "outcome_raw_variants": [],
                "source_locators": [],
            },
        )
        for field, value in (
            ("name_variants", row[0]),
            ("office_variants", row[1]),
            ("secondary_office_variants", row[2]),
            ("identifier_raw_variants", row[3]),
            ("listing_raw_variants", row[4]),
            ("expiry_raw_variants", row[5]),
            ("outcome_raw_variants", row[6]),
            ("sections", item["section"]),
            ("section_label_raw_variants", f"{item['section']} - {item['section_label_raw']}"),
        ):
            if value and value not in group[field]:
                group[field].append(value)
        group["source_locators"].append(f"p{item['page']}:r{item['row']}")

    if len(groups) != _EXPECTED_LISTED_RECORDS:
        raise RuntimeError(f"Foggia listed grouped-record drift: {len(groups)} != {_EXPECTED_LISTED_RECORDS}")

    records: list[dict[str, Any]] = []
    reconciliation_count = 0
    for key, group in groups.items():
        name, reconciliation = _representative_name(group, key)
        if reconciliation:
            reconciliation_count += 1
        group_status = key[-1]
        listing_key = key[-3]
        expiry_key = key[-2]
        public_status = _public_status(group_status)
        listing_date = listing_key.removeprefix("ISO::") if listing_key.startswith("ISO::") else ""
        expiry_date = expiry_key.removeprefix("ISO::") if expiry_key.startswith("ISO::") else ""
        outcome_raw = ""
        if public_status == "renewal_update_in_progress":
            outcome_raw = "IN CORSO"
        elif group_status == "listed_note":
            outcome_raw = group["outcome_raw_variants"][0]
        record = _record(
            cfg,
            len(records) + 1,
            name=name,
            office=group["office_variants"][0] if group["office_variants"] else "",
            secondary=group["secondary_office_variants"][0] if group["secondary_office_variants"] else "",
            identifier_raw=group["identifier_raw_variants"][0] if group["identifier_raw_variants"] else "",
            activities=list(group["sections"]),
            status=public_status,
            outcome_raw=outcome_raw,
            listing_date=listing_date,
            expiry_date=expiry_date,
            primary_date_label="Data iscrizione",
            source_fields={
                "name_variants": group["name_variants"],
                "registered_office_variants": group["office_variants"],
                "secondary_office_variants": group["secondary_office_variants"],
                "identifier_raw_variants": group["identifier_raw_variants"],
                "sections": group["sections"],
                "section_heading_raw_variants": group["section_label_raw_variants"],
                "listing_date_raw_variants": group["listing_raw_variants"],
                "expiry_date_raw_variants": group["expiry_raw_variants"],
                "outcome_raw_variants": group["outcome_raw_variants"],
                "source_locators": group["source_locators"],
                "reviewed_name_reconciliation": reconciliation,
            },
        )
        record["identifiers"] = _strict_identifiers(record["identifier_field_raw"])
        records.append(record)

    status_counts = dict(Counter(record["source_status"] for record in records))
    if status_counts != _EXPECTED_LISTED_STATUS_COUNTS:
        raise RuntimeError(f"Foggia listed status-count drift: {status_counts!r} != {_EXPECTED_LISTED_STATUS_COUNTS!r}")
    return ParsedBatch(
        records,
        {
            "parser": "foggia_listed",
            "parser_version": PARSER_VERSION,
            "sector_rows": len(sector_rows),
            "public_records": len(records),
            "status_counts": status_counts,
            "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
            "raw_identifier_only": sum(bool(record["identifier_field_raw"]) and not record["identifiers"] for record in records),
            "raw_date_groups": sum(not key[-3].startswith("ISO::") or not key[-2].startswith("ISO::") for key in groups),
            "reviewed_name_reconciliations": reconciliation_count,
        },
    )


def parse_foggia_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(cfg, source_key=_APPLICANT_SOURCE_KEY, reference_date=_APPLICANT_REFERENCE_DATE)
    records: list[dict[str, Any]] = []
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _APPLICANT_PAGES:
            raise RuntimeError(f"Foggia applicant page-count drift: {len(pdf.pages)} != {_APPLICANT_PAGES}")
        for page_number, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables() or []
            if len(tables) != 1:
                raise RuntimeError(f"Foggia applicant page {page_number} table-count drift: {len(tables)} != 1")
            for row_number, raw_row in enumerate(tables[0] or [], start=1):
                row = [_clean(cell) for cell in (raw_row or [])]
                if not any(row) or _is_header(row):
                    continue
                if len(row) != 7:
                    raise RuntimeError(f"Foggia applicant row-width drift p{page_number}:r{row_number}: {len(row)}")
                if not row[0] or not row[6]:
                    continue
                if row[6] != "ISTRUTTORIA":
                    raise RuntimeError(f"Foggia unreviewed applicant outcome p{page_number}:r{row_number}: {row[6]!r}")
                application_date = _parse_date(row[5])
                if not application_date:
                    raise RuntimeError(f"Foggia unreviewed applicant date p{page_number}:r{row_number}: {row[5]!r}")
                if not row[4]:
                    raise RuntimeError(f"Foggia applicant row without requested activity p{page_number}:r{row_number}")
                record = _record(
                    cfg,
                    len(records) + 1,
                    name=row[0],
                    office=row[1],
                    secondary=row[2],
                    identifier_raw=row[3],
                    activities=_activity_parts(row[4]),
                    status="pending",
                    outcome_raw=row[6],
                    application_date=application_date,
                    primary_date_label="Data presentazione istanza",
                    source_fields={
                        "requested_activities_source": row[4],
                        "application_date_raw": row[5],
                        "source_locator": f"p{page_number}:r{row_number}",
                    },
                )
                record["identifiers"] = _strict_identifiers(row[3])
                records.append(record)

    if len(records) != _EXPECTED_APPLICANT_RECORDS:
        raise RuntimeError(f"Foggia applicant record-count drift: {len(records)} != {_EXPECTED_APPLICANT_RECORDS}")
    status_counts = dict(Counter(record["source_status"] for record in records))
    if status_counts != _EXPECTED_APPLICANT_STATUS_COUNTS:
        raise RuntimeError(f"Foggia applicant status-count drift: {status_counts!r}")
    identifier_coverage = sum(bool(record["identifiers"]) for record in records)
    raw_identifier_only = sum(bool(record["identifier_field_raw"]) and not record["identifiers"] for record in records)
    empty_identifier = sum(not record["identifier_field_raw"] for record in records)
    if (
        identifier_coverage != _EXPECTED_APPLICANT_STRICT_IDENTIFIER_ROWS
        or raw_identifier_only != _EXPECTED_APPLICANT_RAW_IDENTIFIER_ROWS
        or empty_identifier != _EXPECTED_APPLICANT_EMPTY_IDENTIFIER_ROWS
    ):
        raise RuntimeError(
            "Foggia applicant identifier-coverage drift: "
            f"strict={identifier_coverage}, raw_only={raw_identifier_only}, empty={empty_identifier}"
        )
    return ParsedBatch(
        records,
        {
            "parser": "foggia_applicants",
            "parser_version": PARSER_VERSION,
            "source_rows": len(records),
            "public_records": len(records),
            "status_counts": status_counts,
            "identifier_coverage": identifier_coverage,
            "raw_identifier_only": raw_identifier_only,
            "empty_identifier": empty_identifier,
        },
    )
