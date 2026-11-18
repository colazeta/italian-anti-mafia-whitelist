"""Restore a reviewed public national candidate by its exact intent from trusted Actions."""
import gzip
import json
import os
from pathlib import Path
import subprocess
import tempfile

from white_list_archive.publishing.frozen_release import configuration_sha256
from white_list_archive.publishing.public_snapshot import FILES, restore as restore_selected, validate_manifest, verify
from white_list_archive.publishing.publication_handoff import records_digest
from white_list_archive.publishing.public_candidate_gate import validate_public_candidate


def output(name, value):
    with open(os.environ['GITHUB_OUTPUT'], 'a') as target:
        target.write(f'{name}={value}\n')


def api(path):
    return json.loads(subprocess.check_output(['gh', 'api', path]))


def pages(url, field):
    page = 1
    while True:
        rows = api(f'{url}&page={page}')[field]
        yield from rows
        if len(rows) < 100:
            return
        page += 1


def restore(bundle, changes, target, work):
    manifest = json.loads((bundle/'manifest.json').read_text())
    validate_manifest(manifest)
    diagnostics = json.loads((bundle/'source-qa.json').read_text())
    if set(diagnostics) != set(changes):
        raise ValueError('Trusted replay diagnostics do not cover the reviewed changes')
    work.mkdir(parents=True, exist_ok=True)
    for key, expected in changes.items():
        qa = diagnostics[key]
        if (Path(key).name != key or set(qa) - {'public_records', 'dropped_date_rows'}
                or qa.get('public_records') != expected['count'] or qa.get('dropped_date_rows', 0)):
            raise ValueError('Trusted replay source census failed')
        (work/f'{key}.diagnostics.json').write_text(json.dumps(qa))
    for name in sorted(FILES):
        spec = manifest['files'][name]
        with gzip.open(bundle/(name+'.gz')) as stream:
            body = stream.read(spec['bytes'] + 1)
        verify(body, spec, name)
        (target/name).write_bytes(body)


def main():
    root = Path('data/publication')
    intent = json.loads((root/'incremental_release_intent.json').read_text())
    config = json.loads((root/'multi_prefecture_pilot.json').read_text())
    preserved = json.loads((root/'preserved_public_sources.json').read_text())
    keys = {s['source_key'] for s in config['sources']}
    if keys == set(preserved):
        output('restored', 'false')
        return
    if (set(preserved) != keys - set(intent['changes']) or
            configuration_sha256(config) != intent['source_config_sha256']):
        raise ValueError('Mixed source scope, baseline or reviewed configuration mismatch')
    selected = json.loads((root/'public_snapshot.json').read_text())
    if configuration_sha256(selected) != intent['baseline_manifest_sha256']:
        # The selector can advance before its preservation inventory is enrolled.
        # Reuse the complete selected edition only when it independently proves
        # the exact reviewed config and every value in all changed scopes.
        target = Path('public-site/data')
        restore_selected(selected, target)
        registry = json.loads((target/'registry.json').read_text())
        validate_public_candidate(registry, json.loads((target/'prefectures.json').read_text()),
                                  root/'multi_prefecture_pilot.json')
        for key, spec in intent['changes'].items():
            rows = [r for r in registry['records'] if r['source_key'] == key]
            if records_digest(rows) != spec['records_sha256'] or any(r['capture_sha256'] != spec['sha256'] for r in rows):
                raise ValueError('Selected release does not contain the exact reviewed edition')
        output('restored', 'true')
        output('selected', 'true')
        return
    repository = os.environ['GITHUB_REPOSITORY']
    prefix = 'repos/' + repository
    runs_url = prefix+'/actions/workflows/public-registry-review.yml/runs?branch=main&per_page=100'
    identity = configuration_sha256(intent)
    tag = 'reviewed-intent-' + identity
    from reviewed_bundle_release import release, verify_assets
    # Trusted main must use this run's successful replay. A blocked current
    # request cannot borrow a prior successful bundle with the same intent.
    current_run = os.environ['GITHUB_RUN_ID'] if os.environ['GITHUB_REF'] == 'refs/heads/main' else None
    durable = None if current_run else release(tag)
    if durable and not durable['isDraft']:
        verify_assets(durable)
        with tempfile.TemporaryDirectory() as directory:
            subprocess.run(['gh', 'release', 'download', tag, '--dir', directory], check=True)
            restore(Path(directory), intent['changes'], Path('public-site/data'), Path('/tmp/public-national-sources'))
        output('restored', 'true')
        return
    runs = [api(f'{prefix}/actions/runs/{current_run}')] if current_run else pages(runs_url, 'workflow_runs')
    for run in runs:
        if (run['event'] not in {'push', 'workflow_dispatch'} or run['head_branch'] != 'main'
                or run['head_repository']['full_name'] != repository):
            continue
        run_id = run['id']
        artifacts = pages(f'{prefix}/actions/runs/{run_id}/artifacts?per_page=100', 'artifacts')
        for artifact in reversed(sorted(artifacts, key=lambda item: item['id'])):
            if current_run and str(artifact['id']) != os.environ.get('REVIEWED_ARTIFACT_ID'):
                continue
            if artifact['expired'] or not artifact['name'].startswith(f'reviewed-national-{run_id}-'):
                continue
            with tempfile.TemporaryDirectory() as directory:
                subprocess.run(['gh', 'run', 'download', str(run_id), '--repo', repository,
                                '--name', artifact['name'], '--dir', directory], check=True)
                bundle = Path(directory)/identity
                if not bundle.is_dir():
                    continue
                restore(bundle, intent['changes'], Path('public-site/data'), Path('/tmp/public-national-sources'))
                print(f'Verified five reviewed national derivatives from trusted main run {run_id}')
                output('restored', 'true')
                return
    raise ValueError('No trusted main replay artifact for the exact reviewed publication intent')


if __name__ == '__main__':
    main()
