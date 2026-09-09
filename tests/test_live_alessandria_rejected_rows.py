import io
import json
import re
from collections import defaultdict
from datetime import date
from urllib.request import Request, urlopen

import pdfplumber

URL = "https://prefettura.interno.gov.it/sites/default/files/14/2026-09/white-list-4-settembre-2026.pdf"
DATE = re.compile(r"^(\d{1,2})[./](\d{1,2})[./](\d{4})$")
YEAR = re.compile(r"20\d{2}")
UA = "italian-anti-mafia-whitelist/0.1 (+source-resolution)"


def clean(value):
    return " ".join(str(value or "").replace("\u00a0", " ").split())


def valid_date(value):
    match = DATE.fullmatch(value or "")
    if not match:
        return False
    day, month, year = map(int, match.groups())
    try:
        date(year, month, day)
    except ValueError:
        return False
    return True


def test_characterise_all_alessandria_date_variants():
    with urlopen(Request(URL, headers={"User-Agent": UA}), timeout=90) as response:
        body = response.read()

    candidate_rows = []
    current_section = ""
    with pdfplumber.open(io.BytesIO(body)) as pdf:
        for page_no, page in enumerate(pdf.pages, 1):
            for table_no, table in enumerate(page.extract_tables(), 1):
                rows = [[clean(cell) for cell in raw] for raw in table]
                for row_no, row in enumerate(rows):
                    if row and row[0].upper().startswith("SEZIONE") and not any(row[1:]):
                        current_section = row[0]
                        continue
                    if len(row) < 7 or not row[0] or not row[3]:
                        continue
                    if not (YEAR.search(row[4] or "") or YEAR.search(row[5] or "")):
                        continue
                    candidate_rows.append(
                        {
                            "page": page_no,
                            "table": table_no,
                            "row": row_no,
                            "section": current_section,
                            "values": row[:7],
                            "dates_valid": [valid_date(row[4]), valid_date(row[5])],
                        }
                    )

    valid_groups = defaultdict(set)
    malformed = []
    for item in candidate_rows:
        row = item["values"]
        key = (row[0], row[3], row[6])
        if all(item["dates_valid"]):
            valid_groups[key].add((row[4], row[5]))
        else:
            malformed.append(item)

    malformed_matches = []
    for item in malformed:
        row = item["values"]
        key = (row[0], row[3], row[6])
        matches = sorted(valid_groups.get(key, set()))
        malformed_matches.append(
            {
                **item,
                "matching_valid_date_pairs": matches,
                "matching_valid_pair_count": len(matches),
            }
        )

    ambiguous_valid_keys = [
        {
            "key": list(key),
            "valid_date_pairs": sorted(pairs),
        }
        for key, pairs in valid_groups.items()
        if len(pairs) > 1
    ]
    match_counts = {
        "zero": sum(item["matching_valid_pair_count"] == 0 for item in malformed_matches),
        "one": sum(item["matching_valid_pair_count"] == 1 for item in malformed_matches),
        "multiple": sum(item["matching_valid_pair_count"] > 1 for item in malformed_matches),
    }

    raise AssertionError(
        "AL_DATE_LINKAGE_AUDIT="
        + json.dumps(
            {
                "candidate_rows": len(candidate_rows),
                "valid_rows": len(candidate_rows) - len(malformed),
                "malformed_rows": len(malformed),
                "malformed_match_counts": match_counts,
                "malformed": malformed_matches,
                "ambiguous_valid_identity_outcome_keys": ambiguous_valid_keys,
            },
            ensure_ascii=False,
        )
    )
