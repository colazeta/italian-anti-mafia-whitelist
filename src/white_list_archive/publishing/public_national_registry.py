from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from white_list_archive.acquisition.national_index import discover_national_index
from white_list_archive.parsers.cosenza_combined_v2 import PARSER_NAME as COSENZA_PARSER_NAME
from white_list_archive.parsers.cosenza_combined_v2 import PARSER_VERSION as COSENZA_PARSER_VERSION
from white_list_archive.parsers.cosenza_combined_v2 import parse_pdf as parse_cosenza
from white_list_archive.parsers.multi_prefecture_tables import PARSERS, ParsedBatch

USER_AGENT = "italian-anti-mafia-whitelist/0.1 (+public national archive)"


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def _json_value(value: Any, fallback: Any) -> Any:
    if value in (None, ""):
        return fallback
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except json.JSONDecodeError:
        return fallback


def _download(url: str, path: Path) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    with urlopen(request, timeout=90) as response:  # noqa: S310 - URLs are versioned official-source config
        body = response.read()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return hashlib.sha256(body).hexdigest()


def _adapt_cosenza(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    source_records = parse_cosenza(path)
    records: list[dict[str, Any]] = []
    for source in source_records:
        identifiers = _json_value(source.get("identifiers_json"), [])
        activities = _json_value(source.get("requested_activities_json"), [])
        application_dates = _json_value(source.get("application_dates_json"), [])
        outcome = _json_value(source.get("outcome_json"), {})
        row_ordinal = int(source["row_ordinal"])
        app_dates: list[str] = []
        for value in application_dates if isinstance(application_dates, list) else []:
            if isinstance(value, str):
                date_value = value
            elif isinstance(value, dict):
                date_value = str(value.get("date") or value.get("raw_value") or "")
            else:
                date_value = ""
            if date_value:
                app_dates.append(date_value)
        primary_date = str(source.get("observed_listing_date") or "") or (app_dates[0] if app_dates else "")
        primary_label = "Data inserimento osservata" if source.get("observed_listing_date") else "Data presentazione istanza"
        records.append(
            {
                "record_locator": f"{cfg['source_key']}:{cfg['reference_date']}:{row_ordinal}",
                "source_key": cfg["source_key"],
                "authority_key": cfg["authority_key"],
                "authority_name": cfg["authority_name"],
                "register_key": cfg["register_key"],
                "register_name": cfg["register_name"],
                "population_scope": cfg["population_scope"],
                "reference_date": cfg["reference_date"],
                "source_row_ordinal": row_ordinal,
                "name": str(source.get("operator_name_raw") or ""),
                "registered_office": str(source.get("registered_office_raw") or ""),
                "secondary_office": str(source.get("secondary_office_raw") or ""),
                "identifier_field_raw": str(source.get("identifier_field_raw") or ""),
                "identifiers": identifiers if isinstance(identifiers, list) else [],
                "requested_activities": activities if isinstance(activities, list) else [],
                "requested_activities_raw": str(source.get("requested_activities_raw") or ""),
                "source_status": str(source.get("source_status") or "other_or_unknown"),
                "outcome_raw": str(source.get("outcome_raw") or ""),
                "application_date": app_dates[0] if app_dates else "",
                "application_dates": app_dates,
                "observed_listing_date": str(source.get("observed_listing_date") or ""),
                "decision_date": "",
                "registration_date": "",
                "observed_expiry_date": str(source.get("observed_expiry_date") or ""),
                "primary_date": primary_date,
                "primary_date_label": primary_label,
                "source_page_url": cfg["source_page_url"],
                "resource_url": cfg["resource_url"],
                "capture_sha256": cfg["sha256"],
                "parser_name": COSENZA_PARSER_NAME,
                "parser_version": COSENZA_PARSER_VERSION,
                "source_fields": {"outcome": outcome},
            }
        )
    diagnostics = {
        "parser": "cosenza_combined_v2",
        "public_records": len(records),
        "status_counts": dict(Counter(record["source_status"] for record in records)),
        "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
    }
    return ParsedBatch(records, diagnostics)


def _parse_source(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    if cfg["parser"] == "cosenza_combined_v2":
        return _adapt_cosenza(path, cfg)
    batch = PARSERS[cfg["parser"]](path, cfg)
    for record in batch.records:
        record["parser_name"] = cfg["parser"]
        record["parser_version"] = "1"
    return batch


def _validate_batch(cfg: dict[str, Any], batch: ParsedBatch) -> None:
    diagnostics = batch.diagnostics
    if cfg.get("expected_source_rows") is not None and diagnostics["public_records"] != int(cfg["expected_source_rows"]):
        raise RuntimeError(
            f"{cfg['source_key']}: expected {cfg['expected_source_rows']} source rows, got {diagnostics['public_records']}"
        )
    if cfg.get("expected_sector_rows") is not None and diagnostics.get("sector_rows") != int(cfg["expected_sector_rows"]):
        raise RuntimeError(
            f"{cfg['source_key']}: expected {cfg['expected_sector_rows']} sector rows, got {diagnostics.get('sector_rows')}"
        )
    if diagnostics.get("dropped_date_rows", 0):
        raise RuntimeError(
            f"{cfg['source_key']}: parser dropped {diagnostics['dropped_date_rows']} rows containing a source date"
        )
    if not batch.records:
        raise RuntimeError(f"{cfg['source_key']}: no public records parsed")


def build_registry(config: dict[str, Any], work_dir: Path) -> dict[str, Any]:
    all_records: list[dict[str, Any]] = []
    source_reports: list[dict[str, Any]] = []
    for cfg in config["sources"]:
        suffix = Path(urlparse(cfg["resource_url"]).path).suffix or ".pdf"
        local_path = work_dir / f"{cfg['source_key']}{suffix}"
        actual_sha = _download(cfg["resource_url"], local_path)
        if actual_sha != cfg["sha256"]:
            raise RuntimeError(
                f"{cfg['source_key']}: approved source SHA mismatch; expected {cfg['sha256']}, got {actual_sha}"
            )
        batch = _parse_source(local_path, cfg)
        _validate_batch(cfg, batch)
        all_records.extend(batch.records)
        source_reports.append(
            {
                "source_key": cfg["source_key"],
                "authority_key": cfg["authority_key"],
                "register_key": cfg["register_key"],
                "population_scope": cfg["population_scope"],
                "reference_date": cfg["reference_date"],
                "sha256": actual_sha,
                "parser": cfg["parser"],
                "diagnostics": batch.diagnostics,
            }
        )

    authority_counts = Counter(record["authority_key"] for record in all_records)
    register_counts = Counter(record["register_key"] for record in all_records)
    status_counts = Counter(record["source_status"] for record in all_records)
    return {
        "meta": {
            "contract_version": 3,
            "unit": "source-backed public observation grouped only where the source repeats one entity across sectors",
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "record_count": len(all_records),
            "authority_count": len(authority_counts),
            "register_count": len(register_counts),
            "source_count": len(source_reports),
            "authority_counts": dict(authority_counts),
            "register_counts": dict(register_counts),
            "status_counts": dict(status_counts),
            "interpretation": (
                "Records are source-backed observations from approved current editions. Sector-only repetition is grouped for readability, "
                "but the export does not assert a nationally deduplicated canonical LegalEntity."
            ),
            "geography_policy": "Publication does not wait for optional geographic enrichment.",
            "sources": source_reports,
        },
        "records": all_records,
    }


def _display_list(value: Any) -> str:
    if not isinstance(value, list):
        return ""
    out: list[str] = []
    for item in value:
        if isinstance(item, str):
            text = item
        elif isinstance(item, dict):
            text = str(item.get("raw_value") or item.get("value") or item.get("label") or item.get("date") or "")
        else:
            text = str(item)
        if _clean(text):
            out.append(_clean(text))
    return " · ".join(out)


def write_registry_csv(registry: dict[str, Any], path: Path) -> None:
    fields = [
        "record_locator",
        "authority_name",
        "register_name",
        "reference_date",
        "name",
        "registered_office",
        "secondary_office",
        "identifiers",
        "requested_activities",
        "source_status",
        "primary_date_label",
        "primary_date",
        "application_date",
        "observed_listing_date",
        "decision_date",
        "registration_date",
        "observed_expiry_date",
        "outcome_raw",
        "source_page_url",
        "resource_url",
        "capture_sha256",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in registry["records"]:
            writer.writerow(
                {
                    **{field: record.get(field, "") for field in fields},
                    "identifiers": _display_list(record.get("identifiers")),
                    "requested_activities": _display_list(record.get("requested_activities")),
                }
            )


def _authority_key_from_url(url: str, jurisdiction: str) -> str:
    parts = [part for part in urlparse(url).path.split("/") if part]
    if "prefetture" in parts:
        idx = parts.index("prefetture")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    folded = unicodedata.normalize("NFKD", jurisdiction).encode("ascii", "ignore").decode("ascii").casefold()
    return re.sub(r"[^a-z0-9]+", "-", folded).strip("-")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def build_prefecture_index(
    config: dict[str, Any],
    verified_pages: Path,
    source_series: Path,
) -> dict[str, Any]:
    entries = discover_national_index(max_pages=12, timeout=45)
    if len(entries) < 90:
        raise RuntimeError(f"National White List index unexpectedly small: {len(entries)} entries")

    verified = {row["authority_key"]: row for row in _read_csv(verified_pages)}
    series_by_authority: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in _read_csv(source_series):
        series_by_authority[row["authority_key"]].append(row)
    published_sources: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for source in config["sources"]:
        published_sources[source["authority_key"]].append(source)

    grouped: dict[str, dict[str, Any]] = {}
    for entry in entries:
        key = _authority_key_from_url(entry.white_list_url, entry.jurisdiction_name)
        item = grouped.setdefault(
            key,
            {
                "authority_key": key,
                "jurisdiction_name": entry.jurisdiction_name,
                "official_white_list_urls": [],
                "national_index_title": entry.title,
            },
        )
        if entry.white_list_url not in item["official_white_list_urls"]:
            item["official_white_list_urls"].append(entry.white_list_url)

    rows: list[dict[str, Any]] = []
    for key, item in grouped.items():
        series = series_by_authority.get(key, [])
        published = published_sources.get(key, [])
        verified_row = verified.get(key)
        last_source_update = max((source.get("last_source_update", "") for source in published), default="")
        if published:
            status = "published"
        elif verified_row:
            status = "source_mapped"
        else:
            status = "discovered"
        rows.append(
            {
                **item,
                "mapping_status": status,
                "mapped": bool(verified_row),
                "published": bool(published),
                "series_count": len(series),
                "publication_models": sorted({row["publication_model"] for row in series if row.get("publication_model")}),
                "published_registers": sorted({source["register_name"] for source in published}),
                "last_project_check": verified_row.get("verification_date", "") if verified_row else "",
                "last_source_update": last_source_update,
                "last_source_update_basis": "; ".join(sorted({source.get("last_source_update_basis", "") for source in published if source.get("last_source_update_basis")})),
                "verified_primary_page": verified_row.get("landing_url", "") if verified_row else "",
            }
        )
    rows.sort(key=lambda row: row["jurisdiction_name"].casefold())
    return {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "national_index_url": "https://prefettura.interno.gov.it/it/white-list-nazionale",
            "authority_count": len(rows),
            "published_count": sum(row["published"] for row in rows),
            "mapped_count": sum(row["mapped"] for row in rows),
            "status_counts": dict(Counter(row["mapping_status"] for row in rows)),
        },
        "prefectures": rows,
    }


def write_prefecture_csv(index: dict[str, Any], path: Path) -> None:
    fields = [
        "jurisdiction_name",
        "authority_key",
        "mapping_status",
        "series_count",
        "publication_models",
        "published_registers",
        "last_project_check",
        "last_source_update",
        "verified_primary_page",
        "official_white_list_urls",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in index["prefectures"]:
            writer.writerow(
                {
                    **{field: row.get(field, "") for field in fields},
                    "publication_models": " · ".join(row["publication_models"]),
                    "published_registers": " · ".join(row["published_registers"]),
                    "official_white_list_urls": " · ".join(row["official_white_list_urls"]),
                }
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the public multi-Prefecture pilot registry and national Prefecture index")
    parser.add_argument("--source-config", type=Path, required=True)
    parser.add_argument("--verified-pages", type=Path, required=True)
    parser.add_argument("--source-series", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--registry-json", type=Path, required=True)
    parser.add_argument("--registry-csv", type=Path, required=True)
    parser.add_argument("--prefectures-json", type=Path, required=True)
    parser.add_argument("--prefectures-csv", type=Path, required=True)
    args = parser.parse_args(argv)

    config = json.loads(args.source_config.read_text(encoding="utf-8"))
    registry = build_registry(config, args.work_dir)
    prefectures = build_prefecture_index(config, args.verified_pages, args.source_series)

    args.registry_json.parent.mkdir(parents=True, exist_ok=True)
    args.registry_json.write_text(json.dumps(registry, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    write_registry_csv(registry, args.registry_csv)
    args.prefectures_json.write_text(json.dumps(prefectures, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    write_prefecture_csv(prefectures, args.prefectures_csv)

    print(
        json.dumps(
            {
                "registry_records": registry["meta"]["record_count"],
                "authorities_published": registry["meta"]["authority_count"],
                "registers_published": registry["meta"]["register_count"],
                "status_counts": registry["meta"]["status_counts"],
                "prefectures_in_national_index": prefectures["meta"]["authority_count"],
                "mapped_prefectures": prefectures["meta"]["mapped_count"],
                "published_prefectures": prefectures["meta"]["published_count"],
                "source_diagnostics": registry["meta"]["sources"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
