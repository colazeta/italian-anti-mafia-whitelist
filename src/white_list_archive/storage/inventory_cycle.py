"""Bounded national recovery verification with private per-run shard checkpoints.

Every run attempt freezes its full denominator. Shards reread originals/provenance;
no earlier run's result is reused as a current provider verification.
"""
from __future__ import annotations

import argparse
import hashlib
import re

from datetime import datetime, timezone
import csv
import json
import subprocess
from pathlib import Path

from white_list_archive.storage.capture_catalogue import CaptureCatalogue
from white_list_archive.storage.catalogue_recovery import load_catalogued_capture
from white_list_archive.storage.evidence import EvidenceStore, StoreConfig, client_for
from white_list_archive.storage.robot_recovery import (
    collect_robot_capture_references, read_robot_history, rehydrate_robot_captures,
)
from white_list_archive.storage.recovery_materialize import (
    materialise_national_recovery,
)
from white_list_archive.storage.inventory_report import (
    persist_inventory_report, persist_private_inventory_document, read_private_inventory_document,
)
from white_list_archive.storage.recovery_migration import (
    materialise_migrating_recovery,
)


from white_list_archive.storage.recovery_evidence import build_repository_recovery_expectations

SHARDS = 4
CONTROLS = (
    ('potenza-combined', '3c8a4e28-ed29-4502-9b78-cb6e7382c92d', 'potenza'),
    ('aosta-listed', '5748d0d5-14a0-4c2d-9a26-6df0817a7dd5', 'aosta'),
    ('cosenza-combined', '9e769f09-3d3c-5d2a-b0f7-1b53ee5895c0', 'cosenza'),
    ('cosenza-combined', '32f713a4-2106-5c58-8256-6f3c02c133c3', 'cosenza'),
)
LEGACY_PATHS = (
    'data/captures/cosenza/combined_2026-06-28.json',
    'data/captures/cosenza/combined_2026-08-03.json',
)


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
        ensure_ascii=False, allow_nan=False).encode('utf-8')).hexdigest()


def robot_shard(reference):
    identity = [reference['source_key'], reference['capture_id']]
    return int(canonical_sha(identity), 16) % SHARDS


def row_identity(row):
    if row.get('identity_kind') == 'capture':
        return ('capture', row['source_key'], row['capture_id'])
    if row.get('identity_kind') == 'known_version':
        return ('known_version', row['authority_key'], row['evidence_version_key'], row['sha256'])
    raise ValueError('Unsupported recovery identity')


def expected_denominator(root, references):
    """Derive all expected identities without bucket discovery or source downloads."""
    repository = build_repository_recovery_expectations(
        repository_root=root, monitoring_path=root/'data/monitoring/national_coverage.json',
        captures_root=root/'data/captures', public_history_path=root/'data/history/public_history.json',
        generated_at='2000-01-01T00:00:00Z',
    )
    consumed = {'legacy-manifest:' + path for path in LEGACY_PATHS}
    known = repository['known_versions']
    if sum(row['evidence_version_key'] in consumed for row in known) != 2:
        raise ValueError('Expected exact legacy Cosenza denominator identities')
    expected = {}
    for row in known:
        if row['evidence_version_key'] in consumed:
            continue
        value = {**row, 'identity_kind': 'known_version', 'scope': 'shared'}
        expected[row_identity(value)] = value
    for source, capture, authority in CONTROLS:
        value = {'identity_kind': 'capture', 'source_key': source, 'capture_id': capture,
                 'authority_key': authority, 'scope': 'shared'}
        expected[row_identity(value)] = value
    for reference in references:
        value = {'identity_kind': 'capture', 'source_key': reference['source_key'],
                 'capture_id': reference['capture_id'], 'authority_key': reference['authority_key'],
                 'scope': robot_shard(reference), **reference['expected']}
        identity = row_identity(value)
        if identity in expected:
            if expected[identity]['authority_key'] != value['authority_key']:
                raise ValueError('Recovery denominator has conflicting authority ownership')
            # Existing controls remain shared, and the stronger robot hash metadata
            # still participates in the frozen expected denominator.
            value['scope'] = expected[identity]['scope']
        expected[identity] = value
    return expected


def expected_for_shard(expected, shard):
    if type(shard) is not int or not 0 <= shard < SHARDS:
        raise ValueError('Invalid inventory shard')
    return {key: row for key, row in expected.items() if row['scope'] in ('shared', shard)}


def denominator_sha(expected):
    return canonical_sha([expected[key] for key in sorted(expected)])


def validate_context(context, expected):
    if set(context) != {'schema_version', 'code_revision', 'robot_state_sha', 'generated_at',
                        'run_key', 'shards', 'denominator_items', 'denominator_sha256'}:
        raise ValueError('Invalid frozen inventory context')
    if context['schema_version'] != 1 or context['shards'] != SHARDS:
        raise ValueError('Invalid inventory context version')
    if any(not isinstance(context[k], str) or not re.fullmatch(r'[a-f0-9]{40}', context[k])
           for k in ('code_revision', 'robot_state_sha')):
        raise ValueError('Inventory context requires exact code and robot-state revisions')
    if not re.fullmatch(r'[0-9]+-[0-9]+', context['run_key']):
        raise ValueError('Inventory context requires a run-attempt identity')
    timestamp = datetime.fromisoformat(context['generated_at'].replace('Z', '+00:00'))
    if timestamp.tzinfo is None:
        raise ValueError('Inventory checkpoint timestamp requires a timezone')
    if context['denominator_items'] != len(expected) or context['denominator_sha256'] != denominator_sha(expected):
        raise ValueError('Inventory context does not match the complete frozen denominator')


def shard_key(context, shard):
    expected_for_shard({}, shard)  # Validate the closed shard index range.
    return f"operations/v1/recovery-inventory-shards/{context['run_key']}/shard-{shard}.json.gz"


def validate_inventory_rows(inventory, expected):
    rows = inventory.get('items')
    if inventory.get('schema_version') != 1 or not isinstance(rows, list):
        raise ValueError('Invalid private inventory shard')
    if inventory.get('metrics', {}).get('denominator_items') != len(rows):
        raise ValueError('Inventory shard count conflicts with its rows')
    if inventory.get('recovery_search_complete') is not False:
        raise ValueError('Shard cannot infer a completed recovery search')
    seen = set()
    for row in rows:
        identity = row_identity(row)
        if identity in seen or identity not in expected:
            raise ValueError('Inventory shard contains a duplicate or unexpected identity')
        seen.add(identity)
        target = expected[identity]
        for field in ('authority_key', 'source_key', 'sha256', 'byte_size'):
            if field in target and target[field] is not None and row.get(field) != target[field]:
                raise ValueError('Inventory shard conflicts with frozen expected provenance')
        if row['status'] not in {'verified', 'recoverable_pending', 'missing', 'not_verified'}:
            raise ValueError('Invalid inventory recovery status')
        if identity[0] == 'capture' and not (
            row['status'] == 'verified' and row['durable_original_verified'] is True
            and row['capture_provenance_verified'] is True
        ):
            raise ValueError('A selected capture lacks independent original/provenance verification')
    if seen != set(expected):
        raise ValueError('Inventory shard does not cover its exact frozen denominator')


def merge_inventory_shards(documents, context, expected):
    """Reduce only a complete matching run attempt; partial/stale results fail closed."""
    validate_context(context, expected)
    if len(documents) != SHARDS:
        raise ValueError('All inventory shards are required')
    merged, seen = {}, set()
    published = None
    for document in documents:
        if (document.get('schema_version') != 1 or
            document.get('report_kind') != 'national_recovery_inventory_shard' or
            document.get('complete_denominator') is not False or
            document.get('shard_complete') is not True or
            document.get('context') != context):
            raise ValueError('Inventory shard belongs to another frozen run attempt')
        shard = document.get('shard')
        if shard in seen:
            raise ValueError('Duplicate inventory shard')
        seen.add(shard)
        inventory = document['inventory']
        validate_inventory_rows(inventory, expected_for_shard(expected, shard))
        if inventory.get('generated_at') != context['generated_at']:
            raise ValueError('Inventory shard checkpoint timestamp mismatch')
        scopes = inventory.get('published_release_scopes', [])
        if published is not None and scopes != published:
            raise ValueError('Inventory shard publication denominators disagree')
        published = scopes
        for row in inventory['items']:
            identity = row_identity(row)
            if identity in merged and merged[identity] != row:
                raise ValueError('Overlapping shard verification evidence disagrees')
            merged[identity] = row
    if seen != set(range(SHARDS)) or set(merged) != set(expected):
        raise ValueError('Incomplete national inventory denominator')
    rows = [merged[key] for key in sorted(merged)]
    counts = {status: sum(row['status'] == status for row in rows)
              for status in ('verified', 'recoverable_pending', 'missing', 'not_verified')}
    metrics = {
        'source_authorities_covered': len({r['authority_key'] for r in rows}),
        'denominator_items': len(rows),
        'captures_expected': sum(r['identity_kind'] == 'capture' for r in rows),
        'known_versions_without_capture_identity': sum(r['identity_kind'] == 'known_version' for r in rows),
        'distinct_content_objects_known': len({r['sha256'] for r in rows}),
        'durably_retrievable_content_objects': len({r['sha256'] for r in rows if r['durable_original_verified']}),
        'captures_with_verified_provenance': sum(r['capture_provenance_verified'] for r in rows),
        'published_release_scopes': len(published),
        'published_release_authorities': len({r['authority_key'] for r in published}),
        **counts,
    }
    return {'schema_version': 1, 'generated_at': context['generated_at'],
            'recovery_search_complete': False, 'metrics': metrics, 'items': rows,
            'published_release_scopes': published}


def source_references(root, robot_head):
    with (root/'data/source_registry/source_series_inventory.csv').open(encoding='utf-8', newline='') as handle:
        authorities = {row['source_series_key']: row['authority_key'] for row in csv.DictReader(handle)}
    snapshots, metrics = read_robot_history(root, robot_head)
    references, selection = collect_robot_capture_references(snapshots, authorities)
    metrics.update(selection)
    return references, metrics


def run_shard(root, store, context, shard):
    generated_at = context['generated_at']
    catalogue = CaptureCatalogue(store)

    def read_capture(source_key, capture_id):
        try:
            return load_catalogued_capture(catalogue, source_key=source_key, capture_id=capture_id)
        except Exception:
            raise SystemExit(f'Capture catalogue not verified: {source_key}/{capture_id}') from None

    authorities = {}
    with (root / 'data/source_registry/source_series_inventory.csv').open(
        encoding='utf-8', newline=''
    ) as handle:
        for row in csv.DictReader(handle):
            source_key = (row.get('source_series_key') or '').strip()
            authority_key = (row.get('authority_key') or '').strip()
            if source_key and authority_key:
                prior = authorities.get(source_key)
                if prior is not None and prior != authority_key:
                    raise SystemExit(
                        'Reviewed SourceSeries registry has conflicting authority ownership'
                    )
                authorities[source_key] = authority_key

    controls = (
        ('potenza-combined', '3c8a4e28-ed29-4502-9b78-cb6e7382c92d'),
        ('aosta-listed', '5748d0d5-14a0-4c2d-9a26-6df0817a7dd5'),
    )
    captures = []
    for source_key, capture_id in controls:
        authority_key = authorities.get(source_key)
        if not authority_key:
            raise SystemExit(f'Reviewed authority binding unavailable for {source_key}')
        manifest, receipt = read_capture(source_key, capture_id)
        captures.append(
            {
                'authority_key': authority_key,
                'capture': manifest,
                'catalogue': receipt,
                'recovery_paths': [],
                'durable_absence_confirmed': False,
                'operator_evidence_refs': [
                    f'lane-a-governed-catalogue-proof:{source_key}:{capture_id}'
                ],
            }
        )


    print('recovery_phase=repository_baseline')
    baseline = materialise_national_recovery(
        repository_root=root,
        store=store,
        plan={
            'schema_version': 1,
            'generated_at': generated_at,
            'recovery_search_complete': False,
            'captures': captures,
            'known_version_recovery': [],
        },
    )

    snapshots, robot_metrics = read_robot_history(root, context['robot_state_sha'])
    references, selection_metrics = collect_robot_capture_references(snapshots, authorities)
    robot_metrics.update(selection_metrics)
    full_expected = expected_denominator(root, references)
    validate_context(context, full_expected)
    controls = {(source, capture) for source, capture, _ in CONTROLS}
    references = [row for row in references if robot_shard(row) == shard
                  and (row['source_key'], row['capture_id']) not in controls]
    print('recovery_phase=shard_catalogue_hydration')
    recovered_robots = rehydrate_robot_captures(references, catalogue)
    existing = {(row['capture']['source_key'], row['capture']['capture_id']) for row in captures}
    additions = [row for row in recovered_robots
                 if (row['capture']['source_key'], row['capture']['capture_id']) not in existing]
    captures.extend(additions)
    robot_metrics['robot_captures_added_to_denominator'] = len(additions)
    print('robot_recovery_selection=' + json.dumps(robot_metrics, sort_keys=True))

    # These exact historical identities passed real provider/catalogue readback
    # in run 36511913025. Reuse that recovery; never mint a new capture from a hash.
    specs = (
        ('data/captures/cosenza/combined_2026-06-28.json', '9e769f09-3d3c-5d2a-b0f7-1b53ee5895c0'),
        ('data/captures/cosenza/combined_2026-08-03.json', '32f713a4-2106-5c58-8256-6f3c02c133c3'),
    )

    migrations = []
    migrated_identities = []
    for manifest_path, capture_id in specs:
        historical = json.loads((root / manifest_path).read_text())
        manifest, receipt = read_capture('cosenza-combined', capture_id)
        expected = {key: historical[key] for key in (
            'sha256', 'byte_size', 'captured_at', 'reference_date', 'resource_url',
            'content_type', 'http_status', 'etag', 'last_modified',
        )}
        expected['resolved_url'] = historical['final_url']
        if any(manifest.get(key) != value for key, value in expected.items()):
            raise SystemExit('Recovered Cosenza catalogue conflicts with historical provenance')
        version_key = 'legacy-manifest:' + manifest_path
        migrations.append(
            {
                'authority_key': 'cosenza',
                'evidence_version_key': version_key,
                'sha256': manifest['sha256'],
                'capture': manifest,
                'catalogue': receipt,
                'operator_evidence_refs': [
                    manifest_path,
                    'github-actions-run:34051655207',
                    'github-actions-run:36511913025',
                ],
            }
        )
        migrated_identities.append(
            (manifest['source_key'], manifest['capture_id'], version_key)
        )
        print(
            'recovered_cosenza_capture=' + json.dumps(
                {
                    'source_key': manifest['source_key'],
                    'capture_id': manifest['capture_id'],
                    'reference_date': manifest['reference_date'],
                    'captured_at': manifest['captured_at'],
                    'sha256': manifest['sha256'],
                    'byte_size': manifest['byte_size'],
                    'durable_capture_provenance_readback_verified': True,
                    'read_only_reverification': True,
                },
                sort_keys=True,
            )
        )

    print('recovery_phase=shard_denominator_verification')
    migrated = materialise_migrating_recovery(
        repository_root=root,
        store=store,
        plan={
            'schema_version': 2,
            'generated_at': generated_at,
            'recovery_search_complete': False,
            'captures': captures,
            'known_version_recovery': [],
            'capture_migrations': migrations,
        },
    )

    before = baseline['metrics']
    after = migrated['metrics']
    print('baseline_recovery_metrics=' + json.dumps(before, sort_keys=True))
    print('shard_recovery_metrics=' + json.dumps(after, sort_keys=True))

    expected_deltas = {
        'denominator_items': len(additions),
        'captures_with_verified_provenance': len(additions) + 2,
        'known_versions_without_capture_identity': -2,
        'verified': len(additions) + 2,
        'recoverable_pending': 0,
        'missing': 0,
        'not_verified': -2,
    }
    for key, delta in expected_deltas.items():
        actual = after[key] - before[key]
        if actual != delta:
            raise SystemExit(
                f'Unexpected recovery migration delta for {key}: expected {delta}, got {actual}'
            )

    capture_items = {
        (item.get('source_key'), item.get('capture_id')): item
        for item in migrated['items']
        if item.get('identity_kind') == 'capture'
    }
    known_keys = {
        item.get('evidence_version_key')
        for item in migrated['items']
        if item.get('identity_kind') == 'known_version'
    }
    for source_key, capture_id, version_key in migrated_identities:
        item = capture_items.get((source_key, capture_id))
        if item is None:
            raise SystemExit(f'Migrated capture missing from denominator: {capture_id}')
        if item['status'] != 'verified':
            raise SystemExit(f'Migrated capture is not verified: {capture_id}')
        if not item['durable_original_verified'] or not item['capture_provenance_verified']:
            raise SystemExit(f'Migrated capture lacks complete provider readback: {capture_id}')
        if version_key in known_keys:
            raise SystemExit(f'Consumed legacy version remains double-counted: {version_key}')

    # A shard is a verified subset checkpoint; only the final reducer may claim
    # the full selected denominator was covered.
    validate_inventory_rows(migrated, expected_for_shard(full_expected, shard))
    report = {
        'schema_version': 1, 'report_kind': 'national_recovery_inventory_shard',
        'context': context, 'shard': shard, 'inventory': migrated,
        'complete_denominator': False, 'shard_complete': True,
    }
    persist_private_inventory_document(store, report, key=shard_key(context, shard))
    print('private_inventory_shard_verified=true')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('freeze', 'shard', 'merge'))
    parser.add_argument('--robot-head', required=True)
    parser.add_argument('--run-key', required=True)
    parser.add_argument('--generated-at')
    parser.add_argument('--denominator-sha256')
    parser.add_argument('--denominator-items', type=int)
    parser.add_argument('--shard', type=int)
    args = parser.parse_args(argv)
    root = Path('.').resolve()
    code = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    references, robot_metrics = source_references(root, args.robot_head)
    expected = expected_denominator(root, references)
    context = {'schema_version': 1, 'code_revision': code, 'robot_state_sha': robot_metrics['robot_state_sha'],
               'generated_at': args.generated_at or datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
               'run_key': args.run_key, 'shards': SHARDS, 'denominator_items': len(expected),
               'denominator_sha256': denominator_sha(expected)}
    if args.mode == 'freeze':
        validate_context(context, expected)
        for key in ('code_revision', 'robot_state_sha', 'generated_at', 'denominator_items', 'denominator_sha256'):
            print(f'{key}={context[key]}')
        return 0
    if (args.denominator_items != context['denominator_items'] or
        args.denominator_sha256 != context['denominator_sha256'] or not args.generated_at):
        raise ValueError('Execution differs from the full frozen denominator')
    validate_context(context, expected)
    config = StoreConfig.from_env()
    store = EvidenceStore(client_for(config), config)
    if args.mode == 'shard':
        expected_for_shard(expected, args.shard)
        run_shard(root, store, context, args.shard)
    else:
        documents = [read_private_inventory_document(store, key=shard_key(context, shard))
                     for shard in range(SHARDS)]
        inventory = merge_inventory_shards(documents, context, expected)
        robot_metrics['robot_captures_added_to_denominator'] = len(
            [ref for ref in references if (ref['source_key'], ref['capture_id']) not in
             {(s, c) for s, c, _ in CONTROLS}])
        robot_metrics['verification_shards'] = SHARDS
        digest = persist_inventory_report(store, inventory=inventory,
                                          robot_metrics=robot_metrics, code_revision=code)
        print('migrated_recovery_metrics=' + json.dumps(inventory['metrics'], sort_keys=True))
        print('private_inventory_report_sha256=' + digest)
        print('private_inventory_report_verified=true')
        print('selected_robot_captures_verified=true')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        raise SystemExit('Private inventory checkpoint failed (' + type(exc).__name__ + ')') from None
