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
# Row geometry in the approved PDF binds 14.04.2026 to FMGDUE SRL;
# the following SI.ECO applicant row has no date. Keep this sequence fail-closed.
_EXPECTED_APPLICANT_DATES = [
    "",
    "24.06.2025",
    "21.04.2026",
    "17.02.2026",
    "17.02.2026",
    "14.04.2026",
    "",
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
_REVIEWED_SPLIT_DIGIT_DATES = {
    "2 1 aprile 2026": "2026-04-21",
    "14 luglio 2 027": "2027-07-14",
    "21 ottobre 202 3": "2023-10-21",
}
_REVIEWED_BLANK_EXPIRY_ROWS = frozenset({
    (
        "“ MAROLLI COSTRUZIONI SRL”",
        "MONFALCONE (GO) Viale San Marco, 13/B",
        "C.F./P.I. 01218760310",
        "29 dicembre 2022",
    ),
    (
        "PEVERE LOGISTICA SRL",
        "MONFALCONE (GO) Via Timavo, 63",
        "C.F./P.I. 01282120315",
        "30 luglio 2026",
    ),
})


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip()


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_cfg(cfg: dict[str, Any], *, source_key: str, population_scope: str, sha256: str) -> None:
    if cfg.get("source_key") != source_key:
        raise RuntimeError(f"Gorizia source-key drift: {cfg.get('source_key')!r} != {source_key!r}")
    if cfg.get("population_scope") != population_scope:
        raise RuntimeError(
            f"Gorizia population-scope drift for {source_key}: {cfg.get('population_scope')!r} != {population_scope!r}"
        )
    if cfg.get("sha256") != sha256:
        raise RuntimeError(f"Gorizia configured SHA-256 drift for {source_key}: {cfg.get('sha256')!r} != {sha256!r}")
    if cfg.get("reference_date") != _REFERENCE_DATE:
        raise RuntimeError(
            f"Gorizia reference-date drift for {source_key}: {cfg.get('reference_date')!r} != {_REFERENCE_DATE!r}"
        )


def _normalise_italian_date(raw: str) -> str | None:
    value = _clean(raw)
    if not value:
        return None
    if value in _REVIEWED_MALFORMED_DATES:
        return None
    if value in _REVIEWED_SPLIT_DIGIT_DATES:
        return _REVIEWED_SPLIT_DIGIT_DATES[value]
    match = re.fullmatch(r"(\d{1,2})\s+([A-Za-zÀ-ÿ]+)\s+(\d{4})", value)
    if not match:
        raise RuntimeError(f"Gorizia unexpected date lexeme: {value!r}")
    month = _ITALIAN_MONTHS.get(match.group(2).lower())
    if not month:
        raise RuntimeError(f"Gorizia unknown Italian month: {match.group(2)!r}")
    parsed = date(int(match.group(3)), month, int(match.group(1)))
    return parsed.isoformat()


def _docx_cell_text(cell: Any) -> str:
    values: list[str] = []
    for paragraph in cell.paragraphs:
        text = _clean(paragraph.text)
        if text:
            values.append(text)
    return _clean(" ".join(values))


def _header_signature(row: Any) -> str:
    return " | ".join(_docx_cell_text(cell) for cell in row.cells)


def _listed_table_rows(path: Path) -> tuple[list[dict[str, Any]], dict[int, int]]:
    document = Document(path)
    if len(document.tables) != 10:
        raise RuntimeError(f"Gorizia listed publisher-shape drift: {len(document.tables)} tables != 10")

    rows: list[dict[str, Any]] = []
    section_counts: defaultdict[int, int] = defaultdict(int)
    expected_headers = {
        "DITTA | SEDE LEGALE | C.F./P.I. | SETTORE ATTIVITA' (cfr. elenco da 1 a 10 a fondo pagina) | Data d’ iscrizione | Scadenza | NOTE/AGGIORNAMENTO",
        "DITTA | SEDE LEGALE | C.F./P.I. | SETTORE ATTIVITA' (cfr. elenco da 1 a 10 a fondo pagina) | Data d ’ iscrizione | Scadenza | NOTE/AGGIORNAMENTO",
        "DITTA | SEDE LEGALE | C.F./P.I. | SETTORE ATTIVITA' (cfr. elenco da 1 a 10 a fondo pagina) | Data di iscrizione | Scadenza | NOTE/AGGIORNAMENTO",
    }
    for table_index, table in enumerate(document.tables, start=1):
        if not table.rows:
            raise RuntimeError(f"Gorizia listed empty table: {table_index}")
        header = _header_signature(table.rows[0])
        if header not in expected_headers:
            raise RuntimeError(f"Gorizia listed header drift in table {table_index}: {header!r}")
        for row_index, row in enumerate(table.rows[1:], start=2):
            cells = [_docx_cell_text(cell) for cell in row.cells]
            if not any(cells):
                continue
            if len(cells) != 7:
                raise RuntimeError(f"Gorizia listed column drift in table {table_index} row {row_index}: {len(cells)} != 7")
            name, address, identifier, sectors_raw, listing_raw, expiry_raw, update_raw = cells
            sectors = [int(value) for value in re.findall(r"(?<!\d)(10|[1-9])(?!\d)", sectors_raw)]
            if not sectors:
                raise RuntimeError(
                    f"Gorizia listed sector parse drift in table {table_index} row {row_index}: {sectors_raw!r}"
                )
            for sector in sectors:
                section_counts[sector] += 1
            rows.append(
                {
                    "table": table_index,
                    "row": row_index,
                    "name": name,
                    "address": address,
                    "identifier_raw": identifier,
                    "sectors_raw": sectors_raw,
                    "sectors": sectors,
                    "listing_raw": listing_raw,
                    "expiry_raw": expiry_raw,
                    "update_raw": update_raw,
                }
            )

    if len(rows) != _EXPECTED_LISTED_REGISTRATIONS:
        raise RuntimeError(f"Gorizia listed public-record drift: {len(rows)} != {_EXPECTED_LISTED_REGISTRATIONS}")
    if sum(section_counts.values()) != _EXPECTED_LISTED_SECTOR_ROWS:
        raise RuntimeError(
            f"Gorizia listed sector-row drift: {sum(section_counts.values())} != {_EXPECTED_LISTED_SECTOR_ROWS}"
        )
    if dict(sorted(section_counts.items())) != _EXPECTED_SECTION_ROWS:
        raise RuntimeError(f"Gorizia listed section-count drift: {dict(sorted(section_counts.items()))!r}")
    return rows, dict(sorted(section_counts.items()))


def parse_gorizia_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(cfg, source_key="gorizia-listed", population_scope="listed", sha256=_LISTED_SHA256)
    if _sha256(path) != _LISTED_SHA256:
        raise RuntimeError("Gorizia listed source bytes drift from approved SHA-256")

    source_rows, section_counts = _listed_table_rows(path)
    update_values = Counter(row["update_raw"] for row in source_rows for _ in row["sectors"])
    if dict(update_values) != _EXPECTED_UPDATE_VALUES:
        raise RuntimeError(f"Gorizia listed update-value drift: {dict(update_values)!r}")

    records: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    blank_expiry_rows = 0
    for source_row in source_rows:
        listing_raw = source_row["listing_raw"]
        expiry_raw = source_row["expiry_raw"]
        if not expiry_raw:
            blank_signature = (
                source_row["name"],
                source_row["address"],
                source_row["identifier_raw"],
                source_row["listing_raw"],
            )
            if blank_signature not in _REVIEWED_BLANK_EXPIRY_ROWS:
                raise RuntimeError(f"Gorizia unreviewed blank expiry row: {blank_signature!r}")
            blank_expiry_rows += 1
        listing_date = _normalise_italian_date(listing_raw)
        expiry_date = _normalise_italian_date(expiry_raw)
        source_status = "renewal_update_in_progress" if source_row["update_raw"] == "IN AGGIORNAMENTO" else "listed"
        for sector_index, sector in enumerate(source_row["sectors"], start=1):
            identifier_match = re.search(r"(?<!\d)(\d{11})(?!\d)", source_row["identifier_raw"])
            identifiers = [identifier_match.group(1)] if identifier_match else []
            record_locator = f"gorizia-listed:t{source_row['table']}:r{source_row['row']}:s{sector_index}"
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
                    "name": source_row["name"],
                    "address": source_row["address"],
                    "identifiers": identifiers,
                    "activity_sectors": [str(sector)],
                    "listing_date_raw": listing_raw,
                    "listing_date": listing_date,
                    "expiry_date_raw": expiry_raw,
                    "expiry_date": expiry_date,
                    "source_status": source_status,
                    "source_status_raw": source_row["update_raw"],
                    "record_locator": record_locator,
                }
            )
            status_counts[source_status] += 1

    if blank_expiry_rows != len(_REVIEWED_BLANK_EXPIRY_ROWS):
        raise RuntimeError(
            f"Gorizia reviewed blank-expiry population drift: {blank_expiry_rows} != {len(_REVIEWED_BLANK_EXPIRY_ROWS)}"
        )
    if len(records) != _EXPECTED_LISTED_SECTOR_ROWS:
        raise RuntimeError(f"Gorizia listed output record drift: {len(records)} != {_EXPECTED_LISTED_SECTOR_ROWS}")
    if len({record["record_locator"] for record in records}) != len(records):
        raise RuntimeError("Gorizia listed record locator collision")

    return ParsedBatch(
        records=records,
        diagnostics={
            "sector_rows": len(records),
            "blank_expiry_rows": blank_expiry_rows,
            "section_rows": section_counts,
            "public_records": len(source_rows),
            "status_counts": dict(status_counts),
            "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
            "update_values": dict(update_values),
        },
    )


def parse_gorizia_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(cfg, source_key="gorizia-applicants", population_scope="applicant", sha256=_APPLICANT_SHA256)
    if _sha256(path) != _APPLICANT_SHA256:
        raise RuntimeError("Gorizia applicant source bytes drift from approved SHA-256")
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != 2:
            raise RuntimeError(f"Gorizia applicant page-count drift: {len(pdf.pages)} != 2")
        words: list[dict[str, Any]] = []
        cumulative = 0.0
        for page_number, page in enumerate(pdf.pages, start=1):
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
    identifier_occurrences: Counter[str] = Counter()
    for word in words:
        text = _clean(word["text"])
        matches = [identifier for identifier in _EXPECTED_APPLICANT_IDENTIFIERS if identifier in text]
        if len(matches) > 1:
            raise RuntimeError(f"Gorizia ambiguous applicant identifier word: {text!r}")
        if matches:
            identifier = matches[0]
            identifier_occurrences[identifier] += 1
            identifier_anchors.append({**word, "identifier": identifier})
    observed_identifiers = [item["identifier"] for item in identifier_anchors]
    if observed_identifiers != _EXPECTED_APPLICANT_IDENTIFIERS or any(
        identifier_occurrences[identifier] != 1 for identifier in _EXPECTED_APPLICANT_IDENTIFIERS
    ):
        raise RuntimeError(
            f"Gorizia applicant identifier-anchor drift: {observed_identifiers!r}; "
            f"occurrences={dict(identifier_occurrences)!r}"
        )

    for index, anchor in enumerate(identifier_anchors):
        current_top = float(anchor["global_top"])
        next_top = (
            float(identifier_anchors[index + 1]["global_top"])
            if index + 1 < len(identifier_anchors)
            else float("inf")
        )
        segment = [word for word in words if current_top - 4 <= float(word["global_top"]) < next_top - 4]
        segment_sorted = sorted(segment, key=lambda item: (float(item["global_top"]), float(item["x0"])))
        name_words = [item for item in segment_sorted if float(item["x0"]) < 225 and item is not anchor]
        name_candidate = _clean(" ".join(_clean(item["text"]) for item in name_words))
        expected_name = _EXPECTED_APPLICANT_NAMES[index]
        if name_candidate.count(expected_name) != 1:
            raise RuntimeError(
                f"Gorizia applicant expected-name anchor drift for {expected_name!r}: {name_candidate!r}"
            )
        name = expected_name
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
                "identifiers": [row["identifier"]],
                "activity_sectors": [],
                "listing_date_raw": row["date_raw"],
                "listing_date": None,
                "expiry_date_raw": "",
                "expiry_date": None,
                "source_status": "pending",
                "source_status_raw": "",
                "record_locator": f"gorizia-applicants:p{row['page']}:r{index}",
            }
        )

    if len(records) != len(_EXPECTED_APPLICANT_IDENTIFIERS):
        raise RuntimeError(f"Gorizia applicant record-count drift: {len(records)} != 10")
    if len({record["record_locator"] for record in records}) != len(records):
        raise RuntimeError("Gorizia applicant record locator collision")

    return ParsedBatch(
        records=records,
        diagnostics={
            "public_records": len(records),
            "status_counts": {"pending": len(records)},
            "identifier_coverage": len(records),
        },
    )
