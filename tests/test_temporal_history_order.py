from collections import Counter
from copy import deepcopy

from white_list_archive.publishing.public_history import compare_releases, validate_history


def registry(reference_date: str, sha: str, checked_at: str, statuses=("pending", "listed")) -> dict:
    rows = []
    for i, status in enumerate(statuses, 1):
        rows.append({
            "record_locator": f"fixture:{sha}:{i}", "source_key": "mutable-fixture",
            "authority_key": "fixture", "authority_name": "Fixture Prefecture",
            "register_key": "fixture-register", "register_name": "Fixture register",
            "population_scope": "listed_and_applicant", "reference_date": reference_date,
            "name": f"Synthetic company {i}", "identifiers": [f"{i:011d}"],
            "identifier_field_raw": f"{i:011d}", "requested_activities": ["fixture"],
            "source_status": status, "source_row_ordinal": i,
            "source_page_url": "https://example.test/page",
            "resource_url": "https://example.test/document", "capture_sha256": sha,
            "parser_name": "fixture_parser", "parser_version": "1",
        })
    return {
        "records": rows,
        "meta": {
            "record_count": len(rows), "source_count": 1, "authority_count": 1, "register_count": 1,
            "authority_counts": {"fixture": len(rows)}, "register_counts": {"fixture-register": len(rows)},
            "status_counts": dict(Counter(statuses)),
            "sources": [{"source_key": "mutable-fixture", "reference_date": reference_date, "sha256": sha, "document_checked_at": checked_at}],
        },
    }


def test_equal_source_date_distinct_payloads_are_retained_and_capture_ordered():
    before = registry("2026-09-22", "a" * 64, "2026-09-22T08:00:00Z")
    after = registry("2026-09-22", "b" * 64, "2026-09-22T09:00:00Z", ("listed", "listed", "pending"))
    history = compare_releases(before, after)
    validate_history(history)
    assert len(history["editions"]) == 2
    assert len(history["comparisons"]) == 1
    comparison = history["comparisons"][0]
    assert comparison["basis"] == "capture_ordered_identifier_observations_v1"
    assert (comparison["added"], comparison["common"]) == (1, 2)


def test_unknown_source_dates_use_observation_order_without_inventing_source_date():
    before = registry("", "c" * 64, "2026-09-22T08:00:00Z")
    after = registry("", "d" * 64, "2026-09-22T09:00:00Z")
    history = compare_releases(before, after)
    assert all(edition["reference_date"] is None for edition in history["editions"])
    assert history["comparisons"][0]["basis"] == "capture_ordered_identifier_observations_v1"


def test_equal_capture_time_distinct_payloads_never_get_invented_order():
    before = registry("2026-09-22", "e" * 64, "2026-09-22T08:00:00Z")
    after = registry("2026-09-22", "f" * 64, "2026-09-22T08:00:00Z")
    history = compare_releases(before, after)
    assert len(history["editions"]) == 2
    assert history["comparisons"] == []


def test_distinct_known_source_dates_keep_source_chronology_basis():
    before = registry("2026-09-21", "1" * 64, "2026-09-22T09:00:00Z")
    after = registry("2026-09-22", "2" * 64, "2026-09-22T08:00:00Z")
    history = compare_releases(before, after)
    assert history["comparisons"][0]["basis"] == "exact_identifier_observations_v1"
