from white_list_archive.parsers.trapani_tables import (
    PARSERS,
    _activities,
    _group_status,
    _strict_date,
)


def test_trapani_dispatch_is_explicit():
    assert set(PARSERS) == {"trapani_listed", "trapani_applicants"}


def test_trapani_dates_are_strict_without_digit_repair():
    assert _strict_date("03/03/2026") == "03/03/2026"
    assert _strict_date("23 /04/2026") == "23/04/2026"
    assert _strict_date("0 3/03/2026") == ""
    assert _strict_date("03/03/206") == ""


def test_trapani_status_requires_positive_update_evidence():
    assert _group_status(["", ""]) == "listed"
    assert _group_status(["In aggiornamento per rinnovo"] * 2) == "renewal_update_in_progress"
    assert _group_status(["*"]) == "renewal_update_in_progress"
    assert _group_status(["*-"]) == "renewal_update_in_progress"


def test_trapani_group_status_rejects_semantic_drift():
    try:
        _group_status(["", "In aggiornamento per rinnovo"])
    except RuntimeError as exc:
        assert "mixes blank and non-blank" in str(exc)
    else:
        raise AssertionError("mixed listed/update evidence must fail closed")

    try:
        _group_status(["nuovo stato"])
    except RuntimeError as exc:
        assert "unapproved update marker" in str(exc)
    else:
        raise AssertionError("unknown update vocabulary must fail closed")


def test_trapani_requested_activities_are_source_preserving():
    raw = "-Fornitura di ferro lavorato -Noli a caldo"
    assert _activities(raw) == ["Fornitura di ferro lavorato", "Noli a caldo"]
    assert _activities("Attività singola") == ["Attività singola"]
