"""Contract tests for November Catania parser (no real company data)."""
from datetime import date
import pytest

from white_list_archive.parsers import catania_openxml as september
from white_list_archive.parsers import catania_openxml_november as november


def test_november_parser_has_distinct_source_identity_and_pins():
    assert set(november.PARSERS)=={"catania_listed_2026_11","catania_applicants_2026_11"}
    assert not (set(november.PARSERS) & set(september.PARSERS))
    assert november._DATE=="2026-11-06"
    assert november._LAYOUT["listed"]["company_rows"]==1864
    assert november._LAYOUT["applicant"]["company_rows"]==173
    assert november._LAYOUT["listed"]["first_row"]==3
    assert november._LAYOUT["applicant"]["first_row"]==5
    assert november._PINS["catania_listed_2026_11"][2] != november._PINS["catania_applicants_2026_11"][2]


def test_malformed_sectors_do_not_create_inferred_sections():
    sectors, anomaly=november._sections("1,2,34,,5,6,10")
    assert sectors==["Sezione 1","Sezione 2","Sezione 5","Sezione 6","Sezione 10"]
    assert anomaly
    assert november._sections("1,2,3")==(["Sezione 1","Sezione 2","Sezione 3"],False)
    with pytest.raises(RuntimeError):
        november._sections("34,69")
    with pytest.raises(RuntimeError):
        november._sections("2,2")


def test_bad_calendar_values_are_kept_raw_not_turned_into_dates():
    assert november._calendar_or_raw(date(2026,11,6))==("2026-11-06",False)
    assert november._calendar_or_raw("16/072026")==("",True)
    with pytest.raises(RuntimeError):
        november._calendar_or_raw("")


def test_raw_source_whitelist_status_is_not_inferred_from_expiry():
    # Both source-status labels have known, separate meanings. A date alone
    # is insufficient to infer a renewal/revocation/negative decision.
    assert november._LAYOUT["listed"]["company_rows"] > september._LISTED_RECORDS
