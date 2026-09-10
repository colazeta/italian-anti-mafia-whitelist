import pytest

from white_list_archive.parsers.ascoli_piceno_labels import (
    _listed_status,
    _parse_applicant_block,
    _parse_listed_block,
    _sections,
    _source_date,
)
from white_list_archive.publishing.public_contract import public_record

LISTED_CFG = {
    "source_key": "ascoli-piceno-listed",
    "authority_key": "ascoli-piceno",
    "authority_name": "Prefettura di Ascoli Piceno",
    "register_key": "ascoli-piceno-ordinary",
    "register_name": "White List ordinaria",
    "population_scope": "listed",
    "reference_date": "2026-08-11",
    "source_page_url": "https://example.test/ascoli",
    "resource_url": "https://example.test/listed.pdf",
    "sha256": "0" * 64,
}
APPLICANT_CFG = {**LISTED_CFG, "source_key": "ascoli-piceno-applicants", "population_scope": "applicant", "resource_url": "https://example.test/applicants.pdf"}


def test_source_date_is_exact_and_calendar_valid():
    assert _source_date("11/08/2026", field="test") == "2026-08-11"
    with pytest.raises(ValueError):
        _source_date("11-08-2026", field="test")
    with pytest.raises(ValueError):
        _source_date("31/02/2026", field="test")


def test_listed_status_is_source_explicit_and_fail_closed():
    assert _listed_status("Iscritto", ordinal=1) == "listed"
    assert _listed_status("In aggiornamento", ordinal=2) == "renewal_update_in_progress"
    with pytest.raises(RuntimeError, match="unreviewed source status"):
        _listed_status("Nuovo stato", ordinal=3)


def test_sections_require_source_backed_codes():
    sections, raw = _sections("SEZ I° attività uno SEZ III° attività tre", source_key="x", ordinal=1)
    assert sections == ["Sezione I", "Sezione III"]
    assert "attività uno" in raw
    with pytest.raises(RuntimeError, match="no source-backed"):
        _sections("attività senza sezione", source_key="x", ordinal=2)


def test_listed_block_preserves_explicit_dates_and_status_without_inference():
    block = """Ragione Sociale: ALPHA SRL CODICE FISCALE: 01234567890
Indirizzo: VIA ROMA 1 63100 ASCOLI PICENO AP
DATA PROVVEDIMENTO - 01/07/2025 - 01/07/2026 SCADENZA:
STATO: In aggiornamento
Lista attività: SEZ I° TRASPORTO MATERIALI SEZ V° NOLI A CALDO
"""
    record = _parse_listed_block(block, LISTED_CFG, 1)
    record["parser_name"] = "ascoli_piceno_listed"
    record["parser_version"] = "1"
    assert public_record(record) == record
    assert record["source_status"] == "renewal_update_in_progress"
    assert record["decision_date"] == "2025-07-01"
    assert record["observed_expiry_date"] == "2026-07-01"
    assert record["observed_listing_date"] == ""
    assert record["primary_date"] == "2025-07-01"
    assert record["identifiers"] == ["01234567890"]
    assert record["requested_activities"] == ["Sezione I", "Sezione V"]


def test_applicant_block_maps_only_explicit_istruttoria_to_pending():
    block = """Azienda: BETA SRL
Sede legale: VIA MAZZINI 2 63100 ASCOLI PICENO AP
Codice fiscale: 10987654321
Data Presentazione Istanza: 10/06/2026
ESITO: istruttoria
ESITO note aggiuntive:
Lista attività: SEZ II° CALCESTRUZZO
"""
    record = _parse_applicant_block(block, APPLICANT_CFG, 1)
    record["parser_name"] = "ascoli_piceno_applicants"
    record["parser_version"] = "1"
    assert public_record(record) == record
    assert record["source_status"] == "pending"
    assert record["application_date"] == "2026-06-10"
    assert record["primary_date"] == "2026-06-10"
    assert record["requested_activities"] == ["Sezione II"]

    with pytest.raises(RuntimeError, match="unreviewed applicant outcome"):
        _parse_applicant_block(block.replace("ESITO: istruttoria", "ESITO: altro"), APPLICANT_CFG, 2)
