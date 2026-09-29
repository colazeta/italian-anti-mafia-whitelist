"""One independently runnable robot per authority; shared discovery and capture engine.

Checks compare bytes/links, not administrative editions. New observations are
quarantined until the existing source/parser/publication review has accepted them.
Only safe acquisition metadata belongs in the public robot-state branch.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import csv
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import time
from urllib.error import HTTPError
from urllib.parse import parse_qs, urldefrag, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from white_list_archive.acquisition.archive_first import archive_payload

ROOT = Path(__file__).resolve().parents[3]
CATALOG = Path('data/source_registry/prefecture_robots.json')
USER_AGENT = 'WhiteListResearchRobot/1.0 (+https://github.com/colazeta/italian-anti-mafia-whitelist)'
DOCUMENT = re.compile(r'\.(pdf|xlsx?|docx?|csv|zip)(?:$|\?)|/allegato\.aspx?(?:$|\?)', re.I)
RELEVANT = re.compile(r'white[ _-]*list|elenc|iscritt|richied|istanze|imprese|sezion|aggiornat', re.I)
EXCLUDE = re.compile(r'modulistica|modello|fac.?simile|informativa|privacy|autocertific|istruzioni', re.I)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def generate_catalog(root=Path('.')):
    def csv_rows(name):
        with (root / 'data/source_registry' / name).open() as f:
            return list(csv.DictReader(f))
    authorities = csv_rows('territorial_authorities.csv')
    verified = csv_rows('verified_primary_pages.csv')
    series = csv_rows('source_series_inventory.csv')
    ledger = {x['authority_key']: x for x in json.loads((root/'data/monitoring/national_coverage.json').read_text())['prefectures']}
    publication = json.loads((root/'data/publication/multi_prefecture_pilot.json').read_text())['sources']
    robots = []
    for authority in authorities:
        key = authority['authority_key']
        approved = [x for x in publication if x['authority_key'] == key]
        pages = {ledger[key]['official_landing_page']}
        pages.update(x['landing_url'] for x in verified if x['authority_key'] == key)
        pages.update(x['series_url'] for x in series if x['authority_key'] == key)
        pages.update(x['source_page_url'] for x in approved)
        resources = []
        for source in approved:
            parts = source.get('resources') or {'main': source}
            for part, item in parts.items():
                resources.append({'source_key': source['source_key'], 'part': part,
                    'population_scope': source['population_scope'], 'parser': source['parser'],
                    'url': item['resource_url'], 'approved_sha256': item['sha256']})
        robots.append({'authority_key': key, 'name': authority['jurisdiction_name'],
            'region': authority['region'], 'landing_pages': sorted(pages),
            'allowed_hosts': sorted({urlsplit(u).hostname for u in pages | {x['url'] for x in resources}}),
            'sources': resources, 'population_mapping_reviewed': bool(approved),
            'discovery_source': 'data/monitoring/national_coverage.json',
            'max_depth': 2, 'max_requests': 60, 'time_budget_seconds': 150})
    return {'schema_version': 1, 'robots': robots}


def validate_catalog(catalog, authorities):
    robots = catalog['robots']
    keys = [r['authority_key'] for r in robots]
    if catalog['schema_version'] != 1 or len(keys) != len(set(keys)) or set(keys) != set(authorities):
        raise ValueError('Every canonical authority must have exactly one robot')
    for robot in robots:
        if not robot['landing_pages'] or not re.fullmatch('[a-z0-9-]+', robot['authority_key']):
            raise ValueError('Robot needs a safe identity and a recorded landing page')
        for url in robot['landing_pages'] + [s['url'] for s in robot['sources']]:
            if not allowed(url, robot['allowed_hosts']):
                raise ValueError('Robot URL outside the configured HTTPS origins')


def allowed(url, hosts):
    p = urlsplit(url)
    return p.scheme == 'https' and p.hostname in hosts and not p.username and not p.password and p.port in (None, 443)


class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.links = []; self.current = None
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.current = [dict(attrs).get('href', ''), '']
    def handle_data(self, value):
        if self.current is not None:
            self.current[1] += value
    def handle_endtag(self, tag):
        if tag == 'a' and self.current is not None:
            self.links.append(self.current); self.current = None


def discover_links(data, page_url, hosts):
    parser = Links(); parser.feed(data.decode('utf-8', errors='replace'))
    documents, pages, external = set(), set(), set()
    for href, label in parser.links:
        url = urldefrag(urljoin(page_url, href))[0]
        text = label + ' ' + urlsplit(url).path
        if not RELEVANT.search(text) or EXCLUDE.search(text):
            continue
        if not allowed(url, hosts):
            if urlsplit(url).scheme in ('http', 'https'):
                external.add(url)
        elif DOCUMENT.search(url):
            documents.add(url)
        elif url != page_url:
            # The Ministry shares an origin across all authorities. Do not let
            # its national menu make one robot crawl another Prefecture.
            local = re.match(r'(/it/prefetture/[^/]+/)', urlsplit(page_url).path)
            local = local or re.match(r'(.*/white[ _-]*list/)', urlsplit(page_url).path, re.I)
            if local and not urlsplit(url).path.lower().startswith(local.group(1).lower()):
                continue
            pages.add(url)
    return sorted(documents), sorted(pages), sorted(external)


class ReviewedRedirect(HTTPRedirectHandler):
    def __init__(self, hosts):
        self.hosts = hosts
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed(newurl, self.hosts) and not published_sheet_redirect(req.full_url, newurl, self.hosts):
            raise ValueError('Redirect outside configured HTTPS origins; review required')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def published_sheet_redirect(source, destination, hosts):
    """Allow the observed Google Sheets CSV export hop, not arbitrary Google URLs.

    Lodi's reviewed CSV publications return 307 to rotating doc-*-sheets hosts.
    This rule applies only to a configured docs.google.com publication export
    and its HTTPS /pub/ download; discovery still uses the exact origin list.
    """
    old, new = urlsplit(source), urlsplit(destination)
    return bool(allowed(source, hosts) and old.hostname == 'docs.google.com'
                and re.fullmatch(r'/spreadsheets/d/e/[A-Za-z0-9_-]+/pub', old.path)
                and parse_qs(old.query).get('output') == ['csv']
                and re.fullmatch(r'doc-[a-z0-9-]+-sheets\.googleusercontent\.com', new.hostname or '')
                and allowed(destination, [new.hostname]) and new.path.startswith('/pub/'))


def fetch_url(url, previous, hosts, force=False):
    if not allowed(url, hosts):
        raise ValueError('URL outside configured HTTPS origins')
    headers = {'User-Agent': USER_AGENT, 'Accept': '*/*'}
    if previous.get('sha256') and not force:
        if previous.get('etag'):
            headers['If-None-Match'] = previous['etag']
        elif previous.get('last_modified'):
            headers['If-Modified-Since'] = previous['last_modified']
    opener = build_opener(ReviewedRedirect(hosts))
    for attempt in range(2):
        try:
            with opener.open(Request(url, headers=headers), timeout=20) as response:
                body = response.read(32 * 1024 * 1024 + 1)
                if not body or len(body) > 32 * 1024 * 1024:
                    raise ValueError('Empty resource or 32 MiB limit exceeded')
                return {'status': response.status, 'body': body, 'resolved_url': response.geturl(),
                    'content_type': response.headers.get('Content-Type', 'application/octet-stream'),
                    'etag': response.headers.get('ETag'), 'last_modified': response.headers.get('Last-Modified')}
        except HTTPError as error:
            if error.code == 304:
                return {'status': 304}
            if attempt == 0 and error.code in (429, 502, 503, 504):
                time.sleep(2); continue
            raise


def _capture_history(robot, old):
    """Retain every known immutable capture identity for one resource.

    Older robot-state snapshots predate append-only capture history and retain only
    the capture ids from the most recent archived payload. Preserve those identities
    explicitly without inventing acquisition timestamps or other provenance that the
    historical state did not record.
    """
    history = old.get('capture_history')
    if history is not None:
        if not isinstance(history, list):
            raise ValueError('capture_history must be a list')
        return deepcopy(history)

    capture_ids = old.get('capture_ids', [])
    if not capture_ids:
        return []
    source_keys = old.get('source_keys') or [robot['authority_key'] + '-robot-discovery']
    exact_key_alignment = len(source_keys) == len(capture_ids)
    return [{
        'capture_id': capture_id,
        'source_key': source_keys[index] if exact_key_alignment else None,
        'sha256': old.get('archived_sha256'),
        'byte_size': None,
        'content_type': None,
        'captured_at': None,
        'reference_date': None,
        'http_status': None,
    } for index, capture_id in enumerate(capture_ids)]


def run_robot(robot, previous=None, *, mode='capture', store=None, work_dir=Path('/tmp/white-list-robots'),
              fetch=fetch_url, force=False, pause=0.4, clock=time.monotonic):
    if mode not in ('check', 'capture') or store is None:
        raise ValueError('Every robot acquisition requires the designated evidence store')
    # Explicit compatibility migration: the old "check" spelling remains accepted,
    # but is no longer a path that downloads and then discards source evidence.
    previous = previous or {}
    at = datetime.now(timezone.utc).isoformat()
    resources = deepcopy(previous.get('resources', {}))
    approved = {}
    for item in robot['sources']:
        approved.setdefault(item['url'], []).append(item)
    # A bounded scan can span several runs. Preserve its frontier and skip
    # documents already checked in this cycle, while rereading current sources.
    continuing = bool(previous.get('pending_urls'))
    cycle_started_at = (previous.get('cycle_started_at') or previous.get('checked_at') or at) if continuing else at
    current = set(robot['landing_pages']) | set(approved)
    def needs_visit(url):
        old = resources.get(url, {})
        return (url in current or not continuing or old.get('last_checked_at', '') < cycle_started_at
                or old.get('archived_sha256') != old.get('sha256'))

    queue = [(url, 0, 'landing') for url in robot['landing_pages']]
    queue.extend((url, 0, 'source') for url in sorted(approved))
    # pending_urls is retained for public consumers and older state files.
    frontier = {item['url']: item for item in previous.get('pending_queue', [])}
    for url in previous.get('pending_urls', []):
        item = frontier.get(url, {})
        queue.append((url, item.get('depth', robot['max_depth']),
                      item.get('role', 'candidate' if DOCUMENT.search(url) else 'landing')))
    seen, errors, changed, new, external, captures = set(), [], [], [], set(), []
    discovered = set(); start = clock()
    while queue and len(seen) < robot['max_requests'] and clock() - start < robot['time_budget_seconds']:
        # New/oldest observations first; reverse URL order favours dated recent
        # attachments without interpreting filenames as administrative dates.
        queue.sort(key=lambda item: item[0], reverse=True)
        queue.sort(key=lambda item: (
            0 if item[0] in robot['landing_pages'] else 1 if item[0] in approved else 2 if item[2] == 'landing' else 3,
            resources.get(item[0], {}).get('last_checked_at', '')))
        url, depth, role = queue.pop(0)
        if url in seen or not needs_visit(url):
            continue
        seen.add(url)
        if url in approved:
            role = 'source'
        old = resources.get(url, {})
        receipts = []
        stage = 'state_validation'
        try:
            history = _capture_history(robot, old)
            stage = 'acquisition'
            # Pages are read every time so a 304 never prevents link discovery.
            page = (role == 'landing' or url in robot['landing_pages'] or
                    old.get('content_type') in ('text/html', 'application/xhtml+xml'))
            temporal_capture = role in ('source', 'candidate')
            # A new capture needs exact bytes. Avoid a conditional request followed
            # by an unnecessary second request to the same official endpoint.
            response = fetch(url, old, robot['allowed_hosts'], force=force or page or temporal_capture)
            if response['status'] == 304:
                if not old.get('sha256'):
                    raise ValueError('304 without a preceding content identity')
                if temporal_capture or old.get('archived_sha256') != old['sha256']:
                    response = fetch(url, {}, robot['allowed_hosts'], force=True)
                else:
                    old['last_checked_at'] = at; resources[url] = old; continue
            body = response['body']; sha = digest(body)
            mime = response['content_type'].split(';')[0].lower()
            item = {'sha256': sha, 'byte_size': len(body), 'content_type': mime,
                'resolved_url': response['resolved_url'], 'etag': response.get('etag'),
                'last_modified': response.get('last_modified'), 'last_checked_at': at, 'role': role,
                'source_keys': sorted({s['source_key'] for s in approved.get(url, [])}),
                'archived_sha256': old.get('archived_sha256'), 'capture_ids': old.get('capture_ids', []),
                'capture_history': history}
            should_archive = temporal_capture or item['archived_sha256'] != sha
            if should_archive:
                stage = 'archive'
                # Unbound discovery captures are explicitly quarantined, never bound
                # to an applicant/listed SourceSeries by a filename heuristic.
                capture_keys = item['source_keys'] or [robot['authority_key'] + '-robot-discovery']
                for key in capture_keys:
                    result = archive_payload(data=body, source_key=key, resource_url=url,
                        reference_date=None, content_type=response['content_type'], store=store,
                        work_dir=work_dir, resolved_url=response['resolved_url'], http_status=response['status'],
                        etag=response.get('etag'), last_modified=response.get('last_modified'),
                        origin_type='official_current', authority_rank_code='primary_official',
                        resource_type_code='html' if mime in ('text/html', 'application/xhtml+xml') else 'other')
                    receipts.append(result.manifest['capture_id'])
                    item['capture_history'].append({
                        'capture_id': result.manifest['capture_id'],
                        'source_key': result.manifest['source_key'],
                        'sha256': result.manifest['sha256'],
                        'byte_size': result.manifest['byte_size'],
                        'content_type': result.manifest['content_type'],
                        'captured_at': result.manifest['captured_at'],
                        'reference_date': result.manifest['reference_date'],
                        'http_status': result.manifest['http_status'],
                    })
                    # Record each verified success immediately. A later binding or
                    # response-validation failure must retain its catalogue identity
                    # without replacing the last accepted resource state.
                    resources[url] = {**old, 'capture_history': history}
                    if url not in captures:
                        captures.append(url)
                    result.path.unlink(missing_ok=True)
                item['archived_sha256'] = sha; item['capture_ids'] = receipts
            stage = 'response_validation'
            if DOCUMENT.search(url) and mime in ('text/html', 'application/xhtml+xml'):
                raise ValueError('Document endpoint returned HTML; source access requires review')
            baseline = old.get('sha256') or next((s['approved_sha256'] for s in approved.get(url, [])), None)
            if baseline is None:
                new.append(url)
            elif sha != baseline:
                changed.append(url)
            resources[url] = item
            if mime in ('text/html', 'application/xhtml+xml'):
                stage = 'discovery'
                docs, pages, elsewhere = discover_links(body, response['resolved_url'], robot['allowed_hosts'])
                external.update(elsewhere); discovered.update(docs)
                queue.extend((u, depth, 'candidate') for u in docs if u not in seen)
                if depth < robot['max_depth']:
                    queue.extend((u, depth + 1, 'landing') for u in pages if u not in seen)
        except Exception as error:
            # Keep the previous valid resource state; never make a partial failure
            # erase the preceding byte identity or durable capture evidence.
            errors.append({'url': url, 'error': type(error).__name__,
                           'http_status': error.code if isinstance(error, HTTPError) else None,
                           'stage': stage, 'verified_capture_ids': list(receipts)})
        if pause:
            time.sleep(pause)
    frontier = {}
    for url, depth, role in queue:
        if url not in seen and needs_visit(url):
            if url not in frontier or depth < frontier[url]['depth']:
                frontier[url] = {'url': url, 'depth': depth, 'role': role}
    pending = sorted(frontier)
    status = 'partial' if errors or pending else 'changed' if changed else 'baseline' if not previous else 'unchanged'
    if previous and new and status == 'unchanged':
        status = 'changed'
    return {'authority_key': robot['authority_key'], 'checked_at': at, 'status': status,
        'mode': 'capture', 'requested_mode': mode,
        'last_successful_check_at': at if status != 'partial' else previous.get('last_successful_check_at'),
        'requests': len(seen), 'changed_urls': changed, 'new_urls': new, 'captured_urls': captures,
        'discovered_documents': sorted(discovered), 'external_links_for_review': sorted(external),
        'pending_urls': pending, 'pending_queue': [frontier[url] for url in pending],
        'cycle_started_at': cycle_started_at, 'errors': errors, 'resources': resources,
        'population_mapping_reviewed': robot['population_mapping_reviewed'],
        'publication_approved': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', type=Path, default=CATALOG)
    parser.add_argument('--generate-catalog', action='store_true')
    parser.add_argument('--authority', default='all')
    parser.add_argument('--shard', type=int, default=0)
    parser.add_argument('--shards', type=int, default=1)
    parser.add_argument('--mode', choices=('check', 'capture'), default='capture',
                        help='Both modes preserve evidence; check is a legacy alias for capture')
    parser.add_argument('--state', type=Path)
    parser.add_argument('--output', type=Path, default=Path('robot-report.json'))
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()
    if args.generate_catalog:
        data = generate_catalog(); args.catalog.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n'); return
    catalog = json.loads(args.catalog.read_text())
    with open('data/source_registry/territorial_authorities.csv') as handle:
        validate_catalog(catalog, [r['authority_key'] for r in csv.DictReader(handle)])
    if args.shards < 1 or not 0 <= args.shard < args.shards:
        parser.error('invalid shard')
    robots = [r for i, r in enumerate(catalog['robots']) if (args.authority == 'all' or r['authority_key'] == args.authority) and i % args.shards == args.shard]
    if not robots:
        parser.error('unknown authority or empty shard')
    old = json.loads(args.state.read_text()) if args.state and args.state.exists() else {'robots': {}}
    from white_list_archive.storage.evidence import EvidenceStore, StoreConfig, client_for
    config = StoreConfig.from_env(); store = EvidenceStore(client_for(config), config)
    result = {'schema_version': 1, 'robots': {}}
    for robot in robots:
        report = run_robot(robot, old.get('robots', {}).get(robot['authority_key']), mode=args.mode, store=store, force=args.force)
        result['robots'][robot['authority_key']] = report
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
        print(robot['authority_key'], report['status'], report['requests'], 'requests', len(report['captured_urls']), 'captures')


if __name__ == '__main__':
    main()
