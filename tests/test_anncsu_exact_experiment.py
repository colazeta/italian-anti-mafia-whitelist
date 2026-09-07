from white_list_archive.geocoding.anncsu_exact_experiment import (
    canonical_street_key,
    parse_source_street_and_civic,
)


def test_street_key_normalises_but_preserves_road_type():
    assert canonical_street_key("Via Nazionale") == "via|nazionale"
    assert canonical_street_key("C/da Padula") == "contrada|padula"
    assert canonical_street_key("CONTRADA SCANNELLE") == "contrada|scannelle"
    assert canonical_street_key("S.S. 18") == "ss|18"
    assert canonical_street_key("STRADA STATALE 18") == "ss|18"
    assert canonical_street_key("Via IV Novembre") == "via|iv novembre"


def test_distinct_road_types_with_same_name_do_not_collapse():
    assert canonical_street_key("Via Roma") != canonical_street_key("Piazza Roma")
    assert canonical_street_key("Via Petraro") != canonical_street_key("Contrada Petraro")


def test_terminal_civic_and_exponent_are_parsed_conservatively():
    parsed = parse_source_street_and_civic("VIA VERDI 33/A")
    assert parsed.status == "civic"
    assert parsed.street_text == "VIA VERDI"
    assert parsed.number == "33"
    assert parsed.exponent == "A"


def test_explicit_no_civic_is_not_mistaken_for_route_number():
    parsed = parse_source_street_and_civic("VIA CRISTOFORO COLOMBO SS 19 SN")
    assert parsed.status == "explicit_no_civic"
    assert parsed.street_text == "VIA CRISTOFORO COLOMBO SS 19"
    assert parsed.number is None


def test_numeric_range_is_not_silently_reduced_to_one_civic():
    parsed = parse_source_street_and_civic("Via Madre Isabella De Rosis 63/65")
    assert parsed.status == "no_confident_terminal_civic"
    assert parsed.number is None


def test_plain_terminal_civic_is_parsed():
    parsed = parse_source_street_and_civic("Via Nazionale, 17")
    assert parsed.status == "civic"
    assert parsed.street_text == "Via Nazionale"
    assert parsed.number == "17"
    assert parsed.exponent is None
