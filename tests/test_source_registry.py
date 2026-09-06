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
    assert len(pages) == 24
    assert {row["authority_key"] for row in pages} <= authorities
    assert all(row["verification_status"] == "verified" for row in pages)
    assert all(row["landing_url"].startswith("https://") for row in pages)


def test_pilot_profiles_are_diverse_and_reference_verified_pages():
    verified = {row["authority_key"] for row in _read_csv("verified_primary_pages.csv")}
    profiles = _read_csv("pilot_source_profiles.csv")
    assert len(profiles) == 10
    assert {row["authority_key"] for row in profiles} <= verified
    assert len({row["publication_model"] for row in profiles}) >= 6


def test_national_index_parser_extracts_real_links_from_table_fixture():
    fixture = (ROOT / "tests/fixtures/national_index_sample.html").read_text(encoding="utf-8")
    page = "https://prefettura.interno.gov.it/it/white-list-nazionale?page=0"
    entries = parse_national_index_html(fixture, page)

    assert [entry.jurisdiction_name for entry in entries] == ["Aosta", "Milano", "Trento"]
    assert entries[0].white_list_url.startswith("https://www.regione.vda.it/")
    assert entries[1].white_list_url == "https://prefettura.interno.gov.it/it/prefetture/milano/evidenza/white-list"
    assert entries[2].title == "WHITE LIST"
