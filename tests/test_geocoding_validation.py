from white_list_archive.geocoding.validation import (
    ValidationRow,
    _allocate_stratified_sample,
    build_manual_sample,
    summarize,
)


def row(
    suffix: str,
    *,
    status: str = "candidate",
    precision: str | None = "street",
    candidate_count: int = 1,
    source_country_code: str | None = "IT",
    derived_country_code: str | None = None,
    country_classification_status: str = "source_explicit",
    country_route_code: str = "italian_anncsu",
    country_code: str | None = "IT",
    street: str | None = "Via Roma",
    house: str | None = None,
) -> ValidationRow:
    return ValidationRow(
        address_id=f"id-{suffix}",
        source_address=f"source-{suffix}",
        source_country_code=source_country_code,
        derived_country_code=derived_country_code,
        country_classification_status=country_classification_status,
        country_route_code=country_route_code,
        country_derivation_reason="fixture",
        match_status=status,
        candidate_count=candidate_count,
        provider_name="nominatim" if status != "unprocessed" else None,
        provider_endpoint="https://example.test" if status != "unprocessed" else None,
        provider_version="5.3" if status != "unprocessed" else None,
        provider_data_updated="2026-09-07T00:00:00+00:00" if status != "unprocessed" else None,
        query_text=f"source-{suffix}" if status != "unprocessed" else None,
        normalised_address=f"normalised-{suffix}" if status in {"candidate", "accepted"} else None,
        street_name=street if status in {"candidate", "accepted"} else None,
        house_number=house if status in {"candidate", "accepted"} else None,
        postal_code="87100" if status in {"candidate", "accepted"} else None,
        locality="Cosenza" if status in {"candidate", "accepted"} else None,
        admin_unit_l2="Cosenza" if status in {"candidate", "accepted"} else None,
        admin_unit_l1="Calabria" if status in {"candidate", "accepted"} else None,
        country_name="Italia" if country_code == "IT" else "France",
        country_code=country_code if status in {"candidate", "accepted"} else None,
        latitude=39.3 if status in {"candidate", "accepted"} else None,
        longitude=16.2 if status in {"candidate", "accepted"} else None,
        precision_code=precision if status in {"candidate", "accepted"} else None,
    )


def test_summary_distinguishes_match_failure_precision_ambiguity_and_country_conflict():
    rows = [
        row("a", precision="address", house="1"),
        row("b", precision="street", candidate_count=2),
        row("c", status="not_found"),
        row("d", status="error"),
        row("e", status="unprocessed"),
        row("f", precision="street", source_country_code="IT", country_code="FR"),
    ]
    result = summarize(rows)
    assert result["total_canonical_addresses"] == 6
    assert result["addresses_with_provider_match"] == 3
    assert result["match_rate_pct"] == 50.0
    assert result["not_found"] == 1
    assert result["errors"] == 1
    assert result["unprocessed"] == 1
    assert result["precision_counts"] == {"address": 1, "street": 2}
    assert result["candidate_multiplicity"]["multiple_candidates"] == 1
    assert result["provider_country_counts"] == {"FR": 1, "IT": 2}
    assert result["source_country_counts"] == {"IT": 6}
    assert result["derived_country_counts"] == {"UNKNOWN": 6}
    assert result["country_route_counts"] == {"italian_anncsu": 6}
    assert result["source_provider_country_conflicts"] == 1
    assert result["field_completeness"]["house_number"]["present"] == 1


def test_summary_keeps_derived_and_source_country_separate():
    rows = [
        row(
            "derived",
            source_country_code=None,
            derived_country_code="IT",
            country_classification_status="derived_italian",
            country_route_code="italian_anncsu",
        ),
        row(
            "foreign",
            status="unprocessed",
            source_country_code="FR",
            derived_country_code=None,
            country_classification_status="source_explicit",
            country_route_code="foreign_fallback",
            country_code=None,
        ),
        row(
            "unresolved",
            status="unprocessed",
            source_country_code=None,
            derived_country_code=None,
            country_classification_status="unresolved",
            country_route_code="unresolved_fallback",
            country_code=None,
        ),
    ]
    result = summarize(rows)
    assert result["source_country_counts"] == {"FR": 1, "UNKNOWN": 2}
    assert result["derived_country_counts"] == {"IT": 1, "UNKNOWN": 2}
    assert result["country_route_counts"] == {
        "foreign_fallback": 1,
        "italian_anncsu": 1,
        "unresolved_fallback": 1,
    }
    assert result["review_strata"] == {
        "country_unresolved": 1,
        "foreign_routed": 1,
        "matched_street": 1,
    }


def test_stratified_allocation_never_exceeds_population_or_requested_total():
    sizes = {"matched_street": 100, "not_found": 20, "error": 2}
    allocation = _allocate_stratified_sample(sizes, 30)
    assert sum(allocation.values()) == 30
    assert all(0 <= allocation[key] <= sizes[key] for key in sizes)
    assert allocation["error"] == 2
    assert allocation["not_found"] >= 5


def test_manual_sample_is_deterministic_and_carries_sampling_weights():
    rows = [row(str(i), precision="street") for i in range(20)]
    rows += [row(f"nf-{i}", status="not_found") for i in range(7)]
    first = build_manual_sample(rows, sample_size=10)
    second = build_manual_sample(rows, sample_size=10)
    assert first == second
    assert len(first) == 10
    assert {item["review_stratum"] for item in first} == {"matched_street", "not_found"}
    assert all(item["sampling_weight"] >= 1 for item in first)
    assert all(item["manual_address_correct"] == "" for item in first)
