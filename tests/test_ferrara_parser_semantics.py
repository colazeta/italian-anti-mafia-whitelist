from white_list_archive.parsers.ferrara_tables import (
    _normalise_date_or_blank,
    _status,
    _strict_identifiers,
)


def test_ferrara_dates_normalise_only_exact_valid_source_values():
    assert _normalise_date_or_blank("01/02/2026") == "2026-02-01"
    assert _normalise_date_or_blank("31/02/2026") == ""
    assert _normalise_date_or_blank("17.01/2024") == ""
    assert _normalise_date_or_blank("") == ""


def test_ferrara_status_mapping_is_conservative():
    assert _status("") == "listed"
    assert _status("RINNOVO IN CORSO") == "renewal_update_in_progress"
    assert _status("RINOVO IN CORSO") == "renewal_update_in_progress"
    assert _status("annotazione non classificata") == "other_or_unknown"


def test_ferrara_identifiers_accept_only_strict_tax_id_shapes():
    assert _strict_identifiers("01234567890") == ["01234567890"]
    assert _strict_identifiers("RSSMRA80A01H501U") == ["RSSMRA80A01H501U"]
    assert _strict_identifiers("P. IVA 01234567890") == ["01234567890"]
    assert _strict_identifiers("12345") == []
