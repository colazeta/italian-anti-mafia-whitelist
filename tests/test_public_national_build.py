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
