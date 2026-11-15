import json

import pytest

from white_list_archive.acquisition import release_readiness as readiness
from test_biella_parser_semantics import _source_html


def test_explicit_date_keeps_page_update_separate_from_capture_and_ignores_scripts():
    raw = b'<script>Ultimo aggiornamento 30 dicembre 2029</script><p>Ultimo aggiornamento</p><time>6 novembre 2026, 12:00</time>'
    assert readiness.explicit_update_date(raw, '2026-11-15T12:00:00Z') == '2026-11-06'
    assert readiness.explicit_update_date('Ultimo aggiornamento Giovedì 12 Novembre 2026, ore 10:49'.encode(),
                                         '2026-11-15T12:00:00Z') == '2026-11-12'


@pytest.mark.parametrize('text', [
    'No declared source date', 'Ultimo aggiornamento 31 febbraio 2026',
    'Ultimo aggiornamento 16 novembre 2026',
    'Ultimo aggiornamento 3 novembre 2026 Ultimo aggiornamento 4 novembre 2026',
    'Ultimo aggiornamento Lunedì 12 Novembre 2026',
])
def test_missing_invalid_ambiguous_future_dates_fail_closed(text):
    with pytest.raises(ValueError):
        readiness.explicit_update_date(text.encode(), '2026-11-15T12:00:00Z')


def test_biella_census_accounts_for_every_row_and_rejects_silently_skipped_widths(tmp_path):
    path = tmp_path/'source.html'
    path.write_text(_source_html())
    assert readiness.biella_complete_physical_rows(path, 'listed') == 10
    assert readiness.biella_complete_physical_rows(path, 'applicant') == 3
    # The legacy parser skips this 3-cell row. Readiness must quarantine it.
    text = _source_html().replace('</table>', '<tr><td>unknown source row</td><td>details</td><td>123</td></tr></table>', 1)
    path.write_text(text)
    with pytest.raises(ValueError, match='Unclassified'):
        readiness.biella_complete_physical_rows(path, 'applicant')


def test_authorities_and_populations_are_independent_and_never_approved():
    jobs = [{'source_key': a+'-'+p, 'config': {'authority_key': a, 'population_scope': p}}
            for a in ('biella', 'como') for p in ('listed', 'applicant')]
    def inspect(job):
        if job['source_key'] == 'biella-listed': raise ValueError('private source data')
        return {'source_key': job['source_key'], 'status': 'source_candidate_requires_review', 'publication_approved': False}
    report = readiness.triage(jobs, inspect)
    assert [r['status'] for r in report['results']] == ['requires_source_review', 'review_metadata_ready', 'incomplete_population_inputs']
    assert report['approvals'] == report['publications'] == 0
    assert 'private source data' not in json.dumps(report)


def test_public_readiness_is_closed_against_private_diagnostics_and_messages():
    report = {'kind': 'archived-release-readiness', 'results': [{'authority_key': 'biella', 'status': 'review_metadata_ready', 'sources': [{
        'source_key': 'biella-listed', 'status': 'source_candidate_requires_review', 'publication_approved': False,
        'private_text': 'sensitive fixture', 'diagnostics': {'sector_rows': 10, 'rows': ['sensitive fixture'],
        'identifier_coverage': 'sensitive fixture', 'status_counts': {'listed': 3, 'sensitive fixture': 2}}}]}]}
    safe = readiness.public_summary(report)
    assert 'sensitive fixture' not in json.dumps(safe)
    assert safe['results'][0]['sources'][0]['quality_counts'] == {'sector_rows': 10}
    assert safe['publications'] == safe['approvals'] == 0


def test_source_inspection_uses_verified_original_and_never_reuses_old_date(monkeypatch):
    from test_biella_parser_semantics import _cfg
    import hashlib
    raw = (_source_html() + '<p>Ultimo aggiornamento Giovedì 12 Novembre 2026, ore 10:49</p>').encode()
    sha = hashlib.sha256(raw).hexdigest()
    cfg = {**_cfg('listed'), 'parser': 'biella_html_listed', 'expected_source_rows': 8}
    job = {'source_key': 'biella-listed', 'config': cfg,
           'captures': {'primary': {'url': cfg['resource_url'], 'state': {'sha256': sha}}}}
    monkeypatch.setattr(readiness.transform, '_verified_capture', lambda store, entry: (
        {'sha256': sha, 'byte_size': len(raw), 'captured_at': '2026-11-15T12:00:00Z'}, {}, raw))
    result = readiness.inspect_job(job, object())
    assert result['records'] == 9 and result['physical_rows'] == 10
    assert result['reference_date'] == '2026-11-12'
    assert result['previous_reference_date'] == '2026-08-26'
    assert result['previous_edition_qa_differences'] == ['source_row_count_changed']
    assert result['publication_approved'] is False
    assert result['original_and_capture_provenance_verified'] is True
