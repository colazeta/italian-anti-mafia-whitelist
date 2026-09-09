from white_list_archive.parsers.multi_prefecture_tables import _aosta_activities, _status_aosta_applicant


def test_aosta_activity_split_preserves_i_quater():
    assert _aosta_activities("C – D – E – I-quater") == ["C", "D", "E", "I-quater"]


def test_aosta_applicant_source_outcomes_are_not_inferred():
    assert _status_aosta_applicant("ISCRITTA IN WHITE LIST") == "listed"
    assert _status_aosta_applicant("IN ISTRUTTORIA") == "pending"
    assert _status_aosta_applicant("esito non classificato") == "other_or_unknown"
