from pathlib import Path

import pytest

from white_list_archive.parsers.belluno_combined import PARSER_NAME, PARSER_VERSION, _parse_row, _sections, _valid_date_token
from white_list_archive.publishing.public_contract import public_record


CFG = {
    "source_key": "belluno-combined",
    "authority_key": "belluno",
    "authority_name": "Prefettura di Belluno",
    "register_key": "belluno-ordinary",
    "register_name": "White List ordinaria",
    "population_scope": "combined",
    "reference_date": "2026-09-02",
    "source_page_url": "https://example.test/belluno",
    "resource_url": "https://example.test/belluno.pdf",
    "sha256": "0" * 64,
}


def _row(
    *,
    name: str = "ALPHA SRL",
    identifier: str = "01234567890 01234567890",
    listing: str = "28/07/2022 W",
    expiry: str = "28/07/2023",
    sections: str = "I - III - V -",
    note: str = "",
    application: str = "10/06/2022",
) -> list[str]:
    return [name, "BELLUNO", identifier, listing, expiry, sections, note, application]


def _contract_record(row: list[str], ordinal: int = 1):
    record, applicant = _parse_row(row, CFG, ordinal)
    record["parser_name"] = PARSER_NAME
    record["parser_version"] = PARSER_VERSION
    assert public_record(record) == record
    return record, applicant


def test_date_token_normalises_only_explicit_valid_date() -> None:
    assert _valid_date_token("F 28/07/2022 F", required=True) == "2022-07-28"
    assert _valid_date_token("M30/07/2026", required=True) == "2026-07-30"
    assert _valid_date_token("07/04/202", required=False) == ""
    with pytest.raises(ValueError, match="Invalid Belluno date"):
        _valid_date_token("31/02/2026", required=True)
    with pytest.raises(ValueError, match="exactly one"):
        _valid_date_token("01/01/2026 02/01/2026", required=True)


def test_section_codes_are_source_backed_and_strict() -> None:
    assert _sections("I - III - V - VII -") == ["I", "III", "V", "VII"]
    with pytest.raises(ValueError, match="Unsupported Belluno section-cell"):
        _sections("I - custom")


def test_listed_row_preserves_raw_date_and_deduplicates_valid_identifier() -> None:
    record, applicant = _contract_record(_row())
    assert applicant is False
    assert record["source_status"] == "listed"
    assert record["observed_listing_date"] == "2022-07-28"
    assert record["observed_expiry_date"] == "2023-07-28"
    assert record["source_fields"]["listing_date_raw_variants"] == ["28/07/2022 W"]
    assert record["identifiers"] == ["01234567890"]
    assert record["requested_activities"] == ["Sezione I", "Sezione III", "Sezione V"]


def test_malformed_identifier_remains_raw_without_repair() -> None:
    record, _ = _contract_record(_row(identifier="012771502254"))
    assert record["identifier_field_raw"] == "012771502254"
    assert record["identifiers"] == []


def test_truncated_application_date_is_not_repaired() -> None:
    record, _ = _contract_record(_row(application="07/04/202"))
    assert record["application_date"] == ""
    assert record["observed_listing_date"] == "2022-07-28"


def test_explicit_applicant_semantics_allow_blank_or_footnote_listing_cell() -> None:
    for listing in ("", "M", "T"):
        record, applicant = _contract_record(
            _row(listing=listing, expiry="", note="IN FASE ISTRUTTORIA", application="21/10/2025")
        )
        assert applicant is True
        assert record["source_status"] == "pending"
        assert record["observed_listing_date"] == ""
        assert record["observed_expiry_date"] == ""
        assert record["application_date"] == "2025-10-21"
        assert record["primary_date_label"] == "Data presentazione istanza"


def test_applicant_classification_fails_closed_on_conflicting_dates() -> None:
    with pytest.raises(ValueError, match="unexpectedly has an expiry"):
        _parse_row(_row(listing="", expiry="01/01/2027", note="IN FASE ISTRUTTORIA"), CFG, 1)
    with pytest.raises(ValueError, match="unsupported listing-cell"):
        _parse_row(_row(listing="01/01/2026", expiry="", note="IN FASE ISTRUTTORIA"), CFG, 1)


def test_renewal_and_expired_notes_use_existing_public_status_vocabulary() -> None:
    renewal, _ = _contract_record(
        _row(note="Aggiornamento in corso: l'iscrizione resta valida anche oltre la scadenza fino all'esito definitivo")
    )
    expired, _ = _contract_record(
        _row(note="SCADUTA: iscrizione non rinnovata per mancata comunicazione dell'interesse a permanere")
    )
    assert renewal["source_status"] == "renewal_update_in_progress"
    assert expired["source_status"] == "expired_observed"


def test_unknown_nonblank_legal_note_is_not_guessed() -> None:
    with pytest.raises(ValueError, match="Unsupported Belluno listed-row note"):
        _parse_row(_row(note="nuovo esito non classificato"), CFG, 1)
