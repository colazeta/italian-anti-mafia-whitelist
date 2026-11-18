"""Keep fully validated public review bundles addressable by publication intent."""
from pathlib import Path
import json
import re
import subprocess
import sys
import tempfile

from white_list_archive.publishing.public_snapshot import FILES

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


def retain(bundle, revision):
    if not re.fullmatch('[0-9a-f]{64}', bundle.name) or sorted(p.name for p in bundle.iterdir()) != ASSETS:
        raise ValueError('Unexpected intent directory or unapproved assets')
    tag = 'reviewed-intent-' + bundle.name
    existing = release(tag)
    if existing and not existing['isDraft']:
        verify_assets(existing)
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
