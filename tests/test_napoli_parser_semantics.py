from __future__ import annotations

import pytest

from white_list_archive.parsers.napoli_tables import (
    _EXPECTED_APPLICANT_RECORDS,
    _EXPECTED_APPLICANT_STATUS_COUNTS,
    _EXPECTED_LISTED_RECORDS,
    _EXPECTED_LISTED_STATUS_COUNTS,
    _LISTED_MALFORMED_LISTING_DATE,
    _LISTED_NONCALENDAR_EXPIRY,
    _SECTION_EXCEPTIONS,
    _listed_expiry,
    _listed_listing_date,
    _sections,
    _short_date,
)


def test_napoli_source_denominators_and_statuses_are_frozen() -> None:
    assert _EXPECTED_LISTED_RECORDS == 2259
    assert _EXPECTED_APPLICANT_RECORDS == 2571
    assert _EXPECTED_LISTED_STATUS_COUNTS == {
        "listed": 792,
        "renewal_update_in_progress": 1423,
        "rejected_or_denied": 12,
        "cancellation_related": 3,
        "other_or_unknown": 29,
    }
    assert _EXPECTED_APPLICANT_STATUS_COUNTS == {
        "pending": 2530,
        "rejected_or_denied": 40,
        "other_or_unknown": 1,
    }
    assert len(_LISTED_MALFORMED_LISTING_DATE) == 1
    assert len(_LISTED_NONCALENDAR_EXPIRY) == 7
    assert len(_SECTION_EXCEPTIONS["listed"]) == 4
    assert len(_SECTION_EXCEPTIONS["applicants"]) == 5


def test_napoli_malformed_listing_date_is_exactly_source_bound() -> None:
    assert (
        _listed_listing_date(
            "14/0319",
            ordinal=556,
            company="DE LISIO COSTRUZIONI SRL",
            identifier_raw="04518100633",
        )
        == ""
    )
    with pytest.raises(RuntimeError, match="reviewed malformed listing-date drift"):
        _listed_listing_date(
            "14/03/19",
            ordinal=556,
            company="DE LISIO COSTRUZIONI SRL",
            identifier_raw="04518100633",
        )
    with pytest.raises(RuntimeError, match="reviewed malformed listing-date drift"):
        _listed_listing_date(
            "14/0319",
            ordinal=556,
            company="DE LISIO COSTRUZIONI SRL",
            identifier_raw="04518100634",
        )


def test_napoli_date_handling_is_fail_closed() -> None:
    assert _short_date("14/03/19", ordinal=1, population="listed", field="listing date") == "2019-03-14"
    assert _short_date("", ordinal=1, population="listed", field="listing date") == ""
    with pytest.raises(RuntimeError, match="unreviewed listing date typography"):
        _short_date("14/0319", ordinal=1, population="listed", field="listing date")
    with pytest.raises(RuntimeError, match="invalid listing date calendar date"):
        _short_date("31/02/19", ordinal=1, population="listed", field="listing date")


def test_napoli_noncalendar_expiry_is_not_inferred_as_a_date() -> None:
    raw = "Iscrizione valida per la durata dell'amministrazi one giudiziaria"
    assert _listed_expiry(raw, ordinal=83, company="AMBIENTE CAMPANIA S.R.L.") == ""
    with pytest.raises(RuntimeError, match="reviewed non-calendar expiry drift"):
        _listed_expiry(raw, ordinal=83, company="ALTRA IMPRESA")


def test_napoli_section_anomalies_retain_only_positive_valid_tokens() -> None:
    assert _sections(
        "II-IIII",
        ordinal=454,
        population="listed",
        company="CONGLOMERATI S.r.l.",
        identifier_raw="05027321214",
    ) == ["Sezione II"]
    assert _sections(
        "IIII",
        ordinal=1099,
        population="applicants",
        company="FG SERVICE S.R.L.",
        identifier_raw="09706611218",
    ) == []
    with pytest.raises(RuntimeError, match="reviewed section exception drift"):
        _sections(
            "II-IV",
            ordinal=454,
            population="listed",
            company="CONGLOMERATI S.r.l.",
            identifier_raw="05027321214",
        )
