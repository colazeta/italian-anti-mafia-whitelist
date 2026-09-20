from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LISTED_PAGE = "https://prefettura.interno.gov.it/it/prefetture/pescara/evidenza/white-list"
APPLICANT_PAGE = "https://prefettura.interno.gov.it/it/prefetture/pescara/elenco-imprese-richiedenti-liscrizione-nelle-white-list"


def patch_csv(path: Path, key: str, new_rows: list[dict[str, str]], sort_key: str) -> None:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    if not fieldnames:
        raise RuntimeError(f"Cannot infer CSV schema from {path}")
    for row in new_rows:
        if set(row) != set(fieldnames):
            raise RuntimeError(
                f"CSV schema mismatch for {path}: extras={sorted(set(row)-set(fieldnames))}, "
                f"missing={sorted(set(fieldnames)-set(row))}"
            )
    wanted = {row[key]: row for row in new_rows}
    existing = {row[key]: row for row in rows if row.get(key) in wanted}
    if existing:
        if existing != wanted:
            raise RuntimeError(f"Pre-existing {path.name} Pescara rows differ from candidate")
        return
    rows.extend(new_rows)
    rows.sort(key=lambda row: row[sort_key])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


patch_csv(
    ROOT / "data/source_registry/verified_primary_pages.csv",
    "authority_key",
    [{
        "authority_key": "pescara",
        "landing_url": LISTED_PAGE,
        "verification_date": "2026-09-21",
        "verification_status": "verified",
    }],
    "authority_key",
)

patch_csv(
    ROOT / "data/source_registry/source_series_inventory.csv",
    "source_series_key",
    [
        {
            "source_series_key": "pescara-listed",
            "authority_key": "pescara",
            "regime_code": "WL-REGIME-L190-2012",
            "population_scope": "listed",
            "sector_scope": "all",
            "publication_model": "periodic_attachment",
            "series_url": LISTED_PAGE,
            "resource_resolution_status": "landing_page_resolved",
            "verified_date": "2026-09-21",
            "notes": "Current official Pescara listed landing directly verified 21 September 2026 and positively exposes White list 16/09/2026. Two independent captures of the legacy Word attachment are byte-identical at SHA-256 6a8aa832db7d0f55c17d9ed1f8179d9ed46a7c927b5b88d85319f79a1da92239. Exact full-row grouping yields 607 observations from 1,060 company-by-section rows; raw malformed identifiers/dates and the single nonstandard status token are not repaired by inference.",
        },
        {
            "source_series_key": "pescara-applicants",
            "authority_key": "pescara",
            "regime_code": "WL-REGIME-L190-2012",
            "population_scope": "applicant",
            "sector_scope": "all",
            "publication_model": "periodic_attachment",
            "series_url": APPLICANT_PAGE,
            "resource_resolution_status": "direct_series_page_resolved",
            "verified_date": "2026-09-21",
            "notes": "Current official Pescara applicant page directly verified 21 September 2026 and positively exposes Elenco richiedenti White List - 04.09.2026. Two independent captures are byte-identical at SHA-256 2a0f74ab6548ad2418f539aba7fc2eaf0d23998b709b0bc247e512d7b46a578c. Thirty-six physical rows yield 35 applicant observations after one exact reviewed continuation; no applicant status is inferred from absence.",
        },
    ],
    "source_series_key",
)
