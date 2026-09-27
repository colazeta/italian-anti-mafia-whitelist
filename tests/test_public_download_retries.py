from io import BytesIO
from urllib.error import HTTPError

import pytest
from white_list_archive.publishing import public_national_registry as publishing


def test_retry_is_limited_to_failed_request_and_retains_both_versions(monkeypatch, tmp_path):
    path = tmp_path / 'source.pdf'
    calls, sleeps = [], []

    def fetch(request, timeout):
        calls.append(request.full_url)
        if len(calls) == 1:
            raise HTTPError(request.full_url, 503, 'temporary', {}, None)
        return BytesIO(b'first edition' if len(calls) == 2 else b'second edition')

    monkeypatch.setattr(publishing, 'urlopen', fetch)
    first = publishing._download('https://example.test/source', path, sleep=sleeps.append)
    second = publishing._download('https://example.test/source', path, sleep=sleeps.append)
    assert sleeps == [3]
    assert (tmp_path / 'content' / path.name / first).read_bytes() == b'first edition'
    assert (tmp_path / 'content' / path.name / second).read_bytes() == path.read_bytes() == b'second edition'


@pytest.mark.parametrize('status', [400, 401, 403, 404])
def test_permanent_http_failure_is_not_retried(monkeypatch, tmp_path, status):
    calls = []

    def fail(request, timeout):
        calls.append(request.full_url)
        raise HTTPError(request.full_url, status, 'permanent', {}, None)

    monkeypatch.setattr(publishing, 'urlopen', fail)
    with pytest.raises(HTTPError):
        publishing._download('https://example.test/source', tmp_path / 'source', sleep=lambda _: pytest.fail('must not sleep'))
    assert len(calls) == 1


def test_source_preflight_reports_all_failures_after_attempting_independent_inputs(monkeypatch, tmp_path):
    calls = []
    def acquire(source, directory):
        key = source['source_key']
        calls.append(key)
        if key == 'unavailable':
            raise HTTPError('https://example.test', 403, 'private error details', {}, None)
        path = directory / key
        path.write_bytes(b'recoverable original')
        return path, 'actual'
    monkeypatch.setattr(publishing, '_acquire_source_input', acquire)
    sources = [dict(source_key='changed', sha256='expected'), dict(source_key='unavailable', sha256='expected'), dict(source_key='good', sha256='actual')]
    with pytest.raises(RuntimeError) as error:
        publishing._prefetch_source_inputs({'sources': sources}, tmp_path)
    assert set(calls) == {'changed', 'unavailable', 'good'}
    assert 'changed: approved raw SHA mismatch' in str(error.value)
    assert 'unavailable: HTTPError HTTP 403' in str(error.value)
    assert 'private error details' not in str(error.value)
    assert (tmp_path / 'good').read_bytes() == b'recoverable original'
