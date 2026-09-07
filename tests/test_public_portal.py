import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public-site"


def _data():
    return json.loads((PUBLIC / "data" / "site.json").read_text(encoding="utf-8"))


def test_public_portal_has_explicit_public_contract():
    data = _data()
    assert data["meta"]["classification"] == "PUBLIC EXPERIMENTAL VIEW"
    assert data["meta"]["public_contract_version"] == 1
    assert "disclaimer" in data["meta"]


def test_cosenza_source_statuses_reconcile():
    data = _data()
    assert sum(data["cosenza"]["status_counts"].values()) == data["cosenza"]["source_rows"]


def test_address_quality_totals_reconcile():
    q = _data()["quality"]
    assert q["anncsu_candidates"] + q["not_found"] == q["address_population"]
    assert q["auto_accepted"] == 0


def test_public_site_does_not_embed_internal_review_or_identifier_fields():
    text = (PUBLIC / "data" / "site.json").read_text(encoding="utf-8").casefold()
    forbidden = (
        "legal_entity_id",
        "entity_identifier",
        "tax_identifier",
        "vat_number",
        "review_notes",
        "reviewed_at",
        "source_occurrences",
        "address_id",
    )
    for token in forbidden:
        assert token not in text
