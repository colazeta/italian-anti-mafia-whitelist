from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import shutil
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import psycopg

from white_list_archive.acquisition.anncsu import USER_AGENT, build_bulk_url
from white_list_archive.geocoding.italian_address import MunicipalityPrefixMatcher
from white_list_archive.geocoding.national_anncsu import (
    ANNCSU_REGION_DATASETS,
    MAP_VERSION,
    orchestrate,
)
from white_list_archive.publishing.public_national_registry import (
    _download,
    _parse_source,
    _validate_batch,
)


def _probe_dataset(item: dict[str, str | None]) -> dict[str, object]:
    code = str(item["dataset"])
    url = build_bulk_url(code)
    # The ANNCSU endpoint rejects Range requests with HTTP 406. Read the first
    # two response bytes and close the connection instead; this validates the ZIP
    # signature without intentionally retaining the provider archive.
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/octet-stream,*/*"},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        magic = response.read(2)
        result = {
            "region": item["region"],
            "province": item["province"],
            "dataset_code": code,
            "url": url,
            "http_status": response.status,
            "content_type": response.headers.get("Content-Type"),
            "content_disposition": response.headers.get("Content-Disposition"),
            "magic_hex": magic.hex(),
        }
    if magic != b"PK":
        raise RuntimeError(f"{code}: official endpoint did not return ZIP signature: {result}")
    return result


def verify_catalogue(artifact_dir: Path) -> list[dict[str, object]]:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, object]] = []
    failures: list[dict[str, str]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(_probe_dataset, item): item for item in ANNCSU_REGION_DATASETS}
        for future in concurrent.futures.as_completed(futures):
            item = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:  # retain complete diagnostic before failing the gate
                failures.append(
                    {
                        "dataset_code": str(item["dataset"]),
                        "region": str(item["region"]),
                        "province": str(item["province"] or ""),
                        "error": repr(exc),
                    }
                )
    results.sort(key=lambda row: str(row["dataset_code"]))
    failures.sort(key=lambda row: row["dataset_code"])
    payload = {
        "map_version": MAP_VERSION,
        "verified_dataset_count": len(results),
        "failure_count": len(failures),
        "datasets": results,
        "failures": failures,
    }
    (artifact_dir / "provider-catalogue-probe.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    if failures:
        raise RuntimeError(f"ANNCSU regional catalogue probe failed: {failures}")
    if len(results) != 21 or len({row["dataset_code"] for row in results}) != 21:
        raise RuntimeError("Regional ANNCSU catalogue did not reconcile to 21 unique provider datasets")
    return results


def _source_backed_fixture(
    *,
    dsn: str,
    istat_csv: Path,
    source_config: Path,
    artifact_dir: Path,
) -> str:
    config = json.loads(source_config.read_text(encoding="utf-8"))
    wanted = {
        "cosenza-combined": ("Calabria", 20, 0),
        "pistoia-listed": ("Toscana", 20, 1),
    }
    matcher = MunicipalityPrefixMatcher.from_istat_csv(istat_csv)
    source_dir = Path("/tmp/anncsu-national-whitelist-sources")
    selected: dict[str, list[str]] = {}
    reserve: dict[str, list[str]] = {}
    source_evidence: dict[str, object] = {}

    for cfg in config["sources"]:
        if cfg["source_key"] not in wanted:
            continue
        region, target, reserve_n = wanted[cfg["source_key"]]
        suffix = Path(urlparse(cfg["resource_url"]).path).suffix or ".pdf"
        path = source_dir / f"{cfg['source_key']}{suffix}"
        observed_sha = _download(cfg["resource_url"], path)
        if observed_sha != cfg["sha256"]:
            raise RuntimeError(f"{cfg['source_key']}: approved source SHA mismatch")
        batch = _parse_source(path, cfg)
        _validate_batch(cfg, batch)

        addresses: list[str] = []
        seen: set[str] = set()
        for record in batch.records:
            for field in ("registered_office", "secondary_office"):
                address = " ".join(str(record.get(field) or "").split())
                if not address or address in seen:
                    continue
                split = matcher.split(address)
                if (
                    split.status == "exact"
                    and split.split
                    and split.split.municipality.region_name == region
                ):
                    addresses.append(address)
                    seen.add(address)
        if len(addresses) < target + reserve_n:
            raise RuntimeError(
                f"{cfg['source_key']}: only {len(addresses)} exact {region} addresses"
            )
        selected[cfg["source_key"]] = addresses[:target]
        reserve[cfg["source_key"]] = addresses[target : target + reserve_n]
        source_evidence[cfg["source_key"]] = {
            "authority_key": cfg["authority_key"],
            "region": region,
            "capture_sha256": observed_sha,
            "reference_date": cfg["reference_date"],
            "parsed_records": len(batch.records),
            "initial_addresses": target,
            "reserved_new_addresses": reserve_n,
        }

    if set(selected) != set(wanted):
        raise RuntimeError(f"Missing multi-region source: {set(wanted) - set(selected)}")
    initial = [address for values in selected.values() for address in values]
    if len(initial) != 40 or len(set(initial)) != 40:
        raise RuntimeError("Expected 40 unique initial source-backed addresses")

    now = datetime.now(timezone.utc).replace(microsecond=0)
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO provenance.processing_activity(
                activity_type_code,software_name,software_version,
                configuration_hash,started_at,completed_at
            ) VALUES ('normalise','anncsu-national-live-fixture','1',%s,%s,%s)
            RETURNING processing_activity_id
            """,
            ("f" * 64, now, now),
        )
        activity = cur.fetchone()[0]
        for address in initial:
            cur.execute(
                "INSERT INTO core.address(full_address,country_code,processing_activity_id) VALUES (%s,NULL,%s)",
                (address, activity),
            )
        conn.commit()

    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "fixture-evidence.json").write_text(
        json.dumps(
            {"sources": source_evidence, "initial_address_count": 40},
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    reserved = reserve.get("pistoia-listed") or []
    if len(reserved) != 1:
        raise RuntimeError(f"Expected one reserved Toscana address, got {len(reserved)}")
    return reserved[0]


def _write_run(artifact_dir: Path, number: int, payload: dict[str, object]) -> None:
    (artifact_dir / f"run-{number}.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )


def _validate_first(payload: dict[str, object]) -> None:
    regions = {row["dataset_code"]: row for row in payload["regions"]}
    if set(regions) != {"INDIR_CALA", "INDIR_TOSC"}:
        raise RuntimeError(f"Unexpected required datasets: {set(regions)}")
    plan = payload["plan"]
    if plan["total_canonical_addresses"] != 40 or plan["italian_route_addresses"] != 40:
        raise RuntimeError(f"Unexpected first-run population: {plan}")
    if plan["unassigned_addresses"] != 0:
        raise RuntimeError(f"Unexpected unassigned Italian addresses: {plan}")
    if payload["processed_address_count"] != 40 or payload["skipped_existing_count"] != 0:
        raise RuntimeError("First run did not process exactly the initial population")
    if not payload["all_processed_addresses_accounted_for"] or payload["public_nominatim_used"]:
        raise RuntimeError("First-run accounting/provider policy failure")
    for item in regions.values():
        if item["planned_address_count"] != 20 or item["processed_address_count"] != 20:
            raise RuntimeError(f"Bad first regional accounting: {item}")
        if item["cache_status"] != "acquired" or not item["provider_version"]:
            raise RuntimeError(f"Provider cache/provenance missing: {item}")
        if item["candidate"] + item["not_found"] != 20:
            raise RuntimeError(f"Provider attempt accounting mismatch: {item}")


def _validate_second(first: dict[str, object], second: dict[str, object]) -> None:
    one = {row["dataset_code"]: row for row in first["regions"]}
    two = {row["dataset_code"]: row for row in second["regions"]}
    if second["processed_address_count"] != 0 or second["skipped_existing_count"] != 40:
        raise RuntimeError("Second run was not an incremental same-version no-op")
    for code in one:
        if two[code]["cache_status"] != "reused":
            raise RuntimeError(f"{code}: provider cache was not reused")
        identity_one = (
            one[code]["provider_version"],
            one[code]["zip_sha256"],
            one[code]["csv_sha256"],
        )
        identity_two = (
            two[code]["provider_version"],
            two[code]["zip_sha256"],
            two[code]["csv_sha256"],
        )
        if identity_one != identity_two:
            raise RuntimeError(f"{code}: cached provider identity changed")
        if two[code]["processed_address_count"] != 0 or two[code]["skipped_existing_count"] != 20:
            raise RuntimeError(f"{code}: same-version rows were reprocessed")


def _insert_new_toscana_address(dsn: str, address: str) -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO provenance.processing_activity(
                activity_type_code,software_name,software_version,
                configuration_hash,started_at,completed_at
            ) VALUES ('normalise','anncsu-national-new-address','1',%s,%s,%s)
            RETURNING processing_activity_id
            """,
            ("e" * 64, now, now),
        )
        activity = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO core.address(full_address,country_code,processing_activity_id) VALUES (%s,NULL,%s)",
            (address, activity),
        )
        conn.commit()


def _validate_third(payload: dict[str, object]) -> None:
    regions = {row["dataset_code"]: row for row in payload["regions"]}
    plan = payload["plan"]
    if plan["total_canonical_addresses"] != 41 or plan["italian_route_addresses"] != 41:
        raise RuntimeError(f"New address absent from third-run plan: {plan}")
    if payload["processed_address_count"] != 1 or payload["skipped_existing_count"] != 40:
        raise RuntimeError("New-address incremental processing failed")
    if regions["INDIR_CALA"]["planned_address_count"] != 20 or regions["INDIR_CALA"]["processed_address_count"] != 0:
        raise RuntimeError("Calabria should be a complete same-version no-op")
    if regions["INDIR_TOSC"]["planned_address_count"] != 21 or regions["INDIR_TOSC"]["processed_address_count"] != 1:
        raise RuntimeError("Toscana should process only the new address")
    if any(row["cache_status"] != "reused" for row in regions.values()):
        raise RuntimeError("Third-run provider inputs should all be reused")


def _validate_persistence(dsn: str) -> None:
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM geo.anncsu_orchestration_run WHERE status_code='succeeded'")
        if int(cur.fetchone()[0]) != 3:
            raise RuntimeError("Expected exactly three successful orchestration runs")
        cur.execute(
            """
            SELECT dataset_code,provider_version,zip_sha256,csv_sha256,cache_status,
                   planned_address_count,processed_address_count,candidate_count,
                   not_found_count,skipped_existing_count,status_code
            FROM geo.anncsu_region_run
            ORDER BY created_at,dataset_code
            """
        )
        rows = cur.fetchall()
        if len(rows) != 6 or {row[0] for row in rows} != {"INDIR_CALA", "INDIR_TOSC"}:
            raise RuntimeError(f"Unexpected persisted regional provenance: {rows}")
        for row in rows:
            _, version, zip_sha, csv_sha, _, planned, processed, candidate, not_found, skipped, status = row
            if not version or not re.fullmatch(r"[0-9a-f]{64}", zip_sha) or not re.fullmatch(r"[0-9a-f]{64}", csv_sha):
                raise RuntimeError(f"Incomplete provider physical identity: {row}")
            if candidate + not_found != processed or processed + skipped != planned or status != "succeeded":
                raise RuntimeError(f"Persisted regional accounting mismatch: {row}")
        cur.execute(
            "SELECT count(*) FROM geo.address_geocode_result WHERE upper_inf(system_period) AND provider_name<>'anncsu'"
        )
        if int(cur.fetchone()[0]):
            raise RuntimeError("Recurring national validation used a non-ANNCSU provider")
        cur.execute(
            """
            SELECT count(*)
            FROM geo.address_geocode_result g
            JOIN geo.address_country_assessment ca USING(address_id)
            WHERE upper_inf(g.system_period) AND upper_inf(ca.system_period)
              AND g.provider_name='anncsu' AND ca.route_code<>'italian_anncsu'
            """
        )
        if int(cur.fetchone()[0]):
            raise RuntimeError("ANNCSU result exists outside defensibly Italian route")
        cur.execute(
            "SELECT count(*) FROM geo.address_geocode_result WHERE upper_inf(system_period) AND match_status_code='accepted'"
        )
        if int(cur.fetchone()[0]):
            raise RuntimeError("National orchestration must not auto-accept geography")


def run(args: argparse.Namespace) -> dict[str, object]:
    artifact_dir = args.artifact_dir
    artifact_dir.mkdir(parents=True, exist_ok=True)
    probes = verify_catalogue(artifact_dir)
    reserved_toscana = _source_backed_fixture(
        dsn=args.dsn,
        istat_csv=args.istat_csv,
        source_config=args.source_config,
        artifact_dir=artifact_dir,
    )
    shutil.rmtree(args.cache_dir, ignore_errors=True)

    first = orchestrate(
        dsn=args.dsn,
        istat_csv=args.istat_csv,
        istat_manifest=args.istat_manifest,
        cache_dir=args.cache_dir,
    )
    _write_run(artifact_dir, 1, first)
    _validate_first(first)

    second = orchestrate(
        dsn=args.dsn,
        istat_csv=args.istat_csv,
        istat_manifest=args.istat_manifest,
        cache_dir=args.cache_dir,
    )
    _write_run(artifact_dir, 2, second)
    _validate_second(first, second)

    _insert_new_toscana_address(args.dsn, reserved_toscana)
    third = orchestrate(
        dsn=args.dsn,
        istat_csv=args.istat_csv,
        istat_manifest=args.istat_manifest,
        cache_dir=args.cache_dir,
    )
    _write_run(artifact_dir, 3, third)
    _validate_third(third)
    _validate_persistence(args.dsn)

    summary = {
        "catalogue_dataset_codes_verified": len(probes),
        "validated_prefectures": ["cosenza", "pistoia"],
        "validated_regions": ["Calabria", "Toscana"],
        "provider_datasets": ["INDIR_CALA", "INDIR_TOSC"],
        "run_count": 3,
        "first_run_processed": first["processed_address_count"],
        "same_version_second_run_processed": second["processed_address_count"],
        "new_address_third_run_processed": third["processed_address_count"],
        "public_nominatim_used": False,
    }
    (artifact_dir / "live-validation-summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--istat-csv", type=Path, required=True)
    parser.add_argument("--istat-manifest", type=Path, required=True)
    parser.add_argument("--source-config", type=Path, required=True)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    args = parser.parse_args()
    summary = run(args)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
