from white_list_archive.geocoding.country_routing import assess_source_address
from white_list_archive.geocoding.italian_address import (
    MunicipalityPrefixMatcher,
    MunicipalityRecord,
)


def matcher() -> MunicipalityPrefixMatcher:
    return MunicipalityPrefixMatcher(
        [
            MunicipalityRecord("078045", "Cosenza", "Cosenza", "CS", "Calabria", "D086"),
            MunicipalityRecord("060038", "Frosinone", "Frosinone", "FR", "Lazio", "D810"),
            MunicipalityRecord(
                "078119",
                "San Giovanni in Fiore",
                "San Giovanni in Fiore",
                "CS",
                "Calabria",
                "H919",
            ),
        ]
    )


def test_exact_istat_prefix_derives_italy_without_faking_source_country():
    result = assess_source_address(
        "COSENZA Via Roma 1", municipality_matcher=matcher()
    )
    assert result.source_country_code is None
    assert result.derived_country_code == "IT"
    assert result.classification_status_code == "derived_italian"
    assert result.route_code == "italian_anncsu"
    assert result.derivation_reason.startswith("istat_municipality_prefix:")


def test_italian_province_plate_fr_is_not_misread_as_france():
    result = assess_source_address(
        "FROSINONE (FR) Via Roma 1", municipality_matcher=matcher()
    )
    assert result.source_country_code is None
    assert result.derived_country_code == "IT"
    assert result.route_code == "italian_anncsu"


def test_known_cosenza_foreign_form_is_source_explicit_france():
    result = assess_source_address(
        "PARIGI (FR)Rue du Cardinal Demoine 62", municipality_matcher=matcher()
    )
    assert result.source_country_code == "FR"
    assert result.derived_country_code is None
    assert result.classification_status_code == "source_explicit"
    assert result.route_code == "foreign_fallback"
    assert "validated_foreign_street_language" in result.derivation_reason


def test_unresolved_abbreviation_is_not_silently_italian():
    result = assess_source_address(
        "S. GIOVANNI IN FIORE Via Roma 1", municipality_matcher=matcher()
    )
    assert result.source_country_code is None
    assert result.derived_country_code is None
    assert result.classification_status_code == "unresolved"
    assert result.route_code == "unresolved_fallback"


def test_dedicated_source_country_field_has_priority_over_derived_text():
    result = assess_source_address(
        "COSENZA Via Roma 1",
        municipality_matcher=matcher(),
        explicit_source_country_code="DE",
    )
    assert result.source_country_code == "DE"
    assert result.derived_country_code is None
    assert result.classification_status_code == "source_explicit"
    assert result.route_code == "foreign_fallback"


def test_explicit_italian_source_country_routes_anncsu_without_derivation():
    result = assess_source_address(
        "Qualunque forma",
        municipality_matcher=matcher(),
        explicit_source_country_code="IT",
    )
    assert result.source_country_code == "IT"
    assert result.derived_country_code is None
    assert result.route_code == "italian_anncsu"
