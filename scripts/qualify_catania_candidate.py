"""Aggregate-only exact-November Catania source qualification (no company data)."""
from __future__ import annotations
from collections import Counter
from datetime import date, datetime
from pathlib import Path
import json
import re
import tempfile

import openpyxl
from white_list_archive.publishing.public_national_registry import _download
from white_list_archive.parsers import catania_openxml as old

DATE = re.compile(r"^(?:\\d{1,2}/\\d{1,2}/\\d{4}|\\d{4}-\\d{2}-\\d{2}(?: 00:00:00)?)$")
SECTION = re.compile(r"^(?:\\s*(?:10|[1-9])\\s*[,;.]?)+$")
FORMULA = re.compile(r"^=DATE\\(YEAR\\(F\\d+\\)\\+1,MONTH\\(F\\d+\\),DAY\\(F\\d+\\)\\)$", re.I)


def classify(value):
    if value is None or old._clean(value) == "":
        return "missing"
    if isinstance(value, (date, datetime)):
        return "excel_calendar"
    if isinstance(value, str) and value.startswith("="):
        return "formula" if FORMULA.fullmatch(value) else "unexpected_formula"
    return "date_like" if DATE.fullmatch(old._clean(value)) else "other"


def profile(path: Path, key: str):
    wb=openpyxl.load_workbook(path,data_only=False,read_only=False)
    raw=wb.active
    applicant=key.endswith("applicants")
    start=5 if applicant else 3
    header=4 if applicant else 2
    field_count=7 if applicant else 8
    header_cells=[old._clean(cell.value) for cell in raw[header][:field_count]]
    same_headers=all(
        header_cells[c] == expected for c,expected in ({
            0:"RAGIONE SOCIALE",1:"SEDE LEGALE",
            2:"SEDE SECONDARIA CON RAPPRESENTANZA IN ITALIA",
            4:"CODICE FISCALE/PARTITA IVA",
            5:"DATA PRESENTAZIONE ISTANZA",6:"ESITO",
        } if applicant else {
            0:"RAGIONE SOCIALE",1:"SEDE LEGALE",
            2:"SEDE SECONDARIA CON RAPPRESENTANZA IN ITALIA",
            4:"CODICE FISCALE/PARTITA IVA",
            5:"DATA DI ISCRIZIONE",6:"SCADENZA ISCRIZIONE",
            7:"AGGIORNAMENTO IN CORSO",
        }).items()
    )
    last=start-1
    for n in range(start,raw.max_row+1):
        if not old._clean(raw.cell(n,1).value):
            break
        last=n
    totals=Counter()
    rows=last-start+1
    invalid_rows=[]
    category_status=Counter()
    identifier_shapes=Counter()
    for n in range(start,last+1):
        values=[raw.cell(n,c+1).value for c in range(field_count)]
        sections=old._clean(values[3])
        totals["nonblank_names"]+=bool(old._clean(values[0]))
        totals["nonblank_offices"]+=bool(old._clean(values[1]))
        totals["nonblank_sectors"]+=bool(sections)
        if not SECTION.fullmatch(sections):totals["unrecognised_sector_syntax"]+=1
        strict=old._strict_identifiers(values[4])
        identifier_shapes["strict" if strict else "raw_nonstandard" if old._clean(values[4]) else "missing"]+=1
        if applicant:
            totals["date_"+classify(values[5])]+=1
            outcome=old._clean(values[6]);category_status["blank" if not outcome else "nonblank"]+=1
        else:
            totals["listing_"+classify(values[5])]+=1
            totals["expiry_"+classify(values[6])]+=1
            status=old._clean(values[7]).casefold()
            category_status["renewal" if "rinnovo" in status else "blank" if not status else "other_note"]+=1
    footer=old._footer_signature(raw,applicant=applicant)
    expected=old._EXPECTED_APPLICANT_FOOTER_LABELS if applicant else old._EXPECTED_LISTED_FOOTER_LABELS
    return {
        "source_key":key,"sheets":len(wb.sheetnames),
        "sheet_name_matches_legacy":wb.sheetnames == [old._SHEET],
        "max_row":raw.max_row,"max_column":raw.max_column,
        "header_compatible":same_headers,
        "company_rows":rows,"first_company_row":start,"last_company_row":last,
        "historical_rows":old._APPLICANT_RECORDS if applicant else old._LISTED_RECORDS,
        "footer_labels_match": [x[0] for x in footer] == expected,
        "footer_rows":len(footer),
        "value_shapes":dict(sorted(totals.items())),
        "identifiers":dict(sorted(identifier_shapes.items())),
        "source_status_shapes":dict(sorted(category_status.items())),
        "archive_byte_sha256_verified":True,
        "release_approved":False,
    }


def main():
    cfg=json.loads(Path('data/publication/multi_prefecture_pilot.json').read_text())
    sources={s['source_key']:s for s in cfg['sources']}
    result=[]
    with tempfile.TemporaryDirectory(prefix='catania-november-') as d:
        for key in ("catania-listed","catania-applicants"):
            source=sources[key]
            if source['reference_date']!="2026-11-06" or source['authority_key']!="catania":
                raise SystemExit("Unapproved Catania candidate identity")
            path=Path(d)/(key+".xlsx")
            sha=_download(source['resource_url'],path)
            if sha!=source['sha256']:raise SystemExit(f"{key}: SHA-256 mismatch")
            result.append(profile(path,key))
    print(json.dumps({"review_only":True,"results":result},sort_keys=True))


if __name__=="__main__":
    main()
