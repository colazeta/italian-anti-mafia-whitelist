"""Read-only, exact-input qualification of one legacy Ascoli publication key.

This cannot register or relabel a SourceSeries, create a capture, link a parse run,
approve an edition, or permit public promotion. Keep any later persistence decision
separate from the evidence that two *different logical names* share one original.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
import re

LEGACY_KEY = "ascoli-piceno-listed"
REGISTERED_KEY = "ascoli-piceno-listed-comprehensive"
APPROVED_SHA256 = "5c1e7e6145929162207721d79302a5267524e5b35429234a961eee504b75c43b"
APPROVED_DATE = "2026-08-11"
EXPECTED_ROWS = 544
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def qualify_review_only_alias(
    publication_source: Mapping[str, object],
    reviewed_inventory: Iterable[Mapping[str, str]],
    observed_capture: Mapping[str, object],
) -> dict[str, object]:
    """Qualify the sole pinned candidate without altering source provenance.

    ``observed_capture`` is an independently read PostgreSQL aggregate joined
    through the actual capture, content object, source series, authority and
    register. Counts are *per exact candidate*, not per entire authority.
    A successful result is evidence for a future review, never an alias binding.
    """
    expected_source = {
        "source_key": LEGACY_KEY,
        "authority_key": "ascoli-piceno",
        "register_key": "ascoli-piceno-ordinary",
        "population_scope": "listed",
        "parser": "ascoli_piceno_listed",
        "reference_date": APPROVED_DATE,
        "sha256": APPROVED_SHA256,
        "expected_source_rows": EXPECTED_ROWS,
    }
    if not _HEX64.fullmatch(APPROVED_SHA256):
        raise ValueError("Invalid frozen source digest")
    if any(publication_source.get(k) != value for k, value in expected_source.items()):
        raise ValueError("Frozen Ascoli publication descriptor disagrees with the reviewed candidate")

    matching_inventory = [row for row in reviewed_inventory
                          if row.get("source_series_key") == REGISTERED_KEY]
    if len(matching_inventory) != 1:
        raise ValueError("Reviewed registered SourceSeries must be unique")
    inventory = matching_inventory[0]
    expected_inventory = {
        "authority_key": "ascoli-piceno",
        "regime_code": "WL-REGIME-L190-2012",
        "population_scope": "listed",
        "sector_scope": "all",
    }
    if any(inventory.get(k) != value for k, value in expected_inventory.items()):
        raise ValueError("Registered SourceSeries scope differs from frozen publication source")

    expected_observed = {
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
    }
    if any(observed_capture.get(k) != value for k, value in expected_observed.items()):
        raise ValueError("No unique, durable, official exact-byte Ascoli capture match")
    # A PostgreSQL capture may have no independently attributable edition date.
    # Never promote the manifest's document date into capture or administrative time.
    if observed_capture.get("declared_reference_date") is not None:
        raise ValueError("Unexpected capture date attribution requires separate source review")
    if observed_capture.get("register_matches_reviewed_authority") is not True:
        raise ValueError("Existing source register/authority binding was not independently verified")

    return {
        "legacy_public_source_key": LEGACY_KEY,
        "registered_source_series_key": REGISTERED_KEY,
        "qualification": "exact_capture_candidate_review_only",
        "exact_byte_and_authority_regime_match": True,
        "capture_provenance_relabelled": False,
        "approved_parser_snapshot": False,
        "edition_approved": False,
        "automatic_alias_binding": False,
        "public_promotion": False,
    }
