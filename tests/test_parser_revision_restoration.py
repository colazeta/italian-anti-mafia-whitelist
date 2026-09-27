from __future__ import annotations

import json

import pytest

from white_list_archive.publishing import public_national_build as build


def _registry(records):
    return {"meta": {}, "records": records}


def test_declared_parser_revision_replaces_legacy_generic_stamp(tmp_path, monkeypatch):
    config = {"sources": [{"source_key": "mutable-combined", "parser": "mutable_parser"}]}
    (tmp_path / "mutable-combined.diagnostics.json").write_text(
        json.dumps({"parser": "mutable_parser", "parser_version": "6"}),
        encoding="utf-8",
    )
    registry = _registry(
        [{"source_key": "mutable-combined", "parser_name": "mutable_parser", "parser_version": "1"}]
    )
    monkeypatch.setattr(build, "validate_registry", lambda value: None)

    result = build._restore_declared_parser_revisions(registry, config, tmp_path)

    assert result["records"][0]["parser_version"] == "6"


def test_legacy_parser_without_declared_revision_is_not_guessed(tmp_path, monkeypatch):
    config = {"sources": [{"source_key": "legacy-listed", "parser": "legacy_parser"}]}
    (tmp_path / "legacy-listed.diagnostics.json").write_text(
        json.dumps({"parser": "legacy_parser", "public_records": 1}),
        encoding="utf-8",
    )
    registry = _registry(
        [{"source_key": "legacy-listed", "parser_name": "legacy_parser", "parser_version": "1"}]
    )
    monkeypatch.setattr(build, "validate_registry", lambda value: None)

    result = build._restore_declared_parser_revisions(registry, config, tmp_path)

    assert result["records"][0]["parser_version"] == "1"


def test_parser_identity_drift_fails_closed(tmp_path, monkeypatch):
    config = {"sources": [{"source_key": "alpha", "parser": "alpha_parser"}]}
    (tmp_path / "alpha.diagnostics.json").write_text(
        json.dumps({"parser": "different_parser", "parser_version": "2"}),
        encoding="utf-8",
    )
    registry = _registry(
        [{"source_key": "alpha", "parser_name": "alpha_parser", "parser_version": "1"}]
    )
    monkeypatch.setattr(build, "validate_registry", lambda value: None)

    with pytest.raises(RuntimeError, match="another parser"):
        build._restore_declared_parser_revisions(registry, config, tmp_path)


@pytest.mark.parametrize('adapter,physical', [
    ('ferrara-provincial-listed','ferrara_ordinary'),
    ('ferrara-provincial-applicants','ferrara_applicants'),
    ('ferrara-reconstruction-listed','ferrara_reconstruction_bundle'),
    ('pordenone-provincial-listed','pordenone_listed_bundle'),
    ('pordenone-provincial-applicants','pordenone_applicants'),
])
def test_existing_adapter_bindings_preserve_physical_revision(tmp_path, monkeypatch, adapter, physical):
    config = {'sources':[{'source_key':'reviewed', 'parser':adapter}]}
    path = tmp_path/'reviewed.diagnostics.json'
    path.write_text(json.dumps({'parser':physical,'parser_version':'7'}))
    registry = _registry([{'source_key':'reviewed','parser_name':adapter,'parser_version':'1'}])
    monkeypatch.setattr(build,'validate_registry',lambda value: None)
    result = build._restore_declared_parser_revisions(registry,config,tmp_path)
    assert result['records'][0]['parser_version'] == '7'
    assert result['records'][0]['parser_name'] == adapter
    path.write_text(json.dumps({'parser':physical+'_unreviewed','parser_version':'7'}))
    with pytest.raises(RuntimeError,match='another parser'):
        build._restore_declared_parser_revisions(registry,config,tmp_path)
