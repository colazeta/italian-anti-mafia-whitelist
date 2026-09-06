from __future__ import annotations

from pathlib import Path

import pytest

from white_list_archive.parsers.registry import (
    load_families,
    load_semantic_profiles,
    select_parser,
    semantic_profile_for_family,
)

ROOT = Path(__file__).resolve().parents[1]
FAMILIES = ROOT / "data/source_registry/parser_families.csv"
BINDINGS = ROOT / "data/source_registry/parser_bindings.csv"
PROFILES = ROOT / "data/source_registry/semantic_profiles.csv"
COSENZA_FP = "fbb124c5a43d26bef93316844b3021096060f7ed9d2cc0f8f6081f6df935dc97"


def test_cosenza_series_selects_explicit_validated_parser_family():
    selection = select_parser(
        "cosenza-combined",
        COSENZA_FP,
        families_path=FAMILIES,
        bindings_path=BINDINGS,
    )
    assert selection.family.code == "cosenza-combined-pdf-bbox-v2"
    assert selection.selection_basis == "explicit_series_binding"
    assert selection.family.record_contract_code == "prefecture-combined-whitelist-v1"


def test_parser_family_and_semantic_profile_share_record_contract():
    family = load_families(FAMILIES)["cosenza-combined-pdf-bbox-v2"]
    profile = semantic_profile_for_family(family, profiles_path=PROFILES)
    assert profile.code == "prefecture-combined-whitelist-v1"
    assert profile.record_contract_code == family.record_contract_code
    assert profile.projector_module == "white_list_archive.semantic.combined_whitelist_v1"


def test_exact_fingerprint_can_reuse_family_without_series_specific_binding():
    selection = select_parser(
        "hypothetical-compatible-series",
        COSENZA_FP,
        families_path=FAMILIES,
        bindings_path=BINDINGS,
    )
    assert selection.family.code == "cosenza-combined-pdf-bbox-v2"
    assert selection.selection_basis == "exact_schema_fingerprint"


def test_unknown_fingerprint_does_not_fall_back_to_guessed_parser():
    with pytest.raises(LookupError):
        select_parser(
            "unknown-series",
            "not-a-known-fingerprint",
            families_path=FAMILIES,
            bindings_path=BINDINGS,
        )


def test_registry_references_are_internally_complete():
    families = load_families(FAMILIES)
    profiles = load_semantic_profiles(PROFILES)
    assert families
    assert profiles
    for family in families.values():
        assert family.semantic_profile_code in profiles
        assert profiles[family.semantic_profile_code].record_contract_code == family.record_contract_code
        assert family.supported_schema_fingerprints
