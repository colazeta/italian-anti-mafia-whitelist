import json
from white_list_archive.acquisition.chieti_archive_preflight import profile_docbook, audit, PINS


def test_listed_shape_census_preserves_residual_and_never_prints_values():
    doc = """<book><informaltable><row><entry>Ragione Sociale</entry><entry/><entry/><entry/><entry/><entry/></row>
    <row><entry>PRIVATE BUSINESS</entry><entry>PRIVATE ADDRESS</entry><entry>01234567890</entry><entry>01/11/2026</entry><entry>01/11/2027</entry><entry/></row>
    <row><entry>PRIVATE RESIDUAL</entry></row></informaltable></book>"""
    profile = profile_docbook(doc, "listed")
    assert profile["counts"]["physical_rows"] == 3
    assert profile["counts"]["six_column_data_clue"] == 1
    assert profile["counts"]["unclassified"] == 1
    assert profile["review_code"] == "unresolved_listed_rows"
    assert profile["counts"]["identifier_syntax"] == 1
    assert not profile["logical_census_approved"]
    assert "PRIVATE" not in json.dumps(profile)
    assert "01234567890" not in json.dumps(profile)


def test_applicant_bel_header_and_residual_are_not_approved():
    header = ["Ragione Sociale", "Sede legale", "Sede secondaria con rappresentanza stabile in Italia",
              "Codice fiscale Partita IVA", "Attività per cui è richiesta l’iscrizione",
              "Data di presentazione dell’istanza", "Esito", ""]
    row = ["PRIVATE BUSINESS", "PRIVATE ADDRESS", "", "01234567890", "PRIVATE ACTIVITY",
           "01/11/2026", "PRIVATE OUTCOME", ""]
    result = profile_docbook("<para>" + "\x07".join(header + row + ["PRIVATE RESIDUAL"]) + "</para>", "applicant")
    assert result["counts"]["seven_column_data_clue"] == 1
    assert result["counts"]["residual_tokens"] == 1
    assert result["review_code"] == "unresolved_applicant_blocks"
    assert not result["logical_census_approved"]
    assert "PRIVATE" not in json.dumps(result)
    assert "01234567890" not in json.dumps(result)


def test_mismatched_originals_are_not_scanned_or_approved():
    class Store:
        def read_digest_verified(self, digest):
            return b"wrong bytes"
    def scanner(*args):
        raise AssertionError("Must not scan mismatched bytes")
    report = audit(Store(), PINS, scanner)
    assert report["originals_sha_verified"] == 0
    assert report["physical_profiles_returned"] == 0
    assert not report["source_edition_approved"]
    assert not report["privacy_approved"]


def test_missing_table_is_explicit_review_block():
    result = profile_docbook("<book/>", "listed")
    assert result["review_code"] == "unresolved_table_layout"
    assert not result["logical_census_approved"]


def test_grouped_chieti_diagnostics_use_only_exact_sector_and_fixed_buckets():
    from white_list_archive.parsers.chieti_legacy_doc import _EXPECTED_ACTIVITY_LABELS
    row = "<row><entry>PRIVATE BUSINESS</entry><entry>PRIVATE ADDRESS</entry><entry>01234567890</entry><entry>01/11/2026</entry><entry>PRIVATE BAD DATE</entry><entry>rinnovo PRIVATE NOTE</entry></row>"
    table = "<informaltable>" + row + "</informaltable>"
    doc = ("<book><chapter><para>" + _EXPECTED_ACTIVITY_LABELS[0] + "</para>"
           "<para>" + table + "</para><para>" + table + "</para>"
           "<para>PRIVATE UNKNOWN HEADING</para><para>" + table + "</para>"
           "</chapter></book>")
    result = profile_docbook(doc, "listed")
    assert result["counts"]["six_column_data_clue"] == 3
    assert result["counts"]["exact_cell_groups_not_entities"] == 1
    assert result["sector_row_clues_not_approved"] == {"1": 2, "unresolved_heading": 1}
    assert result["same_known_sector_repeated_rows"] == 1
    assert result["sector_group_count"] == 1
    assert result["group_identifier_syntax_count"] == 1
    assert result["note_clues_not_statuses"] == {"procedure_wording": 1}
    assert result["date_clues_not_edition_dates"] == {"listing:parsed": 1, "expiry:nonblank_unparsed": 1}
    assert not result["logical_census_approved"]
    assert "PRIVATE" not in json.dumps(result)
    assert "01234567890" not in json.dumps(result)


def test_note_clues_do_not_force_overlapping_or_unmapped_outcomes():
    from white_list_archive.acquisition.chieti_archive_preflight import _note_clue
    assert _note_clue("rinnovo e cancellazione PRIVATE", "listed") == "overlapping_wording_requires_review"
    assert _note_clue("PRIVATE", "applicant") == "unmapped_wording_requires_review"
    assert _note_clue("", "applicant") == "blank"
