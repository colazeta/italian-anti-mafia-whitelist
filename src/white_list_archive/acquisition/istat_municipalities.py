from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import tempfile
import unicodedata
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

ISTAT_MUNICIPALITY_URL = (
    "https://www.istat.it/storage/codici-unita-amministrative/Elenco-comuni-italiani.xlsx"
)
USER_AGENT = (
    "italian-anti-mafia-whitelist/istat-municipalities "
    "(+https://github.com/colazeta/italian-anti-mafia-whitelist)"
)
DATA_SHEET_RE = re.compile(r"^CODICI\s+al\s+(?P<date>\d{2}_\d{2}_\d{4})$", re.IGNORECASE)
MUNICIPALITY_CODE_RE = re.compile(r"^\d{6}$")
CADASTRAL_CODE_RE = re.compile(r"^[A-Z][0-9A-Z]{3}$")

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
OFFICE_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"m": MAIN_NS}
REL_NS = {"r": PACKAGE_REL_NS}


def _header(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "")
    return " ".join(value.replace("\n", " ").split()).strip()


HEADER_TO_FIELD = {
    _header("Codice Regione"): "region_code",
    _header("Codice dell'Unità territoriale sovracomunale (valida a fini statistici)"): "supra_unit_code",
    _header("Codice Provincia (Storico)(1)"): "historical_province_code",
    _header("Progressivo del Comune (2)"): "municipality_progressive",
    _header("Codice Comune formato alfanumerico"): "municipality_code",
    _header("Denominazione (Italiana e straniera)"): "municipality_name",
    _header("Denominazione in italiano"): "municipality_name_it",
    _header("Denominazione altra lingua"): "municipality_name_other",
    _header("Codice Ripartizione Geografica"): "geographic_division_code",
    _header("Ripartizione geografica"): "geographic_division_name",
    _header("Denominazione Regione"): "region_name",
    _header("Denominazione dell'Unità territoriale sovracomunale (valida a fini statistici)"): "supra_unit_name",
    _header("Tipologia di Unità territoriale sovracomunale"): "supra_unit_type_code",
    _header("Flag Comune capoluogo di Provincia/Città metropolitana/libero consorzio"): "capital_flag",
    _header("Sigla automobilistica"): "province_plate",
    _header("Codice Comune formato numerico"): "municipality_code_numeric",
    _header("Codice Comune numerico con 107 Province (dal 2017 al 2025)"): "municipality_code_numeric_2017_2025",
    _header("Codice Comune numerico con 110 Province (dal 2010 al 2016)"): "municipality_code_numeric_2010_2016",
    _header("Codice Comune numerico con 107 Province (dal 2006 al 2009)"): "municipality_code_numeric_2006_2009",
    _header("Codice Comune numerico con 103 Province (dal 1995 al 2005)"): "municipality_code_numeric_1995_2005",
    _header("Codice Catastale del Comune"): "cadastral_code",
    _header("Codice NUTS1 2021"): "nuts1_2021",
    _header("Codice NUTS2 2021 (3)"): "nuts2_2021",
    _header("Codice NUTS3 2021"): "nuts3_2021",
    _header("Codice NUTS1 2024"): "nuts1_2024",
    _header("Codice NUTS2 2024 (3)"): "nuts2_2024",
    _header("Codice NUTS3 2024"): "nuts3_2024",
}
OUTPUT_FIELDS = tuple(HEADER_TO_FIELD.values())


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _column_index(reference: str) -> int:
    match = re.match(r"([A-Z]+)", reference)
    if not match:
        raise ValueError(f"Invalid XLSX cell reference: {reference!r}")
    result = 0
    for char in match.group(1):
        result = result * 26 + ord(char) - 64
    return result - 1


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    return [
        "".join(text.text or "" for text in item.iterfind(".//m:t", NS))
        for item in root.findall("m:si", NS)
    ]


def _sheet_targets(archive: zipfile.ZipFile) -> list[tuple[str, str]]:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    relationship_map = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in relationships.findall("r:Relationship", REL_NS)
    }
    sheets = workbook.find("m:sheets", NS)
    if sheets is None:
        raise ValueError("Istat workbook has no sheets")
    result: list[tuple[str, str]] = []
    for sheet in sheets:
        name = sheet.attrib["name"]
        relationship_id = sheet.attrib[f"{{{OFFICE_REL_NS}}}id"]
        target = relationship_map[relationship_id].replace("\\", "/")
        if target.startswith("/"):
            path = target.lstrip("/")
        elif target.startswith("xl/"):
            path = target
        else:
            path = "xl/" + target
        while "/../" in path:
            left, right = path.split("/../", 1)
            path = left.rsplit("/", 1)[0] + "/" + right
        result.append((name, path))
    return result


def _cell_text(cell: ET.Element, shared: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        inline = cell.find("m:is", NS)
        if inline is None:
            return ""
        return "".join(text.text or "" for text in inline.iterfind(".//m:t", NS))
    value = cell.find("m:v", NS)
    if value is None or value.text is None:
        return ""
    raw = value.text
    if cell_type == "s":
        try:
            return shared[int(raw)]
        except (ValueError, IndexError) as exc:
            raise ValueError(f"Invalid XLSX shared-string reference: {raw!r}") from exc
    return raw


def _worksheet_rows(
    archive: zipfile.ZipFile, sheet_path: str, shared: list[str]
) -> list[list[str]]:
    root = ET.fromstring(archive.read(sheet_path))
    rows: list[list[str]] = []
    for row in root.findall(".//m:sheetData/m:row", NS):
        values: dict[int, str] = {}
        for cell in row.findall("m:c", NS):
            reference = cell.attrib.get("r")
            if not reference:
                continue
            values[_column_index(reference)] = _cell_text(cell, shared)
        if not values:
            continue
        rows.append([values.get(index, "") for index in range(max(values) + 1)])
    return rows


def _data_sheet(archive: zipfile.ZipFile) -> tuple[str, str, str]:
    matches: list[tuple[str, str, str]] = []
    for name, path in _sheet_targets(archive):
        match = DATA_SHEET_RE.fullmatch(name.strip())
        if match:
            version = datetime.strptime(match.group("date"), "%d_%m_%Y").date().isoformat()
            matches.append((name, path, version))
    if len(matches) != 1:
        raise ValueError(
            "Expected exactly one Istat data sheet named 'CODICI al DD_MM_YYYY'; "
            f"found {[item[0] for item in matches]}"
        )
    return matches[0]


def parse_workbook(path: Path) -> dict[str, object]:
    """Parse and validate the current Istat municipality crosswalk."""
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open("rb") as handle:
        if handle.read(2) != b"PK":
            raise ValueError("Istat municipality response is not an XLSX archive")

    with zipfile.ZipFile(path) as archive:
        bad_member = archive.testzip()
        if bad_member is not None:
            raise ValueError(f"Corrupt Istat XLSX member: {bad_member}")
        sheet_name, sheet_path, provider_version = _data_sheet(archive)
        rows = _worksheet_rows(archive, sheet_path, _shared_strings(archive))

    if not rows:
        raise ValueError("Istat municipality data sheet is empty")
    source_headers = [_header(value) for value in rows[0]]
    index_by_field: dict[str, int] = {}
    for index, source_header in enumerate(source_headers):
        field = HEADER_TO_FIELD.get(source_header)
        if field:
            index_by_field[field] = index
    missing = [field for field in OUTPUT_FIELDS if field not in index_by_field]
    if missing:
        raise ValueError(f"Istat municipality workbook missing required fields: {missing}")

    records: list[dict[str, str]] = []
    seen_municipality_codes: set[str] = set()
    seen_cadastral_codes: set[str] = set()
    for source_row in rows[1:]:
        record = {
            field: (
                source_row[index_by_field[field]].strip()
                if index_by_field[field] < len(source_row)
                else ""
            )
            for field in OUTPUT_FIELDS
        }
        if not any(record.values()):
            continue
        municipality_code = record["municipality_code"]
        cadastral_code = record["cadastral_code"].upper()
        record["cadastral_code"] = cadastral_code
        if not MUNICIPALITY_CODE_RE.fullmatch(municipality_code):
            raise ValueError(f"Invalid Istat municipality code: {municipality_code!r}")
        if not CADASTRAL_CODE_RE.fullmatch(cadastral_code):
            raise ValueError(f"Invalid Istat cadastral/Belfiore code: {cadastral_code!r}")
        if municipality_code in seen_municipality_codes:
            raise ValueError(f"Duplicate Istat municipality code: {municipality_code}")
        if cadastral_code in seen_cadastral_codes:
            raise ValueError(f"Duplicate Istat cadastral/Belfiore code: {cadastral_code}")
        seen_municipality_codes.add(municipality_code)
        seen_cadastral_codes.add(cadastral_code)
        records.append(record)

    if not records:
        raise ValueError("Istat municipality workbook yielded no municipality records")
    return {
        "provider_version": provider_version,
        "source_sheet": sheet_name,
        "source_headers": source_headers,
        "records": records,
    }


def write_crosswalk_csv(records: list[dict[str, str]], destination: Path) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="",
        dir=destination.parent,
        prefix=destination.name + ".",
        suffix=".part",
        delete=False,
    ) as temp:
        temp_path = Path(temp.name)
        writer = csv.DictWriter(temp, fieldnames=OUTPUT_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)
    try:
        observed = sha256_file(temp_path)
        if destination.exists():
            if sha256_file(destination) != observed:
                raise FileExistsError(
                    f"Refusing to replace different Istat crosswalk at {destination}"
                )
            temp_path.unlink()
        else:
            os.replace(temp_path, destination)
        return observed
    finally:
        temp_path.unlink(missing_ok=True)


def iter_municipalities(path: Path):
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != OUTPUT_FIELDS:
            raise ValueError("Istat municipality crosswalk CSV schema does not match OUTPUT_FIELDS")
        for row in reader:
            yield {key: value or "" for key, value in row.items() if key is not None}


def acquire_crosswalk(
    output_dir: Path,
    *,
    expected_xlsx_sha256: str | None = None,
    source_url: str = ISTAT_MUNICIPALITY_URL,
) -> dict[str, object]:
    """Download, hash, validate and normalise the official Istat municipality workbook."""
    output_dir.mkdir(parents=True, exist_ok=True)
    captured_at = utc_now()
    request = urllib.request.Request(
        source_url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*",
        },
        method="GET",
    )
    with tempfile.NamedTemporaryFile(
        mode="wb", dir=output_dir, prefix="istat-municipalities.", suffix=".xlsx.part", delete=False
    ) as temp:
        temp_path = Path(temp.name)
        with urllib.request.urlopen(request, timeout=180) as response:
            http = {
                "http_status": response.status,
                "content_type": response.headers.get("Content-Type"),
                "content_length": response.headers.get("Content-Length"),
                "last_modified": response.headers.get("Last-Modified"),
                "etag": response.headers.get("ETag"),
            }
            shutil.copyfileobj(response, temp, length=1024 * 1024)

    try:
        observed_xlsx_sha256 = sha256_file(temp_path)
        if expected_xlsx_sha256 and observed_xlsx_sha256.lower() != expected_xlsx_sha256.lower():
            raise ValueError(
                "Istat municipality XLSX SHA-256 mismatch: "
                f"expected {expected_xlsx_sha256}, observed {observed_xlsx_sha256}"
            )
        parsed = parse_workbook(temp_path)
        provider_version = str(parsed["provider_version"])
        xlsx_path = output_dir / f"istat-municipalities-{provider_version}.xlsx"
        if xlsx_path.exists():
            if sha256_file(xlsx_path) != observed_xlsx_sha256:
                raise FileExistsError(
                    f"Refusing to replace different Istat workbook at {xlsx_path}"
                )
            temp_path.unlink()
        else:
            os.replace(temp_path, xlsx_path)
    finally:
        temp_path.unlink(missing_ok=True)

    records = list(parsed["records"])
    csv_path = output_dir / f"istat-municipalities-{provider_version}.csv"
    csv_sha256 = write_crosswalk_csv(records, csv_path)
    manifest = {
        "provider": "ISTAT",
        "dataset": "Elenco comuni italiani",
        "provider_version": provider_version,
        "source_url": source_url,
        "captured_at": captured_at.isoformat(),
        "source_sheet": parsed["source_sheet"],
        "municipality_count": len(records),
        "xlsx": {
            "path": xlsx_path.name,
            "bytes": xlsx_path.stat().st_size,
            "sha256": observed_xlsx_sha256,
            "source_headers": parsed["source_headers"],
        },
        "crosswalk_csv": {
            "path": csv_path.name,
            "bytes": csv_path.stat().st_size,
            "sha256": csv_sha256,
            "fields": list(OUTPUT_FIELDS),
        },
        "http": http,
    }
    manifest_path = output_dir / f"istat-municipalities-{provider_version}.manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    manifest["manifest_path"] = manifest_path.name
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Acquire and normalise Istat's official current municipality crosswalk."
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-sha256")
    args = parser.parse_args()
    manifest = acquire_crosswalk(
        args.output_dir,
        expected_xlsx_sha256=args.expected_sha256,
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
