"""Build a finite national candidate on trusted main, exporting only public derivatives."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

from white_list_archive.acquisition.auto_transform import private_connection
from white_list_archive.acquisition.recover_reviewed_manifest import recover
from white_list_archive.publishing import public_national_build, publication_handoff, public_snapshot
from white_list_archive.publishing.frozen_release import configuration_sha256
from white_list_archive.publishing.public_candidate_gate import validate_public_candidate
from white_list_archive.storage.evidence import StoreConfig, EvidenceStore, client_for


def stage(request_path, output):
    request = json.loads(request_path.read_text())
    intent = {**request['publication'], 'changes': request['changes']}
    selected = json.loads(Path(publication_handoff.SELECTOR).read_text())
    if configuration_sha256(selected) != intent['baseline_manifest_sha256']:
        return  # The reviewed baseline has already advanced.
    if not Path(intent['review_document']).is_file():
        raise ValueError('Publication review document missing')
    national = json.loads(Path('data/publication/multi_prefecture_pilot.json').read_text())
    updates = {s['source_key']: s for s in request['config']['sources']}
    national['sources'] = [updates.get(s['source_key'], s) for s in national['sources']]
    if configuration_sha256(national) != intent['source_config_sha256']:
        raise ValueError('Reconstructed national configuration differs from the reviewed intent')
    preserved = [s['source_key'] for s in national['sources'] if s['source_key'] not in updates]
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        national_path = root/'national.json'
        national_path.write_text(json.dumps(national))
        keys = root/'preserved.json'
        keys.write_text(json.dumps(preserved))
        private = root/'private'
        private.mkdir()
        cfg = StoreConfig.from_env()
        store = EvidenceStore(client_for(cfg), cfg)
        with private_connection(os.environ['EVIDENCE_DATABASE_URL']) as connection:
            receipt = recover(request_path, private, connection, store)
        # Consume the durable private handoff, independent of the producer's local file.
        digest = receipt['private_manifest_sha256']
        stream = store.client.get_object(Bucket=cfg.bucket,
            Key=f'operations/v1/reviewed-replay/manifests/{digest}.json')['Body']
        try:
            payload = stream.read(2_000_001)
        finally:
            stream.close()
        if len(payload) > 2_000_000 or hashlib.sha256(payload).hexdigest() != digest:
            raise ValueError('Private manifest readback mismatch')
        manifest = root/'verified.json'
        manifest.write_bytes(payload)
        data = root/'data'
        work = root/'work'
        public_national_build.main([
            '--require-archived-changes', '--source-config', str(national_path),
            '--release-manifest', str(manifest), '--runtime-code-revision', receipt['code_revision'],
            '--preserved-public-sources', str(keys), '--public-snapshot-manifest', publication_handoff.SELECTOR,
            '--verified-pages', 'data/source_registry/verified_primary_pages.csv',
            '--source-series', 'data/source_registry/source_series_inventory.csv',
            '--authority-aliases', 'data/source_registry/national_index_authority_aliases.csv',
            '--work-dir', str(work), '--registry-json', str(data/'registry.json'),
            '--registry-csv', str(data/'registry.csv'), '--prefectures-json', str(data/'prefectures.json'),
            '--prefectures-csv', str(data/'prefectures.csv')])
        registry = json.loads((data/'registry.json').read_text())
        validate_public_candidate(registry, json.loads((data/'prefectures.json').read_text()), national_path)
        bundle = root/'packed'
        packed = public_snapshot.pack(data, bundle, 'public-data-review-' + os.environ['GITHUB_RUN_ID'])
        before = root/'before'
        public_snapshot.restore(selected, before)
        approved, _ = publication_handoff.prepare_proposal(selected_manifest=selected, candidate_manifest=packed,
            selected_bytes=(before/'registry.json').read_bytes(), candidate_bytes=publication_handoff.verify_candidate_files(packed, data),
            config=national, monitoring=json.loads(Path(publication_handoff.MONITORING).read_text()), intent=intent)
        if approved['state'] != 'selector_proposal_ready':
            raise ValueError('Full national comparison did not validate the intended changes')
        diagnostics = {}
        for key in updates:
            diagnostic = json.loads((work/f'{key}.diagnostics.json').read_text())
            diagnostics[key] = {k: diagnostic[k] for k in ('public_records', 'dropped_date_rows') if k in diagnostic}
            if diagnostics[key]['public_records'] != intent['changes'][key]['count'] or diagnostics[key].get('dropped_date_rows', 0):
                raise ValueError('Incomplete source diagnostics')
        (bundle/'source-qa.json').write_text(json.dumps(diagnostics))
        output.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copytree(bundle, output/configuration_sha256(intent))
        print(json.dumps(approved), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    for path in sorted(Path('data/publication/archive_replay_requests').glob('*.json')):
        if 'publication' in json.loads(path.read_text()):
            stage(path, args.output)
