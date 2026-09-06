from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CATALOG = DATA / "catalog.csv"

REQUIRED_DOCS = [
    ROOT / "README.md",
    ROOT / "CONTRIBUTING.md",
    ROOT / "docs/README.md",
    ROOT / "docs/project-rules.md",
    ROOT / "docs/data-access.md",
    DATA / "README.md",
    DATA / "releases/README.md",
]

REQUIRED_CATALOG_COLUMNS = {
    "dataset_id",
    "layer",
    "path",
    "format",
    "scope",
    "status",
    "unit",
    "record_count",
    "contains_row_level_entities",
    "release_class",
    "description",
}


def _catalog_rows() -> list[dict[str, str]]:
    with CATALOG.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames is not None
        assert set(reader.fieldnames) == REQUIRED_CATALOG_COLUMNS
        return list(reader)


def test_required_project_entrypoint_documentation_exists():
    missing = [str(path.relative_to(ROOT)) for path in REQUIRED_DOCS if not path.exists()]
    assert not missing, f"Missing required project documentation: {missing}"


def test_data_catalog_has_unique_ids_and_paths_that_exist():
    rows = _catalog_rows()
    ids = [row["dataset_id"] for row in rows]
    paths = [row["path"] for row in rows]
    assert len(ids) == len(set(ids)), "data/catalog.csv contains duplicate dataset_id values"
    assert len(paths) == len(set(paths)), "data/catalog.csv contains duplicate paths"
    missing = [path for path in paths if not (ROOT / path).is_file()]
    assert not missing, f"Catalogued data paths do not exist: {missing}"


def test_every_persistent_csv_or_json_under_data_is_catalogued():
    catalogued = {row["path"] for row in _catalog_rows()}
    candidates = {
        str(path.relative_to(ROOT))
        for path in DATA.rglob("*")
        if path.is_file()
        and path.suffix.lower() in {".csv", ".json"}
        and path != CATALOG
    }
    missing = sorted(candidates - catalogued)
    stale = sorted(catalogued - candidates)
    assert not missing, f"Persistent data files missing from data/catalog.csv: {missing}"
    assert not stale, f"Catalog entries no longer point to persistent CSV/JSON files: {stale}"


def test_declared_csv_record_counts_are_current():
    for row in _catalog_rows():
        declared = row["record_count"].strip()
        if row["format"] != "csv" or not declared:
            continue
        path = ROOT / row["path"]
        with path.open(encoding="utf-8", newline="") as handle:
            actual = sum(1 for _ in csv.DictReader(handle))
        assert actual == int(declared), (
            f"Catalog count for {row['dataset_id']} is {declared}, actual CSV rows are {actual}. "
            "Update the data and catalog together."
        )


def test_release_directory_does_not_bypass_catalog():
    release_files = [
        path
        for path in (DATA / "releases").rglob("*")
        if path.is_file() and path.suffix.lower() in {".csv", ".json", ".parquet"}
    ]
    catalogued = {row["path"] for row in _catalog_rows()}
    missing = [str(path.relative_to(ROOT)) for path in release_files if str(path.relative_to(ROOT)) not in catalogued]
    assert not missing, f"Release artifacts must be catalogued before publication: {missing}"
