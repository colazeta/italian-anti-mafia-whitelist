#!/usr/bin/env python3
"""Read-only source diagnostics, not canonical procedure performance estimates.

Reuses existing production parsers without modifying them. Frozen source bytes
must match their approved hash. Historical editions are exploratory and never
enter canonical storage. Only non-identifying aggregates leave the runner.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import os
import re
import statistics
import subprocess
import tempfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[3]
VERSION = '0.2.0-source-diagnostic'
PILOT = {'cosenza', 'pistoia', 'biella', 'cagliari', 'torino', 'potenza',
         'parma', 'milano', 'taranto', 'roma', 'brescia', 'napoli'}
OPEN = {'pending', 'renewal_requested', 'renewal_update_in_progress'}
HEX = re.compile(r'^[0-9a-f]{64}$')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def parse_date(value):
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d.%m.%Y'):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    return None


def quantiles(values):
    values = sorted(values)
    def q(p):
        pos = (len(values) - 1) * p
        lo = int(pos)
        hi = min(lo + 1, len(values) - 1)
        return round(values[lo] + (values[hi] - values[lo]) * (pos - lo), 2)
    if not values:
        return {'n': 0, 'median_days': None, 'p25_days': None, 'p75_days': None,
                'p90_days': None, 'gt90': None, 'gt180': None, 'gt365': None}
    return {'n': len(values), 'median_days': q(.5), 'p25_days': q(.25),
            'p75_days': q(.75), 'p90_days': q(.9),
            'gt90': sum(x > 90 for x in values),
            'gt180': sum(x > 180 for x in values),
            'gt365': sum(x > 365 for x in values)}


def fetch(url):
    request = Request(url, headers={'User-Agent': 'italian-anti-mafia-whitelist/0.2 (bounded research pilot)',
                                   'Cache-Control': 'no-cache'})
    with urlopen(request, timeout=45) as response:
        data = response.read(40_000_001)
        if len(data) > 40_000_000:
            raise ValueError('Resource exceeds bounded capture size')
        return data, {'final_url': response.geturl(), 'http_status': response.status,
                      'content_type': response.headers.get_content_type(),
                      'captured_at': datetime.now(timezone.utc).isoformat(),
                      'sha256': digest(data), 'byte_size': len(data)}


def json_value(value, default):
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value) if value else default
    except (ValueError, TypeError):
        return default


def normalise(record, cfg):
    """Field adapter only. Does not assert identity, procedure type or outcome."""
    ids = record.get('identifiers')
    if ids is None:
        ids = json_value(record.get('identifiers_json'), [])
    tokens = []
    for item in ids or []:
        value = item.get('raw_value', '') if isinstance(item, dict) else str(item)
        value = re.sub(r'\s+', '', value).upper()
        if re.fullmatch(r'(?:\d{11}|[A-Z0-9]{16})', value):
            tokens.append(value)
    candidates = record.get('application_dates')
    if candidates is None:
        candidates = json_value(record.get('application_dates_json'), [])
    dates = []
    parenthesised = 0
    for item in candidates or []:
        if isinstance(item, dict):
            if item.get('parenthesized'):
                parenthesised += 1
                continue
            value = item.get('date') or item.get('raw_value')
        else:
            value = item
        d = parse_date(value)
        if d:
            dates.append(d)
    d = parse_date(record.get('application_date'))
    if d:
        dates.append(d)
    dates = sorted(set(dates))
    return {'id_tokens': sorted(set(tokens)),
            'name': ' '.join(str(record.get('name') or record.get('operator_name_normalised')
                                or record.get('operator_name_raw') or '').upper().split()),
            'app': dates[0] if len(dates) == 1 else None,
            'app_count': len(dates), 'parenthesised_dates': parenthesised,
            'listing': parse_date(record.get('observed_listing_date')),
            'decision': parse_date(record.get('decision_date')),
            'status': str(record.get('source_status') or 'other_or_unknown'),
            'reference': parse_date(cfg['reference_date']),
            'source_key': cfg['source_key']}


def safe_records(records):
    """Conservative source-observation linkage, never a canonical identity key."""
    names = defaultdict(set)
    for r in records:
        for token in r['id_tokens']:
            names[token].add(r['name'])
    good, rejected = [], Counter()
    for r in records:
        valid = [x for x in r['id_tokens'] if len(names[x]) == 1]
        if len(valid) != 1 or not r['name']:
            rejected['identity_missing_multiple_or_conflicting'] += 1
            continue
        x = dict(r)
        x['link_key'] = (valid[0], r['name'])
        good.append(x)
    # Multiple rows for one entity/date are not assumed to be independent cases.
    counts = Counter((r['link_key'], r['app']) for r in good)
    selected = []
    for r in good:
        if counts[(r['link_key'], r['app'])] > 1:
            rejected['ambiguous_same_entity_application_rows'] += 1
        else:
            selected.append(r)
    return selected, dict(rejected)


def analyse(records):
    selected, identity_exclusions = safe_records(records)
    open_ages, renewal_ages, pairs = [], [], []
    qa = Counter()
    for r in selected:
        if r['app_count'] > 1:
            qa['multiple_application_dates'] += 1
        if r['app'] and r['app'] > r['reference']:
            qa['application_after_reference'] += 1
            continue
        if not r['app']:
            qa['no_unique_application_date'] += 1
            continue
        if r['status'] == 'pending':
            open_ages.append((r['reference'] - r['app']).days)
        elif r['status'] in OPEN:
            renewal_ages.append((r['reference'] - r['app']).days)
        if r['listing'] and r['listing'] < r['app']:
            qa['listing_precedes_application'] += 1
        elif r['listing'] and r['listing'] > r['reference']:
            qa['listing_after_reference'] += 1
        elif r['status'] == 'listed' and r['listing']:
            # Merely a candidate date-pair lag; same-procedure linkage unverified.
            pairs.append((r['listing'] - r['app']).days)
    return {'source_observations': len(records),
            'source_status_counts': dict(sorted(Counter(r['status'] for r in records).items())),
            'rows_with_unique_application_date': sum(r['app'] is not None for r in records),
            'rows_with_listing_date': sum(r['listing'] is not None for r in records),
            'rows_with_explicit_decision_field': sum(r['decision'] is not None for r in records),
            'source_linkage_eligible_rows': len(selected),
            'identity_exclusions': identity_exclusions,
            'date_exclusions': dict(qa),
            'observed_pending_age': quantiles(open_ages),
            'renewal_date_age_diagnostic': quantiles(renewal_ages),
            'candidate_application_to_listing_lag_NOT_processing_time': quantiles(pairs),
            'true_processing_time': None, 'clearance_rate': None, 'backlog_rate': None,
            'flow_blocker': 'Complete application inflows, all terminal outcomes and period boundaries not verified',
            'interpretation': 'Source-observation diagnostics at source reference date; no legal-deadline compliance or comparative efficiency inference.'}


def parser_registry():
    from white_list_archive.publishing import public_national_registry as module
    parsers = {}
    for name, value in vars(module).items():
        if (name == 'PARSERS' or name.endswith('_PARSERS')) and isinstance(value, dict):
            parsers.update({k: v for k, v in value.items() if callable(v)})
    return parsers


def cosenza_records(path):
    from white_list_archive.parsers.cosenza_combined_v2 import parse_pdf
    value = parse_pdf(path)
    if isinstance(value, tuple):
        value = value[0]
    if not isinstance(value, list):
        raise TypeError('Unexpected Cosenza parse contract')
    return value


def current_source(cfg, work, parsers):
    report = {k: cfg.get(k) for k in ('source_key', 'authority_key', 'register_key',
                                    'reference_date', 'population_scope', 'parser', 'resource_url')}
    report['expected_sha256'] = cfg.get('sha256')
    try:
        data, capture = fetch(cfg['resource_url'])
        report.update(capture)
        if not HEX.fullmatch(str(cfg.get('sha256') or '')) or digest(data) != cfg['sha256']:
            report['status'] = 'blocked_unapproved_bytes'
            return report, []
        path = work / (cfg['source_key'] + ('.pdf' if data.startswith(b'%PDF') else '.source'))
        path.write_bytes(data)
        if cfg['parser'] == 'cosenza_combined_v2':
            records = cosenza_records(path)
        else:
            fn = parsers[cfg['parser']]
            records = fn(path, cfg).records
        if len(records) != cfg['expected_source_rows']:
            raise ValueError('Approved source-row count mismatch')
        adapted = [normalise(r, cfg) for r in records]
        report['status'] = 'approved_parser_executed'
        report['metrics'] = analyse(adapted)
        return report, adapted
    except Exception as exc:
        # Raw parser exception strings can contain company data: do not emit them.
        report['status'] = 'capture_or_parse_failed'
        report['error_class'] = type(exc).__name__
        return report, []


def historical_source(edition, work):
    from white_list_archive.acquisition.cosenza_capture import resolve_combined_resource
    report = {'edition_key': edition['edition_key'], 'reference_date': edition['reference_date'],
              'page_url': edition['edition_page_url'], 'source_origin': edition['source_origin']}
    try:
        resource, label = resolve_combined_resource(edition['edition_page_url'])
        data, capture = fetch(resource)
        report.update(capture)
        report['resource_url'] = resource
        if not data.startswith(b'%PDF'):
            report['status'] = 'captured_format_requires_adapter'
            return report, []
        path = work / (edition['edition_key'] + '.pdf')
        path.write_bytes(data)
        # Historical source compatibility remains explicit research evidence.
        text = subprocess.run(['pdftotext', '-f', '1', '-l', '1', '-layout', str(path), '-'],
                              check=True, capture_output=True, text=True).stdout
        folded = ' '.join(text.upper().split())
        headers = ['RAGIONE', 'SEDE', 'ISTANZA', 'ESITO']
        report['required_header_tokens_found'] = sum(x in folded for x in headers)
        if not all(x in folded for x in headers):
            report['status'] = 'captured_schema_requires_review'
            return report, []
        records = cosenza_records(path)
        cfg = {'source_key': 'cosenza-combined', 'reference_date': edition['reference_date']}
        adapted = [normalise(r, cfg) for r in records]
        report['status'] = 'exploratory_parse_NOT_canonicalised'
        report['metrics'] = analyse(adapted)
        report['validation_limit'] = 'Header-token check is necessary, not sufficient: historical layout/row recall needs independent review'
        return report, adapted
    except Exception as exc:
        report['status'] = 'capture_or_parse_failed'
        report['error_class'] = type(exc).__name__
        return report, []


def transition_diagnostics(editions):
    result = []
    for (d1, rows1), (d2, rows2) in zip(editions, editions[1:]):
        a, _ = safe_records(rows1)
        b, _ = safe_records(rows2)
        aa = {(r['link_key'], r['app']): r for r in a if r['app']}
        bb = {(r['link_key'], r['app']): r for r in b if r['app']}
        common = aa.keys() & bb.keys()
        counts = Counter(aa[k]['status'] + ' -> ' + bb[k]['status'] for k in common)
        result.append({'from_reference_date': d1, 'to_reference_date': d2,
                       'matched_entity_application_pairs': len(common),
                       'observed_transitions': dict(sorted(counts.items())),
                       'disappeared_from_source_NOT_resolved': len(aa.keys() - bb.keys()),
                       'first_observed_NOT_incoming': len(bb.keys() - aa.keys()),
                       'administrative_decision_intervals': None,
                       'interval_blocker': 'Pending snapshot may be stale; a source transition is not a validated administrative decision interval'})
    return result


def self_test():
    assert parse_date('31/02/2026') is None
    assert quantiles([])['median_days'] is None
    assert quantiles([10, 20])['median_days'] == 15
    assert quantiles([90, 91, 180, 181, 365, 366])['gt90'] == 5
    cfg = {'source_key': 'synthetic', 'reference_date': '2026-09-20'}
    r = normalise({'identifiers': ['12345678901'], 'name': 'SYNTHETIC',
                   'application_date': '2026-10-01', 'source_status': 'pending'}, cfg)
    out = analyse([r])
    assert out['observed_pending_age']['n'] == 0
    assert out['clearance_rate'] is None
    assert out['date_exclusions']['application_after_reference'] == 1
    assert not safe_records([r, r])[0]
    assert normalise({'application_dates': [{'date':'01/01/2026','parenthesized': True}]}, cfg)['app'] is None


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument('--output-dir', type=Path, required=True)
    cli.add_argument('--self-test-only', action='store_true')
    args = cli.parse_args()
    self_test()
    if args.self_test_only:
        print('Research source diagnostic self-tests passed')
        return
    config_path = ROOT / 'data/publication/multi_prefecture_pilot.json'
    history_path = ROOT / 'data/source_registry/cosenza_historical_editions.csv'
    sources = json.loads(config_path.read_text())['sources']
    selected = [c for c in sources if c['authority_key'] in PILOT]
    history = list(csv.DictReader(history_path.open()))
    parsers = parser_registry()
    result = {'analysis_version': VERSION, 'analysis_status': 'experimental_source_diagnostics',
              'code_commit': os.environ.get('GITHUB_SHA'),
              'started_at': datetime.now(timezone.utc).isoformat(),
              'input_sha256': {str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in (config_path, history_path)},
              'current_sources': [], 'cosenza_history': [], 'source_transitions': [],
              'canonical_database_writes': 0, 'production_files_modified': 0}
    with tempfile.TemporaryDirectory(prefix='wl-performance-') as temp:
        work = Path(temp)
        with ThreadPoolExecutor(max_workers=2) as pool:
            outputs = list(pool.map(lambda c: current_source(c, work, parsers), selected))
        for report, _ in outputs:
            result['current_sources'].append(report)
        editions = []
        # Sequential historical capture avoids burst traffic to the same publisher.
        for entry in history:
            report, rows = historical_source(entry, work)
            result['cosenza_history'].append(report)
            if rows:
                editions.append((entry['reference_date'], rows))
        result['source_transitions'] = transition_diagnostics(sorted(editions))
    result['completed_at'] = datetime.now(timezone.utc).isoformat()
    result['run_summary'] = {
        'current_sources_requested': len(selected),
        'current_sources_parsed': sum(x['status'] == 'approved_parser_executed' for x in result['current_sources']),
        'historical_editions_requested': len(history),
        'historical_editions_exploratory_parsed': len(editions),
        'current_source_observations': sum(x.get('metrics', {}).get('source_observations', 0) for x in result['current_sources'])}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / 'source_diagnostics.json'
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print('RESEARCH_AGGREGATE_JSON=' + json.dumps(result, ensure_ascii=True, separators=(',', ':')))

if __name__ == '__main__':
    main()
