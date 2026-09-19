from datetime import datetime

import pytest

from white_list_archive.parsers.grosseto_openxml import (
    _EXPECTED_APPLICANT_RECORDS,
    _EXPECTED_APPLICANT_SECTOR_COUNTS,
    _EXPECTED_LISTED_RECORDS,
    _EXPECTED_LISTED_SECTOR_COUNTS,
    _listed_status,
    _source_date,
    _structured_identifier,
)


def test_grosseto_source_date_is_conservative():
    assert _source_date(datetime(2026, 9, 11)) == "2026-09-11"
    assert _source_date("11/09/2026") == "2026-09-11"
    assert _source_date(46092) == ""
    assert _source_date("") == ""


def test_grosseto_status_mapping_requires_reviewed_source_wording():
    assert _listed_status("iscrizione") == "listed"
    assert _listed_status("ISCRIZIONE") == "listed"
    assert _listed_status("iscizione") == "listed"
    assert _listed_status("Presentata istanza di rinnovo in data 08/09/2026") == "renewal_update_in_progress"
    with pytest.raises(RuntimeError):
        _listed_status("esito nuovo non revisionato")


def test_grosseto_identifier_validation_does_not_repair_source_tokens():
    assert _structured_identifier("01639910536")
    assert _structured_identifier("mntfba74m12f032f")
    assert not _structured_identifier("101600010530")
    assert not _structured_identifier("")


def test_grosseto_reviewed_denominators_are_frozen():
    assert _EXPECTED_LISTED_RECORDS == 406
    assert _EXPECTED_APPLICANT_RECORDS == 12
    assert sum(_EXPECTED_LISTED_SECTOR_COUNTS.values()) == 762
    assert sum(_EXPECTED_APPLICANT_SECTOR_COUNTS.values()) == 35
    assert 8 not in _EXPECTED_APPLICANT_SECTOR_COUNTS
