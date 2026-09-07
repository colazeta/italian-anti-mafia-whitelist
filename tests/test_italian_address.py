from white_list_archive.geocoding.italian_address import (
    MunicipalityPrefixMatcher,
    MunicipalityRecord,
)


def matcher() -> MunicipalityPrefixMatcher:
    return MunicipalityPrefixMatcher(
        [
            MunicipalityRecord("078017", "Bisignano", "Bisignano", "CS", "Calabria", "A887"),
            MunicipalityRecord("078102", "Rende", "Rende", "CS", "Calabria", "H235"),
            MunicipalityRecord("078157", "Corigliano-Rossano", "Corigliano-Rossano", "CS", "Calabria", "M403"),
            MunicipalityRecord("078133", "Santa Sofia d'Epiro", "Santa Sofia d'Epiro", "CS", "Calabria", "I309"),
        ]
    )


def test_exact_prefix_preserves_source_and_returns_remainder():
    result = matcher().split("BISIGNANO Via Nazionale, 17")
    assert result.status == "exact"
    assert result.split is not None
    assert result.split.source_address == "BISIGNANO Via Nazionale, 17"
    assert result.split.municipality.display_name == "Bisignano"
    assert result.split.municipality.cadastral_code == "A887"
    assert result.split.remainder == "Via Nazionale, 17"


def test_parenthetical_province_is_checked_and_removed_from_remainder():
    result = matcher().split("RENDE(CS), VIA VERDI 33/A")
    assert result.status == "exact"
    assert result.split is not None
    assert result.split.remainder == "VIA VERDI 33/A"
    mismatch = matcher().split("RENDE(RC), VIA VERDI 33/A")
    assert mismatch.status == "province_marker_mismatch"
    assert mismatch.split is None


def test_punctuation_and_diacritic_folding_do_not_create_fuzzy_aliases():
    result = matcher().split("CORIGLIANO ROSSANO Via Virgilio 14")
    assert result.status == "exact"
    assert result.split is not None
    result = matcher().split("SANTA SOFIA D’EPIRO Via Pedilati snc")
    assert result.status == "exact"
    assert result.split is not None
    assert matcher().split("S. GIOVANNI IN FIORE Via Roma 1").status == "no_exact_municipality_prefix"
    assert matcher().split("PARIGI (FR) Rue du Cardinal Lemoine 62").status == "no_exact_municipality_prefix"
