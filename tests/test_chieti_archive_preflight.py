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
