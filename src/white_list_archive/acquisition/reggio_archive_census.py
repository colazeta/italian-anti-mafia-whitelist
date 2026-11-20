"""Read-only structural census of the archived Reggio Calabria November originals."""
from collections import Counter
from hashlib import sha256
from io import BytesIO
import json
import re
from datetime import datetime

import pdfplumber

from white_list_archive.storage.evidence import EvidenceStore, StoreConfig, client_for

PINS = (
    ("listed", "d185e63dcd0a603aec194ddc32593960cb72f183fdba120abd0d2dc6f9666b13", 281479),
    ("applicant", "fa15cb7cbd4c17d94a05c374c2e69b073648122197aef866b7ed6ea95a969764", 392393),
)


def content_profile(cells, population, counters):
    """Summarise the source fields without emitting any row values."""
    fields = (
        ("name", "office", "secondary_office", "identifier", "listing_date",
         "expiry_date", "activities", "outcome")
        if population == "listed"
        else ("name", "office", "secondary_office", "identifier", "activities",
              "application_date", "outcome")
    )
    if len(cells) != len(fields) + 1:
        raise ValueError("Unexpected data row width")
    for field, value in zip(fields, cells[1:], strict=True):
        if not value:
            counters[f"{field}_blank"] += 1
        elif field.endswith("_date"):
            counters[f"{field}_{date_shape(value)}"] += 1
        elif field == "identifier":
            shape = "standard_shape" if re.fullmatch(r"(?:[0-9]{11}|[A-Za-z0-9]{16})", value) else "other_shape"
            counters[f"identifier_{shape}"] += 1
        elif field == "outcome":
            outcome = " ".join(value.casefold().split())
            if population == "applicant":
                label = "instruction" if outcome in {"istruttoria", "istrutoria", "istruttorria"} else "other"
            else:
                label = "renewal_or_update" if (
                    "aggiornamento in corso" in outcome or
                    ("istruttoria" in outcome and any(x in outcome for x in ("rinnovo", "aggiornamento", "permanenza")))
                ) else "other"
            counters[f"outcome_{label}"] += 1


def date_shape(value):
    value = re.sub(r"\s*-\s*", "-", value.casefold())
    for italian, english in (("gen", "jan"), ("mag", "may"), ("giu", "jun"),
                             ("lug", "jul"), ("ago", "aug"), ("set", "sep"),
                             ("ott", "oct"), ("dic", "dec")):
        value = value.replace(f"-{italian}-", f"-{english}-")
    for fmt in ("%d-%b-%y", "%d-%b-%Y", "%d/%m/%Y", "%d.%m.%Y"):
        try:
            datetime.strptime(value, fmt)
        except ValueError:
            continue
        return "calendar_value"
    return "needs_review"


def census(raw, population):
    tables_per_page = []
    numbered_rows_per_page = []
    widths = Counter()
    numbers = Counter()
    number_only = 0
    profile = Counter()
    number_only_ordinals = []
    header_like_rows = 0
    other_nonblank_rows = 0
    with pdfplumber.open(BytesIO(raw)) as pdf:
        for page in pdf.pages:
            tables = page.find_tables()
            tables_per_page.append(len(tables))
            start = numbers.total()
            for table in tables:
                for row in table.extract():
                    cells = [str(cell or "").strip() for cell in row]
                    if not any(cells):
                        continue
                    if cells[0].isascii() and cells[0].isdecimal():
                        numbers[int(cells[0])] += 1
                        widths[len(cells)] += 1
                        if any(cells[1:]):
                            content_profile(cells, population, profile)
                        else:
                            number_only += 1
                            number_only_ordinals.append(int(cells[0]))
                    else:
                        other_nonblank_rows += 1
                        label = ' '.join(cells).casefold()
                        header_like_rows += 'ragione sociale' in label and ('codice fiscale' in label or 'partita iva' in label)
            numbered_rows_per_page.append(numbers.total() - start)
            page.close()
    return {
        "pages": len(tables_per_page),
        "tables_per_page": tables_per_page,
        "numbered_rows_per_page": numbered_rows_per_page,
        "numbered_rows": numbers.total(),
        "duplicate_numbers": numbers.total() - len(numbers),
        "min_number": min(numbers, default=None),
        "max_number": max(numbers, default=None),
        "number_only_rows": number_only,
        "number_only_ordinals": number_only_ordinals,
        "header_like_rows": header_like_rows,
        "content_profile": profile,
        "numbered_row_widths": widths,
        "other_nonblank_table_rows": other_nonblank_rows,
    }


def main():
    config = StoreConfig.from_env()
    store = EvidenceStore(client_for(config), config)
    results = []
    for population, digest, size in PINS:
        result = {"population": population, "sha256": digest, "bytes": size}
        try:
            raw = store.read_digest_verified(digest)
            if len(raw) != size or sha256(raw).hexdigest() != digest:
                raise ValueError("Archived original differs from pin")
            result["verified_bytes"] = True
            result["structure"] = census(raw, population)
        except Exception as exc:
            result["error_type"] = type(exc).__name__
        results.append(result)
    print(json.dumps({"source_reference": "2026-11-16", "review_only": True, "results": results},
                     sort_keys=True))
    return int(any("structure" not in result for result in results))


if __name__ == "__main__":
    raise SystemExit(main())
