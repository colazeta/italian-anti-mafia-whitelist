"""Read-only structural census of the archived Reggio Calabria November originals."""
from collections import Counter
from hashlib import sha256
from io import BytesIO
import json

import pdfplumber

from white_list_archive.storage.evidence import EvidenceStore, StoreConfig, client_for

PINS = (
    ("listed", "d185e63dcd0a603aec194ddc32593960cb72f183fdba120abd0d2dc6f9666b13", 281479),
    ("applicant", "fa15cb7cbd4c17d94a05c374c2e69b073648122197aef866b7ed6ea95a969764", 392393),
)


def census(raw):
    tables_per_page = []
    numbered_rows_per_page = []
    widths = Counter()
    numbers = Counter()
    number_only = 0
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
                        number_only += not any(cells[1:])
                    else:
                        other_nonblank_rows += 1
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
            result["structure"] = census(raw)
        except Exception as exc:
            result["error_type"] = type(exc).__name__
        results.append(result)
    print(json.dumps({"source_reference": "2026-11-16", "review_only": True, "results": results},
                     sort_keys=True))
    return int(any("structure" not in result for result in results))


if __name__ == "__main__":
    raise SystemExit(main())
