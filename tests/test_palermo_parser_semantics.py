from white_list_archive.parsers.palermo_positioned import (
    PARSERS,
    _applicant_status,
    _listed_status,
    _section_values,
    _strict_date,
    _valid_identifier,
)


def test_palermo_dispatch_is_explicit():
    assert set(PARSERS) == {"palermo_listed", "palermo_applicants"}


def test_palermo_identifier_shapes_are_source_preserving():
    assert _valid_identifier("05815390827")
    assert _valid_identifier("BRSSVT64H09L740K")
    assert not _valid_identifier("0557970829")
    assert not _valid_identifier("CNGVCN61P65B780 H")


def test_palermo_dates_are_strict_without_digit_repair():
    assert _strict_date("28/07/2026") == "28/07/2026"
    assert _strict_date("28/072027") == ""
    assert _strict_date("20/072027") == ""


def test_palermo_sections_are_explicit_and_ordered():
    assert _section_values("1 3 5 10") == ["Sezione 1", "Sezione 3", "Sezione 5", "Sezione 10"]
    for value in ("", "3 3", "5 3", "11"):
        try:
            _section_values(value)
        except RuntimeError:
            pass
        else:
            raise AssertionError(f"section drift must fail closed: {value!r}")


def test_palermo_listed_status_requires_approved_positive_evidence():
    assert _listed_status("") == "listed"
    assert _listed_status("Aggiornamento in corso") == "renewal_update_in_progress"
    assert _listed_status("Aggironamento in corso") == "renewal_update_in_progress"
    assert _listed_status("Aggiornamneto in corso") == "renewal_update_in_progress"
    note = (
        "provvedimento prot. n. 119218 del 30/07/2026, di applicazione della misura di "
        "prevenzione collaborativa, ai sensi dell'art. 94 bis, D.lgs."
    )
    assert _listed_status(note) == "listed"
    try:
        _listed_status("nuovo stato")
    except RuntimeError:
        pass
    else:
        raise AssertionError("unknown listed outcome must fail closed")


def test_palermo_applicant_status_is_closed_to_observed_vocabulary():
    assert _applicant_status("In istruttoria") == "pending"
    assert _applicant_status("In istrutoria") == "pending"
    assert _applicant_status("Iistruttoria") == "pending"
    try:
        _applicant_status("Iscritta")
    except RuntimeError:
        pass
    else:
        raise AssertionError("unreviewed applicant outcome must fail closed")
