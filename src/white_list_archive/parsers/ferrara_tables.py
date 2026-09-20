from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Mapping

import pdfplumber

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _clean, _record

PARSER_VERSION = "1"

_EXPECTED_ORDINARY_PAGES = 87
_EXPECTED_ORDINARY_RECORDS = 868
_EXPECTED_ORDINARY_CONTINUATIONS = 28
_EXPECTED_ORDINARY_STATUS_COUNTS = {
    "listed": 717,
    "renewal_update_in_progress": 150,
    "other_or_unknown": 1,
}
_EXPECTED_ORDINARY_IDENTIFIER_COVERAGE = 860
_EXPECTED_ORDINARY_DATE_ANOMALIES = 2

_EXPECTED_APPLICANT_PAGES = 5
_EXPECTED_APPLICANT_RECORDS = 21
_EXPECTED_APPLICANT_IDENTIFIER_COVERAGE = 21
_EXPECTED_EMPTY_APPLICANT_PAGES = {5}

_RECONSTRUCTION_SECTORS = {
    "A": ("fornitura moduli prefabbricati e relativi arredi", 8),
    "B": ("demolizione edifici e altre strutture", 35),
    "C": ("movimenti di terra", 23),
    "D": ("noleggio con conducente mezzi speciali", 7),
    "E": ("fornitura e posa impianti fotovoltaici", 13),
    "F": ("fornitura e manutenzione impianti tecnologici", 14),
    "G": ("fornitura beni necessari alla ricostruzione", 3),
}
_EXPECTED_RECONSTRUCTION_PHYSICAL = 1161
_EXPECTED_RECONSTRUCTION_LOGICAL = 697
_EXPECTED_RECONSTRUCTION_STATUS_COUNTS = {
    "listed": 542,
    "renewal_update_in_progress": 153,
    "other_or_unknown": 2,
}
_EXPECTED_RECONSTRUCTION_IDENTIFIER_COVERAGE = 683
_EXPECTED_RECONSTRUCTION_MULTI_SECTOR_GROUPS = 282
_EXPECTED_RECONSTRUCTION_DATE_ANOMALIES = 15
_EXPECTED_RECONSTRUCTION_EMPTY_PAGES = {("C", 23)}

_STRICT_ID = re.compile(r"^(?:[0-9]{11}|[A-Z0-9]{16})$")
_CANONICAL_DATE = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")


def _fold(value: str) -> str:
    value = unicodedata.normalize("NFKD", _clean(value))
    return "".join(ch for ch in value if not unicodedata.combining(ch)).casefold()


def _strict_identifiers(value: str) -> list[str]:
    upper = _clean(value).upper()
    compact = re.sub(r"[^0-9A-Z]", "", upper)
    found = re.findall(r"(?<![0-9A-Z])(?:[0-9]{11}|[A-Z0-9]{16})(?![0-9A-Z])", upper)
    if len(compact) in (11, 16) and _STRICT_ID.fullmatch(compact) and compact not in found:
        found.append(compact)
    return list(dict.fromkeys(found))


def _normalise_date_or_blank(raw_value: str) -> str:
    """Normalise only exact dd/mm/yyyy source values; preserve every anomaly raw."""
    raw = _clean(raw_value)
    if not raw:
        return ""
    match = _CANONICAL_DATE.fullmatch(raw)
    if not match:
        return ""
    day, month, year = map(int, match.groups())
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return ""


def _date_is_anomalous(raw_value: str) -> bool:
    raw = _clean(raw_value)
    return bool(raw) and not bool(_normalise_date_or_blank(raw))


def _status(note: str) -> str:
    folded = _fold(note)
    if not folded:
        return "listed"
    if "rinnovo" in folded or "rinovo" in folded:
        return "renewal_update_in_progress"
    return "other_or_unknown"


def _is_header(row: list[str]) -> bool:
    joined = _fold(" | ".join(row))
    return (
        ("denominazione" in joined or "ragione sociale" in joined)
        and ("c.f" in joined or "p.iva" in joined or "partita iva" in joined)
    )


def _is_ordinary_structural(row: list[str]) -> bool:
    first = _fold(row[0]) if row else ""
    joined = _fold(" | ".join(row))
    return (
        first.startswith("prefettura di ferrara")
        or first.startswith("sezione ")
        or "elenco dei fornitori, prestatori di servizi" in joined
    )


def _is_reconstruction_structural(row: list[str]) -> bool:
    joined = _fold(" | ".join(row))
    return (
        ("prefettura" in joined and "ferrara" in joined)
        or "white list" in joined
        or ("art. 1" in joined and "legge" in joined)
        or ("elenco" in joined and ("imprese" in joined or "fornitori" in joined))
    )


def _is_applicant_title(row: list[str]) -> bool:
    joined = _fold(" | ".join(row))
    return "white list" in joined and "elenco imprese richiedenti" in joined


def _validate_cfg(cfg: dict[str, Any], expected_source_key: str) -> None:
    if cfg.get("source_key") != expected_source_key:
        raise RuntimeError(
            f"Ferrara parser/source mismatch: {cfg.get('source_key')!r} != {expected_source_key!r}"
        )
    if cfg.get("authority_key") != "ferrara":
        raise RuntimeError("Ferrara parser bound to a non-Ferrara authority")


def parse_ferrara_ordinary(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(cfg, "ferrara-provincial-listed")
    rows: list[dict[str, Any]] = []
    continuations = 0
    current: dict[str, Any] | None = None
    unclassified: list[tuple[str, list[str]]] = []

    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _EXPECTED_ORDINARY_PAGES:
            raise RuntimeError(
                f"Ferrara ordinary page-count drift: {len(pdf.pages)} != {_EXPECTED_ORDINARY_PAGES}"
            )
        for page_number, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables() or []
            if len(tables) != 1:
                raise RuntimeError(f"Ferrara ordinary table-count drift page={page_number}: {len(tables)}")
            for row_number, raw in enumerate(tables[0] or [], start=1):
                cells = [_clean(value) for value in raw]
                if not any(cells):
                    continue
                if len(cells) != 7:
                    raise RuntimeError(
                        f"Ferrara ordinary column-count drift page={page_number} row={row_number}: {len(cells)}"
                    )
                locator = f"p{page_number}:r{row_number}"
                if _is_header(cells) or _is_ordinary_structural(cells):
                    current = None
                    continue
                name, office, secondary, identifier_raw, listed_raw, expiry_raw, note = cells
                if identifier_raw and expiry_raw:
                    current = {
                        "name": name,
                        "office": office,
                        "secondary": secondary,
                        "identifier_raw": identifier_raw,
                        "listed_raw": listed_raw,
                        "expiry_raw": expiry_raw,
                        "note": note,
                        "physical_locators": [locator],
                    }
                    rows.append(current)
                    continue
                if current is not None and not identifier_raw and not listed_raw and not expiry_raw:
                    if any((name, office, secondary, note)):
                        for key, value in (
                            ("name", name),
                            ("office", office),
                            ("secondary", secondary),
                            ("note", note),
                        ):
                            if value:
                                current[key] = _clean(f"{current[key]} {value}")
                        current["physical_locators"].append(locator)
                        continuations += 1
                        continue
                unclassified.append((locator, cells))

    if unclassified:
        raise RuntimeError(f"Ferrara ordinary unclassified source rows: {unclassified!r}")
    if len(rows) != _EXPECTED_ORDINARY_RECORDS:
        raise RuntimeError(
            f"Ferrara ordinary observation drift: {len(rows)} != {_EXPECTED_ORDINARY_RECORDS}"
        )
    if continuations != _EXPECTED_ORDINARY_CONTINUATIONS:
        raise RuntimeError(
            f"Ferrara ordinary continuation drift: {continuations} != {_EXPECTED_ORDINARY_CONTINUATIONS}"
        )

    records: list[dict[str, Any]] = []
    anomaly_count = 0
    for row in rows:
        listing_date = _normalise_date_or_blank(row["listed_raw"])
        expiry_date = _normalise_date_or_blank(row["expiry_raw"])
        anomaly_count += int(_date_is_anomalous(row["listed_raw"]))
        anomaly_count += int(_date_is_anomalous(row["expiry_raw"]))
        record = _record(
            cfg,
            len(records) + 1,
            name=row["name"],
            office=row["office"],
            secondary=row["secondary"],
            identifier_raw=row["identifier_raw"],
            status=_status(row["note"]),
            outcome_raw=row["note"],
            listing_date=listing_date,
            expiry_date=expiry_date,
            source_fields={
                "listing_date_raw": row["listed_raw"],
                "expiry_date_raw": row["expiry_raw"],
                "notes": [row["note"]] if row["note"] else [],
                "physical_locators": list(row["physical_locators"]),
            },
        )
        record["identifiers"] = _strict_identifiers(row["identifier_raw"])
        records.append(record)

    status_counts = dict(Counter(record["source_status"] for record in records))
    identifier_coverage = sum(bool(record["identifiers"]) for record in records)
    if status_counts != _EXPECTED_ORDINARY_STATUS_COUNTS:
        raise RuntimeError(f"Ferrara ordinary status drift: {status_counts!r}")
    if identifier_coverage != _EXPECTED_ORDINARY_IDENTIFIER_COVERAGE:
        raise RuntimeError(
            f"Ferrara ordinary identifier-coverage drift: {identifier_coverage} != {_EXPECTED_ORDINARY_IDENTIFIER_COVERAGE}"
        )
    if anomaly_count != _EXPECTED_ORDINARY_DATE_ANOMALIES:
        raise RuntimeError(
            f"Ferrara ordinary date-anomaly drift: {anomaly_count} != {_EXPECTED_ORDINARY_DATE_ANOMALIES}"
        )

    return ParsedBatch(
        records=records,
        diagnostics={
            "parser": "ferrara_ordinary",
            "parser_version": PARSER_VERSION,
            "source_pages": _EXPECTED_ORDINARY_PAGES,
            "public_records": len(records),
            "continuation_rows": continuations,
            "status_counts": status_counts,
            "identifier_coverage": identifier_coverage,
            "date_anomalies": anomaly_count,
        },
    )


def parse_ferrara_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(cfg, "ferrara-provincial-applicants")
    rows: list[dict[str, str]] = []
    empty_pages: set[int] = set()
    unclassified: list[tuple[str, list[str]]] = []

    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _EXPECTED_APPLICANT_PAGES:
            raise RuntimeError(
                f"Ferrara applicant page-count drift: {len(pdf.pages)} != {_EXPECTED_APPLICANT_PAGES}"
            )
        for page_number, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables() or []
            if not tables:
                text = _clean(page.extract_text() or "")
                words = page.extract_words() or []
                if page_number not in _EXPECTED_EMPTY_APPLICANT_PAGES or text or words:
                    raise RuntimeError(
                        f"Ferrara applicant unexpected table gap page={page_number}: text={text!r} words={len(words)}"
                    )
                empty_pages.add(page_number)
                continue
            if len(tables) != 1:
                raise RuntimeError(f"Ferrara applicant table-count drift page={page_number}: {len(tables)}")
            for row_number, raw in enumerate(tables[0] or [], start=1):
                cells = [_clean(value) for value in raw]
                if not any(cells):
                    continue
                locator = f"p{page_number}:r{row_number}"
                if _is_header(cells) or _is_applicant_title(cells):
                    continue
                if len(cells) == 6:
                    name, office, secondary, identifier_raw, application_raw, activities = cells
                elif len(cells) == 8 and not cells[0] and not cells[-1]:
                    _, name, office, secondary, identifier_raw, application_raw, activities, _ = cells
                else:
                    unclassified.append((locator, cells))
                    continue
                if not all((name, office, identifier_raw, application_raw, activities)):
                    unclassified.append((locator, cells))
                    continue
                rows.append(
                    {
                        "name": name,
                        "office": office,
                        "secondary": secondary,
                        "identifier_raw": identifier_raw,
                        "application_raw": application_raw,
                        "activities": activities,
                        "physical_locator": locator,
                    }
                )

    if empty_pages != _EXPECTED_EMPTY_APPLICANT_PAGES:
        raise RuntimeError(f"Ferrara applicant empty-page drift: {empty_pages!r}")
    if unclassified:
        raise RuntimeError(f"Ferrara applicant unclassified source rows: {unclassified!r}")
    if len(rows) != _EXPECTED_APPLICANT_RECORDS:
        raise RuntimeError(
            f"Ferrara applicant observation drift: {len(rows)} != {_EXPECTED_APPLICANT_RECORDS}"
        )

    records: list[dict[str, Any]] = []
    for row in rows:
        application_date = _normalise_date_or_blank(row["application_raw"])
        if not application_date:
            raise RuntimeError(f"Ferrara unreviewed applicant application date: {row['application_raw']!r}")
        record = _record(
            cfg,
            len(records) + 1,
            name=row["name"],
            office=row["office"],
            secondary=row["secondary"],
            identifier_raw=row["identifier_raw"],
            activities=[row["activities"]],
            status="pending",
            application_date=application_date,
            primary_date_label="Data presentazione istanza",
            source_fields={
                "application_date_raw": row["application_raw"],
                "requested_activities_source": row["activities"],
                "physical_locators": [row["physical_locator"]],
                "shared_publication_no_duplicate_ingest": True,
                "logical_series": [
                    "ferrara-provincial-applicants",
                    "ferrara-reconstruction-applicants",
                ],
            },
        )
        record["identifiers"] = _strict_identifiers(row["identifier_raw"])
        records.append(record)

    identifier_coverage = sum(bool(record["identifiers"]) for record in records)
    if identifier_coverage != _EXPECTED_APPLICANT_IDENTIFIER_COVERAGE:
        raise RuntimeError(
            f"Ferrara applicant identifier-coverage drift: {identifier_coverage} != {_EXPECTED_APPLICANT_IDENTIFIER_COVERAGE}"
        )
    return ParsedBatch(
        records=records,
        diagnostics={
            "parser": "ferrara_applicants",
            "parser_version": PARSER_VERSION,
            "source_pages": _EXPECTED_APPLICANT_PAGES,
            "public_records": len(records),
            "status_counts": {"pending": len(records)},
            "identifier_coverage": identifier_coverage,
            "shared_publication_no_duplicate_ingest": True,
        },
    )


def _parse_reconstruction_physical(paths: Mapping[str, Path]) -> list[dict[str, Any]]:
    if set(paths) != set(_RECONSTRUCTION_SECTORS):
        raise RuntimeError(
            f"Ferrara reconstruction sector set drift: {sorted(paths)!r} != {sorted(_RECONSTRUCTION_SECTORS)!r}"
        )
    physical: list[dict[str, Any]] = []
    seen_empty_pages: set[tuple[str, int]] = set()
    unclassified: list[tuple[str, str, list[str]]] = []

    for sector in sorted(_RECONSTRUCTION_SECTORS):
        activity, expected_pages = _RECONSTRUCTION_SECTORS[sector]
        current: dict[str, Any] | None = None
        with pdfplumber.open(paths[sector]) as pdf:
            if len(pdf.pages) != expected_pages:
                raise RuntimeError(
                    f"Ferrara reconstruction page-count drift sector={sector}: {len(pdf.pages)} != {expected_pages}"
                )
            for page_number, page in enumerate(pdf.pages, start=1):
                tables = page.extract_tables() or []
                if len(tables) != 1:
                    text = _clean(page.extract_text() or "")
                    words = page.extract_words() or []
                    key = (sector, page_number)
                    if key in _EXPECTED_RECONSTRUCTION_EMPTY_PAGES and not tables and not text and not words:
                        seen_empty_pages.add(key)
                        continue
                    raise RuntimeError(
                        f"Ferrara reconstruction table-count drift sector={sector} page={page_number}: "
                        f"tables={len(tables)} text={text!r} words={len(words)}"
                    )
                for table_number, table in enumerate(tables, start=1):
                    for row_number, raw in enumerate(table or [], start=1):
                        cells = [_clean(value) for value in raw]
                        if not any(cells):
                            continue
                        if len(cells) != 6:
                            raise RuntimeError(
                                f"Ferrara reconstruction column-count drift sector={sector} page={page_number} "
                                f"row={row_number}: {len(cells)}"
                            )
                        locator = f"{sector}:p{page_number}:t{table_number}:r{row_number}"
                        if _is_header(cells) or _is_reconstruction_structural(cells):
                            current = None
                            continue
                        name, office, identifier_raw, listed_raw, expiry_raw, note = cells
                        if name and identifier_raw and expiry_raw:
                            current = {
                                "sector": sector,
                                "activity": activity,
                                "name": name,
                                "office": office,
                                "identifier_raw": identifier_raw,
                                "listed_raw": listed_raw,
                                "expiry_raw": expiry_raw,
                                "note": note,
                                "physical_locators": [locator],
                            }
                            physical.append(current)
                            continue
                        if current is not None and not identifier_raw and not listed_raw and not expiry_raw and any((name, office, note)):
                            for key_name, value in (("name", name), ("office", office), ("note", note)):
                                if value:
                                    current[key_name] = _clean(f"{current[key_name]} {value}")
                            current["physical_locators"].append(locator)
                            continue
                        unclassified.append((sector, locator, cells))

    if seen_empty_pages != _EXPECTED_RECONSTRUCTION_EMPTY_PAGES:
        raise RuntimeError(f"Ferrara reconstruction empty-page drift: {seen_empty_pages!r}")
    if unclassified:
        raise RuntimeError(f"Ferrara reconstruction unclassified source rows: {unclassified!r}")
    if len(physical) != _EXPECTED_RECONSTRUCTION_PHYSICAL:
        raise RuntimeError(
            f"Ferrara reconstruction physical-row drift: {len(physical)} != {_EXPECTED_RECONSTRUCTION_PHYSICAL}"
        )
    return physical


def parse_ferrara_reconstruction_bundle(
    paths: Mapping[str, Path], cfg: dict[str, Any]
) -> ParsedBatch:
    """Parse the seven content-addressed reconstruction PDFs as one logical source.

    This deliberately accepts a bundle rather than hiding network access inside a
    parser. The publication layer must acquire and hash every member explicitly
    before calling this function.
    """
    _validate_cfg(cfg, "ferrara-reconstruction-listed")
    physical = _parse_reconstruction_physical(paths)

    groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in physical:
        listing_norm = _normalise_date_or_blank(row["listed_raw"])
        expiry_norm = _normalise_date_or_blank(row["expiry_raw"])
        listing_semantic = listing_norm or (f"RAW:{_clean(row['listed_raw'])}" if row["listed_raw"] else "")
        expiry_semantic = expiry_norm or (f"RAW:{_clean(row['expiry_raw'])}" if row["expiry_raw"] else "")
        groups[(row["identifier_raw"].casefold(), listing_semantic, expiry_semantic, _status(row["note"]))].append(row)

    if len(groups) != _EXPECTED_RECONSTRUCTION_LOGICAL:
        raise RuntimeError(
            f"Ferrara reconstruction logical-row drift: {len(groups)} != {_EXPECTED_RECONSTRUCTION_LOGICAL}"
        )

    records: list[dict[str, Any]] = []
    multi_sector_groups = 0
    date_anomalies = 0
    for _key, members in sorted(groups.items(), key=lambda item: item[0]):
        sectors = sorted({member["sector"] for member in members})
        activities = [
            _RECONSTRUCTION_SECTORS[sector][0]
            for sector in sectors
        ]
        if len(sectors) > 1:
            multi_sector_groups += 1
        representative = sorted(
            members,
            key=lambda member: (
                member["sector"], member["name"].casefold(), member["office"].casefold(),
                member["physical_locators"][0],
            ),
        )[0]
        listing_date = _normalise_date_or_blank(representative["listed_raw"])
        expiry_date = _normalise_date_or_blank(representative["expiry_raw"])
        if _date_is_anomalous(representative["listed_raw"]) or _date_is_anomalous(representative["expiry_raw"]):
            date_anomalies += 1
        names = sorted({_clean(member["name"]) for member in members}, key=str.casefold)
        offices = sorted({_clean(member["office"]) for member in members}, key=str.casefold)
        notes = sorted({_clean(member["note"]) for member in members if _clean(member["note"])}, key=str.casefold)
        physical_locators = sorted(
            locator
            for member in members
            for locator in member["physical_locators"]
        )
        record = _record(
            cfg,
            len(records) + 1,
            name=representative["name"],
            office=representative["office"],
            identifier_raw=representative["identifier_raw"],
            activities=activities,
            status=_status(representative["note"]),
            outcome_raw=representative["note"],
            listing_date=listing_date,
            expiry_date=expiry_date,
            source_fields={
                "listing_date_raw": representative["listed_raw"],
                "expiry_date_raw": representative["expiry_raw"],
                "sectors": sectors,
                "name_variants": names,
                "office_variants": offices,
                "notes": notes,
                "physical_locators": physical_locators,
                "physical_sector_observations": len(members),
            },
        )
        record["identifiers"] = _strict_identifiers(representative["identifier_raw"])
        records.append(record)

    status_counts = dict(Counter(record["source_status"] for record in records))
    identifier_coverage = sum(bool(record["identifiers"]) for record in records)
    if status_counts != _EXPECTED_RECONSTRUCTION_STATUS_COUNTS:
        raise RuntimeError(f"Ferrara reconstruction status drift: {status_counts!r}")
    if identifier_coverage != _EXPECTED_RECONSTRUCTION_IDENTIFIER_COVERAGE:
        raise RuntimeError(
            f"Ferrara reconstruction identifier-coverage drift: {identifier_coverage} != {_EXPECTED_RECONSTRUCTION_IDENTIFIER_COVERAGE}"
        )
    if multi_sector_groups != _EXPECTED_RECONSTRUCTION_MULTI_SECTOR_GROUPS:
        raise RuntimeError(
            f"Ferrara reconstruction multi-sector-group drift: {multi_sector_groups} != {_EXPECTED_RECONSTRUCTION_MULTI_SECTOR_GROUPS}"
        )
    if date_anomalies != _EXPECTED_RECONSTRUCTION_DATE_ANOMALIES:
        raise RuntimeError(
            f"Ferrara reconstruction date-anomaly drift: {date_anomalies} != {_EXPECTED_RECONSTRUCTION_DATE_ANOMALIES}"
        )

    return ParsedBatch(
        records=records,
        diagnostics={
            "parser": "ferrara_reconstruction_bundle",
            "parser_version": PARSER_VERSION,
            "physical_sector_observations": len(physical),
            "public_records": len(records),
            "status_counts": status_counts,
            "identifier_coverage": identifier_coverage,
            "multi_sector_groups": multi_sector_groups,
            "date_anomalies": date_anomalies,
            "bundle_sectors": sorted(paths),
        },
    )


# Only single-resource parsers are exposed through the current scalar-resource
# dispatcher. Reconstruction is intentionally held behind the explicit bundle API
# until the publication layer can acquire/hash all seven members transactionally.
PARSERS = {
    "ferrara-provincial-listed": parse_ferrara_ordinary,
    "ferrara-provincial-applicants": parse_ferrara_applicants,
}
