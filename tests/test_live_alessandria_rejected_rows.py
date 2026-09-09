import io
import json
import re
from urllib.request import Request, urlopen

import pdfplumber

URL = "https://prefettura.interno.gov.it/sites/default/files/14/2026-09/white-list-4-settembre-2026.pdf"
DATE = re.compile(r"^\d{1,2}[./]\d{1,2}[./]\d{4}$")
YEAR = re.compile(r"20\d{2}")
UA = "italian-anti-mafia-whitelist/0.1 (+source-resolution)"


def clean(value):
    return " ".join(str(value or "").replace("\u00a0", " ").split())


def test_characterise_all_alessandria_date_variants():
    with urlopen(Request(URL, headers={"User-Agent": UA}), timeout=90) as response:
        body = response.read()
    candidates = 0
    unusual = []
    with pdfplumber.open(io.BytesIO(body)) as pdf:
        for page_no, page in enumerate(pdf.pages, 1):
            for table_no, table in enumerate(page.extract_tables(), 1):
                rows = [[clean(cell) for cell in raw] for raw in table]
                for row_no, row in enumerate(rows):
                    if len(row) < 7 or not row[0] or not row[3]:
                        continue
                    # A source company row carries a year in at least one of the two date columns.
                    if not (YEAR.search(row[4] or "") or YEAR.search(row[5] or "")):
                        continue
                    candidates += 1
                    if DATE.fullmatch(row[4] or "") and DATE.fullmatch(row[5] or ""):
                        continue
                    unusual.append({
                        "page": page_no,
                        "table": table_no,
                        "row": row_no,
                        "values": row,
                        "previous": rows[row_no - 1] if row_no else None,
                        "next": rows[row_no + 1] if row_no + 1 < len(rows) else None,
                    })
    raise AssertionError("AL_DATE_AUDIT=" + json.dumps({"candidate_rows": candidates, "unusual": unusual}, ensure_ascii=False))
