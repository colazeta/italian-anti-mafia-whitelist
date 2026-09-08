import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public-site"


def _data():
    return json.loads((PUBLIC / "data" / "site.json").read_text(encoding="utf-8"))


def _baseline():
    return json.loads((ROOT / "docs/publication/public-portal-baseline-2026-09-08.json").read_text())


def test_public_portal_has_explicit_public_contract_v3():
    data = _data()
    assert data["meta"]["classification"] == "PUBLIC EXPERIMENTAL VIEW"
    assert data["meta"]["public_contract_version"] == 3
    assert data["publication"]["principle"] == "public-first, audit-transparent"
    assert "disclaimer" in data["meta"]


def test_cosenza_source_statuses_still_reconcile_as_frozen_baseline():
    data = _baseline()
    assert sum(data["cosenza"]["status_counts"].values()) == data["cosenza"]["source_rows"] == 1334


def test_address_quality_totals_reconcile_but_geography_is_optional():
    data = _baseline()
    q = data["quality"]
    assert q["anncsu_candidates"] + q["not_found"] == q["address_population"]
    assert q["auto_accepted"] == 0
    policy = data["publication"]["geography_policy"].casefold()
    assert "non attende" in policy
    assert "opzionale" in policy
    assert "geolocalizzazione" in data["method"]["publication_rule"].casefold()


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


def test_public_contract_allows_national_registry_dimensions_and_source_attributes():
    data = _data()
    fields = set(data["publication"]["registry_fields"])
    required = {
        "name",
        "authority_name",
        "register_name",
        "reference_date",
        "registered_office",
        "secondary_office",
        "identifiers",
        "requested_activities",
        "source_status",
        "primary_date_label",
        "primary_date",
        "application_date",
        "observed_listing_date",
        "decision_date",
        "registration_date",
        "observed_expiry_date",
        "source_page_url",
        "resource_url",
    }
    assert required <= fields


def test_public_frontend_has_prefecture_directory_and_multi_registry_filters():
    html = (PUBLIC / "index.html").read_text(encoding="utf-8")
    js = (PUBLIC / "app.js").read_text(encoding="utf-8")
    assert 'data-view="prefectures"' in html
    assert 'id="view-prefectures"' in html
    assert "reg-authority" in js
    assert "reg-register" in js
    assert "pref-status" in js
    assert "last_project_check" in js
    assert "last_source_update" in js


def test_first_multi_prefecture_pilot_is_declared_in_public_config():
    data = _baseline()
    assert data["national"]["published_entity_registers"] == [
        "Cosenza",
        "Parma",
        "Pistoia",
        "Bologna",
    ]


def test_public_static_payload_excludes_internal_metrics():
    assert set(_data()) == {"meta", "publication", "history", "audit"}
    js = (PUBLIC / "app.js").read_text()
    for token in ("D.quality", "D.national", "canonical population", "candidate precision", "schema_fingerprint", "renderCoverage", "renderOverview"):
        assert token not in js
