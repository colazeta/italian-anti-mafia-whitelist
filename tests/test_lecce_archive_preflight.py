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
