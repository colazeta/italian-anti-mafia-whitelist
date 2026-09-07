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
    country_code: str | None = "IT",
    street: str | None = "Via Roma",
    house: str | None = None,
) -> ValidationRow:
    return ValidationRow(
        address_id=f"id-{suffix}",
        source_address=f"source-{suffix}",
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


def test_summary_distinguishes_match_failure_precision_and_ambiguity():
    rows = [
        row("a", precision="address", house="1"),
        row("b", precision="street", candidate_count=2),
        row("c", status="not_found"),
        row("d", status="error"),
        row("e", status="unprocessed"),
        row("f", precision="street", country_code="FR"),
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
    assert result["country_counts"] == {"FR": 1, "IT": 2}
    assert result["field_completeness"]["house_number"]["present"] == 1


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
