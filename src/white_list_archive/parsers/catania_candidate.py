"""Provisional, variable-row Catania XLSX extractor for robot-discovered documents.

Distinct from the SHA- and edition-pinned approved November parser. This
extractor only produces *unapproved private* source observations and QA flags;
the archive/CLI enforces that no public release can invoke it implicitly.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from pathlib import Path
import re
from typing import Any

import openpyxl

from white_list_archive.parsers.catania_openxml import _strict_identifiers
from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _clean, _record

VERSION = "1"
PARSERS = {"listed": "catania_candidate_listed", "applicant": "catania_candidate_applicants"}
HEADERS = {
    "listed": {
        0: "RAGIONE SOCIALE", 1: "SEDE LEGALE",
        2: "SEDE SECONDARIA CON RAPPRESENTANZA IN ITALIA",
        4: "CODICE FISCALE/PARTITA IVA", 5: "DATA DI ISCRIZIONE",
        6: "SCADENZA ISCRIZIONE", 7: "AGGIORNAMENTO IN CORSO",
    },
    "applicant": {
        0: "RAGIONE SOCIALE", 1: "SEDE LEGALE",
        2: "SEDE SECONDARIA CON RAPPRESENTANZA IN ITALIA",
        4: "CODICE FISCALE/PARTITA IVA", 5: "DATA PRESENTAZIONE ISTANZA",
        6: "ESITO",
    },
}
SECTIONS = frozenset(str(i) for i in range(1, 11))
MAX_ROWS = 10_000
MAX_COLS = 12


def _source_date(value: Any) -> tuple[str, bool]:
    """Parse only explicit Gregorian dates; retain anything else in raw fields."""
    if isinstance(value, datetime):
        return value.date().isoformat(), False
    if isinstance(value, date):
        return value.isoformat(), False
    text = _clean(value)
    for pattern in (r"(\d{2})/(\d{2})/(\d{4})", r"(\d{4})-(\d{2})-(\d{2})"):
        match = re.fullmatch(pattern, text)
        if not match:
            continue
        try:
            if "/" in text:
                d, m, y = map(int, match.groups())
            else:
                y, m, d = map(int, match.groups())
            return date(y, m, d).isoformat(), False
        except ValueError:
            pass
    return "", bool(text)


def _sectors(value: Any) -> tuple[list[str], bool]:
    original = _clean(value)
    parts = [part.strip() for part in re.split(r"[,;]+", original) if part.strip()]
    valid = []
    for part in parts:
        if part in SECTIONS and part not in valid:
            valid.append(part)
    anomaly = not parts or len(valid) != len(parts)
    return [f"Sezione {p}" for p in valid], anomaly


def _header_row(sheet, population: str) -> int:
    required = HEADERS[population]
    width = 8 if population == "listed" else 7
    for rowno in range(1, min(sheet.max_row, 10) + 1):
        values = [_clean(sheet.cell(rowno, col + 1).value).upper() for col in range(width)]
        if all(values[col] == label for col, label in required.items()):
            if population == "applicant" and "ATTIVITA" not in values[3].replace("'", "").replace("’", ""):
                continue
            return rowno
    raise ValueError("Catania candidate worksheet header identity is unknown")


def parse_candidate_xlsx(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    """Read all candidate rows; never infer an edition date from capture time."""
    if cfg.get("authority_key") != "catania" or cfg.get("reference_date") not in ("", None):
        raise ValueError("Catania candidate parser requires unapproved, undated source context")
    population = cfg.get("population_scope")
    if population not in PARSERS or cfg.get("parser") != PARSERS[population]:
        raise ValueError("Catania candidate population/parser hypothesis is inconsistent")
    wb = openpyxl.load_workbook(path, read_only=False, data_only=False)
    cached = openpyxl.load_workbook(path, read_only=False, data_only=True)
    try:
        if wb.sheetnames != ["Foglio1"] or cached.sheetnames != wb.sheetnames:
            raise ValueError("Unexpected Catania candidate worksheet identity")
        sheet, values = wb.active, cached.active
        if (not sheet.max_row or sheet.max_row > MAX_ROWS or not sheet.max_column
                or sheet.max_column > MAX_COLS):
            raise ValueError("Catania candidate worksheet exceeds reviewed processing bounds")
        start = _header_row(sheet, population) + 1
        width = 8 if population == "listed" else 7
        records = []
        flags = Counter()
        sectors_total = 0
        for rowno in range(start, sheet.max_row + 1):
            raw = [sheet.cell(rowno, col + 1).value for col in range(width)]
            name, office, secondary, sector, identifier = raw[:5]
            name_text, id_text, sector_text = _clean(name), _clean(identifier), _clean(sector)
            # Blank/formatting-only rows and explanatory footers have no
            # complete company signature. Never silently skip a data-like row
            # with just one of the two mandatory semantic anchors.
            if not id_text and not sector_text:
                continue
            if not id_text or not sector_text:
                raise ValueError("Candidate source contains an incomplete data-like row")
            if name_text.upper() == "RAGIONE SOCIALE":
                raise ValueError("Unexpected repeated source header within candidate data")
            sections, sector_anomaly = _sectors(sector)
            flags["sector_anomalies"] += sector_anomaly
            sectors_total += len(sections)
            ids = _strict_identifiers(identifier)
            flags["unrecognised_identifiers"] += not bool(ids)
            fields = {
                "candidate_physical_row": rowno,
                "requested_activities_source": sector_text,
                "identifier_field_raw": id_text,
            }
            if population == "listed":
                raw_listing, raw_expiry, annotation = raw[5:8]
                listing, bad_listing = _source_date(raw_listing)
                expiry_value = raw_expiry
                if isinstance(raw_expiry, str) and raw_expiry.startswith("="):
                    # No invented anniversary: use only an actually cached Excel
                    # formula result, preserve the original formula in the source.
                    expiry_value = values.cell(rowno, 7).value
                    flags["source_expiry_formulas"] += 1
                    if expiry_value is None:
                        flags["formula_without_cached_date"] += 1
                expiry, bad_expiry = _source_date(expiry_value)
                flags["unparsed_source_dates"] += int(bad_listing or bad_expiry)
                annotation_text = _clean(annotation)
                status = ("renewal_update_in_progress"
                          if re.search(r"rinnov|aggiornament", annotation_text, re.I)
                          else "listed")
                if annotation_text and status == "listed":
                    flags["unclassified_status_notes"] += 1
                fields.update({
                    "listing_date_raw": _clean(raw_listing),
                    "expiry_date_raw": _clean(raw_expiry),
                    "update_raw": annotation_text,
                })
                record = _record(
                    cfg, len(records) + 1, name=name_text, office=_clean(office),
                    secondary=_clean(secondary), identifier_raw=id_text,
                    activities=sections, status=status, outcome_raw=annotation_text,
                    listing_date=listing, expiry_date=expiry,
                    primary_date_label="Data iscrizione",
                    source_fields=fields,
                )
            else:
                raw_application, outcome = raw[5:7]
                application, bad_application = _source_date(raw_application)
                flags["unparsed_source_dates"] += bad_application
                outcome_text = _clean(outcome)
                if not outcome_text or re.search(r"istruttoria|in.lavorazione", outcome_text, re.I):
                    status = "pending"
                elif re.search(r"^iscritt[oa]$", outcome_text, re.I):
                    status = "listed"
                else:
                    status = "other_or_unknown"
                    flags["unclassified_source_outcomes"] += 1
                fields.update({"application_date_raw": _clean(raw_application),
                               "outcome_raw": outcome_text})
                record = _record(
                    cfg, len(records) + 1, name=name_text, office=_clean(office),
                    secondary=_clean(secondary), identifier_raw=id_text,
                    activities=sections, status=status, outcome_raw=outcome_text,
                    application_date=application,
                    primary_date_label="Data presentazione istanza",
                    source_fields=fields,
                )
            record["identifiers"] = ids
            record["parser_name"] = cfg["parser"]
            record["parser_version"] = VERSION
            records.append(record)
        if not records:
            raise ValueError("Catania candidate contains no recognisable source observations")
        detected = [k for k in (
            "sector_anomalies", "unrecognised_identifiers", "unparsed_source_dates",
            "formula_without_cached_date", "unclassified_status_notes",
            "unclassified_source_outcomes"
        ) if flags[k]]
        return ParsedBatch(records=records, diagnostics={
            "parser": cfg["parser"], "parser_version": VERSION,
            "public_records": len(records), "sector_rows": sectors_total,
            "dropped_date_rows": 0,
            "candidate_quality_flags": detected,
            "counts": dict(sorted(flags.items())),
            "source_rows_represented": len(records),
            "source_date_assigned": False,
            "publication_approved": False,
        })
    finally:
        wb.close()
        cached.close()
