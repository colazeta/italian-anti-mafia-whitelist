from pathlib import Path

import pytest

from white_list_archive.publishing.public_national_build import (
    _alias_publication_config,
    _canonicalise_prefecture_authority_keys,
)

ROOT = Path(__file__).resolve().parents[1]
ALIASES = ROOT / "data/source_registry/national_index_authority_aliases.csv"


def test_publication_config_alias_preserves_canonical_source_identity():
    canonical = {
        "source_key": "pesaro-urbino-combined",
        "authority_key": "pesaro-e-urbino",
        "register_key": "pesaro-urbino-ordinary",
        "reference_date": "2026-08-31",
    }
    config = {"sources": [canonical]}

    aliased = _alias_publication_config(config, ALIASES)

    assert config["sources"] == [canonical]
    assert len(aliased["sources"]) == 2
    assert aliased["sources"][0] == canonical
    national = aliased["sources"][1]
    assert national["authority_key"] == "pesaro-urbino"
    assert national["source_key"] == canonical["source_key"]
    assert national["register_key"] == canonical["register_key"]
    assert national["reference_date"] == canonical["reference_date"]


def test_publication_config_alias_does_not_duplicate_existing_national_key():
    config = {
        "sources": [
            {"source_key": "canonical", "authority_key": "pesaro-e-urbino"},
            {"source_key": "national", "authority_key": "pesaro-urbino"},
        ]
    }

    aliased = _alias_publication_config(config, ALIASES)

    assert len(aliased["sources"]) == 2


def test_prefecture_directory_uses_canonical_authority_identity_after_alias_join():
    payload = {
        "meta": {"authority_count": 2, "mapped_count": 2, "published_count": 1},
        "prefectures": [
            {
                "authority_key": "pesaro-urbino",
                "jurisdiction_name": "Pesaro e Urbino",
                "published": True,
            },
            {
                "authority_key": "bolzano",
                "jurisdiction_name": "Bolzano",
                "published": False,
            },
        ],
    }

    canonical = _canonicalise_prefecture_authority_keys(payload, ALIASES)

    assert payload["prefectures"][0]["authority_key"] == "pesaro-urbino"
    assert [row["authority_key"] for row in canonical["prefectures"]] == [
        "pesaro-e-urbino",
        "bolzano-bozen",
    ]
    assert canonical["meta"] == payload["meta"]
    assert canonical["prefectures"][0]["jurisdiction_name"] == "Pesaro e Urbino"


def test_prefecture_directory_alias_collision_fails_closed(tmp_path: Path):
    aliases = tmp_path / "aliases.csv"
    aliases.write_text(
        "national_index_key,catalog_authority_key,reason\n"
        "source-key,canonical-key,test\n",
        encoding="utf-8",
    )
    payload = {
        "meta": {"authority_count": 2},
        "prefectures": [
            {"authority_key": "source-key"},
            {"authority_key": "canonical-key"},
        ],
    }

    with pytest.raises(RuntimeError, match="Authority alias collision"):
        _canonicalise_prefecture_authority_keys(payload, aliases)
