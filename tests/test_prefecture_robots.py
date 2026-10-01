import csv
from copy import deepcopy
import json
from pathlib import Path
from urllib.error import HTTPError

import pytest

from white_list_archive.acquisition.prefecture_robots import (
    digest, discover_links, generate_catalog, published_sheet_redirect, run_robot, validate_catalog,
)
from test_archive_first_replay import store

ROOT = Path(__file__).resolve().parents[1]
PAGE = 'https://prefettura.example/white-list'
PDF = 'https://prefettura.example/elenco.pdf'


def robot():
    return {'authority_key': 'fixture', 'name': 'Fixture', 'landing_pages': [PAGE],
            'allowed_hosts': ['prefettura.example'], 'max_depth': 2, 'max_requests': 10,
            'time_budget_seconds': 10, 'population_mapping_reviewed': True,
            'sources': [{'source_key': 'fixture-listed', 'url': PDF,
                         'approved_sha256': digest(b'%PDF-original')} ]}


def response(url, body=b'%PDF-original'):
    return {'status': 200, 'body': body, 'resolved_url': url,
            'content_type': 'text/html' if url == PAGE else 'application/pdf', 'etag': 'v1'}


def fetch(url, *args, **kwargs):
    return response(url, b'<a href="/elenco.pdf">Elenco iscritti</a>' if url == PAGE else b'%PDF-original')


@pytest.fixture
def run(tmp_path):
    evidence = store()
    def invoke(*args, **kwargs):
        kwargs.setdefault('store', evidence)
        kwargs.setdefault('work_dir', tmp_path)
        return run_robot(*args, **kwargs)
    return invoke


def test_every_authority_has_a_reproducible_dedicated_robot():
    catalog = json.loads((ROOT/'data/source_registry/prefecture_robots.json').read_text())
    with (ROOT/'data/source_registry/territorial_authorities.csv').open() as f:
        keys = [r['authority_key'] for r in csv.DictReader(f)]
    validate_catalog(catalog, keys)
    assert len(catalog['robots']) == 106
    assert catalog == generate_catalog(ROOT)
    assert len({r['authority_key'] for r in catalog['robots'] if r['sources']}) == 75


def test_deduplicate_pages_and_resources_and_detect_same_url_change(run):
    r = robot(); r['landing_pages'].append(PDF)
    first = run(r, fetch=fetch, pause=0)
    assert first['requests'] == 2
    assert first['status'] == 'baseline'
    assert first['resources'][PDF]['role'] == 'source'
    second = run(r, first, fetch=lambda u, *a, **k: fetch(u) if u == PAGE else response(u, b'%PDF-new'), pause=0)
    assert second['status'] == 'changed'
    assert second['changed_urls'] == [PDF]
    assert second['publication_approved'] is False


def test_failure_preserves_previous_identity_and_success_time(run):
    first = run(robot(), fetch=fetch, pause=0)
    def failing(url, *a, **k):
        if url == PDF: raise HTTPError(url, 503, 'unavailable', {}, None)
        return fetch(url)
    second = run(robot(), first, fetch=failing, pause=0)
    assert second['status'] == 'partial'
    assert second['resources'][PDF] == first['resources'][PDF]
    assert second['last_successful_check_at'] == first['last_successful_check_at']
    assert second['errors'][0]['http_status'] == 503


def test_capture_after_legacy_check_refetches_304_and_keeps_separate_temporal_checks(tmp_path, run):
    evidence = store()
    first = run(robot(), fetch=fetch, pause=0)
    for item in first['resources'].values():
        item.pop('capture_history')
        item['capture_ids'] = []
        item['archived_sha256'] = None
    calls = []
    def conditional(url, old, hosts, force=False):
        calls.append((url, force))
        return fetch(url) if force or url == PAGE else {'status': 304}
    captured = run(robot(), first, mode='capture', store=evidence, work_dir=tmp_path,
                         fetch=conditional, pause=0)
    assert captured['status'] == 'unchanged'
    assert (PDF, True) in calls
    resource = captured['resources'][PDF]
    assert resource['archived_sha256'] == digest(b'%PDF-original')
    assert len(resource['capture_ids']) == 1
    assert len(resource['capture_history']) == 1

    first_capture_id = resource['capture_ids'][0]
    again = run(robot(), captured, mode='capture', store=evidence, work_dir=tmp_path,
                      fetch=conditional, pause=0)
    assert again['captured_urls'] == [PDF]
    resource = again['resources'][PDF]
    assert len(resource['capture_ids']) == 1
    assert resource['capture_ids'][0] != first_capture_id
    assert len(resource['capture_history']) == 2
    assert [item['sha256'] for item in resource['capture_history']] == [
        digest(b'%PDF-original'), digest(b'%PDF-original')
    ]
    assert len({item['capture_id'] for item in resource['capture_history']}) == 2
    assert {item['source_key'] for item in resource['capture_history']} == {'fixture-listed'}
    assert all(item['captured_at'] for item in resource['capture_history'])


def test_capture_history_retains_changed_bytes_and_reappearance(tmp_path, run):
    evidence = store()
    def with_pdf(body):
        def _fetch(url, *args, **kwargs):
            if url == PAGE:
                return response(url, b'<a href="/elenco.pdf">Elenco iscritti</a>')
            return response(url, body)
        return _fetch

    first = run(robot(), mode='capture', store=evidence, work_dir=tmp_path,
                      fetch=with_pdf(b'%PDF-original'), pause=0)
    second = run(robot(), first, mode='capture', store=evidence, work_dir=tmp_path,
                       fetch=with_pdf(b'%PDF-new'), pause=0)
    third = run(robot(), second, mode='capture', store=evidence, work_dir=tmp_path,
                      fetch=with_pdf(b'%PDF-original'), pause=0)

    history = third['resources'][PDF]['capture_history']
    assert [item['sha256'] for item in history] == [
        digest(b'%PDF-original'), digest(b'%PDF-new'), digest(b'%PDF-original')
    ]
    assert len({item['capture_id'] for item in history}) == 3
    assert history[0]['capture_id'] != history[2]['capture_id']
    assert third['resources'][PDF]['archived_sha256'] == digest(b'%PDF-original')


def test_legacy_capture_ids_are_retained_without_inventing_old_timestamps(tmp_path, run):
    evidence = store()
    first = run(robot(), mode='capture', store=evidence, work_dir=tmp_path,
                      fetch=fetch, pause=0)
    legacy = deepcopy(first)
    legacy_resource = legacy['resources'][PDF]
    original_capture_id = legacy_resource['capture_ids'][0]
    legacy_resource.pop('capture_history')

    second = run(robot(), legacy, mode='capture', store=evidence, work_dir=tmp_path,
                       fetch=fetch, pause=0)
    history = second['resources'][PDF]['capture_history']
    assert history[0]['capture_id'] == original_capture_id
    assert history[0]['source_key'] == 'fixture-listed'
    assert history[0]['sha256'] == digest(b'%PDF-original')
    assert history[0]['captured_at'] is None
    assert history[0]['reference_date'] is None
    assert history[1]['capture_id'] != original_capture_id
    assert history[1]['captured_at'] is not None


def test_new_document_is_discovered_without_guessing_population_binding(run):
    def updated(url, *a, **k):
        return response(url, b'<a href="/elenco-nuovo.pdf">Elenco iscritti aggiornato</a>') if url == PAGE else fetch(url)
    report = run(robot(), fetch=updated, pause=0)
    new = 'https://prefettura.example/elenco-nuovo.pdf'
    assert new in report['discovered_documents']
    assert report['resources'][new]['source_keys'] == []
    assert report['resources'][new]['role'] == 'candidate'


def test_bounds_and_rejected_document_response_do_not_claim_success(run):
    r = robot(); r['max_requests'] = 1
    report = run(r, fetch=fetch, pause=0)
    assert report['status'] == 'partial' and PDF in report['pending_urls']
    report = run(robot(), fetch=lambda u, *a, **k: {**fetch(u), 'content_type': 'text/html'}, pause=0)
    assert report['status'] == 'partial'
    assert 'sha256' not in report['resources'][PDF]
    assert report['resources'][PDF]['capture_history']


def test_discovery_leaves_external_origins_for_review():
    docs, pages, external = discover_links(b'<a href="https://other.example/list.pdf">Elenco</a><a href="/modello.pdf">Modulo istanza</a><a href="/listed.pdf">Elenco</a>', PAGE, ['prefettura.example'])
    assert docs == ['https://prefettura.example/listed.pdf']
    assert external == ['https://other.example/list.pdf']


@pytest.mark.parametrize('mode', ['check', 'capture'])
def test_capture_requires_configured_store_before_any_fetch(mode):
    calls = []
    with pytest.raises(ValueError, match='store'):
        run_robot(robot(), mode=mode, fetch=lambda *a, **k: calls.append(a))
    assert calls == []


def test_legacy_check_mode_cannot_discard_acquired_evidence(tmp_path, run):
    evidence = store()
    first = run(robot(), mode='check', store=evidence, fetch=fetch, pause=0)
    second = run(robot(), first, mode='check', store=evidence, fetch=fetch, pause=0)
    assert second['mode'] == 'capture'
    assert second['requested_mode'] == 'check'
    history = second['resources'][PDF]['capture_history']
    assert len(history) == 2
    assert len({item['capture_id'] for item in history}) == 2
    assert len([key for key in evidence.client.objects if key.startswith('sha256/')]) == 2
    assert len([key for key in evidence.client.objects if key.startswith('captures/')]) == 3


@pytest.mark.parametrize('mime', ['text/html', 'application/xhtml+xml'])
def test_rejected_document_keeps_exact_evidence_and_previous_accepted_state(mime, run):
    evidence = store()
    first = run(robot(), store=evidence, fetch=fetch, pause=0)
    original = deepcopy(first)
    rejected = b'<html>Access check, not a PDF</html>'
    def changed(url, *a, **k):
        return fetch(url) if url == PAGE else {**response(url, rejected), 'content_type': mime}
    second = run(robot(), first, store=evidence, fetch=changed, pause=0)
    assert first == original
    assert second['status'] == 'partial'
    assert second['last_successful_check_at'] == first['last_successful_check_at']
    resource = second['resources'][PDF]
    for key, value in first['resources'][PDF].items():
        if key != 'capture_history':
            assert resource[key] == value
    capture = resource['capture_history'][-1]
    assert capture['sha256'] == digest(rejected)
    assert capture['content_type'] == mime
    assert capture['reference_date'] is None
    assert capture['captured_at']
    records = [json.loads(body) for key, body in evidence.client.objects.items() if key.startswith('captures/')]
    record = next(item for item in records if item['capture_id'] == capture['capture_id'])
    assert evidence.read_verified(record['capture_manifest']) == rejected
    assert second['errors'][0]['stage'] == 'response_validation'
    assert second['errors'][0]['verified_capture_ids'] == [capture['capture_id']]
    assert PDF in second['captured_urls']
    assert PDF not in second['changed_urls']
    assert second['publication_approved'] is False


def test_partial_multi_scope_archive_retains_completed_capture(monkeypatch, run):
    from white_list_archive.acquisition import prefecture_robots as module
    evidence = store()
    first = run(robot(), store=evidence, fetch=fetch, pause=0)
    r = robot()
    r['sources'].append({**r['sources'][0], 'source_key': 'fixture-other'})
    real_archive = module.archive_payload
    def failing_archive(**kwargs):
        if kwargs['source_key'] == 'fixture-other':
            raise RuntimeError('private provider coordinates must not escape')
        return real_archive(**kwargs)
    monkeypatch.setattr(module, 'archive_payload', failing_archive)
    second = run(r, first, store=evidence, fetch=fetch, pause=0)
    history = second['resources'][PDF]['capture_history']
    assert len(history) == 2
    assert history[-1]['capture_id'] != history[0]['capture_id']
    assert second['resources'][PDF]['capture_ids'] == first['resources'][PDF]['capture_ids']
    assert second['resources'][PDF]['last_checked_at'] == first['resources'][PDF]['last_checked_at']
    assert second['status'] == 'partial'
    assert second['errors'][0]['stage'] == 'archive'
    assert second['errors'][0]['verified_capture_ids'] == [history[-1]['capture_id']]
    assert 'private provider' not in json.dumps(second)


def test_unexpected_304_is_refetched_once_for_new_temporal_capture(run):
    first = run(robot(), fetch=fetch, pause=0)
    calls = []
    def conditional(url, old, hosts, force=False):
        if url == PDF:
            calls.append(force)
            if len(calls) == 1:
                return {'status': 304}
        return fetch(url)
    second = run(robot(), first, fetch=conditional, pause=0)
    assert calls == [True, True]
    assert second['status'] == 'unchanged'
    assert len(second['resources'][PDF]['capture_history']) == 2


def test_html_table_also_used_as_landing_page_is_reread_for_new_links(run):
    r = robot()
    r['sources'].append({'source_key': 'fixture-combined', 'url': PAGE,
                         'approved_sha256': digest(b'old HTML')})
    seen = []
    def conditional(url, old, hosts, force=False):
        seen.append((url, force))
        return fetch(url) if force or not old else {'status': 304}
    first = run(r, fetch=conditional, pause=0)
    run(r, first, fetch=conditional, pause=0)
    assert [force for url, force in seen if url == PAGE] == [True, True]


def test_large_scan_resumes_until_complete_without_starving_documents(run):
    r = robot(); r['max_requests'] = 4
    docs = [f'https://prefettura.example/elenco-{i}.pdf' for i in range(7)]
    calls = []
    def many(url, *a, **k):
        calls.append(url)
        return response(url, ''.join(f'<a href="{u}">Elenco</a>' for u in docs).encode()) if url == PAGE else fetch(url)
    report = None
    remaining = []
    for index in range(4):
        report = run(r, report, fetch=many, pause=0)
        remaining.append(len(report['pending_urls']))
        assert report['requests'] <= 4
        if index == 0:
            started = report['cycle_started_at']
        assert report['cycle_started_at'] == started
    assert remaining == [5, 3, 1, 0]
    assert report['status'] != 'partial'
    assert report['last_successful_check_at'] == report['checked_at']
    assert all(calls.count(url) == 1 for url in docs)
    assert calls.count(PAGE) == calls.count(PDF) == 4
    assert calls.index(docs[-1]) < calls.index(docs[0])
    again = run(r, report, fetch=many, pause=0)
    assert again['cycle_started_at'] != started
    assert len(again['pending_urls']) == 5


def test_legacy_frontier_resumes_and_new_links_are_not_skipped(run):
    r = robot(); r['max_requests'] = 3
    docs = [f'https://prefettura.example/elenco-{i}.pdf' for i in range(3)]
    def many(url, *a, **k):
        return response(url, ''.join(f'<a href="{u}">Elenco</a>' for u in docs).encode()) if url == PAGE else fetch(url)
    first = run(r, fetch=many, pause=0)
    first.pop('pending_queue'); first.pop('cycle_started_at')
    docs.append('https://prefettura.example/elenco-9.pdf')
    second = run(r, first, fetch=many, pause=0)
    assert docs[-1] in second['resources']
    assert second['cycle_started_at'] == first['checked_at']
    assert len(second['pending_urls']) == 2


def test_pending_page_preserves_depth_across_runs(run):
    r = robot(); r['max_requests'] = 3
    pages = [f'https://prefettura.example/white-list-{i}' for i in range(3)]
    called = []
    def nested(url, *a, **k):
        called.append(url)
        if url == PDF: return fetch(url)
        target = pages[0] if url == PAGE else pages[pages.index(url)+1]
        return {**response(url, f'<a href="{target}">White list</a>'.encode()), 'content_type': 'text/html'}
    first = run(r, fetch=nested, pause=0)
    assert first['pending_queue'] == [{'url': pages[1], 'depth': 2, 'role': 'landing'}]
    second = run(r, first, fetch=nested, pause=0)
    assert second['pending_urls'] == []
    assert pages[2] not in called


def test_regional_site_navigation_does_not_leave_white_list_section():
    page = 'https://www.regione.vda.it/prefettura/Antimafia/white_list/default_i.aspx'
    html = b'<a href="/Portale_imprese/default_i.asp">Imprese</a><a href="/sanita/elenco_i.asp">Elenco allerte</a><a href="/allegato.aspx?pk=123">Elenco imprese</a><a href="elenco_imprese_white_list_i.aspx">Iscritti</a>'
    docs, pages, external = discover_links(html, page, ['www.regione.vda.it'])
    assert docs == ['https://www.regione.vda.it/allegato.aspx?pk=123']
    assert pages == ['https://www.regione.vda.it/prefettura/Antimafia/white_list/elenco_imprese_white_list_i.aspx']
    assert external == []


def test_published_sheet_export_redirect_is_narrowly_scoped():
    source = 'https://docs.google.com/spreadsheets/d/e/reviewed-publication/pub?gid=0&output=csv'
    target = 'https://doc-10-c0-sheets.googleusercontent.com/pub/export'
    assert published_sheet_redirect(source, target, ['docs.google.com'])
    assert not published_sheet_redirect(source, target, ['prefettura.example'])
    assert not published_sheet_redirect(source.replace('output=csv', 'output=html'), target, ['docs.google.com'])
    assert not published_sheet_redirect(source.replace('/pub?', '/edit?'), target, ['docs.google.com'])
    for bad in [target.replace('https:', 'http:'), target.replace('.com/', '.com.evil.example/'),
                target.replace('/pub/', '/other/'), target.replace('https://', 'https://user@'),
                target.replace('doc-10-c0-sheets', 'other')]:
        assert not published_sheet_redirect(source, bad, ['docs.google.com'])
