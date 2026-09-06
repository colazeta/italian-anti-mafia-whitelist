from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from white_list_archive.acquisition.cosenza_snapshot import parse_cosenza_snapshot_html

ROOT = Path(__file__).resolve().parents[1]


def _edition_rows() -> list[dict[str, str]]:
    path = ROOT / "data/source_registry/cosenza_historical_editions.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_cosenza_historical_edition_inventory_is_explicit_and_chronological():
    rows = _edition_rows()
    assert len(rows) == 11
    dates = [date.fromisoformat(row["reference_date"]) for row in rows]
    assert dates == sorted(dates)
    assert len(set(dates)) == len(dates)
    assert {row["authority_key"] for row in rows} == {"cosenza"}
    assert {row["source_series_key"] for row in rows} == {"cosenza-combined"}
    assert {row["source_origin"] for row in rows} >= {"official_current", "official_historical"}
    assert all(row["edition_identity_status"].startswith("explicit") for row in rows)


def test_cosenza_2026_inventory_contains_verified_monthly_points():
    observed = {row["reference_date"] for row in _edition_rows()}
    required = {
        "2026-01-19",
        "2026-02-16",
        "2026-03-16",
        "2026-04-20",
        "2026-05-25",
        "2026-06-28",
        "2026-08-03",
    }
    assert required <= observed


def test_cosenza_snapshot_parser_extracts_combined_and_ten_sector_resources():
    fixture = (ROOT / "tests/fixtures/cosenza_snapshot_sample.html").read_text(encoding="utf-8")
    page_url = "https://prefettura.interno.gov.it/it/prefetture/cosenza/white-list-elenchi-aggiornati-03-agosto-2026"
    edition = parse_cosenza_snapshot_html(fixture, page_url)

    assert edition.reference_date == date(2026, 8, 3)
    assert len(edition.attachments) == 11
    combined = [item for item in edition.attachments if item.resource_kind == "combined_list"]
    sectors = [item for item in edition.attachments if item.resource_kind == "sector_list"]
    assert len(combined) == 1
    assert len(sectors) == 10
    assert {item.section_notation for item in sectors} == {"I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"}
    assert all(item.url.startswith("https://prefettura.interno.gov.it/files/") for item in edition.attachments)
    assert all("modulistica" not in item.url for item in edition.attachments)
