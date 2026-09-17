from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import pdfplumber

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _clean, _record

PARSER_VERSION = "1"
_REFERENCE_DATE = "2026-09-16"
_DMY = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")
_UPDATE = re.compile(r"(?:aggiornamento|rinnovo)\s+in\s+corso", re.I)

_SOURCE_EXPECTATIONS: dict[str, dict[str, Any]] = {
    "modena-provincial-listed": {
        "population": "listed",
        "sha256": "84f7ffa41f8e14b7cb1b3f5817d46e20c721b43a1a77280955999be331f2380a",
        "pages": 225,
        "physical_rows": 2174,
        "public_records": 1181,
        "status_counts": {"listed": 634, "renewal_update_in_progress": 547},
        "identifier_counts": {0: 12, 1: 1169},
        "section_count": 10,
        "reviewed_malformed_date_rows": 1,
        "field_variation_groups": 1,
    },
    "modena-provincial-applicants": {
        "population": "applicant",
        "sha256": "323c1dace295b50f4baff85545879be920dc05ef9072f34b4d98449acf11f79f",
        "pages": 88,
        "physical_rows": 803,
        "public_records": 502,
        "status_counts": {"pending": 502},
        "identifier_counts": {0: 4, 1: 498},
        "section_count": 10,
        "reviewed_malformed_date_rows": 0,
        "field_variation_groups": 0,
    },
    "modena-post-sisma-listed": {
        "population": "listed",
        "sha256": "658e24f8342c04dc8c16dba8d4e3660c16fbff89722507a30dfba1d9a43274d0",
        "pages": 274,
        "physical_rows": 2927,
        "public_records": 1679,
        "status_counts": {"listed": 926, "renewal_update_in_progress": 753},
        "identifier_counts": {0: 19, 1: 1660},
        "section_count": 7,
        "reviewed_malformed_date_rows": 3,
        "field_variation_groups": 6,
    },
    "modena-post-sisma-applicants": {
        "population": "applicant",
        "sha256": "e21f47c956dd355fc2400ef110916349632ad6f31eb7878c99a3d05834eb5bf1",
        "pages": 40,
        "physical_rows": 432,
        "public_records": 430,
        "status_counts": {"pending": 430},
        "identifier_counts": {0: 6, 1: 424},
        "section_count": 1,
        "reviewed_malformed_date_rows": 0,
        "field_variation_groups": 0,
    },
}

_REVIEWED_MALFORMED_DATE_ROWS: dict[str, dict[tuple[int, int, int], tuple[str, ...]]] = {
    "modena-provincial-listed": {
        (154, 1, 11): (
            "EDIL GP LA MODENESE SRL",
            "MODENA",
            "03807930361",
            "02/10/20218",
            "Prot n° 73579/2024 del 01/09/2022 emesso dal Prefetto di MODENA",
            "31/08/2023",
            "Aggiornamento in corso",
        ),
    },
    "modena-post-sisma-listed": {
        (32, 1, 5): (
            "ARTE E RESTAURO S.R.L.S.",
            "MIRANDOLA (MO)",
            "03903570368",
            "22/10/2024",
            "Prot n° 69452/2024 del 19/08/2026 emesso dal Prefetto di MODENA",
            "18/008/2027",
            "-",
        ),
        (62, 1, 4): (
            "EDIL GP LA MODENESE SRL",
            "MODENA",
            "03807930361",
            "02/10/20218",
            "Prot n° 73579/2024 del 01/09/2022 emesso dal Prefetto di MODENA",
            "31/08/2023",
            "Aggiornamento in corso",
        ),
        (144, 1, 4): (
            "EDIL GP LA MODENESE SRL",
            "MODENA",
            "03807930361",
            "02/10/20218",
            "Prot n° 73579/2024 del 01/09/2022 emesso dal Prefetto di MODENA",
            "31/08/2023",
            "Aggiornamento in corso",
        ),
    },
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _valid_date(raw: str, *, context: str) -> str:
    value = _clean(raw)
    if not _DMY.fullmatch(value):
        raise RuntimeError(f"Modena {context} unreviewed date typography: {value!r}")
    try:
        datetime.strptime(value, "%d/%m/%Y")
    except ValueError as exc:
        raise RuntimeError(f"Modena {context} invalid calendar date: {value!r}") from exc
    return value


def _validate_cfg(cfg: dict[str, Any], *, population: str) -> dict[str, Any]:
    source_key = str(cfg.get("source_key") or "")
    expected = _SOURCE_EXPECTATIONS.get(source_key)
    if expected is None:
        raise RuntimeError(f"Unapproved Modena source key: {source_key!r}")
    if cfg.get("authority_key") != "modena":
        raise RuntimeError("Modena parser bound to a non-Modena authority")
    if cfg.get("population_scope") != population or expected["population"] != population:
        raise RuntimeError(f"Modena population-scope drift for {source_key}")
    if cfg.get("reference_date") != _REFERENCE_DATE:
        raise RuntimeError(
            f"Modena reference-date drift for {source_key}: {cfg.get('reference_date')!r} != {_REFERENCE_DATE!r}"
        )
    if cfg.get("sha256") != expected["sha256"]:
        raise RuntimeError(f"Modena configured SHA-256 drift for {source_key}")
    if int(cfg.get("expected_source_rows", -1)) != expected["public_records"]:
        raise RuntimeError(f"Modena configured public denominator drift for {source_key}")
    if int(cfg.get("expected_sector_rows", -1)) != expected["physical_rows"]:
        raise RuntimeError(f"Modena configured physical-row denominator drift for {source_key}")
    return expected


def _page_section(page: pdfplumber.page.Page, source_key: str) -> str:
    lines = [_clean(line) for line in (page.extract_text() or "").splitlines() if _clean(line)]
    if source_key.startswith("modena-provincial-"):
        section_index = next(
            (index for index, line in enumerate(lines) if re.fullmatch(r"Sezione\s+[IVX]+", line, re.I)),
            None,
        )
        if section_index is None:
            raise RuntimeError(f"Modena provincial section heading missing on page {page.page_number}")
        title: list[str] = []
        for line in lines[section_index + 1 :]:
            if line.startswith("Sede Legale") or line.startswith("Codice Fiscale") or line.startswith("Ragione Sociale"):
                break
            title.append(line)
        if not title:
            raise RuntimeError(f"Modena provincial activity heading missing on page {page.page_number}")
        return f"{lines[section_index]} | {' '.join(title)}"
    if source_key == "modena-post-sisma-applicants":
        if not any(line == "ULTERIORI SETTORI" for line in lines):
            raise RuntimeError(f"Modena post-sisma applicant heading missing on page {page.page_number}")
        return "ULTERIORI SETTORI"

    marker = next(
        (index for index, line in enumerate(lines) if "ulteriori settori individuati" in line.casefold()),
        None,
    )
    if marker is None:
        raise RuntimeError(f"Modena post-sisma legal heading missing on page {page.page_number}")
    title: list[str] = []
    for line in lines[marker + 1 :]:
        if line.startswith("Sede Legale") or line.startswith("Codice Fiscale") or line.startswith("Ragione Sociale"):
            break
        title.append(line)
    if not title:
        raise RuntimeError(f"Modena post-sisma activity heading missing on page {page.page_number}")
    return " ".join(title)


def _physical_rows(path: Path, cfg: dict[str, Any], *, population: str) -> list[dict[str, Any]]:
    expected = _validate_cfg(cfg, population=population)
    actual_sha = _sha256(path)
    if actual_sha != expected["sha256"]:
        raise RuntimeError(
            f"Modena current-source byte drift for {cfg['source_key']}: {actual_sha} != {expected['sha256']}"
        )

    listed = population == "listed"
    reviewed = _REVIEWED_MALFORMED_DATE_ROWS.get(cfg["source_key"], {})
    seen_reviewed: set[tuple[int, int, int]] = set()
    rows: list[dict[str, Any]] = []
    encountered_sections: list[str] = []
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != expected["pages"]:
            raise RuntimeError(
                f"Modena page-count drift for {cfg['source_key']}: {len(pdf.pages)} != {expected['pages']}"
            )
        for page in pdf.pages:
            section = _page_section(page, cfg["source_key"])
            if section not in encountered_sections:
                encountered_sections.append(section)
            tables = page.extract_tables()
            if listed and len(tables) != 1:
                raise RuntimeError(
                    f"Modena listed table-count drift on page {page.page_number}: {len(tables)} != 1"
                )
            if not tables:
                raise RuntimeError(f"Modena table missing on page {page.page_number}")
            page_data_rows = 0
            for table_number, table in enumerate(tables, start=1):
                for table_row, raw in enumerate(table, start=1):
                    cells = [_clean(value) for value in (raw or [])]
                    if not any(cells):
                        continue
                    expected_width = 7 if listed else 5
                    if len(cells) != expected_width:
                        if not listed and len(cells) == 1:
                            continue
                        raise RuntimeError(
                            f"Modena table-width drift {cfg['source_key']} p{page.page_number} "
                            f"t{table_number} r{table_row}: {len(cells)} != {expected_width}"
                        )
                    locator = (page.page_number, table_number, table_row)
                    reviewed_cells = reviewed.get(locator)
                    normal_data = (
                        _DMY.fullmatch(cells[3]) is not None
                        and (not listed or _DMY.fullmatch(cells[5]) is not None)
                    )
                    if reviewed_cells is not None:
                        if tuple(cells) != reviewed_cells:
                            raise RuntimeError(
                                f"Modena reviewed malformed-date row drift at {cfg['source_key']} {locator}: "
                                f"{tuple(cells)!r} != {reviewed_cells!r}"
                            )
                        seen_reviewed.add(locator)
                        is_data = True
                    else:
                        is_data = normal_data
                    if not is_data:
                        if any(_DMY.fullmatch(value) for value in cells):
                            raise RuntimeError(
                                f"Modena unreviewed date-bearing non-data row at {cfg['source_key']} {locator}: {cells!r}"
                            )
                        continue
                    if not cells[0] or not cells[2]:
                        raise RuntimeError(
                            f"Modena data row lost name/identifier at {cfg['source_key']} "
                            f"p{page.page_number} t{table_number} r{table_row}"
                        )
                    if reviewed_cells is None:
                        _valid_date(cells[3], context=f"{cfg['source_key']} application/listing")
                        if listed:
                            _valid_date(cells[5], context=f"{cfg['source_key']} expiry")
                    else:
                        for index in ([3, 5] if listed else [3]):
                            if _DMY.fullmatch(cells[index]):
                                _valid_date(cells[index], context=f"{cfg['source_key']} reviewed row")
                    rows.append(
                        {
                            "page": page.page_number,
                            "table": table_number,
                            "table_row": table_row,
                            "section": section,
                            "cells": cells,
                        }
                    )
                    page_data_rows += 1
            if page_data_rows == 0:
                raise RuntimeError(f"Modena source page without data rows: {cfg['source_key']} p{page.page_number}")

    if seen_reviewed != set(reviewed):
        raise RuntimeError(
            f"Modena reviewed malformed-date locator drift for {cfg['source_key']}: "
            f"seen={sorted(seen_reviewed)!r} expected={sorted(reviewed)!r}"
        )
    if len(rows) != expected["physical_rows"]:
        raise RuntimeError(
            f"Modena physical-row denominator drift for {cfg['source_key']}: "
            f"{len(rows)} != {expected['physical_rows']}"
        )
    if len(encountered_sections) != expected["section_count"]:
        raise RuntimeError(
            f"Modena source-section denominator drift for {cfg['source_key']}: "
            f"{len(encountered_sections)} != {expected['section_count']}"
        )
    return rows


def _listed_key(row: dict[str, Any]) -> tuple[str, str, str, str, str]:
    cells = row["cells"]
    return cells[0], cells[2], cells[3], cells[5], cells[6].casefold()


def _applicant_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    cells = row["cells"]
    return cells[0], cells[2], cells[3], cells[4].casefold()


def _group(rows: list[dict[str, Any]], *, population: str) -> list[list[dict[str, Any]]]:
    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = _listed_key(row) if population == "listed" else _applicant_key(row)
        grouped[key].append(row)
    return list(grouped.values())


def _unique(values: list[str]) -> list[str]:
    out: list[str] = []
    for value in values:
        value = _clean(value)
        if not value:
            continue
        if value not in out:
            out.append(value)
    return out


def _validate_group_boundary(
    cfg: dict[str, Any],
    expected: dict[str, Any],
    groups: list[list[dict[str, Any]]],
    records: list[dict[str, Any]],
    *,
    population: str,
) -> dict[str, Any]:
    if len(groups) != expected["public_records"] or len(records) != expected["public_records"]:
        raise RuntimeError(
            f"Modena logical observation denominator drift for {cfg['source_key']}: "
            f"groups={len(groups)} records={len(records)} expected={expected['public_records']}"
        )
    status_counts = dict(Counter(record["source_status"] for record in records))
    if status_counts != expected["status_counts"]:
        raise RuntimeError(
            f"Modena status denominator drift for {cfg['source_key']}: "
            f"{status_counts!r} != {expected['status_counts']!r}"
        )
    identifier_counts = dict(Counter(len(record["identifiers"]) for record in records))
    if identifier_counts != expected["identifier_counts"]:
        raise RuntimeError(
            f"Modena identifier evidence drift for {cfg['source_key']}: "
            f"{identifier_counts!r} != {expected['identifier_counts']!r}"
        )
    variation_groups = 0
    for group in groups:
        if population == "listed":
            variants = {(row["cells"][1], row["cells"][4], row["cells"][6]) for row in group}
        else:
            variants = {(row["cells"][1], row["cells"][4]) for row in group}
        variation_groups += len(variants) > 1
    if variation_groups != expected["field_variation_groups"]:
        raise RuntimeError(
            f"Modena reviewed field-variation boundary drift for {cfg['source_key']}: "
            f"{variation_groups} != {expected['field_variation_groups']}"
        )
    return {
        "public_records": len(records),
        "sector_rows": sum(len(group) for group in groups),
        "dropped_date_rows": 0,
        "reviewed_malformed_date_rows": expected["reviewed_malformed_date_rows"],
        "status_counts": status_counts,
        "identifier_count_distribution": identifier_counts,
        "source_section_count": expected["section_count"],
        "reviewed_field_variation_groups": variation_groups,
    }


def parse_modena_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    expected = _validate_cfg(cfg, population="listed")
    rows = _physical_rows(path, cfg, population="listed")
    groups = _group(rows, population="listed")
    records: list[dict[str, Any]] = []
    for ordinal, group in enumerate(groups, start=1):
        first = group[0]
        name, identifier_raw, listing_raw, expiry_raw, note_folded = _listed_key(first)
        sections = _unique([row["section"] for row in group])
        offices = _unique([row["cells"][1] for row in group])
        note_variants = _unique([row["cells"][6] for row in group])
        protocols = _unique([row["cells"][4] for row in group])
        locators = [f"p{row['page']}:t{row['table']}:r{row['table_row']}" for row in group]
        status = "renewal_update_in_progress" if _UPDATE.search(note_folded) else "listed"
        meaningful_notes = [value for value in note_variants if value not in {"-", ""}]
        source_notes = meaningful_notes + [f"Provvedimento: {value}" for value in protocols if value]
        records.append(
            _record(
                cfg,
                ordinal,
                name=name,
                office=offices[0] if offices else "",
                identifier_raw=identifier_raw,
                activities=sections,
                status=status,
                outcome_raw=note_variants[0] if note_variants else "",
                listing_date=listing_raw,
                expiry_date=expiry_raw,
                primary_date_label="Data iscrizione",
                source_fields={
                    "sections": sections,
                    "physical_locators": locators,
                    "registered_office_variants": offices,
                    "listing_date_raw_variants": [listing_raw],
                    "expiry_date_raw_variants": [expiry_raw],
                    "notes": source_notes,
                    "in_aggiornamento": note_variants[0] if status == "renewal_update_in_progress" else "",
                },
            )
        )
    diagnostics = _validate_group_boundary(cfg, expected, groups, records, population="listed")
    return ParsedBatch(records=records, diagnostics=diagnostics)


def parse_modena_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    expected = _validate_cfg(cfg, population="applicant")
    rows = _physical_rows(path, cfg, population="applicant")
    groups = _group(rows, population="applicant")
    records: list[dict[str, Any]] = []
    for ordinal, group in enumerate(groups, start=1):
        first = group[0]
        name, identifier_raw, application_raw, _ = _applicant_key(first)
        sections = _unique([row["section"] for row in group])
        offices = _unique([row["cells"][1] for row in group])
        notes = _unique([row["cells"][4] for row in group])
        locators = [f"p{row['page']}:t{row['table']}:r{row['table_row']}" for row in group]
        records.append(
            _record(
                cfg,
                ordinal,
                name=name,
                office=offices[0] if offices else "",
                identifier_raw=identifier_raw,
                activities=sections,
                status="pending",
                outcome_raw=notes[0] if notes else "Richiedente iscrizione",
                application_date=application_raw,
                primary_date_label="Data presentazione istanza",
                source_fields={
                    "sections": sections,
                    "physical_locators": locators,
                    "registered_office_variants": offices,
                    "application_date_raw_variants": [application_raw],
                    "notes": notes,
                },
            )
        )
    diagnostics = _validate_group_boundary(cfg, expected, groups, records, population="applicant")
    return ParsedBatch(records=records, diagnostics=diagnostics)


PARSERS = {
    "modena_listed": parse_modena_listed,
    "modena_applicants": parse_modena_applicants,
}
