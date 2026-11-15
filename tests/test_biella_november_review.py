import hashlib
import json
from pathlib import Path

import pytest

from white_list_archive.publishing import biella_review as review
from white_list_archive.publishing.public_national_registry import _parse_source, _semantic_digest
from test_biella_parser_semantics import _source_html

ROOT = Path(__file__).resolve().parents[1]


def configs():
    return [s for s in json.loads((ROOT/'data/publication/multi_prefecture_pilot.json').read_text())['sources']
            if s['authority_key'] == 'biella']


def test_reviewed_configuration_has_exact_both_populations_and_pinned_archive_original():
    selected = configs()
    assert {s['population_scope'] for s in selected} == {'listed', 'applicant'}
    assert {s['sha256'] for s in selected} == {review.SOURCE_SHA256}
    assert {s['reference_date'] for s in selected} == {'2026-11-12'}
    assert {s['approval_mode'] for s in selected} == {'raw_sha256'}
    preserved = set(json.loads((ROOT/'data/publication/preserved_public_sources.json').read_text()))
    all_keys = {s['source_key'] for s in json.loads((ROOT/'data/publication/multi_prefecture_pilot.json').read_text())['sources']}
    assert preserved == all_keys - set(review.PROFILES)
    assert len(preserved) == 140


def test_full_source_profile_rejects_new_bytes_dates_parser_and_semantics(tmp_path, monkeypatch):
    cfg = next(s for s in configs() if s['population_scope'] == 'listed')
    path = tmp_path/'synthetic.html'
    raw = (_source_html() + '<p>Ultimo aggiornamento Giovedì 12 Novembre 2026, ore 10:49</p>').encode()
    path.write_bytes(raw)
    sha = hashlib.sha256(raw).hexdigest()
    monkeypatch.setattr(review, 'SOURCE_SHA256', sha)
    monkeypatch.setattr(review, 'SOURCE_BYTES', len(raw))
    cfg = {**cfg, 'sha256': sha}
    batch = _parse_source(path, cfg)
    monkeypatch.setattr(review, 'PROFILES', {'biella-listed': {
        'sector_rows': 10, 'public_records': 9, 'semantic_sha256': _semantic_digest(batch.records)}})
    assert len(review.qualify(path, cfg, checked_at='2026-11-15T12:00:00Z').records) == 9
    with pytest.raises(ValueError, match='binding drift'):
        review.qualify(path, {**cfg, 'parser': 'other-family'}, checked_at='2026-11-15T12:00:00Z')
    path.write_bytes(raw+b'changed bytes')
    with pytest.raises(ValueError, match='identity mismatch'):
        review.qualify(path, cfg, checked_at='2026-11-15T12:00:00Z')
    path.write_bytes(raw)
    review.PROFILES['biella-listed']['semantic_sha256'] = '0'*64
    with pytest.raises(ValueError, match='semantics mismatch'):
        review.qualify(path, cfg, checked_at='2026-11-15T12:00:00Z')


def test_bundle_binding_collection_preserves_original_pordenone_and_explicit_ferrara_descriptor():
    binding = json.loads((ROOT/'data/publication/approved_bundle_public_derivative.json').read_text())
    assert binding['schema_version'] == 3
    assert {b['source']['source_key'] for b in binding['bindings']} == {'pordenone-provincial-listed', 'ferrara-reconstruction-listed'}
    for b in binding['bindings']:
        assert b['schema_version'] == 2
        assert len(b['records_sha256']) == len(b['report_sha256']) == 64
