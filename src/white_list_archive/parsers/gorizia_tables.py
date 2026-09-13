from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import pdfplumber
from docx import Document
from docx.oxml.ns import qn

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch

_LISTED_SHA256 = "680f0822f56ce7499a5d3f6c9e524d3d33b631feca51886e57e70fdf9e5fbd6d"
_APPLICANT_SHA256 = "befe7ed054e0cfe9dda48c8dec59f843b569019e40b925d6d5d1fcec19021c7c"
_REFERENCE_DATE = "2026-09-13"

_EXPECTED_LISTED_SECTOR_ROWS = 186
_EXPECTED_LISTED_REGISTRATIONS = 117
_EXPECTED_SECTION_ROWS = {1: 26, 2: 13, 3: 25, 4: 14, 5: 32, 6: 38, 8: 1, 9: 10, 10: 27}
_EXPECTED_UPDATE_VALUES = {
    "": 138,
    "IN AGGIORNAMENTO": 41,
    "21 gennaio 2026": 1,
    "25 settembre 2026": 3,
    "30 luglio 2027": 1,
    "“": 2,
}
_EXPECTED_APPLICANT_IDENTIFIERS = [
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
_EXPECTED_APPLICANT_DATES = [
    "",
    "24.06.2025",
    "21.04.2026",
    "17.02.2026",
    "17.02.2026",
    "",
    "14.04.2026",
    "",
    "01.04.2026",
    "",
]

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
_REVIEWED_MALFORMED_DATES = frozenset({"10.12.202", "Dal 10.12.202", "14 agosto 204"})
_REVIEWED_SPLIT_DIGIT_DATES = {"2 1 aprile 2026": "2026-04-21"}
_REVIEWED_BLANK_EXPIRY_ROWS = frozenset({
    (
        "“ MAROLLI COSTRUZIONI SRL”",
        "MONFALCONE (GO) Viale San Marco, 13/B",
        "C.F./P.I. 01218760310",
        "29 dicembre 2022",
    ),
})


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


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").replace("\xa0", " ")).strip()


def _source_status(update_values: list[str]) -> str:
    return "renewal_update_in_progress" if any(_clean(value) for value in update_values) else "listed"


def parse_gorizia_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(cfg, source_key="gorizia-listed", population_scope="listed", sha256=_LISTED_SHA256)
    document = Document(path)
    if len(document.tables) != 10:
        raise RuntimeError(f"Gorizia listed table-count drift: {len(document.tables)} != 10")

    expected_headers = [
        "Ragione Sociale",
        "Sede legale",
        "Sede secondaria con rappresentanza stabile in Italia",
        "Codice fiscale/Partita IVA",
        "Data d’ iscrizione",
        "Data scadenza iscrizione",
        "Aggiornamento in corso",
    ]
    sector_rows: list[dict[str, Any]] = []
    section_counts: Counter[int] = Counter()
    update_values: Counter[str] = Counter()
    blank_expiry_rows = 0
    for section, table in enumerate(document.tables, start=1):
        if not table.rows:
            raise RuntimeError(f"Gorizia listed section {section} has no header")
        header = _physical_cells(table.rows[0])
        expected_header = list(expected_headers)
        if section == 3:
            expected_header[4] = "Data d ’ iscrizione"
        if header != expected_header:
            raise RuntimeError(f"Gorizia listed header drift in section {section}: {header!r}")
        for source_row, row in enumerate(table.rows[1:], start=2):
            values = _physical_cells(row)
            if not any(values):
                continue
            if len(values) != 7:
                raise RuntimeError(f"Gorizia listed row-shape drift in section {section}, row {source_row}: {values!r}")
            name, office, secondary, identifier_raw, listing_raw, expiry_raw, update_raw = values
            if not name or not listing_raw:
                raise RuntimeError(f"Gorizia incomplete listed row in section {section}, row {source_row}: {values!r}")
            reviewed_blank_expiry = (name, office, identifier_raw, listing_raw) in _REVIEWED_BLANK_EXPIRY_ROWS
            if not expiry_raw:
                if not reviewed_blank_expiry:
                    raise RuntimeError(
                        f"Gorizia unreviewed blank listed expiry in section {section}, row {source_row}: {values!r}"
                    )
                blank_expiry_rows += 1
            listing_date = _strict_source_date(listing_raw, label="listing")
            expiry_date = _strict_source_date(expiry_raw, label="expiry", allow_blank=reviewed_blank_expiry)
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

    if blank_expiry_rows != 1:
        raise RuntimeError(f"Gorizia reviewed blank-expiry row drift: {blank_expiry_rows} != 1")
    if dict(section_counts) != _EXPECTED_SECTION_ROWS:
        raise RuntimeError(f"Gorizia listed section-row drift: {dict(section_counts)!r}")
    if len(sector_rows) != _EXPECTED_LISTED_SECTOR_ROWS:
        raise RuntimeError(f"Gorizia listed sector-row drift: {len(sector_rows)} != {_EXPECTED_LISTED_SECTOR_ROWS}")
    if dict(update_values) != _EXPECTED_UPDATE_VALUES:
        raise RuntimeError(f"Gorizia listed update-value drift: {dict(update_values)!r}")

    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in sector_rows:
        key = (
            row["name"],
            row["office"],
            row["secondary"],
            row["identifier_raw"],
            row["listing_raw"],
            row["expiry_raw"],
        )
        grouped[key].append(row)
    if len(grouped) != _EXPECTED_LISTED_REGISTRATIONS:
        raise RuntimeError(f"Gorizia listed registration-group drift: {len(grouped)} != {_EXPECTED_LISTED_REGISTRATIONS}")

    records: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    for index, (key, rows) in enumerate(grouped.items(), start=1):
        name, office, secondary, identifier_raw, listing_raw, expiry_raw = key
        identifiers = _strict_identifiers(identifier_raw)
        updates = [row["update_raw"] for row in rows if row["update_raw"]]
        source_status = _source_status(updates)
        status_counts[source_status] += 1
        sections = sorted({row["section"] for row in rows})
        source_rows = [f"table-{row['section']}:row-{row['source_row']}" for row in rows]
        record = {
            "authority_key": cfg["authority_key"],
            "authority_name": cfg["authority_name"],
            "register_key": cfg["register_key"],
            "register_name": cfg["register_name"],
            "source_key": cfg["source_key"],
            "population_scope": cfg["population_scope"],
            "source_page_url": cfg["source_page_url"],
            "resource_url": cfg["resource_url"],
            "reference_date": cfg["reference_date"],
            "name": name,
            "address": office,
            "secondary_address": secondary,
            "identifiers": identifiers,
            "identifier_raw": identifier_raw,
            "listing_date": rows[0]["listing_date"],
            "listing_date_raw": listing_raw,
            "expiry_date": rows[0]["expiry_date"],
            "expiry_date_raw": expiry_raw,
            "source_status": source_status,
            "source_status_raw": " | ".join(dict.fromkeys(updates)),
            "sector_memberships": sections,
            "source_rows": source_rows,
            "record_locator": f"gorizia-listed-{index:04d}",
        }
        records.append(record)

    expected_status_counts = {"listed": 86, "renewal_update_in_progress": 31}
    if dict(status_counts) != expected_status_counts:
        raise RuntimeError(f"Gorizia listed status drift: {dict(status_counts)!r}")
    if len({record["record_locator"] for record in records}) != len(records):
        raise RuntimeError("Gorizia listed record locator collision")

    return ParsedBatch(
        records=records,
        diagnostics={
            "sector_rows": len(sector_rows),
            "blank_expiry_rows": blank_expiry_rows,
            "section_rows": dict(section_counts),
            "public_records": len(records),
            "status_counts": dict(status_counts),
            "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
            "update_values": dict(update_values),
        },
    )


def parse_gorizia_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(cfg, source_key="gorizia-applicants", population_scope="applicant", sha256=_APPLICANT_SHA256)
    rows: list[dict[str, Any]] = []
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != 2:
            raise RuntimeError(f"Gorizia applicant page-count drift: {len(pdf.pages)} != 2")
        words: list[dict[str, Any]] = []
        page_offsets: dict[int, float] = {}
        cumulative = 0.0
        for page_number, page in enumerate(pdf.pages, start=1):
            page_offsets[page_number] = cumulative
            for word in page.extract_words(use_text_flow=True, keep_blank_chars=False):
                words.append(
                    {
                        **word,
                        "page": page_number,
                        "global_top": cumulative + float(word["top"]),
                    }
                )
            cumulative += float(page.height)

    identifier_anchors: list[dict[str, Any]] = []
    for word in words:
        text = _clean(word["text"])
        if re.fullmatch(r"\d{11}", text):
            identifier_anchors.append(word)
    observed_identifiers = [_clean(item["text"]) for item in identifier_anchors]
    if observed_identifiers != _EXPECTED_APPLICANT_IDENTIFIERS:
        raise RuntimeError(f"Gorizia applicant identifier-anchor drift: {observed_identifiers!r}")

    for index, anchor in enumerate(identifier_anchors):
        current_top = float(anchor["global_top"])
        next_top = (
            float(identifier_anchors[index + 1]["global_top"])
            if index + 1 < len(identifier_anchors)
            else float("inf")
        )
        segment = [word for word in words if current_top - 4 <= float(word["global_top"]) < next_top - 4]
        segment_sorted = sorted(segment, key=lambda item: (float(item["global_top"]), float(item["x0"])))
        name_words = [item for item in segment_sorted if float(item["x0"]) < 225 and _clean(item["text"]) != observed_identifiers[index]]
        name = _clean(" ".join(_clean(item["text"]) for item in name_words))
        date_candidates = [
            _clean(item["text"])
            for item in segment_sorted
            if re.fullmatch(r"\d{1,2}\.\d{1,2}\.\d{4}", _clean(item["text"]))
        ]
        date_raw = date_candidates[0] if date_candidates else ""
        rows.append(
            {
                "identifier": observed_identifiers[index],
                "name": name,
                "date_raw": date_raw,
                "page": anchor["page"],
            }
        )

    names = [row["name"] for row in rows]
    dates = [row["date_raw"] for row in rows]
    if names != _EXPECTED_APPLICANT_NAMES:
        raise RuntimeError(f"Gorizia applicant name drift: {names!r}")
    if dates != _EXPECTED_APPLICANT_DATES:
        raise RuntimeError(f"Gorizia applicant date drift: {dates!r}")

    records: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        records.append(
            {
                "authority_key": cfg["authority_key"],
                "authority_name": cfg["authority_name"],
                "register_key": cfg["register_key"],
                "register_name": cfg["register_name"],
                "source_key": cfg["source_key"],
                "population_scope": cfg["population_scope"],
                "source_page_url": cfg["source_page_url"],
                "resource_url": cfg["resource_url"],
                "reference_date": cfg["reference_date"],
                "name": row["name"],
                "address": "",
                "secondary_address": "",
                "identifiers": [row["identifier"]],
                "identifier_raw": row["identifier"],
                "listing_date": _strict_source_date(row["date_raw"], label="applicant", allow_blank=True),
                "listing_date_raw": row["date_raw"],
                "expiry_date": "",
                "expiry_date_raw": "",
                "source_status": "pending",
                "source_status_raw": "richiedente iscrizione",
                "sector_memberships": [],
                "source_rows": [f"page-{row['page']}:anchor-{row['identifier']}"],
                "record_locator": f"gorizia-applicant-{index:04d}",
            }
        )

    return ParsedBatch(
        records=records,
        diagnostics={
            "public_records": len(records),
            "status_counts": {"pending": len(records)},
            "identifier_coverage": len(records),
            "pages": 2,
        },
    )
