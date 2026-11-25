from hashlib import sha256
import json
from white_list_archive.acquisition.cagliari_archive_preflight import audit, profile_pages, PINS


class Page:
    def extract_text(self):
        return "ELENCO DELLE IMPRESE RICHIEDENTI 15/11/2026 DATA ISCRIZIONE DATA SCADENZA"

    def extract_tables(self):
        return [[["1", "Sez. 1", "PRIVATE NAME", "PRIVATE ADDRESS", "",
                  "12345678901", "01/11/2026", "01/11/2027", ""],
                 ["2", "Sez. 2", "PRIVATE NAME", "PRIVATE ADDRESS", "",
                  "12345678901", "01/11/2026", "01/11/2027", ""],
                 ["1", "PRIVATE APPLICANT", "PRIVATE ADDRESS", "12345678901",
                  "I", "31/11/2026", "In istruttoria"],
                 ["other"], [""]]]


def test_population_shape_conflict_preserved_without_record_approval():
    result = profile_pages([Page()], "2026-11-15")
    c = result["counts"]
    assert c["physical_rows"] == 5
    assert c["listed_shaped_rows"] == 2 and c["applicant_shaped_rows"] == 1
    assert c["applicant_rows_invalid_date"] == 1
    assert c["applicant_title_clue_pages"] == 1
    assert c["filename_date_marker_pages"] == 1
    assert result["listed_shape_groups_not_entities"] == 1
    assert not result["logical_record_census_approved"]
    assert "PRIVATE" not in json.dumps(result)
    assert "12345678901" not in json.dumps(result)


def test_exact_pairs_fail_closed_and_redact():
    assert len(PINS) == 4 and len({p[2] for p in PINS}) == 4
    raw = b"synthetic"
    digest = sha256(raw).hexdigest()

    class Store:
        def read_digest_verified(self, _):
            return raw

    result = audit(Store(), pins=(("2026-11-08", "listed", digest, len(raw)),
                                ("2026-11-08", "applicant", "0" * 64, len(raw))),
                   scanner=lambda *_: profile_pages([Page()], "2026-11-15"))
    assert result["originals_sha_verified"] == 1
    assert result["physical_profiles_completed"] == 1
    assert not result["public_release_eligible"]
    assert not result["privacy_approved"]
    assert "PRIVATE" not in json.dumps(result)


def test_residuals_and_notes_remain_unapproved_and_reconciled():
    class ResidualPage(Page):
        def extract_tables(self):
            return [super().extract_tables()[0] + [
                ["Ragione sociale", "Codice fiscale", "PRIVATE HEADING"],
                ["PRIVATE", "other"],
                ["3", "Sez. 1", "PRIVATE NAME", "PRIVATE ADDRESS", "",
                 "12345678901", "01/11/2026", "01/11/2027", ""],
                ["4", "Sez. 3", "PRIVATE NAME", "PRIVATE ADDRESS", "",
                 "12345678901", "01/11/2026", "01/11/2027", "AGGIORNAMENTO IN CORSO"],
                ["5", "Sez. 4", "PRIVATE NAME", "PRIVATE ADDRESS", "",
                 "12345678901", "01/11/2026", "01/11/2027", "PRIVATE NOTE"],
            ]]
    result = profile_pages([ResidualPage()], "2026-11-15")
    assert result["counts"]["unclassified_rows"] == 3
    assert result["residual_shape_clues_not_classifications"] == {
        "single_nonblank_cell": 1, "multiple_known_header_labels": 1, "other_multicell": 1,
    }
    assert result["listed_note_clues_not_statuses"] == {
        "blank_note": 3, "explicit_update_in_progress": 1, "other_note_requires_review": 1,
    }
    assert result["counts"]["repeated_same_section_rows"] == 1
    assert not result["logical_record_census_approved"]
    assert "PRIVATE" not in json.dumps(result)
    assert "12345678901" not in json.dumps(result)



def test_candidate_group_notes_and_cross_population_evidence_are_aggregate():
    result = profile_pages([Page()], "2026-11-15")
    assert result["listed_group_note_clues_not_statuses"] == {"blank_note": 1}
    assert result["applicant_shape_evidence_not_classifications"] == {
        "legacy_outcome_invalid_date": 1, "request_tokens_known_roman": 1,
    }
    assert result["applicant_repeated_ordinal_rows"] == 0
    assert not result["logical_record_census_approved"]
    assert "PRIVATE" not in json.dumps(result)
