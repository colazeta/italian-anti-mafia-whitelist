from __future__ import annotations

import pytest

from white_list_archive.geocoding.nominatim import (
    NominatimClient,
    PUBLIC_NOMINATIM_ENDPOINT,
    lightly_clean_query,
    parse_geocodejson,
    query_variants,
)


def _payload() -> dict:
    return {
        "type": "FeatureCollection",
        "geocoding": {
            "version": "0.1.0",
            "attribution": "Data © OpenStreetMap contributors",
            "licence": "ODbL",
            "query": "Via Roma 1, Cosenza",
        },
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "geocoding": {
                        "type": "house",
                        "label": "1, Via Roma, Cosenza, Calabria, Italia",
                        "housenumber": "1",
                        "street": "Via Roma",
                        "postcode": "87100",
                        "city": "Cosenza",
                        "county": "Cosenza",
                        "state": "Calabria",
                        "country": "Italia",
                        "country_code": "it",
                        "osm_type": "way",
                        "osm_id": "12345",
                    }
                },
                "geometry": {"type": "Point", "coordinates": [16.25, 39.30]},
            }
        ],
    }


def test_geocodejson_maps_to_provider_neutral_address_fields():
    candidates = parse_geocodejson(_payload())
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.provider_result_id == "osm:way:12345"
    assert candidate.matched_address == "1, Via Roma, Cosenza, Calabria, Italia"
    assert candidate.street_name == "Via Roma"
    assert candidate.house_number == "1"
    assert candidate.postal_code == "87100"
    assert candidate.locality == "Cosenza"
    assert candidate.admin_unit_l2 == "Cosenza"
    assert candidate.admin_unit_l1 == "Calabria"
    assert candidate.country_name == "Italia"
    assert candidate.country_code == "IT"
    assert candidate.latitude == pytest.approx(39.30)
    assert candidate.longitude == pytest.approx(16.25)
    assert candidate.precision_code == "address"
    assert candidate.is_address_level
    assert candidate.attribution == "Data © OpenStreetMap contributors"
    assert candidate.licence == "ODbL"


def test_geocodejson_precision_is_conservative_and_uses_street_name_fallback():
    payload = _payload()
    geocoding = payload["features"][0]["properties"]["geocoding"]
    geocoding["type"] = "street"
    geocoding["name"] = "Via Quattro Novembre"
    geocoding.pop("housenumber")
    geocoding.pop("street")
    candidate = parse_geocodejson(payload)[0]
    assert candidate.precision_code == "street"
    assert candidate.street_name == "Via Quattro Novembre"
    assert not candidate.is_address_level


def test_light_query_cleanup_only_repairs_source_formatting():
    assert lightly_clean_query("RENDE(CS), VIALE ORSO MARIO CORBINO 33") == (
        "RENDE, VIALE ORSO MARIO CORBINO 33"
    )
    assert lightly_clean_query("CASSANO ALL’IONIO Via IV Novembre, 2") == (
        "CASSANO ALL’IONIO, Via IV Novembre, 2"
    )
    assert lightly_clean_query("PARIGI (FR)Rue du Cardinal Demoine 62") == (
        "PARIGI, Rue du Cardinal Demoine 62"
    )


def test_query_variants_preserve_source_first_and_deduplicate_unchanged_queries():
    raw = "RENDE(CS), VIALE ORSO MARIO CORBINO 33"
    assert query_variants(raw) == [
        raw,
        "RENDE, VIALE ORSO MARIO CORBINO 33",
    ]
    assert query_variants("Via Roma 1, Cosenza") == ["Via Roma 1, Cosenza"]


def test_public_osmf_service_requires_explicit_opt_in_and_enforces_rate_limit():
    with pytest.raises(ValueError, match="explicit"):
        NominatimClient(PUBLIC_NOMINATIM_ENDPOINT)

    client = NominatimClient(
        PUBLIC_NOMINATIM_ENDPOINT,
        allow_public_service=True,
        min_interval_seconds=0,
    )
    assert client.is_public_osmf_service
    assert client.min_interval_seconds >= 1.0


def test_non_public_compatible_endpoint_is_swappable_without_public_policy_flag():
    client = NominatimClient("https://geocoder.example.test/nominatim/", min_interval_seconds=0)
    assert client.endpoint == "https://geocoder.example.test/nominatim"
    assert not client.is_public_osmf_service
    assert client.min_interval_seconds == 0


def test_invalid_geocodejson_contract_fails_loudly():
    with pytest.raises(ValueError, match="features"):
        parse_geocodejson({"type": "FeatureCollection"})
