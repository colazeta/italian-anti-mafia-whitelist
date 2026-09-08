from white_list_archive.publishing.public_registry import build_registry


def _record():
    return {
        "row_ordinal": 7,
        "operator_name_raw": "IMPRESA ESEMPIO SRL",
        "registered_office_raw": "COSENZA Via Roma 1",
        "secondary_office_raw": "RENDE Via Verdi 2",
        "identifier_field_raw": "01234567890",
        "identifiers_json": '[{"kind":"tax_or_vat","raw_value":"01234567890"}]',
        "requested_activities_raw": "TRASPORTO",
        "requested_activities_json": '["TRASPORTO"]',
        "application_date_field_raw": "01/07/2026",
        "application_dates_json": '[{"date":"2026-07-01","raw_value":"01/07/2026"}]',
        "source_status": "listed",
        "outcome_raw": "ISCRITTA DAL 03/08/2026",
        "outcome_json": '{"status":"listed"}',
        "observed_listing_date": "2026-08-03",
        "observed_expiry_date": "2027-08-03",
    }


def test_public_registry_preserves_source_attributes_and_provenance():
    result = build_registry(
        [_record()],
        reference_date="2026-08-03",
        authority_key="cosenza",
        authority_name="Prefettura di Cosenza",
        source_page_url="https://example.test/page",
        resource_url="https://example.test/list.pdf",
        capture_sha256="a" * 64,
    )
    assert result["meta"]["contract_version"] == 2
    assert result["meta"]["record_count"] == 1
    assert result["meta"]["status_counts"] == {"listed": 1}
    row = result["records"][0]
    assert row["record_locator"] == "cosenza:2026-08-03:7"
    assert row["name"] == "IMPRESA ESEMPIO SRL"
    assert row["registered_office"] == "COSENZA Via Roma 1"
    assert row["secondary_office"] == "RENDE Via Verdi 2"
    assert row["identifier_field_raw"] == "01234567890"
    assert row["identifiers"][0]["raw_value"] == "01234567890"
    assert row["requested_activities"] == ["TRASPORTO"]
    assert row["application_dates"][0]["date"] == "2026-07-01"
    assert row["source_status"] == "listed"
    assert row["observed_listing_date"] == "2026-08-03"
    assert row["observed_expiry_date"] == "2027-08-03"
    assert row["source_page_url"] == "https://example.test/page"
    assert row["resource_url"] == "https://example.test/list.pdf"


def test_public_registry_does_not_invent_canonical_entity_identity():
    result = build_registry(
        [_record()],
        reference_date="2026-08-03",
        authority_key="cosenza",
        authority_name="Prefettura di Cosenza",
        source_page_url="https://example.test/page",
        resource_url="https://example.test/list.pdf",
        capture_sha256="a" * 64,
    )
    row = result["records"][0]
    assert "legal_entity_id" not in row
    assert "address_id" not in row
    assert "review_notes" not in row
    assert "source_occurrences" not in row
