from __future__ import annotations

import csv
import json
import time

from white_list_archive.mcp_public.store import REGISTRY_FIELDS, SnapshotStore


def _row(**changes):
    base = {field: "" for field in REGISTRY_FIELDS}
    base.update(
        {
            "record_locator": "fixture:1",
            "authority_name": "Prefettura di Milano",
            "register_name": "White List provinciale",
            "reference_date": "2026-09-01",
            "name": "Alpha Costruzioni Srl",
            "identifiers": "12345678901",
            "source_status": "pending",
            "application_date": "2026-01-15",
            "source_page_url": "https://example.test/milano",
            "resource_url": "https://example.test/milano/list",
            "capture_sha256": "a" * 64,
        }
    )
    base.update(changes)
    return base


def _fixture_store(tmp_path):
    store = SnapshotStore(cache_dir=tmp_path, refresh_seconds=3600)
    prefectures = {
        "meta": {"authority_count": 2, "published_count": 2, "mapped_count": 2},
        "prefectures": [
            {
                "authority_key": "milano",
                "jurisdiction_name": "Milano",
                "mapping_status": "published",
                "mapped": True,
                "published": True,
                "published_registers": ["White List provinciale"],
            },
            {
                "authority_key": "catanzaro",
                "jurisdiction_name": "Catanzaro",
                "mapping_status": "published",
                "mapped": True,
                "published": True,
                "published_registers": ["White List provinciale"],
            },
        ],
    }
    rows = [
        _row(),
        _row(
            record_locator="fixture:2",
            name="Beta Servizi Spa",
            identifiers="10987654321",
            source_status="renewal_update_in_progress",
            application_date="",
            observed_expiry_date="2026-12-31",
        ),
        _row(
            record_locator="fixture:3",
            authority_name="Prefettura di Catanzaro",
            name="Gamma Scavi Srl",
            identifiers="11111111111",
            source_status="listed",
            application_date="",
            observed_listing_date="2026-03-01",
            source_page_url="https://example.test/catanzaro",
            resource_url="https://example.test/catanzaro/list",
        ),
    ]
    csv_path = tmp_path / "registry.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REGISTRY_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    store._build_database(csv_path, prefectures, store.db_path)
    store.prefectures_path.write_text(json.dumps(prefectures), encoding="utf-8")
    store.history_path.write_text(
        json.dumps({"version": 1, "editions": [], "checks": [], "comparisons": []}),
        encoding="utf-8",
    )
    store.manifest_path.write_text(
        json.dumps({"release_tag": "public-data-fixture"}),
        encoding="utf-8",
    )
    store._release_tag = "public-data-fixture"
    store._last_checked = time.monotonic()
    return store


def test_identifier_search_and_authority_resolution(tmp_path):
    store = _fixture_store(tmp_path)
    result = store.search_registry("123 456 789 01", authority="milano")
    assert result["total_matches"] == 1
    assert result["match_basis"] == "identifier"
    assert result["results"][0]["name"] == "Alpha Costruzioni Srl"
    assert result["results"][0]["authority_key"] == "milano"


def test_prefecture_aggregates_are_observation_counts(tmp_path):
    store = _fixture_store(tmp_path)
    result = store.get_prefecture("Milano")
    assert result["archive"]["record_count"] == 2
    assert result["archive"]["status_counts"] == {
        "pending": 1,
        "renewal_update_in_progress": 1,
    }


def test_date_distributions_keep_unknown_dates_explicit(tmp_path):
    store = _fixture_store(tmp_path)
    pending = store.date_distribution(
        "application",
        authority="Milano",
        status="pending",
        bucket="month",
    )
    assert pending["distribution"] == [{"bucket": "2026-01", "count": 1}]
    assert pending["unknown_or_unusable_dates"] == 0

    updates = store.date_distribution(
        "expiry",
        authority="Milano",
        status="renewal_update_in_progress",
        bucket="year",
    )
    assert updates["distribution"] == [{"bucket": "2026", "count": 1}]


def test_compare_prefectures_does_not_deduplicate_companies(tmp_path):
    store = _fixture_store(tmp_path)
    result = store.compare_prefectures(["Milano", "Catanzaro"])
    assert [item["record_count"] for item in result["comparisons"]] == [2, 1]
    assert result["denominator"] == "public source observations in the selected reviewed snapshot"
