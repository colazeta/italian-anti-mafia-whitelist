import pytest

from white_list_archive.parsers.macerata_tables import (
    _EXPECTED_APPLICANT_BAD_DATES,
    _EXPECTED_APPLICANT_MALFORMED_IDENTIFIERS,
    _EXPECTED_LISTED_MALFORMED_IDENTIFIERS,
    _EXPECTED_NONSTANDARD_EXPIRY,
    _applicant_status,
    _listed_status,
    _valid_identifier,
)


def test_macerata_listed_statuses_require_positive_source_evidence():
    assert _listed_status("") == "listed"
    assert _listed_status("in corso rinnovo") == "renewal_update_in_progress"
    assert _listed_status("In corso rinnovo") == "renewal_update_in_progress"
    assert _listed_status("in corso rinnnovo") == "renewal_update_in_progress"
    assert _listed_status("in corsi rinnovo") == "renewal_update_in_progress"
    assert _listed_status("i") == "other_or_unknown"
    with pytest.raises(RuntimeError):
        _listed_status("presunto rinnovo")


def test_macerata_applicant_outcome_is_not_repaired_or_inferred():
    assert _applicant_status("") == ("pending", "")
    assert _applicant_status("Iscritta il 14/08/2026") == ("listed", "14/08/2026")
    with pytest.raises(RuntimeError):
        _applicant_status("forse iscritta")


def test_macerata_identifier_shape_is_conservative():
    assert _valid_identifier("01957330432")
    assert _valid_identifier("BRRRLA62H11H876Z")
    assert not _valid_identifier("0219970444")
    assert not _valid_identifier("009874300442")
    assert not _valid_identifier("1749820435 2073570430")


def test_macerata_reviewed_anomalies_are_frozen_boundary_evidence():
    assert len(_EXPECTED_LISTED_MALFORMED_IDENTIFIERS) == 37
    assert _EXPECTED_LISTED_MALFORMED_IDENTIFIERS[284] == "1749820435 2073570430"
    assert _EXPECTED_LISTED_MALFORMED_IDENTIFIERS[689] == "00948/570437"
    assert _EXPECTED_NONSTANDARD_EXPIRY[884] == "ISCRIZIONE 05/01/2027"
    assert len(_EXPECTED_NONSTANDARD_EXPIRY) == 10
    assert _EXPECTED_APPLICANT_MALFORMED_IDENTIFIERS == {
        7: "0195302433",
        20: "009874300442",
        27: "0219970444",
        57: "0085180435",
    }
    assert _EXPECTED_APPLICANT_BAD_DATES == {34: "27/01/206"}
