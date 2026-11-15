import copy
import json

import pytest

from white_list_archive.publishing import public_national_build as build
from test_preserved_public_editions import setup


def test_scope_binding_collection_is_explicit_and_rejects_duplicates_and_absence(tmp_path):
    one = {'schema_version': 2, 'source': {'source_key': 'one'}, 'records_sha256': 'a'*64}
    two = {'schema_version': 2, 'source': {'source_key': 'two'}, 'records_sha256': 'b'*64}
    path = tmp_path/'binding.json'
    def write(bindings): path.write_text(json.dumps({'schema_version': 3, 'bindings': bindings}))
    write([one, two])
    assert build._read_scope_binding(path, {'source_key': 'two'}) == two
    with pytest.raises(ValueError): build._read_scope_binding(path, {'source_key': 'absent'})
    write([one, one])
    with pytest.raises(ValueError, match='duplicate'): build._read_scope_binding(path, {'source_key': 'one'})
    path.write_text(json.dumps(one))
    assert build._read_scope_binding(path, {'source_key': 'one'}) == one


def test_existing_explicit_physical_parser_identity_can_be_preserved_but_unrelated_parser_cannot(monkeypatch, tmp_path):
    config, approved, calls, manifest = setup(monkeypatch, tmp_path)
    cfg = config['sources'][0]
    cfg['parser'] = 'cosenza_combined_v2'
    approved['records'][0]['parser_name'] = build.DECLARED_PARSER_IDENTITIES[cfg['parser']]
    approved['meta']['sources'][0]['parser'] = cfg['parser']
    result = build._build_registry_from_selected_inputs(config, tmp_path, None,
        preserved_source_keys=('preserved',), public_snapshot_manifest=manifest)
    assert result['records'][1] == approved['records'][0]
    calls.clear()
    approved['records'][0]['parser_name'] = 'unreviewed-other-family'
    with pytest.raises(ValueError, match='parser provenance'):
        build._build_registry_from_selected_inputs(config, tmp_path, None,
            preserved_source_keys=('preserved',), public_snapshot_manifest=manifest)
    assert calls == []


def test_bundle_collection_never_substitutes_a_different_scope_or_changed_report(monkeypatch, tmp_path):
    config, approved, calls, manifest = setup(monkeypatch, tmp_path)
    cfg = config['sources'][0]
    cfg['resources'] = {'I': {'resource_url': 'https://example.test/one.pdf', 'sha256': 'f'*64}}
    record = {'schema_version': 2, 'snapshot_tag': 'public-data-original', 'purpose': 'synthetic scope',
              'source': copy.deepcopy(cfg), 'records_sha256': build._public_scope_digest(approved['records']),
              'report_sha256': build._public_scope_digest(approved['meta']['sources'][0])}
    path = tmp_path/'binding.json'
    path.write_text(json.dumps({'schema_version': 3, 'bindings': [record]}))
    monkeypatch.setattr(build, 'APPROVED_BUNDLE_PUBLIC_DERIVATIVE_BINDING', path)
    result = build._build_registry_from_selected_inputs(config, tmp_path, None,
        preserved_source_keys=('preserved',), public_snapshot_manifest=manifest)
    assert result['records'][1] == approved['records'][0]
    calls.clear()
    approved['meta']['sources'][0]['document_checked_at'] = '2026-11-15T00:00:00Z'
    with pytest.raises(ValueError):
        build._build_registry_from_selected_inputs(config, tmp_path, None,
            preserved_source_keys=('preserved',), public_snapshot_manifest=manifest)
    assert calls == []
