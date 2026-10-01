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
        "targets": {8,34,178,265,533},
    },
    "applicant": {
        "url": "https://prefettura.interno.gov.it/sites/default/files/0/2026-09/elenco-richieste-iscrizioni-white-list-foglio-del-24-set-2026.pdf",
        "sha256": "da60df92f7ffdfc1148ead109395e00ae34e11cb53c01ccc6928bbdff0c71d53",
        "byte_size": 372194,
        "targets": {451,652},
    },
}

def _clean(v):
    return " ".join(str(v or "").replace("\n"," ").split())

def _header(cells):
    f=" | ".join(cells).casefold()
    return "ragione sociale" in f and ("codice fiscale" in f or "partita iva" in f)

def _sig(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16] if text else ""

def _probe(kind,path,targets):
    out={"page_rows":[],"targets":{},"identifier_other_rows":[],"status_other_rows":[]}
    with pdfplumber.open(path) as pdf:
        for page_no,page in enumerate(pdf.pages,1):
            count=0
            tables=page.find_tables()
            if len(tables)!=1:
                raise AssertionError(f"table count drift {kind} p{page_no}: {len(tables)}")
            table=tables[0]
            extracted=table.extract()
            for idx,(row_obj,raw) in enumerate(zip(table.rows,extracted),1):
                cells=[_clean(x) for x in raw]
                if not any(cells) or _header(cells):
                    continue
                count+=1
                n=int(cells[0]) if cells and re.fullmatch(r"\d+",cells[0]) else None
                if n in targets:
                    blank_fallback={}
                    for col,(value,bbox) in enumerate(zip(cells,row_obj.cells)):
                        if value or bbox is None:
                            continue
                        crop=page.crop(bbox,strict=False)
                        recovered=_clean(crop.extract_text() or "")
                        blank_fallback[str(col)]={"nonempty":bool(recovered),"length":len(recovered),"sha16":_sig(recovered)}
                    out["targets"][str(n)]={
                        "page":page_no,
                        "table_row":idx,
                        "nonempty_mask":[bool(x) for x in cells],
                        "lengths":[len(x) for x in cells],
                        "blank_cell_fallback":blank_fallback,
                        "note_tokens":{
                            "istruttoria":"istruttoria" in (cells[-1].casefold() if cells else ""),
                            "rinnovo":"rinnovo" in (cells[-1].casefold() if cells else ""),
                            "aggiornamento":"aggiornamento" in (cells[-1].casefold() if cells else ""),
                            "art34":"art. 34" in (cells[-1].casefold() if cells else ""),
                            "giudiziaria":"giudiziaria" in (cells[-1].casefold() if cells else ""),
                        },
                    }
                ident=cells[4].strip() if len(cells)>4 else ""
                if ident and not (re.fullmatch(r"\d{11}",ident) or re.fullmatch(r"[A-Za-z0-9]{16}",ident)):
                    out["identifier_other_rows"].append({"n":n,"length":len(ident),"chars":"".join(sorted(set(re.sub(r"[A-Za-z0-9]","A",ident))))[:20]})
                if kind=="listed" and len(cells)==9:
                    note=cells[8].casefold()
                    if note and not (
                        (any(t in note for t in ("rinnovo","aggiornamento","permanenza")) and "istruttoria" in note)
                        or "aggiornamento in corso" in note
                    ):
                        out["status_other_rows"].append(n)
                if kind=="applicant" and len(cells)==8:
                    outcome=cells[7].casefold()
                    if "istruttoria" not in outcome:
                        out["status_other_rows"].append(n)
            out["page_rows"].append(count)
    return out

def test_reggio_calabria_live_structure_probe(tmp_path: Path):
    summary={}
    for kind,cfg in SOURCES.items():
        req=urllib.request.Request(cfg["url"],headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req,timeout=60) as resp:
            payload=resp.read()
        assert len(payload)==cfg["byte_size"]
        assert hashlib.sha256(payload).hexdigest()==cfg["sha256"]
        p=tmp_path/f"{kind}.pdf"; p.write_bytes(payload)
        summary[kind]=_probe(kind,p,cfg["targets"])
    raise AssertionError("REGGIO_ANOMALY_PROBE="+json.dumps(summary,sort_keys=True,ensure_ascii=False))
