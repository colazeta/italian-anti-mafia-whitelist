import csv
from copy import deepcopy
import json
from pathlib import Path
from urllib.error import HTTPError

import pytest

from white_list_archive.acquisition.prefecture_robots import (
    digest, discover_links, generate_catalog, run_robot, validate_catalog,
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


def test_every_authority_has_a_reproducible_dedicated_robot():
    catalog = json.loads((ROOT/'data/source_registry/prefecture_robots.json').read_text())
    with (ROOT/'data/source_registry/territorial_authorities.csv').open() as f:
        keys = [r['authority_key'] for r in csv.DictReader(f)]
    validate_catalog(catalog, keys)
    assert len(catalog['robots']) == 106
    assert catalog == generate_catalog(ROOT)
    assert len({r['authority_key'] for r in catalog['robots'] if r['sources']}) == 74


def test_deduplicate_pages_and_resources_and_detect_same_url_change():
    r = robot(); r['landing_pages'].append(PDF)
    first = run_robot(r, fetch=fetch, pause=0)
    assert first['requests'] == 2
    assert first['status'] == 'baseline'
    assert first['resources'][PDF]['role'] == 'source'
    second = run_robot(r, first, fetch=lambda u, *a, **k: fetch(u) if u == PAGE else response(u, b'%PDF-new'), pause=0)
    assert second['status'] == 'changed'
    assert second['changed_urls'] == [PDF]
    assert second['publication_approved'] is False


def test_failure_preserves_previous_identity_and_success_time():
    first = run_robot(robot(), fetch=fetch, pause=0)
    def failing(url, *a, **k):
        if url == PDF: raise HTTPError(url, 503, 'unavailable', {}, None)
        return fetch(url)
    second = run_robot(robot(), first, fetch=failing, pause=0)
    assert second['status'] == 'partial'
    assert second['resources'][PDF] == first['resources'][PDF]
    assert second['last_successful_check_at'] == first['last_successful_check_at']
    assert second['errors'][0]['http_status'] == 503


def test_capture_after_check_refetches_304_and_keeps_originals(tmp_path):
    evidence = store()
    first = run_robot(robot(), fetch=fetch, pause=0)
    calls = []
    def conditional(url, old, hosts, force=False):
        calls.append((url, force))
        return fetch(url) if force or url == PAGE else {'status': 304}
    captured = run_robot(robot(), first, mode='capture', store=evidence, work_dir=tmp_path,
                         fetch=conditional, pause=0)
    assert captured['status'] == 'unchanged'
    assert (PDF, True) in calls
    assert captured['resources'][PDF]['archived_sha256'] == digest(b'%PDF-original')
    assert len(captured['resources'][PDF]['capture_ids']) == 1
    again = run_robot(robot(), captured, mode='capture', store=evidence, work_dir=tmp_path,
                      fetch=conditional, pause=0)
    assert again['captured_urls'] == []
    assert again['resources'][PDF]['capture_ids'] == captured['resources'][PDF]['capture_ids']


def test_new_document_is_discovered_without_guessing_population_binding():
    def updated(url, *a, **k):
        return response(url, b'<a href="/elenco-nuovo.pdf">Elenco iscritti aggiornato</a>') if url == PAGE else fetch(url)
    report = run_robot(robot(), fetch=updated, pause=0)
    new = 'https://prefettura.example/elenco-nuovo.pdf'
    assert new in report['discovered_documents']
    assert report['resources'][new]['source_keys'] == []
    assert report['resources'][new]['role'] == 'candidate'


def test_bounds_and_rejected_document_response_do_not_claim_success():
    r = robot(); r['max_requests'] = 1
    report = run_robot(r, fetch=fetch, pause=0)
    assert report['status'] == 'partial' and PDF in report['pending_urls']
    report = run_robot(robot(), fetch=lambda u, *a, **k: {**fetch(u), 'content_type': 'text/html'}, pause=0)
    assert report['status'] == 'partial' and PDF not in report['resources']


def test_discovery_leaves_external_origins_for_review():
    docs, pages, external = discover_links(b'<a href="https://other.example/list.pdf">Elenco</a><a href="/modello.pdf">Modulo istanza</a><a href="/listed.pdf">Elenco</a>', PAGE, ['prefettura.example'])
    assert docs == ['https://prefettura.example/listed.pdf']
    assert external == ['https://other.example/list.pdf']


def test_capture_requires_configured_store():
    with pytest.raises(ValueError, match='store'):
        run_robot(robot(), mode='capture')


def test_html_table_also_used_as_landing_page_is_reread_for_new_links():
    r = robot()
    r['sources'].append({'source_key': 'fixture-combined', 'url': PAGE,
                         'approved_sha256': digest(b'old HTML')})
    seen = []
    def conditional(url, old, hosts, force=False):
        seen.append((url, force))
        return fetch(url) if force or not old else {'status': 304}
    first = run_robot(r, fetch=conditional, pause=0)
    run_robot(r, first, fetch=conditional, pause=0)
    assert [force for url, force in seen if url == PAGE] == [True, True]


def test_large_scan_resumes_until_complete_without_starving_documents():
    r = robot(); r['max_requests'] = 4
    docs = [f'https://prefettura.example/elenco-{i}.pdf' for i in range(7)]
    calls = []
    def many(url, *a, **k):
        calls.append(url)
        return response(url, ''.join(f'<a href="{u}">Elenco</a>' for u in docs).encode()) if url == PAGE else fetch(url)
    report = None
    remaining = []
    for index in range(4):
        report = run_robot(r, report, fetch=many, pause=0)
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
    again = run_robot(r, report, fetch=many, pause=0)
    assert again['cycle_started_at'] != started
    assert len(again['pending_urls']) == 5


def test_legacy_frontier_resumes_and_new_links_are_not_skipped():
    r = robot(); r['max_requests'] = 3
    docs = [f'https://prefettura.example/elenco-{i}.pdf' for i in range(3)]
    def many(url, *a, **k):
        return response(url, ''.join(f'<a href="{u}">Elenco</a>' for u in docs).encode()) if url == PAGE else fetch(url)
    first = run_robot(r, fetch=many, pause=0)
    first.pop('pending_queue'); first.pop('cycle_started_at')
    docs.append('https://prefettura.example/elenco-9.pdf')
    second = run_robot(r, first, fetch=many, pause=0)
    assert docs[-1] in second['resources']
    assert second['cycle_started_at'] == first['checked_at']
    assert len(second['pending_urls']) == 2


def test_pending_page_preserves_depth_across_runs():
    r = robot(); r['max_requests'] = 3
    pages = [f'https://prefettura.example/white-list-{i}' for i in range(3)]
    called = []
    def nested(url, *a, **k):
        called.append(url)
        if url == PDF: return fetch(url)
        target = pages[0] if url == PAGE else pages[pages.index(url)+1]
        return {**response(url, f'<a href="{target}">White list</a>'.encode()), 'content_type': 'text/html'}
    first = run_robot(r, fetch=nested, pause=0)
    assert first['pending_queue'] == [{'url': pages[1], 'depth': 2, 'role': 'landing'}]
    second = run_robot(r, first, fetch=nested, pause=0)
    assert second['pending_urls'] == []
    assert pages[2] not in called
