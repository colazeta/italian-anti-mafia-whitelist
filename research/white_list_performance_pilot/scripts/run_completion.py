#!/usr/bin/env python3
"""Expanded, aggregate-only research pilot. No production or canonical writes."""
from __future__ import annotations
import argparse, csv, json, os, re, tempfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import run_followup as follow
base = follow.base
extra_metrics = follow.extra_metrics
current_source = follow.current_source
history_source = follow.history_source
linked_lag_diagnostics = follow.linked_lag_diagnostics
VERSION = '0.4.0-source-diagnostic'

# Explicit finite research sample; production configuration is unchanged.
EXPANDED_PILOT = base.PILOT | {
    'agrigento', 'siracusa', 'trapani', 'perugia', 'pisa', 'modena',
    'lecce', 'catanzaro',
}
MONTHS = {'gennaio': 1, 'febbraio': 2, 'marzo': 3, 'aprile': 4, 'maggio': 5,
          'giugno': 6, 'luglio': 7, 'agosto': 8, 'settembre': 9,
          'ottobre': 10, 'novembre': 11, 'dicembre': 12}
LANDING = 'https://prefettura.interno.gov.it/it/prefetture/cosenza/evidenza/white-list'
# Independently identified official page, not a production binding.
LATEST_KNOWN = 'https://prefettura.interno.gov.it/it/prefetture/cosenza/white-list-elenchi-aggiornati-15-settembre-2026'


def edition_date_from_url(url):
    match = re.search(r'/white-list-elenchi-aggiornati-(\d{1,2})-([a-z]+)-(20\d{2})/?$', url)
    if not match or match[2] not in MONTHS:
        return None
    try:
        return datetime(int(match[3]), MONTHS[match[2]], int(match[1])).date().isoformat()
    except ValueError:
        return None


def discover_history(frozen):
    """Discover only actual links on the official landing page. Never guess URLs."""
    from html.parser import HTMLParser
    from urllib.parse import urljoin
    class Links(HTMLParser):
        def __init__(self):
            super().__init__()
            self.urls = []
        def handle_starttag(self, tag, attrs):
            if tag.lower() == 'a':
                href = dict(attrs).get('href')
                if href:
                    self.urls.append(urljoin(LANDING, href))
    found = {x['reference_date']: dict(x) for x in frozen}
    audit = {'landing_url': LANDING, 'frozen_editions': len(frozen),
             'new_dates_discovered': [], 'replaced_legacy_urls': [],
             'latest_known_page': LATEST_KNOWN}
    links = [LATEST_KNOWN]
    try:
        data, capture = base.fetch(LANDING)
        audit['landing_capture'] = capture
        parser = Links()
        parser.feed(data.decode('utf-8', errors='replace'))
        links.extend(parser.urls)
        audit['discovery_status'] = 'official_landing_links_read'
    except Exception as exc:
        audit['discovery_status'] = 'landing_failed_frozen_and_known_page_only'
        audit['error_class'] = type(exc).__name__
    for url in sorted(set(links)):
        if not url.startswith('https://prefettura.interno.gov.it/it/prefetture/cosenza/'):
            continue
        ref = edition_date_from_url(url)
        if not ref or ref > datetime.now(timezone.utc).date().isoformat():
            continue
        if ref not in found:
            audit['new_dates_discovered'].append(ref)
        elif found[ref]['edition_page_url'] != url:
            if 'www1.prefettura.it' not in found[ref]['edition_page_url']:
                continue
            audit['replaced_legacy_urls'].append({'reference_date': ref,
                'old_url': found[ref]['edition_page_url'], 'new_url': url})
        found[ref] = {'edition_key': 'cosenza-' + ref, 'reference_date': ref,
                      'edition_page_url': url, 'source_origin': 'official_current',
                      'reference_date_basis': 'explicit dated official page URL, not capture time'}
    audit['new_dates_discovered'].sort()
    audit['discovered_edition_count'] = len(found)
    if len(found) > 40:
        raise ValueError('Historical discovery exceeded reviewed pilot bound')
    return [found[d] for d in sorted(found)], audit


def linkage_map(rows):
    selected, excluded = base.safe_records(rows)
    result = {(r['link_key'], r['app']): r for r in selected
              if r['app'] and r['reference'] and r['app'] <= r['reference']}
    return result, excluded


def observation_cohorts(editions):
    """Cohorts first OBSERVED pending, not cohorts of incoming applications.

    Unobserved final states remain a separate category. A later published
    listing is an observed transition, not administrative clearance.
    """
    if not editions:
        return {'cohorts': [], 'interpretation': 'No usable editions'}
    first, ever_listed, maps = {}, set(), []
    for ref, rows in sorted(editions):
        mapping, _ = linkage_map(rows)
        maps.append((ref, mapping))
        for key, row in mapping.items():
            if row['status'] == 'pending' and key not in first:
                first[key] = ref
            if key in first and ref > first[key] and row['status'] == 'listed':
                ever_listed.add(key)
    last_ref, last = maps[-1]
    grouped = defaultdict(Counter)
    for key, first_ref in first.items():
        group = grouped[first_ref]
        group['n_first_observed_pending'] += 1
        row = last.get(key)
        if row is None:
            category = 'not_observed_in_last_edition'
        elif row['status'] == 'pending':
            category = 'published_pending_at_last_edition'
        elif row['status'] == 'listed':
            category = 'published_listed_at_last_edition'
        elif row['status'] in {'renewal_requested', 'renewal_update_in_progress'}:
            category = 'published_renewal_at_last_edition'
        else:
            category = 'published_other_at_last_edition'
        group[category] += 1
        if key in ever_listed:
            group['ever_observed_later_listed'] += 1
    rows = []
    categories = ['published_pending_at_last_edition', 'published_listed_at_last_edition',
                  'published_renewal_at_last_edition', 'published_other_at_last_edition',
                  'not_observed_in_last_edition']
    for ref, counts in sorted(grouped.items()):
        row = {'first_pending_observation_date': ref, 'last_edition_date': last_ref,
               'followup_calendar_days': (base.parse_date(last_ref) - base.parse_date(ref)).days,
               'n_first_observed_pending': counts['n_first_observed_pending'],
               **{k: counts[k] for k in categories},
               'ever_observed_later_listed': counts['ever_observed_later_listed']}
        assert sum(row[k] for k in categories) == row['n_first_observed_pending']
        assert row['ever_observed_later_listed'] <= row['n_first_observed_pending']
        rows.append(row)
    return {'cohorts': rows, 'unit': 'conservative source entity/application linkage',
            'true_cohort_completion_rate': None,
            'interpretation': 'First-observed-pending cohorts include prevalent cases and incomplete ascertainment. Observation loss is not resolution or independent censoring. These counts do not identify survival or clearance.'}


def coverage_bounds(metrics):
    """Worst-case age-threshold bounds for published rows, not confidence intervals."""
    n = metrics['source_status_counts'].get('pending', 0)
    q = metrics['observed_pending_age_all_source_rows']
    known, unknown = q['n'], n - q['n']
    assert 0 <= known <= n
    return {'published_pending_rows': n, 'age_assessable_rows': known,
            'age_unassessable_rows': unknown,
            'dated_fraction': known / n if n else None,
            'threshold_bounds': {str(t): {
                'known_over_threshold': q['gt' + str(t)] if known else 0,
                'lower_share_all_published_pending': (q['gt' + str(t)] or 0) / n if n else None,
                'upper_share_all_published_pending': ((q['gt' + str(t)] or 0) + unknown) / n if n else None}
                for t in (90, 180, 365)},
            'interpretation': 'Worst-case missing-age bounds concern source rows, not true administrative backlog. No missing-at-random assumption.'}


def source_overlap_audit(sources, outputs):
    groups = defaultdict(list)
    for cfg, (report, rows) in zip(sources, outputs):
        if rows:
            groups[(cfg['authority_key'], cfg.get('register_key'))].append((cfg, rows))
    result = []
    for (authority, register), items in sorted(groups.items()):
        if len(items) < 2:
            continue
        pairs = []
        for i, (a, ra) in enumerate(items):
            for b, rb in items[i + 1:]:
                ma, _ = linkage_map(ra)
                mb, _ = linkage_map(rb)
                ids_a, ids_b = {k[0] for k in ma}, {k[0] for k in mb}
                pairs.append({'source_a': a['source_key'], 'source_b': b['source_key'],
                    'reference_date_a': a['reference_date'], 'reference_date_b': b['reference_date'],
                    'same_entity_application_pairs': len(ma.keys() & mb.keys()),
                    'same_entity_among_date_linkable_rows': len(ids_a & ids_b)})
        result.append({'authority_key': authority, 'register_key': register,
                       'pairs': pairs, 'interpretation': 'Source overlap QA only; do not sum source populations into unique procedures.'})
    return result


def completion_self_tests():
    assert edition_date_from_url(LATEST_KNOWN) == '2026-09-15'
    assert edition_date_from_url(LATEST_KNOWN.replace('15-settembre','31-febbraio')) is None
    assert edition_date_from_url('https://example.org/anything') is None
    cfg1 = {'source_key':'synthetic', 'reference_date':'2026-01-01'}
    cfg2 = {'source_key':'synthetic', 'reference_date':'2026-02-01'}
    def row(cfg, status, ident='12345678901'):
        return base.normalise({'identifiers':[ident], 'name':'SYNTHETIC',
            'application_date':'2025-12-01', 'source_status':status}, cfg)
    a, b = row(cfg1, 'pending'), row(cfg2, 'listed')
    c = row(cfg1, 'pending','12345678902')
    observed = observation_cohorts([('2026-01-01',[a,c]), ('2026-02-01',[b])])['cohorts'][0]
    assert observed['n_first_observed_pending'] == 2
    assert observed['ever_observed_later_listed'] == 1
    assert observed['not_observed_in_last_edition'] == 1
    m = extra_metrics([a])
    assert coverage_bounds(m)['threshold_bounds']['90']['lower_share_all_published_pending'] == 0
    unknown = row(cfg1,'pending','12345678903'); unknown['app']=None
    bounds = coverage_bounds(extra_metrics([a,unknown]))
    assert bounds['threshold_bounds']['90']['upper_share_all_published_pending'] == .5
    assert bounds['dated_fraction'] == .5
    assert m['clearance_rate'] is None


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument('--output-dir', type=Path, required=True)
    args = cli.parse_args()
    completion_self_tests()
    config = base.ROOT / 'data/publication/multi_prefecture_pilot.json'
    history_path = base.ROOT / 'data/source_registry/cosenza_historical_editions.csv'
    sources = [c for c in json.loads(config.read_text())['sources'] if c['authority_key'] in EXPANDED_PILOT]
    history, discovery = discover_history(list(csv.DictReader(history_path.open())))
    result = {'analysis_version': VERSION, 'code_commit': os.environ.get('GITHUB_SHA'),
              'started_at': datetime.now(timezone.utc).isoformat(),
              'requested_authorities': sorted(EXPANDED_PILOT),
              'input_sha256': {str(p.relative_to(base.ROOT)): base.digest(p.read_bytes()) for p in (config, history_path)},
              'history_discovery': discovery,
              'current_sources': [], 'cosenza_history': [], 'canonical_database_writes': 0,
              'production_files_modified': 0, 'completion_self_tests':'passed'}
    with tempfile.TemporaryDirectory(prefix='wl-research-completion-') as temp:
        work = Path(temp)
        parsers = base.parser_registry()
        with ThreadPoolExecutor(max_workers=2) as pool:
            outputs = list(pool.map(lambda cfg: current_source(cfg, work, parsers), sources))
        result['current_sources'] = [report for report, _ in outputs]
        result['source_overlap_audit'] = source_overlap_audit(sources, outputs)
        for report in result['current_sources']:
            if 'metrics' in report:
                report['age_coverage_bounds'] = coverage_bounds(report['metrics'])
        with ThreadPoolExecutor(max_workers=2) as pool:
            historical_outputs = list(pool.map(lambda e: history_source(e, work), history))
        result['cosenza_history'] = [report for report, _ in historical_outputs]
        hashes = defaultdict(list)
        for report, rows in historical_outputs:
            if rows:
                hashes[report['sha256']].append(report['reference_date'])
        ambiguous = {h for h, refs in hashes.items() if len(set(refs)) > 1}
        result['identical_bytes_at_multiple_reference_dates'] = [
            {'sha256': h, 'reference_dates': hashes[h]} for h in sorted(ambiguous)]
        editions = []
        for report, rows in historical_outputs:
            if rows and report['sha256'] not in ambiguous:
                report['age_coverage_bounds'] = coverage_bounds(report['metrics'])
                editions.append((report['reference_date'], rows))
            elif rows:
                report['longitudinal_eligibility'] = 'excluded_same_bytes_different_reference_dates'
        result['source_transitions'] = base.transition_diagnostics(sorted(editions))
        result['linked_lag_diagnostics'] = linked_lag_diagnostics(editions)
        result['first_observed_pending_cohorts'] = observation_cohorts(editions)
    result['run_summary'] = {
        'current_sources_requested': len(sources),
        'current_sources_parsed': sum(x['status'] == 'approved_parser_executed' for x in result['current_sources']),
        'authorities_with_approved_source_results': len({x['authority_key'] for x in result['current_sources'] if x['status'] == 'approved_parser_executed'}),
        'historical_editions_requested': len(history),
        'historical_editions_exploratory_parsed': sum(bool(r) for _, r in historical_outputs),
        'historical_editions_longitudinally_used': len(editions),
        'current_source_observations': sum(x.get('metrics', {}).get('source_observations', 0) for x in result['current_sources']),
        'historical_source_observations': sum(x.get('metrics', {}).get('source_observations', 0) for x in result['cosenza_history'])}
    result['completed_at'] = datetime.now(timezone.utc).isoformat()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    # Filename retained for artefact compatibility; analysis_version is authoritative.
    (args.output_dir / 'source_diagnostics_v3.json').write_text(json.dumps(result, indent=2) + '\n')
    print('RESEARCH_FOLLOWUP_SUMMARY=' + json.dumps(result['run_summary']))

if __name__ == '__main__':
    main()
