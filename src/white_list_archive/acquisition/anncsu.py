from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import tempfile
import urllib.request
import zipfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, TextIO

ANNCSU_BASE_URL = (
    "https://anncsu.open.agenziaentrate.gov.it/age-inspire/opendata/anncsu"
)
USER_AGENT = (
    "italian-anti-mafia-whitelist/anncsu-acquisition "
    "(+https://github.com/colazeta/italian-anti-mafia-whitelist)"
)
DATASET_CODE_RE = re.compile(r"^[A-Z0-9_]+$")
VERSION_RE = re.compile(r"_(?P<date>\d{8})\.csv$", re.IGNORECASE)

ANNCSU_REQUIRED_FIELDS = (
    "CODICE_COMUNE",
    "CODICE_ISTAT",
    "PROGRESSIVO_NAZIONALE",
    "CODICE_COMUNALE",
    "ODONIMO",
    "LOCALITA'",
    "DIZIONE_LINGUA1",
    "DIZIONE_LINGUA2",
    "PROGRESSIVO_ACCESSO",
    "CODICE_COMUNALE_ACCESSO",
    "CIVICO",
    "ESPONENTE",
    "SPECIFICITA",
    "METRICO",
    "PROGRESSIVO_SNC",
    "COORD_X_COMUNE",
    "COORD_Y_COMUNE",
    "QUOTA",
    "METODO",
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def build_bulk_url(dataset_code: str, *, base_url: str = ANNCSU_BASE_URL) -> str:
    """Build the ANNCSU bulk-download URL.

    ANNCSU expects the dataset identifier as a *bare query key* (for example
    ``?INDIR_CALA``). Adding an equals sign changes the request value and the
    official endpoint rejects it with HTTP 406.
    """
    dataset_code = dataset_code.strip().upper()
    if not DATASET_CODE_RE.fullmatch(dataset_code):
        raise ValueError(f"Invalid ANNCSU dataset code: {dataset_code!r}")
    return f"{base_url.rstrip('/')}/getds.php?{dataset_code}"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _provider_version(member_name: str) -> str:
    match = VERSION_RE.search(member_name)
    if not match:
        raise ValueError(
            f"ANNCSU CSV member does not expose YYYYMMDD version: {member_name!r}"
        )
    value = datetime.strptime(match.group("date"), "%Y%m%d").date()
    return value.isoformat()


def _validate_header(fieldnames: list[str] | None) -> list[str]:
    if not fieldnames:
        raise ValueError("ANNCSU CSV has no header")
    missing = [field for field in ANNCSU_REQUIRED_FIELDS if field not in fieldnames]
    if missing:
        raise ValueError(f"ANNCSU CSV missing required fields: {missing}")
    return fieldnames


@contextmanager
def open_anncsu_csv(csv_path: Path) -> Iterator[TextIO]:
    """Open an extracted ANNCSU CSV using the observed official encoding."""
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        yield handle


def iter_anncsu_rows(
    csv_path: Path, *, municipality_belfiore: str | None = None
) -> Iterator[dict[str, str]]:
    """Stream ANNCSU rows without loading the national/regional file in memory."""
    municipality = municipality_belfiore.strip().upper() if municipality_belfiore else None
    with open_anncsu_csv(csv_path) as handle:
        reader = csv.DictReader(handle, delimiter=";")
        _validate_header(reader.fieldnames)
        for row in reader:
            if municipality and (row.get("CODICE_COMUNE") or "").strip().upper() != municipality:
                continue
            yield {key: value or "" for key, value in row.items() if key is not None}


def parse_decimal_coordinate(value: str) -> float | None:
    value = value.strip()
    if not value:
        return None
    return float(value.replace(",", "."))


def inspect_archive(zip_path: Path) -> dict[str, object]:
    """Validate an ANNCSU ZIP and return deterministic physical metadata."""
    if not zip_path.is_file():
        raise FileNotFoundError(zip_path)
    with zip_path.open("rb") as handle:
        if handle.read(2) != b"PK":
            raise ValueError("ANNCSU response is not a ZIP archive")

    with zipfile.ZipFile(zip_path) as archive:
        bad_member = archive.testzip()
        if bad_member is not None:
            raise ValueError(f"Corrupt ANNCSU ZIP member: {bad_member}")
        members = [item for item in archive.infolist() if not item.is_dir()]
        csv_members = [item for item in members if item.filename.lower().endswith(".csv")]
        if len(csv_members) != 1:
            raise ValueError(
                "Expected exactly one ANNCSU CSV member; found "
                + repr([item.filename for item in csv_members])
            )
        csv_info = csv_members[0]
        provider_version = _provider_version(csv_info.filename)
        with archive.open(csv_info) as raw:
            import io

            text = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
            reader = csv.reader(text, delimiter=";")
            header = next(reader, None)
            _validate_header(header)

    return {
        "zip_sha256": sha256_file(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "csv_member": csv_info.filename,
        "csv_uncompressed_bytes": csv_info.file_size,
        "csv_compressed_bytes": csv_info.compress_size,
        "provider_version": provider_version,
        "encoding": "utf-8-sig",
        "delimiter": ";",
        "fieldnames": header,
    }


def extract_csv(zip_path: Path, output_dir: Path, archive_metadata: dict[str, object]) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    member = str(archive_metadata["csv_member"])
    destination = output_dir / Path(member).name
    with zipfile.ZipFile(zip_path) as archive, archive.open(member) as source:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=output_dir, prefix=destination.name + ".", suffix=".part", delete=False
        ) as temp:
            temp_path = Path(temp.name)
            shutil.copyfileobj(source, temp, length=1024 * 1024)
    try:
        csv_sha256 = sha256_file(temp_path)
        if destination.exists():
            if sha256_file(destination) != csv_sha256:
                raise FileExistsError(
                    f"Refusing to replace different ANNCSU CSV at {destination}"
                )
            temp_path.unlink()
        else:
            os.replace(temp_path, destination)
    finally:
        temp_path.unlink(missing_ok=True)
    return destination


def acquire_dataset(
    dataset_code: str,
    output_dir: Path,
    *,
    expected_zip_sha256: str | None = None,
    base_url: str = ANNCSU_BASE_URL,
) -> dict[str, object]:
    """Acquire, hash, validate and extract an official ANNCSU bulk dataset."""
    dataset_code = dataset_code.strip().upper()
    url = build_bulk_url(dataset_code, base_url=base_url)
    output_dir.mkdir(parents=True, exist_ok=True)
    captured_at = utc_now()

    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/octet-stream,*/*"},
        method="GET",
    )
    with tempfile.NamedTemporaryFile(
        mode="wb", dir=output_dir, prefix=f"{dataset_code.lower()}.", suffix=".zip.part", delete=False
    ) as temp:
        temp_path = Path(temp.name)
        with urllib.request.urlopen(request, timeout=180) as response:
            response_metadata = {
                "http_status": response.status,
                "content_type": response.headers.get("Content-Type"),
                "content_disposition": response.headers.get("Content-Disposition"),
                "last_modified": response.headers.get("Last-Modified"),
                "etag": response.headers.get("ETag"),
            }
            shutil.copyfileobj(response, temp, length=1024 * 1024)

    try:
        archive_metadata = inspect_archive(temp_path)
        observed_sha256 = str(archive_metadata["zip_sha256"])
        if expected_zip_sha256 and observed_sha256.lower() != expected_zip_sha256.lower():
            raise ValueError(
                "ANNCSU ZIP SHA-256 mismatch: "
                f"expected {expected_zip_sha256}, observed {observed_sha256}"
            )
        version = str(archive_metadata["provider_version"])
        zip_path = output_dir / f"anncsu-{dataset_code.lower()}-{version}.zip"
        if zip_path.exists():
            if sha256_file(zip_path) != observed_sha256:
                raise FileExistsError(
                    f"Refusing to replace different ANNCSU ZIP at {zip_path}"
                )
            temp_path.unlink()
        else:
            os.replace(temp_path, zip_path)
    finally:
        temp_path.unlink(missing_ok=True)

    csv_path = extract_csv(zip_path, output_dir, archive_metadata)
    csv_sha256 = sha256_file(csv_path)
    manifest = {
        "provider": "ANNCSU",
        "dataset_code": dataset_code,
        "provider_version": archive_metadata["provider_version"],
        "source_url": url,
        "captured_at": captured_at.isoformat(),
        "zip": {
            "path": zip_path.name,
            "bytes": archive_metadata["zip_bytes"],
            "sha256": archive_metadata["zip_sha256"],
        },
        "csv": {
            "path": csv_path.name,
            "member": archive_metadata["csv_member"],
            "bytes": archive_metadata["csv_uncompressed_bytes"],
            "sha256": csv_sha256,
            "encoding": archive_metadata["encoding"],
            "delimiter": archive_metadata["delimiter"],
            "fieldnames": archive_metadata["fieldnames"],
        },
        "http": response_metadata,
    }
    manifest_path = output_dir / f"anncsu-{dataset_code.lower()}-{version}.manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    manifest["manifest_path"] = manifest_path.name
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Acquire an official ANNCSU monthly bulk address dataset."
    )
    parser.add_argument("--dataset", required=True, help="ANNCSU dataset code, e.g. INDIR_CALA")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-sha256")
    args = parser.parse_args()
    manifest = acquire_dataset(
        args.dataset,
        args.output_dir,
        expected_zip_sha256=args.expected_sha256,
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
