from pathlib import Path

from white_list_archive.publishing.public_national_build import _alias_publication_config

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
