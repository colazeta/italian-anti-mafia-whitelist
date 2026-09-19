from white_list_archive.parsers.imperia_sources import (
    _applicant_status,
    _listed_status,
    _outcome_listing_date,
    _source_date,
    _source_identifiers,
)


def test_imperia_dates_are_conservative():
    assert _source_date("9 settembre 2014") == "2014-09-09"
    assert _source_date("03/10/2019") == "2019-10-03"
    assert _source_date("2-4-2024") == "2024-04-02"
    assert _source_date("3/11/23") == "2023-11-03"
    assert _source_date("25/0720522") == ""
    assert _source_date("10/1\\0/2024") == ""
    assert _source_date("07/07/206") == ""


def test_imperia_outcome_enrolment_dates_require_positive_text():
    assert _outcome_listing_date("Iscritta dal 18/5/2015") == "2015-05-18"
    assert _outcome_listing_date("Iscritta dall’8/2/2016") == "2016-02-08"
    assert _outcome_listing_date("Iscritta dall/8/10/2019") == "2019-10-08"
    assert _outcome_listing_date("Iscritta dal 3 maggio 2016") == "2016-05-03"
    assert _outcome_listing_date("Iscritta del 28/08/2024") == "2024-08-28"
    assert _outcome_listing_date("In corso") == ""


def test_imperia_identifier_extraction_preserves_only_strict_shapes():
    assert _source_identifiers("RVRNRC44M17D969E - 02253400101") == ["02253400101", "RVRNRC44M17D969E"]
    assert _source_identifiers("01540730080 - CHAVTR73D13A145N") == ["01540730080", "CHAVTR73D13A145N"]
    assert _source_identifiers("0165000088") == []
    assert _source_identifiers("025687110990") == []


def test_imperia_statuses_require_positive_source_evidence():
    assert _listed_status("") == "listed"
    assert _listed_status("IN CORSO - PER RINNOVO") == "renewal_update_in_progress"
    assert _listed_status("IN CORSO - PER MODIFICHE SOCIETARIE") == "renewal_update_in_progress"
    assert _applicant_status("ALFA SRL", "Iscritta dal 18/5/2015") == "listed"
    assert _applicant_status("ALFA SRL", "In corso") == "pending"
    assert _applicant_status("ALFA SRL", "") == "other_or_unknown"
    assert _applicant_status("SINERGIE SRL", "06/02/2025") == "other_or_unknown"
    assert _applicant_status("CANCELLATA ALFA SRL", "") == "cancellation_related"
