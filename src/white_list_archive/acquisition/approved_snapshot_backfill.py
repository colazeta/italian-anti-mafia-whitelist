"""Bounded private backfill of exact already-reviewed archived source inputs.

This does not approve editions, project canonical records or publish anything.
Discovery captures are never relabelled, and changed inputs remain quarantined.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from . import auto_transform as transform


def existing_snapshot(conn, job):
    """Verify complete input/config identities across prior code revisions.

    A backfill fills absence; it does not silently replace an interpretation
    because unrelated repository code has changed. Conflicting outputs fail closed.
    """
    from white_list_archive.publishing.frozen_release import configuration_sha256
    cfg = job['config']
    expected = {label: part['state']['sha256'] for label, part in job['captures'].items()}
    with conn.cursor() as cur:
        cur.execute('''
            SELECT pr.parse_run_id, jsonb_object_agg(i.input_label, co.sha256)
            FROM source.parse_run pr
            JOIN provenance.processing_activity pa ON pa.processing_activity_id=pr.processing_activity_id
            JOIN source.parse_snapshot ps ON ps.parse_run_id=pr.parse_run_id
            JOIN source.parse_run_input i ON i.parse_run_id=pr.parse_run_id
            JOIN source.content_object co ON co.content_object_id=i.content_object_id
            WHERE pa.software_name=%s AND pa.configuration_hash=%s
              AND pr.status_code='succeeded'
            GROUP BY pr.parse_run_id
        ''', (cfg['parser'], configuration_sha256(cfg)))
        matches = [str(identity) for identity, hashes in cur.fetchall() if hashes == expected]
    digests = set()
    from white_list_archive.persistence.parse_snapshot import snapshot_sha256
    for identity in matches:
        records, diagnostics = transform.read_snapshot_verified(conn, identity)
        if transform._quality_flags(cfg, records, diagnostics):
            raise ValueError('Previously stored approved-source snapshot has QA drift')
        digests.add(snapshot_sha256(records, diagnostics))
    if len(digests) > 1:
        raise ValueError('Conflicting approved-source interpretations require review')
    return bool(matches)


def backfill(jobs, *, limit, lookup, materialise):
    """Verify existing snapshots, then fill a bounded newest-first missing set."""
    if not 1 <= limit <= 8:
        raise ValueError('Backfill limit must be between one and eight')
    result = {'existing_verified': 0, 'materialised': 0, 'quarantined': 0, 'deferred': 0,
              'publications': 0, 'outcomes': []}
    attempted = 0
    for job in sorted(jobs, key=lambda j: (j['config'].get('reference_date', ''), j['source_key']), reverse=True):
        try:
            if transform._parse_config(job) != job['config']:
                raise ValueError('Backfill requires complete exact reviewed input identity')
            if lookup(job):
                result['existing_verified'] += 1
                continue
            if attempted >= limit:
                result['deferred'] += 1
                continue
            attempted += 1
            outcome = materialise(job)
            if outcome.get('database_readback') != 'verified' or outcome.get('qa_flags'):
                raise ValueError('Approved-source snapshot did not pass private readback and QA')
            if outcome.get('publication_approved') is not False:
                raise ValueError('Backfill cannot grant publication approval')
            result['materialised'] += 1
            result['outcomes'].append(outcome)
        except Exception as exc:
            result['quarantined'] += 1
            result['outcomes'].append({'source_key': job['source_key'], 'error_type': type(exc).__name__})
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--source-config', type=Path, required=True)
    parser.add_argument('--code-revision', required=True)
    parser.add_argument('--shard', type=int, default=0)
    parser.add_argument('--shards', type=int, default=1)
    parser.add_argument('--limit', type=int, default=4)
    args = parser.parse_args(argv)
    if transform._HEX40.fullmatch(args.code_revision) is None:
        raise SystemExit('An exact checked-out code revision is required')
    jobs, deferred = transform.select_reviewed_jobs(
        json.loads(args.state.read_text()), json.loads(args.source_config.read_text()),
        shard=args.shard, shards=args.shards, approved_only=True)
    from white_list_archive.storage.evidence import EvidenceStore, StoreConfig, client_for
    config = StoreConfig.from_env()
    store = EvidenceStore(client_for(config), config)
    dsn = os.environ['EVIDENCE_DATABASE_URL']

    def lookup(job):
        with transform.private_connection(dsn) as conn:
            return existing_snapshot(conn, job)

    report = backfill(jobs, limit=args.limit, lookup=lookup, materialise=lambda job: transform.transform_one(
        job, store=store, dsn=dsn, code_revision=args.code_revision,
        authority_registry=Path('data/source_registry/territorial_authorities.csv'),
        series_registry=Path('data/source_registry/source_series_inventory.csv')))
    report.update(schema_version=1, run_at=datetime.now(timezone.utc).isoformat(),
                  shard=args.shard, shards=args.shards, code_revision=args.code_revision,
                  missing_capture_bindings=len(deferred))
    from collections import Counter
    report['quarantine_error_types'] = dict(sorted(Counter(
        row['error_type'] for row in report['outcomes'] if 'error_type' in row).items()))
    transform.persist_operational_report(store, report)
    print(json.dumps({k: v for k, v in report.items() if k != 'outcomes'}, sort_keys=True))
    return int(bool(report['quarantined']))


if __name__ == '__main__':
    raise SystemExit(main())
