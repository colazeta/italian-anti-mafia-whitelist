from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

from white_list_archive.acquisition.national_index import parse_national_index_html

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "data/source_registry"


def _read_csv(name: str) -> list[dict[str, str]]:
    with (REGISTRY / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_territorial_authority_seed_is_complete_and_unique():
    rows = _read_csv("territorial_authorities.csv")
    assert len(rows) == 106
    keys = [row["authority_key"] for row in rows]
    assert len(set(keys)) == 106
    assert all(key == key.strip() and " " not in key for key in keys)

    types = Counter(row["office_type"] for row in rows)
    assert types == {
        "prefettura_utg": 103,
        "government_commissariat": 2,
        "valle_d_aosta_special": 1,
    }
    assert len({row["region"] for row in rows}) == 20


def test_verified_primary_pages_reference_seeded_authorities():
    authorities = {row["authority_key"] for row in _read_csv("territorial_authorities.csv")}
    pages = _read_csv("verified_primary_pages.csv")
    assert len(pages) == 39
    assert len({row["authority_key"] for row in pages}) == len(pages)
    assert {row["authority_key"] for row in pages} <= authorities
    assert all(row["verification_status"] == "verified" for row in pages)
    assert all(row["landing_url"].startswith("https://") for row in pages)


def test_national_index_authority_aliases_reference_seeded_and_verified_catalog_keys():
    authorities = {row["authority_key"] for row in _read_csv("territorial_authorities.csv")}
    verified = {row["authority_key"] for row in _read_csv("verified_primary_pages.csv")}
    aliases = _read_csv("national_index_authority_aliases.csv")

    assert len({row["national_index_key"] for row in aliases}) == len(aliases)
    assert all(row["national_index_key"] and row["catalog_authority_key"] and row["reason"] for row in aliases)
    assert {row["catalog_authority_key"] for row in aliases} <= authorities
    assert {row["catalog_authority_key"] for row in aliases} <= verified
    assert any(
        row["national_index_key"] == "pesaro-urbino" and row["catalog_authority_key"] == "pesaro-e-urbino"
        for row in aliases
    )


def test_pilot_profiles_are_diverse_and_reference_verified_pages():
    verified = {row["authority_key"] for row in _read_csv("verified_primary_pages.csv")}
    profiles = _read_csv("pilot_source_profiles.csv")
    assert len(profiles) == 10
    assert {row["authority_key"] for row in profiles} <= verified
    assert len({row["publication_model"] for row in profiles}) >= 6


def test_source_series_inventory_is_evidence_backed_and_normalised():
    authorities = {row["authority_key"] for row in _read_csv("territorial_authorities.csv")}
    verified = {row["authority_key"] for row in _read_csv("verified_primary_pages.csv")}
    series = _read_csv("source_series_inventory.csv")

    assert len(series) >= 28
    keys = [row["source_series_key"] for row in series]
    assert len(keys) == len(set(keys))
    assert all(key == key.strip() and " " not in key for key in keys)
    assert {row["authority_key"] for row in series} <= authorities
    assert {row["authority_key"] for row in series} <= verified
    assert all(row["series_url"].startswith("https://") for row in series)
    assert {row["regime_code"] for row in series} <= {
        "WL-REGIME-L190-2012",
        "WL-REGIME-ER-SISMA-2012",
    }
    assert "bologna-post-sisma-listed" in keys
    assert "ascoli-piceno-listed-by-sector" in keys
    assert "cosenza-combined" in keys


def test_national_index_parser_extracts_real_links_from_table_fixture():
    fixture = (ROOT / "tests/fixtures/national_index_sample.html").read_text(encoding="utf-8")
    page = "https://prefettura.interno.gov.it/it/white-list-nazionale?page=0"
    entries = parse_national_index_html(fixture, page)
    assert [entry.jurisdiction_name for entry in entries] == ["Aosta", "Milano", "Trento"]
    assert entries[0].white_list_url.startswith("https://www.regione.vda.it/")
    assert entries[1].white_list_url == "https://prefettura.interno.gov.it/it/prefetture/milano/evidenza/white-list"
    assert entries[2].title == "WHITE LIST"
