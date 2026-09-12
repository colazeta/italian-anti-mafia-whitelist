from __future__ import annotations

import hashlib
import io
import json
import re
from collections import Counter
from urllib.request import Request, urlopen

import openpyxl

URL = "https://prefettura.interno.gov.it/sites/default/files/0/2026-09/elenco-ditte-iscritte-10-settembre-2026.xlsx"
SHA = "509e6724de2d4d63f403e254236ec2c5b77077d676ee8c17382464d5c9da07a7"
SECTION_RE = re.compile(r"^\s*sezione\s*(i{1,3}|iv|v|vi{0,3}|ix|x)\s*$", re.I)


def clean(value):
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def fetch():
    request = Request(URL, headers={"User-Agent": "italian-anti-mafia-whitelist/layout-audit"})
    with urlopen(request, timeout=90) as response:
        body = response.read()
    digest = hashlib.sha256(body).hexdigest()
    if digest != SHA:
        raise SystemExit(f"sha drift {digest} != {SHA}")
    return body


def main():
    wb = openpyxl.load_workbook(io.BytesIO(fetch()), data_only=True, read_only=True)
    ws = wb["Foglio1"]
    current_section = ""
    columns = None
    patterns = Counter()
    anomalies = []
    headers = []
    for rowno, row in enumerate(ws.iter_rows(values_only=True), start=1):
        vals = [clean(v) for v in row]
        nonempty = [(i, value) for i, value in enumerate(vals) if value]
        section_hits = [SECTION_RE.fullmatch(value).group(1).upper() for _, value in nonempty if SECTION_RE.fullmatch(value)]
        if section_hits:
            current_section = section_hits[0]
            columns = None
            continue
        if any("ragione sociale" in value.casefold() for value in vals):
            name = next(i for i, value in enumerate(vals) if "ragione sociale" in value.casefold())
            office = next(i for i, value in enumerate(vals) if "sede legale" in value.casefold())
            ident = next(i for i, value in enumerate(vals) if "codice fiscale" in value.casefold() or "partita iva" in value.casefold())
            listing = next(i for i, value in enumerate(vals) if "data iscrizione" in value.casefold() or "data di iscrizione" in value.casefold())
            expiry = next(i for i, value in enumerate(vals) if "data scadenza" in value.casefold() or "data di scadenza" in value.casefold())
            update = next(i for i, value in enumerate(vals) if "aggiornamento" in value.casefold())
            columns = (name, office, ident, listing, expiry, update)
            headers.append({"row": rowno, "section": current_section, "columns": columns, "values": vals})
            continue
        if columns is None or not nonempty:
            continue
        name, office, ident, listing, expiry, update = columns
        # Rows that look company-like based on a fiscal-id/date token anywhere.
        has_company_signal = any(re.fullmatch(r"\d{11}", value) for _, value in nonempty) or any(
            re.fullmatch(r"\d{1,2}[./-]\d{1,2}[./-]\d{2,5}|\d{4}-\d{2}-\d{2}(?: 00:00:00)?", value)
            for _, value in nonempty
        )
        if not has_company_signal:
            continue
        pattern = tuple(i for i, _ in nonempty)
        patterns[(current_section, pattern)] += 1
        expected_name = vals[name] if name < len(vals) else ""
        if not expected_name:
            anomalies.append({
                "row": rowno,
                "section": current_section,
                "header_columns": columns,
                "nonempty": nonempty,
                "before": [[i, vals[i]] for i in range(max(0, name - 3), min(len(vals), update + 4))],
            })
    out = {
        "headers": headers,
        "pattern_counts": [
            {"section": section, "indices": list(indices), "count": count}
            for (section, indices), count in patterns.most_common()
        ],
        "expected_name_blank_company_like_count": len(anomalies),
        "expected_name_blank_company_like_rows": anomalies,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
