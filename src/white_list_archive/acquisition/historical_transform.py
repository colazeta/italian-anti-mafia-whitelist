"""Bounded private interpretations of retained reviewed historical byte versions.

Git history is a candidate index. Every selected input is independently rehydrated
and read from the immutable catalogue/object store by the ordinary transformer.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from white_list_archive.acquisition.auto_transform import (
    EditionReviewRequired, _resource_urls, persist_operational_report, transform_one,
)
from white_list_archive.acquisition.prefecture_robots import _capture_history
from white_list_archive.acquisition.transform_resilience import with_bounded_retry, quarantine_age
from white_list_archive.storage.capture_catalogue import CaptureCatalogue
from white_list_archive.storage.catalogue_recovery import load_catalogued_capture
from white_list_archive.storage.robot_recovery import read_robot_history

SHA40 = re.compile(r'[a-f0-9]{40}')
SHA64 = re.compile(r'[a-f0-9]{64}')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
        ensure_ascii=False, allow_nan=False).encode('utf-8')).hexdigest()


def select_historical_jobs(snapshots, config, *, shard=0, shards=4):
    """Enumerate byte-distinct scalar versions and witnessed complete bundle states.

    Bundle members must coexist in an actual retained resource-state revision;
    unobserved Cartesian combinations are never created. Repeated unchanged
    capture checks remain in the archive index and share one interpretation job.
    """
    if type(shards) is not int or type(shard) is not int or not 1 <= shards <= 4 or not 0 <= shard < shards:
        raise ValueError('Invalid historical authority shard')
    sources = config.get('sources')
    if not isinstance(sources, list):
        raise ValueError('Invalid reviewed configuration')
    keys, selected, issues, captured_identities = set(), {}, {}, {}
    def issue(source, reason, revision):
        row = issues.setdefault((source, reason), {'source_key': source, 'reason': reason,
            'first_history_revision': revision, 'affected_revisions': 0})
        row['affected_revisions'] += 1
    for cfg in sources:
        key, authority = cfg.get('source_key'), cfg.get('authority_key')
        if not isinstance(key, str) or key in keys or not isinstance(authority, str):
            raise ValueError('Missing or duplicate reviewed source binding')
        keys.add(key)
        if int(hashlib.sha256(authority.encode()).hexdigest(), 16) % shards != shard:
            continue
        urls = _resource_urls(cfg)
        for revision, state in snapshots:
            if not SHA40.fullmatch(revision) or state.get('schema_version') != 1 or not isinstance(state.get('robots'), dict):
                raise ValueError('Historical selection requires valid frozen Git states')
            robot = state['robots'].get(authority, {})
            if not robot.get('population_mapping_reviewed'):
                issue(key, 'unreviewed_authority_at_retained_state', revision)
                continue
            resources = robot.get('resources', {})
            if not isinstance(resources, dict):
                issue(key, 'invalid_robot_resources', revision)
                continue
            members = {}
            for label, url in urls.items():
                resource = resources.get(url)
                if not isinstance(resource, dict):
                    issue(key, 'missing_reviewed_resource', revision)
                    break
                history = _capture_history({'authority_key': authority}, resource)
                candidates = [row for row in history if isinstance(row, dict)
                    and row.get('source_key') == key
                    and isinstance(row.get('capture_id'), str)
                    and isinstance(row.get('sha256'), str) and SHA64.fullmatch(row['sha256'])]
                if any(not isinstance(row, dict) or (row.get('source_key') in (key, None)
                       and (not isinstance(row.get('capture_id'), str) or
                            not isinstance(row.get('sha256'), str) or not SHA64.fullmatch(row['sha256'])))
                       for row in history):
                    issue(key, 'retained_capture_metadata_unresolved', revision)
                for row in candidates:
                    identity = (key, row['capture_id'])
                    observed = (url, row['sha256'])
                    if identity in captured_identities and captured_identities[identity] != observed:
                        raise ValueError('One historical capture identity has conflicting provenance')
                    captured_identities[identity] = observed
                if cfg.get('resources') is not None:
                    # capture_ids are the resource state's actual current archived
                    # captures. Historical members are not joined by guessed dates.
                    active = resource.get('capture_ids')
                    if not isinstance(active, list):
                        issue(key, 'bundle_active_capture_identity_unresolved', revision)
                        break
                    candidates = [row for row in candidates if row['capture_id'] in active]
                    if len(candidates) != 1:
                        issue(key, 'bundle_active_capture_identity_unresolved', revision)
                        break
                if not candidates:
                    issue(key, 'capture_byte_identity_unresolved', revision)
                    break
                members[label] = [{'url': url, 'state': deepcopy(row)} for row in candidates]
            if set(members) != set(urls):
                continue
            combinations = ([{'primary': row} for row in members['primary']]
                            if cfg.get('resources') is None else
                            [{label: rows[0] for label, rows in members.items()}])
            for captures in combinations:
                identity = digest({'source_key': key,
                    'labelled_sha256': {label: part['state']['sha256'] for label, part in captures.items()}})
                if identity not in selected:
                    selected[identity] = {'source_key': key, 'config': deepcopy(cfg),
                        'captures': captures, 'interpretation_key': identity,
                        'first_history_revision': revision, 'witnessed_state_count': 0}
                selected[identity]['witnessed_state_count'] += 1
    jobs = sorted(selected.values(), key=lambda row: (row['source_key'], row['interpretation_key']))
    return jobs, sorted(issues.values(), key=lambda row: (row['source_key'], row['reason']))


def selection_manifest(jobs):
    return [{'interpretation_key': row['interpretation_key'], 'source_key': row['source_key'],
             'configuration_sha256': digest(row['config']),
             'first_history_revision': row['first_history_revision'],
             'inputs': {label: {'capture_id': part['state']['capture_id'],
                                'sha256': part['state']['sha256']}
                        for label, part in sorted(row['captures'].items())}}
            for row in jobs]


def select_batch(jobs, *, cursor, max_jobs):
    if type(cursor) is not int or not 0 <= cursor <= len(jobs):
        raise ValueError('Cursor is outside the frozen historical denominator')
    if type(max_jobs) is not int or not 1 <= max_jobs <= 10:
        raise ValueError('Historical batch must contain one to ten jobs')
    batch = jobs[cursor:cursor+max_jobs]
    next_cursor = cursor + len(batch)
    return batch, {'denominator_interpretations': len(jobs), 'cursor': cursor,
                   'selected_interpretations': len(batch), 'next_cursor': next_cursor,
                   'pending_interpretations': len(jobs)-next_cursor,
                   'batch_covers_remaining_denominator': next_cursor == len(jobs)}


def hydrate_selected_job(job, store):
    """Fill missing legacy metadata only from its exact immutable catalogue record."""
    hydrated = deepcopy(job)
    catalogue = CaptureCatalogue(store)
    for part in hydrated['captures'].values():
        state = part['state']
        manifest, _ = load_catalogued_capture(catalogue, source_key=job['source_key'], capture_id=state['capture_id'])
        if manifest['resource_url'] != part['url']:
            raise ValueError('Historical capture locator conflicts with reviewed binding')
        for field in ('sha256', 'byte_size', 'captured_at', 'content_type', 'http_status', 'reference_date'):
            if state.get(field) is not None and state[field] != manifest.get(field):
                raise ValueError('Historical index conflicts with immutable provenance')
            state[field] = manifest.get(field)
    return hydrated


def execute_batch(jobs, *, store, dsn, code_revision, authority_registry, series_registry):
    outcomes = []
    for job in jobs:
        progress = {'stage': 'archive_integrity'}
        def operation():
            progress['stage'] = 'archive_integrity'
            hydrated = hydrate_selected_job(job, store)
            return transform_one(hydrated, store=store, dsn=dsn, code_revision=code_revision,
                authority_registry=authority_registry, series_registry=series_registry, progress=progress)
        try:
            outcome = with_bounded_retry(operation, progress)
        except Exception as exc:
            outcome = {'source_key': job['source_key'], 'status': 'quarantined',
                       'stage': progress['stage'], 'error_type': type(exc).__name__,
                       'attempts': progress.get('attempts', 1),
                       'reason': 'edition_bound_parser_requires_review' if isinstance(exc, EditionReviewRequired) else 'stage_failed'}
            if isinstance(exc, EditionReviewRequired) and 'structural_inspection' in progress:
                outcome['structural_inspection'] = progress['structural_inspection']
            try:
                outcome['quarantine_age'] = quarantine_age(store, job, outcome)
            except Exception:
                outcome['quarantine_age'] = {'verified': False}
                outcome['diagnostic_failure'] = True
        outcome['interpretation_key'] = job['interpretation_key']
        outcome['capture_inputs'] = {label: {'capture_id': part['state']['capture_id'], 'sha256': part['state']['sha256']}
                                    for label, part in job['captures'].items()}
        outcomes.append(outcome)
    return outcomes


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--robot-head', required=True)
    parser.add_argument('--source-config', type=Path, default=Path('data/publication/multi_prefecture_pilot.json'))
    parser.add_argument('--shard', type=int, default=0)
    parser.add_argument('--shards', type=int, default=4)
    parser.add_argument('--cursor', type=int, default=0)
    parser.add_argument('--max-jobs', type=int, default=2)
    parser.add_argument('--expected-selection-sha256')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    if args.cursor and (not SHA40.fullmatch(args.robot_head) or not args.expected_selection_sha256):
        raise ValueError('Continuing requires the exact frozen robot revision and selection digest')
    root = Path('.').resolve()
    snapshots, metrics = read_robot_history(root, args.robot_head)
    jobs, issues = select_historical_jobs(snapshots, json.loads(args.source_config.read_text()), shard=args.shard, shards=args.shards)
    plan = selection_manifest(jobs)
    selection_sha = digest(plan)
    if args.expected_selection_sha256 and args.expected_selection_sha256 != selection_sha:
        raise ValueError('Historical cursor does not match the frozen selection')
    batch, coverage = select_batch(jobs, cursor=args.cursor, max_jobs=args.max_jobs)
    code = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    summary = {'schema_version': 1, 'robot_state_sha': metrics['robot_state_sha'],
               'selection_sha256': selection_sha, 'code_revision': code,
               'shard': args.shard, 'shards': args.shards, **coverage,
               'selection_review_items': len(issues), 'publications': 0}
    if args.dry_run:
        print(json.dumps({**summary, 'mode': 'selection_only_no_provider_or_database_verification'}, sort_keys=True))
        return 0
    from white_list_archive.storage.evidence import EvidenceStore, StoreConfig, client_for
    dsn = os.environ.get('EVIDENCE_DATABASE_URL')
    if not dsn:
        raise ValueError('Private historical interpretation requires the designated database writer')
    config = StoreConfig.from_env()
    store = EvidenceStore(client_for(config), config)
    outcomes = execute_batch(batch, store=store, dsn=dsn, code_revision=code,
        authority_registry=root/'data/source_registry/territorial_authorities.csv',
        series_registry=root/'data/source_registry/source_series_inventory.csv')
    report = {**summary, 'report_kind': 'bounded_historical_private_transform',
              'run_at': datetime.now(timezone.utc).isoformat(), 'planned_interpretations': plan,
              'selection_review_items': issues, 'outcomes': outcomes,
              'cursor_semantics': 'next_cursor advances attempts, not successful validation or approval'}
    persist_operational_report(store, report)
    summary.update(transformed=sum(r['status'] == 'parsed_private_review_required' for r in outcomes),
                   reused=sum(r['status'] == 'reused_private_interpretation' for r in outcomes),
                   quarantined=sum(r['status'] == 'quarantined' for r in outcomes),
                   database_verified=sum(r.get('database_readback') == 'verified' for r in outcomes),
                   diagnostic_failures=sum(bool(r.get('diagnostic_failure')) for r in outcomes),
                   private_report_verified=True)
    print(json.dumps(summary, sort_keys=True))
    return 1 if summary['quarantined'] or summary['diagnostic_failures'] else 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        raise SystemExit('Historical interpretation failed (' + type(exc).__name__ + ')') from None
