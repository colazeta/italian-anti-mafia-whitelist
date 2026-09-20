import pytest

from white_list_archive.parsers.ravenna_combined import (
    _identity,
    _record_from_cells,
    _repair_reviewed_extraction,
    _sections,
    _status,
)

CFG = {
    "source_key": "ravenna-combined",
    "authority_key": "ravenna",
    "authority_name": "Prefettura di Ravenna",
    "register_key": "ravenna-ordinary",
    "register_name": "White List ordinaria",
    "population_scope": "listed_and_applicant",
    "reference_date": "2026-09-17",
    "source_page_url": "https://example.test/ravenna",
    "resource_url": "https://example.test/ravenna.pdf",
    "sha256": "0" * 64,
}


def _row(*, application="10/06/2026", listing="01/09/2026", note="", company="ALPHA SRL 01234567890", sections=None):
    sections = sections or ["X", "", "", "", "", "", "", "", "", ""]
    return ["1", company, "VIA ROMA 1, RAVENNA (RA)", application, listing, note, *sections]


def test_listed_row_uses_direct_listing_date_even_with_application_date():
    record = _record_from_cells(_row(), CFG, 1)
    assert record["source_status"] == "listed"
    assert record["application_date"] == "2026-06-10"
    assert record["observed_listing_date"] == "2026-09-01"
    assert record["identifiers"] == ["01234567890"]
    assert record["name"] == "ALPHA SRL"


def test_application_only_row_is_pending_positive_evidence():
    record = _record_from_cells(_row(listing=""), CFG, 1)
    assert record["source_status"] == "pending"
    assert record["primary_date_label"] == "Data presentazione istanza"


@pytest.mark.parametrize("note", [
    "Richiesto rinnovo - Aggiornamento in corso",
    "Richiesta rinnovo - aggiornamento in corso",
])
def test_both_reviewed_renewal_note_spellings_map_to_update_status(note):
    assert _status(application_raw="01/01/2025", listing_raw="01/01/2026", note_raw=note) == "renewal_update_in_progress"


def test_special_judicial_control_note_stays_unknown():
    note = "Iscrizione temporanea per effetto del controllo giudiziario, conclusosi, ex art. 34/bis del D.Lgs 159/2011 Aggiornamento in corso"
    record = _record_from_cells(_row(note=note), CFG, 1)
    assert record["source_status"] == "other_or_unknown"
    assert record["outcome_raw"] == note


def test_reviewed_malformed_application_date_is_preserved_not_repaired():
    record = _record_from_cells(_row(application="23/06/026", listing=""), CFG, 1)
    assert record["source_status"] == "pending"
    assert record["application_date"] == ""
    assert record["source_fields"]["application_date_raw_variants"] == ["23/06/026"]
    assert record["source_fields"]["malformed_date_pairs"] == ["application:23/06/026"]


def test_sections_accept_x_and_x_star_only_and_preserve_marker():
    activities, markers = _sections(["X", "", "X*", "", "", "", "", "", "", "X"])
    assert activities == ["Sezione I", "Sezione III", "Sezione X"]
    assert markers == ["I:X", "III:X*", "X:X"]
    with pytest.raises(RuntimeError, match="unsupported section marker"):
        _sections(["YES"] + [""] * 9)


def test_identity_extracts_only_structurally_valid_visible_tokens():
    name, raw, values = _identity("COSTA FRANCO CSTFNC71T30H199H 01227130398")
    assert name == "COSTA FRANCO"
    assert raw == "CSTFNC71T30H199H 01227130398"
    assert values == ["CSTFNC71T30H199H", "01227130398"]
    assert _identity("ASTRA SOC. CONS. A R.L. 014772900396") == ("ASTRA SOC. CONS. A R.L. 014772900396", "", [])


def test_reviewed_page_26_blank_name_repair_is_exactly_anchored():
    rows = [[str(index + 1174), "COMPANY", "ADDRESS", "01/01/2025", "01/01/2026", "", *([""] * 10)] for index in range(26)]
    rows[25] = ["1199", "", "MAASKADE 1199 BG ROTTERDAM", "10/12/2025", "", "", "", "", "", "", "", "", "", "X", "", ""]
    repaired = _repair_reviewed_extraction(26, rows)
    assert repaired[25][1] == "LOGLI MASSIMO DELLA MAASKADE RECQUIN BV"
    rows[25][2] = "CHANGED"
    with pytest.raises(RuntimeError, match="reviewed extraction repair no longer matches"):
        _repair_reviewed_extraction(26, rows)
