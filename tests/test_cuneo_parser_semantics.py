from white_list_archive.parsers.cuneo_positioned import (
    _EXPECTED_MALFORMED_IDENTIFIERS,
    _listed_status,
    _ordered_unique,
    _source_date,
)


def test_cuneo_status_normalisation_requires_explicit_source_labels():
    assert _listed_status("Iscritta") == "listed"
    assert _listed_status("iscritta") == "listed"
    assert _listed_status("Iscritto") == "listed"
    assert _listed_status("Aggiornamento in corso") == "renewal_update_in_progress"
    assert _listed_status("Aggiornamnto in corso") == "renewal_update_in_progress"


def test_cuneo_dates_preserve_source_digits_without_repair():
    assert _source_date("15/09/2026") == "2026-09-15"
    assert _source_date("09-07-2026") == "2026-07-09"
    assert _source_date("") == ""


def test_cuneo_reviewed_identifier_exceptions_are_fixed_boundary_evidence():
    assert len(_EXPECTED_MALFORMED_IDENTIFIERS) == 11
    assert _EXPECTED_MALFORMED_IDENTIFIERS[184] == "027874310043"
    assert _EXPECTED_MALFORMED_IDENTIFIERS[326] == "0329755042"


def test_cuneo_source_variants_are_order_preserving_only():
    assert _ordered_unique(["07/01/2025", "07/01/2015", "07/01/2025"]) == [
        "07/01/2025",
        "07/01/2015",
    ]
