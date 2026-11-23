"""Verona protected PDF preflight: exact bytes, bounded redaction, no approval."""
from collections import Counter
from hashlib import sha256
import json

import pytest

from white_list_archive.acquisition import verona_archive_preflight as qa


class FakePage:
    width = 600
    height = 800

    def __init__(self, text, header, rows):
        self.text = text
        self.header = header
        self.rows = rows
    def extract_text(self):
        return self.text
    def crop(self, rect):
        assert len(rect) == 4
        return FakePage(self.header, self.header, [])
    def find_tables(self):
        class Table:
            def __init__(self, rows):
                self.rows = rows
            def extract(self):
                return self.rows
        return [Table(self.rows)] if self.rows else []
    def close(self):
        pass


def test_redacted_physical_profile_no_row_data_or_edition():
    sensitive = "RISERVATO ROSSI MARIO RSSMRA85M01H501Z"
    page = FakePage(
        "Elenco imprese iscritte\n" + sensitive,
        "Prefettura di Verona\nElenco imprese iscritte 19 novembre 2026",
        [["Azienda", "CF"], [sensitive, "12345678901"]],
    )
    report = qa.page_profile(page, "listed")
    serial = json.dumps(report)
    assert report["table_count"] == 1
    assert report["physical_table_rows"] == 2
    assert report["filename_date_in_title_line_cue"]
    assert report["verona_authority_header_cue"]
    assert sensitive not in serial
    assert "12345678901" not in serial


def test_unrelated_date_cannot_become_edition_cue():
    p = FakePage(
        "Elenco imprese richiedenti\n19/11/2026 Rossi Mario",
        "Prefettura di Verona\nElenco imprese richiedenti\n19/11/2026 Rossi",
        [],
    )
    assert not qa.page_profile(p, "applicant")["filename_date_in_title_line_cue"]


def test_exact_verified_pair_and_privacy_fail_closed():
    originals = (b"%PDF-1.4\nLISTED", b"%PDF-1.4\nAPPLICANT")
    pins = tuple((population, sha256(data).hexdigest(), len(data))
                 for (population, _, _), data in zip(qa.PINS, originals))
    class Store:
        def read_digest_verified(self, digest):
            return originals[0] if digest == pins[0][1] else originals[1]
    result = qa.audit_pair(Store(), pins=pins, scanner=lambda raw, pop: {
        "pages": 1, "logical_record_census": False,
        "official_document_date_authenticated": False,
    })
    assert result["originals_sha_verified"] == 2
    assert result["physical_profiles_completed"] == 2
    assert result["source_edition_approved"] is False
    assert result["public_release_eligible"] is False
    assert result["postgresql_writes"] == result["public_promotions"] == 0


def test_wrong_size_never_qualifies_original_and_errors_are_redacted():
    private = b"%PDF-1.4\nPRIVATE_SOURCE_IDENTIFIER"
    pins = (("listed", sha256(private).hexdigest(), len(private)+1),
            ("applicant", sha256(private).hexdigest(), len(private)+1))
    class Store:
        def read_digest_verified(self, digest):
            return private
    result = qa.audit_pair(Store(), pins=pins)
    assert result["originals_sha_verified"] == 0
    assert result["physical_profiles_completed"] == 0
    assert result["results"][0]["review_code"] == "byte_identity_mismatch"
    assert "PRIVATE" not in json.dumps(result)


def test_oversize_and_table_limit_fail_closed():
    with pytest.raises(ValueError):
        qa.census_pdf(b"BAD", "listed")
    huge = FakePage("x", "x", [["x", "y"]] * (qa.MAX_TABLE_ROWS_PER_PAGE + 1))
    with pytest.raises(ValueError, match="bounded review"):
        qa.page_profile(huge, "listed")


def test_workflow_only_existing_protected_worker():
    from pathlib import Path
    workflow = (Path(__file__).resolve().parents[1] /
                ".github/workflows/transform-reviewed-captures.yml").read_text()
    block = workflow.split(
        "- name: Audit archived Verona listed/applicant PDFs (source only)", 1)[1].split("- name:", 1)[0]
    assert "matrix.shard == 0 && !cancelled()" in block
    assert "continue-on-error: true" in block
    assert "python -m white_list_archive.acquisition.verona_archive_preflight" in block


def test_bounded_row_shapes_provide_counts_not_identity_or_continuation_decisions():
    private_name = "PERSONA PRIVATA"
    private_cf = "RSSMRA85M01H501Z"
    rows = [
        ["Ragione sociale", "Codice fiscale", "Sezione"],
        [private_name, private_cf, "I"],
        ["Impresa riservata", "12345678901", "II"],
        ["Segue dalla riga precedente", None, None],
        ["", "", ""],
        ["Societa", "12345678901", private_cf],
    ]
    page = FakePage("Elenco imprese iscritte 19/11/2026", "Prefettura di Verona", rows)
    result = qa.page_profile(page, "listed")
    counts = result["unapproved_row_shape_counts"]
    assert result["physical_table_rows"] == 6
    assert counts["header_like_rows"] == 1
    assert counts["eleven_digit_whole_cell_rows"] == 2
    assert counts["sixteen_character_whole_cell_rows"] == 2
    assert counts["both_syntactic_shapes_rows"] == 1
    assert counts["unanchored_nonheader_nonblank_rows"] == 1
    assert counts["empty_table_rows"] == 1
    assert counts["single_nonblank_cell_rows"] == 1
    assert result["filename_date_anywhere_in_page_text_cue"]
    assert not result["filename_date_in_title_line_cue"]
    serialized = json.dumps(result)
    assert private_name not in serialized
    assert private_cf not in serialized
    assert "12345678901" not in serialized
    assert "Segue dalla riga" not in serialized


def test_substring_identifier_or_unvalidated_header_cannot_become_anchor():
    counts = qa.row_shape_clues(["CF: RSSMRA85M01H501Z", "PIVA: 12345678901", "record"])
    assert not counts["eleven_digit_whole_cell_rows"]
    assert not counts["sixteen_character_whole_cell_rows"]
    assert counts["unanchored_nonheader_nonblank_rows"]
    with pytest.raises(ValueError, match="bounded review"):
        qa.row_shape_clues(["PRIVATE " * 2000])


def test_pdf_total_aggregates_shape_clues_but_never_approves(monkeypatch):
    page = FakePage(
        "Elenco imprese richiedenti",
        "Prefettura di Verona",
        [["Denominazione", "Partita IVA", "Settore"],
         ["Societa privata", "12345678901", "I"]],
    )
    class FakePdf:
        pages = [page]
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
    monkeypatch.setattr(qa.pdfplumber, "open", lambda _: FakePdf())
    result = qa.census_pdf(b"%PDF-1.4 test", "applicant")
    assert result["unapproved_row_shape_counts"]["eleven_digit_whole_cell_rows"] == 1
    assert result["unapproved_row_shape_counts"]["header_like_rows"] == 1
    assert result["identifier_syntax_only_not_validated"] is True
    assert result["logical_record_census"] is False
    assert result["official_document_date_authenticated"] is False
