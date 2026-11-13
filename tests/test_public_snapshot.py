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


def test_missing_snapshot_never_falls_back_to_current_pages(monkeypatch, tmp_path):
    calls = []

    def missing(url, limit):
        calls.append(url)
        raise HTTPError(url, 404, 'missing', {}, None)

    monkeypatch.setattr(snapshot, 'download', missing)
    with pytest.raises(HTTPError):
        snapshot.restore(fixture_manifest(), tmp_path / 'data')
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


def test_publisher_and_source_candidate_cannot_cancel_each_other():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    publisher = (root / '.github/workflows/public-pages.yml').read_text()
    candidate = (root / '.github/workflows/public-registry-review.yml').read_text()
    def group(text):
        return next(line.strip() for line in text.splitlines() if line.strip().startswith('group:'))
    assert group(publisher) != group(candidate)
    assert 'white-list-public-national-build' not in publisher
    assert 'actions/deploy-pages' not in candidate


def test_public_snapshot_retries_connection_reset_without_changing_input(monkeypatch):
    import io
    from urllib.error import URLError
    from white_list_archive.publishing import public_snapshot
    calls = []
    def open_once(request, **kwargs):
        calls.append(request.full_url)
        if len(calls) == 1:
            raise URLError(ConnectionResetError('reset'))
        return io.BytesIO(b'verified downstream')
    monkeypatch.setattr(public_snapshot, 'urlopen', open_once)
    monkeypatch.setattr(public_snapshot.time, 'sleep', lambda _: None)
    url = 'https://github.com/colazeta/italian-anti-mafia-whitelist/releases/download/public-data-test/registry.json.gz'
    assert public_snapshot.download(url, 64) == b'verified downstream'
    assert calls == [url, url]


def test_live_verification_reads_only_actual_pages_and_pins_all_five_files(monkeypatch):
    from urllib.parse import urlparse
    calls = []
    def download(url, limit):
        calls.append(url)
        return urlparse(url).path.rsplit('/', 1)[-1].encode()
    monkeypatch.setattr(snapshot, 'download', download)
    result = snapshot.verify_live(fixture_manifest())
    assert result['live_files_verified'] == fixture_manifest()['files']
    assert len(calls) == 5 and all(url.startswith(snapshot.PAGES_URL + 'data/') for url in calls)
    assert all('snapshot=public-data-test' in url for url in calls)
    with pytest.raises(ValueError, match='origin'):
        snapshot.verify_live(fixture_manifest(), 'https://unreviewed.example/')
    with pytest.raises(ValueError, match='retry bound'):
        snapshot.verify_live(fixture_manifest(), attempts=0)


def test_live_cdn_propagation_is_retried_but_a_persistent_mismatch_never_passes(monkeypatch):
    from urllib.parse import urlparse
    calls, waits = [], []
    def download(url, limit):
        calls.append(url)
        name = urlparse(url).path.rsplit('/', 1)[-1]
        return b'stale' if name == 'history.json' and 'attempt=1' in url else name.encode()
    monkeypatch.setattr(snapshot, 'download', download)
    result = snapshot.verify_live(fixture_manifest(), sleep=waits.append)
    assert len(result['live_files_verified']) == 5 and len(calls) == 6 and waits == [5]
    calls.clear(); waits.clear()
    monkeypatch.setattr(snapshot, 'download', lambda url, limit: calls.append(url) or b'tampered')
    with pytest.raises(ValueError, match='integrity'):
        snapshot.verify_live(fixture_manifest(), attempts=2, sleep=waits.append)
    assert len(calls) == 2 and waits == [5]
    assert all(url.startswith(snapshot.PAGES_URL) and '/releases/' not in url for url in calls)
