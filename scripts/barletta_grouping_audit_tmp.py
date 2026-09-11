from __future__ import annotations

import hashlib
import json
import re
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from urllib.request import Request, urlopen

import pdfplumber

URL = "https://prefettura.interno.gov.it/sites/default/files/104/2026-09/white-list-prefettura-di-barletta-andria-trani_1.pdf"
SHA = "d3c0e61942cbdefd03cfa7d99f71b2abbfc430f25ff86b8693d44ef14de07e13"
DATEISH = re.compile(r"\d{1,2}[./-]\d{1,2}[./-](?:\d{4}|\d{3}\s*\d)|\d{1,2}/\d{1,2}/\d{1,2}/\d{4}")
STRICT_ID = re.compile(r"(?<![A-Za-z0-9])(?:\d{11}|[A-Za-z0-9]{16})(?![A-Za-z0-9])", re.I)
SECTION = re.compile(r"\bSezione\s+([IVX]+)\b", re.I)
ADMIN = ("denominazio", "ragione sociale", "elenco fornitori", "p.i./cf", "iscrizione nelle white", "provvediment")


def clean(v):
    return " ".join(str(v or "").replace("\u00a0", " ").split())


def strict_ids(text):
    out=[]
    for m in STRICT_ID.finditer(clean(text)):
        v=m.group(0).upper()
        if v not in out: out.append(v)
    return out


def date_cells(row):
    out=[]
    for i, cell in enumerate(row[3:],3):
        if DATEISH.search(cell): out.append((i,cell))
    return out


def is_candidate(row):
    dates=date_cells(row)
    return bool(row and clean(row[0]) and (len(dates)>=2 or (dates and strict_ids(" | ".join(row[2:])))))


def is_admin(row):
    f=" | ".join(row).casefold()
    return any(x in f for x in ADMIN)


def main():
    req=Request(URL,headers={"User-Agent":"ItalianAntiMafiaWhitelistArchive/1.0 grouping-audit"})
    with urlopen(req,timeout=90) as r: body=r.read()
    assert hashlib.sha256(body).hexdigest()==SHA
    logical=[]; current=None; previous_section=None
    with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
        tmp.write(body); tmp.flush()
        with pdfplumber.open(tmp.name) as pdf:
            for pno,page in enumerate(pdf.pages,1):
                text=clean(page.extract_text() or "")
                marker=SECTION.search(text)
                new_section=marker.group(1).upper() if marker else None
                rows=[]
                for table in page.find_tables():
                    rows.extend([[clean(x) for x in row] for row in (table.extract() or []) if any(clean(x) for x in row)])
                candidate_indices=[i for i,row in enumerate(rows) if is_candidate(row)]
                first_candidate=min(candidate_indices) if candidate_indices else None
                # Leading fragments continue the previous record only when the page remains in the same section.
                if logical and first_candidate is not None and (new_section is None or new_section==current):
                    for row in rows[:first_candidate]:
                        if not is_admin(row) and len(" ".join(row))>5:
                            logical[-1]["continuations"].append(row)
                if new_section: current=new_section
                previous_section=current
                for i,row in enumerate(rows):
                    if not is_candidate(row): continue
                    logical.append({"page":pno,"row":i+1,"section":current,"cells":row,"continuations":[]})
                    j=i+1
                    while j<len(rows) and not is_candidate(rows[j]):
                        extra=rows[j]
                        nonempty=[x for x in extra if x]
                        repeated=len(nonempty)>=4 and len(set(nonempty))==1
                        if not is_admin(extra) and not repeated and len(" ".join(extra))>5:
                            logical[-1]["continuations"].append(extra)
                        j+=1
    assert len(logical)==1013,len(logical)
    parsed=[]
    for item in logical:
        row=item["cells"]; dates=date_cells(row)
        raw_dates=[v for _,v in dates]
        ids=strict_ids(" | ".join(row[2:]))
        for extra in item["continuations"]: ids += [v for v in strict_ids(" | ".join(extra[2:])) if v not in ids]
        name=clean(" ".join([row[0]]+[x[0] for x in item["continuations"] if x]))
        office=clean(" ".join([row[1] if len(row)>1 else ""]+[x[1] if len(x)>1 else "" for x in item["continuations"]]))
        status="renewal_update_in_progress" if "aggiornament" in " ".join(row).casefold() else "listed"
        parsed.append({"page":item["page"],"row":item["row"],"section":item["section"],"name":name,"office":office,"ids":ids,"dates":raw_dates,"status":status})
    groups={}
    ambiguous=[]
    for rec in parsed:
        dates=tuple(rec["dates"][-2:])
        if rec["ids"]:
            key=("id",tuple(sorted(rec["ids"])),dates,rec["status"])
        else:
            key=("name",rec["name"].casefold(),dates,rec["status"])
        g=groups.setdefault(key,{"records":[],"sections":[]})
        g["records"].append(rec)
        if rec["section"] not in g["sections"]: g["sections"].append(rec["section"])
    multi=[g for g in groups.values() if len(g["records"])>1]
    # Detect same strict identity mapping to conflicting date/status tuples.
    by_id=defaultdict(set)
    for rec in parsed:
        if rec["ids"]: by_id[tuple(sorted(rec["ids"]))].add((tuple(rec["dates"][-2:]),rec["status"]))
    conflicts={"|".join(k):sorted(map(str,v)) for k,v in by_id.items() if len(v)>1}
    result={
      "sector_rows":len(parsed),"grouped_records":len(groups),
      "sector_rows_by_section":dict(Counter(r["section"] for r in parsed)),
      "sector_status_counts":dict(Counter(r["status"] for r in parsed)),
      "group_size_distribution":dict(Counter(len(g["records"]) for g in groups.values())),
      "multi_section_group_count":sum(len(g["sections"])>1 for g in groups.values()),
      "identifier_conflict_count":len(conflicts),"identifier_conflicts":conflicts,
      "sample_multi_groups":multi[:20],
      "no_strict_identifier_sector_rows":sum(not r["ids"] for r in parsed),
    }
    Path("tmp/barletta-andria-trani-grouping.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:v for k,v in result.items() if k not in {"identifier_conflicts","sample_multi_groups"}},ensure_ascii=False,indent=2))

if __name__=="__main__": main()
