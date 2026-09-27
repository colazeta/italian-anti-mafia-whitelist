from __future__ import annotations

import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _clean, _record

PARSER_VERSION = "1"
_LISTED_SOURCE_KEY = "pescara-listed"
_APPLICANT_SOURCE_KEY = "pescara-applicants"
_LISTED_REFERENCE_DATE = "2026-09-16"
_APPLICANT_REFERENCE_DATE = "2026-09-04"
_EXPECTED_SECTION_LABELS = (
    "SEZIONE IESTRAZIONE, FORNITURA E TRASPORTO DI TERRA E MATERIALI INERTI",
    "SEZIONE IICONFEZIONAMENTO, FORNITURA E TRASPORTO DI CALCESTRUZZO E DI BITUME",
    "SEZIONE IIINOLI A FREDDO DI MACCHINARI",
    "SEZIONE IVFORNITURA DI FERRO LAVORATO",
    "SEZIONE VNOLI A CALDO",
    "SEZIONE VIAUTOTRASPORTI PER CONTO DI TERZI",
    "SEZIONE VIIGUARDIANIA AI CANTIERI",
    "SEZIONE VIIISERVIZI FUNERARI E CIMITERIALI",
    "SEZIONE IXRISTORAZIONE, GESTIONE DELLE MENSE E CATERING",
    "SEZIONE XSERVIZI AMBIENTALI, COMPRESE LE ATTIVITÀ DI RACCOLTA, DI TRASPORTO NAZIONALE E TRANSFRONTALIERO, ANCHE PER CONTO DI TERZI, DI TRATTAMENTO E DI SMALTIMENTO DEI RIFIUTI, NONCHÉ LE ATTIVITÀ DI RISANAMENTO E DI BONIFICA E GLI ALTRI SERVIZI CONNESSI ALLA GESTIONE DEI RIFIUTI",
)
_EXPECTED_LISTED_TABLE_GROUPS = 13
_EXPECTED_LISTED_SECTOR_ROWS = 1060
_EXPECTED_LISTED_RECORDS = 607
_EXPECTED_LISTED_SECTION_MEMBERSHIPS = 1058
_EXPECTED_LISTED_DUPLICATE_MEMBERSHIPS = 2
_EXPECTED_LISTED_STATUS_COUNTS = Counter({
    "listed": 456,
    "renewal_update_in_progress": 150,
    "other_or_unknown": 1,
})
_EXPECTED_LISTED_IDENTIFIER_COVERAGE = 579
_EXPECTED_LISTED_MALFORMED_IDENTIFIERS = Counter({
    "1412620682": 1,
    "0655575210": 4,
    "022094180682": 1,
    "023356290685": 3,
    "0228450685": 1,
    "0205262685": 1,
    "0235389060": 1,
    "0231100687": 1,
    "0245080862": 1,
    "019280609688": 1,
    "0141830683": 1,
    "0205890693": 1,
    "0164300689": 1,
    "016443890682": 1,
    "0511970681": 1,
    "0170880682": 1,
    "0135770680": 1,
    "017854909663": 1,
    "0925750689": 1,
    "0185430682": 1,
    "0209740685": 1,
    "0207900682": 1,
    "0224970685": 1,
})
_EXPECTED_LISTED_MALFORMED_DATES = Counter({
    "21/052024": 1,
    "13/07/20222": 1,
    "23701/2026": 1,
    "09/06/20206": 1,
    "22/12/202": 1,
    "30707/2024": 1,
    "29/10/204": 1,
})
_EXPECTED_LISTED_NONSTANDARD_NOTES = Counter({"I": 1})
_EXPECTED_APPLICANT_TABLE_GROUPS = 2
_EXPECTED_APPLICANT_PHYSICAL_ROWS = 36
_EXPECTED_APPLICANT_RECORDS = 35
_EXPECTED_APPLICANT_IDENTIFIER_COVERAGE = 34
_EXPECTED_APPLICANT_MALFORMED_IDENTIFIERS = Counter({"0285069069": 1})
_EXPECTED_APPLICANT_HEADER = (
    "Ragione Sociale",
    "Sede legale",
    "Sede secondaria con rappresentanza stabile in Italia",
    "Codice fiscale Partita IVA",
    "Attività per cui è richiesta l’iscrizione",
    "Data di presentazione dell’istanza",
)
_REVIEWED_APPLICANT_CONTINUATION_ORDINAL = 6
_REVIEWED_APPLICANT_CONTINUATION_OWNER = "CALISTA IMPIANTI SRL"
_STRICT_IDENTIFIER = re.compile(
    r"(?<![A-Za-z0-9])(?:\d{11}|[A-Za-z]{6}[0-9A-Za-z]{10})(?![A-Za-z0-9])"
)
_DATE_TOKEN = re.compile(r"^(\d{1,2})\s*([/.])\s*(\d{1,2})\s*\2\s*(\d{4})$")


def _validate_cfg(cfg: dict[str, Any], *, source_key: str, reference_date: str) -> None:
    if cfg.get("source_key") != source_key:
        raise RuntimeError(f"Pescara parser/source mismatch: {cfg.get('source_key')!r} != {source_key!r}")
    if cfg.get("authority_key") != "pescara":
        raise RuntimeError("Pescara parser bound to a non-Pescara authority")
    if cfg.get("reference_date") != reference_date:
        raise RuntimeError(
            f"{source_key}: reference-date drift: {cfg.get('reference_date')!r} != {reference_date!r}"
        )


def _antiword_docbook(path: Path) -> ET.Element:
    executable = shutil.which("antiword")
    if executable is None:
        raise RuntimeError("antiword is required to parse the reviewed Pescara legacy Word sources")
    process = subprocess.run(
        [executable, "-x", "db", str(path)],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if process.returncode:
        raise RuntimeError(
            f"antiword failed for Pescara source {path.name}: "
            f"{process.stderr.decode('utf-8', 'replace').strip()}"
        )
    docbook = process.stdout.decode("utf-8", "replace")
    xml = re.sub(r'<!DOCTYPE book PUBLIC.*?docbookx\.dtd">\s*', "", docbook, flags=re.S)
    try:
        return ET.fromstring(xml)
    except ET.ParseError as exc:
        raise RuntimeError(f"Pescara antiword DocBook XML drift: {exc}") from exc


def _strict_identifiers(value: str) -> list[str]:
    return list(dict.fromkeys(match.group(0).upper() for match in _STRICT_IDENTIFIER.finditer(_clean(value))))


def _reviewed_date(raw: str, *, malformed: Counter[str], observed: Counter[str]) -> str:
    value = _clean(raw)
    if not value:
        return ""
    match = _DATE_TOKEN.fullmatch(value)
    if match is not None:
        day = int(match.group(1))
        month = int(match.group(3))
        year = int(match.group(4))
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            pass
    if value not in malformed:
        raise RuntimeError(f"Pescara unreviewed malformed source date: {value!r}")
    observed[value] += 1
    return ""


def _is_header(cells: list[str]) -> bool:
    return bool(cells) and cells[0].casefold().startswith("ragione sociale")


def _listed_rows(root: ET.Element) -> tuple[list[tuple[str, list[str], str]], int, tuple[str, ...]]:
    chapters = [chapter for chapter in root.findall(".//chapter") if chapter.findall(".//informaltable")]
    if len(chapters) != 1:
        raise RuntimeError(f"Pescara listed: expected one table-bearing chapter, got {len(chapters)}")
    current_section = ""
    labels: list[str] = []
    rows: list[tuple[str, list[str], str]] = []
    table_groups = 0
    for para_number, para in enumerate(chapters[0].findall("./para"), start=1):
        table = para.find(".//informaltable")
        if table is None:
            text = _clean("".join(para.itertext()))
            if text.upper().startswith("SEZIONE"):
                current_section = text
                labels.append(text)
            continue
        if not current_section:
            raise RuntimeError(f"Pescara listed table before section heading at paragraph {para_number}")
        for group_number, group in enumerate(table.findall(".//tgroup"), start=1):
            table_groups += 1
            if group.get("cols") != "7":
                raise RuntimeError(f"Pescara listed column-count drift: {group.get('cols')!r}")
            for row_number, row in enumerate(group.findall(".//row"), start=1):
                cells = [_clean("".join(entry.itertext())) for entry in row.findall("./entry")]
                if not any(cells) or _is_header(cells):
                    continue
                if len(cells) != 7:
                    raise RuntimeError(f"Pescara listed row-width drift: {len(cells)}")
                if not cells[0]:
                    raise RuntimeError(
                        f"Pescara listed blank company name at paragraph {para_number}, group {group_number}, row {row_number}"
                    )
                rows.append((current_section, cells, f"p{para_number}:t{group_number}:r{row_number}"))
    labels_tuple = tuple(labels)
    if labels_tuple != _EXPECTED_SECTION_LABELS:
        raise RuntimeError(f"Pescara listed section-heading drift: {labels_tuple!r}")
    if table_groups != _EXPECTED_LISTED_TABLE_GROUPS:
        raise RuntimeError(
            f"Pescara listed table-group drift: {table_groups} != {_EXPECTED_LISTED_TABLE_GROUPS}"
        )
    if len(rows) != _EXPECTED_LISTED_SECTOR_ROWS:
        raise RuntimeError(
            f"Pescara listed sector-row drift: {len(rows)} != {_EXPECTED_LISTED_SECTOR_ROWS}"
        )
    return rows, table_groups, labels_tuple


def _listed_status(note: str) -> str:
    value = _clean(note)
    if not value:
        return "listed"
    if value.casefold() == "in rinnovo":
        return "renewal_update_in_progress"
    if value == "I":
        return "other_or_unknown"
    raise RuntimeError(f"Pescara listed unreviewed status note: {value!r}")


def parse_pescara_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(cfg, source_key=_LISTED_SOURCE_KEY, reference_date=_LISTED_REFERENCE_DATE)
    sector_rows, table_groups, labels = _listed_rows(_antiword_docbook(path))
    grouped: dict[tuple[str, ...], dict[str, Any]] = {}
    duplicate_memberships = 0
    for section, cells, locator in sector_rows:
        key = tuple(cells)
        group = grouped.setdefault(key, {"cells": cells, "sections": [], "physical_locators": []})
        group["physical_locators"].append(locator)
        if section in group["sections"]:
            duplicate_memberships += 1
        else:
            group["sections"].append(section)
    if len(grouped) != _EXPECTED_LISTED_RECORDS:
        raise RuntimeError(
            f"Pescara listed observation drift: {len(grouped)} != {_EXPECTED_LISTED_RECORDS}"
        )
    section_memberships = sum(len(group["sections"]) for group in grouped.values())
    if section_memberships != _EXPECTED_LISTED_SECTION_MEMBERSHIPS:
        raise RuntimeError(
            "Pescara listed section-membership drift: "
            f"{section_memberships} != {_EXPECTED_LISTED_SECTION_MEMBERSHIPS}"
        )
    if duplicate_memberships != _EXPECTED_LISTED_DUPLICATE_MEMBERSHIPS:
        raise RuntimeError(
            f"Pescara listed reviewed duplicate-membership drift: {duplicate_memberships} "
            f"!= {_EXPECTED_LISTED_DUPLICATE_MEMBERSHIPS}"
        )

    malformed_dates = Counter()
    malformed_identifiers = Counter()
    nonstandard_notes = Counter()
    records: list[dict[str, Any]] = []
    for group in grouped.values():
        cells = group["cells"]
        note = _clean(cells[6])
        status = _listed_status(note)
        if note not in ("", "IN RINNOVO"):
            nonstandard_notes[note] += 1
        listing_date = _reviewed_date(
            cells[4], malformed=_EXPECTED_LISTED_MALFORMED_DATES, observed=malformed_dates
        )
        expiry_date = _reviewed_date(
            cells[5], malformed=_EXPECTED_LISTED_MALFORMED_DATES, observed=malformed_dates
        )
        identifiers = _strict_identifiers(cells[3])
        if cells[3] and not identifiers:
            malformed_identifiers[cells[3]] += 1
        record = _record(
            cfg,
            len(records) + 1,
            name=cells[0],
            office=cells[1],
            secondary=cells[2],
            identifier_raw=cells[3],
            activities=list(group["sections"]),
            status=status,
            outcome_raw=note,
            listing_date=listing_date,
            expiry_date=expiry_date,
            primary_date_label="Data iscrizione",
            source_fields={
                "sections": list(group["sections"]),
                "physical_locators": list(group["physical_locators"]),
                "listing_date_raw_variants": [cells[4]] if cells[4] else [],
                "expiry_date_raw_variants": [cells[5]] if cells[5] else [],
                "in_aggiornamento": note if status == "renewal_update_in_progress" else "",
                "notes": [note] if note and status != "renewal_update_in_progress" else [],
            },
        )
        record["identifiers"] = identifiers
        records.append(record)

    status_counts = Counter(record["source_status"] for record in records)
    identifier_coverage = sum(bool(record["identifiers"]) for record in records)
    if status_counts != _EXPECTED_LISTED_STATUS_COUNTS:
        raise RuntimeError(f"Pescara listed status-count drift: {dict(status_counts)!r}")
    if identifier_coverage != _EXPECTED_LISTED_IDENTIFIER_COVERAGE:
        raise RuntimeError(
            f"Pescara listed identifier-coverage drift: {identifier_coverage} != {_EXPECTED_LISTED_IDENTIFIER_COVERAGE}"
        )
    if malformed_identifiers != _EXPECTED_LISTED_MALFORMED_IDENTIFIERS:
        raise RuntimeError(f"Pescara listed malformed-identifier drift: {dict(malformed_identifiers)!r}")
    if malformed_dates != _EXPECTED_LISTED_MALFORMED_DATES:
        raise RuntimeError(f"Pescara listed malformed-date drift: {dict(malformed_dates)!r}")
    if nonstandard_notes != _EXPECTED_LISTED_NONSTANDARD_NOTES:
        raise RuntimeError(f"Pescara listed nonstandard-note drift: {dict(nonstandard_notes)!r}")

    return ParsedBatch(records, {
        "parser": "pescara_legacy_listed",
        "parser_version": PARSER_VERSION,
        "table_groups": table_groups,
        "section_labels": list(labels),
        "sector_rows": len(sector_rows),
        "section_memberships": section_memberships,
        "duplicate_memberships": duplicate_memberships,
        "public_records": len(records),
        "status_counts": dict(status_counts),
        "identifier_coverage": identifier_coverage,
        "raw_only_identifier_records": sum(malformed_identifiers.values()),
        "reviewed_malformed_dates": sum(malformed_dates.values()),
    })


def _applicant_rows(root: ET.Element) -> tuple[list[list[str]], int, int]:
    rows: list[list[str]] = []
    table_groups = 0
    header_count = 0
    physical_ordinal = 0
    current: list[str] | None = None
    for group in root.findall(".//informaltable//tgroup"):
        table_groups += 1
        if group.get("cols") != "6":
            raise RuntimeError(f"Pescara applicant column-count drift: {group.get('cols')!r}")
        for row in group.findall(".//row"):
            cells = [_clean("".join(entry.itertext())) for entry in row.findall("./entry")]
            if not any(cells):
                continue
            if _is_header(cells):
                header_count += 1
                if tuple(cells) != _EXPECTED_APPLICANT_HEADER:
                    raise RuntimeError(f"Pescara applicant header drift: {cells!r}")
                continue
            if len(cells) != 6:
                raise RuntimeError(f"Pescara applicant row-width drift: {len(cells)}")
            physical_ordinal += 1
            if cells[0]:
                current = list(cells)
                rows.append(current)
                continue
            if physical_ordinal != _REVIEWED_APPLICANT_CONTINUATION_ORDINAL:
                raise RuntimeError(
                    f"Pescara applicant unreviewed blank-name row at physical ordinal {physical_ordinal}: {cells!r}"
                )
            if current is None or current[0] != _REVIEWED_APPLICANT_CONTINUATION_OWNER:
                raise RuntimeError(
                    "Pescara applicant reviewed continuation owner drift: "
                    f"{current and current[0]!r}"
                )
            if cells[:4] != ["", "", "//", ""] or not cells[4] or not cells[5]:
                raise RuntimeError(f"Pescara applicant reviewed continuation shape drift: {cells!r}")
            if current[2] != "//" or current[4] or current[5]:
                raise RuntimeError(f"Pescara applicant continuation target drift: {current!r}")
            current[4] = cells[4]
            current[5] = cells[5]
    if table_groups != _EXPECTED_APPLICANT_TABLE_GROUPS:
        raise RuntimeError(
            f"Pescara applicant table-group drift: {table_groups} != {_EXPECTED_APPLICANT_TABLE_GROUPS}"
        )
    if header_count != 1:
        raise RuntimeError(f"Pescara applicant header-count drift: {header_count} != 1")
    if physical_ordinal != _EXPECTED_APPLICANT_PHYSICAL_ROWS:
        raise RuntimeError(
            f"Pescara applicant physical-row drift: {physical_ordinal} != {_EXPECTED_APPLICANT_PHYSICAL_ROWS}"
        )
    if len(rows) != _EXPECTED_APPLICANT_RECORDS:
        raise RuntimeError(
            f"Pescara applicant observation drift: {len(rows)} != {_EXPECTED_APPLICANT_RECORDS}"
        )
    return rows, table_groups, physical_ordinal


def parse_pescara_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(cfg, source_key=_APPLICANT_SOURCE_KEY, reference_date=_APPLICANT_REFERENCE_DATE)
    rows, table_groups, physical_rows = _applicant_rows(_antiword_docbook(path))
    malformed_dates = Counter()
    malformed_identifiers = Counter()
    records: list[dict[str, Any]] = []
    for row in rows:
        identifiers = _strict_identifiers(row[3])
        if row[3] and not identifiers:
            malformed_identifiers[row[3]] += 1
        application_date = _reviewed_date(row[5], malformed=Counter(), observed=malformed_dates)
        record = _record(
            cfg,
            len(records) + 1,
            name=row[0],
            office=row[1],
            secondary=row[2],
            identifier_raw=row[3],
            activities=[row[4]] if row[4] else [],
            status="pending",
            application_date=application_date,
            primary_date_label="Data presentazione istanza",
            source_fields={
                "physical_locator": f"logical-row:{len(records) + 1}",
                "requested_activities_source": row[4],
                "application_date_raw_variants": [row[5]] if row[5] else [],
            },
        )
        record["identifiers"] = identifiers
        records.append(record)

    identifier_coverage = sum(bool(record["identifiers"]) for record in records)
    if identifier_coverage != _EXPECTED_APPLICANT_IDENTIFIER_COVERAGE:
        raise RuntimeError(
            f"Pescara applicant identifier-coverage drift: {identifier_coverage} != {_EXPECTED_APPLICANT_IDENTIFIER_COVERAGE}"
        )
    if malformed_identifiers != _EXPECTED_APPLICANT_MALFORMED_IDENTIFIERS:
        raise RuntimeError(f"Pescara applicant malformed-identifier drift: {dict(malformed_identifiers)!r}")
    if malformed_dates:
        raise RuntimeError(f"Pescara applicant malformed-date drift: {dict(malformed_dates)!r}")

    return ParsedBatch(records, {
        "parser": "pescara_legacy_applicants",
        "parser_version": PARSER_VERSION,
        "table_groups": table_groups,
        "physical_rows": physical_rows,
        "reviewed_continuation_rows": 1,
        "public_records": len(records),
        "status_counts": {"pending": len(records)},
        "identifier_coverage": identifier_coverage,
        "raw_only_identifier_records": sum(malformed_identifiers.values()),
        "reviewed_malformed_dates": 0,
    })


PARSERS = {
    "pescara_legacy_listed": parse_pescara_listed,
    "pescara_legacy_applicants": parse_pescara_applicants,
}
