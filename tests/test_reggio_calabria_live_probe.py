from __future__ import annotations

import hashlib
import json
import re
import urllib.request
from collections import Counter
from pathlib import Path

import pdfplumber

SOURCES = {
    "listed": {
        "url": "https://prefettura.interno.gov.it/sites/default/files/0/2026-09/white-list-foglio-unico-nuove-attivita-24-set-2026.pdf",
        "sha256": "f93a63a89c2c22f9fee27af29654c3dd5e97b58452dde92224b4b2259d3f148f",
        "byte_size": 266878,
    },
    "applicant": {
        "url": "https://prefettura.interno.gov.it/sites/default/files/0/2026-09/elenco-richieste-iscrizioni-white-list-foglio-del-24-set-2026.pdf",
        "sha256": "da60df92f7ffdfc1148ead109395e00ae34e11cb53c01ccc6928bbdff0c71d53",
        "byte_size": 372194,
    },
}

def _clean(value):
    return " ".join(str(value or "").replace("\n", " ").split())

def _date_shape(value):
    value=_clean(value)
    if not value:
        return "empty"
    if re.fullmatch(r"\d{1,2}/\d{1,2}/\d{2,4}", value):
        return "slash_numeric"
    if re.fullmatch(r"\d{1,2}-[A-Za-zÀ-ÿ]{3,}-\d{2,4}", value):
        return "dash_month_name"
    if re.fullmatch(r"\d{1,2}-\d{1,2}-\d{2,4}", value):
        return "dash_numeric"
    return "other"

def _probe(kind, path):
    result={"kind":kind}
    with pdfplumber.open(path) as pdf:
        result["page_count"]=len(pdf.pages)
        table_counts=[]
        row_counts=[]
        column_counts=Counter()
        header_signatures=Counter()
        raw_rows=0
        nonempty_rows=0
        identifier_11=0
        identifier_16=0
        date_shapes=Counter()
        status_buckets=Counter()
        incomplete_required=0
        for page_no,page in enumerate(pdf.pages,start=1):
            tables=page.extract_tables()
            table_counts.append(len(tables))
            page_rows=0
            for table in tables:
                if not table:
                    continue
                header=[_clean(x) for x in table[0]]
                header_signatures[" | ".join(header)]+=1
                for row in table[1:]:
                    cells=[_clean(x) for x in row]
                    if not any(cells):
                        continue
                    raw_rows += 1
                    page_rows += 1
                    nonempty_rows += 1
                    column_counts[len(cells)] += 1
                    if kind=="listed" and len(cells)>=9:
                        identifier=cells[4].upper()
                        if re.fullmatch(r"\d{11}",identifier): identifier_11+=1
                        if re.fullmatch(r"[A-Z0-9]{16}",identifier): identifier_16+=1
                        date_shapes["registration:"+_date_shape(cells[5])] += 1
                        date_shapes["expiry:"+_date_shape(cells[6])] += 1
                        note=cells[8].casefold()
                        if not note:
                            status_buckets["listed_empty_note"] += 1
                        elif any(t in note for t in ("rinnovo","permanenza","aggiornamento","istruttoria in corso")):
                            status_buckets["renewal_update_language"] += 1
                        else:
                            status_buckets["other_note"] += 1
                        if not all((cells[1],cells[2],cells[4],cells[5],cells[6],cells[7])):
                            incomplete_required += 1
                    elif kind=="applicant" and len(cells)>=8:
                        identifier=cells[4].upper()
                        if re.fullmatch(r"\d{11}",identifier): identifier_11+=1
                        if re.fullmatch(r"[A-Z0-9]{16}",identifier): identifier_16+=1
                        date_shapes["application:"+_date_shape(cells[6])] += 1
                        outcome=cells[7].casefold()
                        if "istruttoria" in outcome:
                            status_buckets["istruttoria"] += 1
                        elif not outcome:
                            status_buckets["empty_outcome"] += 1
                        else:
                            status_buckets["other_outcome"] += 1
                        if not all((cells[1],cells[2],cells[4],cells[5],cells[6])):
                            incomplete_required += 1
            row_counts.append(page_rows)
        result.update({
            "tables_per_page": dict(Counter(table_counts)),
            "rows_per_page_min": min(row_counts) if row_counts else 0,
            "rows_per_page_max": max(row_counts) if row_counts else 0,
            "raw_nonempty_rows": nonempty_rows,
            "column_counts": dict(column_counts),
            "header_signatures": dict(header_signatures),
            "strict_identifier_11": identifier_11,
            "strict_identifier_16": identifier_16,
            "date_shapes": dict(date_shapes),
            "status_buckets": dict(status_buckets),
            "incomplete_required_rows": incomplete_required,
        })
    return result

def test_reggio_calabria_live_structure_probe(tmp_path: Path) -> None:
    summary={}
    for kind,cfg in SOURCES.items():
        request=urllib.request.Request(cfg["url"],headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(request,timeout=60) as response:
            payload=response.read()
        digest=hashlib.sha256(payload).hexdigest()
        assert len(payload)==cfg["byte_size"], (kind,len(payload),cfg["byte_size"])
        assert digest==cfg["sha256"], (kind,digest,cfg["sha256"])
        path=tmp_path/f"{kind}.pdf"
        path.write_bytes(payload)
        summary[kind]=_probe(kind,path)
    raise AssertionError("REGGIO_PROBE="+json.dumps(summary,sort_keys=True,ensure_ascii=False))
