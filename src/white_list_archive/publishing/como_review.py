"""Finite read-only review of the exact archived November Como originals."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile

from white_list_archive.acquisition.release_readiness import como_complete_physical_rows, explicit_update_date
from white_list_archive.publishing.incremental_audit import _digest
from white_list_archive.publishing.public_contract import public_record
from white_list_archive.publishing.public_national_registry import _download, _parse_source, _semantic_digest

# Exact originals independently read back from genuine CaptureCatalogue/R2 in
# Transform reviewed captures #43727548231, shard 1, not URL/date guesses.
PINS = {
    'como-listed': {'sha256': 'f8ea7067f3e2218d9e5b9ff1994dc6f30ba8fca3518ee39cde4a5af7b4733900',
        'records': 400, 'statuses': {'listed': 361, 'renewal_update_in_progress': 39},
        'semantic_sha256': '21a2c00e2ca8b9a276b01ead27f2312c583369c9716d2bc24be4f023c895be1e'},
    'como-applicants': {'sha256': 'afd73b6ee1286a4a4d8ac1cd26f2b44214c5b69150f87409bc612cdbc2241d8a',
        'records': 18, 'statuses': {'pending': 18},
        'semantic_sha256': 'e930da7209455cc8aaa1fc9fb81f21da50888dc7988e6b890c56426a8298a739'},
}
REFERENCE_DATE = '2026-11-10'


def inspect(path, cfg, *, checked_at):
    key = cfg['source_key']
    profile = PINS[key]
    expected_parser = 'como_html_' + ('listed' if key == 'como-listed' else 'applicants')
    if cfg.get('authority_key') != 'como' or cfg.get('register_key') != 'como-ordinary' or cfg.get('parser') != expected_parser:
        raise ValueError('Unreviewed Como parser/register binding')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != profile['sha256']:
        raise ValueError('Original differs from the independently archived source pin')
    if explicit_update_date(raw, checked_at) != REFERENCE_DATE:
        raise ValueError('Explicit official source date differs')
    candidate = {**cfg, 'reference_date': REFERENCE_DATE, 'sha256': profile['sha256']}
    batch = _parse_source(path, candidate)
    physical = como_complete_physical_rows(path, cfg['population_scope'])
    if (physical != profile['records'] or len(batch.records) != physical
            or batch.diagnostics.get('source_rows') != physical
            or batch.diagnostics.get('parser') != expected_parser
            or batch.diagnostics.get('parser_version') != '2'
            or batch.diagnostics.get('status_counts') != profile['statuses']
            or _semantic_digest(batch.records) != profile['semantic_sha256']):
        raise ValueError('Independent physical/semantic source census mismatch')
    records = [public_record(row) for row in batch.records]
    # Diagnostics are emitted through an explicitly numeric/closed projection.
    counts = {name: value for name, value in batch.diagnostics.items()
              if type(value) is int and name in {'source_rows', 'public_records', 'declared_count',
                  'declared_count_delta', 'identifier_coverage', 'raw_identifier_only',
                  'blank_identifier_rows', 'malformed_date_rows'}}
    return {'source_key': key, 'status': 'exact_source_review_metadata', 'bytes': len(raw),
            'sha256': profile['sha256'], 'reference_date': REFERENCE_DATE,
            'physical_rows': physical, 'records': len(records), 'counts': counts,
            'statuses': batch.diagnostics['status_counts'], 'semantic_sha256': profile['semantic_sha256'],
            'public_records_sha256': _digest(records), 'blank_names': sum(not r['name'] for r in records),
            'blank_activities': sum(not r['requested_activities'] for r in records),
            'approval_granted': False, 'publications': 0}


def main():
    config = json.loads(Path('data/publication/multi_prefecture_pilot.json').read_text())
    selected = [s for s in config['sources'] if s['authority_key'] == 'como']
    if {s['source_key'] for s in selected} != set(PINS):
        print(json.dumps({'status': 'incomplete_source_scope', 'publications': 0}))
        return 1
    result, failed = [], False
    with tempfile.TemporaryDirectory(prefix='como-exact-source-review-') as td:
        for cfg in selected:
            try:
                path = Path(td)/(cfg['source_key'] + '.html')
                _download(cfg['resource_url'], path)
                result.append(inspect(path, cfg, checked_at=datetime.now(timezone.utc).isoformat()))
            except Exception as exc:
                failed = True
                result.append({'source_key': cfg['source_key'], 'status': 'requires_source_review',
                               'error_type': type(exc).__name__, 'approval_granted': False})
    print(json.dumps({'sources': result, 'publications': 0, 'approval_granted': False}, sort_keys=True))
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
