import csv
from pathlib import Path

from white_list_archive.publishing.public_national_build import _alias_inputs


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
