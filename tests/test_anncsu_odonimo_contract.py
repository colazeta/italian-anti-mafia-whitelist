import csv

from white_list_archive.geocoding.anncsu_linkage import (
    _official_street_name,
    resolve_anncsu_addresses,
)
from white_list_archive.geocoding.italian_address import (
    MunicipalityPrefixMatcher,
    MunicipalityRecord,
)

FIELDS = [
    "CODICE_COMUNE", "CODICE_ISTAT", "PROGRESSIVO_NAZIONALE",
    "CODICE_COMUNALE", "ODONIMO", "LOCALITA'", "DIZIONE_LINGUA1",
    "DIZIONE_LINGUA2", "PROGRESSIVO_ACCESSO", "CODICE_COMUNALE_ACCESSO",
    "CIVICO", "ESPONENTE", "SPECIFICITA", "METRICO", "PROGRESSIVO_SNC",
    "COORD_X_COMUNE", "COORD_Y_COMUNE", "QUOTA", "METODO",
]


def matcher():
    return MunicipalityPrefixMatcher(
        [MunicipalityRecord("078045", "Cosenza", "Cosenza", "CS", "Calabria", "D086")]
    )


def test_language_field_is_never_used_as_street_name_or_match_key(tmp_path):
    row = {field: "" for field in FIELDS}
    row.update(
        {
            "CODICE_COMUNE": "D086",
            "CODICE_ISTAT": "078045",
            "PROGRESSIVO_NAZIONALE": "S1",
            "ODONIMO": "VIA GIANGURGOLO",
            "DIZIONE_LINGUA1": "ITALIANA",
            "PROGRESSIVO_ACCESSO": "A1",
            "CIVICO": "3",
            "COORD_X_COMUNE": "16,25",
            "COORD_Y_COMUNE": "39,30",
            "METODO": "3",
        }
    )
    path = tmp_path / "INDIR_CALA_20260803.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, delimiter=";")
        writer.writeheader()
        writer.writerow(row)

    assert _official_street_name([row]) == "VIA GIANGURGOLO"

    correct = resolve_anncsu_addresses(
        ["COSENZA Via Giangurgolo 3"],
        municipality_matcher=matcher(),
        anncsu_csv=path,
    )[0]
    assert correct.candidate is not None
    assert correct.candidate.street_name == "VIA GIANGURGOLO"

    false_language_match = resolve_anncsu_addresses(
        ["COSENZA Via Italiana 3"],
        municipality_matcher=matcher(),
        anncsu_csv=path,
    )[0]
    assert false_language_match.status == "no_exact_street_match"
    assert false_language_match.candidate is None
