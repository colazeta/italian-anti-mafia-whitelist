from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path

import pytest

from white_list_archive.acquisition.anncsu import (
    ANNCSU_REQUIRED_FIELDS,
    build_bulk_url,
    inspect_archive,
    iter_anncsu_rows,
    parse_decimal_coordinate,
)


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ANNCSU_REQUIRED_FIELDS, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


def _row(**overrides: str) -> dict[str, str]:
    row = {field: "" for field in ANNCSU_REQUIRED_FIELDS}
    row.update(
        {
            "CODICE_COMUNE": "D086",
            "CODICE_ISTAT": "078045",
            "PROGRESSIVO_NAZIONALE": "1001377",
            "ODONIMO": "CONTRADA ALBICELLO",
            "PROGRESSIVO_ACCESSO": "34648394",
            "CIVICO": "1",
            "COORD_X_COMUNE": "16,2855499",
            "COORD_Y_COMUNE": "39,2501403",
            "METODO": "3",
        }
    )
    row.update(overrides)
    return row


def test_bulk_url_uses_anncsu_bare_query_key():
    url = build_bulk_url("INDIR_CALA")
    assert url.endswith("getds.php?INDIR_CALA")
    assert not url.endswith("=")
    with pytest.raises(ValueError):
        build_bulk_url("INDIR_CALA=")


def test_archive_identity_and_schema_are_validated(tmp_path: Path):
    csv_text = io.StringIO()
    writer = csv.DictWriter(csv_text, fieldnames=ANNCSU_REQUIRED_FIELDS, delimiter=";")
    writer.writeheader()
    writer.writerow(_row())
    zip_path = tmp_path / "calabria.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "INDIR_CALA_20260803.csv",
            "\ufeff" + csv_text.getvalue(),
        )

    metadata = inspect_archive(zip_path)
    assert metadata["provider_version"] == "2026-08-03"
    assert metadata["csv_member"] == "INDIR_CALA_20260803.csv"
    assert metadata["encoding"] == "utf-8-sig"
    assert metadata["delimiter"] == ";"
    assert metadata["fieldnames"] == list(ANNCSU_REQUIRED_FIELDS)
    assert len(str(metadata["zip_sha256"])) == 64


def test_archive_rejects_missing_required_fields(tmp_path: Path):
    zip_path = tmp_path / "bad.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("INDIR_CALA_20260803.csv", "CODICE_COMUNE;CODICE_ISTAT\nD086;078045\n")
    with pytest.raises(ValueError, match="missing required fields"):
        inspect_archive(zip_path)


def test_rows_stream_and_filter_by_belfiore_code(tmp_path: Path):
    csv_path = tmp_path / "INDIR_CALA_20260803.csv"
    _write_csv(
        csv_path,
        [
            _row(),
            _row(CODICE_COMUNE="F888", CODICE_ISTAT="079160", CIVICO="2"),
        ],
    )
    all_rows = list(iter_anncsu_rows(csv_path))
    cosenza = list(iter_anncsu_rows(csv_path, municipality_belfiore="d086"))
    assert len(all_rows) == 2
    assert len(cosenza) == 1
    assert cosenza[0]["CODICE_ISTAT"] == "078045"
    assert cosenza[0]["PROGRESSIVO_ACCESSO"] == "34648394"


def test_decimal_coordinates_follow_anncsu_comma_decimal_format():
    assert parse_decimal_coordinate("16,2855499") == pytest.approx(16.2855499)
    assert parse_decimal_coordinate("39,2501403") == pytest.approx(39.2501403)
    assert parse_decimal_coordinate("") is None
