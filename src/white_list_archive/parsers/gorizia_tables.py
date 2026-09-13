from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import pdfplumber
from docx import Document
from docx.oxml.ns import qn

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _clean, _record

PARSER_VERSION = "1"
_REFERENCE_DATE = "2026-09-13"  # archive capture date: the current attachments are not document-dated
_LISTED_SOURCE_KEY = "gorizia-listed"
_APPLICANT_SOURCE_KEY = "gorizia-applicants"
_LISTED_SHA256 = "680f0822f56ce7499a5d3f6c9e524d3d33b631feca51886e57e70fdf9e5fbd6d"
_APPLICANT_SHA256 = "befe7ed054e0cfe9dda48c8dec59f843b569019e40b925d6d5d1fcec19021c7c"

_EXPECTED_SECTION_ROWS = {
    1: 26,
    2: 13,
    3: 25,
    4: 14,
    5: 32,
    6: 38,
    7: 0,
    8: 1,
    9: 10,
    10: 27,
}
_EXPECTED_LISTED_SECTOR_ROWS = 186
_EXPECTED_LISTED_RECORDS = 117
_EXPECTED_LISTED_STATUS_COUNTS = {"listed": 86, "renewal_update_in_progress": 31}
_EXPECTED_UPDATE_VALUES = {
    "": 138,
    "IN AGGIORNAMENTO": 41,
    "21 gennaio 2026": 1,
    "25 settembre 2026": 3,
    "30 luglio 2027": 1,
    "“": 2,
}
_EXPECTED_APPLICANT_ROWS = 10
_EXPECTED_APPLICANT_STATUS_COUNTS = {"pending": 10}
_EXPECTED_APPLICANT_IDS = [
    "01270500315",
    "01262160318",
    "01190800316",
    "01270740317",
    "00407990316",
    "01268270319",
    "00557360310",
    "01040110312",
    "01170510315",
    "01195820319",
]
_EXPECTED_APPLICANT_NAMES = [
    "ITALTRCH SRL",
    "METAL X SRL",
    "“L’ANTICA RICETTA SRLS”",
    "EL.NET SOLUTION SRL",
    "C.M.T. SRL",
    "FMGDUE SRL",
    "SI.ECO:SICUREZZA ED ECOLOGIA SRL",
    "SULTAN SRL",
    "SVILUPPO SOLARE SRL",
    "T-RECYCLE SRL",
]
_EXPECTED_APPLICANT_DATES = ["", "24.06.2025", "21.04.2026", "17.02.2026", "17.02.2026", "", "14.04.2026", "", "01.04.2026", ""]
_EXPECTED_APPLICANT_TABLE_ROWS = [46, 17]

_SECTION_ACTIVITIES = {
    1: "Estrazione, fornitura e trasporto di terra e materiali inerti",
    2: "Confezionamento, fornitura e trasporto di calcestruzzo e bitume",
    3: "Noli a freddo di macchinari",
    4: "Fornitura di ferro lavorato",
    5: "Noli a caldo",
    6: "Autotrasporto per conto terzi",
    7: "Guardiania ai cantieri",
    8: "Servizi funebri e cimiteriali",
    9: "Ristorazione, gestione delle mense e catering",
    10: "Servizi ambientali, comprese le attività di raccolta, di trasporto nazionale e transfrontaliero, anche per conto terzi, di trattamento e smaltimento dei rifiuti, nonché le attività di risanamento e bonifica e gli altri servizi connessi alla gestione dei rifiuti",
}

_ITALIAN_MONTHS = {
    "gennaio": 1,
    "febbraio": 2,
    "marzo": 3,
    "aprile": 4,
    "maggio": 5,
    "giugno": 6,
    "luglio": 7,
    "agosto": 8,
    "settembre": 9,
    "ottobre": 10,
    "novembre": 11,
    "dicembre": 12,
}
_REVIEWED_MALFORMED_DATES = frozenset({"10.12.202", "14 agosto 204"})
_REVIEWED_SPLIT_DIGIT_DATES = {"2 1 aprile 2026": "2026-04-21"}


def _physical_cells(row: Any) -> list[str]:
    return [
        _clean(" ".join((node.text or "") for node in tc.iter(qn("w:t"))))
        for tc in row._tr.tc_lst
    ]


def _validate_cfg(cfg: dict[str, Any], *, source_key: str, population_scope: str, sha256: str) -> None:
    if cfg.get("source_key") != source_key:
        raise RuntimeError(f"Gorizia parser/source mismatch: {cfg.get('source_key')!r} != {source_key!r}")
    if cfg.get("authority_key") != "gorizia":
        raise RuntimeError("Gorizia parser bound to a non-Gorizia authority")
    if cfg.get("population_scope") != population_scope:
        raise RuntimeError(f"Gorizia population-scope drift: {cfg.get('population_scope')!r}")
    if cfg.get("reference_date") != _REFERENCE_DATE:
        raise RuntimeError(f"Gorizia reference date drift: {cfg.get('reference_date')!r}")
    if cfg.get("sha256") != sha256:
        raise RuntimeError(f"Gorizia approved-byte digest drift: {cfg.get('sha256')!r}")


def _strict_source_date(raw: str, *, label: str, allow_blank: bool = False) -> str:
    value = _clean(raw)
    if not value:
        if allow_blank:
            return ""
        raise RuntimeError(f"Gorizia unexpected blank {label} date")
    if value in _REVIEWED_MALFORMED_DATES:
        return ""
    if value in _REVIEWED_SPLIT_DIGIT_DATES:
        return _REVIEWED_SPLIT_DIGIT_DATES[value]
    match = re.fullmatch(r"(\d{1,2})[./](\d{1,2})[./](\d{4})", value)
    if match:
        day, month, year = map(int, match.groups())
    else:
        match = re.fullmatch(r"(\d{1,2})°?\s+([A-Za-zÀ-ÿ]+)\s+(\d{4})", value)
        if not match:
            raise RuntimeError(f"Gorizia unreviewed {label} date typography: {value!r}")
        day = int(match.group(1))
        month_name = match.group(2).casefold()
        if month_name not in _ITALIAN_MONTHS:
            raise RuntimeError(f"Gorizia unreviewed {label} month: {value!r}")
        month = _ITALIAN_MONTHS[month_name]
        year = int(match.group(3))
    try:
        return date(year, month, day).isoformat()
    except ValueError as exc:
        raise RuntimeError(f"Gorizia unreviewed invalid {label} calendar date: {value!r}") from exc


def _strict_identifiers(raw: str) -> list[str]:
    value = _clean(raw).upper()
    matches: list[str] = []
    for token in re.findall(r"(?<![A-Z0-9])[A-Z0-9]{11,16}(?![A-Z0-9])", value):
        if token.isdigit() and len(token) == 11 and token not in matches:
            matches.append(token)
        elif len(token) == 16 and token.isalnum() and any(ch.isalpha() for ch in token) and token not in matches:
            matches.append(token)
    return matches


def _validate_listed_header(values: list[str], section: int) -> None:
    if (
        len(values) != 7
        or values[0].casefold() != "ragione sociale"
        or values[1].casefold() != "sede legale"
        or "sede secondaria" not in values[2].casefold()
        or "codice fiscale" not in values[3].casefold()
        or "data d" not in values[4].casefold()
        or "data scadenza iscrizione" not in values[5].casefold()
        or "aggiornamento in corso" not in values[6].casefold()
    ):
        raise RuntimeError(f"Gorizia listed header drift in section {section}: {values!r}")


def parse_gorizia_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(cfg, source_key=_LISTED_SOURCE_KEY, population_scope="listed", sha256=_LISTED_SHA256)
    document = Document(path)
    if len(document.tables) != 10:
        raise RuntimeError(f"Gorizia listed table-count drift: {len(document.tables)} != 10")

    sector_rows: list[dict[str, Any]] = []
    section_counts: Counter[int] = Counter()
    update_values: Counter[str] = Counter()
    for section, table in enumerate(document.tables, start=1):
        if not table.rows:
            raise RuntimeError(f"Gorizia listed section {section} has no header")
        _validate_listed_header(_physical_cells(table.rows[0]), section)
        for source_row, row in enumerate(table.rows[1:], start=2):
            values = _physical_cells(row)
            if not any(values):
                continue
            if len(values) != 7:
                raise RuntimeError(f"Gorizia listed row-shape drift in section {section}, row {source_row}: {values!r}")
            name, office, secondary, identifier_raw, listing_raw, expiry_raw, update_raw = values
            if not name or not listing_raw or not expiry_raw:
                raise RuntimeError(f"Gorizia incomplete listed row in section {section}, row {source_row}: {values!r}")
            listing_date = _strict_source_date(listing_raw, label="listing")
            expiry_date = _strict_source_date(expiry_raw, label="expiry")
            section_counts[section] += 1
            update_values[update_raw] += 1
            sector_rows.append(
                {
                    "section": section,
                    "source_row": source_row,
                    "name": name,
                    "office": office,
                    "secondary": secondary,
                    "identifier_raw": identifier_raw,
                    "listing_raw": listing_raw,
                    "listing_date": listing_date,
                    "expiry_raw": expiry_raw,
                    "expiry_date": expiry_date,
                    "update_raw": update_raw,
                }
            )

    if dict(section_counts) != _EXPECTED_SECTION_ROWS:
        raise RuntimeError(f"Gorizia listed section-row drift: {dict(section_counts)!r}")
    if len(sector_rows) != _EXPECTED_LISTED_SECTOR_ROWS:
        raise RuntimeError(f"Gorizia listed source-row drift: {len(sector_rows)}")
    if dict(update_values) != _EXPECTED_UPDATE_VALUES:
        raise RuntimeError(f"Gorizia listed update-lexeme drift: {dict(update_values)!r}")

    grouped: dict[tuple[str, str, str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in sector_rows:
        grouped[
            (
                row["name"], row["office"], row["secondary"], row["identifier_raw"],
                row["listing_raw"], row["expiry_raw"],
            )
        ].append(row)
    if len(grouped) != _EXPECTED_LISTED_RECORDS:
        raise RuntimeError(f"Gorizia listed registration-group drift: {len(grouped)}")

    records: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    for ordinal, members in enumerate(grouped.values(), start=1):
        sections = sorted({member["section"] for member in members})
        if sum(1 for member in members) != len({(member["section"], member["source_row"]) for member in members}):
            raise RuntimeError(f"Gorizia repeated source locator inside registration group: {members!r}")
        update_raw_values: list[str] = []
        for member in members:
            if member["update_raw"] and member["update_raw"] not in update_raw_values:
                update_raw_values.append(member["update_raw"])
        # The source column itself is explicitly 'Aggiornamento in corso'. A nonblank raw value is
        # therefore retained as positive update evidence, including publisher date/ditto lexemes.
        status = "renewal_update_in_progress" if update_raw_values else "listed"
        status_counts[status] += 1
        first = members[0]
        activities = [_SECTION_ACTIVITIES[section] for section in sections]
        record = _record(
            cfg,
            ordinal,
            name=first["name"],
            office=first["office"],
            secondary=first["secondary"],
            identifier_raw=first["identifier_raw"],
            activities=activities,
            status=status,
            listing_date=first["listing_date"],
            expiry_date=first["expiry_date"],
            primary_date_label="Data iscrizione",
            source_fields={
                "sections": [f"Sezione {section}" for section in sections],
                "source_locators": [f"section-{member['section']}:row-{member['source_row']}" for member in members],
                "listing_date_raw_variants": sorted({member["listing_raw"] for member in members}),
                "expiry_date_raw_variants": sorted({member["expiry_raw"] for member in members}),
                "update_raw_values": update_raw_values,
            },
        )
        record["identifiers"] = _strict_identifiers(first["identifier_raw"])
        records.append(record)

    if dict(status_counts) != _EXPECTED_LISTED_STATUS_COUNTS:
        raise RuntimeError(f"Gorizia listed status drift: {dict(status_counts)!r}")
    return ParsedBatch(
        records=records,
        diagnostics={
            "sector_rows": len(sector_rows),
            "section_rows": dict(section_counts),
            "public_records": len(records),
            "status_counts": dict(status_counts),
            "update_values": dict(update_values),
            "malformed_listing_values": sorted({row["listing_raw"] for row in sector_rows if not row["listing_date"]}),
            "malformed_expiry_values": sorted({row["expiry_raw"] for row in sector_rows if not row["expiry_date"]}),
        },
    )


def _applicant_pages(path: Path) -> list[list[list[str]]]:
    pages: list[list[list[str]]] = []
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != 2:
            raise RuntimeError(f"Gorizia applicant page-count drift: {len(pdf.pages)} != 2")
        for page_number, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables() or []
            if len(tables) != 1:
                raise RuntimeError(f"Gorizia applicant table-count drift on page {page_number}: {len(tables)} != 1")
            rows = [[_clean(cell) for cell in row] for row in tables[0] if row is not None]
            pages.append(rows)
    if [len(rows) for rows in pages] != _EXPECTED_APPLICANT_TABLE_ROWS:
        raise RuntimeError(f"Gorizia applicant table-row drift: {[len(rows) for rows in pages]!r}")
    if any(len(row) != 7 for row in pages[0]) or any(len(row) != 6 for row in pages[1]):
        raise RuntimeError("Gorizia applicant physical-width drift")
    return pages


def _record_starts(rows: list[list[str]], id_column: int, *, first_data_row: int) -> list[tuple[int, str]]:
    anchors: list[tuple[int, str]] = []
    for index, row in enumerate(rows):
        ids = re.findall(r"(?<!\d)\d{11}(?!\d)", row[id_column])
        if len(ids) > 1:
            raise RuntimeError(f"Gorizia applicant multiple identifiers in row {index + 1}: {row[id_column]!r}")
        if ids:
            anchors.append((index, ids[0]))
    starts: list[tuple[int, str]] = []
    for anchor_number, (anchor_index, identifier) in enumerate(anchors):
        if anchor_number == 0:
            start = first_data_row
        else:
            previous_anchor = anchors[anchor_number - 1][0]
            blanks = [
                idx for idx in range(previous_anchor + 1, anchor_index)
                if not any(rows[idx])
            ]
            start = (max(blanks) + 1) if blanks else anchor_index
        starts.append((start, identifier))
    return starts


def _extract_applicant_rows(path: Path) -> list[dict[str, str]]:
    pages = _applicant_pages(path)
    records: list[dict[str, str]] = []
    page_specs = [
        {"name": 1, "office": 2, "secondary": 3, "identifier": 4, "date": 5, "activity": 6, "first_data": 6},
        {"name": 0, "office": 1, "secondary": 2, "identifier": 3, "date": 4, "activity": 5, "first_data": 0},
    ]
    for page_index, (rows, spec) in enumerate(zip(pages, page_specs, strict=True), start=1):
        starts = _record_starts(rows, spec["identifier"], first_data_row=spec["first_data"])
        if page_index == 1 and len(starts) != 7:
            raise RuntimeError(f"Gorizia applicant page-one anchor drift: {len(starts)} != 7")
        if page_index == 2 and len(starts) != 3:
            raise RuntimeError(f"Gorizia applicant page-two anchor drift: {len(starts)} != 3")
        for number, (start, identifier) in enumerate(starts):
            end = starts[number + 1][0] if number + 1 < len(starts) else len(rows)
            chunk = rows[start:end]
            if not chunk:
                raise RuntimeError(f"Gorizia applicant empty chunk for {identifier}")
            def joined(column: int) -> str:
                return _clean(" ".join(row[column] for row in chunk if row[column]))
            identifier_raw = joined(spec["identifier"])
            ids = re.findall(r"(?<!\d)\d{11}(?!\d)", identifier_raw)
            if ids != [identifier]:
                raise RuntimeError(f"Gorizia applicant identifier-chunk drift for {identifier}: {ids!r}")
            date_raw = joined(spec["date"])
            dates = re.findall(r"(?<!\d)\d{2}\.\d{2}\.\d{4}(?!\d)", date_raw)
            if len(dates) > 1:
                raise RuntimeError(f"Gorizia applicant multiple application dates for {identifier}: {dates!r}")
            records.append(
                {
                    "page": str(page_index),
                    "source_start_row": str(start + 1),
                    "source_end_row": str(end),
                    "name": joined(spec["name"]),
                    "office": joined(spec["office"]),
                    "secondary": joined(spec["secondary"]),
                    "identifier_raw": identifier_raw,
                    "identifier": identifier,
                    "application_raw": date_raw,
                    "application_date_source": dates[0] if dates else "",
                    "activities_raw": joined(spec["activity"]),
                }
            )
    return records


def parse_gorizia_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(cfg, source_key=_APPLICANT_SOURCE_KEY, population_scope="applicant", sha256=_APPLICANT_SHA256)
    rows = _extract_applicant_rows(path)
    if len(rows) != _EXPECTED_APPLICANT_ROWS:
        raise RuntimeError(f"Gorizia applicant population drift: {len(rows)} != {_EXPECTED_APPLICANT_ROWS}")
    if [row["identifier"] for row in rows] != _EXPECTED_APPLICANT_IDS:
        raise RuntimeError(f"Gorizia applicant identifier-order drift: {[row['identifier'] for row in rows]!r}")
    if [row["name"] for row in rows] != _EXPECTED_APPLICANT_NAMES:
        raise RuntimeError(f"Gorizia applicant name transcription drift: {[row['name'] for row in rows]!r}")
    if [row["application_date_source"] for row in rows] != _EXPECTED_APPLICANT_DATES:
        raise RuntimeError(f"Gorizia applicant date transcription drift: {[row['application_date_source'] for row in rows]!r}")
    if any(not row["office"] or not row["activities_raw"] for row in rows):
        raise RuntimeError("Gorizia applicant blank office/activity after source reconstruction")

    records: list[dict[str, Any]] = []
    for ordinal, row in enumerate(rows, start=1):
        application_date = _strict_source_date(row["application_date_source"], label="application", allow_blank=True)
        record = _record(
            cfg,
            ordinal,
            name=row["name"],
            office=row["office"],
            secondary=row["secondary"],
            identifier_raw=row["identifier_raw"],
            activities=[row["activities_raw"]],
            status="pending",
            application_date=application_date,
            primary_date_label="Data presentazione istanza",
            source_fields={
                "page": int(row["page"]),
                "source_start_row": int(row["source_start_row"]),
                "source_end_row": int(row["source_end_row"]),
                "application_date_raw": row["application_raw"],
                "requested_activities_source": row["activities_raw"],
            },
        )
        record["identifiers"] = [row["identifier"]]
        records.append(record)

    status_counts = {"pending": len(records)}
    if status_counts != _EXPECTED_APPLICANT_STATUS_COUNTS:
        raise RuntimeError(f"Gorizia applicant status drift: {status_counts!r}")
    return ParsedBatch(
        records=records,
        diagnostics={
            "source_rows": len(rows),
            "public_records": len(records),
            "status_counts": status_counts,
            "identifier_coverage": len(records),
            "application_date_coverage": sum(bool(record["application_date"]) for record in records),
        },
    )


PARSERS = {
    "gorizia_listed": parse_gorizia_listed,
    "gorizia_applicants": parse_gorizia_applicants,
}
