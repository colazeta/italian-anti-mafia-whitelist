"""Regressions for the read-only, single-source Ascoli provenance candidate."""
from __future__ import annotations

import csv
from copy import deepcopy
import json
from pathlib import Path

import pytest

from white_list_archive.acquisition.approved_source_alias_audit import (
    APPROVED_SHA256, LEGACY_KEY, REGISTERED_KEY, qualify_review_only_alias,
)

ROOT = Path(__file__).resolve().parents[1]


def _reviewed():
    config = json.loads(
        (ROOT / "data/publication/multi_prefecture_pilot.json").read_text(encoding="utf-8")
    )
    source = next(row for row in config["sources"] if row["source_key"] == LEGACY_KEY)
    with (ROOT / "data/source_registry/source_series_inventory.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        inventory = list(csv.DictReader(handle))
    return source, inventory


def _capture():
    # This is a synthetic aggregate standing in for an independent SQL read.
    # No captured entity, URL, storage key, private row, or source cell appears.
    return {
        "series_code": REGISTERED_KEY,
        "authority_code": "ascoli-piceno",
        "regime_code": "WL-REGIME-L190-2012",
        "sha256": APPROVED_SHA256,
        "origin_type_code": "official_current",
        "authority_rank_code": "primary_official",
        "storage_status_code": "durable",
        "http_status": 200,
        "exact_capture_count": 1,
        "exact_content_object_count": 1,
        "declared_reference_date": None,
        "register_matches_reviewed_authority": True,
    }


def test_real_reviewed_inventory_and_frozen_descriptor_can_only_qualify_prospectively():
    source, inventory = _reviewed()
    original = deepcopy(source)
    result = qualify_review_only_alias(source, inventory, _capture())
    assert result["legacy_public_source_key"] == LEGACY_KEY
    assert result["registered_source_series_key"] == REGISTERED_KEY
    assert result["exact_byte_and_authority_regime_match"] is True
    assert result["qualification"] == "exact_capture_candidate_review_only"
    for key in ("capture_provenance_relabelled", "approved_parser_snapshot",
                "edition_approved", "automatic_alias_binding", "public_promotion"):
        assert result[key] is False
    assert source == original


@pytest.mark.parametrize("key,value", [
    ("series_code", "ascoli-piceno-listed-by-sector"),
    ("authority_code", "ancona"),
    ("regime_code", "WL-OTHER"),
    ("sha256", "0" * 64),
    ("origin_type_code", "unverified"),
    ("authority_rank_code", "other"),
    ("storage_status_code", "pending"),
    ("http_status", 404),
    ("exact_capture_count", 0),
    ("exact_capture_count", 2),
    ("exact_content_object_count", 0),
    ("register_matches_reviewed_authority", False),
    ("declared_reference_date", "2026-08-11"),
])
def test_capture_provenance_or_uniqueness_drift_fails_closed(key, value):
    source, inventory = _reviewed()
    observed = _capture()
    observed[key] = value
    with pytest.raises(ValueError):
        qualify_review_only_alias(source, inventory, observed)


@pytest.mark.parametrize("key,value", [
    ("source_key", "ascoli-piceno-applicants"),
    ("authority_key", "ancona"),
    ("register_key", "other-register"),
    ("population_scope", "listed_and_applicant"),
    ("parser", "unreviewed_parser"),
    ("reference_date", "2026-11-15"),
    ("sha256", "a" * 64),
    ("expected_source_rows", 545),
])
def test_public_manifest_drift_cannot_change_the_pinned_alias(key, value):
    source, inventory = _reviewed()
    source = dict(source, **{key: value})
    with pytest.raises(ValueError):
        qualify_review_only_alias(source, inventory, _capture())


def test_inventory_ambiguity_or_changed_sector_scope_fails_closed():
    source, inventory = _reviewed()
    ascoli = next(row for row in inventory if row["source_series_key"] == REGISTERED_KEY)
    with pytest.raises(ValueError, match="unique"):
        qualify_review_only_alias(source, inventory + [ascoli], _capture())
    different = [dict(row) for row in inventory]
    row = next(row for row in different if row["source_series_key"] == REGISTERED_KEY)
    row["sector_scope"] = "per_sector"
    with pytest.raises(ValueError, match="scope"):
        qualify_review_only_alias(source, different, _capture())
