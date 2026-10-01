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

def _is_header(cells):
    folded=" | ".join(cells).casefold()
    return "ragione sociale" in folded and ("codice fiscale" in folded or "partita iva" in folded)

def _shape(value):
    value=_clean(value)
    if not value:
        return "empty"
    if re.fullmatch(r"\d{1,2}-[A-Za-zÀ-ÿ]{3,}-\d{2,4}", value):
        return "dash_month"
    if re.fullmatch(r"\d{1,2}/\d{1,2}/\d{2,4}", value):
        return "slash"
    if re.fullmatch(r"\d{1,2}\.\d{1,2}\.\d{2,4}", value):
        return "dot"
    return "other"

def _probe(kind, path):
    result={"kind":kind}
    rows=[]
    header_pages=[]
    table_counts=[]
    with pdfplumber.open(path) as pdf:
        result["page_count"]=len(pdf.pages)
        for page_no,page in enumerate(pdf.pages,start=1):
            tables=page.extract_tables()
            table_counts.append(len(tables))
            if len(tables)!=1 or not tables[0]:
                continue
            table=tables[0]
            start=0
            first=[_clean(x) for x in table[0]]
            if _is_header(first):
                start=1
                header_pages.append(page_no)
            for table_row,row in enumerate(table[start:],start=start+1):
                cells=[_clean(x) for x in row]
                if any(cells):
                    rows.append((page_no,table_row,cells))
    result["header_pages"]=header_pages
    result["tables_per_page"]=dict(Counter(table_counts))
    result["data_rows"]=len(rows)
    result["column_counts"]=dict(Counter(len(c) for _,_,c in rows))
    numbers=[]
    nonnumeric=[]
    duplicates=[]
    seen=set()
    required_gaps=[]
    identifier_shapes=Counter()
    date_shapes=Counter()
    date_anomalies=[]
    status_buckets=Counter()
    other_status_values=Counter()
    for page_no,table_row,cells in rows:
        raw_no=cells[0] if cells else ""
        if re.fullmatch(r"\d+",raw_no):
            n=int(raw_no)
            numbers.append(n)
            if n in seen: duplicates.append(n)
            seen.add(n)
        else:
            nonnumeric.append({"page":page_no,"table_row":table_row,"first_cell":raw_no[:80]})
            n=None
        if kind=="listed" and len(cells)==9:
            required={"name":cells[1],"office":cells[2],"identifier":cells[4],"registration":cells[5],"activities":cells[7]}
            gaps=[k for k,v in required.items() if not v]
            if gaps: required_gaps.append({"n":n,"page":page_no,"gaps":gaps})
            ident=cells[4].strip()
            if re.fullmatch(r"\d{11}",ident): identifier_shapes["strict_11"]+=1
            elif re.fullmatch(r"[A-Za-z0-9]{16}",ident): identifier_shapes["strict_16"]+=1
            elif not ident: identifier_shapes["empty"]+=1
            else: identifier_shapes["other"]+=1
            for label,idx in (("registration",5),("expiry",6)):
                shp=_shape(cells[idx]); date_shapes[f"{label}:{shp}"]+=1
                if shp in {"other","slash","dot","empty"}:
                    date_anomalies.append({"n":n,"field":label,"shape":shp,"value":cells[idx][:80]})
            note=cells[8].casefold()
            if not note:
                status_buckets["empty_note"]+=1
            elif any(t in note for t in ("rinnovo","aggiornamento","permanenza")) and "istruttoria" in note:
                status_buckets["renewal_or_update_in_progress"]+=1
            elif "aggiornamento in corso" in note:
                status_buckets["renewal_or_update_in_progress"]+=1
            else:
                status_buckets["other_note"]+=1
                # Public log carries only evidence categories, never company identity/text.
                for token in ("art. 34","amministrazione giudiziaria","amm.ne giudiziaria","dissequestro","cancellazione","interdittiva"):
                    if token in note: other_status_values[token]+=1
        elif kind=="applicant" and len(cells)==8:
            required={"name":cells[1],"office":cells[2],"identifier":cells[4],"activities":cells[5],"application":cells[6]}
            gaps=[k for k,v in required.items() if not v]
            if gaps: required_gaps.append({"n":n,"page":page_no,"gaps":gaps})
            ident=cells[4].strip()
            if re.fullmatch(r"\d{11}",ident): identifier_shapes["strict_11"]+=1
            elif re.fullmatch(r"[A-Za-z0-9]{16}",ident): identifier_shapes["strict_16"]+=1
            elif not ident: identifier_shapes["empty"]+=1
            else: identifier_shapes["other"]+=1
            shp=_shape(cells[6]); date_shapes[f"application:{shp}"]+=1
            if shp!="dash_month":
                date_anomalies.append({"n":n,"field":"application","shape":shp,"value":cells[6][:80]})
            outcome=cells[7]
            folded=outcome.casefold()
            if "istruttoria" in folded:
                status_buckets["istruttoria"]+=1
            elif not folded:
                status_buckets["empty_outcome"]+=1
            else:
                status_buckets["other_outcome"]+=1
                other_status_values[outcome]+=1
    result["number_count"]=len(numbers)
    result["number_min"]=min(numbers) if numbers else None
    result["number_max"]=max(numbers) if numbers else None
    result["missing_numbers"]=sorted(set(range(min(numbers),max(numbers)+1))-set(numbers)) if numbers else []
    result["duplicate_numbers"]=duplicates
    result["nonnumeric_rows"]=nonnumeric
    result["required_gaps"]=required_gaps
    result["identifier_shapes"]=dict(identifier_shapes)
    result["date_shapes"]=dict(date_shapes)
    result["date_anomalies"]=date_anomalies
    result["status_buckets"]=dict(status_buckets)
    result["other_status_values"]=dict(other_status_values)
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
    raise AssertionError("REGGIO_SAFE_PROBE="+json.dumps(summary,sort_keys=True,ensure_ascii=False))
