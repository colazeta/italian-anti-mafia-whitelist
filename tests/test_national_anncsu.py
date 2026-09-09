import hashlib
import json
from pathlib import Path

import pytest

from white_list_archive.geocoding.national_anncsu import (
    ANNCSU_REGION_DATASETS,
    MAP_VERSION,
    _latest_cached_dataset,
    dataset_code_for,
)


def test_all_dataset_codes_are_unique_and_well_formed():
    codes = [str(item["dataset"]) for item in ANNCSU_REGION_DATASETS]
    assert len(codes) == 20
    assert len(codes) == len(set(codes))
    assert all(code.startswith("INDIR_") for code in codes)
    assert dataset_code_for("Calabria") == "INDIR_CALA"
    assert dataset_code_for("Toscana") == "INDIR_TOSC"
    assert dataset_code_for("Emilia-Romagna") == "INDIR_EMIL"


def test_trentino_is_one_official_regional_dataset():
    assert dataset_code_for("Trentino-Alto Adige/Südtirol", "BZ") == "INDIR_TREN"
    assert dataset_code_for("Trentino Alto Adige", "TN") == "INDIR_TREN"
    assert dataset_code_for("Trentino-Alto Adige/Südtirol") == "INDIR_TREN"


def test_unknown_region_fails_closed():
    with pytest.raises(LookupError):
        dataset_code_for("Atlantide")


def _write_cached_dataset(root: Path, code: str, version: str, suffix: str):
    directory = root / code
    directory.mkdir(parents=True, exist_ok=True)
    zip_bytes = ("zip-" + suffix).encode()
    csv_bytes = ("csv-" + suffix).encode()
    zip_path = directory / f"anncsu-{code.lower()}-{version}.zip"
    csv_path = directory / f"{code}_{version.replace('-', '')}.csv"
    zip_path.write_bytes(zip_bytes)
    csv_path.write_bytes(csv_bytes)
    zip_sha = hashlib.sha256(zip_bytes).hexdigest()
    csv_sha = hashlib.sha256(csv_bytes).hexdigest()
    manifest = {
        "provider": "ANNCSU",
        "dataset_code": code,
        "provider_version": version,
        "source_url": f"https://example.test/getds.php?{code}",
        "zip": {"path": zip_path.name, "sha256": zip_sha},
        "csv": {"path": csv_path.name, "sha256": csv_sha},
    }
    manifest_path = directory / f"anncsu-{code.lower()}-{version}.manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path


def test_cache_reuses_latest_verified_provider_version(tmp_path):
    _write_cached_dataset(tmp_path, "INDIR_CALA", "2026-07-01", "old")
    latest = _write_cached_dataset(tmp_path, "INDIR_CALA", "2026-08-03", "new")
    cached = _latest_cached_dataset(tmp_path, "INDIR_CALA")
    assert cached is not None
    assert cached.provider_version == "2026-08-03"
    assert cached.manifest_path == latest
    assert cached.cache_status == "reused"


def test_cache_refuses_manifest_whose_physical_bytes_changed(tmp_path):
    manifest = _write_cached_dataset(tmp_path, "INDIR_TOSC", "2026-08-03", "stable")
    data = json.loads(manifest.read_text())
    (manifest.parent / data["csv"]["path"]).write_text("mutated", encoding="utf-8")
    with pytest.raises(ValueError, match="CSV identity mismatch"):
        _latest_cached_dataset(tmp_path, "INDIR_TOSC")


def test_map_version_is_explicitly_versioned():
    assert MAP_VERSION == "anncsu-regional-datasets-2026-09"
