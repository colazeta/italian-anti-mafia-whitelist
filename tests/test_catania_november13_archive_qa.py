"""Regression: a verified Catania source candidate is never an approved edition."""
from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

from white_list_archive.acquisition.catania_november13_archive_qa import (
    PINS, audit_primary_archive,
)


class Archive:
    def __init__(self, payloads):
        self.payloads = payloads
        self.reads = []

    def read_digest_verified(self, digest):
        self.reads.append(digest)
        return self.payloads[digest]


def _fixture_pins():
    raw = [b"listed synthetic XLSX placeholder", b"applicant synthetic XLSX placeholder"]
    pins = tuple((key, population, hashlib.sha256(blob).hexdigest())
                 for (key, population, _), blob in zip(PINS, raw))
    return pins, dict(zip((p[2] for p in pins), raw))


def _parser(path, cfg):
    assert path.read_bytes()
    assert cfg["reference_date"] == ""
    assert cfg["source_page_url"] == cfg["resource_url"] == ""
    assert cfg["parser"].startswith("catania_candidate_")
    return SimpleNamespace(
        records=[
            {"source_status": "listed" if cfg["population_scope"] == "listed"
             else "pending", "reference_date": ""}
        ],
        diagnostics={
            "publication_approved": False,
            "source_date_assigned": False,
            "source_rows_represented": 1,
            "candidate_quality_flags": ["sector_anomalies"],
            "counts": {"sector_anomalies": 1},
        },
    )


def test_exact_two_source_inputs_are_qualified_without_edition_or_publication():
    assert len(PINS) == 2 and len({p[2] for p in PINS}) == 2
    pins, payloads = _fixture_pins()
    store = Archive(payloads)
    result = audit_primary_archive(store, pins=pins, parser=_parser)
    assert store.reads == [p[2] for p in pins]
    assert result["primary_originals_verified"] == 2
    assert result["provisional_extractions"] == 2
    assert [row["source_rows_for_review"] for row in result["results"]] == [1, 1]
    assert result["results"][0]["source_status_counts"] == {"listed": 1}
    assert result["results"][1]["source_status_counts"] == {"pending": 1}
    assert result["capture_catalogue_verified_by_this_probe"] is False
    assert result["date_attribution_or_edition_approved"] is False
    assert result["postgresql_writes"] == result["public_promotions"] == 0


def test_wrong_or_inaccessible_bytes_are_unknown_and_not_parsed():
    pins, payloads = _fixture_pins()
    store = Archive({pins[0][2]: b"tampered", pins[1][2]: payloads[pins[1][2]]})
    result = audit_primary_archive(store, pins=pins, parser=_parser)
    assert result["primary_originals_verified"] == 1
    assert result["provisional_extractions"] == 1
    assert result["results"][0]["primary_bytes"] == "unknown"
    assert result["results"][0]["source_rows_for_review"] is None


def test_parser_error_is_redacted_but_verified_original_remains_verified():
    pins, payloads = _fixture_pins()

    def rejecting_parser(path, cfg):
        raise RuntimeError("private-source-name secret token /bucket/dump.xlsx")

    result = audit_primary_archive(Archive(payloads), pins=pins,
                                   parser=rejecting_parser)
    assert result["primary_originals_verified"] == 2
    assert result["provisional_extractions"] == 0
    assert all(r["candidate_schema"] == "layout_or_parser_review_required"
               for r in result["results"])
    safe = json.dumps(result)
    assert "private-source-name" not in safe
    assert "secret token" not in safe and "/bucket/" not in safe


def test_provisional_parser_cannot_assume_an_edition_date_or_approval():
    pins, payloads = _fixture_pins()

    def unauthorised_parser(path, cfg):
        result = _parser(path, cfg)
        result.diagnostics["publication_approved"] = True
        result.records[0]["reference_date"] = "2026-11-13"
        return result

    result = audit_primary_archive(Archive(payloads), pins=pins,
                                   parser=unauthorised_parser)
    assert result["primary_originals_verified"] == 2
    assert result["provisional_extractions"] == 0
    assert all(r["source_rows_for_review"] is None for r in result["results"])


def test_duplicate_source_pins_fail_before_access_to_the_store():
    pins, payloads = _fixture_pins()
    wrong = (pins[0], ("catania-applicants", "applicant", pins[0][2]))
    try:
        audit_primary_archive(Archive(payloads), pins=wrong, parser=_parser)
    except ValueError:
        pass
    else:
        raise AssertionError("Distinct official originals are required")


def test_formula_counter_is_a_closed_informational_metric_not_a_parser_failure():
    """Provisional listed extracts may report source_expiry_formulas without a flag."""
    pins, payloads = _fixture_pins()

    def parser_with_formulas(path, cfg):
        batch = _parser(path, cfg)
        if cfg["population_scope"] == "listed":
            batch.diagnostics["counts"]["source_expiry_formulas"] = 2
        return batch

    result = audit_primary_archive(Archive(payloads), pins=pins,
                                   parser=parser_with_formulas)
    assert result["primary_originals_verified"] == 2
    assert result["provisional_extractions"] == 2
    assert result["results"][0]["candidate_schema"] == "provisional_extraction_for_review"
    assert result["results"][0]["candidate_quality_counts"]["source_expiry_formulas"] == 2
    assert result["date_attribution_or_edition_approved"] is False
    assert result["postgresql_writes"] == result["public_promotions"] == 0


def test_undeclared_counter_still_quarantines_without_leaking_raw_information():
    pins, payloads = _fixture_pins()

    def parser_with_unreviewed_counter(path, cfg):
        batch = _parser(path, cfg)
        batch.diagnostics["counts"]["private-unknown-counter"] = 1
        return batch

    result = audit_primary_archive(Archive(payloads), pins=pins,
                                   parser=parser_with_unreviewed_counter)
    assert result["primary_originals_verified"] == 2
    assert result["provisional_extractions"] == 0
    assert all(row["candidate_schema"] == "layout_or_parser_review_required"
               for row in result["results"])
    assert "private-unknown-counter" not in json.dumps(result)


def test_closed_parser_layout_category_is_reported_without_source_text():
    pins, payloads = _fixture_pins()

    def rejecting_parser(path, cfg):
        raise ValueError("Candidate source contains an incomplete data-like row")

    result = audit_primary_archive(Archive(payloads), pins=pins, parser=rejecting_parser)
    assert result["primary_originals_verified"] == 2
    assert result["provisional_extractions"] == 0
    assert all(row["candidate_blocker_class"] == "incomplete_data_like_row"
               for row in result["results"])
    assert all(row["source_rows_for_review"] is None for row in result["results"])
    assert result["postgresql_writes"] == result["public_promotions"] == 0


def test_unrecognised_parser_exception_never_discloses_error_text():
    pins, payloads = _fixture_pins()

    def secret_exception(path, cfg):
        raise ValueError("private account: secret identifier from worksheet")

    result = audit_primary_archive(Archive(payloads), pins=pins, parser=secret_exception)
    assert all(row["candidate_blocker_class"] == "other_review_required"
               for row in result["results"])
    assert "private account" not in json.dumps(result)
    assert "secret identifier" not in json.dumps(result)


def test_unknown_bytes_have_no_layout_classification():
    pins, payloads = _fixture_pins()
    result = audit_primary_archive(Archive({}), pins=pins, parser=_parser)
    assert all(row["primary_bytes"] == "unknown" for row in result["results"])
    assert all(row["candidate_blocker_class"] is None for row in result["results"])
