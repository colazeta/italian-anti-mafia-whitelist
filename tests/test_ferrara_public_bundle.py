from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch
from white_list_archive.publishing.public_national_registry import (
    FERRARA_RECONSTRUCTION_PARSER,
    _adapt_ferrara_public_fields,
    _bundle_digest,
)


MEMBER_HASHES = {
    "A": "4fdf292b1538892c7b5ff79d3c0c14e0ed3b5830effb791316b0fddb8c90ae01",
    "B": "97d9af0d587af0b7d93d31df33bd612440bf5be5b48b57872d436e2afeb164ec",
    "C": "99f519101dccff84dddd9753f0d6fa27170c33b1982858afe9fdf9ebbc63c57e",
    "D": "07c27b38e48a879aa0d1efff4710bf7dbbf1bb323e59f62eb0b0b796a75a46d8",
    "E": "9cea950d37f653d0356edb9a46a7f43665a382e771c969bc93f7027f95fecf9e",
    "F": "ac7dd77f1c4633c27a62c0ad7e074f507a10b091a327c2fc1072cfb52fd45664",
    "G": "0657c7e0f0b9fb8ad7f0b341682716d695132e61131adc92407627a5cae82bae",
}


def test_ferrara_bundle_identity_is_order_stable_and_content_addressed():
    expected = "bundle:f3d9093a8859e082ed304b1342ab7a3ae687f7735da04b3d363bbe7440543283"
    assert _bundle_digest(MEMBER_HASHES) == expected
    assert _bundle_digest(dict(reversed(list(MEMBER_HASHES.items())))) == expected
    changed = dict(MEMBER_HASHES)
    changed["G"] = "0" * 64
    assert _bundle_digest(changed) != expected


def _batch(fields):
    return ParsedBatch(records=[{"source_fields": fields}], diagnostics={"public_records": 1})


def test_ferrara_public_adapter_closes_ordinary_fields():
    batch = _adapt_ferrara_public_fields(
        _batch({"listing_date_raw": "01/02/2026", "expiry_date_raw": "01/02/2027", "notes": ["RINNOVO IN CORSO"], "physical_locators": ["p1:r2", "p2:r1"]}),
        "ferrara-provincial-listed",
    )
    assert batch.records[0]["source_fields"]["physical_locators"] == ["p1:r2", "p2:r1"]
    assert batch.records[0]["source_fields"]["listing_date_raw_variants"] == ["01/02/2026"]


def test_ferrara_public_adapter_closes_shared_applicant_fields():
    batch = _adapt_ferrara_public_fields(
        _batch({"application_date_raw": "03/04/2026", "requested_activities_source": "demolizione edifici", "physical_locators": ["p1:r4"], "shared_publication_no_duplicate_ingest": True, "logical_series": ["ferrara-provincial-applicants", "ferrara-reconstruction-applicants"]}),
        "ferrara-provincial-applicants",
    )
    assert "logical_series" not in batch.records[0]["source_fields"]
    assert batch.records[0]["source_fields"]["application_date_raw_variants"] == ["03/04/2026"]


def test_ferrara_public_adapter_preserves_reconstruction_provenance():
    batch = _adapt_ferrara_public_fields(
        _batch({"listing_date_raw": "01/01/2026", "expiry_date_raw": "01/01/2027", "sectors": ["B", "C"], "name_variants": ["Example S.r.l."], "office_variants": ["Ferrara"], "notes": [], "physical_locators": ["B:p1:t1:r2", "C:p1:t1:r2"], "physical_sector_observations": 2}),
        FERRARA_RECONSTRUCTION_PARSER,
    )
    assert batch.records[0]["source_fields"]["sections"] == ["B", "C"]
    assert batch.records[0]["source_fields"]["registered_office_variants"] == ["Ferrara"]
