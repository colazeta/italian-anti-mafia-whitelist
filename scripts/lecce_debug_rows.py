from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

import pdfplumber

URL = "https://prefettura.interno.gov.it/sites/default/files/49/2026-09/elenco-white-list-per-categoria-aggiornato-9-settembre-2026.pdf"
SHA = "acbe7b735107d48735bc8d01902fc73d49f00e6d8d6ef11dc0c1f9dfd344765d"
TARGET = "05054270755"
PAGES = {1, 19, 39, 53, 63, 68}
OUT = Path("tmp/lecce_debug_rows.json")


def clean(value: object) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split())


def main() -> None:
    req = Request(URL, headers={"User-Agent": "italian-anti-mafia-whitelist/0.1 (+source audit)", "Accept": "application/pdf,*/*"})
    with urlopen(req, timeout=90) as response:  # noqa: S310 - fixed official source
        body = response.read()
    digest = hashlib.sha256(body).hexdigest()
    if digest != SHA:
        raise RuntimeError(f"source changed: {digest}")
    pdf_path = Path("/tmp/lecce-listed.pdf")
    pdf_path.write_bytes(body)
    result: dict[str, object] = {"sha256": digest, "target": TARGET, "pages": {}}
    with pdfplumber.open(pdf_path) as pdf:
        for page_no in sorted(PAGES):
            page = pdf.pages[page_no - 1]
            tables = page.find_tables()
            if len(tables) != 1:
                raise RuntimeError(f"page {page_no}: {len(tables)} tables")
            rows = [[clean(cell) for cell in row] for row in (tables[0].extract() or [])]
            hits = [i for i, row in enumerate(rows) if any(TARGET in cell for cell in row)]
            snippets = []
            for hit in hits:
                lo, hi = max(0, hit - 2), min(len(rows), hit + 3)
                snippets.append({"hit_index": hit, "rows": [{"index": i, "cells": rows[i]} for i in range(lo, hi)]})
            result["pages"][str(page_no)] = {"text": page.extract_text() or "", "hits": snippets}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"sha256": digest, "page_hit_counts": {p: len(v["hits"]) for p, v in result["pages"].items()}}, sort_keys=True))


if __name__ == "__main__":
    main()
