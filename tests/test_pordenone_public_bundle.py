from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch
from white_list_archive.publishing.public_national_registry import (
    PORDENONE_LISTED_PARSER,
    _adapt_pordenone_public_fields,
    _bundle_digest,
)


MEMBER_HASHES = {
    "I": "f4e6374e5e03daa25daedd49ada730ae39c6b77437e763e3c0308aa0a0c627de",
    "II": "62d63a080b3025e2ee2f37c3af1d486f12095be8f83e73cae611e2ca56bf84d5",
    "III": "2204fe651b733e32fe13f001c97fd2c6a93ccd9a846cc9f4ddd40d4f471e6ce9",
    "IV": "55a1edd7bcc52de101536c42091e14e040892cf1122462c36b37a861c48eeb62",
    "V": "4fcd95954d20ba19ffcfb11e64a911a637056ba2fd794d47c5d3f19171f77803",
    "VI": "62c39abfc260ecacf59b0201867263499643fe5dc36c95500e380fa53deb87aa",
    "VII": "35c5ef5ddb218e50d1f5a56007f2c1886ac73b6a91c5a13fb37e4b7f4952d2c8",
    "VIII": "cac3354a388d87b3f7ee1fef965f7b9968d2fea4dfcbafa776fc175bee5d96b3",
    "IX": "a3b7c0b749be947692cb6ebb031e21e6c2e61913f34c1ad9f4741f3a7b9e96fa",
    "X": "af639b5c55ff31893bfd3906876e0c60e1e6614065efae1e5c7871ac62290c0f",
}


def _batch(fields):
    return ParsedBatch(records=[{"source_fields": fields}], diagnostics={"public_records": 1})


def test_pordenone_listed_bundle_identity_is_content_addressed_and_order_stable():
    expected = "bundle:ce7759de3f7bc81c9f79298c8ad427a387446e8d61ff2d9f1c78cb8ad258e4a3"
    assert _bundle_digest(MEMBER_HASHES) == expected
    assert _bundle_digest(dict(reversed(list(MEMBER_HASHES.items())))) == expected
    changed = dict(MEMBER_HASHES)
    changed["X"] = "0" * 64
    assert _bundle_digest(changed) != expected


def test_pordenone_public_adapter_preserves_listed_sector_provenance():
    batch = _adapt_pordenone_public_fields(
        _batch({
            "sections": ["I", "VI"],
            "physical_locators": ["I:p1:r2", "VI:p1:r3"],
            "physical_sector_observations": 2,
            "name_variants": ["Example S.r.l."],
            "office_variants": ["Pordenone"],
            "secondary_office_variants": [],
            "listing_date_raw": "01/02/2026",
            "expiry_date_raw": "01/02/2027",
            "notes": [],
        }),
        PORDENONE_LISTED_PARSER,
    )
    fields = batch.records[0]["source_fields"]
    assert fields["sections"] == ["I", "VI"]
    assert fields["physical_locators"] == ["I:p1:r2", "VI:p1:r3"]
    assert fields["listing_date_raw_variants"] == ["01/02/2026"]


def test_pordenone_public_adapter_drops_non_public_review_only_applicant_fields():
    batch = _adapt_pordenone_public_fields(
        _batch({
            "application_date_raw": "07/01/2026",
            "requested_activities_source": "Sezioni I, VI",
            "physical_locators": ["XI:p3:r2"],
            "source_row_raw": ["MGDSCAVI SRL", "", "", "01975030931", "Sezioni I, VI", "07/01/2026", "IN ISTRUTTORIA"],
            "source_name_missing": False,
        }),
        "pordenone-provincial-applicants",
    )
    fields = batch.records[0]["source_fields"]
    assert fields["physical_locators"] == ["XI:p3:r2"]
    assert fields["application_date_raw_variants"] == ["07/01/2026"]
    assert "source_row_raw" not in fields
    assert "source_name_missing" not in fields
