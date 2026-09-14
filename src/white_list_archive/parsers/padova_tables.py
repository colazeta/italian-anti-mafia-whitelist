from __future__ import annotations

import hashlib
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import pdfplumber

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _clean, _record

PARSER_VERSION = "1"
_REFERENCE_DATE = "2026-08-14"
_LISTED_SHA256 = "d140451c7a091e7df497f49465177ba012422917d2031c24df676e76dd909289"
_APPLICANT_SHA256 = "b2cce4c2d34db016a7b84ac83f71032acdf319c020e1bf881d923ef1d45601a3"
_LISTED_PAGES = 105
_APPLICANT_PAGES = 17
_EXPECTED_LISTED_RECORDS = 831
_EXPECTED_APPLICANT_RECORDS = 174
_EXPECTED_LISTED_STATUS_COUNTS = {"listed": 581, "renewal_update_in_progress": 250}
_EXPECTED_APPLICANT_STATUS_COUNTS = {"pending": 174}
_EXPECTED_LISTED_IDENTIFIER_COUNTS = {0: 9, 1: 713, 2: 109}
_EXPECTED_APPLICANT_IDENTIFIER_COUNTS = {0: 2, 1: 143, 2: 29}

_DATE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
_PROTOCOL = re.compile(r"^\d+/\d{4}$")
_IDENTIFIER_11 = re.compile(r"^\d{11}$")
_IDENTIFIER_16 = re.compile(r"^[A-Z0-9]{16}$")
_UPDATE_NOTE = (
    "IN FASE DI AGGIORNAMENTO l'iscrizione resta valida anche oltre la scadenza, "
    "fino all'esito definitivo"
)

# Both values are printed verbatim in the byte-pinned official listed PDF and
# are not calendar dates. They are retained as raw source fields but never
# interpreted as dates.
_LISTED_NONCALENDAR_EXPIRY = {
    108: (
        "BIOPROGRAMM BIOTECNOLOGIE AVANZATE E TECNICHE AMBIENTALI SRL",
        "02038910283",
        "14/07/2026",
        "46581,00",
    ),
    479: (
        "LA PERLA TRASPORTI E LOGISTICA DI MORELLO CARLO",
        "MRLCRL77H12F904 M/05700010282",
        "24/06/2026",
        "8807/2026",
    ),
}

# pdfplumber's table extraction loses the printed company name in this one
# physical row even though the words are visibly present in the same cell of
# the byte-pinned source. Recovery is therefore exact and source-bound.
_APPLICANT_NAME_RECOVERY = {
    113: (
        (
            "",
            "SELVAZZANO DENTRO, VIA ENRICO FERMI 2",
            "",
            "05504630285",
            "",
            "",
            "3",
            "",
            "5",
            "",
            "",
            "",
            "",
            "",
            "21/08/2025",
            "12319/2025",
            "",
        ),
        "NON SOLO ZANZARE SRL",
    )
}

# The source itself contains two adjacent, fully identical applicant rows.
# They are separate source observations and must not be deduplicated.
_APPLICANT_REVIEWED_DUPLICATE = (38, 39)
_EXPECTED_DUPLICATE_ROW = (
    "CLEAN SRL",
    "CAMPOSAMPIERO, VIA BORGO PADOVA 64",
    "",
    "02027230289",
    "",
    "",
    "3",
    "4",
    "",
    "",
    "",
    "",
    "",
    "",
    "14/01/2026",
    "674/2026",
    "",
)

# This chronology is printed in the official source. It is retained without
# correction and frozen so a future edition/extraction change fails closed.
_LISTED_REVIEWED_DATE_INVERSION = {
    387: (
        "GEROTTO FEDERICO SRL",
        "18/06/2026",
        "04/02/2025",
        _UPDATE_NOTE,
    )
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_cfg(cfg: dict[str, Any], *, source_key: str, population_scope: str, sha256: str) -> None:
    if cfg.get("source_key") != source_key:
        raise RuntimeError(f"Padova source-key drift: {cfg.get('source_key')!r} != {source_key!r}")
    if cfg.get("authority_key") != "padova":
        raise RuntimeError("Padova parser bound to a non-Padova authority")
    if cfg.get("population_scope") != population_scope:
        raise RuntimeError(
            f"Padova population-scope drift for {source_key}: "
            f"{cfg.get('population_scope')!r} != {population_scope!r}"
        )
    if cfg.get("sha256") != sha256:
        raise RuntimeError(
            f"Padova configured SHA-256 drift for {source_key}: {cfg.get('sha256')!r} != {sha256!r}"
        )
    if cfg.get("reference_date") != _REFERENCE_DATE:
        raise RuntimeError(
            f"Padova reference-date drift for {source_key}: "
            f"{cfg.get('reference_date')!r} != {_REFERENCE_DATE!r}"
        )


def _date(raw: str, *, ordinal: int, population: str, field: str) -> str:
    value = _clean(raw)
    if not _DATE.fullmatch(value):
        raise RuntimeError(
            f"Padova {population} unreviewed {field} typography at ordinal {ordinal}: {value!r}"
        )
    try:
        datetime.strptime(value, "%d/%m/%Y")
    except ValueError as exc:
        raise RuntimeError(
            f"Padova {population} invalid {field} calendar date at ordinal {ordinal}: {value!r}"
        ) from exc
    return value


def _strict_identifiers(raw: str) -> list[str]:
    """Extract only explicit fiscal/VAT identifiers while preserving raw text separately.

    The official PDF visually line-wraps some identifiers inside a table cell.
    Whitespace inside an explicit slash-delimited component is therefore removed,
    but no punctuation other than that source delimiter is treated as evidence of
    multiple identifiers.
    """

    values: list[str] = []
    for component in _clean(raw).upper().split("/"):
        token = re.sub(r"\s+", "", component)
        if (_IDENTIFIER_11.fullmatch(token) or _IDENTIFIER_16.fullmatch(token)) and token not in values:
            values.append(token)
    return values


def _sections(cells: list[str], *, ordinal: int, population: str) -> list[str]:
    sections: list[str] = []
    for section_number, value in enumerate(cells[4:14], start=1):
        if not value:
            continue
        if value != str(section_number):
            raise RuntimeError(
                f"Padova {population} section-cell drift at ordinal {ordinal}: "
                f"column={section_number}; value={value!r}"
            )
        sections.append(f"Sezione {section_number}")
    if not sections:
        raise RuntimeError(f"Padova {population} row without a positive source section at ordinal {ordinal}")
    return sections


def _physical_rows(path: Path, *, pages: int, expected_records: int, population: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    header_count = 0
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != pages:
            raise RuntimeError(f"Padova {population} page-count drift: {len(pdf.pages)} != {pages}")
        for page_number, page in enumerate(pdf.pages, start=1):
            tables = page.find_tables()
            if len(tables) != 1:
                raise RuntimeError(
                    f"Padova {population} table-count drift on page {page_number}: {len(tables)} != 1"
                )
            extracted = tables[0].extract() or []
            page_headers = 0
            for row_number, raw in enumerate(extracted, start=1):
                cells = [_clean(value) for value in (raw or [])]
                if not any(cells):
                    continue
                if len(cells) != 17:
                    raise RuntimeError(
                        f"Padova {population} table-width drift p{page_number} r{row_number}: "
                        f"{len(cells)} != 17"
                    )
                if cells[0] == "Ragione Sociale":
                    header_count += 1
                    page_headers += 1
                    continue
                rows.append({"page": page_number, "row": row_number, "cells": cells})
            if page_headers != 1:
                raise RuntimeError(
                    f"Padova {population} header-count drift on page {page_number}: {page_headers} != 1"
                )
    if header_count != pages:
        raise RuntimeError(f"Padova {population} total header-count drift: {header_count} != {pages}")
    if len(rows) != expected_records:
        raise RuntimeError(
            f"Padova {population} source denominator drift: {len(rows)} != {expected_records}"
        )
    return rows


def _recover_applicant_names(rows: list[dict[str, Any]]) -> None:
    blank_names = {ordinal for ordinal, row in enumerate(rows, start=1) if not row["cells"][0]}
    expected = set(_APPLICANT_NAME_RECOVERY)
    if blank_names != expected:
        raise RuntimeError(
            f"Padova applicant blank-name population drift: observed={sorted(blank_names)!r}; "
            f"expected={sorted(expected)!r}"
        )
    for ordinal, (expected_row, recovered_name) in _APPLICANT_NAME_RECOVERY.items():
        current = tuple(rows[ordinal - 1]["cells"])
        if current != expected_row:
            raise RuntimeError(
                f"Padova applicant reviewed name-recovery drift at ordinal {ordinal}: "
                f"{current!r} != {expected_row!r}"
            )
        rows[ordinal - 1]["cells"][0] = recovered_name


def _listed_expiry(
    raw: str,
    *,
    ordinal: int,
    company: str,
    identifier_raw: str,
    listing_raw: str,
) -> str:
    value = _clean(raw)
    reviewed = _LISTED_NONCALENDAR_EXPIRY.get(ordinal)
    if reviewed is not None:
        expected_company, expected_identifier, expected_listing, expected_expiry = reviewed
        if (
            _clean(company) != expected_company
            or _clean(identifier_raw).upper() != expected_identifier
            or _clean(listing_raw) != expected_listing
            or value != expected_expiry
        ):
            raise RuntimeError(
                f"Padova listed reviewed non-calendar expiry drift at ordinal {ordinal}: "
                f"company={_clean(company)!r}; identifier={_clean(identifier_raw)!r}; "
                f"listing={_clean(listing_raw)!r}; expiry={value!r}"
            )
        return ""
    return _date(value, ordinal=ordinal, population="listed", field="expiry date")


def _validate_listed_chronology(rows: list[dict[str, Any]]) -> None:
    observed: dict[int, tuple[str, str, str, str]] = {}
    for ordinal, row in enumerate(rows, start=1):
        c = row["cells"]
        if ordinal in _LISTED_NONCALENDAR_EXPIRY:
            continue
        listing = datetime.strptime(_date(c[14], ordinal=ordinal, population="listed", field="listing date"), "%d/%m/%Y").date()
        expiry = datetime.strptime(_date(c[15], ordinal=ordinal, population="listed", field="expiry date"), "%d/%m/%Y").date()
        if expiry < listing:
            observed[ordinal] = (c[0], c[14], c[15], c[16])
    if observed != _LISTED_REVIEWED_DATE_INVERSION:
        raise RuntimeError(
            f"Padova listed reviewed chronology-inversion population drift: {observed!r}"
        )


def parse_padova_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(cfg, source_key="padova-listed", population_scope="listed", sha256=_LISTED_SHA256)
    if _sha256(path) != _LISTED_SHA256:
        raise RuntimeError("Padova listed source bytes drift from approved SHA-256")

    rows = _physical_rows(
        path,
        pages=_LISTED_PAGES,
        expected_records=_EXPECTED_LISTED_RECORDS,
        population="listed",
    )
    if any(not row["cells"][0] for row in rows):
        raise RuntimeError("Padova listed contains an unreviewed blank company name")
    _validate_listed_chronology(rows)

    update_count = sum(row["cells"][16] == _UPDATE_NOTE for row in rows)
    nonblank_other_note_count = sum(bool(row["cells"][16]) and row["cells"][16] != _UPDATE_NOTE for row in rows)
    if update_count != 250 or nonblank_other_note_count != 5:
        raise RuntimeError(
            "Padova listed note-population drift: "
            f"updates={update_count!r}; other_nonblank={nonblank_other_note_count!r}"
        )

    id_coverage: Counter[int] = Counter()
    records: list[dict[str, Any]] = []
    for ordinal, row in enumerate(rows, start=1):
        c = row["cells"]
        name, office, secondary, identifier_raw = c[:4]
        sections = _sections(c, ordinal=ordinal, population="listed")
        listing_date = _date(c[14], ordinal=ordinal, population="listed", field="listing date")
        expiry_date = _listed_expiry(
            c[15],
            ordinal=ordinal,
            company=name,
            identifier_raw=identifier_raw,
            listing_raw=c[14],
        )
        status = "renewal_update_in_progress" if c[16] == _UPDATE_NOTE else "listed"
        identifiers = _strict_identifiers(identifier_raw)
        id_coverage[len(identifiers)] += 1

        record = _record(
            cfg,
            ordinal,
            name=name,
            office=office,
            secondary=secondary,
            identifier_raw=identifier_raw,
            activities=sections,
            status=status,
            outcome_raw=c[16],
            listing_date=listing_date,
            expiry_date=expiry_date,
            primary_date_label="Data iscrizione",
            source_fields={
                "sections": sections,
                "section_cells_raw": c[4:14],
                "listing_date_raw": c[14],
                "expiry_date_raw": c[15],
                "note_raw": c[16],
                "source_page": row["page"],
                "source_table_row": row["row"],
            },
        )
        record["identifiers"] = identifiers
        records.append(record)

    status_counts = dict(Counter(record["source_status"] for record in records))
    if status_counts != _EXPECTED_LISTED_STATUS_COUNTS:
        raise RuntimeError(f"Padova listed status drift: {status_counts!r}")
    if dict(id_coverage) != _EXPECTED_LISTED_IDENTIFIER_COUNTS:
        raise RuntimeError(f"Padova listed strict-identifier coverage drift: {dict(id_coverage)!r}")

    return ParsedBatch(
        records=records,
        diagnostics={
            "parser": "padova_listed",
            "parser_version": PARSER_VERSION,
            "source_pages": _LISTED_PAGES,
            "public_records": len(records),
            "status_counts": status_counts,
            "strict_identifier_count_distribution": dict(id_coverage),
            "reviewed_noncalendar_expiries": len(_LISTED_NONCALENDAR_EXPIRY),
            "reviewed_date_inversions": len(_LISTED_REVIEWED_DATE_INVERSION),
            "update_note_rows": update_count,
            "other_nonblank_note_rows": nonblank_other_note_count,
        },
    )


def parse_padova_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(cfg, source_key="padova-applicants", population_scope="applicant", sha256=_APPLICANT_SHA256)
    if _sha256(path) != _APPLICANT_SHA256:
        raise RuntimeError("Padova applicant source bytes drift from approved SHA-256")

    rows = _physical_rows(
        path,
        pages=_APPLICANT_PAGES,
        expected_records=_EXPECTED_APPLICANT_RECORDS,
        population="applicants",
    )
    _recover_applicant_names(rows)

    left, right = _APPLICANT_REVIEWED_DUPLICATE
    left_row = tuple(rows[left - 1]["cells"])
    right_row = tuple(rows[right - 1]["cells"])
    if left_row != _EXPECTED_DUPLICATE_ROW or right_row != _EXPECTED_DUPLICATE_ROW:
        raise RuntimeError(
            f"Padova applicant reviewed duplicate-row drift at {left}/{right}: "
            f"{left_row!r} / {right_row!r}"
        )

    id_coverage: Counter[int] = Counter()
    note_counts = Counter(row["cells"][16] for row in rows)
    if note_counts[""] != 172 or sum(count for note, count in note_counts.items() if note) != 2:
        raise RuntimeError(f"Padova applicant note-population drift: {dict(note_counts)!r}")

    records: list[dict[str, Any]] = []
    for ordinal, row in enumerate(rows, start=1):
        c = row["cells"]
        name, office, secondary, identifier_raw = c[:4]
        if not name:
            raise RuntimeError(f"Padova applicant blank company name after reviewed recovery at ordinal {ordinal}")
        sections = _sections(c, ordinal=ordinal, population="applicants")
        application_date = _date(c[14], ordinal=ordinal, population="applicants", field="application date")
        if not _PROTOCOL.fullmatch(c[15]):
            raise RuntimeError(
                f"Padova applicant protocol typography drift at ordinal {ordinal}: {c[15]!r}"
            )
        identifiers = _strict_identifiers(identifier_raw)
        id_coverage[len(identifiers)] += 1

        record = _record(
            cfg,
            ordinal,
            name=name,
            office=office,
            secondary=secondary,
            identifier_raw=identifier_raw,
            activities=sections,
            status="pending",
            outcome_raw=c[16],
            application_date=application_date,
            primary_date_label="Data presentazione istanza",
            source_fields={
                "sections": sections,
                "section_cells_raw": c[4:14],
                "application_date_raw": c[14],
                "protocol_raw": c[15],
                "note_raw": c[16],
                "source_page": row["page"],
                "source_table_row": row["row"],
                "reviewed_name_recovery": ordinal in _APPLICANT_NAME_RECOVERY,
                "reviewed_source_duplicate": ordinal in _APPLICANT_REVIEWED_DUPLICATE,
            },
        )
        record["identifiers"] = identifiers
        records.append(record)

    status_counts = dict(Counter(record["source_status"] for record in records))
    if status_counts != _EXPECTED_APPLICANT_STATUS_COUNTS:
        raise RuntimeError(f"Padova applicant status drift: {status_counts!r}")
    if dict(id_coverage) != _EXPECTED_APPLICANT_IDENTIFIER_COUNTS:
        raise RuntimeError(f"Padova applicant strict-identifier coverage drift: {dict(id_coverage)!r}")

    return ParsedBatch(
        records=records,
        diagnostics={
            "parser": "padova_applicants",
            "parser_version": PARSER_VERSION,
            "source_pages": _APPLICANT_PAGES,
            "public_records": len(records),
            "status_counts": status_counts,
            "strict_identifier_count_distribution": dict(id_coverage),
            "reviewed_name_recoveries": len(_APPLICANT_NAME_RECOVERY),
            "reviewed_duplicate_source_rows": len(_APPLICANT_REVIEWED_DUPLICATE),
            "nonblank_note_rows": 2,
        },
    )


PARSERS = {
    "padova_listed": parse_padova_listed,
    "padova_applicants": parse_padova_applicants,
}
