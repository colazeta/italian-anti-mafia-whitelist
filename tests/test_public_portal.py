import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public-site"


def _data():
    return json.loads((PUBLIC / "data" / "site.json").read_text(encoding="utf-8"))


def test_public_portal_has_explicit_public_contract():
    data = _data()
    assert data["meta"]["classification"] == "PUBLIC EXPERIMENTAL VIEW"
    assert data["meta"]["public_contract_version"] == 2
    assert "disclaimer" in data["meta"]


def test_cosenza_source_statuses_reconcile():
    data = _data()
    assert sum(data["cosenza"]["status_counts"].values()) == data["cosenza"]["source_rows"]


def test_address_quality_totals_reconcile():
    q = _data()["quality"]
    assert q["anncsu_candidates"] + q["not_found"] == q["address_population"]
    assert q["auto_accepted"] == 0


def test_public_site_static_config_does_not_embed_internal_review_ids():
    text = (PUBLIC / "data" / "site.json").read_text(encoding="utf-8").casefold()
    forbidden = (
        "legal_entity_id",
        "address_id",
        "review_notes",
        "reviewed_at",
        "source_occurrences",
    )
    for token in forbidden:
        assert token not in text


def test_public_contract_explicitly_allows_source_registry_attributes():
    data = _data()
    fields = set(data["publication"]["registry_fields"])
    assert "name" in fields
    assert "registered_office" in fields
    assert "secondary_office" in fields
    assert "identifiers" in fields
    assert "requested_activities" in fields
    assert "application_dates" in fields
    assert "source_status" in fields
    assert "observed_listing_date" in fields
    assert "observed_expiry_date" in fields
