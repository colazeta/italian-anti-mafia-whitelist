from __future__ import annotations

import json
import re
from collections import Counter
from html.parser import HTMLParser
from urllib.request import Request, urlopen


SOURCES = {
    "listed": "https://prefettura.interno.gov.it/it/prefetture/taranto/white-list-elenco-imprese-iscritte",
    "applicants": "https://prefettura.interno.gov.it/it/prefetture/taranto/elenco-imprese-richiedenti-liscrizione-nella-white-list",
}
USER_AGENT = "italian-anti-mafia-whitelist/0.1 (+Taranto source-boundary audit)"


class TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._parts: list[str] | None = None
        self._cell_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        tag = tag.casefold()
        if tag == "table":
            if self._table is not None:
                raise RuntimeError("nested table in Taranto source")
            self._table = []
        elif tag == "tr" and self._table is not None:
            if self._row is not None:
                raise RuntimeError("nested row in Taranto source")
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            if self._parts is None:
                self._parts = []
                self._cell_depth = 0
            else:
                self._cell_depth += 1
        elif tag == "br" and self._parts is not None:
            self._parts.append(" ")

    def handle_data(self, data: str) -> None:
        if self._parts is not None:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if tag in {"td", "th"} and self._parts is not None:
            if self._cell_depth:
                self._cell_depth -= 1
                return
            if self._row is None:
                raise RuntimeError("Taranto cell closed outside row")
            self._row.append(" ".join("".join(self._parts).split()))
            self._parts = None
        elif tag == "tr" and self._row is not None:
            if self._table is None:
                raise RuntimeError("Taranto row closed outside table")
            if any(self._row):
                self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            if self._row is not None or self._parts is not None:
                raise RuntimeError("Taranto table ended incomplete")
            if self._table:
                self.tables.append(self._table)
            self._table = None


def fetch_tables(url: str) -> tuple[bytes, list[list[list[str]]]]:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*"})
    with urlopen(request, timeout=60) as response:  # noqa: S310 - fixed official sources
        body = response.read()
    text = body.decode("utf-8")
    parser = TableParser()
    parser.feed(text)
    parser.close()
    return body, parser.tables


def fold(row: list[str]) -> tuple[str, ...]:
    return tuple(" ".join(value.split()).casefold() for value in row)


def classify_identifier(raw: str) -> str:
    raw = "".join(raw.split()).upper()
    if not raw:
        return "blank"
    if re.fullmatch(r"\d{11}", raw):
        return "numeric11"
    if re.fullmatch(r"[A-Z]{6}[0-9A-Z]{10}", raw):
        return "cf16"
    return "nonstandard"


def candidate_rows(tables: list[list[list[str]]], kind: str) -> tuple[list[str], list[list[str]], list[list[str]]]:
    if kind == "applicants":
        wanted = (
            "ragione sociale",
            "sede legale",
            "codice fiscale/partita iva",
            "sezioni",
            "data di presentazione dell'istanza",
        )
    else:
        wanted = (
            "ragione sociale",
            "sede legale",
            "codice fiscale - partita iva",
            "data iscrizione",
            "data scadenza iscrizione",
            "sezioni",
            "note",
        )
    hits: list[tuple[list[str], list[list[str]]]] = []
    for table in tables:
        for index, row in enumerate(table):
            if fold(row) == wanted:
                hits.append((row, table[index + 1 :]))
    if len(hits) != 1:
        raise RuntimeError(
            json.dumps(
                {
                    "kind": kind,
                    "wanted": wanted,
                    "matching_tables": len(hits),
                    "table_shapes": [[len(row) for row in table[:12]] for table in tables],
                    "table_heads": [table[:4] for table in tables],
                },
                ensure_ascii=False,
            )
        )
    header, tail = hits[0]
    width = len(header)
    rows = [row for row in tail if len(row) == width and any(row)]
    malformed_width = [row for row in tail if any(row) and len(row) != width]
    return header, rows, malformed_width


def probe(kind: str) -> dict[str, object]:
    body, tables = fetch_tables(SOURCES[kind])
    header, rows, malformed_width = candidate_rows(tables, kind)
    identifier_counts = Counter(classify_identifier(row[2]) for row in rows)
    diagnostics: dict[str, object] = {
        "kind": kind,
        "bytes": len(body),
        "table_count": len(tables),
        "header": header,
        "rows": len(rows),
        "first_rows": rows[:4],
        "last_rows": rows[-4:],
        "identifier_counts": dict(identifier_counts),
        "nonstandard_identifier_rows": [row for row in rows if classify_identifier(row[2]) == "nonstandard"],
        "malformed_width_count": len(malformed_width),
        "malformed_width_rows": malformed_width,
    }
    good = re.compile(r"^\d{2}/\d{2}/\d{4}$")
    if kind == "applicants":
        diagnostics["date_counts"] = dict(Counter("valid_format" if good.fullmatch(row[4]) else "nonstandard" for row in rows))
        diagnostics["nonstandard_dates"] = [row for row in rows if not good.fullmatch(row[4])]
    else:
        diagnostics["listing_date_counts"] = dict(Counter("valid_format" if good.fullmatch(row[3]) else "nonstandard" for row in rows))
        diagnostics["expiry_date_counts"] = dict(Counter("valid_format" if good.fullmatch(row[4]) else "nonstandard" for row in rows))
        diagnostics["nonstandard_date_rows"] = [row for row in rows if not good.fullmatch(row[3]) or not good.fullmatch(row[4])]
        diagnostics["note_counts"] = dict(Counter(" ".join(row[6].split()) for row in rows))
    return diagnostics


if __name__ == "__main__":
    print(json.dumps({kind: probe(kind) for kind in ("listed", "applicants")}, ensure_ascii=False, indent=2, sort_keys=True))
