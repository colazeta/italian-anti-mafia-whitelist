from white_list_archive.geocoding.review_sample import (
    build_review_sample,
    review_stratum,
)


def row(
    suffix: str,
    *,
    status: str = "candidate",
    precision: str = "street",
    latitude: str = "39.3",
    longitude: str = "16.2",
    country: str = "IT",
):
    return {
        "address_id": f"id-{suffix}",
        "source_address": f"source-{suffix}",
        "match_status": status,
        "precision_code": precision,
        "latitude": latitude,
        "longitude": longitude,
        "country_code": country,
    }


def test_review_strata_separate_precision_and_missing_coordinates():
    assert review_stratum(row("c", precision="civic_access")) == "matched_civic_access"
    assert review_stratum(row("s", precision="street")) == "matched_street"
    assert review_stratum(row("a", precision="address")) == "matched_address"
    assert (
        review_stratum(row("n", precision="civic_access", latitude="", longitude=""))
        == "matched_without_coordinates"
    )
    assert review_stratum(row("nf", status="not_found")) == "not_found"
    assert review_stratum(row("fr", country="FR")) == "foreign_matched"


def test_review_sample_is_deterministic_and_represents_every_observed_stratum():
    rows = [row(f"ca-{i}", precision="civic_access") for i in range(30)]
    rows += [row(f"st-{i}", precision="street") for i in range(30)]
    rows += [
        row(f"nc-{i}", precision="street", latitude="", longitude="")
        for i in range(10)
    ]
    rows += [row(f"nf-{i}", status="not_found") for i in range(20)]
    first = build_review_sample(rows, sample_size=40)
    second = build_review_sample(rows, sample_size=40)
    assert first == second
    assert len(first) == 40
    assert {item["review_stratum"] for item in first} == {
        "matched_civic_access",
        "matched_street",
        "matched_without_coordinates",
        "not_found",
    }
    assert all(float(item["sampling_weight"]) >= 1 for item in first)
