from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import psycopg
except ImportError as exc:  # pragma: no cover
    psycopg = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

from white_list_archive.acquisition.anncsu import acquire_dataset, sha256_file
from white_list_archive.geocoding.anncsu_scoped import enrich_scoped_addresses_from_anncsu
from white_list_archive.geocoding.country_routing import assess_address_countries
from white_list_archive.geocoding.italian_address import MunicipalityPrefixMatcher

SOFTWARE_NAME = "white_list_archive.geocoding.national_anncsu"
SOFTWARE_VERSION = "1"
MAP_VERSION = "anncsu-regional-datasets-2026-09"

# ANNCSU regional/provincial bulk files. Bolzano and Trento are distinct provider
# datasets although the Istat municipality crosswalk reports one shared region.
ANNCSU_REGION_DATASETS: tuple[dict[str, str | None], ...] = (
    {"region": "Abruzzo", "province": None, "dataset": "INDIR_ABRU"},
    {"region": "Basilicata", "province": None, "dataset": "INDIR_BASI"},
    {"region": "Trentino-Alto Adige/Südtirol", "province": "BZ", "dataset": "INDIR_BOLZ"},
    {"region": "Calabria", "province": None, "dataset": "INDIR_CALA"},
    {"region": "Campania", "province": None, "dataset": "INDIR_CAMP"},
    {"region": "Emilia-Romagna", "province": None, "dataset": "INDIR_EMIL"},
    {"region": "Friuli-Venezia Giulia", "province": None, "dataset": "INDIR_FRIU"},
    {"region": "Lazio", "province": None, "dataset": "INDIR_LAZI"},
    {"region": "Liguria", "province": None, "dataset": "INDIR_LIGU"},
    {"region": "Lombardia", "province": None, "dataset": "INDIR_LOMB"},
    {"region": "Marche", "province": None, "dataset": "INDIR_MARC"},
    {"region": "Molise", "province": None, "dataset": "INDIR_MOLI"},
    {"region": "Piemonte", "province": None, "dataset": "INDIR_PIEM"},
    {"region": "Puglia", "province": None, "dataset": "INDIR_PUGL"},
    {"region": "Sardegna", "province": None, "dataset": "INDIR_SARD"},
    {"region": "Sicilia", "province": None, "dataset": "INDIR_SICI"},
    {"region": "Toscana", "province": None, "dataset": "INDIR_TOSC"},
    {"region": "Trentino-Alto Adige/Südtirol", "province": "TN", "dataset": "INDIR_TREN"},
    {"region": "Umbria", "province": None, "dataset": "INDIR_UMBR"},
    {"region": "Valle d'Aosta/Vallée d'Aoste", "province": None, "dataset": "INDIR_VALL"},
    {"region": "Veneto", "province": None, "dataset": "INDIR_VENE"},
)

_REGION_ALIASES = {
    "trentino alto adige": "trentino alto adige sudtirol",
    "trentino alto adige sudtirol": "trentino alto adige sudtirol",
    "valle d aosta": "valle d aosta vallee d aoste",
    "valle d aosta vallee d aoste": "valle d aosta vallee d aoste",
}


def _fold(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text).strip().casefold()
    return _REGION_ALIASES.get(text, text)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _sha_json(value: Any) -> str:
    material = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def dataset_code_for(region_name: str, province_plate: str | None = None) -> str:
    region_key = _fold(region_name)
    province = (province_plate or "").strip().upper() or None
    matches: list[str] = []
    for item in ANNCSU_REGION_DATASETS:
        if _fold(str(item["region"])) != region_key:
            continue
        item_province = item["province"]
        if item_province is not None and item_province != province:
            continue
        if item_province is None and region_key == _fold("Trentino-Alto Adige/Südtirol"):
            continue
        matches.append(str(item["dataset"]))
    if len(matches) != 1:
        raise LookupError(
            f"No unique ANNCSU dataset mapping for region={region_name!r}, province={province!r}: {matches}"
        )
    return matches[0]


@dataclass(frozen=True)
class RegionPlan:
    region_name: str
    province_plate: str | None
    dataset_code: str
    address_ids: tuple[Any, ...]
    address_fingerprints: tuple[str, ...]

    @property
    def address_count(self) -> int:
        return len(self.address_ids)


@dataclass(frozen=True)
class NationalPlan:
    total_canonical_addresses: int
    italian_route_addresses: int
    assignable_addresses: int
    unassigned_addresses: int
    unassigned_reason_counts: dict[str, int]
    regions: tuple[RegionPlan, ...]
    plan_sha256: str

    def payload(self) -> dict[str, Any]:
        return {
            "total_canonical_addresses": self.total_canonical_addresses,
            "italian_route_addresses": self.italian_route_addresses,
            "assignable_addresses": self.assignable_addresses,
            "unassigned_addresses": self.unassigned_addresses,
            "unassigned_reason_counts": self.unassigned_reason_counts,
            "required_regions": [
                {
                    "region_name": region.region_name,
                    "province_plate": region.province_plate,
                    "dataset_code": region.dataset_code,
                    "address_count": region.address_count,
                }
                for region in self.regions
            ],
            "plan_sha256": self.plan_sha256,
        }


@dataclass(frozen=True)
class CachedDataset:
    dataset_code: str
    provider_version: str
    source_url: str
    zip_path: Path
    csv_path: Path
    manifest_path: Path
    zip_sha256: str
    csv_sha256: str
    cache_status: str

    def payload(self) -> dict[str, Any]:
        return {
            "dataset_code": self.dataset_code,
            "provider_version": self.provider_version,
            "source_url": self.source_url,
            "zip_sha256": self.zip_sha256,
            "csv_sha256": self.csv_sha256,
            "cache_status": self.cache_status,
        }


def _validate_istat(istat_csv: Path, istat_manifest: Path) -> dict[str, Any]:
    manifest = json.loads(istat_manifest.read_text(encoding="utf-8"))
    expected = str(manifest.get("crosswalk_csv", {}).get("sha256") or "")
    observed = sha256_file(istat_csv)
    if not expected or expected != observed:
        raise ValueError("Istat municipality CSV does not match its manifest SHA-256")
    return manifest


def _build_plan_from_connection(conn, *, istat_csv: Path, istat_manifest: Path) -> NationalPlan:
    _validate_istat(istat_csv, istat_manifest)
    matcher = MunicipalityPrefixMatcher.from_istat_csv(istat_csv)
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM core.address")
        total = int(cur.fetchone()[0])
        cur.execute(
            """
            SELECT a.address_id,a.full_address
            FROM core.address a
            JOIN geo.address_country_assessment ca
              ON ca.address_id=a.address_id
             AND upper_inf(ca.system_period)
             AND ca.route_code='italian_anncsu'
            ORDER BY a.full_address,a.address_id
            """
        )
        rows = cur.fetchall()

    grouped: dict[tuple[str, str | None, str], list[tuple[Any, str]]] = defaultdict(list)
    unassigned = Counter()
    for address_id, full_address in rows:
        source_address = str(full_address)
        split = matcher.split(source_address)
        if split.status != "exact" or split.split is None:
            unassigned[f"istat_split:{split.status}"] += 1
            continue
        municipality = split.split.municipality
        dataset_code = dataset_code_for(municipality.region_name, municipality.province_plate)
        province_scope = (
            municipality.province_plate
            if dataset_code in {"INDIR_BOLZ", "INDIR_TREN"}
            else None
        )
        grouped[(municipality.region_name, province_scope, dataset_code)].append(
            (address_id, source_address)
        )

    regions: list[RegionPlan] = []
    for (region_name, province_plate, dataset_code), items in sorted(
        grouped.items(), key=lambda item: item[0][2]
    ):
        regions.append(
            RegionPlan(
                region_name=region_name,
                province_plate=province_plate,
                dataset_code=dataset_code,
                address_ids=tuple(item[0] for item in items),
                address_fingerprints=tuple(
                    hashlib.sha256(item[1].encode("utf-8")).hexdigest()
                    for item in items
                ),
            )
        )

    plan_material = {
        "map_version": MAP_VERSION,
        "regions": [
            {
                "region": region.region_name,
                "province": region.province_plate,
                "dataset": region.dataset_code,
                "address_fingerprints": sorted(region.address_fingerprints),
            }
            for region in regions
        ],
        "unassigned_reason_counts": dict(sorted(unassigned.items())),
    }
    assignable = sum(region.address_count for region in regions)
    return NationalPlan(
        total_canonical_addresses=total,
        italian_route_addresses=len(rows),
        assignable_addresses=assignable,
        unassigned_addresses=len(rows) - assignable,
        unassigned_reason_counts=dict(sorted(unassigned.items())),
        regions=tuple(regions),
        plan_sha256=_sha_json(plan_material),
    )


def build_plan(*, dsn: str, istat_csv: Path, istat_manifest: Path) -> NationalPlan:
    if psycopg is None:
        raise RuntimeError("Install the project with the database extra") from _IMPORT_ERROR
    with psycopg.connect(dsn) as conn:
        return _build_plan_from_connection(conn, istat_csv=istat_csv, istat_manifest=istat_manifest)


def _cached_from_manifest(
    manifest_path: Path,
    *,
    dataset_code: str,
    cache_status: str,
) -> CachedDataset:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if str(manifest.get("dataset_code") or "").upper() != dataset_code:
        raise ValueError(f"Cached ANNCSU manifest dataset mismatch: {manifest_path}")
    version = str(manifest.get("provider_version") or "")
    source_url = str(manifest.get("source_url") or "")
    zip_info = manifest.get("zip") or {}
    csv_info = manifest.get("csv") or {}
    zip_path = manifest_path.parent / str(zip_info.get("path") or "")
    csv_path = manifest_path.parent / str(csv_info.get("path") or "")
    zip_sha = str(zip_info.get("sha256") or "")
    csv_sha = str(csv_info.get("sha256") or "")
    if not version or not source_url or not zip_sha or not csv_sha:
        raise ValueError(f"Incomplete cached ANNCSU manifest: {manifest_path}")
    if not zip_path.is_file() or sha256_file(zip_path) != zip_sha:
        raise ValueError(f"Cached ANNCSU ZIP identity mismatch: {zip_path}")
    if not csv_path.is_file() or sha256_file(csv_path) != csv_sha:
        raise ValueError(f"Cached ANNCSU CSV identity mismatch: {csv_path}")
    return CachedDataset(
        dataset_code=dataset_code,
        provider_version=version,
        source_url=source_url,
        zip_path=zip_path,
        csv_path=csv_path,
        manifest_path=manifest_path,
        zip_sha256=zip_sha,
        csv_sha256=csv_sha,
        cache_status=cache_status,
    )


def _latest_cached_dataset(cache_dir: Path, dataset_code: str) -> CachedDataset | None:
    dataset_dir = cache_dir / dataset_code
    cached = [
        _cached_from_manifest(path, dataset_code=dataset_code, cache_status="reused")
        for path in sorted(dataset_dir.glob(f"anncsu-{dataset_code.lower()}-*.manifest.json"))
    ]
    return max(cached, key=lambda item: (item.provider_version, item.csv_sha256)) if cached else None


def acquire_or_reuse_dataset(
    *,
    cache_dir: Path,
    dataset_code: str,
    refresh_provider_inputs: bool,
) -> CachedDataset:
    dataset_code = dataset_code.strip().upper()
    cached = _latest_cached_dataset(cache_dir, dataset_code)
    if cached is not None and not refresh_provider_inputs:
        return cached
    dataset_dir = cache_dir / dataset_code
    dataset_dir.mkdir(parents=True, exist_ok=True)
    manifest = acquire_dataset(dataset_code, dataset_dir)
    return _cached_from_manifest(
        dataset_dir / str(manifest["manifest_path"]),
        dataset_code=dataset_code,
        cache_status="refreshed" if cached else "acquired",
    )


def _start_run(
    conn,
    *,
    plan: NationalPlan,
    istat_manifest: dict[str, Any],
    refresh_provider_inputs: bool,
):
    configuration = {
        "software": SOFTWARE_NAME,
        "software_version": SOFTWARE_VERSION,
        "map_version": MAP_VERSION,
        "plan_sha256": plan.plan_sha256,
        "istat_provider_version": istat_manifest.get("provider_version"),
        "istat_sha256": istat_manifest.get("crosswalk_csv", {}).get("sha256"),
        "refresh_provider_inputs": refresh_provider_inputs,
    }
    now = _utc_now()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO provenance.processing_activity(
                activity_type_code,software_name,software_version,
                configuration_hash,started_at
            ) VALUES ('anncsu_orchestrate',%s,%s,%s,%s)
            RETURNING processing_activity_id
            """,
            (SOFTWARE_NAME, SOFTWARE_VERSION, _sha_json(configuration), now),
        )
        activity_id = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO geo.anncsu_orchestration_run(
                processing_activity_id,map_version,plan_sha256,
                istat_reference_version,istat_sha256,refresh_provider_inputs,
                total_canonical_addresses,italian_route_addresses,
                assignable_addresses,unassigned_addresses,status_code,started_at
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'running',%s)
            RETURNING anncsu_orchestration_run_id
            """,
            (
                activity_id,
                MAP_VERSION,
                plan.plan_sha256,
                str(istat_manifest.get("provider_version") or ""),
                str(istat_manifest.get("crosswalk_csv", {}).get("sha256") or ""),
                refresh_provider_inputs,
                plan.total_canonical_addresses,
                plan.italian_route_addresses,
                plan.assignable_addresses,
                plan.unassigned_addresses,
                now,
            ),
        )
        run_id = cur.fetchone()[0]
    conn.commit()
    return run_id, activity_id


def _record_region(
    conn,
    *,
    run_id,
    region: RegionPlan,
    dataset: CachedDataset,
    result: dict[str, Any] | None,
    status_code: str,
    error_text: str | None = None,
) -> None:
    processed = int((result or {}).get("selected_address_ids") or 0)
    candidate = int((result or {}).get("candidate") or 0)
    not_found = int((result or {}).get("not_found") or 0)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO geo.anncsu_region_run(
                anncsu_orchestration_run_id,region_name,province_plate,
                dataset_code,provider_version,provider_endpoint,
                zip_sha256,csv_sha256,cache_status,
                planned_address_count,processed_address_count,candidate_count,
                not_found_count,skipped_existing_count,status_code,error_text
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                run_id,
                region.region_name,
                region.province_plate,
                region.dataset_code,
                dataset.provider_version,
                dataset.source_url,
                dataset.zip_sha256,
                dataset.csv_sha256,
                dataset.cache_status,
                region.address_count,
                processed,
                candidate,
                not_found,
                region.address_count - processed,
                status_code,
                error_text,
            ),
        )
    conn.commit()


def _finish_run(conn, *, run_id, activity_id, status_code: str, error_text: str | None = None) -> None:
    now = _utc_now()
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE geo.anncsu_orchestration_run
            SET status_code=%s,completed_at=%s,error_text=%s
            WHERE anncsu_orchestration_run_id=%s
            """,
            (status_code, now, error_text, run_id),
        )
        cur.execute(
            "UPDATE provenance.processing_activity SET completed_at=%s WHERE processing_activity_id=%s",
            (now, activity_id),
        )
    conn.commit()


def orchestrate(
    *,
    dsn: str,
    istat_csv: Path,
    istat_manifest: Path,
    cache_dir: Path,
    refresh_provider_inputs: bool = False,
) -> dict[str, Any]:
    if psycopg is None:
        raise RuntimeError("Install the project with the database extra") from _IMPORT_ERROR
    istat = _validate_istat(istat_csv, istat_manifest)

    with psycopg.connect(dsn) as conn:
        country_assessment = assess_address_countries(
            conn, istat_csv=istat_csv, istat_manifest=istat_manifest
        )
        conn.commit()
        plan = _build_plan_from_connection(conn, istat_csv=istat_csv, istat_manifest=istat_manifest)
        run_id, activity_id = _start_run(
            conn,
            plan=plan,
            istat_manifest=istat,
            refresh_provider_inputs=refresh_provider_inputs,
        )

    region_outputs: list[dict[str, Any]] = []
    try:
        for region in plan.regions:
            dataset = acquire_or_reuse_dataset(
                cache_dir=cache_dir,
                dataset_code=region.dataset_code,
                refresh_provider_inputs=refresh_provider_inputs,
            )
            try:
                result = enrich_scoped_addresses_from_anncsu(
                    dsn=dsn,
                    istat_csv=istat_csv,
                    istat_manifest=istat_manifest,
                    anncsu_csv=dataset.csv_path,
                    anncsu_manifest=dataset.manifest_path,
                    dataset_region_name=region.region_name,
                    address_ids=region.address_ids,
                )
            except Exception as exc:
                with psycopg.connect(dsn) as conn:
                    _record_region(
                        conn,
                        run_id=run_id,
                        region=region,
                        dataset=dataset,
                        result=None,
                        status_code="failed",
                        error_text=str(exc),
                    )
                raise

            processed = int(result.get("selected_address_ids") or 0)
            if int(result.get("candidate") or 0) + int(result.get("not_found") or 0) != processed:
                raise RuntimeError(f"Regional ANNCSU accounting does not reconcile for {region.dataset_code}")
            with psycopg.connect(dsn) as conn:
                _record_region(
                    conn,
                    run_id=run_id,
                    region=region,
                    dataset=dataset,
                    result=result,
                    status_code="succeeded",
                )
            region_outputs.append(
                {
                    **dataset.payload(),
                    "region_name": region.region_name,
                    "province_plate": region.province_plate,
                    "planned_address_count": region.address_count,
                    "processed_address_count": processed,
                    "skipped_existing_count": region.address_count - processed,
                    "candidate": int(result.get("candidate") or 0),
                    "not_found": int(result.get("not_found") or 0),
                    "precision_counts": result.get("precision_counts") or {},
                    "resolution_status_counts": result.get("resolution_status_counts") or {},
                }
            )
    except Exception as exc:
        with psycopg.connect(dsn) as conn:
            _finish_run(
                conn,
                run_id=run_id,
                activity_id=activity_id,
                status_code="failed",
                error_text=str(exc),
            )
        raise

    with psycopg.connect(dsn) as conn:
        _finish_run(conn, run_id=run_id, activity_id=activity_id, status_code="succeeded")

    processed_total = sum(region["processed_address_count"] for region in region_outputs)
    skipped_total = sum(region["skipped_existing_count"] for region in region_outputs)
    return {
        "software": SOFTWARE_NAME,
        "software_version": SOFTWARE_VERSION,
        "map_version": MAP_VERSION,
        "orchestration_run_id": str(run_id),
        "generated_at": _utc_now().isoformat(),
        "country_assessment": country_assessment,
        "plan": plan.payload(),
        "regions": region_outputs,
        "processed_address_count": processed_total,
        "skipped_existing_count": skipped_total,
        "candidate": sum(region["candidate"] for region in region_outputs),
        "not_found": sum(region["not_found"] for region in region_outputs),
        "all_processed_addresses_accounted_for": all(
            region["candidate"] + region["not_found"] == region["processed_address_count"]
            for region in region_outputs
        ),
        "public_nominatim_used": False,
    }


def _emit(path: Path | None, payload: dict[str, Any]) -> None:
    text = json.dumps(payload, indent=2, ensure_ascii=False, default=str)
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
    print(text)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Select only the ANNCSU regional bulk datasets required by the current "
            "defensibly Italian canonical address population, cache/version them, "
            "and apply incremental exact linkage locally."
        )
    )
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--istat-csv", type=Path, required=True)
    parser.add_argument("--istat-manifest", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--refresh-provider-inputs", action="store_true")
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()

    if args.plan_only:
        if psycopg is None:
            raise RuntimeError("Install the project with the database extra") from _IMPORT_ERROR
        with psycopg.connect(args.dsn) as conn:
            assess_address_countries(
                conn,
                istat_csv=args.istat_csv,
                istat_manifest=args.istat_manifest,
            )
            conn.commit()
            plan = _build_plan_from_connection(
                conn,
                istat_csv=args.istat_csv,
                istat_manifest=args.istat_manifest,
            )
        payload = {
            "software": SOFTWARE_NAME,
            "software_version": SOFTWARE_VERSION,
            "map_version": MAP_VERSION,
            "plan": plan.payload(),
            "public_nominatim_used": False,
        }
    else:
        payload = orchestrate(
            dsn=args.dsn,
            istat_csv=args.istat_csv,
            istat_manifest=args.istat_manifest,
            cache_dir=args.cache_dir,
            refresh_provider_inputs=args.refresh_provider_inputs,
        )
    _emit(args.output, payload)


if __name__ == "__main__":
    main()
