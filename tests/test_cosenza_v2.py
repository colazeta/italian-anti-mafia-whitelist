import json

from white_list_archive.parsers.cosenza_combined_v2 import (
    _is_row_start,
    _parse_identifiers,
    _parse_outcome,
)


def _word(x, text):
    return {"xc": x, "text": text}


def _line(name, legal, identifier, application="", outcome=""):
    words = [
        _word(80, name),
        _word(200, legal),
        _word(315, identifier),
        _word(365, "Noli"),
    ]
    if application:
        words.append(_word(485, application))
    if outcome:
        words.append(_word(535, outcome))
    return {"words": words}


def test_v2_row_detection_does_not_require_valid_11_digit_identifier():
    # Real failure class from v1: GENISE FORTUNATO is published with a 12-digit
    # numeric source value but has a clear row-level application date.
    assert _is_row_start(
        _line("GENISE FORTUNATO", "FIRMO", "019706230787", "20/10/2020", "IN ISTRUTTORIA")
    )

    # Real failure class from v1: some rows have only an alphanumeric CF split
    # across lines. Row identity must come from table structure, not identifier shape.
    assert _is_row_start(
        _line("NICASTRO GIUSEPPE", "SAN GIOVANNI IN FIORE", "NCSGPP63A18H9", "16/11/2021", "IN ISTRUTTORIA")
    )


def test_v2_does_not_split_alias_line_without_row_context():
    # "ABBREVIATAMENTE SMIC S.R.L." is a continuation/alias line in the source,
    # not a second table record. V1 incorrectly split it because it saw 11 digits.
    assert not _is_row_start(
        _line("ABBREVIATAMENTE SMIC S.R.L.", "SORBO SN", "01122910803")
    )


def test_v2_identifier_parser_preserves_malformed_and_multivalue_source_data():
    raw, values = _parse_identifiers(["019706230787", "GNSFTN75S22Z1", "12O"])
    assert raw.startswith("019706230787")
    assert values[0]["shape"] == "numeric_12_digits"
    assert values[0]["scheme_assertion"] == "UNKNOWN"
    assert values[1]["raw_value"] == "GNSFTN75S22Z112O"
    assert values[1]["scheme_assertion"] == "IT_CF_CANDIDATE"

    _, cf_hint_values = _parse_identifiers(["02311680785", "C.F.", "00940370802"])
    assert len(cf_hint_values) == 2
    assert cf_hint_values[1]["source_hint"] == "CF"
    assert cf_hint_values[1]["candidate_schemes"] == ["IT_CF"]


def test_v2_outcome_extracts_observed_listing_and_expiry_without_canonicalising():
    listed = _parse_outcome("INSERITO NELLE LISTE IN DATA 13/02/2026")
    assert listed["status"] == "listed"
    assert listed["observed_listing_date"] == "13/02/2026"
    assert listed["observed_expiry_date"] is None

    renewal = _parse_outcome(
        "RICHIESTA DI RINNOVO – Scadenza 27/09/2017 AGGIORNAMENTO IN CORSO"
    )
    assert renewal["status"] == "renewal_update_in_progress"
    assert renewal["observed_expiry_date"] == "27/09/2017"
    assert renewal["renewal_requested"] is True
    assert renewal["update_in_progress"] is True
