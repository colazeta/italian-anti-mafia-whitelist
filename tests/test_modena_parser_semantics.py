from __future__ import annotations

import re

from white_list_archive.parsers.modena_tables import (
    _REFERENCE_DATE,
    _REVIEWED_MALFORMED_DATE_ROWS,
    _SOURCE_EXPECTATIONS,
    _UPDATE,
)


def test_modena_four_source_series_are_frozen() -> None:
    assert _REFERENCE_DATE == "2026-09-16"
    assert set(_SOURCE_EXPECTATIONS) == {
        "modena-provincial-listed",
        "modena-provincial-applicants",
        "modena-post-sisma-listed",
        "modena-post-sisma-applicants",
    }
    assert _SOURCE_EXPECTATIONS["modena-provincial-listed"]["physical_rows"] == 2174
    assert _SOURCE_EXPECTATIONS["modena-provincial-listed"]["public_records"] == 1181
    assert _SOURCE_EXPECTATIONS["modena-provincial-applicants"]["physical_rows"] == 803
    assert _SOURCE_EXPECTATIONS["modena-provincial-applicants"]["public_records"] == 502
    assert _SOURCE_EXPECTATIONS["modena-post-sisma-listed"]["physical_rows"] == 2927
    assert _SOURCE_EXPECTATIONS["modena-post-sisma-listed"]["public_records"] == 1679
    assert _SOURCE_EXPECTATIONS["modena-post-sisma-applicants"]["physical_rows"] == 432
    assert _SOURCE_EXPECTATIONS["modena-post-sisma-applicants"]["public_records"] == 430
    assert sum(item["public_records"] for item in _SOURCE_EXPECTATIONS.values()) == 3792


def test_modena_status_boundaries_are_source_explicit() -> None:
    assert _SOURCE_EXPECTATIONS["modena-provincial-listed"]["status_counts"] == {
        "listed": 634,
        "renewal_update_in_progress": 547,
    }
    assert _SOURCE_EXPECTATIONS["modena-post-sisma-listed"]["status_counts"] == {
        "listed": 926,
        "renewal_update_in_progress": 753,
    }
    assert _SOURCE_EXPECTATIONS["modena-provincial-applicants"]["status_counts"] == {"pending": 502}
    assert _SOURCE_EXPECTATIONS["modena-post-sisma-applicants"]["status_counts"] == {"pending": 430}
    assert _UPDATE.search("Aggiornamento in corso")
    assert _UPDATE.search("rinnovo in corso")
    assert not _UPDATE.search("art. 94-bis D.Lgs 159/2011")
    assert not _UPDATE.search("Società sottoposta a misura di controllo giudiziario")


def test_modena_malformed_dates_are_preserved_only_at_reviewed_locators() -> None:
    provincial = _REVIEWED_MALFORMED_DATE_ROWS["modena-provincial-listed"]
    post_sisma = _REVIEWED_MALFORMED_DATE_ROWS["modena-post-sisma-listed"]
    assert set(provincial) == {(154, 1, 11)}
    assert set(post_sisma) == {(32, 1, 5), (62, 1, 4), (144, 1, 4)}
    assert provincial[(154, 1, 11)][3] == "02/10/20218"
    assert post_sisma[(32, 1, 5)][5] == "18/008/2027"
    assert post_sisma[(62, 1, 4)][3] == "02/10/20218"
    assert post_sisma[(144, 1, 4)][3] == "02/10/20218"
    valid_dmy = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")
    assert not valid_dmy.fullmatch(provincial[(154, 1, 11)][3])
    assert not valid_dmy.fullmatch(post_sisma[(32, 1, 5)][5])


def test_modena_identifier_evidence_is_not_repaired() -> None:
    assert _SOURCE_EXPECTATIONS["modena-provincial-listed"]["identifier_counts"] == {0: 12, 1: 1169}
    assert _SOURCE_EXPECTATIONS["modena-provincial-applicants"]["identifier_counts"] == {0: 4, 1: 498}
    assert _SOURCE_EXPECTATIONS["modena-post-sisma-listed"]["identifier_counts"] == {0: 19, 1: 1660}
    assert _SOURCE_EXPECTATIONS["modena-post-sisma-applicants"]["identifier_counts"] == {0: 6, 1: 424}
