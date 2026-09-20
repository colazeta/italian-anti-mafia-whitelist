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

_LISTED_SECTIONS = {
    "I": 4,
    "II": 2,
    "III": 5,
    "IV": 2,
    "V": 6,
    "VI": 4,
    "VII": 1,
    "VIII": 2,
    "IX": 2,
    "X": 4,
}
_EXPECTED_LISTED_PHYSICAL = 595
_EXPECTED_LISTED_LOGICAL = 401
_EXPECTED_LISTED_STATUS = {
    "listed": 335,
    "renewal_update_in_progress": 65,
    "other_or_unknown": 1,
}
_EXPECTED_LISTED_IDENTIFIER_COVERAGE = 234
_EXPECTED_LISTED_MULTI_SECTION = 105
_EXPECTED_LISTED_CONFLICT_IDENTITIES = 20
_EXPECTED_LISTED_MISSING_DATE_FIELDS = 4
_EXPECTED_LISTED_DATE_ANOMALIES = 5

_EXPECTED_APPLICANT_PAGES = 4
_EXPECTED_APPLICANTS = 32
_EXPECTED_APPLICANT_STATUS = {
    "pending": 31,
    "renewal_update_in_progress": 1,
}
_EXPECTED_APPLICANT_IDENTIFIER_COVERAGE = 32
_EXPECTED_APPLICANT_DATE_ANOMALIES = 0

_STRICT_ID = re.compile(r"^(?:[0-9]{11}|[A-Z0-9]{16})$")
_CANONICAL_DATE = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")
_DATE_IN_ROW = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")


def _fold(value: str) -> str:
    value = unicodedata.normalize("NFKD", _clean(value))
    return "".join(ch for ch in value if not unicodedata.combining(ch)).casefold()


def _strict_identifiers(value: str) -> list[str]:
    compact = re.sub(r"[^0-9A-Z]", "", _clean(value).upper())
    return [compact] if _STRICT_ID.fullmatch(compact) else []


def _normalise_date_or_blank(raw_value: str) -> str:
    raw = _clean(raw_value)
    match = _CANONICAL_DATE.fullmatch(raw)
    if match is None:
        return ""
    day, month, year = map(int, match.groups())
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return ""


def _date_is_anomalous(raw_value: str) -> bool:
    raw = _clean(raw_value)
    return bool(raw) and not bool(_normalise_date_or_blank(raw))


def _party_fields(cells: list[str]) -> tuple[str, str, str]:
    prefix = cells[:-4]
    if prefix and (prefix[0].isdigit() or not prefix[0]):
        prefix = prefix[1:]
    values = (prefix + ["", "", ""])[:3]
    return tuple(_clean(value) for value in values)  # type: ignore[return-value]


def _is_structural(cells: list[str]) -> bool:
    nonempty = [_clean(value) for value in cells if _clean(value)]
    joined = _fold(" | ".join(cells))
    if not nonempty:
        return True
    if len(nonempty) == 1 and (
        nonempty[0].isdigit()
        or _CANONICAL_DATE.fullmatch(nonempty[0]) is not None
        or _fold(nonempty[0]) == "stabile in italia"
    ):
        return True
    if "rag. sociale" in joined and ("cod. fiscale" in joined or "partita iva" in joined):
        return True
    if "ragione sociale" in joined and "cod. fiscale" in joined and "data presentazione istanza" in joined:
        return True
    if joined.startswith("rag. | sede | sede secondaria | cod. fiscale | data di | data scadenza | aggiornamento in"):
        return True
    if joined.startswith("sociale | legale | con rappresentanza | partita iva | iscrizione | iscrizione | corso"):
        return True
    if joined.startswith("sezione "):
        return True
    return False


def _listed_status(note: str) -> str:
    folded = _fold(note)
    if "aggiornamento" in folded:
        return "renewal_update_in_progress"
    if "trasferita" in folded or "competenza prefettura" in folded:
        return "other_or_unknown"
    if not folded or "iscritta" in folded:
        return "listed"
    return ""


def _applicant_status(value: str) -> str:
    folded = _fold(value)
    if "in istruttoria" in folded:
        return "pending"
    if "in aggiornamento" in folded:
        return "renewal_update_in_progress"
    return ""


def _validate_cfg(cfg: dict[str, Any], expected_source_key: str) -> None:
    if cfg.get("source_key") != expected_source_key:
        raise RuntimeError(
            f"Pordenone parser/source mismatch: {cfg.get('source_key')!r} != {expected_source_key!r}"
        )
    if cfg.get("authority_key") != "pordenone":
        raise RuntimeError("Pordenone parser bound to a non-Pordenone authority")


def _parse_listed_physical(paths: Mapping[str, Path]) -> list[dict[str, Any]]:
    if set(paths) != set(_LISTED_SECTIONS):
        raise RuntimeError(
            f"Pordenone listed section set drift: {sorted(paths)!r} != {sorted(_LISTED_SECTIONS)!r}"
        )
    rows: list[dict[str, Any]] = []
    unclassified: list[tuple[str, list[str]]] = []
    for section in _LISTED_SECTIONS:
        with pdfplumber.open(paths[section]) as pdf:
            expected_pages = _LISTED_SECTIONS[section]
            if len(pdf.pages) != expected_pages:
                raise RuntimeError(
                    f"Pordenone listed page-count drift section={section}: {len(pdf.pages)} != {expected_pages}"
                )
            for page_number, page in enumerate(pdf.pages, start=1):
                tables = page.extract_tables() or []
                if len(tables) != 1:
                    raise RuntimeError(
                        f"Pordenone listed table-count drift section={section} page={page_number}: {len(tables)}"
                    )
                for row_number, raw in enumerate(tables[0] or [], start=1):
                    cells = [_clean(value) for value in raw]
                    if _is_structural(cells):
                        continue
                    locator = f"{section}:p{page_number}:r{row_number}"
                    if len(cells) not in (7, 8):
                        unclassified.append((locator, cells))
                        continue
                    name, office, secondary = _party_fields(cells)
                    identifier_raw = _clean(cells[-4])
                    listed_raw = _clean(cells[-3])
                    expiry_raw = _clean(cells[-2])
                    note = _clean(cells[-1])
                    status = _listed_status(note)
                    if not status or not (name or identifier_raw):
                        unclassified.append((locator, cells))
                        continue
                    rows.append(
                        {
                            "section": section,
                            "locator": locator,
                            "name": name,
                            "office": office,
                            "secondary": secondary,
                            "identifier_raw": identifier_raw,
                            "identifier": (_strict_identifiers(identifier_raw) or [""])[0],
                            "listed_raw": listed_raw,
                            "expiry_raw": expiry_raw,
                            "note": note,
                            "status": status,
                        }
                    )
    if unclassified:
        raise RuntimeError(f"Pordenone listed unclassified source rows: {unclassified!r}")
    if len(rows) != _EXPECTED_LISTED_PHYSICAL:
        raise RuntimeError(
            f"Pordenone listed physical-row drift: {len(rows)} != {_EXPECTED_LISTED_PHYSICAL}"
        )
    return rows


def parse_pordenone_listed_bundle(paths: Mapping[str, Path], cfg: dict[str, Any]) -> ParsedBatch:
    """Parse Sections I-X transactionally and retain sector membership as provenance."""
    _validate_cfg(cfg, "pordenone-provincial-listed")
    physical = _parse_listed_physical(paths)

    identity_states: dict[tuple[str, ...], set[tuple[str, str, str]]] = defaultdict(set)
    groups: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in physical:
        identity = (
            ("id", row["identifier"])
            if row["identifier"]
            else ("fallback", _fold(row["name"]), _fold(row["office"]), _fold(row["secondary"]))
        )
        state = (row["listed_raw"], row["expiry_raw"], row["status"])
        identity_states[identity].add(state)
        groups[identity + state].append(row)

    if len(groups) != _EXPECTED_LISTED_LOGICAL:
        raise RuntimeError(
            f"Pordenone listed logical-row drift: {len(groups)} != {_EXPECTED_LISTED_LOGICAL}"
        )

    records: list[dict[str, Any]] = []
    multi_section = 0
    for _key, members in sorted(groups.items(), key=lambda item: item[0]):
        members = sorted(members, key=lambda row: (row["section"], row["locator"]))
        representative = members[0]
        sections = sorted({row["section"] for row in members}, key=lambda value: list(_LISTED_SECTIONS).index(value))
        if len(sections) > 1:
            multi_section += 1
        names = sorted({_clean(row["name"]) for row in members if _clean(row["name"])}, key=str.casefold)
        offices = sorted({_clean(row["office"]) for row in members if _clean(row["office"])}, key=str.casefold)
        secondary = sorted({_clean(row["secondary"]) for row in members if _clean(row["secondary"])}, key=str.casefold)
        notes = sorted({_clean(row["note"]) for row in members if _clean(row["note"])}, key=str.casefold)
        locators = [row["locator"] for row in members]
        record = _record(
            cfg,
            len(records) + 1,
            name=representative["name"],
            office=representative["office"],
            secondary=representative["secondary"],
            identifier_raw=representative["identifier_raw"],
            activities=[f"Sezione {section}" for section in sections],
            status=representative["status"],
            outcome_raw=representative["note"],
            listing_date=_normalise_date_or_blank(representative["listed_raw"]),
            expiry_date=_normalise_date_or_blank(representative["expiry_raw"]),
            source_fields={
                "sections": sections,
                "physical_locators": locators,
                "physical_sector_observations": len(members),
                "name_variants": names,
                "office_variants": offices,
                "secondary_office_variants": secondary,
                "listing_date_raw": representative["listed_raw"],
                "expiry_date_raw": representative["expiry_raw"],
                "notes": notes,
            },
        )
        record["identifiers"] = _strict_identifiers(representative["identifier_raw"])
        records.append(record)

    status_counts = dict(Counter(record["source_status"] for record in records))
    identifier_coverage = sum(bool(record["identifiers"]) for record in records)
    conflicts = sum(len(states) > 1 for states in identity_states.values())
    missing_dates = sum(
        int(not row["listed_raw"]) + int(not row["expiry_raw"])
        for row in physical
    )
    date_anomalies = sum(
        int(_date_is_anomalous(row["listed_raw"])) + int(_date_is_anomalous(row["expiry_raw"]))
        for row in physical
    )
    if status_counts != _EXPECTED_LISTED_STATUS:
        raise RuntimeError(f"Pordenone listed status drift: {status_counts!r}")
    if identifier_coverage != _EXPECTED_LISTED_IDENTIFIER_COVERAGE:
        raise RuntimeError(
            f"Pordenone listed identifier-coverage drift: {identifier_coverage} != {_EXPECTED_LISTED_IDENTIFIER_COVERAGE}"
        )
    if multi_section != _EXPECTED_LISTED_MULTI_SECTION:
        raise RuntimeError(
            f"Pordenone listed multi-section drift: {multi_section} != {_EXPECTED_LISTED_MULTI_SECTION}"
        )
    if conflicts != _EXPECTED_LISTED_CONFLICT_IDENTITIES:
        raise RuntimeError(
            f"Pordenone listed identity-state conflict drift: {conflicts} != {_EXPECTED_LISTED_CONFLICT_IDENTITIES}"
        )
    if missing_dates != _EXPECTED_LISTED_MISSING_DATE_FIELDS:
        raise RuntimeError(
            f"Pordenone listed missing-date drift: {missing_dates} != {_EXPECTED_LISTED_MISSING_DATE_FIELDS}"
        )
    if date_anomalies != _EXPECTED_LISTED_DATE_ANOMALIES:
        raise RuntimeError(
            f"Pordenone listed date-anomaly drift: {date_anomalies} != {_EXPECTED_LISTED_DATE_ANOMALIES}"
        )

    return ParsedBatch(
        records=records,
        diagnostics={
            "parser": "pordenone_listed_bundle",
            "parser_version": PARSER_VERSION,
            "physical_sector_observations": len(physical),
            "public_records": len(records),
            "status_counts": status_counts,
            "identifier_coverage": identifier_coverage,
            "multi_section_groups": multi_section,
            "identity_groups_with_conflicting_date_or_status": conflicts,
            "missing_date_fields": missing_dates,
            "date_anomalies": date_anomalies,
            "bundle_sections": list(_LISTED_SECTIONS),
        },
    )


def parse_pordenone_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(cfg, "pordenone-provincial-applicants")
    rows: list[dict[str, Any]] = []
    unclassified: list[tuple[str, list[str]]] = []

    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _EXPECTED_APPLICANT_PAGES:
            raise RuntimeError(
                f"Pordenone applicant page-count drift: {len(pdf.pages)} != {_EXPECTED_APPLICANT_PAGES}"
            )
        for page_number, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables() or []
            if len(tables) != 1:
                raise RuntimeError(
                    f"Pordenone applicant table-count drift page={page_number}: {len(tables)}"
                )
            for row_number, raw in enumerate(tables[0] or [], start=1):
                cells = [_clean(value) for value in raw]
                if _is_structural(cells):
                    continue
                locator = f"XI:p{page_number}:r{row_number}"
                if len(cells) not in (7, 8):
                    unclassified.append((locator, cells))
                    continue
                name, office, secondary = _party_fields(cells)
                identifier_raw = _clean(cells[-4])
                joined = " | ".join(cells)
                dates = _DATE_IN_ROW.findall(joined)
                status = _applicant_status(joined)

                if locator == "XI:p3:r2":
                    if not (
                        name == "MGDSCAVI SRL"
                        and identifier_raw == "01975030931"
                        and dates == ["07/01/2026"]
                        and "istruttoria" in _fold(joined)
                    ):
                        unclassified.append((locator, cells))
                        continue
                    status = "pending"

                if locator == "XI:p3:r9":
                    # The immutable PDF has no company-name token in this row. pdfplumber places
                    # the address in the first column; preserve the name as missing rather than
                    # importing DL SERVICES SRL from another source observation.
                    if not (
                        name == "SEQUALS - VIA CECILIA DANIELI, 7"
                        and not office
                        and identifier_raw == "01456650934"
                        and dates == ["29/09/2025"]
                        and status == "renewal_update_in_progress"
                    ):
                        unclassified.append((locator, cells))
                        continue
                    office = name
                    name = ""

                if not status or len(dates) != 1 or not (name or office or identifier_raw):
                    unclassified.append((locator, cells))
                    continue
                activities = _clean(cells[-3])
                # MGDSCAVI activities are split by the PDF table geometry. Preserve the table
                # fragment raw instead of reconstructing unseen text into the canonical field.
                rows.append(
                    {
                        "locator": locator,
                        "name": name,
                        "office": office,
                        "secondary": secondary,
                        "identifier_raw": identifier_raw,
                        "activities_raw": activities,
                        "application_raw": dates[0],
                        "status": status,
                        "row_raw": cells,
                    }
                )

    if unclassified:
        raise RuntimeError(f"Pordenone applicant unclassified source rows: {unclassified!r}")
    if len(rows) != _EXPECTED_APPLICANTS:
        raise RuntimeError(
            f"Pordenone applicant observation drift: {len(rows)} != {_EXPECTED_APPLICANTS}"
        )

    records: list[dict[str, Any]] = []
    for row in rows:
        application_date = _normalise_date_or_blank(row["application_raw"])
        if not application_date:
            raise RuntimeError(f"Pordenone applicant date drift: {row!r}")
        record = _record(
            cfg,
            len(records) + 1,
            name=row["name"],
            office=row["office"],
            secondary=row["secondary"],
            identifier_raw=row["identifier_raw"],
            activities=[row["activities_raw"]] if row["activities_raw"] else [],
            status=row["status"],
            outcome_raw="IN ISTRUTTORIA" if row["status"] == "pending" else "IN AGGIORNAMENTO",
            application_date=application_date,
            primary_date_label="Data presentazione istanza",
            source_fields={
                "application_date_raw": row["application_raw"],
                "requested_activities_source": row["activities_raw"],
                "physical_locators": [row["locator"]],
                "source_row_raw": row["row_raw"],
                "source_name_missing": not bool(row["name"]),
            },
        )
        record["identifiers"] = _strict_identifiers(row["identifier_raw"])
        records.append(record)

    status_counts = dict(Counter(record["source_status"] for record in records))
    identifier_coverage = sum(bool(record["identifiers"]) for record in records)
    date_anomalies = sum(not bool(record["application_date"]) for record in records)
    if status_counts != _EXPECTED_APPLICANT_STATUS:
        raise RuntimeError(f"Pordenone applicant status drift: {status_counts!r}")
    if identifier_coverage != _EXPECTED_APPLICANT_IDENTIFIER_COVERAGE:
        raise RuntimeError(
            f"Pordenone applicant identifier-coverage drift: {identifier_coverage} != {_EXPECTED_APPLICANT_IDENTIFIER_COVERAGE}"
        )
    if date_anomalies != _EXPECTED_APPLICANT_DATE_ANOMALIES:
        raise RuntimeError(f"Pordenone applicant date-anomaly drift: {date_anomalies}")

    return ParsedBatch(
        records=records,
        diagnostics={
            "parser": "pordenone_applicants",
            "parser_version": PARSER_VERSION,
            "source_pages": _EXPECTED_APPLICANT_PAGES,
            "public_records": len(records),
            "status_counts": status_counts,
            "identifier_coverage": identifier_coverage,
            "date_anomalies": date_anomalies,
            "source_name_missing": sum(not bool(record["name"]) for record in records),
        },
    )


# Applicants are a scalar resource. Listed Pordenone evidence is deliberately held
# behind the explicit bundle API because Sections I-X must be acquired and hashed
# transactionally before cross-section grouping can occur.
PARSERS = {
    "pordenone-provincial-applicants": parse_pordenone_applicants,
}
