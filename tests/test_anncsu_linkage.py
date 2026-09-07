import csv

import pytest

from white_list_archive.geocoding.anncsu_linkage import (
    canonical_street_key,
    parse_street_and_civic,
    resolve_anncsu_addresses,
)
from white_list_archive.geocoding.italian_address import (
    MunicipalityPrefixMatcher,
    MunicipalityRecord,
)

FIELDS = [
    "CODICE_COMUNE",
    "CODICE_ISTAT",
    "PROGRESSIVO_NAZIONALE",
    "CODICE_COMUNALE",
    "ODONIMO",
    "LOCALITA'",
    "DIZIONE_LINGUA1",
    "DIZIONE_LINGUA2",
    "PROGRESSIVO_ACCESSO",
    "CODICE_COMUNALE_ACCESSO",
    "CIVICO",
    "ESPONENTE",
    "SPECIFICITA",
    "METRICO",
    "PROGRESSIVO_SNC",
    "COORD_X_COMUNE",
    "COORD_Y_COMUNE",
    "QUOTA",
    "METODO",
]


def matcher():
    return MunicipalityPrefixMatcher(
        [MunicipalityRecord("078045", "Cosenza", "Cosenza", "CS", "Calabria", "D086")]
    )


def row(street_id, street, access_id, civic, *, exponent="", lon="16,25", lat="39,30", method="3"):
    return {
        "CODICE_COMUNE": "D086",
        "CODICE_ISTAT": "078045",
        "PROGRESSIVO_NAZIONALE": street_id,
        "CODICE_COMUNALE": street_id,
        "ODONIMO": street,
        "LOCALITA'": "",
        "DIZIONE_LINGUA1": "",
        "DIZIONE_LINGUA2": "",
        "PROGRESSIVO_ACCESSO": access_id,
        "CODICE_COMUNALE_ACCESSO": access_id,
        "CIVICO": civic,
        "ESPONENTE": exponent,
        "SPECIFICITA": "",
        "METRICO": "",
        "PROGRESSIVO_SNC": "",
        "COORD_X_COMUNE": lon,
        "COORD_Y_COMUNE": lat,
        "QUOTA": "",
        "METODO": method,
    }


def write_anncsu(tmp_path, rows):
    path = tmp_path / "INDIR_CALA_20260803.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_road_type_is_part_of_exact_street_identity():
    assert canonical_street_key("Via Roma") == "via|roma"
    assert canonical_street_key("Piazza Roma") == "piazza|roma"
    assert canonical_street_key("C/da Padula") == "contrada|padula"
    assert canonical_street_key("S.S. 18") == "ss|18"


def test_civic_parser_does_not_invent_ranges_or_route_civics():
    parsed = parse_street_and_civic("Via Verdi 33/A")
    assert (parsed.status, parsed.number, parsed.exponent) == ("civic", "33", "A")
    assert parse_street_and_civic("Via Verdi 63/65").number is None
    assert parse_street_and_civic("S.S. 18").status == "terminal_number_is_route_number"
    assert parse_street_and_civic("Via Verdi SNC").status == "explicit_no_civic"


def test_exact_civic_prefers_direct_anncsu_access_coordinate(tmp_path):
    path = write_anncsu(
        tmp_path,
        [
            row("S1", "VIA ROMA", "A1", "1", lon="16,26", lat="39,31", method="4"),
            row("S2", "PIAZZA ROMA", "B1", "1", lon="16,27", lat="39,32"),
        ],
    )
    result = resolve_anncsu_addresses(
        ["COSENZA Via Roma 1"], municipality_matcher=matcher(), anncsu_csv=path
    )[0]
    assert result.status == "exact_civic_with_coordinates"
    assert result.candidate is not None
    assert result.candidate.precision_code == "civic_access"
    assert result.candidate.latitude == pytest.approx(39.31)
    assert result.candidate.longitude == pytest.approx(16.26)
    assert result.candidate.house_number == "1"
    assert result.candidate.payload["street_id"] == "S1"
    assert result.candidate.payload["access_id"] == "A1"


def test_exact_civic_without_coordinate_falls_back_to_street_median(tmp_path):
    path = write_anncsu(
        tmp_path,
        [
            row("S3", "VIA VERDI", "C10", "10", lon="", lat=""),
            row("S3", "VIA VERDI", "C11", "11", lon="16,20", lat="39,20"),
            row("S3", "VIA VERDI", "C12", "12", lon="16,40", lat="39,40"),
        ],
    )
    result = resolve_anncsu_addresses(
        ["COSENZA Via Verdi 10"], municipality_matcher=matcher(), anncsu_csv=path
    )[0]
    assert result.status == "exact_civic_street_coordinate_fallback"
    assert result.candidate is not None
    assert result.candidate.precision_code == "street"
    assert result.candidate.latitude == pytest.approx(39.30)
    assert result.candidate.longitude == pytest.approx(16.30)
    assert result.candidate.payload["coordinate_derivation"] == "median_of_anncsu_street_access_coordinates"


def test_exact_street_without_civic_can_produce_honest_street_candidate(tmp_path):
    path = write_anncsu(
        tmp_path,
        [
            row("S4", "VIA SENZA", "D1", "1", lon="16,10", lat="39,10"),
            row("S4", "VIA SENZA", "D2", "2", lon="16,30", lat="39,30"),
        ],
    )
    result = resolve_anncsu_addresses(
        ["COSENZA Via Senza SNC"], municipality_matcher=matcher(), anncsu_csv=path
    )[0]
    assert result.status == "exact_street_no_confident_civic"
    assert result.candidate is not None
    assert result.candidate.precision_code == "street"
    assert result.candidate.house_number is None
    assert result.candidate.latitude == pytest.approx(39.20)
    assert result.candidate.longitude == pytest.approx(16.20)


def test_same_normalised_street_key_with_multiple_official_street_ids_is_ambiguous(tmp_path):
    path = write_anncsu(
        tmp_path,
        [
            row("S5", "VIA DUPLICATA", "E1", "1"),
            row("S6", "VIA DUPLICATA", "F1", "1"),
        ],
    )
    result = resolve_anncsu_addresses(
        ["COSENZA Via Duplicata 1"], municipality_matcher=matcher(), anncsu_csv=path
    )[0]
    assert result.status == "exact_street_ambiguous"
    assert result.candidate is None


def test_missing_exact_street_remains_explicit(tmp_path):
    path = write_anncsu(tmp_path, [row("S7", "VIA ESISTENTE", "G1", "1")])
    result = resolve_anncsu_addresses(
        ["COSENZA Via Inesistente 1"], municipality_matcher=matcher(), anncsu_csv=path
    )[0]
    assert result.status == "no_exact_street_match"
    assert result.candidate is None
