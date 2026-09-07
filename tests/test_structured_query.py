from white_list_archive.geocoding.structured_query import (
    MunicipalityPrefixMatcher,
    MunicipalityRecord,
)


def matcher() -> MunicipalityPrefixMatcher:
    return MunicipalityPrefixMatcher(
        [
            MunicipalityRecord("078017", "Bisignano", "Bisignano", "CS", "Calabria"),
            MunicipalityRecord("078102", "Rende", "Rende", "CS", "Calabria"),
            MunicipalityRecord("078157", "Zumpano", "Zumpano", "CS", "Calabria"),
            MunicipalityRecord("078157X", "Corigliano-Rossano", "Corigliano-Rossano", "CS", "Calabria"),
            MunicipalityRecord("078133", "Santa Sofia d'Epiro", "Santa Sofia d'Epiro", "CS", "Calabria"),
        ]
    )


def test_plain_municipality_prefix_is_split_without_rewriting_source():
    result = matcher().split("BISIGNANO Via Nazionale, 17")
    assert result.status == "structured"
    assert result.query is not None
    assert result.query.source_address == "BISIGNANO Via Nazionale, 17"
    assert result.query.city == "Bisignano"
    assert result.query.street == "Via Nazionale, 17"


def test_parenthetical_province_marker_is_removed_from_street_query():
    result = matcher().split("RENDE(CS), VIA VERDI 33/A")
    assert result.status == "structured"
    assert result.query is not None
    assert result.query.city == "Rende"
    assert result.query.street == "VIA VERDI 33/A"


def test_punctuation_folding_handles_hyphenated_official_municipality():
    result = matcher().split("CORIGLIANO ROSSANO Via Madre Isabella De Rosis 63/65")
    assert result.status == "structured"
    assert result.query is not None
    assert result.query.city == "Corigliano-Rossano"
    assert result.query.street == "Via Madre Isabella De Rosis 63/65"


def test_apostrophe_style_does_not_block_exact_token_match():
    result = matcher().split("SANTA SOFIA D’EPIRO Via Pedilati snc")
    assert result.status == "structured"
    assert result.query is not None
    assert result.query.city == "Santa Sofia d'Epiro"
    assert result.query.street == "Via Pedilati snc"


def test_conflicting_explicit_province_marker_is_rejected():
    result = matcher().split("RENDE(RC), VIA VERDI 33/A")
    assert result.status == "province_marker_mismatch"
    assert result.query is None


def test_unrecognised_or_abbreviated_city_is_not_fuzzily_guessed():
    result = matcher().split("S. GIOVANNI IN FIORE Contrada Nunziatella, 9")
    assert result.status == "no_exact_municipality_prefix"
    assert result.query is None


def test_foreign_city_is_left_unstructured():
    result = matcher().split("PARIGI (FR) Rue du Cardinal Lemoine 62")
    assert result.status == "no_exact_municipality_prefix"
    assert result.query is None
