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
    assert report["verified_authority_count"] == 71
    assert report["register_scope_count"] == 74
    assert report["complete_register_scope_count"] == 74
    assert report["incomplete_register_scope_count"] == 0

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

    forli = [
        row
        for row in report["rows"]
        if row["authority_key"] == "forli-cesena"
        and row["regime_code"] == "WL-REGIME-L190-2012"
    ]
    assert {row["coverage_status"] for row in forli} == {"COVERED_COMBINED_SERIES"}
    assert all(row["covering_series_keys"] == ["forli-cesena-combined"] for row in forli)

    sassari = [
        row
        for row in report["rows"]
        if row["authority_key"] == "sassari"
        and row["regime_code"] == "WL-REGIME-L190-2012"
    ]
    assert {row["coverage_status"] for row in sassari} == {"COVERED_COMBINED_SERIES"}
    assert all(row["covering_series_keys"] == ["sassari-combined"] for row in sassari)

    milano = [
        row
        for row in report["rows"]
        if row["authority_key"] == "milano"
        and row["regime_code"] == "WL-REGIME-L190-2012"
    ]
    assert {row["coverage_status"] for row in milano} == {"COVERED_COMBINED_SERIES"}
    assert all(row["covering_series_keys"] == ["milano-combined"] for row in milano)

    cremona = [
        row
        for row in report["rows"]
        if row["authority_key"] == "cremona"
        and row["regime_code"] == "WL-REGIME-L190-2012"
    ]
    assert {row["coverage_status"] for row in cremona} == {"COVERED_COMBINED_SERIES"}
    assert all(row["covering_series_keys"] == ["cremona-combined"] for row in cremona)

    ravenna = [
        row
        for row in report["rows"]
        if row["authority_key"] == "ravenna"
        and row["regime_code"] == "WL-REGIME-L190-2012"
    ]
    assert {row["population_target"] for row in ravenna} == {"listed", "applicant"}
    assert {row["coverage_status"] for row in ravenna} == {"COVERED_COMBINED_SERIES"}
    assert all(row["covering_series_keys"] == ["ravenna-combined"] for row in ravenna)


def test_separate_series_and_unresolved_gaps_are_distinguished():
    report = _report()
    agrigento = {
        row["population_target"]: row
        for row in report["rows"]
        if row["authority_key"] == "agrigento"
    }
    assert agrigento["listed"]["coverage_status"] == "COVERED_SEPARATE_SERIES"
    assert agrigento["applicant"]["coverage_status"] == "COVERED_SEPARATE_SERIES"

    unresolved = {
        row["authority_key"]
        for row in report["scopes"]
        if not row["source_population_complete"]
    }
    assert unresolved == set()


def test_recently_resolved_current_pages_cover_both_populations():
    report = _report()
    for authority in (
        "bari",
        "udine",
        "crotone",
        "cuneo",
        "fermo",
        "grosseto",
        "imperia",
        "lucca",
        "macerata",
        "trapani",
        "palermo",
        "matera",
        "siracusa",
        "viterbo",
    ):
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


def test_modena_special_register_is_a_separate_completeness_scope():
    report = _report()
    modena = [row for row in report["scopes"] if row["authority_key"] == "modena"]
    assert {row["regime_code"] for row in modena} == {
        "WL-REGIME-L190-2012",
        "WL-REGIME-ER-SISMA-2012",
    }
    assert all(row["listed_status"] == "COVERED_SEPARATE_SERIES" for row in modena)
    assert all(row["applicant_status"] == "COVERED_SEPARATE_SERIES" for row in modena)
    assert all(row["source_population_complete"] for row in modena)


def test_ferrara_ordinary_and_reconstruction_registers_are_separate_complete_scopes():
    report = _report()
    scopes = [row for row in report["scopes"] if row["authority_key"] == "ferrara"]
    assert {row["regime_code"] for row in scopes} == {
        "WL-REGIME-L190-2012",
        "WL-REGIME-ER-SISMA-2012",
    }
    assert all(row["listed_status"] == "COVERED_SEPARATE_SERIES" for row in scopes)
    assert all(row["applicant_status"] == "COVERED_SEPARATE_SERIES" for row in scopes)
    assert all(row["source_population_complete"] for row in scopes)

    rows = {
        (row["regime_code"], row["population_target"]): row
        for row in report["rows"]
        if row["authority_key"] == "ferrara"
    }
    assert rows[("WL-REGIME-L190-2012", "listed")]["covering_series_keys"] == [
        "ferrara-provincial-listed"
    ]
    assert rows[("WL-REGIME-L190-2012", "applicant")]["covering_series_keys"] == [
        "ferrara-provincial-applicants"
    ]
    assert rows[("WL-REGIME-ER-SISMA-2012", "listed")]["covering_series_keys"] == [
        "ferrara-reconstruction-listed"
    ]
    assert rows[("WL-REGIME-ER-SISMA-2012", "applicant")]["covering_series_keys"] == [
        "ferrara-reconstruction-applicants"
    ]
