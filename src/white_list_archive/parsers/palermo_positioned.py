from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any

import pdfplumber

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _clean, _record

_DATE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
_LISTED_GEOMETRY = (1190.40, 841.68)
_APPLICANT_GEOMETRY = (841.68, 595.20)
_LISTED_PAGE_ROWS = (
    5, 18, 18, 18, 18, 15, 17, 17, 17, 17, 18, 17, 17, 18, 18, 17, 17, 17,
    17, 18, 18, 17, 17, 17, 18, 17, 17, 17, 17, 16, 16, 17, 17, 17, 17, 18,
    17, 17, 16, 17, 17, 18, 18, 17, 18, 17, 18, 18, 17, 18, 18, 18, 18, 18, 7,
)
_APPLICANT_PAGE_ROWS = (
    0, 0, 9, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11,
    11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11,
    11, 11, 11, 11, 11, 11, 11, 13, 10, 10, 10, 11, 11, 11, 11, 11, 11, 11, 11, 7,
)
_LISTED_SOURCE_NUMBERS = tuple(value for value in range(1, 932) if value not in {252, 316})
_APPLICANT_SOURCE_NUMBERS = tuple(range(1, 610))
_LISTED_OUTCOMES = Counter(
    {
        "": 485,
        "Aggiornamento in corso": 430,
        "Aggironamento in corso": 4,
        "Aggiornamento incorso": 3,
        "Aggiornamneto in corso": 3,
        "Agggiornamento in corso": 2,
        "Aggiornamtno in corso": 1,
        "provvedimento prot. n. 119218 del 30/07/2026, di applicazione della misura di prevenzione collaborativa, ai sensi dell'art. 94 bis, D.lgs.": 1,
    }
)
_APPLICANT_OUTCOMES = Counter(
    {
        "In istruttoria": 599,
        "In istrutoria": 2,
        "In istruttortia": 1,
        "In struttoria": 1,
        "Ini struttoria": 1,
        "In isruttoria": 1,
        "In isttuttoria": 1,
        "In istrutttoria": 1,
        "Iistruttoria": 1,
        "In Istruttoria": 1,
    }
)
_LISTED_BAD_EXPIRY = {247: "28/072027", 577: "20/072027"}
_LISTED_MALFORMED_CF = {
    238: "CRSGDU64S27FG273M",
    461: "GDUGTN797D20G348J",
    622: "MNTPTR71C09G273 E",
    674: "PSSSFN73D09G5111P",
}
_LISTED_MALFORMED_VAT = {
    207: "CNGVCN61P65B780 H",
    353: "0557970829",
    423: "066322880821",
    457: "C.O.E. SM26890",
    734: "0548495028",
}
_APPLICANT_MALFORMED_CF = {263: "1464340841"}
_APPLICANT_MALFORMED_VAT = {
    80: "5244110820",
    195: "6682250821",
    256: "0461050822",
    482: "0318330826",
}

_LISTED_BANDS = {
    "name": (175.0, 282.0),
    "office": (282.0, 347.0),
    "address": (347.0, 412.0),
    "secondary": (412.0, 482.0),
    "cf": (482.0, 568.0),
    "vat": (568.0, 630.0),
    "activities": (630.0, 835.0),
    "listing": (835.0, 892.0),
    "expiry": (892.0, 950.0),
    "outcome": (950.0, 1191.0),
}
_APPLICANT_BANDS = {
    "name": (40.0, 152.0),
    "office": (152.0, 225.0),
    "address": (225.0, 289.0),
    "secondary": (289.0, 324.0),
    "cf": (324.0, 396.0),
    "vat": (396.0, 457.0),
    "activities": (457.0, 742.0),
    "outcome": (742.0, 842.0),
}


def _valid_identifier(value: str) -> bool:
    value = _clean(value)
    return bool((value.isdigit() and len(value) == 11) or (len(value) == 16 and value.isalnum()))


def _listed_status(raw: str) -> str:
    if raw == "":
        return "listed"
    if raw in {
        "Aggiornamento in corso",
        "Aggironamento in corso",
        "Aggiornamento incorso",
        "Aggiornamneto in corso",
        "Agggiornamento in corso",
        "Aggiornamtno in corso",
    }:
        return "renewal_update_in_progress"
    if raw == (
        "provvedimento prot. n. 119218 del 30/07/2026, di applicazione della misura di "
        "prevenzione collaborativa, ai sensi dell'art. 94 bis, D.lgs."
    ):
        return "listed"
    raise RuntimeError(f"palermo_listed: unapproved outcome/update marker {raw!r}")


def _applicant_status(raw: str) -> str:
    if raw in _APPLICANT_OUTCOMES:
        return "pending"
    raise RuntimeError(f"palermo_applicants: unapproved outcome {raw!r}")


def _strict_date(raw: str) -> str:
    raw = _clean(raw)
    return raw if _DATE.fullmatch(raw) else ""


def _section_values(raw: str) -> list[str]:
    values = _clean(raw).split()
    if not values or any(not value.isdigit() or not 1 <= int(value) <= 10 for value in values):
        raise RuntimeError(f"palermo: invalid section cell {raw!r}")
    numbers = [int(value) for value in values]
    if numbers != sorted(set(numbers)):
        raise RuntimeError(f"palermo: non-monotonic or duplicate section cell {raw!r}")
    return [f"Sezione {value}" for value in numbers]


def _centre(word: dict[str, Any]) -> float:
    return (float(word["x0"]) + float(word["x1"])) / 2.0


def _load_words(path: Path) -> tuple[list[dict[str, Any]], list[str], list[tuple[float, float]]]:
    words: list[dict[str, Any]] = []
    page_texts: list[str] = []
    geometries: list[tuple[float, float]] = []
    offset = 0.0
    with pdfplumber.open(path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            geometries.append((round(float(page.width), 2), round(float(page.height), 2)))
            page_texts.append(_clean(page.extract_text() or ""))
            for source_word in page.extract_words(
                use_text_flow=False,
                keep_blank_chars=False,
                x_tolerance=1,
                y_tolerance=2,
            ):
                word = dict(source_word)
                word["page"] = page_number
                word["xc"] = _centre(word)
                word["gmid"] = offset + (float(word["top"]) + float(word["bottom"])) / 2.0
                words.append(word)
            offset += float(page.height)
    return words, page_texts, geometries


def _extract_rows(
    words: list[dict[str, Any]],
    *,
    ordinal_band: tuple[float, float],
    bands: dict[str, tuple[float, float]],
    expected_numbers: tuple[int, ...],
    outcome_near_anchor: bool,
) -> list[dict[str, Any]]:
    anchors: list[tuple[int, dict[str, Any]]] = []
    for word in words:
        text = str(word["text"])
        if ordinal_band[0] <= float(word["xc"]) < ordinal_band[1] and re.fullmatch(r"\d{1,4}", text):
            anchors.append((int(text), word))
    source_numbers = tuple(number for number, _word in anchors)
    if source_numbers != expected_numbers:
        raise RuntimeError(
            f"palermo: source row-number boundary drift; got {len(source_numbers)} rows and "
            f"gaps around {source_numbers[:5]} ... {source_numbers[-5:]}"
        )

    ordinary_gaps = [
        float(anchors[index + 1][1]["gmid"]) - float(anchors[index][1]["gmid"])
        for index in range(len(anchors) - 1)
        if float(anchors[index + 1][1]["gmid"]) - float(anchors[index][1]["gmid"]) < 100.0
    ]
    if not ordinary_gaps:
        raise RuntimeError("palermo: unable to establish row spacing")
    half_spacing = median(ordinary_gaps) / 2.0

    rows: list[dict[str, Any]] = []
    for index, (number, anchor) in enumerate(anchors):
        anchor_mid = float(anchor["gmid"])
        lower = (
            anchor_mid - half_spacing
            if index == 0
            else (float(anchors[index - 1][1]["gmid"]) + anchor_mid) / 2.0
        )
        upper = (
            anchor_mid + half_spacing
            if index + 1 == len(anchors)
            else (anchor_mid + float(anchors[index + 1][1]["gmid"])) / 2.0
        )
        segment = [
            word
            for word in words
            if lower <= float(word["gmid"]) < upper and word is not anchor
        ]
        row: dict[str, Any] = {"source_number": number, "page": int(anchor["page"])}
        for field, (x_min, x_max) in bands.items():
            selected = [word for word in segment if x_min <= float(word["xc"]) < x_max]
            if field == "outcome" and outcome_near_anchor:
                selected = [word for word in selected if abs(float(word["gmid"]) - anchor_mid) < 8.0]
            selected.sort(key=lambda word: (float(word["gmid"]), float(word["x0"])))
            row[field] = _clean(" ".join(str(word["text"]) for word in selected))
        rows.append(row)
    return rows


def _registered_office(row: dict[str, Any]) -> str:
    office = _clean(row["office"])
    address = _clean(row["address"])
    if office and address:
        return f"{office} — {address}"
    return office or address


def parse_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    words, page_texts, geometries = _load_words(path)
    if len(page_texts) != 55 or set(geometries) != {_LISTED_GEOMETRY}:
        raise RuntimeError(f"palermo_listed: page/geometry drift: {len(page_texts)} / {set(geometries)}")
    if "Ultima modifica: 18/09/2026" not in page_texts[0]:
        raise RuntimeError("palermo_listed: approved 18/09/2026 document marker missing")

    rows = _extract_rows(
        words,
        ordinal_band=(150.0, 180.0),
        bands=_LISTED_BANDS,
        expected_numbers=_LISTED_SOURCE_NUMBERS,
        outcome_near_anchor=False,
    )
    page_rows = Counter(int(row["page"]) for row in rows)
    observed_page_rows = tuple(page_rows[page] for page in range(1, 56))
    if observed_page_rows != _LISTED_PAGE_ROWS:
        raise RuntimeError(f"palermo_listed: page denominator drift: {observed_page_rows}")

    outcomes = Counter(str(row["outcome"]) for row in rows)
    if outcomes != _LISTED_OUTCOMES:
        raise RuntimeError(f"palermo_listed: outcome vocabulary drift: {dict(outcomes)}")

    malformed_cf = {
        int(row["source_number"]): str(row["cf"])
        for row in rows
        if row["cf"] and not _valid_identifier(str(row["cf"]))
    }
    malformed_vat = {
        int(row["source_number"]): str(row["vat"])
        for row in rows
        if row["vat"] and not _valid_identifier(str(row["vat"]))
    }
    if malformed_cf != _LISTED_MALFORMED_CF or malformed_vat != _LISTED_MALFORMED_VAT:
        raise RuntimeError(
            f"palermo_listed: identifier anomaly drift: cf={malformed_cf}, vat={malformed_vat}"
        )
    bad_expiry = {
        int(row["source_number"]): str(row["expiry"])
        for row in rows
        if not _DATE.fullmatch(str(row["expiry"]))
    }
    if bad_expiry != _LISTED_BAD_EXPIRY:
        raise RuntimeError(f"palermo_listed: expiry anomaly drift: {bad_expiry}")
    bad_listing = {
        int(row["source_number"]): str(row["listing"])
        for row in rows
        if not _DATE.fullmatch(str(row["listing"]))
    }
    if bad_listing:
        raise RuntimeError(f"palermo_listed: listing-date anomaly drift: {bad_listing}")

    records: list[dict[str, Any]] = []
    for row in rows:
        source_number = int(row["source_number"])
        sections = _section_values(str(row["activities"]))
        identifier_raw = _clean(f"{row['cf']} {row['vat']}")
        expiry_raw = str(row["expiry"])
        status = _listed_status(str(row["outcome"]))
        registered_office = _registered_office(row)
        source_fields: dict[str, Any] = {
            "sections": sections,
            "physical_locators": [f"page {row['page']}; source N° {source_number}"],
            "registered_office_variants": [registered_office],
            "listing_date_raw_variants": [str(row["listing"])],
            "expiry_date_raw_variants": [expiry_raw],
            "in_aggiornamento": str(row["outcome"]) if status == "renewal_update_in_progress" else "",
            "requested_activities_source": str(row["activities"]),
        }
        if row["secondary"]:
            source_fields["secondary_office_variants"] = [str(row["secondary"])]
        if row["outcome"] and status == "listed":
            source_fields["notes"] = [str(row["outcome"])]
        records.append(
            _record(
                cfg,
                source_number,
                name=str(row["name"]),
                office=registered_office,
                secondary=str(row["secondary"]),
                identifier_raw=identifier_raw,
                activities=sections,
                status=status,
                outcome_raw=str(row["outcome"]),
                listing_date=str(row["listing"]),
                expiry_date=_strict_date(expiry_raw),
                primary_date_label="Data iscrizione",
                source_fields=source_fields,
            )
        )

    identifier_coverage = sum(bool(record["identifiers"]) for record in records)
    if identifier_coverage != 924:
        raise RuntimeError(f"palermo_listed: structured identifier coverage drift: {identifier_coverage}")
    status_counts = Counter(record["source_status"] for record in records)
    expected_status = Counter({"listed": 486, "renewal_update_in_progress": 443})
    if status_counts != expected_status:
        raise RuntimeError(f"palermo_listed: normalised status drift: {dict(status_counts)}")

    return ParsedBatch(
        records,
        {
            "parser": "palermo_listed",
            "pages": 55,
            "public_records": 929,
            "status_counts": dict(status_counts),
            "identifier_coverage": identifier_coverage,
            "source_number_gaps": [252, 316],
            "malformed_identifier_fields": len(malformed_cf) + len(malformed_vat),
            "nonstandard_expiry_count": len(bad_expiry),
        },
    )


def parse_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    words, page_texts, geometries = _load_words(path)
    if len(page_texts) != 58 or set(geometries) != {_APPLICANT_GEOMETRY}:
        raise RuntimeError(
            f"palermo_applicants: page/geometry drift: {len(page_texts)} / {set(geometries)}"
        )
    if "Ultima modifica: 17/09/2026" not in page_texts[0]:
        raise RuntimeError("palermo_applicants: approved 17/09/2026 document marker missing")

    rows = _extract_rows(
        words,
        ordinal_band=(20.0, 45.0),
        bands=_APPLICANT_BANDS,
        expected_numbers=_APPLICANT_SOURCE_NUMBERS,
        outcome_near_anchor=True,
    )
    page_rows = Counter(int(row["page"]) for row in rows)
    observed_page_rows = tuple(page_rows[page] for page in range(1, 59))
    if observed_page_rows != _APPLICANT_PAGE_ROWS:
        raise RuntimeError(f"palermo_applicants: page denominator drift: {observed_page_rows}")

    outcomes = Counter(str(row["outcome"]) for row in rows)
    if outcomes != _APPLICANT_OUTCOMES:
        raise RuntimeError(f"palermo_applicants: outcome vocabulary drift: {dict(outcomes)}")

    malformed_cf = {
        int(row["source_number"]): str(row["cf"])
        for row in rows
        if row["cf"] and not _valid_identifier(str(row["cf"]))
    }
    malformed_vat = {
        int(row["source_number"]): str(row["vat"])
        for row in rows
        if row["vat"] and not _valid_identifier(str(row["vat"]))
    }
    if malformed_cf != _APPLICANT_MALFORMED_CF or malformed_vat != _APPLICANT_MALFORMED_VAT:
        raise RuntimeError(
            f"palermo_applicants: identifier anomaly drift: cf={malformed_cf}, vat={malformed_vat}"
        )

    records: list[dict[str, Any]] = []
    for row in rows:
        source_number = int(row["source_number"])
        sections = _section_values(str(row["activities"]))
        identifier_raw = _clean(f"{row['cf']} {row['vat']}")
        status = _applicant_status(str(row["outcome"]))
        registered_office = _registered_office(row)
        source_fields: dict[str, Any] = {
            "sections": sections,
            "physical_locators": [f"page {row['page']}; source N° {source_number}"],
            "registered_office_variants": [registered_office],
            "requested_activities_source": str(row["activities"]),
            "outcome": {
                "status": str(row["outcome"]),
                "observed_listing_date": "",
                "observed_expiry_date": "",
                "renewal_requested": False,
                "update_in_progress": False,
                "dates": [],
            },
        }
        if row["secondary"]:
            source_fields["secondary_office_variants"] = [str(row["secondary"])]
        records.append(
            _record(
                cfg,
                source_number,
                name=str(row["name"]),
                office=registered_office,
                secondary=str(row["secondary"]),
                identifier_raw=identifier_raw,
                activities=sections,
                status=status,
                outcome_raw=str(row["outcome"]),
                primary_date_label="",
                source_fields=source_fields,
            )
        )

    identifier_coverage = sum(bool(record["identifiers"]) for record in records)
    if identifier_coverage != 606:
        raise RuntimeError(f"palermo_applicants: structured identifier coverage drift: {identifier_coverage}")
    if sum(not record["registered_office"] for record in records) != 0:
        raise RuntimeError("palermo_applicants: empty registered-office observation")
    status_counts = Counter(record["source_status"] for record in records)
    if status_counts != Counter({"pending": 609}):
        raise RuntimeError(f"palermo_applicants: normalised status drift: {dict(status_counts)}")

    return ParsedBatch(
        records,
        {
            "parser": "palermo_applicants",
            "pages": 58,
            "public_records": 609,
            "status_counts": dict(status_counts),
            "identifier_coverage": identifier_coverage,
            "malformed_identifier_fields": len(malformed_cf) + len(malformed_vat),
        },
    )


PARSERS = {
    "palermo_listed": parse_listed,
    "palermo_applicants": parse_applicants,
}
