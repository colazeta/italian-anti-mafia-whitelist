from __future__ import annotations

import hashlib
import json
import re
import tempfile
from collections import Counter
from pathlib import Path
from urllib.request import Request, urlopen

import pdfplumber

SOURCES = {
    "listed": (
        "https://prefettura.interno.gov.it/sites/default/files/104/2026-09/white-list-prefettura-di-barletta-andria-trani_1.pdf",
        "d3c0e61942cbdefd03cfa7d99f71b2abbfc430f25ff86b8693d44ef14de07e13",
        211,
    ),
    "applicants": (
        "https://prefettura.interno.gov.it/sites/default/files/104/2026-09/elenco-imprese-rich-iscriz-white-list-prefettura-di-barletta-andria-trani_0.pdf",
        "ce460ca66f2d996784ac28d559af5fe702ae8a1d72ed80affeb70a0cb36b0d57",
        15,
    ),
}
DATEISH = re.compile(r"(?<!\d)\d{1,2}[./-]\d{1,2}[./-]\d{2,4}(?!\d)")
ID11 = re.compile(r"(?<!\d)\d{11}(?!\d)")
CF16 = re.compile(r"(?<![A-Za-z0-9])[A-Za-z0-9]{16}(?![A-Za-z0-9])")
SECTION = re.compile(r"\bSezione\s+([IVX]+)\b", re.I)


def clean(value: object) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split())


def fetch(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": "ItalianAntiMafiaWhitelistArchive/1.0 parser-boundary-audit"})
    with urlopen(req, timeout=90) as response:
        return response.read()


def main() -> None:
    result = {}
    for kind, (url, expected_sha, expected_pages) in SOURCES.items():
        body = fetch(url)
        observed = hashlib.sha256(body).hexdigest()
        if observed != expected_sha:
            raise SystemExit(f"{kind}: byte drift {observed}")
        width_counts = Counter()
        table_counts = Counter()
        candidates = []
        suspicious = []
        malformed = []
        sections = []
        current_section = None
        with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
            tmp.write(body)
            tmp.flush()
            with pdfplumber.open(tmp.name) as pdf:
                if len(pdf.pages) != expected_pages:
                    raise SystemExit(f"{kind}: page drift {len(pdf.pages)}")
                for pno, page in enumerate(pdf.pages, 1):
                    text = clean(page.extract_text() or "")
                    marker = SECTION.search(text)
                    if marker:
                        current_section = marker.group(1).upper()
                        sections.append([pno, current_section])
                    tables = page.find_tables()
                    table_counts[len(tables)] += 1
                    for table in tables:
                        for ridx, raw in enumerate(table.extract() or [], 1):
                            row = [clean(cell) for cell in raw]
                            if not any(row):
                                continue
                            width_counts[len(row)] += 1
                            joined = " | ".join(row)
                            dates = DATEISH.findall(joined)
                            ids = ID11.findall(joined)
                            cfs = CF16.findall(joined)
                            for value in dates:
                                parts = re.split(r"[./-]", value)
                                try:
                                    day, month, year = map(int, parts)
                                    if len(parts[2]) != 4 or not 1 <= day <= 31 or not 1 <= month <= 12:
                                        raise ValueError
                                except Exception:
                                    malformed.append([pno, ridx, value, row])
                            strong = bool((ids or cfs) and dates) or (kind == "listed" and len(dates) >= 2)
                            if kind == "applicants" and dates and len(row) >= 6 and clean(row[4]):
                                strong = True
                            if strong:
                                candidates.append({"page": pno, "row": ridx, "width": len(row), "section": current_section, "cells": row, "dates": dates, "ids": ids, "cfs": cfs})
                            else:
                                folded = joined.casefold()
                                administrative = any(token in folded for token in ("denominazio", "ragione sociale", "elenco fornitori", "elenco delle imprese", "p.i./cf"))
                                if not administrative and len(joined) > 5:
                                    suspicious.append({"page": pno, "row": ridx, "width": len(row), "section": current_section, "cells": row})
        per_section = Counter(x["section"] or "UNKNOWN" for x in candidates)
        update_rows = sum("aggiornament" in " ".join(x["cells"]).casefold() for x in candidates)
        result[kind] = {
            "sha256": expected_sha,
            "pages": expected_pages,
            "table_counts": dict(table_counts),
            "width_counts": dict(width_counts),
            "section_markers": sections,
            "candidate_count": len(candidates),
            "candidate_by_section": dict(per_section),
            "update_candidate_rows": update_rows,
            "malformed_dates": malformed,
            "suspicious_noncandidate_count": len(suspicious),
            "suspicious_noncandidate_rows": suspicious[:200],
            "first_candidates": candidates[:10],
            "last_candidates": candidates[-10:],
        }
    Path("tmp").mkdir(exist_ok=True)
    Path("tmp/barletta-andria-trani-structure.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: {kk: v[kk] for kk in ("pages", "table_counts", "width_counts", "candidate_count", "candidate_by_section", "update_candidate_rows", "suspicious_noncandidate_count")} for k, v in result.items()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
