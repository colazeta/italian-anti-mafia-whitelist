from white_list_archive.parsers.fermo_openxml import (
    _EXPECTED_APPLICANT_ORDINALS,
    _EXPECTED_LISTED_ORDINALS,
    _listed_status,
    _sections,
    _source_date,
)


def test_fermo_source_date_is_conservative():
    assert _source_date("22/05/2026") == "2026-05-22"
    assert _source_date("2026-05-22 00:00:00") == "2026-05-22"
    assert _source_date("28/11/204") == ""
    assert _source_date(46092) == ""


def test_fermo_activity_codes_are_explicit_only():
    assert _sections("Sez. I- III- V") == ["Sez. I", "Sez. III", "Sez. V"]
    assert _sections("Sez. IX-X") == ["Sez. IX", "Sez. X"]


def test_fermo_status_mapping_does_not_infer_beyond_source_note():
    assert _listed_status("") == "listed"
    assert _listed_status("IN FASE DI RINNOVO (l'iscrizione resta valida anche oltre la scadenza, fino all'esito definitivo)") == "renewal_update_in_progress"


def test_fermo_reviewed_source_ordinal_gaps_are_frozen():
    assert len(_EXPECTED_LISTED_ORDINALS) == 174
    assert 105 not in _EXPECTED_LISTED_ORDINALS
    assert 121 not in _EXPECTED_LISTED_ORDINALS
    assert len(_EXPECTED_APPLICANT_ORDINALS) == 75
    assert 38 not in _EXPECTED_APPLICANT_ORDINALS
