"""Deterministic private Cosenza review dossier; no edition or database writes."""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
import re
from uuid import UUID

from white_list_archive.acquisition.auto_transform import read_snapshot_verified
from white_list_archive.normalisation.cosenza_qa import assess
from white_list_archive.parsers import cosenza_combined_v2 as parser
from white_list_archive.persistence.parse_snapshot import snapshot_sha256
from white_list_archive.storage.capture_catalogue import CaptureCatalogue
from white_list_archive.storage.catalogue_recovery import load_catalogued_capture

CONTRACT = 'cosenza-private-review-v1'
PREFIX = 'operations/v1/cosenza-review/'
MAX_BYTES = 32_000_000
CHECKLIST = [
    {'item': 'document_identity', 'status': 'requires_review',
     'basis': 'Inspect the exact archived original and its catalogue provenance.'},
    {'item': 'administrative_reference_date', 'status': 'unknown',
     'basis': 'Capture times and owner command labels are not document reference dates.'},
    {'item': 'population_and_sector_scope', 'status': 'requires_review',
     'basis': 'Confirm document coverage and source activity wording from the original.'},
    {'item': 'identifier_identity_and_dates', 'status': 'requires_review',
     'basis': 'Candidate identifier shapes and observed dates are not canonical legal facts.'},
    {'item': 'temporal_document_differences', 'status': 'requires_review',
     'basis': 'Absence or changed wording alone proves no revocation, cancellation or interdiction.'},
    {'item': 'edition_attribution', 'status': 'blocked',
     'basis': 'An independently authenticated review and explicit attribution remain necessary.'},
    {'item': 'publication', 'status': 'blocked',
     'basis': 'Publication requires the separately authorised publisher and approval.'},
]


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def document_diff(before, after):
    """Compare document occurrences, never inferred enterprises or legal events."""
    old = Counter(row['record_hash'] for row in before)
    new = Counter(row['record_hash'] for row in after)
    removed, added = old - new, new - old
    groups = [defaultdict(list), defaultdict(list)]
    for rows, group in zip((before, after), groups):
        for row in rows:
            group[row['mention_key']].append(row)
    changes = []
    ambiguous = 0
    for key in sorted(set(groups[0]) & set(groups[1])):
        left, right = groups[0][key], groups[1][key]
        if len(left) != 1 or len(right) != 1:
            ambiguous += 1
            continue
        if left[0]['record_hash'] != right[0]['record_hash']:
            changes.append({'mention_key': key,
                'before_row_ordinal': left[0]['row_ordinal'],
                'after_row_ordinal': right[0]['row_ordinal'],
                'changed_fields': sorted(k for k in left[0] if k != 'row_ordinal'
                                         and left[0][k] != right[0][k])})
    def occurrences(counts):
        return [{'record_hash': key, 'occurrences': counts[key]} for key in sorted(counts)]
    return {'basis': 'explicit_input_order_document_occurrences_only',
        'before_rows': len(before), 'after_rows': len(after),
        'identical_occurrences': sum((old & new).values()),
        'before_only_occurrences': sum(removed.values()),
        'after_only_occurrences': sum(added.values()),
        'before_only_hashes': occurrences(removed), 'after_only_hashes': occurrences(added),
        'changed_unambiguous_document_mentions': changes,
        'ambiguous_shared_mention_groups': ambiguous,
        'legal_event_inference_performed': False}


def _pins(item):
    required = {'capture_id', 'parse_run_id', 'source_revision', 'expected_count'}
    if not isinstance(item, dict) or set(item) != required:
        raise ValueError('Exact dossier input pins required')
    result = dict(item)
    for key in ('capture_id', 'parse_run_id'):
        result[key] = str(UUID(result[key]))
    if not re.fullmatch('[0-9a-f]{40}', result['source_revision']):
        raise ValueError('Exact source parser revision required')
    if type(result['expected_count']) is not int or not 0 < result['expected_count'] <= 10_000:
        raise ValueError('Bounded source record denominator required')
    return result


def prepare_version(conn, store, item, dossier_code_revision):
    """Read-only QA plus original/snapshot readback precede dossier construction."""
    from white_list_archive.normalisation.cosenza_candidate import plan_records
    pins = _pins(item)
    qa = assess(conn, capture_id=pins['capture_id'], parse_run_id=pins['parse_run_id'],
        code_revision=pins['source_revision'], expected_count=pins['expected_count'],
        qa_code_revision=dossier_code_revision)
    if (qa.get('writes') != 0 or qa.get('semantic_ready') is not False
        or qa.get('publication_ready') is not False
        or qa.get('gates', {}).get('structural_parser_lineage', {}).get('status') != 'ready'):
        raise ValueError('Dossier source QA lacks complete verified lineage')
    manifest, receipt = load_catalogued_capture(CaptureCatalogue(store),
        source_key='cosenza-combined', capture_id=pins['capture_id'])
    original = store.read_verified(manifest)
    original_sha = hashlib.sha256(original).hexdigest()
    if (manifest.get('capture_id') != pins['capture_id'] or manifest.get('sha256') != original_sha
        or len(original) != manifest.get('byte_size') or qa.get('source_sha256') != original_sha):
        raise ValueError('Dossier original/capture/QA identity mismatch')
    records, diagnostics = read_snapshot_verified(conn, pins['parse_run_id'])
    snapshot_sha = snapshot_sha256(records, diagnostics)
    if (len(records) != pins['expected_count'] or qa.get('snapshot_sha256') != snapshot_sha
        or qa.get('capture_id') != pins['capture_id'] or qa.get('parse_run_id') != pins['parse_run_id']
        or qa.get('source_parser_code_revision') != pins['source_revision']):
        raise ValueError('Dossier QA/snapshot identity mismatch')
    qa = {key: value for key, value in qa.items() if key != 'verified_at'}
    pins.update(source_sha256=original_sha, snapshot_sha256=snapshot_sha,
        parser_name=parser.PARSER_NAME, parser_version=parser.PARSER_VERSION,
        parser_configuration_sha256=parser.PARSER_CONFIGURATION_HASH,
        schema_fingerprint=parser.SCHEMA_FINGERPRINT)
    candidate = plan_records(records, capture_id=pins['capture_id'],parse_run_id=pins['parse_run_id'],
        source_sha256=original_sha,snapshot_sha256=snapshot_sha,
        source_revision=pins['source_revision'],planner_revision=dossier_code_revision)
    if digest(candidate['private_payload']) != candidate['candidate_sha256']:
        raise ValueError('Candidate payload failed deterministic digest check')
    return {'pins': pins, 'capture_manifest': manifest, 'catalogue_receipt': receipt,
        'administrative_reference_date': None, 'reference_date_basis': 'not_reviewed',
        'qa': qa, 'candidate': candidate['private_payload'],
        'candidate_sha256': candidate['candidate_sha256'],
        'snapshot_diagnostics': diagnostics, 'records': records}


def _read(store, key):
    stream = store.client.get_object(Bucket=store.config.bucket, Key=key)['Body']
    try:
        data = stream.read(MAX_BYTES + 1)
    finally:
        stream.close()
    if len(data) > MAX_BYTES:
        raise ValueError('Private review object exceeds bound')
    return data


def _retain(store, key, body):
    from botocore.exceptions import ClientError
    if len(body) > MAX_BYTES:
        raise ValueError('Private review object exceeds bound')
    try:
        store.client.put_object(Bucket=store.config.bucket, Key=key, Body=body,
            ContentType='application/json', IfNoneMatch='*')
    except ClientError as exc:
        if not (exc.response.get('Error', {}).get('Code') == 'PreconditionFailed'
                or exc.response.get('ResponseMetadata', {}).get('HTTPStatusCode') == 412):
            raise
    if _read(store, key) != body:
        raise ValueError('Private review object failed exact readback')


def load_retained_review(store, dossier_sha256):
    """Private verified reader; callers must not print its row-level result."""
    if not re.fullmatch('[0-9a-f]{64}', dossier_sha256):
        raise ValueError('Exact private dossier digest required')
    body = _read(store, PREFIX + 'dossiers/' + dossier_sha256 + '.json')
    if hashlib.sha256(body).hexdigest() != dossier_sha256:
        raise ValueError('Private dossier failed digest verification')
    result = json.loads(body)
    if result.get('contract') != CONTRACT:
        raise ValueError('Unexpected private dossier contract')
    return result


def retain_review(conn, store, *, inputs, dossier_code_revision):
    """Retain one or two versions; only safe_summary is suitable for console output.

    Caller supplies explicit document comparison order and owns read-only database
    transaction rollback. This method never grants, commits, reparses or approves.
    """
    if not re.fullmatch('[0-9a-f]{40}', dossier_code_revision):
        raise ValueError('Exact dossier code revision required')
    if not isinstance(inputs, list) or not 1 <= len(inputs) <= 2:
        raise ValueError('One or two explicitly ordered dossier inputs required')
    pins = [_pins(item) for item in inputs]
    if len({(p['capture_id'], p['parse_run_id']) for p in pins}) != len(pins):
        raise ValueError('Duplicate dossier versions are not a comparison')
    versions = [prepare_version(conn, store, item, dossier_code_revision) for item in pins]
    comparison = document_diff(versions[0]['records'], versions[1]['records']) if len(versions) == 2 else None
    dossier = {'contract': CONTRACT, 'dossier_code_revision': dossier_code_revision,
        'comparison_order_basis': 'explicit_caller_input_order_not_administrative_dates',
        'versions': versions, 'document_comparison': comparison, 'review_checklist': CHECKLIST,
        'edition_approval': 'not_performed', 'semantic_ready': False, 'publication_ready': False,
        'database_writes': 0}
    body = canonical(dossier)
    dossier_sha = hashlib.sha256(body).hexdigest()
    dossier_key = PREFIX + 'dossiers/' + dossier_sha + '.json'
    _retain(store, dossier_key, body)
    receipt = {'contract': 'cosenza-private-review-receipt-v1', 'dossier_sha256': dossier_sha,
        'dossier_bytes': len(body), 'dossier_code_revision': dossier_code_revision,
        'ordered_input_pins': [version['pins'] for version in versions], 'immutable': True}
    receipt_body = canonical(receipt)
    receipt_sha = hashlib.sha256(receipt_body).hexdigest()
    receipt_key = PREFIX + 'receipts/' + receipt_sha + '.json'
    _retain(store, receipt_key, receipt_body)
    checkpoint_key = PREFIX + 'checkpoints/' + digest({'inputs': pins, 'dossier_code_revision': dossier_code_revision,
        'evidence_sha256': dossier_sha}) + '.json'
    _retain(store, checkpoint_key, receipt_body)
    summary = {'contract': CONTRACT, 'dossier_sha256': dossier_sha, 'receipt_sha256': receipt_sha,
        'immutable': True, 'versions_expected': len(pins), 'versions_verified': len(versions),
        'records_verified': sum(len(v['records']) for v in versions),
        'comparison_verified': comparison is not None,
        'identical_occurrences': comparison['identical_occurrences'] if comparison else None,
        'before_only_occurrences': comparison['before_only_occurrences'] if comparison else None,
        'after_only_occurrences': comparison['after_only_occurrences'] if comparison else None,
        'changed_document_mentions': len(comparison['changed_unambiguous_document_mentions']) if comparison else None,
        'administrative_reference_dates_unknown': len(versions),
        'database_writes': 0, 'edition_approvals': 0, 'semantic_ready': False, 'publication_ready': False}
    return {'dossier_sha256': dossier_sha, 'receipt_sha256': receipt_sha,
            'dossier_key': dossier_key, 'receipt_key': receipt_key, 'checkpoint_key': checkpoint_key,
            'safe_summary': summary}
