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
_REFERENCE_DATE = "2026-09-08"

_LISTED_SOURCE_KEY = "pisa-listed"
_APPLICANT_SOURCE_KEY = "pisa-applicants"
_RENEWAL_SOURCE_KEY = "pisa-renewal-update"

_LISTED_SHA256 = "30eea93e542aea6ceb13bcfd4e3f1358e1c3f9cfb274b23e738dfb304b1dea23"
_APPLICANT_SHA256 = "ed3bbf19670dbed899f6386836f4723898e4c20f9315e4d4297156fd1dcd6b12"
_RENEWAL_SHA256 = "8658cd2e6048c44de18687b3933980778dd36bbf3721cd944063f61c0e2ceedb"

_LISTED_BYTES = 169257
_APPLICANT_BYTES = 68334
_RENEWAL_BYTES = 73013

_LISTED_PAGES = 6
_APPLICANT_PAGES = 1
_RENEWAL_PAGES = 1
_LISTED_RECORDS = 398
_APPLICANT_RECORDS = 18
_RENEWAL_RECORDS = 33

_LISTED_STATUS_RAW = "ISCRITTA"
_APPLICANT_STATUS_RAW = "RICHIEDENTE_ISCRIZIONE"
_RENEWAL_STATUS_RAW = "IN_AGGIORNAMENTO"

_EXPECTED_LISTED_STATUS_COUNTS = {"listed": 398}
_EXPECTED_APPLICANT_STATUS_COUNTS = {"pending": 18}
_EXPECTED_RENEWAL_STATUS_COUNTS = {"renewal_update_in_progress": 33}
_EXPECTED_LISTED_IDENTIFIER_COVERAGE = 397
_EXPECTED_APPLICANT_IDENTIFIER_COVERAGE = 18
_EXPECTED_RENEWAL_IDENTIFIER_COVERAGE = 33
_REVIEWED_BLANK_LISTED_IDENTIFIER_NAME = "ROHDE NIELSEN A/S"

_DATE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
_STRICT_IDENTIFIER_11 = re.compile(r"^\d{11}$")
_STRICT_IDENTIFIER_16 = re.compile(r"^[A-Z]{6}[0-9A-Z]{10}$")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_cfg(
    cfg: dict[str, Any],
    *,
    source_key: str,
    population_scope: str,
    sha256: str,
) -> None:
    if cfg.get("source_key") != source_key:
        raise RuntimeError(f"Pisa source-key drift: {cfg.get('source_key')!r} != {source_key!r}")
    if cfg.get("authority_key") != "pisa":
        raise RuntimeError("Pisa parser bound to a non-Pisa authority")
    if cfg.get("population_scope") != population_scope:
        raise RuntimeError(
            f"Pisa population-scope drift for {source_key}: "
            f"{cfg.get('population_scope')!r} != {population_scope!r}"
        )
    if cfg.get("reference_date") != _REFERENCE_DATE:
        raise RuntimeError(
            f"Pisa reference-date drift for {source_key}: "
            f"{cfg.get('reference_date')!r} != {_REFERENCE_DATE!r}"
        )
    if cfg.get("sha256") != sha256:
        raise RuntimeError(
            f"Pisa configured SHA-256 drift for {source_key}: {cfg.get('sha256')!r} != {sha256!r}"
        )


def _strict_identifier(raw: str) -> str:
    value = _clean(raw).upper()
    if _STRICT_IDENTIFIER_11.fullmatch(value) or _STRICT_IDENTIFIER_16.fullmatch(value):
        return value
    return ""


def _strict_date(raw: str, *, source_key: str, locator: str) -> str:
    value = _clean(raw)
    if not _DATE.fullmatch(value):
        raise RuntimeError(
            f"Pisa unreviewed date typography for {source_key} at {locator}: {value!r}"
        )
    try:
        return datetime.strptime(value, "%d/%m/%Y").date().isoformat()
    except ValueError as exc:
        raise RuntimeError(
            f"Pisa invalid calendar date for {source_key} at {locator}: {value!r}"
        ) from exc


def _is_header(row: list[str]) -> bool:
    folded = " | ".join(row).casefold()
    return "prefettura competente" in folded and "codice fiscale" in folded


def _sections(raw: str) -> list[str]:
    value = _clean(raw)
    if not value:
        return []
    values = [_clean(item) for item in value.split(",") if _clean(item)]
    if not values:
        raise RuntimeError(f"Pisa nonblank section field could not be preserved: {value!r}")
    return list(dict.fromkeys(values))


def _rows(path: Path, *, pages: int, width: int, expected_records: int, source_key: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    header_count = 0
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != pages:
            raise RuntimeError(f"Pisa page-count drift for {source_key}: {len(pdf.pages)} != {pages}")
        for page_number, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables() or []
            if len(tables) != 1:
                raise RuntimeError(
                    f"Pisa table-count drift for {source_key} page {page_number}: {len(tables)} != 1"
                )
            for row_number, raw in enumerate(tables[0] or [], start=1):
                cells = [_clean(cell) for cell in (raw or [])]
                if not any(cells):
                    continue
                if len(cells) != width:
                    raise RuntimeError(
                        f"Pisa row-width drift for {source_key} p{page_number}:r{row_number}: "
                        f"{len(cells)} != {width}"
                    )
                if _is_header(cells):
                    header_count += 1
                    continue
                if not cells[3]:
                    raise RuntimeError(
                        f"Pisa blank company name for {source_key} p{page_number}:r{row_number}"
                    )
                rows.append(
                    {
                        "cells": cells,
                        "page": page_number,
                        "row": row_number,
                        "locator": f"p{page_number}:r{row_number}",
                    }
                )
    if header_count != pages:
        raise RuntimeError(f"Pisa header-count drift for {source_key}: {header_count} != {pages}")
    if len(rows) != expected_records:
        raise RuntimeError(
            f"Pisa record-count drift for {source_key}: {len(rows)} != {expected_records}"
        )
    return rows


def _validate_file(path: Path, *, source_key: str, sha256: str, byte_count: int) -> None:
    actual_bytes = path.stat().st_size
    if actual_bytes != byte_count:
        raise RuntimeError(
            f"Pisa byte-length drift for {source_key}: {actual_bytes} != {byte_count}"
        )
    actual_sha = _sha256(path)
    if actual_sha != sha256:
        raise RuntimeError(
            f"Pisa byte identity drift for {source_key}: {actual_sha!r} != {sha256!r}"
        )


def _finalise(
    records: list[dict[str, Any]],
    *,
    source_key: str,
    expected_status_counts: dict[str, int],
    expected_identifier_coverage: int,
) -> ParsedBatch:
    status_counts = dict(Counter(record["source_status"] for record in records))
    if status_counts != expected_status_counts:
        raise RuntimeError(
            f"Pisa status-count drift for {source_key}: {status_counts!r} != {expected_status_counts!r}"
        )
    identifier_coverage = sum(bool(record["identifiers"]) for record in records)
    if identifier_coverage != expected_identifier_coverage:
        raise RuntimeError(
            f"Pisa identifier-coverage drift for {source_key}: "
            f"{identifier_coverage} != {expected_identifier_coverage}"
        )
    identifiers = [identifier for record in records for identifier in record["identifiers"]]
    duplicates = {value: count for value, count in Counter(identifiers).items() if count > 1}
    if duplicates:
        raise RuntimeError(f"Pisa duplicate strict identifiers within {source_key}: {duplicates!r}")
    return ParsedBatch(
        records=records,
        diagnostics={
            "parser": source_key,
            "parser_version": PARSER_VERSION,
            "source_rows": len(records),
            "public_records": len(records),
            "status_counts": status_counts,
            "identifier_coverage": identifier_coverage,
        },
    )


def parse_pisa_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(cfg, source_key=_LISTED_SOURCE_KEY, population_scope="listed", sha256=_LISTED_SHA256)
    _validate_file(path, source_key=_LISTED_SOURCE_KEY, sha256=_LISTED_SHA256, byte_count=_LISTED_BYTES)
    rows = _rows(
        path,
        pages=_LISTED_PAGES,
        width=10,
        expected_records=_LISTED_RECORDS,
        source_key=_LISTED_SOURCE_KEY,
    )
    records: list[dict[str, Any]] = []
    blank_identifier_names: list[str] = []
    for ordinal, item in enumerate(rows, start=1):
        cells = item["cells"]
        if cells[6] != _LISTED_STATUS_RAW:
            raise RuntimeError(
                f"Pisa unreviewed listed status at {item['locator']}: {cells[6]!r}"
            )
        application_date = _strict_date(cells[1], source_key=_LISTED_SOURCE_KEY, locator=item["locator"])
        listing_date = _strict_date(cells[8], source_key=_LISTED_SOURCE_KEY, locator=item["locator"])
        expiry_date = _strict_date(cells[9], source_key=_LISTED_SOURCE_KEY, locator=item["locator"])
        identifier = _strict_identifier(cells[2])
        if not identifier:
            if cells[2]:
                raise RuntimeError(
                    f"Pisa unreviewed malformed listed identifier at {item['locator']}: {cells[2]!r}"
                )
            blank_identifier_names.append(cells[3])
        sections = _sections(cells[5])
        record = _record(
            cfg,
            ordinal,
            name=cells[3],
            office=cells[4],
            identifier_raw=cells[2],
            activities=sections,
            status="listed",
            application_date=application_date,
            listing_date=listing_date,
            expiry_date=expiry_date,
            primary_date_label="Data iscrizione",
            source_fields={
                "sections": sections,
                "requested_activities_source": cells[5],
                "application_date_raw_variants": [cells[1]],
                "listing_date_raw_variants": [cells[8]],
                "expiry_date_raw_variants": [cells[9]],
            },
        )
        record["identifiers"] = [identifier] if identifier else []
        records.append(record)
    if blank_identifier_names != [_REVIEWED_BLANK_LISTED_IDENTIFIER_NAME]:
        raise RuntimeError(
            f"Pisa reviewed blank listed-identifier drift: {blank_identifier_names!r}"
        )
    return _finalise(
        records,
        source_key=_LISTED_SOURCE_KEY,
        expected_status_counts=_EXPECTED_LISTED_STATUS_COUNTS,
        expected_identifier_coverage=_EXPECTED_LISTED_IDENTIFIER_COVERAGE,
    )


def parse_pisa_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(cfg, source_key=_APPLICANT_SOURCE_KEY, population_scope="applicant", sha256=_APPLICANT_SHA256)
    _validate_file(path, source_key=_APPLICANT_SOURCE_KEY, sha256=_APPLICANT_SHA256, byte_count=_APPLICANT_BYTES)
    rows = _rows(
        path,
        pages=_APPLICANT_PAGES,
        width=7,
        expected_records=_APPLICANT_RECORDS,
        source_key=_APPLICANT_SOURCE_KEY,
    )
    records: list[dict[str, Any]] = []
    for ordinal, item in enumerate(rows, start=1):
        cells = item["cells"]
        if cells[6] != _APPLICANT_STATUS_RAW:
            raise RuntimeError(
                f"Pisa unreviewed applicant status at {item['locator']}: {cells[6]!r}"
            )
        identifier = _strict_identifier(cells[2])
        if not identifier:
            raise RuntimeError(
                f"Pisa missing/malformed applicant identifier at {item['locator']}: {cells[2]!r}"
            )
        application_date = _strict_date(cells[1], source_key=_APPLICANT_SOURCE_KEY, locator=item["locator"])
        sections = _sections(cells[5])
        record = _record(
            cfg,
            ordinal,
            name=cells[3],
            office=cells[4],
            identifier_raw=cells[2],
            activities=sections,
            status="pending",
            application_date=application_date,
            primary_date_label="Data presentazione istanza",
            source_fields={
                "sections": sections,
                "requested_activities_source": cells[5],
                "application_date_raw_variants": [cells[1]],
            },
        )
        record["identifiers"] = [identifier]
        records.append(record)
    return _finalise(
        records,
        source_key=_APPLICANT_SOURCE_KEY,
        expected_status_counts=_EXPECTED_APPLICANT_STATUS_COUNTS,
        expected_identifier_coverage=_EXPECTED_APPLICANT_IDENTIFIER_COVERAGE,
    )


def parse_pisa_renewal_update(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(cfg, source_key=_RENEWAL_SOURCE_KEY, population_scope="listed", sha256=_RENEWAL_SHA256)
    _validate_file(path, source_key=_RENEWAL_SOURCE_KEY, sha256=_RENEWAL_SHA256, byte_count=_RENEWAL_BYTES)
    rows = _rows(
        path,
        pages=_RENEWAL_PAGES,
        width=8,
        expected_records=_RENEWAL_RECORDS,
        source_key=_RENEWAL_SOURCE_KEY,
    )
    records: list[dict[str, Any]] = []
    for ordinal, item in enumerate(rows, start=1):
        cells = item["cells"]
        if cells[6] != _RENEWAL_STATUS_RAW:
            raise RuntimeError(
                f"Pisa unreviewed renewal/update status at {item['locator']}: {cells[6]!r}"
            )
        identifier = _strict_identifier(cells[2])
        if not identifier:
            raise RuntimeError(
                f"Pisa missing/malformed renewal/update identifier at {item['locator']}: {cells[2]!r}"
            )
        application_date = _strict_date(cells[1], source_key=_RENEWAL_SOURCE_KEY, locator=item["locator"])
        sections = _sections(cells[5])
        record = _record(
            cfg,
            ordinal,
            name=cells[3],
            office=cells[4],
            identifier_raw=cells[2],
            activities=sections,
            status="renewal_update_in_progress",
            application_date=application_date,
            primary_date_label="Data presentazione istanza",
            source_fields={
                "sections": sections,
                "requested_activities_source": cells[5],
                "application_date_raw_variants": [cells[1]],
                "in_aggiornamento": cells[6],
            },
        )
        record["identifiers"] = [identifier]
        records.append(record)
    return _finalise(
        records,
        source_key=_RENEWAL_SOURCE_KEY,
        expected_status_counts=_EXPECTED_RENEWAL_STATUS_COUNTS,
        expected_identifier_coverage=_EXPECTED_RENEWAL_IDENTIFIER_COVERAGE,
    )


PARSERS = {
    "pisa_listed": parse_pisa_listed,
    "pisa_applicants": parse_pisa_applicants,
    "pisa_renewal_update": parse_pisa_renewal_update,
}
