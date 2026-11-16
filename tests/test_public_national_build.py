import csv
from pathlib import Path
from urllib.error import URLError

from white_list_archive.publishing.public_national_build import (
    _alias_inputs,
    _build_registry_with_network_retries,
)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_alias_inputs_preserve_canonical_rows_and_add_national_index_view(tmp_path):
    verified = tmp_path / "verified.csv"
    series = tmp_path / "series.csv"
    aliases = tmp_path / "aliases.csv"
    write_csv(
        verified,
        ["authority_key", "landing_url", "verification_date", "verification_status"],
        [{"authority_key": "bolzano-bozen", "landing_url": "https://example.test/bolzano", "verification_date": "2026-09-07", "verification_status": "verified"}],
    )
    write_csv(
        series,
        ["source_series_key", "authority_key", "publication_model"],
        [{"source_series_key": "bolzano-listed", "authority_key": "bolzano-bozen", "publication_model": "linked_series_page"}],
    )
    write_csv(
        aliases,
        ["national_index_key", "catalog_authority_key", "reason"],
        [{"national_index_key": "bolzano", "catalog_authority_key": "bolzano-bozen", "reason": "bilingual canonical key"}],
    )

    verified_out, series_out = _alias_inputs(verified, series, aliases, tmp_path / "out")
    verified_rows = read_csv(verified_out)
    series_rows = read_csv(series_out)

    assert {row["authority_key"] for row in verified_rows} == {"bolzano-bozen", "bolzano"}
    assert {row["authority_key"] for row in series_rows} == {"bolzano-bozen", "bolzano"}
    assert next(row for row in verified_rows if row["authority_key"] == "bolzano")["landing_url"] == "https://example.test/bolzano"
    assert next(row for row in series_rows if row["authority_key"] == "bolzano")["source_series_key"] == "bolzano-listed"


def test_registry_failure_preserves_successfully_acquired_evidence(monkeypatch, tmp_path):
    import white_list_archive.publishing.public_national_build as build
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    original = work_dir / "already-captured.pdf"
    original.write_bytes(b"observed source bytes")
    calls = []

    def failed(config, path):
        calls.append(path)
        raise URLError("source unavailable after per-request retries")

    monkeypatch.setattr(build, "build_registry", failed)
    import pytest
    with pytest.raises(URLError):
        _build_registry_with_network_retries({"sources": []}, work_dir)
    assert calls == [work_dir]
    assert original.read_bytes() == b"observed source bytes"


def test_registry_does_not_retry_semantic_failures(monkeypatch, tmp_path):
    import white_list_archive.publishing.public_national_build as build

    calls = 0

    def invalid(config, path):
        nonlocal calls
        calls += 1
        raise RuntimeError("fixture hash or semantic failure")

    monkeypatch.setattr(build, "build_registry", invalid)
    try:
        _build_registry_with_network_retries(
            {"sources": []}, tmp_path / "work"
        )
    except RuntimeError as exc:
        assert "semantic" in str(exc)
    else:
        raise AssertionError("semantic failures must not be retried")
    assert calls == 1


def test_public_edition_date_does_not_use_page_modification_date(monkeypatch, tmp_path):
    import white_list_archive.publishing.public_national_registry as publishing
    from white_list_archive.acquisition.national_index import NationalIndexEntry
    entries = [NationalIndexEntry(str(i), "White List", f"https://example.test/it/prefetture/p{i}/white-list", "https://example.test/index") for i in range(90)]
    entries.append(NationalIndexEntry("Sito tipo", "White List", "https://example.test/it/prefetture/sito-tipo/white-list", "https://example.test/index"))
    monkeypatch.setattr(publishing, "discover_national_index", lambda **kw: entries)
    verified, series = tmp_path / "pages.csv", tmp_path / "series.csv"
    write_csv(verified, ["authority_key", "landing_url", "verification_date"], [{"authority_key": "p0", "landing_url": entries[0].white_list_url, "verification_date": "2026-09-06"}])
    write_csv(series, ["authority_key", "publication_model"], [])
    config = {"sources": [{"authority_key": "p0", "reference_date": "2026-09-05", "last_source_update": "2026-09-07", "register_name": "Ordinary"}]}
    result = publishing.build_prefecture_index(config, verified, series)
    assert len(entries) == 91  # Original discovery evidence remains untouched.
    assert result["meta"]["authority_count"] == 90
    assert not any(r["authority_key"] == "sito-tipo" for r in result["prefectures"])
    row = next(r for r in result["prefectures"] if r["authority_key"] == "p0")
    assert row["last_source_update"] == "2026-09-05"
    assert row["last_project_check"] == "2026-09-06"


def test_all_preserved_release_uses_verified_approved_derivatives_without_network(monkeypatch, tmp_path):
    import json
    import pytest
    import white_list_archive.publishing.public_national_build as build
    cfg = {
        'source_key': 'test-listed', 'authority_key': 'test', 'register_key': 'test-ordinary',
        'population_scope': 'listed', 'reference_date': '2026-11-06',
        'parser': 'test_parser', 'sha256': 'a' * 64,
        'source_page_url': 'https://official.example/source',
        'resource_url': 'https://official.example/immutable',
        'expected_source_rows': 1,
    }
    report = {**cfg, 'document_checked_at': '2026-11-06T10:00:00Z'}
    record = {**{k: cfg[k] for k in (
        'source_key', 'authority_key', 'register_key', 'population_scope',
        'reference_date', 'source_page_url', 'resource_url')},
        'parser_name': 'test_parser', 'parser_version': '1', 'record_locator': 'table:1:row:1'}
    original = {'records': [record], 'meta': {'sources': [report], 'record_count': 1, 'source_count': 1}}
    manifest = tmp_path / 'manifest.json'
    manifest.write_text('{"release_tag":"reviewed-baseline"}')
    verified = []
    monkeypatch.setattr(build, 'validate_registry', lambda registry: verified.append(registry))
    def restored(release, path):
        assert release['release_tag'] == 'reviewed-baseline'
        (path/'registry.json').write_text(json.dumps(original))
    monkeypatch.setattr(build, 'restore', restored)
    monkeypatch.setattr(build, '_build_registry_from_selected_inputs', lambda *a, **kw:
                        (_ for _ in ()).throw(AssertionError('Live acquisition must not run')))
    assert build._build_with_preserved_public_sources(
        {'sources': [cfg]}, tmp_path, ('test-listed',), manifest) == original
    assert verified == [original]

    # The immutable prior derivative cannot be silently used under a changed
    # official date or original hash, even when all source keys were selected.
    for key, changed in [('reference_date', '2026-11-07'), ('sha256', 'b' * 64)]:
        altered = {**cfg, key: changed}
        with pytest.raises(ValueError, match='differs from configured'):
            build._build_with_preserved_public_sources(
                {'sources': [altered]}, tmp_path, ('test-listed',), manifest)


def test_preserved_public_sources_compose_only_with_exact_frozen_new_scope(monkeypatch, tmp_path):
    """Frozen input for one changed scope must never refetch the 140 preserved URLs."""
    import json
    import pytest
    import white_list_archive.publishing.public_national_build as build

    def scope(key, population, digest, date):
        return {
            'source_key': key, 'authority_key': 'sample', 'register_key': 'sample-ordinary',
            'population_scope': population, 'reference_date': date,
            'parser': 'reviewed_parser', 'sha256': digest,
            'source_page_url': 'https://official.example/page',
            'resource_url': 'https://official.example/archive',
            'expected_source_rows': 1,
        }

    prior = scope('sample-listed', 'listed', 'a' * 64, '2026-09-01')
    current = scope('sample-applicants', 'applicant', 'b' * 64, '2026-11-06')

    def record(cfg, status):
        return {
            **{key: cfg[key] for key in (
                'source_key', 'authority_key', 'register_key', 'population_scope',
                'reference_date', 'source_page_url', 'resource_url',
            )},
            'parser_name': cfg['parser'], 'parser_version': '1',
            'record_locator': 'row:1', 'source_status': status,
        }

    approved_report = {**prior, 'document_checked_at': '2026-09-02T10:00:00Z'}
    new_report = {**current, 'document_checked_at': '2026-11-06T10:00:00Z'}
    original = {'records': [record(prior, 'listed')], 'meta': {
        'sources': [approved_report], 'record_count': 1, 'source_count': 1,
    }}
    frozen = {'records': [record(current, 'pending')], 'meta': {
        'sources': [new_report], 'record_count': 1, 'source_count': 1,
    }}
    snapshot = tmp_path / 'selected.json'
    snapshot.write_text(json.dumps({'release_tag': 'approved-baseline'}))
    frozen_manifest = tmp_path / 'frozen.json'
    frozen_manifest.write_text('{"test":"exact archived manifest supplied by protected workflow"}')
    checked = []

    def restore_approved(manifest, destination):
        assert manifest['release_tag'] == 'approved-baseline'
        (destination / 'registry.json').write_text(json.dumps(original))

    def archived_child(config, work_dir, release_manifest_path, *, runtime_code_revision=None, **kwargs):
        assert [s['source_key'] for s in config['sources']] == ['sample-applicants']
        assert release_manifest_path == frozen_manifest
        assert runtime_code_revision == 'frozen-code-sha'
        checked.append('archived-only')
        return frozen

    monkeypatch.setattr(build, 'restore', restore_approved)
    monkeypatch.setattr(build, 'validate_registry', lambda registry: None)
    monkeypatch.setattr(build, '_build_registry_from_selected_inputs', archived_child)
    monkeypatch.setattr(build, '_build_registry_with_network_retries',
                        lambda *args, **kwargs: pytest.fail('No live source fallback permitted'))

    result = build._build_with_preserved_public_sources(
        {'sources': [prior, current]}, tmp_path, ('sample-listed',), snapshot,
        release_manifest_path=frozen_manifest, runtime_code_revision='frozen-code-sha',
    )
    assert checked == ['archived-only']
    assert result['meta']['record_count'] == 2
    assert result['meta']['source_count'] == 2
    assert result['meta']['status_counts'] == {'listed': 1, 'pending': 1}
    assert result['meta']['sources'][1] is approved_report or result['meta']['sources'][1] == approved_report
    assert result['meta']['sources'][1]['document_checked_at'] == '2026-09-02T10:00:00Z'
    assert {r['source_key'] for r in result['records']} == {'sample-listed', 'sample-applicants'}

    def rejected(*args, **kwargs):
        raise ValueError('archived provenance mismatch')

    monkeypatch.setattr(build, '_build_registry_from_selected_inputs', rejected)
    with pytest.raises(ValueError, match='archived provenance mismatch'):
        build._build_with_preserved_public_sources(
            {'sources': [prior, current]}, tmp_path, ('sample-listed',), snapshot,
            release_manifest_path=frozen_manifest, runtime_code_revision='frozen-code-sha',
        )


def test_mixed_frozen_replay_requires_runtime_and_selected_baseline(monkeypatch, tmp_path):
    import pytest
    import white_list_archive.publishing.public_national_build as build

    cfg = {'sources': [{'source_key': 'new-applicant'}]}
    frozen = tmp_path / 'frozen.json'
    frozen.write_text('{}')
    selected = tmp_path / 'selected.json'
    selected.write_text('{}')
    delegated = []

    def delegate(*args, **kwargs):
        delegated.append(kwargs)
        return {'records': []}

    monkeypatch.setattr(build, '_build_with_preserved_public_sources', delegate)
    with pytest.raises(ValueError, match='runtime code revision'):
        build._build_registry_from_selected_inputs(
            cfg, tmp_path, frozen, preserved_source_keys=('old-listed',),
            public_snapshot_manifest=selected,
        )
    with pytest.raises(ValueError, match='both explicit source keys'):
        build._build_registry_from_selected_inputs(
            cfg, tmp_path, frozen, runtime_code_revision='exact-code',
            preserved_source_keys=('old-listed',),
        )
    assert not delegated
    build._build_registry_from_selected_inputs(
        cfg, tmp_path, frozen, runtime_code_revision='exact-code',
        preserved_source_keys=('old-listed',), public_snapshot_manifest=selected,
    )
    assert delegated[0]['release_manifest_path'] == frozen
    assert delegated[0]['runtime_code_revision'] == 'exact-code'
