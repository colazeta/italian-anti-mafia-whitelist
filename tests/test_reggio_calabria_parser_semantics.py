from __future__ import annotations

from white_list_archive.parsers.reggio_calabria_tables import (
    _applicant_status,
    _listed_status,
    _source_date,
    _strict_identifiers,
)


def test_reggio_calabria_source_dates_are_conservative() -> None:
    assert _source_date("21-gen-22") == "2022-01-21"
    assert _source_date("08.08.2024") == "2024-08-08"
    assert _source_date("23- mar - 26") == "2026-03-23"
    assert _source_date("31-lug- 27") == "2027-07-31"
    assert _source_date("12/06/2020 (cessazione amm.ne giudiziaria)") == "2020-06-12"
    assert _source_date("03.06.2022") == "2022-06-03"
    assert _source_date("07/13/2024") == ""
    assert _source_date("07/04//23") == ""


def test_reggio_calabria_statuses_preserve_nonstandard_evidence() -> None:
    assert _listed_status("") == "listed"
    assert _listed_status("Istanza di rinnovo iscrizione White List - Istruttoria in corso") == "renewal_update_in_progress"
    assert _listed_status("Aggiornamento in corso") == "renewal_update_in_progress"
    assert _listed_status("Iscrizione disposta ai sensi dell'art. 34 bis") == "other_or_unknown"
    assert _applicant_status("Istruttoria") == "pending"
    assert _applicant_status("Istrutoria") == "pending"
    assert _applicant_status("Istruttorria") == "pending"
    assert _applicant_status("") == "other_or_unknown"
    assert _applicant_status("L.M.") == "other_or_unknown"


def test_reggio_calabria_identifiers_are_not_repaired() -> None:
    assert _strict_identifiers("02198480804") == ["02198480804"]
    assert _strict_identifiers("MRBNMR66S56H224D") == ["MRBNMR66S56H224D"]
    assert _strict_identifiers("03205300803)") == []
    assert _strict_identifiers("988220802") == []
