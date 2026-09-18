from __future__ import annotations

import json
import re
from collections import Counter
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

SOURCES = {
    "listed": "https://prefettura.interno.gov.it/it/prefetture/taranto/white-list-elenco-imprese-iscritte",
    "applicants": "https://prefettura.interno.gov.it/it/prefetture/taranto/elenco-imprese-richiedenti-liscrizione-nella-white-list",
}
HEADERS = {
    "listed": (
        "ragione sociale",
        "sede legale",
        "codice fiscale - partita iva",
        "data iscrizione",
        "data scadenza iscrizione",
        "sezioni",
        "note",
    ),
    "applicants": (
        "ragione sociale",
        "sede legale",
        "codice fiscale/partita iva",
        "sezioni",
        "data di presentazione dell'istanza",
    ),
}


def clean(value: str) -> str:
    return " ".join(value.split())


def rows_for(table) -> list[list[str]]:
    rows: list[list[str]] = []
    for tr in table.find_all("tr"):
        if tr.find_parent("table") is not table:
            continue
        cells = [clean(cell.get_text(" ", strip=True)) for cell in tr.find_all(["th", "td"], recursive=False)]
        if any(cells):
            rows.append(cells)
    return rows


def identifier_kind(raw: str) -> str:
    raw = "".join(raw.split()).upper()
    if not raw:
        return "blank"
    if re.fullmatch(r"\d{11}", raw):
        return "numeric11"
    if re.fullmatch(r"[A-Z]{6}[0-9A-Z]{10}", raw):
        return "cf16"
    return "nonstandard"


def probe(kind: str) -> dict[str, object]:
    request = Request(SOURCES[kind], headers={"User-Agent": "italian-anti-mafia-whitelist/0.1", "Accept": "text/html,*/*"})
    with urlopen(request, timeout=60) as response:  # noqa: S310 - fixed official pages
        body = response.read()
    soup = BeautifulSoup(body, "html.parser")
    candidates: list[tuple[list[str], list[list[str]]]] = []
    table_shapes: list[list[int]] = []
    for table in soup.find_all("table"):
        rows = rows_for(table)
        table_shapes.append([len(row) for row in rows[:12]])
        for index, row in enumerate(rows):
            if tuple(value.casefold() for value in row) == HEADERS[kind]:
                candidates.append((row, rows[index + 1 :]))
    if len(candidates) != 1:
        raise RuntimeError(json.dumps({"kind": kind, "candidate_tables": len(candidates), "table_shapes": table_shapes}))
    header, tail = candidates[0]
    width = len(header)
    rows = [row for row in tail if len(row) == width and any(row)]
    malformed_width = [row for row in tail if len(row) != width and any(row)]
    good_date = re.compile(r"^\d{2}/\d{2}/\d{4}$")
    result: dict[str, object] = {
        "kind": kind,
        "bytes": len(body),
        "table_count": len(soup.find_all("table")),
        "header": header,
        "rows": len(rows),
        "first_rows": rows[:4],
        "last_rows": rows[-4:],
        "identifier_counts": dict(Counter(identifier_kind(row[2]) for row in rows)),
        "nonstandard_identifier_rows": [row for row in rows if identifier_kind(row[2]) == "nonstandard"],
        "malformed_width_count": len(malformed_width),
        "malformed_width_rows": malformed_width,
    }
    if kind == "applicants":
        result["application_date_counts"] = dict(Counter("valid_format" if good_date.fullmatch(row[4]) else "nonstandard" for row in rows))
        result["nonstandard_date_rows"] = [row for row in rows if not good_date.fullmatch(row[4])]
    else:
        result["listing_date_counts"] = dict(Counter("valid_format" if good_date.fullmatch(row[3]) else "nonstandard" for row in rows))
        result["expiry_date_counts"] = dict(Counter("valid_format" if good_date.fullmatch(row[4]) else "nonstandard" for row in rows))
        result["nonstandard_date_rows"] = [row for row in rows if not good_date.fullmatch(row[3]) or not good_date.fullmatch(row[4])]
        result["note_counts"] = dict(Counter(clean(row[6]) for row in rows))
    return result


if __name__ == "__main__":
    print(json.dumps({kind: probe(kind) for kind in ("listed", "applicants")}, ensure_ascii=False, indent=2, sort_keys=True))
