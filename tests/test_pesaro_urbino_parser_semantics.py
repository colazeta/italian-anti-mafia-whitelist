from pathlib import Path

import pytest

from white_list_archive.parsers import pesaro_urbino_combined as parser


def _cfg() -> dict[str, str]:
    return {
        "source_key": "pesaro-urbino-combined",
        "authority_key": "pesaro-e-urbino",
        "authority_name": "Prefettura di Pesaro e Urbino",
        "register_key": "pesaro-urbino-ordinary",
        "register_name": "White List ordinaria",
        "population_scope": "listed_and_applicant",
        "reference_date": "2026-08-31",
        "source_page_url": "https://example.invalid/page",
        "resource_url": "https://example.invalid/resource.pdf",
        "sha256": "0" * 64,
    }


def _row(*, identifier="02750360410", listing="10/12/2025", expiry="09/12/2026", sections="2, 5", update=""):
    return ["Impresa Alfa", "PESARO (PU) VIA ROMA 1", identifier, listing, expiry, None, None, sections, update]


def test_explicit_date_pair_is_listed():
    record = parser._record_from_cells(_row(), _cfg(), 1)
    assert record["source_status"] == "listed"
    assert record["observed_listing_date"] == "2025-12-10"
    assert record["observed_expiry_date"] == "2026-12-09"
    assert record["requested_activities"] == ["Sezione 2", "Sezione 5"]


def test_update_marker_is_preserved_without_inventing_applicant_status():
    record = parser._record_from_cells(_row(listing="", expiry="", update="X"), _cfg(), 2)
    assert record["source_status"] == "renewal_update_in_progress"
    assert record["observed_listing_date"] == ""
    assert record["observed_expiry_date"] == ""
    assert record["outcome_raw"] == "X"
    assert record["source_fields"]["in_aggiornamento"] == "X"


def test_dated_update_row_remains_update_in_progress():
    record = parser._record_from_cells(_row(update="X"), _cfg(), 3)
    assert record["source_status"] == "renewal_update_in_progress"
    assert record["observed_listing_date"] == "2025-12-10"


def test_dot_date_typography_normalises_without_changing_digits():
    record = parser._record_from_cells(_row(listing="25.11.2025", expiry="25.11.2026"), _cfg(), 4)
    assert record["observed_listing_date"] == "2025-11-25"
    assert record["observed_expiry_date"] == "2026-11-25"
    assert record["source_fields"]["listing_date_raw_variants"] == ["25.11.2025"]


def test_noncanonical_identifier_is_preserved_raw_not_repaired():
    raw = "BRBLCN65L16D488V/0117606"
    record = parser._record_from_cells(_row(identifier=raw), _cfg(), 5)
    assert record["identifier_field_raw"] == raw
    assert record["identifiers"] == []


def test_missing_sections_do_not_create_an_activity():
    record = parser._record_from_cells(_row(sections=""), _cfg(), 6)
    assert record["requested_activities"] == []


def test_row_without_date_or_update_marker_fails_closed():
    with pytest.raises(RuntimeError, match="neither an explicit listing date pair nor an update-in-progress marker"):
        parser._record_from_cells(_row(listing="", expiry="", update=""), _cfg(), 7)


def test_incomplete_date_pair_fails_closed():
    with pytest.raises(RuntimeError, match="structurally incomplete"):
        parser._record_from_cells(_row(expiry=""), _cfg(), 8)
