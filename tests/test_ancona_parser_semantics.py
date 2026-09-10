import pytest

from white_list_archive.parsers.ancona_combined import (
    PARSER_NAME,
    PARSER_VERSION,
    _identifier_values,
    _record_from_cells,
    _repair_reviewed_extraction,
    _sections,
)
from white_list_archive.publishing.public_contract import public_record

CFG = {
    "source_key": "ancona-combined",
    "authority_key": "ancona",
    "authority_name": "Prefettura di Ancona",
    "register_key": "ancona-ordinary",
    "register_name": "White List ordinaria",
    "population_scope": "listed_and_applicant",
    "reference_date": "2026-09-07",
    "source_page_url": "https://example.test/ancona",
    "resource_url": "https://example.test/ancona.pdf",
    "sha256": "0" * 64,
}


def _row(*, listing="01/09/2026", expiry="31/08/2027", update="", application="", sections="I - III"):
    return ["ALPHA SRL", "Via Roma 1 - ANCONA", "", "01234567890", listing, expiry, sections, update, application]


def _contract_record(row):
    record = _record_from_cells(row, CFG, 1)
    record["parser_name"] = PARSER_NAME
    record["parser_version"] = PARSER_VERSION
    assert public_record(record) == record
    return record


def test_direct_listing_pair_is_positive_listing_evidence_even_with_application_date():
    record = _contract_record(_row(application="10/06/2026"))
    assert record["source_status"] == "listed"
    assert record["observed_listing_date"] == "2026-09-01"
    assert record["application_date"] == "2026-06-10"


def test_application_only_row_in_official_combined_population_is_pending():
    record = _contract_record(_row(listing="", expiry="", application="10/06/2026"))
    assert record["source_status"] == "pending"
    assert record["primary_date_label"] == "Data presentazione istanza"


def test_exact_renewal_marker_uses_existing_renewal_status():
    record = _contract_record(_row(update="Richiesto rinnovo"))
    assert record["source_status"] == "renewal_update_in_progress"
    assert record["source_fields"]["in_aggiornamento"] == "Richiesto rinnovo"


def test_nonsemantic_punctuation_update_is_preserved_but_not_promoted():
    record = _contract_record(_row(update=",,,,,,,,,"))
    assert record["source_status"] == "other_or_unknown"
    assert record["outcome_raw"] == ",,,,,,,,,"


def test_no_status_signal_remains_unknown():
    record = _contract_record(_row(listing="", expiry="", application="", sections=""))
    assert record["source_status"] == "other_or_unknown"


def test_incomplete_or_invalid_source_date_pair_fails_closed():
    with pytest.raises(RuntimeError, match="structurally incomplete"):
        _record_from_cells(_row(expiry=""), CFG, 1)
    with pytest.raises(RuntimeError, match="invalid listing source date"):
        _record_from_cells(_row(listing="31/02/2026"), CFG, 1)


def test_sections_accept_only_source_roman_codes():
    assert _sections("I - III - V - X") == ["Sezione I", "Sezione III", "Sezione V", "Sezione X"]
    with pytest.raises(RuntimeError, match="unsupported section-cell"):
        _sections("I - custom")


def test_spaced_second_identifier_is_typographically_normalised_without_padding():
    assert _identifier_values("92025390425/02791 470426") == ["92025390425", "02791470426"]
    assert _identifier_values("012771502254") == []


def test_reviewed_page_21_geometry_repair_redistributes_only_audited_identity_cells():
    rows = [[""] * 9 for _ in range(26)]
    rows[7] = ["SIRIO COSTRUZIONI SRL", "", "", "00715570420 03033810429 02566930422", "28/03/2025", "27/03/2026", "I", "Richiesto rinnovo", ""]
    rows[8] = ["SM SRL", "", "", "", "", "", "VI", "", "20/05/2026"]
    rows[9] = ["", "", "", "", "27/08/2026", "25/08/2027", "II", "", ""]
    rows[25] = ["", "Via Veneto 8/10/12 - FABRIANO", "", "02557530421", "", "", "IX", "", "11/08/2025"]
    repaired = _repair_reviewed_extraction(21, rows)
    assert repaired[7][1:4] == ["Via Molini I, 18 - SIROLO", "", "00715570420"]
    assert repaired[8][1:4] == ["via Manzoni n. 65 -OSIMO", "", "03033810429"]
    assert repaired[9][:4] == ["SMART BUILDING DESIGN SRL", "Via Giancarlo Mascino n.3/F - ANCONA", "", "02566930422"]
    assert repaired[25][0] == "TAVERNA DA IVO SRL"
