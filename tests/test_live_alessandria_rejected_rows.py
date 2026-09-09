import io
import json
import re
from collections import defaultdict
from datetime import date
from urllib.request import Request, urlopen

import pdfplumber

URL = "https://prefettura.interno.gov.it/sites/default/files/14/2026-09/white-list-4-settembre-2026.pdf"
DATE = re.compile(r"^(\d{1,2})[./](\d{1,2})[./](\d{4})$")
YEAR = re.compile(r"20(?:\s?\d){2}")
UA = "italian-anti-mafia-whitelist/0.1 (+source-resolution)"


def clean(value):
    return " ".join(str(value or "").replace("\u00a0", " ").split())


def source_date(value):
    raw = clean(value)
    # Alessandria's official PDF uses an ordinal marker after day 1 in a few
    # cells and one extracted year contains an embedded layout space. Treat
    # those as explicit source typography, not as a guessed missing digit.
    candidate = re.sub(r"^(\d{1,2})[°º]([./])", r"\1\2", raw)
    candidate = re.sub(r"(?<=\d)\s+(?=\d)", "", candidate)
    match = DATE.fullmatch(candidate)
    if not match:
        return ""
    day, month, year = map(int, match.groups())
    try:
        date(year, month, day)
    except ValueError:
        return ""
    return f"{year:04d}-{month:02d}-{day:02d}"


def test_characterise_all_alessandria_date_variants():
    with urlopen(Request(URL, headers={"User-Agent": UA}), timeout=90) as response:
        body = response.read()

    candidate_rows = []
    current_section = ""
    with pdfplumber.open(io.BytesIO(body)) as pdf:
        for page_no, page in enumerate(pdf.pages, 1):
            for table_no, table in enumerate(page.extract_tables(), 1):
                for row_no, raw in enumerate(table):
                    row = [clean(cell) for cell in raw]
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
                            "listing": source_date(row[4]),
                            "expiry": source_date(row[5]),
                        }
                    )

    groups = defaultdict(lambda: {"rows": [], "sections": set(), "listing": set(), "expiry": set(), "raw_pairs": set()})
    for item in candidate_rows:
        row = item["values"]
        key = (row[0], row[3], row[6])
        group = groups[key]
        group["rows"].append(item)
        if item["section"]:
            group["sections"].add(item["section"])
        if item["listing"]:
            group["listing"].add(item["listing"])
        if item["expiry"]:
            group["expiry"].add(item["expiry"])
        group["raw_pairs"].add((row[4], row[5]))

    conflicts = []
    incomplete = []
    malformed_groups = []
    for key, group in groups.items():
        if len(group["listing"]) > 1 or len(group["expiry"]) > 1:
            conflicts.append(
                {
                    "key": list(key),
                    "normalised_listing": sorted(group["listing"]),
                    "normalised_expiry": sorted(group["expiry"]),
                    "raw_pairs": sorted(group["raw_pairs"]),
                    "sections": sorted(group["sections"]),
                }
            )
        if not group["listing"] or not group["expiry"]:
            incomplete.append(
                {
                    "key": list(key),
                    "normalised_listing": sorted(group["listing"]),
                    "normalised_expiry": sorted(group["expiry"]),
                    "raw_pairs": sorted(group["raw_pairs"]),
                    "sections": sorted(group["sections"]),
                }
            )
        bad_rows = [item for item in group["rows"] if not item["listing"] or not item["expiry"]]
        if bad_rows:
            malformed_groups.append(
                {
                    "key": list(key),
                    "normalised_listing": sorted(group["listing"]),
                    "normalised_expiry": sorted(group["expiry"]),
                    "raw_pairs": sorted(group["raw_pairs"]),
                    "sections": sorted(group["sections"]),
                    "malformed_rows": bad_rows,
                }
            )

    raise AssertionError(
        "AL_GROUPING_AUDIT="
        + json.dumps(
            {
                "candidate_sector_rows": len(candidate_rows),
                "identity_outcome_groups": len(groups),
                "groups_with_date_conflicts": len(conflicts),
                "groups_missing_any_normalised_date": len(incomplete),
                "groups_with_malformed_raw_rows": len(malformed_groups),
                "conflicts": conflicts,
                "incomplete": incomplete,
                "malformed_groups": malformed_groups,
            },
            ensure_ascii=False,
        )
    )
