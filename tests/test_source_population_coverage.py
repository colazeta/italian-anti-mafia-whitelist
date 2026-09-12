from pathlib import Path

from white_list_archive.acquisition.source_population_coverage import (
    TARGET_POPULATIONS,
    _read_csv,
    build_coverage,
)

ROOT = Path(__file__).resolve().parents[1]


def _report():
    return build_coverage(
        _read_csv(ROOT / "data/source_registry/verified_primary_pages.csv"),
        _read_csv(ROOT / "data/source_registry/source_series_inventory.csv"),
    )


def test_every_verified_scope_accounts_for_both_logical_populations():
    report = _report()
    assert report["verified_authority_count"] == 38
    assert report["register_scope_count"] == 39
    assert report["complete_register_scope_count"] == 37
    assert report["incomplete_register_scope_count"] == 2

    by_scope = {}
    for row in report["rows"]:
        by_scope.setdefault((row["authority_key"], row["regime_code"]), set()).add(
            row["population_target"]
        )
    assert by_scope
    assert all(targets == set(TARGET_POPULATIONS) for targets in by_scope.values())


def test_combined_series_satisfies_both_targets_without_duplication():
    report = _report()
    cosenza = [
        row
        for row in report["rows"]
        if row["authority_key"] == "cosenza"
        and row["regime_code"] == "WL-REGIME-L190-2012"
    ]
    assert {row["population_target"] for row in cosenza} == {"listed", "applicant"}
    assert {row["coverage_status"] for row in cosenza} == {"COVERED_COMBINED_SERIES"}
    assert all(row["covering_series_keys"] == ["cosenza-combined"] for row in cosenza)

    ancona = [
        row
        for row in report["rows"]
        if row["authority_key"] == "ancona"
        and row["regime_code"] == "WL-REGIME-L190-2012"
    ]
    assert {row["coverage_status"] for row in ancona} == {"COVERED_COMBINED_SERIES"}
    assert all(row["covering_series_keys"] == ["ancona-combined"] for row in ancona)


def test_separate_series_and_unresolved_gaps_are_distinguished():
    report = _report()
    agrigento = {
        row["population_target"]: row
        for row in report["rows"]
        if row["authority_key"] == "agrigento"
    }
    assert agrigento["listed"]["coverage_status"] == "COVERED_SEPARATE_SERIES"
    assert agrigento["applicant"]["coverage_status"] == "COVERED_SEPARATE_SERIES"

    milano = {
        row["population_target"]: row
        for row in report["rows"]
        if row["authority_key"] == "milano"
    }
    assert milano["listed"]["coverage_status"] == "COVERED_SEPARATE_SERIES"
    assert milano["applicant"]["coverage_status"] == "UNRESOLVED_REQUIRES_REVIEW"

    unresolved = {
        row["authority_key"]
        for row in report["scopes"]
        if not row["source_population_complete"]
    }
    assert unresolved == {"milano", "sassari"}


def test_recently_resolved_current_pages_cover_both_populations():
    report = _report()
    for authority in ("bari", "udine", "crotone"):
        rows = {
            row["population_target"]: row
            for row in report["rows"]
            if row["authority_key"] == authority
        }
        assert set(rows) == {"listed", "applicant"}
        assert rows["listed"]["coverage_status"] == "COVERED_SEPARATE_SERIES"
        assert rows["applicant"]["coverage_status"] == "COVERED_SEPARATE_SERIES"
        assert rows["listed"]["covering_series_keys"] == [f"{authority}-listed"]
        assert rows["applicant"]["covering_series_keys"] == [f"{authority}-applicants"]


def test_bologna_special_register_is_a_separate_completeness_scope():
    report = _report()
    bologna = [row for row in report["scopes"] if row["authority_key"] == "bologna"]
    assert {row["regime_code"] for row in bologna} == {
        "WL-REGIME-L190-2012",
        "WL-REGIME-ER-SISMA-2012",
    }
    assert all(row["listed_status"] == "COVERED_SEPARATE_SERIES" for row in bologna)
    assert all(row["applicant_status"] == "COVERED_SEPARATE_SERIES" for row in bologna)
    assert all(row["source_population_complete"] for row in bologna)
