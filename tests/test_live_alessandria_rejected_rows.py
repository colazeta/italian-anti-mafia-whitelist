import io
import json
import re
from urllib.request import Request, urlopen

import pdfplumber

URL = "https://prefettura.interno.gov.it/sites/default/files/14/2026-09/white-list-4-settembre-2026.pdf"
DATE = re.compile(r"^\d{1,2}[./]\d{1,2}[./]\d{4}$")
UA = "italian-anti-mafia-whitelist/0.1 (+source-resolution)"


def clean(value):
    return " ".join(str(value or "").replace("\u00a0", " ").split())


def test_characterise_rejected_alessandria_rows():
    with urlopen(Request(URL, headers={"User-Agent": UA}), timeout=90) as response:
        body = response.read()
    rejected = []
    with pdfplumber.open(io.BytesIO(body)) as pdf:
        for page_no, page in enumerate(pdf.pages, 1):
            for table_no, table in enumerate(page.extract_tables(), 1):
                rows = [[clean(cell) for cell in raw] for raw in table]
                for row_no, row in enumerate(rows):
                    if len(row) < 5 or not DATE.fullmatch(row[4] or ""):
                        continue
                    accepted = len(row) >= 7 and DATE.fullmatch(row[5] or "") and bool(row[0]) and bool(row[3])
                    if accepted:
                        continue
                    rejected.append({
                        "page": page_no,
                        "table": table_no,
                        "row": row_no,
                        "values": row,
                        "previous": rows[row_no - 1] if row_no else None,
                        "next": rows[row_no + 1] if row_no + 1 < len(rows) else None,
                        "page_text": clean(page.extract_text() or "")[:4000],
                    })
    assert rejected == [], "AL_REJECTED=" + json.dumps(rejected, ensure_ascii=False)
