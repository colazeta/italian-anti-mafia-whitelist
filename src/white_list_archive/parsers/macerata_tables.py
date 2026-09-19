from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

import pdfplumber

from white_list_archive.parsers.multi_prefecture_tables import (
    ParsedBatch,
    _activities,
    _clean,
    _record,
)

_DATE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
_EXPECTED_LISTED_PAGE_ROWS = (
    38, 45, 45, 45, 46, 46, 45, 40, 38, 45, 46, 44, 36, 45, 46, 45, 46, 46, 40, 41,
    34, 44, 44, 46, 37, 39, 45, 43, 45, 46, 46, 45, 39, 36, 45, 45, 46, 44, 38, 43,
    46, 46, 37, 40, 37, 45, 45, 46, 46, 44,
)
_EXPECTED_SECTIONS = (
    "SEZIONE I - ESTRAZIONE FORNITURA E TRASPORTO DI TERRA E MATERIALI INERTI",
    "SEZIONE II - CONFEZIONAMENTO, FORNITURA E TRASPORTO DI CALCESTRUZZO IN BITUME",
    "SEZIONE III- NOLI A FREDDO DI MACCHINARI",
    "SEZIONE IV - FORNITURA DI FERRO LAVORATO",
    "SEZIONE V - NOLI A CALDO",
    "SEZIONE VI - AUTOTRASPORTO PER CONTO TERZI",
    "SEZIONE VII- GUARDIANIA DEI CANTIERI",
    "SEZIONE VIII - SERVIZI FUNERARI E CIMITERIALI",
    "SEZIONE IX - RISTORAZIONE, GESTIONE DELLE MENSE E CATERING",
    "SEZIONE X - SERVIZI AMBIENTALI, COMPRESE LE ATTIVITA' DI RACCOLTA, DI TRASPORTO NAZIONALE E TRANSFRONTALIERO, ANCHE PER CONTO DI TERZI, DI TRATTAMENTO E DI SMALTIMENTO RIFIUTI, NONCHE' LE ATTIVITA' DI RISANAMENTOE E DI BONIFICA E GLI ALTRI SERVIZI COMMESSI ALLA GESTIONE DEI RIFIUTI",
)
_EXPECTED_LISTED_RAW_STATUS = Counter(
    {
        "": 879,
        "in corso rinnovo": 284,
        "In corso rinnovo": 104,
        "IN corso rinnovo": 3,
        "iN corso rinnovo": 1,
        "in corso rinnnovo": 1,
        "in corsi rinnovo": 1,
        "i": 1,
    }
)
_EXPECTED_LISTED_MALFORMED_IDENTIFIERS = {
    207: "0125030430",
    228: "0210970438",
    284: "1749820435 2073570430",
    285: "",
    314: "LVR61L13B474B",
    334: "008367407431",
    337: "1625520430 1841650433",
    338: "",
    367: "1859540435",
    378: "01440590436 01944400439 1350050439",
    379: "",
    380: "",
    397: "2091000436",
    431: "1427540438",
    461: "013774440434",
    561: "2095540437",
    579: "1554240430",
    602: "0156253034",
    605: "2088330432",
    684: "01440590436 1350050439",
    685: "",
    689: "00948/570437",
    732: "0614750585",
    772: "1374440434",
    828: "",
    833: "0128608435",
    839: "1454380435",
    842: "0210970438",
    895: "2121320432",
    920: "1961700430",
    973: "006595830430",
    1045: "0755171008",
    1139: "0147260435",
    1166: "019132020432",
    1194: "",
    1199: "020197010439",
    1231: "014950804323",
}
_EXPECTED_NONSTANDARD_EXPIRY = {
    219: "",
    265: "",
    310: "",
    350: "",
    409: "",
    720: "",
    838: "",
    884: "ISCRIZIONE 05/01/2027",
    1054: "",
    1274: "",
}
_EXPECTED_APPLICANT_PAGE_ROWS = (3, 5, 4, 5, 5, 4, 5, 3, 5, 5, 5, 3, 5, 3, 5, 5, 4, 3, 5, 2)
_EXPECTED_APPLICANT_MALFORMED_IDENTIFIERS = {
    7: "0195302433",
    20: "009874300442",
    27: "0219970444",
    57: "0085180435",
}
_EXPECTED_APPLICANT_BAD_DATES = {34: "27/01/206"}
_EXPECTED_APPLICANT_OUTCOMES = Counter({"": 83, "Iscritta il 14/08/2026": 1})


def _cells(row: list[Any]) -> list[str]:
    return [_clean(value) for value in row]


def _valid_identifier(value: str) -> bool:
    return (value.isdigit() and len(value) == 11) or (len(value) == 16 and value.isalnum())


def _section_activity(section: str) -> str:
    return re.sub(r"^SEZIONE\s+[IVX]+\s*-?\s*", "", section, flags=re.I).strip() or section


def _listed_status(raw: str) -> str:
    folded = _clean(raw).casefold()
    if not folded:
        return "listed"
    if folded in {"in corso rinnovo", "in corso rinnnovo", "in corsi rinnovo"}:
        return "renewal_update_in_progress"
    if raw == "i":
        return "other_or_unknown"
    raise RuntimeError(f"macerata_listed: unapproved update/status value {raw!r}")


def parse_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    sector_rows: list[tuple[int, str, list[str]]] = []
    observed_sections: list[str] = []
    page_rows: list[int] = []
    current_section = ""

    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != 50:
            raise RuntimeError(f"macerata_listed: expected 50 pages, got {len(pdf.pages)}")
        for page_number, page in enumerate(pdf.pages, start=1):
            count = 0
            tables = page.extract_tables()
            if len(tables) != 1:
                raise RuntimeError(
                    f"macerata_listed: page {page_number} expected one table, got {len(tables)}"
                )
            for raw_row in tables[0]:
                row = _cells(raw_row)
                if len(row) != 8:
                    raise RuntimeError(
                        f"macerata_listed: page {page_number} unexpected column count {len(row)}"
                    )
                if row[0].upper().startswith("SEZIONE ") and not any(row[1:]):
                    current_section = row[0]
                    observed_sections.append(current_section)
                    continue
                if _DATE.fullmatch(row[5] or ""):
                    if not current_section:
                        raise RuntimeError(
                            f"macerata_listed: company row before section on page {page_number}"
                        )
                    sector_rows.append((page_number, current_section, row))
                    count += 1
            page_rows.append(count)

    if tuple(page_rows) != _EXPECTED_LISTED_PAGE_ROWS:
        raise RuntimeError(f"macerata_listed: page denominator drift: {page_rows}")
    if tuple(observed_sections) != _EXPECTED_SECTIONS:
        raise RuntimeError(f"macerata_listed: section boundary drift: {observed_sections}")
    if len(sector_rows) != 2150:
        raise RuntimeError(f"macerata_listed: expected 2150 sector rows, got {len(sector_rows)}")

    grouped: dict[tuple[str, ...], dict[str, Any]] = {}
    for page_number, section, row in sector_rows:
        key = tuple(row)
        group = grouped.setdefault(key, {"row": row, "sections": [], "locators": []})
        if section not in group["sections"]:
            group["sections"].append(section)
        group["locators"].append(f"page {page_number}; {section}")

    if len(grouped) != 1274:
        raise RuntimeError(f"macerata_listed: expected 1274 observations, got {len(grouped)}")
    raw_statuses = Counter(key[7] for key in grouped)
    if raw_statuses != _EXPECTED_LISTED_RAW_STATUS:
        raise RuntimeError(f"macerata_listed: grouped status vocabulary drift: {dict(raw_statuses)}")

    malformed: dict[int, str] = {}
    nonstandard_expiry: dict[int, str] = {}
    records: list[dict[str, Any]] = []
    for ordinal, group in enumerate(grouped.values(), start=1):
        row = group["row"]
        identifier_raw = row[4]
        if not _valid_identifier(identifier_raw):
            malformed[ordinal] = identifier_raw
        expiry_raw = row[6]
        if not _DATE.fullmatch(expiry_raw or ""):
            nonstandard_expiry[ordinal] = expiry_raw
        status = _listed_status(row[7])
        records.append(
            _record(
                cfg,
                ordinal,
                name=row[0],
                office=row[1],
                secondary=row[3],
                identifier_raw=identifier_raw,
                activities=[_section_activity(value) for value in group["sections"]],
                status=status,
                outcome_raw=row[7],
                listing_date=row[5],
                expiry_date=expiry_raw if _DATE.fullmatch(expiry_raw or "") else "",
                primary_date_label="Data iscrizione",
                source_fields={
                    "sections": list(group["sections"]),
                    "physical_locators": list(group["locators"]),
                    "listing_date_raw_variants": [row[5]],
                    "expiry_date_raw_variants": [expiry_raw] if expiry_raw else [],
                    "in_aggiornamento": row[7],
                },
            )
        )

    if malformed != _EXPECTED_LISTED_MALFORMED_IDENTIFIERS:
        raise RuntimeError(f"macerata_listed: malformed identifier boundary drift: {malformed}")
    if nonstandard_expiry != _EXPECTED_NONSTANDARD_EXPIRY:
        raise RuntimeError(f"macerata_listed: nonstandard expiry boundary drift: {nonstandard_expiry}")
    if sum(bool(record["identifiers"]) for record in records) != 1240:
        raise RuntimeError("macerata_listed: structured identifier coverage drift")
    status_counts = Counter(record["source_status"] for record in records)
    expected_status = Counter({"listed": 879, "renewal_update_in_progress": 394, "other_or_unknown": 1})
    if status_counts != expected_status:
        raise RuntimeError(f"macerata_listed: normalised status drift: {dict(status_counts)}")

    return ParsedBatch(
        records,
        {
            "parser": "macerata_listed",
            "pages": 50,
            "sector_rows": 2150,
            "public_records": 1274,
            "status_counts": dict(status_counts),
            "identifier_coverage": 1240,
            "malformed_identifier_count": len(malformed),
            "nonstandard_expiry_count": len(nonstandard_expiry),
        },
    )


def _applicant_status(outcome: str) -> tuple[str, str]:
    if not outcome:
        return "pending", ""
    match = re.fullmatch(r"Iscritta il (\d{2}/\d{2}/\d{4})", outcome)
    if match:
        return "listed", match.group(1)
    raise RuntimeError(f"macerata_applicants: unapproved outcome {outcome!r}")


def parse_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    source_rows: list[dict[str, Any]] = []
    page_rows: list[int] = []
    continuation_pages: list[int] = []

    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != 20:
            raise RuntimeError(f"macerata_applicants: expected 20 pages, got {len(pdf.pages)}")
        for page_number, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables()
            if len(tables) != 1:
                raise RuntimeError(
                    f"macerata_applicants: page {page_number} expected one table, got {len(tables)}"
                )
            count = 0
            for table_row_number, raw_row in enumerate(tables[0], start=1):
                row = _cells(raw_row)
                if len(row) != 6:
                    raise RuntimeError(
                        f"macerata_applicants: page {page_number} unexpected column count {len(row)}"
                    )
                if row[0].casefold().startswith("ragione sociale"):
                    continue
                if row[0]:
                    source_rows.append(
                        {
                            "page": page_number,
                            "table_row": table_row_number,
                            "row": row,
                            "activity_fragments": [row[3]] if row[3] else [],
                            "locators": [f"page {page_number}; table row {table_row_number}"],
                        }
                    )
                    count += 1
                    continue
                if row[3] and source_rows:
                    source_rows[-1]["activity_fragments"].append(row[3])
                    source_rows[-1]["locators"].append(
                        f"page {page_number}; table row {table_row_number}; continuation"
                    )
                    continuation_pages.append(page_number)
                    continue
                if any(row):
                    raise RuntimeError(
                        f"macerata_applicants: unreviewed non-company row on page {page_number}: {row!r}"
                    )
            page_rows.append(count)

    if tuple(page_rows) != _EXPECTED_APPLICANT_PAGE_ROWS:
        raise RuntimeError(f"macerata_applicants: page denominator drift: {page_rows}")
    if continuation_pages != [8, 12, 20]:
        raise RuntimeError(f"macerata_applicants: continuation-page drift: {continuation_pages}")
    if len(source_rows) != 84:
        raise RuntimeError(f"macerata_applicants: expected 84 observations, got {len(source_rows)}")

    outcomes = Counter(item["row"][5] for item in source_rows)
    if outcomes != _EXPECTED_APPLICANT_OUTCOMES:
        raise RuntimeError(f"macerata_applicants: outcome vocabulary drift: {dict(outcomes)}")

    malformed: dict[int, str] = {}
    bad_dates: dict[int, str] = {}
    records: list[dict[str, Any]] = []
    for ordinal, item in enumerate(source_rows, start=1):
        row = item["row"]
        identifier_raw = row[2]
        if not _valid_identifier(identifier_raw):
            malformed[ordinal] = identifier_raw
        application_raw = row[4]
        if not _DATE.fullmatch(application_raw or ""):
            bad_dates[ordinal] = application_raw
        status, listing_raw = _applicant_status(row[5])
        activity_source = _clean(" ".join(item["activity_fragments"]))
        activities = [value for value in _activities(activity_source) if value and value != "-"]
        records.append(
            _record(
                cfg,
                ordinal,
                name=row[0],
                office=row[1],
                identifier_raw=identifier_raw,
                activities=activities,
                status=status,
                outcome_raw=row[5],
                application_date=application_raw if _DATE.fullmatch(application_raw or "") else "",
                listing_date=listing_raw,
                primary_date_label="Data presentazione istanza",
                source_fields={
                    "physical_locators": list(item["locators"]),
                    "requested_activities_source": activity_source,
                    "application_date_raw_variants": [application_raw] if application_raw else [],
                    "notes": [row[5]] if row[5] else [],
                },
            )
        )

    if malformed != _EXPECTED_APPLICANT_MALFORMED_IDENTIFIERS:
        raise RuntimeError(f"macerata_applicants: malformed identifier boundary drift: {malformed}")
    if bad_dates != _EXPECTED_APPLICANT_BAD_DATES:
        raise RuntimeError(f"macerata_applicants: application-date boundary drift: {bad_dates}")
    if sum(bool(record["identifiers"]) for record in records) != 80:
        raise RuntimeError("macerata_applicants: structured identifier coverage drift")
    status_counts = Counter(record["source_status"] for record in records)
    if status_counts != Counter({"pending": 83, "listed": 1}):
        raise RuntimeError(f"macerata_applicants: normalised status drift: {dict(status_counts)}")

    return ParsedBatch(
        records,
        {
            "parser": "macerata_applicants",
            "pages": 20,
            "public_records": 84,
            "status_counts": dict(status_counts),
            "identifier_coverage": 80,
            "malformed_identifier_count": len(malformed),
            "reviewed_bad_application_dates": len(bad_dates),
        },
    )


PARSERS = {
    "macerata_listed": parse_listed,
    "macerata_applicants": parse_applicants,
}
