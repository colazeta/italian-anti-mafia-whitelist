from pathlib import Path

from white_list_archive.geocoding.review_analysis import (
    analyse_review_rows,
    read_review_csv,
)


def _row(stratum, population, sample, weight, verdict):
    return {
        "address_id": f"{stratum}-{verdict}-{weight}",
        "review_stratum": stratum,
        "stratum_population": str(population),
        "stratum_sample": str(sample),
        "sampling_weight": str(weight),
        "review_verdict": verdict,
    }


def test_not_found_is_coverage_failure_not_precision_penalty():
    rows = [
        _row("matched_civic_access", 10, 2, 5, "correct"),
        _row("matched_civic_access", 10, 2, 5, "correct"),
        _row("matched_street", 20, 2, 10, "correct"),
        _row("matched_street", 20, 2, 10, "incorrect"),
        _row("not_found", 70, 2, 35, ""),
        _row("not_found", 70, 2, 35, "incorrect"),
    ]
    result = analyse_review_rows(
        rows, treat_not_found_as_coverage_failure=True
    )
    assert result["population"] == 100
    assert result["candidate_population"] == 30
    assert result["candidate_coverage_pct"] == 30.0
    assert result["candidate_weighted_precision_pct"] == 66.67
    assert result["estimated_validated_yield_pct"] == 20.0
    assert result["not_found_effective_semantics"] == "coverage_failure"
    assert result["precision_excludes_not_found"] is True


def test_candidate_verdicts_must_be_complete():
    rows = [
        _row("matched_civic_access", 10, 1, 10, ""),
        _row("not_found", 90, 1, 90, ""),
    ]
    try:
        analyse_review_rows(rows)
    except ValueError as exc:
        assert "candidate review is incomplete" in str(exc)
    else:
        raise AssertionError("expected incomplete candidate review to fail")


def test_frozen_cosenza_review_metrics_do_not_drift():
    path = Path("data/validation/cosenza/address-review-2026-09-07.csv")
    result = analyse_review_rows(
        read_review_csv(path), treat_not_found_as_coverage_failure=True
    )
    assert result["population"] == 1298
    assert result["candidate_population"] == 624
    assert result["candidate_sample_rows"] == 78
    assert result["candidate_review_complete"] is True
    assert result["candidate_coverage_pct"] == 48.07
    assert result["candidate_weighted_precision_pct"] == 82.49
    assert result["estimated_validated_yield_pct"] == 39.65
    assert result["strata"]["matched_civic_access"]["determinate_precision_pct"] == 100.0
    assert result["strata"]["matched_street"]["determinate_precision_pct"] == 57.14
    assert result["strata"]["matched_without_coordinates"]["determinate_precision_pct"] == 85.71
    assert result["not_found_sample_rows"] == 72
    assert result["not_found_explicit_incorrect_rows"] == 14
    assert result["not_found_unmarked_rows"] == 58
