from white_list_archive.parsers.lucca_tables import (
    _first_source_date,
    _listed_status,
    _source_date,
    _source_identifiers,
)


def test_lucca_dates_are_conservative():
    assert _source_date("24/7/2026") == "2026-07-24"
    assert _source_date("12.06.2026") == "2026-06-12"
    assert _source_date("31/02/2026") == ""
    assert _source_date("10.2.26") == ""
    assert _first_source_date("IN AGG. 07/07/2026") == ("2026-07-07", "07/07/2026")
    assert _first_source_date("IN AGG.") == ("", "")


def test_lucca_identifier_extraction_does_not_repair_split_digits():
    assert _source_identifiers("CF/PI PRFDRN82D27Z129W 03281390249") == [
        "PRFDRN82D27Z129W",
        "03281390249",
    ]
    assert _source_identifiers("C.F./ P.I. P.I.02307990461") == ["02307990461"]
    assert _source_identifiers("C.F./P.I. BNGGLG82T02C236F/0 2137880460") == ["BNGGLG82T02C236F"]
    assert _source_identifiers("C.F./P.I. SCCLNI65R21I622O/011 93370465") == ["SCCLNI65R21I622O"]
    assert _source_identifiers("002493530469") == []
    assert _source_identifiers("0269090460") == []


def test_lucca_listed_status_requires_positive_update_marker():
    assert _listed_status("24/7/2026 IN AGG.") == "renewal_update_in_progress"
    assert _listed_status("IN AGG. 07/07/2026") == "renewal_update_in_progress"
    assert _listed_status("18/01/2027 Aggiornato con Modifica compagine del 23.6.2026.") == "listed"
    assert _listed_status("16/05/2025 AGGIORNATA COMPAGINE SOC. IL 17/05/2024") == "listed"
    assert _listed_status("11/02/2027") == "listed"
