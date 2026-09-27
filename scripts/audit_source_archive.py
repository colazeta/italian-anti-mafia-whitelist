"""Archive reviewed source scopes independently; never publish or accept new facts."""
import argparse
import json
import os
from pathlib import Path

from white_list_archive.acquisition.archive_first import (
    acquire_and_archive, public_capture_receipt, _persist_if_configured,
)
from white_list_archive.persistence.source_series_registration import reviewed_source_series_context
from white_list_archive.storage.evidence import EvidenceStore, StoreConfig, client_for


def archive_sources(config, keys, store, work_dir, output):
    by_key = {source['source_key']: source for source in config['sources']}
    if len(by_key) != len(config['sources']) or len(keys) != len(set(keys)) or set(keys) - by_key.keys():
        raise ValueError('Unknown or duplicate source selection')
    for key in keys:
        reviewed_source_series_context(key, authority_csv=Path('data/source_registry/territorial_authorities.csv'), series_csv=Path('data/source_registry/source_series_inventory.csv'))
    # Separate capture/readback from approval. Even a changed or unparseable HTTP
    # response is evidence; it must not be relabelled as an approved source edition.
    results = []
    for key in keys:
        source = by_key[key]
        resources = source.get('resources') or {'document': {'resource_url': source['resource_url'], 'sha256': source['sha256']}}
        for label, resource in resources.items():
            try:
                capture = acquire_and_archive(
                    source_key=key, resource_url=resource['resource_url'],
                    reference_date=None, store=store, # current response may be a new edition or an interstitial
                    work_dir=work_dir / key, origin_type='official_current',
                    authority_rank_code='primary_official', resource_type_code='other',
                )
                database_state, _ = _persist_if_configured(capture, store)
                receipt = public_capture_receipt(capture, database_persistence_state=database_state)
                receipt['resource_label'] = label
                receipt['matches_reviewed_raw_bytes'] = capture.sha256 == resource['sha256']
                receipt['source_facts_promoted'] = False
                results.append(receipt)
            except Exception as error:
                # Provider/DB exception messages can contain private coordinates.
                results.append(dict(source_key=key, resource_label=label, capture_failed=True,
                                    error_type=type(error).__name__, source_facts_promoted=False))
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(results, indent=2) + '\n')
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path('data/publication/multi_prefecture_pilot.json'))
    parser.add_argument('--source-keys', nargs='+', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--work-dir', type=Path, required=True)
    args = parser.parse_args()
    required = ('EVIDENCE_BUCKET', 'EVIDENCE_ENDPOINT', 'EVIDENCE_POLICY_EVIDENCE', 'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY')
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        raise SystemExit('Missing approved archive configuration: ' + ', '.join(missing))
    config = StoreConfig.from_env()
    result = archive_sources(json.loads(args.config.read_text()), args.source_keys,
                             EvidenceStore(client_for(config), config), args.work_dir, args.output)
    print(json.dumps(result, sort_keys=True))
    if any(row.get('capture_failed') for row in result):
        raise SystemExit('One or more captures failed; successful immutable captures remain preserved.')
    if any(row['database_capture_persistence_state'] != 'persisted' for row in result):
        print('Originals and capture provenance verified; relational persistence remains incomplete.')
    if any(not row['matches_reviewed_raw_bytes'] for row in result):
        print('Changed responses were archived for review; no source facts were promoted.')


if __name__ == '__main__':
    main()
