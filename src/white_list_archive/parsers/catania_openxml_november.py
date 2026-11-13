"""Exact November 6, 2026 Catania White List XLSX parser (source-backed only).

Separate from the frozen 11 September parser. Input SHA and source layout are
immutable; administrative outcomes are never inferred from expiry or absence.
Source-only anomalies preserve their raw values rather than fabricate dates or
section identities. Release approval is a separate governed step.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime
import hashlib
from pathlib import Path
import re
from typing import Any

import openpyxl

from white_list_archive.parsers.catania_openxml import (
    _EXPECTED_APPLICANT_FOOTER_LABELS,
    _EXPECTED_LISTED_FOOTER_LABELS,
    _STANDARD_EXPIRY_FORMULA,
    _strict_date,
    _strict_identifiers,
)
from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _clean, _record

PARSER_VERSION = "2026-11-06.1"
_DATE = "2026-11-06"
_PINS = {
    "catania_listed_2026_11": ("catania-listed", "listed", "ccd1a9abbf8144ae4edb43c7df07c1648c0273196a7aff278c03c62b39b733ff"),
    "catania_applicants_2026_11": ("catania-applicants", "applicant", "adb590642773f68047e207beeb6aace3555ece674b6b64872c1347c0c7d4ffbb"),
}
_LAYOUT = {
    "listed": {"max_row": 3366, "max_col": 8, "header_row": 2,
               "first_row": 3, "last_row": 1866, "company_rows": 1864},
    "applicant": {"max_row": 1578, "max_col": 7, "header_row": 4,
                  "first_row": 5, "last_row": 177, "company_rows": 173},
}
_HEADERS = {
    "listed": {0:"RAGIONE SOCIALE",1:"SEDE LEGALE",2:"SEDE SECONDARIA CON RAPPRESENTANZA IN ITALIA",
               4:"CODICE FISCALE/PARTITA IVA",5:"DATA DI ISCRIZIONE",
               6:"SCADENZA ISCRIZIONE",7:"AGGIORNAMENTO IN CORSO"},
    "applicant": {0:"RAGIONE SOCIALE",1:"SEDE LEGALE",2:"SEDE SECONDARIA CON RAPPRESENTANZA IN ITALIA",
                  4:"CODICE FISCALE/PARTITA IVA",5:"DATA PRESENTAZIONE ISTANZA",6:"ESITO"},
}
_SECTORS = {str(n) for n in range(1,11)}
# Safely classified from exact official original without exposing business data.
# Fused/invalid source notation is preserved verbatim as raw source evidence;
# no invented sector is emitted.
_REVIEWED_SECTOR_ANOMALY_CELL_HASHES = {
    406: "38fb0ec05f4bbcc18a3f69a85cc9e3c06a56c8b8bb7229c302a3a4e5ce52ed17",
    892: "f81a89a265352f9eaff5db565539ca7d1dd301bf806b04f77c9c82cd247258e3",
    1264: "60ea9a8b3b875d8890842ccb696d0205cc2d18f00d8a47507b9e952ec763e0c0",
    1353: "74796ee222e137f49196fab535ec306b08c2041ebe32fd7e69224f99854b950b",
}



def _check_cfg(path: Path, cfg: dict[str,Any], parser_name: str) -> None:
    source_key, scope, digest = _PINS[parser_name]
    if cfg.get("source_key") != source_key or cfg.get("authority_key") != "catania":
        raise RuntimeError("November Catania source identity is not approved")
    if cfg.get("population_scope") != scope or cfg.get("reference_date") != _DATE:
        raise RuntimeError("November Catania population/date attribution drift")
    if cfg.get("sha256") != digest:
        raise RuntimeError("November Catania configured source SHA drift")
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise RuntimeError("November Catania original byte digest mismatch")


def _open_sheet(path: Path, population: str, *, values_only: bool=False):
    book = openpyxl.load_workbook(path,read_only=False,data_only=values_only)
    if book.sheetnames != ["Foglio1"]:
        raise RuntimeError("Catania November worksheet name drift")
    sheet=book["Foglio1"]
    layout=_LAYOUT[population]
    if sheet.max_row != layout["max_row"] or sheet.max_column != layout["max_col"]:
        raise RuntimeError("Catania November worksheet dimensions drift")
    header=[_clean(cell.value) for cell in sheet[layout["header_row"]]]
    for index,value in _HEADERS[population].items():
        if header[index] != value:
            raise RuntimeError("Catania November header identity drift")
    if population=="applicant" and "ATTIVITA'" not in header[3]:
        raise RuntimeError("Catania November applicant sector-header drift")
    # No populated cells may be discarded between the company block and the
    # source-defined explanatory footer. Formatting-only rows are permitted.
    for rowno in range(layout["last_row"]+1,sheet.max_row-10):
        if any(_clean(cell.value) for cell in sheet[rowno]):
            raise RuntimeError("Catania November nonempty unparsed source row")
    labels=[item[0] for item in [
        (_clean(sheet.cell(r,2).value),_clean(sheet.cell(r,3).value))
        if population=="applicant" else
        (_clean(sheet.cell(r,1).value),_clean(sheet.cell(r,2).value))
        for r in range(sheet.max_row-10,sheet.max_row+1)
    ]]
    expected = _EXPECTED_APPLICANT_FOOTER_LABELS if population=="applicant" else _EXPECTED_LISTED_FOOTER_LABELS
    if labels != expected:
        raise RuntimeError("Catania November source footer drift")
    return sheet


def _sections(raw: Any) -> tuple[list[str],bool]:
    text=_clean(raw)
    if not text:
        raise RuntimeError("Catania November sector cell missing")
    parts=[p.strip() for p in re.split(r"[,.;]+",text) if p.strip()]
    valid=[part for part in parts if part in _SECTORS]
    if not valid or len(valid) != len(set(valid)):
        raise RuntimeError("Catania November sectors ambiguous or duplicated")
    # Unrecognised/fused source tokens are NOT decomposed into invented sectors.
    # The full original cell is kept in requested_activities_source.
    return [f"Sezione {part}" for part in valid],len(valid)!=len(parts)


def _calendar_or_raw(value: Any) -> tuple[str,bool]:
    # Return only document-supported parseable dates. Unrecognised dates remain
    # unnormalised, with the original string available in source_fields.
    try:
        return _strict_date(value,context="Catania November source date"),False
    except RuntimeError:
        if not _clean(value):
            raise RuntimeError("Catania November required source date missing")
        return "",True


def parse_catania_listed_2026_11(path:Path,cfg:dict[str,Any]) -> ParsedBatch:
    _check_cfg(path,cfg,"catania_listed_2026_11")
    formula=_open_sheet(path,"listed",values_only=False)
    cached=_open_sheet(path,"listed",values_only=True)
    result=[]
    count=Counter()
    for rowno in range(3,1867):
        row=[cell.value for cell in formula[rowno]][:8]
        cachedrow=[cell.value for cell in cached[rowno]][:8]
        if len(row)!=8 or not _clean(row[0]) or not _clean(row[3]):
            raise RuntimeError("Catania November listed incomplete company row")
        name,office,secondary,sectors,rawid,listing,expiry,annotation=row
        sector_values,sector_anomaly=_sections(sectors)
        observed_hash=hashlib.sha256(_clean(sectors).encode("utf-8")).hexdigest()
        expected_hash=_REVIEWED_SECTOR_ANOMALY_CELL_HASHES.get(rowno)
        if sector_anomaly != (expected_hash is not None) or (expected_hash and observed_hash!=expected_hash):
            raise RuntimeError("Catania November listed source sector-anomaly provenance drift")
        count["sector_anomalies"]+=sector_anomaly
        count["blank_offices"]+=not bool(_clean(office))
        identifiers=_strict_identifiers(rawid)
        count["strict_identifiers"]+=bool(identifiers)
        listingdate,unparsed=_calendar_or_raw(listing)
        count["unparsed_listing_dates"]+=unparsed
        expiry_source=_clean(expiry)
        if not expiry_source:
            raise RuntimeError("Catania November listed source expiry missing")
        if isinstance(expiry,str) and expiry.startswith("="):
            match=_STANDARD_EXPIRY_FORMULA.fullmatch(expiry)
            if match is None or int(match.group("row"))!=rowno:
                raise RuntimeError("Catania November unexpected source expiry formula")
            count["standard_expiry_formulas"]+=1
            expirydate,unparsed_expiry=_calendar_or_raw(cachedrow[6])
            if unparsed_expiry:
                raise RuntimeError("Catania November expiry formula lacks valid cached date")
        else:
            expirydate,unparsed_expiry=_calendar_or_raw(expiry)
            count["unparsed_expiry_dates"]+=unparsed_expiry
        status="renewal_update_in_progress" if "rinnovo" in _clean(annotation).casefold() else "listed"
        count[status]+=1
        if _clean(annotation) and status=="listed":
            count["nonrenewal_status_notes"]+=1
        rec=_record(
            cfg,len(result)+1,name=_clean(name),office=_clean(office),secondary=_clean(secondary),
            identifier_raw=_clean(rawid),activities=sector_values,status=status,
            outcome_raw=_clean(annotation),listing_date=listingdate,expiry_date=expirydate,
            primary_date_label="Data iscrizione",
            source_fields={
                "sections":sector_values,
                "requested_activities_source":_clean(sectors),
                "listing_date_raw_variants":[_clean(listing)] if _clean(listing) else [],
                "expiry_date_raw_variants":[expiry_source],
                "in_aggiornamento":_clean(annotation) if status=="renewal_update_in_progress" else "",
            },
        )
        rec["identifiers"]=identifiers
        result.append(rec)
    expected={
        "strict_identifiers":1819,"sector_anomalies":4,"blank_offices":2,
        "unparsed_listing_dates":2,"unparsed_expiry_dates":0,
        "standard_expiry_formulas":1581,
        "listed":1662,"renewal_update_in_progress":202,"nonrenewal_status_notes":5,
    }
    if len(result)!=1864 or any(count[key]!=value for key,value in expected.items()):
        # Closed aggregate counts; never expose names, identifiers or source values.
        raise RuntimeError(f"Catania November listed source aggregate QA drift: {dict(count)}")
    return ParsedBatch(records=result,diagnostics={
        "parser":"catania_listed_2026_11","parser_version":PARSER_VERSION,
        "public_records":len(result),"status_counts":{k:count[k] for k in ("listed","renewal_update_in_progress")},
        "strict_identifiers":count["strict_identifiers"],
        "source_sector_anomalies_preserved":count["sector_anomalies"],
        "unparsed_listing_dates_preserved":count["unparsed_listing_dates"],
        "source_formula_rows":count["standard_expiry_formulas"]
    })


def parse_catania_applicants_2026_11(path:Path,cfg:dict[str,Any]) -> ParsedBatch:
    _check_cfg(path,cfg,"catania_applicants_2026_11")
    sheet=_open_sheet(path,"applicant")
    records=[]
    count=Counter()
    for rowno in range(5,178):
        vals=[cell.value for cell in sheet[rowno]][:7]
        if len(vals)!=7:
            raise RuntimeError("Catania November applicant row width drift")
        name,office,secondary,rawsector,rawid,application,outcome=vals
        if not all(_clean(x) for x in (office,rawsector,rawid,application)) or _clean(outcome):
            raise RuntimeError("Catania November applicant row source-field drift")
        if not _clean(name):
            # One source row actually has a blank enterprise-name field; do not
            # invent an identity from its tax number or adjacent row.
            count["blank_names"]+=1
            if rowno!=5:
                raise RuntimeError("Catania November unexpected applicant blank name")
        sectors,anomaly=_sections(rawsector)
        count["sector_anomalies"]+=anomaly
        identifiers=_strict_identifiers(rawid)
        count["strict_identifiers"]+=bool(identifiers)
        applicationdate,unparsed=_calendar_or_raw(application)
        if unparsed:
            raise RuntimeError("Catania November applicant unparseable application date")
        rec=_record(cfg,len(records)+1,name=_clean(name),office=_clean(office),
            secondary=_clean(secondary),identifier_raw=_clean(rawid),
            activities=sectors,status="pending",outcome_raw="",
            application_date=applicationdate,
            primary_date_label="Data presentazione istanza",
            source_fields={"sections":sectors,
                "requested_activities_source":_clean(rawsector),
                "application_date_raw_variants":[_clean(application)]},
        )
        rec["identifiers"]=identifiers
        records.append(rec)
    if len(records)!=173 or count["blank_names"]!=1 or count["sector_anomalies"]!=0 or count["strict_identifiers"] not in (172,173):
        raise RuntimeError(f"Catania November applicant aggregate QA drift: {dict(count)}")
    return ParsedBatch(records=records,diagnostics={
        "parser":"catania_applicants_2026_11","parser_version":PARSER_VERSION,
        "public_records":len(records),"status_counts":{"pending":len(records)},
        "blank_source_names_preserved":count["blank_names"],
        "strict_identifiers":count["strict_identifiers"],
    })


PARSERS={
    "catania_listed_2026_11":parse_catania_listed_2026_11,
    "catania_applicants_2026_11":parse_catania_applicants_2026_11,
}
