from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import urllib.request
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import pdfplumber

DATE_TOKEN = re.compile(r"(?<!\d)(\d{1,2}[./-]\d{1,2}[./-]\d{4,5})(?!\d)")
STRICT_ID = re.compile(r"(?<![A-Za-z0-9])(?:\d{11}|[A-Za-z0-9]{16})(?![A-Za-z0-9])", re.I)
SECTION = re.compile(r"\bSezione\s+([IVX]+)\b", re.I)


def clean(value: str | None) -> str:
    return " ".join((value or "").split())


def download(url: str, path: Path) -> dict[str, object]:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 white-list-archive-source-audit"})
    with urllib.request.urlopen(request, timeout=60) as response:
        body = response.read()
        status = getattr(response, "status", 200)
        content_type = response.headers.get("Content-Type", "")
    if status != 200 or not body.startswith(b"%PDF"):
        raise RuntimeError(f"bad source fetch {url}: status={status} content-type={content_type} bytes={len(body)}")
    path.write_bytes(body)
    return {
        "url": url,
        "status": status,
        "content_type": content_type,
        "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
    }


def date_key(raw: str) -> str:
    value = clean(raw)
    match = re.fullmatch(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})", value)
    if not match:
        return f"RAW:{value}"
    day, month, year = map(int, match.groups())
    try:
        return f"ISO:{date(year, month, day).isoformat()}"
    except ValueError:
        return f"RAW:{value}"


def main() -> None:
    out = Path("tmp")
    out.mkdir(exist_ok=True)
    listed_path = out / "brindisi-listed.pdf"
    applicant_path = out / "brindisi-applicants.pdf"
    listed_fetch = download(os.environ["LISTED_URL"], listed_path)
    applicant_fetch = download(os.environ["APPLICANT_URL"], applicant_path)

    source_rows: list[dict[str, object]] = []
    markers: list[list[object]] = []
    current_section: str | None = None
    with pdfplumber.open(listed_path) as pdf:
        listed_pages = len(pdf.pages)
        for page_number, page in enumerate(pdf.pages, 1):
            page_text = page.extract_text() or ""
            marker = SECTION.search(page_text)
            if marker:
                current_section = marker.group(1).upper()
                markers.append([page_number, current_section])
            for table in page.find_tables():
                for row_number, raw in enumerate(table.extract() or [], 1):
                    row = [clean(cell) for cell in raw]
                    if len(row) < 7:
                        continue
                    folded = " | ".join(row).casefold()
                    if any(token in folded for token in ("ragione sociale", "codice fiscale", "data iscrizione", "data scadenza")):
                        continue
                    name = clean(row[0])
                    listing_raw = clean(row[4])
                    if not name or not re.search(r"\d{1,2}[./-]\d{1,2}[./-]\d{4}", listing_raw):
                        continue
                    expiry_raw = clean(row[5])
                    identifier_raw = clean(row[3])
                    note_raw = clean(row[6])
                    identifiers = [value.upper() for value in STRICT_ID.findall(identifier_raw)]
                    status = (
                        "renewal_update_in_progress"
                        if "rinnovo" in note_raw.casefold() or "aggiornamento" in note_raw.casefold()
                        else "listed"
                    )
                    identity = ("id", *sorted(identifiers)) if identifiers else ("name", name.casefold())
                    group_key = (
                        *identity,
                        date_key(listing_raw),
                        date_key(expiry_raw),
                        status,
                        note_raw.casefold(),
                    )
                    source_rows.append(
                        {
                            "page": page_number,
                            "row": row_number,
                            "section": current_section,
                            "name": name,
                            "office": clean(row[1]),
                            "identifier_raw": identifier_raw,
                            "identifiers": identifiers,
                            "listing_raw": listing_raw,
                            "expiry_raw": expiry_raw,
                            "note_raw": note_raw,
                            "status": status,
                            "group_key": group_key,
                        }
                    )

    grouped: dict[tuple[object, ...], list[dict[str, object]]] = defaultdict(list)
    for row in source_rows:
        grouped[tuple(row["group_key"])].append(row)
    anomalies = [
        row
        for row in source_rows
        if not row["identifiers"] or date_key(str(row["expiry_raw"])).startswith("RAW:")
    ]
    multi_groups = [
        {
            "name": rows[0]["name"],
            "n": len(rows),
            "sections": list(dict.fromkeys(row["section"] for row in rows)),
            "listing_raw": rows[0]["listing_raw"],
            "expiry_raw": rows[0]["expiry_raw"],
            "status": rows[0]["status"],
        }
        for rows in grouped.values()
        if len(rows) > 1
    ]

    print(
        "AUDIT_SUMMARY",
        json.dumps(
            {
                "listed_fetch": listed_fetch,
                "listed_pages": listed_pages,
                "listed_section_markers": markers,
                "listed_sector_rows": len(source_rows),
                "listed_section_counts": dict(Counter(row["section"] for row in source_rows)),
                "listed_sector_status_counts": dict(Counter(row["status"] for row in source_rows)),
                "listed_public_records": len(grouped),
                "listed_public_status_counts": dict(Counter(rows[0]["status"] for rows in grouped.values())),
                "listed_multi_section_group_count": len(multi_groups),
                "listed_anomaly_count": len(anomalies),
                "applicant_fetch": applicant_fetch,
            },
            ensure_ascii=False,
        ),
    )
    print("LISTED_ANOMALIES", json.dumps(anomalies, ensure_ascii=False))
    print("LISTED_MULTI_GROUPS", json.dumps(multi_groups, ensure_ascii=False))

    layout_path = out / "brindisi-applicants-layout.txt"
    subprocess.run(["pdftotext", "-layout", str(applicant_path), str(layout_path)], check=True)
    print("APPLICANT_LAYOUT_BEGIN")
    print(layout_path.read_text(encoding="utf-8", errors="replace"))
    print("APPLICANT_LAYOUT_END")


if __name__ == "__main__":
    main()
