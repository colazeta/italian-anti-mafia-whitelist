"""Keep fully validated public review bundles addressable by publication intent."""
from pathlib import Path
import json
import gzip
import hashlib
import re
import subprocess
import sys
import tempfile

from white_list_archive.publishing.public_snapshot import FILES, validate_manifest, verify

ASSETS = sorted({'manifest.json', 'source-qa.json'} | {name + '.gz' for name in FILES})


def release(tag):
    result = subprocess.run(['gh', 'release', 'view', tag, '--json', 'isDraft,isPrerelease,assets'],
                            capture_output=True, text=True)
    if result.returncode:
        if 'not found' in result.stderr.lower():
            return None
        raise RuntimeError('Could not inspect candidate release')
    return json.loads(result.stdout)


def verify_assets(info):
    if not info['isPrerelease'] or sorted(a['name'] for a in info['assets']) != ASSETS:
        raise ValueError('Incomplete or unexpected candidate release')


def comparable(value):
    if isinstance(value, dict):
        return {k: comparable(v) for k, v in value.items()
                if k not in {'generated_at', 'document_checked_at'}}
    if isinstance(value, list):
        return [comparable(v) for v in value]
    return value


def retain(bundle, revision):
    if not re.fullmatch('[0-9a-f]{64}', bundle.name) or sorted(p.name for p in bundle.iterdir()) != ASSETS:
        raise ValueError('Unexpected intent directory or unapproved assets')
    tag = 'reviewed-intent-' + bundle.name
    existing = release(tag)
    if existing and not existing['isDraft']:
        verify_assets(existing)
        with tempfile.TemporaryDirectory() as directory:
            remote = Path(directory)
            subprocess.run(['gh', 'release', 'download', tag, '--dir', directory], check=True)
            if all((remote/n).read_bytes() == (bundle/n).read_bytes() for n in ASSETS):
                return
            # Fresh builds have a new tag and verification timestamps. Verify
            # the retained files against their manifest and the reviewed build.
            manifest = json.loads((remote/'manifest.json').read_bytes())
            validate_manifest(manifest)
            for asset in existing['assets']:
                path = remote/asset['name']
                if asset.get('digest') != 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest():
                    raise ValueError('Published asset digest mismatch')
            for name in FILES:
                spec = manifest['files'][name]
                with gzip.open(remote/(name+'.gz')) as source:
                    body = source.read(spec['bytes'] + 1)
                verify(body, spec, name)
                with gzip.open(bundle/(name+'.gz')) as source:
                    fresh = source.read()
                if body == fresh:
                    continue
                if not name.endswith('.json') or comparable(json.loads(body)) != comparable(json.loads(fresh)):
                    raise ValueError('Published derivative differs from reviewed build')
            if json.loads((remote/'source-qa.json').read_bytes()) != json.loads((bundle/'source-qa.json').read_bytes()):
                raise ValueError('Published diagnostics differ from reviewed build')
        return
    if not existing:
        subprocess.run(['gh', 'release', 'create', tag, '--draft', '--prerelease', '--latest=false',
                        '--target', revision, '--title', tag,
                        '--notes', 'Verified public review files. Deployment uses the selected public-data release.'], check=True)
    subprocess.run(['gh', 'release', 'upload', tag, '--clobber', *[str(bundle/n) for n in ASSETS]], check=True)
    verify_assets(release(tag))
    with tempfile.TemporaryDirectory() as directory:
        subprocess.run(['gh', 'release', 'download', tag, '--dir', directory], check=True)
        for name in ASSETS:
            if (Path(directory)/name).read_bytes() != (bundle/name).read_bytes():
                raise ValueError('Candidate asset readback mismatch')
    subprocess.run(['gh', 'release', 'edit', tag, '--draft=false', '--prerelease', '--latest=false'], check=True)


if __name__ == '__main__':
    failures = []
    for bundle in sorted(Path(sys.argv[1]).glob('*')):
        try:
            retain(bundle, sys.argv[2])
        except Exception as error:
            failures.append(bundle.name)
            print(f'::warning::Retention failed for {bundle.name} ({type(error).__name__})')
    if failures:
        raise SystemExit(1)
