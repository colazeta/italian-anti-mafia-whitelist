import pytest

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch
from white_list_archive.publishing.public_national_registry import _apply_parser_lineage


def test_parser_declared_revision_is_preserved_over_legacy_fallback():
    batch = ParsedBatch(records=[{}], diagnostics={"parser_version": "7"})
    result = _apply_parser_lineage(batch, "fixture_parser", "1")
    assert result.records[0]["parser_name"] == "fixture_parser"
    assert result.records[0]["parser_version"] == "7"


def test_legacy_revision_is_used_only_when_parser_does_not_declare_one():
    batch = ParsedBatch(records=[{}], diagnostics={})
    result = _apply_parser_lineage(batch, "legacy_parser", "2")
    assert result.records[0]["parser_version"] == "2"


def test_conflicting_record_lineage_fails_closed():
    batch = ParsedBatch(records=[{"parser_version": "3"}], diagnostics={"parser_version": "4"})
    with pytest.raises(RuntimeError, match="conflicting parser-version lineage"):
        _apply_parser_lineage(batch, "fixture_parser", "1")
