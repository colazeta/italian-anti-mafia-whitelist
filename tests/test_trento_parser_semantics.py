from __future__ import annotations

import pytest

from white_list_archive.parsers import trento_tables as trento


def test_trento_source_and_record_denominators_are_frozen() -> None:
    assert trento._LISTED_PAGES == 289
    assert trento._APPLICANT_PAGES == 22
    assert trento._LISTED_PHYSICAL_ROWS == 3208
    assert trento._APPLICANT_PHYSICAL_ROWS == 117
    assert trento._LISTED_SECTION_ROWS == 3020
    assert trento._LISTED_RECORDS == 1366
    assert trento._APPLICANT_RECORDS == 98
    assert trento._LISTED_RECORDS + trento._APPLICANT_RECORDS == 1464


def test_trento_listed_section_and_status_boundaries_are_frozen() -> None:
    assert trento._EXPECTED_SECTION_ROWS == {
        "I": 571,
        "II": 198,
        "III": 499,
        "IV": 322,
        "V": 700,
        "VI": 308,
        "VII": 9,
        "VIII": 17,
        "IX": 105,
        "X": 291,
    }
    assert trento._EXPECTED_LISTED_SOURCE_STATUS_COUNTS == {
        "listed": 1507,
        "renewal_update_in_progress": 1513,
    }
    assert trento._EXPECTED_LISTED_STATUS_COUNTS == {
        "listed": 699,
        "renewal_update_in_progress": 667,
    }
    assert trento._EXPECTED_APPLICANT_STATUS_COUNTS == {"pending": 98}


def test_trento_table_geometry_and_continuations_are_frozen() -> None:
    assert trento._EXPECTED_LISTED_RAW_WIDTHS == {7: 3169, 9: 39}
    assert trento._EXPECTED_LISTED_TABLE_COUNTS == {0: 1, 1: 281, 2: 7}
    assert trento._TWO_TABLE_PAGES == {69, 116, 147, 244, 246, 248, 261}
    assert trento._ZERO_TABLE_PAGES == {289}
    assert len(trento._HEADER_COORDS) == 10
    assert len(trento._LISTED_BLANK_COORDS) == 6
    assert len(trento._LISTED_CONTINUATIONS) == 172
    assert len(trento._APPLICANT_CONTINUATIONS) == 17
    assert trento._APPLICANT_BLANK_COORDS == {(19, 1, 1)}
    assert trento._APPLICANT_HEADER_COORDS == {(1, 1, 1)}


def test_trento_reviewed_anomaly_populations_are_frozen() -> None:
    assert set(trento._LISTED_DATE_EXCEPTIONS) == {(274, 1, 8)}
    assert len(trento._LISTED_IDENTIFIER_EXCEPTIONS) == 4
    assert trento._LISTED_IDENTIFIER_EXCEPTIONS[(221, 1, 13)][2] == ()
    assert trento._LISTED_IDENTIFIER_EXCEPTIONS[(250, 1, 6)][2] == (
        "02785350220",
        "85000750225",
    )
    assert trento._LISTED_IDENTIFIER_EXCEPTIONS[(260, 1, 4)][2] == (
        "84002830226",
        "01157050228",
    )
    assert trento._LISTED_IDENTIFIER_EXCEPTIONS[(280, 1, 5)][2] == (
        "01731370225",
        "01191130218",
    )
    assert set(trento._APPLICANT_DATE_EXCEPTION) == {(12, 1, 3)}


def test_trento_positive_identifier_extraction_is_conservative() -> None:
    assert trento._positive_identifiers("02785350220") == ["02785350220"]
    assert trento._positive_identifiers("RSSMRA80A01H501U") == ["RSSMRA80A01H501U"]
    assert trento._positive_identifiers("006281590229") == []
    assert trento._positive_identifiers("P.IVA 02785350220 C.F.85000750225") == [
        "02785350220",
        "85000750225",
    ]
    assert trento._positive_identifiers("C.F.84002830226 P.IVA 01157050228") == [
        "84002830226",
        "01157050228",
    ]


def test_trento_split_table_geometry_normalises_only_reviewed_shape() -> None:
    seven = ["A", "B", "C", "01234567890", "01.01.2026", "31.12.2026", ""]
    assert trento._normalise_listed_cells(seven, coord=(1, 1, 2)) == tuple(seven)

    nine = ["A", "B", "C", "01234567890", "", "01.01.2026", "", "31.12.2026", ""]
    assert trento._normalise_listed_cells(nine, coord=(1, 1, 2)) == (
        "A",
        "B",
        "C",
        "01234567890",
        "01.01.2026",
        "31.12.2026",
        "",
    )

    with pytest.raises(RuntimeError, match="ambiguous split registration date"):
        trento._normalise_listed_cells(
            ["A", "B", "C", "01234567890", "01.01.2026", "02.01.2026", "", "31.12.2026", ""],
            coord=(1, 1, 2),
        )


def test_trento_dates_fail_closed() -> None:
    assert trento._calendar_date("29.06.2026", context="test") == "29.06.2026"
    with pytest.raises(RuntimeError, match="unreviewed date typography"):
        trento._calendar_date("29.06.26", context="test")
    with pytest.raises(RuntimeError, match="invalid calendar date"):
        trento._calendar_date("31.02.2026", context="test")


def test_trento_applicant_activity_split_requires_complete_source_coverage() -> None:
    raw = "Trasporto di materiali a discarica per conto terzi (Sezione I) Noli a caldo (Sezione V)"
    assert trento._split_applicant_activities(raw) == [
        "Trasporto di materiali a discarica per conto terzi (Sezione I)",
        "Noli a caldo (Sezione V)",
    ]
    with pytest.raises(RuntimeError, match="left unparsed text"):
        trento._split_applicant_activities(
            "Trasporto di materiali a discarica per conto terzi (Sezione I) testo non classificato"
        )


def test_trento_applicant_activity_membership_counts_are_frozen() -> None:
    assert trento._EXPECTED_APPLICANT_ACTIVITY_SECTION_COUNTS == {
        "I": 34,
        "II": 10,
        "III": 16,
        "IV": 19,
        "V": 32,
        "VI": 12,
        "VIII": 3,
        "IX": 14,
        "X": 16,
    }
