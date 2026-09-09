from __future__ import annotations

from datetime import datetime, timezone

import pytest

from white_list_archive.geocoding.fallback import (
    FallbackTarget,
    _candidate_country_valid,
    _same_identity,
    fallback_geocode,
)
from white_list_archive.geocoding.models import GeocodeCandidate
from white_list_archive.geocoding.nominatim import PUBLIC_NOMINATIM_ENDPOINT


def _target(reason: str, source_country: str | None = None) -> FallbackTarget:
    return FallbackTarget(
        address_id="a",
        query="source text",
        eligibility_reason_code=reason,
        source_route_code={
            "source_foreign": "foreign_fallback",
            "country_unresolved": "unresolved_fallback",
            "anncsu_not_found": "italian_anncsu",
        }[reason],
        source_country_code=source_country,
        upstream_geocode_result_id="up" if reason == "anncsu_not_found" else None,
        upstream_provider_version="ann-v1" if reason == "anncsu_not_found" else None,
        current_result_status="candidate",
        current_candidate_count=1,
        current_provider_version="mock-v1",
        current_provider_data_updated=datetime(2026, 9, 9, tzinfo=timezone.utc),
    )


def _candidate(country_code: str | None) -> GeocodeCandidate:
    return GeocodeCandidate(
        provider_result_id="x",
        candidate_rank=1,
        matched_address="match",
        street_name="Via Test",
        house_number="1",
        postal_code=None,
        locality=None,
        admin_unit_l2=None,
        admin_unit_l1=None,
        country_name=None,
        country_code=country_code,
        latitude=1.0,
        longitude=1.0,
        precision_code="address",
        attribution=None,
        licence=None,
        payload={},
    )


def test_country_filter_is_reason_specific():
    assert _target("anncsu_not_found").country_filter_code == "IT"
    assert _target("source_foreign", "FR").country_filter_code == "FR"
    assert _target("country_unresolved").country_filter_code is None


def test_same_version_and_data_timestamp_are_required_for_cache_reuse():
    target = _target("anncsu_not_found")
    stamp = datetime(2026, 9, 9, tzinfo=timezone.utc)
    assert _same_identity(target, provider_version="mock-v1", provider_data_updated=stamp)
    assert not _same_identity(target, provider_version="mock-v2", provider_data_updated=stamp)
    assert not _same_identity(
        target,
        provider_version="mock-v1",
        provider_data_updated=datetime(2026, 9, 10, tzinfo=timezone.utc),
    )


def test_country_filtered_fallback_rejects_cross_country_candidate():
    assert _candidate_country_valid(_candidate("IT"), "IT")
    assert _candidate_country_valid(_candidate("FR"), "FR")
    assert not _candidate_country_valid(_candidate("IT"), "FR")
    assert not _candidate_country_valid(_candidate(None), "IT")
    assert _candidate_country_valid(_candidate(None), None)


def test_recurring_fallback_can_never_use_public_osmf_nominatim():
    with pytest.raises(ValueError, match="explicit"):
        fallback_geocode(
            dsn="postgresql://unused",
            endpoint=PUBLIC_NOMINATIM_ENDPOINT,
        )
