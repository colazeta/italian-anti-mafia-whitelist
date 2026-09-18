from white_list_archive.parsers.cremona_combined import (
    _identifier_kind,
    _sections,
    _source_date,
    _status,
)


def test_cremona_status_requires_positive_source_evidence():
    assert _status("", "24/04/2026", "24/04/2027", 1) == ("listed", "", "")
    assert _status("ISCRITTO ELENCO RICHIEDENTI-\nIN ISTRUTTORIA", "", "", 3) == (
        "pending",
        "",
        "",
    )
    assert _status("FATTA ISTANZA IN DATA 18/06/2025", "", "", 180) == (
        "pending",
        "18/06/2025",
        "",
    )
    assert _status("FATTA ISTANZA A PERMANERE\nIN DATA 23/07/2026", "", "", 6) == (
        "renewal_update_in_progress",
        "",
        "23/07/2026",
    )
    assert _status("FATTA ISTANZA A PERAMERE IN DATA 29/02/2024", "", "", 165) == (
        "renewal_update_in_progress",
        "",
        "29/02/2024",
    )


def test_cremona_dates_are_not_repaired():
    assert _source_date("15/09/2026", field="listing", ordinal=1) == "2026-09-15"
    assert _source_date("", field="listing", ordinal=1) == ""


def test_cremona_identifier_exceptions_stay_raw_only():
    assert _identifier_kind("01710310192", 1) == ("strict_11_only", ["01710310192"])
    assert _identifier_kind("MMBTTL64A01D150Z\n01832620197", 151) == (
        "strict_11_plus_fiscal16",
        ["01832620197", "MMBTTL64A01D150Z"],
    )
    assert _identifier_kind("009226901930", 11) == ("reviewed_malformed_numeric_only", [])


def test_cremona_sections_are_source_markers_only():
    assert _sections(["X", "", "x", "", "", "", "", "", "", ""], 1) == [
        "Sezione I",
        "Sezione III",
    ]
