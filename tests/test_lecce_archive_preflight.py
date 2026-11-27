from hashlib import sha256
import json

from white_list_archive.acquisition.lecce_archive_preflight import (
    APPLICANT_HEADER, audit_pair, profile_pages,
)


class Table:
    def __init__(self, rows):
        self.rows = rows

    def extract(self):
        return self.rows


class Page:
    def __init__(self, rows):
        self.rows = rows

    def extract_text(self):
        return "19/11/2026"

    def find_tables(self):
        return [Table(self.rows)]


def test_listed_census_preserves_ambiguous_rows_and_redacts():
    row = ["PRIVATE-NAME", "PRIVATE-OFFICE", "", "12345678901",
           "01/01/2026", "INVALID", "UNKNOWN-PRIVATE-NOTE"]
    report = profile_pages([Page([
        ["SEZIONE I"] + [""] * 6, row, row, ["bad width"], [""] * 7,
        ["SEZIONE XI"] + [""] * 6, row,
    ])], "listed")
    c = report["counts"]
    assert c["physical_rows"] == 7
    assert c["unclassified_rows"] == 3
    assert c["candidate_data_shaped_rows"] == 2
    assert c["rows_with_unparseable_nonblank_date"] == 2
    assert report["listed_exact_cell_tuple_groups_not_entities"] == 1
    assert report["listed_status_clues"] == {"unreviewed": 2}
    assert report["source_edition_approved"] is False
    assert "PRIVATE" not in json.dumps(report)


def test_applicant_census_keeps_missing_identity_and_header_separate():
    report = profile_pages([Page([
        APPLICANT_HEADER, ["PRIVATE-NAME", "PRIVATE-OFFICE", "12345678901", "01/01/2026"],
        ["PRIVATE-NAME", "", "", "01/01/2026"],
    ])], "applicant")
    assert report["counts"]["administrative_header_rows"] == 1
    assert report["counts"]["candidate_data_shaped_rows"] == 1
    assert report["counts"]["unclassified_rows"] == 1
    assert "PRIVATE" not in json.dumps(report)


def test_exact_pair_readback_and_redacted_failure():
    raw = b"test"
    digest = sha256(raw).hexdigest()
    class Store:
        def read_digest_verified(self, _):
            return raw
    def scanner(_raw, _population):
        raise ValueError("PRIVATE-ROW")
    result = audit_pair(Store(), pins=(("listed", digest, 4), ("applicant", digest, 5)),
                        scanner=scanner)
    assert result["originals_sha_verified"] == 1
    assert result["physical_profiles_completed"] == 0
    assert result["public_promotions"] == 0
    assert "PRIVATE" not in json.dumps(result)


def test_residual_status_and_date_diagnostics_do_not_resolve_or_disclose():
    report = profile_pages([Page([
        ["SEZIONE I"] + [""] * 6,
        ["PRIVATE-NAME", "", "", "12345678901", "31/02/2026", "PRIVATE-DATE", "PRIVATE-NOTE"],
        ["PRIVATE-RESIDUAL"],
    ])], "listed")
    assert report["counts"]["unclassified_rows"] == 1
    assert report["unclassified_row_shape_counts"] == {"unexpected_width:width_1:nonblank_1": 1}
    assert report["unreviewed_status_shape_counts_not_status_mapping"] == {"unreviewed_total": 1}
    assert report["unparseable_date_field_shapes"] == {"numeric_date_shape": 1, "other_nonblank": 1}
    assert report["listed_status_clues"] == {"unreviewed": 1}
    assert not report["privacy_approved"]
    assert "PRIVATE" not in json.dumps(report)


def test_exact_tuple_review_counts_groups_not_sector_rows():
    row = ["PRIVATE-NAME", "PRIVATE-OFFICE", "", "12345678901",
           "01/01/2026", "INVALID", "UNKNOWN-PRIVATE-NOTE"]
    report = profile_pages([Page([
        ["SEZIONE I"] + [""] * 6, row, row,
        ["SEZIONE II"] + [""] * 6, row,
    ])], "listed")
    assert report["counts"]["candidate_data_shaped_rows"] == 3
    assert report["listed_exact_cell_tuple_groups_not_entities"] == 1
    assert report["listed_group_status_clues_not_approved"] == {"unreviewed": 1}
    review = report["listed_group_review_flags_not_approved"]
    assert review["unreviewed_status"] == 1
    assert review["unparseable_nonblank_date"] == 1
    assert review["groups_with_any_review_flag"] == 1
    assert review["groups_with_repeated_same_section"] == 1
    assert not report["privacy_approved"]
    assert "PRIVATE" not in json.dumps(report)
    assert "12345678901" not in json.dumps(report)


def test_newer_edition_pins_do_not_reuse_old_date_marker_or_originals():
    from white_list_archive.acquisition.lecce_archive_preflight import (
        EDITION_PROFILES, audit_edition,
    )
    old_pins, _, _, old_scope = EDITION_PROFILES['2026-11-19']
    new_pins, revision, marker, new_scope = EDITION_PROFILES['2026-11-25']
    assert old_scope != new_scope
    assert {p[1] for p in old_pins}.isdisjoint(p[1] for p in new_pins)
    assert marker == '25/11/2026'
    report = profile_pages([Page([APPLICANT_HEADER])], 'applicant', marker=marker)
    assert report['counts']['filename_date_marker_pages'] == 0
    assert not report['source_edition_approved']
    class Store:
        def __init__(self):
            self.requested = []
        def read_digest_verified(self, digest):
            self.requested.append(digest)
            return b'PRIVATE-WRONG-BYTES'
    store = Store()
    result = audit_edition(store, '2026-11-25')
    assert store.requested == [p[1] for p in new_pins]
    assert result['scope'] == new_scope and result['robot_revision'] == revision
    assert result['originals_sha_verified'] == 0
    assert result['physical_profiles_completed'] == 0
    assert not result['privacy_approved'] and not result['public_release_eligible']
    assert 'PRIVATE' not in json.dumps(result)
    import pytest
    with pytest.raises(KeyError):
        audit_edition(store, '2026-11-26')


def test_edition_marker_requires_label_in_bounded_or_administrative_header():
    from white_list_archive.acquisition.lecce_archive_preflight import labelled_marker_clue
    assert labelled_marker_clue("Aggiornato al 25/11/2026", "25/11/2026")
    assert not labelled_marker_clue("Data iscrizione 25/11/2026", "25/11/2026")
    assert not labelled_marker_clue("Aggiornato al 25/11/20260", "25/11/2026")

    class HeaderPage(Page):
        width, height = 600, 800
        def __init__(self, rows, header):
            super().__init__(rows)
            self.header = header
        def find_tables(self):
            table = Table(self.rows)
            table.bbox = (0, 100, 600, 700)
            return [table]
        def crop(self, box):
            assert box == (0, 0, 600, 100)
            class Header:
                def extract_text(inner):
                    return self.header
            return Header()

    row = ["PRIVATE NAME", "PRIVATE ADDRESS", "11111111111", "25/11/2026"]
    report = profile_pages([
        HeaderPage([APPLICANT_HEADER, row], "Aggiornato al 25/11/2026 PRIVATE HEADER"),
        HeaderPage([APPLICANT_HEADER, row], "Data istanza 25/11/2026"),
        Page([APPLICANT_HEADER, row]),
    ], "applicant", marker="25/11/2026")
    assert report["counts"]["pages_with_bounded_header_geometry"] == 2
    assert report["counts"]["labelled_edition_marker_clue_pages"] == 1
    assert not report["source_edition_approved"]
    assert "PRIVATE" not in json.dumps(report)
    assert "11111111111" not in json.dumps(report)
