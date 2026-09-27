import copy
import gzip
import hashlib
from urllib.error import HTTPError

import pytest

from white_list_archive.publishing import public_snapshot as snapshot


def fixture_manifest():
    return dict(schema_version=1, repository=snapshot.REPOSITORY, release_tag='public-data-test',
                files={name: dict(sha256=hashlib.sha256(name.encode()).hexdigest(), bytes=len(name))
                       for name in snapshot.FILES})


def test_restore_checks_all_bytes_before_replacing_any_output(monkeypatch, tmp_path):
    manifest = fixture_manifest()
    destination = tmp_path / 'data'
    destination.mkdir()
    (destination / 'registry.json').write_text('previous approved data')

    def download(url, limit):
        name = url.split('/')[-1][:-3]
        return gzip.compress((name if name != 'history.json' else 'tampered').encode())

    monkeypatch.setattr(snapshot, 'download', download)
    with pytest.raises(ValueError, match='integrity'):
        snapshot.restore(manifest, destination)
    assert (destination / 'registry.json').read_text() == 'previous approved data'
    assert len(list(destination.iterdir())) == 1
    monkeypatch.setattr(snapshot, 'download', lambda url, limit: gzip.compress(url.split('/')[-1][:-3].encode()))
    snapshot.restore(manifest, destination)
    assert {p.name for p in destination.iterdir()} == snapshot.FILES


def test_bootstrap_cannot_be_used_for_arbitrary_snapshots(monkeypatch, tmp_path):
    calls = []

    def missing(url, limit):
        calls.append(url)
        raise HTTPError(url, 404, 'missing', {}, None)

    monkeypatch.setattr(snapshot, 'download', missing)
    with pytest.raises(HTTPError):
        snapshot.restore(fixture_manifest(), tmp_path / 'data', allow_bootstrap=True)
    assert len(calls) == 1 and '/releases/download/' in calls[0]


@pytest.mark.parametrize('defect', ['path', 'host', 'size', 'tag'])
def test_snapshot_manifest_limits_publication_surface(defect):
    manifest = copy.deepcopy(fixture_manifest())
    if defect == 'path':
        manifest['files']['../private.json'] = manifest['files'].pop('history.json')
    elif defect == 'host':
        manifest['repository'] = 'unreviewed/other'
    elif defect == 'size':
        manifest['files']['history.json']['bytes'] = 1_000_000_000
    else:
        manifest['release_tag'] = '../latest'
    with pytest.raises(ValueError):
        snapshot.validate_manifest(manifest)


def test_pack_emits_only_approved_derivatives_and_reproducible_gzip(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    for name in snapshot.FILES:
        (source / name).write_text(name)
    (source / 'private-source.pdf').write_text('not for publication')
    a, b = tmp_path / 'a', tmp_path / 'b'
    assert snapshot.pack(source, a, 'public-data-test') == fixture_manifest()
    snapshot.pack(source, b, 'public-data-test')
    assert {p.name for p in a.iterdir()} == {name + '.gz' for name in snapshot.FILES} | {'manifest.json'}
    assert all((a / (name + '.gz')).read_bytes() == (b / (name + '.gz')).read_bytes() for name in snapshot.FILES)
