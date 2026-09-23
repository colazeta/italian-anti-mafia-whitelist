from pathlib import Path

import pytest

from white_list_archive.persistence.source_series_registration import _context_for_source_key


def _write_registries(tmp_path: Path) -> tuple[Path, Path]:
    authorities = tmp_path / "authorities.csv"
    authorities.write_text(
        "authority_key,jurisdiction_name,region,office_type,coverage_status,notes\n"
        "test-authority,Test Province,Test Region,prefettura_utg,territorial_authority_seeded,\n",
        encoding="utf-8",
    )
    series = tmp_path / "series.csv"
    series.write_text(
        "source_series_key,authority_key,regime_code,population_scope,sector_scope,"
        "publication_model,series_url,resource_resolution_status,verified_date,notes\n"
        "test-listed,test-authority,WL-REGIME-L190-2012,listed,all,periodic_attachment,"
        "https://official.example.test/white-list,direct_series_page_resolved,2026-09-23,"
        "Synthetic test metadata only\n",
        encoding="utf-8",
    )
    return authorities, series


def test_registration_context_uses_reviewed_logical_series_not_url_identity(tmp_path: Path):
    authorities, series = _write_registries(tmp_path)
    context = _context_for_source_key(
        "test-listed", authority_csv=authorities, series_csv=series
    )
    assert context.source_series_key == "test-listed"
    assert context.authority_key == "test-authority"
    assert context.regime_code == "WL-REGIME-L190-2012"
    assert context.population_types == ("listed",)
    # RegistryContext intentionally has no locator field: a series URL is discovery
    # metadata, not the identity of an acquired document or administrative edition.
    assert not hasattr(context, "series_url")


def test_unreviewed_source_key_is_rejected(tmp_path: Path):
    authorities, series = _write_registries(tmp_path)
    with pytest.raises(ValueError, match="not present in the reviewed source-series inventory"):
        _context_for_source_key(
            "not-reviewed", authority_csv=authorities, series_csv=series
        )
