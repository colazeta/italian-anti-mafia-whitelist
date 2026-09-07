from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
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

from .anncsu_linkage import AnncsuResolution, resolve_anncsu_addresses
from .italian_address import MunicipalityPrefixMatcher

SOFTWARE_NAME = "white_list_archive.geocoding.anncsu_pipeline"
SOFTWARE_VERSION = "1"
PROVIDER_NAME = "anncsu"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_inputs(
    *,
    istat_csv: Path,
    istat_manifest: Path,
    anncsu_csv: Path,
    anncsu_manifest: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    istat = _load_json(istat_manifest)
    anncsu = _load_json(anncsu_manifest)
    expected_istat = str(istat.get("crosswalk_csv", {}).get("sha256") or "")
    expected_anncsu = str(anncsu.get("csv", {}).get("sha256") or "")
    if not expected_istat or _sha256(istat_csv) != expected_istat:
        raise ValueError("Istat municipality CSV does not match its manifest SHA-256")
    if not expected_anncsu or _sha256(anncsu_csv) != expected_anncsu:
        raise ValueError("ANNCSU indirizzario CSV does not match its manifest SHA-256")
    if not anncsu.get("provider_version") or not anncsu.get("source_url"):
        raise ValueError("ANNCSU manifest lacks provider_version/source_url")
    return istat, anncsu


def _configuration_hash(configuration: dict[str, Any]) -> str:
    material = json.dumps(configuration, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _select_addresses(cur, *, provider_version: str, endpoint: str, refresh: bool, max_addresses: int | None):
    sql = """
        SELECT a.address_id, a.full_address
        FROM core.address a
        WHERE btrim(a.full_address) <> ''
    """
    params: list[Any] = []
    if not refresh:
        sql += """
          AND NOT EXISTS (
              SELECT 1 FROM geo.address_geocode_result g
              WHERE g.address_id=a.address_id
                AND g.provider_name=%s
                AND g.provider_endpoint=%s
                AND g.provider_version=%s
                AND upper_inf(g.system_period)
                AND g.match_status_code IN ('accepted','candidate','not_found')
          )
        """
        params.extend([PROVIDER_NAME, endpoint, provider_version])
    sql += " ORDER BY a.full_address, a.address_id"
    if max_addresses is not None:
        if max_addresses < 1:
            raise ValueError("max_addresses must be >= 1")
        sql += " LIMIT %s"
        params.append(max_addresses)
    cur.execute(sql, params)
    return [(row[0], str(row[1])) for row in cur.fetchall()]


def _create_activity(cur, configuration_hash: str):
    cur.execute(
        """
        INSERT INTO provenance.processing_activity(
            activity_type_code,software_name,software_version,
            configuration_hash,started_at
        ) VALUES ('geocode',%s,%s,%s,%s)
        RETURNING processing_activity_id
        """,
        (SOFTWARE_NAME, SOFTWARE_VERSION, configuration_hash, _utc_now()),
    )
    return cur.fetchone()[0]


def _close_current_provider_results(cur, address_id, endpoint: str) -> None:
    cur.execute(
        """
        UPDATE geo.address_geocode_result
        SET system_period=tstzrange(lower(system_period),CURRENT_TIMESTAMP,'[)')
        WHERE address_id=%s AND provider_name=%s AND provider_endpoint=%s
          AND upper_inf(system_period)
        """,
        (address_id, PROVIDER_NAME, endpoint),
    )


def _insert_candidate(
    cur,
    *,
    address_id,
    source_address: str,
    resolution: AnncsuResolution,
    endpoint: str,
    provider_version: str,
    provider_data_updated: datetime,
    activity_id,
) -> None:
    candidate = resolution.candidate
    if candidate is None:
        raise ValueError("candidate resolution required")
    cur.execute(
        """
        INSERT INTO geo.address_geocode_result(
            address_id,provider_name,provider_endpoint,provider_version,
            provider_data_updated,provider_result_id,candidate_rank,
            match_status_code,precision_code,latitude,longitude,confidence,
            query_text,matched_address,normalised_street_name,
            normalised_house_number,normalised_postal_code,normalised_locality,
            normalised_admin_unit_l2,normalised_admin_unit_l1,
            normalised_country_name,normalised_country_code,
            provider_attribution,provider_licence,provider_payload,
            processing_activity_id
        ) VALUES (
            %s,%s,%s,%s,%s,%s,1,'candidate',%s,%s,%s,NULL,
            %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s
        )
        """,
        (
            address_id,
            PROVIDER_NAME,
            endpoint,
            provider_version,
            provider_data_updated,
            candidate.provider_result_id,
            candidate.precision_code,
            candidate.latitude,
            candidate.longitude,
            source_address,
            candidate.matched_address,
            candidate.street_name,
            candidate.house_number,
            candidate.postal_code,
            candidate.locality,
            candidate.admin_unit_l2,
            candidate.admin_unit_l1,
            candidate.country_name,
            candidate.country_code,
            candidate.attribution,
            candidate.licence,
            json.dumps(candidate.payload, ensure_ascii=False),
            activity_id,
        ),
    )


def _insert_not_found(
    cur,
    *,
    address_id,
    source_address: str,
    resolution: AnncsuResolution,
    endpoint: str,
    provider_version: str,
    provider_data_updated: datetime,
    activity_id,
) -> None:
    payload = dict(resolution.detail)
    payload["resolution_status"] = resolution.status
    cur.execute(
        """
        INSERT INTO geo.address_geocode_result(
            address_id,provider_name,provider_endpoint,provider_version,
            provider_data_updated,candidate_rank,match_status_code,
            query_text,provider_payload,processing_activity_id
        ) VALUES (%s,%s,%s,%s,%s,1,'not_found',%s,%s::jsonb,%s)
        """,
        (
            address_id,
            PROVIDER_NAME,
            endpoint,
            provider_version,
            provider_data_updated,
            source_address,
            json.dumps(payload, ensure_ascii=False),
            activity_id,
        ),
    )


def enrich_addresses_from_anncsu(
    *,
    dsn: str,
    istat_csv: Path,
    istat_manifest: Path,
    anncsu_csv: Path,
    anncsu_manifest: Path,
    dataset_region_name: str,
    refresh: bool = False,
    max_addresses: int | None = None,
) -> dict[str, Any]:
    if psycopg is None:
        raise RuntimeError("Install the project with the 'database' extra") from _IMPORT_ERROR
    istat, anncsu = _validate_inputs(
        istat_csv=istat_csv,
        istat_manifest=istat_manifest,
        anncsu_csv=anncsu_csv,
        anncsu_manifest=anncsu_manifest,
    )
    provider_version = str(anncsu["provider_version"])
    endpoint = str(anncsu["source_url"])
    provider_data_updated = datetime.fromisoformat(provider_version).replace(tzinfo=timezone.utc)
    configuration = {
        "software": SOFTWARE_NAME,
        "software_version": SOFTWARE_VERSION,
        "provider_version": provider_version,
        "provider_endpoint": endpoint,
        "anncsu_csv_sha256": anncsu["csv"]["sha256"],
        "istat_crosswalk_version": istat.get("provider_version"),
        "istat_crosswalk_sha256": istat["crosswalk_csv"]["sha256"],
        "dataset_region_name": dataset_region_name,
        "matching_policy": "istat_exact_prefix+anncsu_exact_typed_street+exact_civic_when_available",
        "street_coordinate_fallback": "median_of_anncsu_street_access_coordinates",
        "candidate_by_default": True,
    }
    config_hash = _configuration_hash(configuration)

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            selected = _select_addresses(
                cur,
                provider_version=provider_version,
                endpoint=endpoint,
                refresh=refresh,
                max_addresses=max_addresses,
            )
        if not selected:
            return {
                "provider": PROVIDER_NAME,
                "provider_version": provider_version,
                "selected_address_ids": 0,
                "candidate": 0,
                "not_found": 0,
                "unresolved_or_out_of_scope": 0,
                "configuration_hash": config_hash,
            }

        by_source: dict[str, list[Any]] = defaultdict(list)
        for address_id, source_address in selected:
            by_source[source_address].append(address_id)
        matcher = MunicipalityPrefixMatcher.from_istat_csv(istat_csv)
        resolutions = resolve_anncsu_addresses(
            by_source.keys(),
            municipality_matcher=matcher,
            anncsu_csv=anncsu_csv,
            dataset_region_name=dataset_region_name,
        )
        resolution_by_source = {item.source_address: item for item in resolutions}
        counts = Counter()
        precision_counts = Counter()

        with conn.cursor() as cur:
            activity_id = _create_activity(cur, config_hash)
            for source_address, address_ids in by_source.items():
                resolution = resolution_by_source[source_address]
                counts[resolution.status] += len(address_ids)
                for address_id in address_ids:
                    if resolution.candidate is not None:
                        _close_current_provider_results(cur, address_id, endpoint)
                        _insert_candidate(
                            cur,
                            address_id=address_id,
                            source_address=source_address,
                            resolution=resolution,
                            endpoint=endpoint,
                            provider_version=provider_version,
                            provider_data_updated=provider_data_updated,
                            activity_id=activity_id,
                        )
                        precision_counts[resolution.candidate.precision_code or "none"] += 1
                    elif resolution.status == "no_exact_street_match":
                        _close_current_provider_results(cur, address_id, endpoint)
                        _insert_not_found(
                            cur,
                            address_id=address_id,
                            source_address=source_address,
                            resolution=resolution,
                            endpoint=endpoint,
                            provider_version=provider_version,
                            provider_data_updated=provider_data_updated,
                            activity_id=activity_id,
                        )
            cur.execute(
                "UPDATE provenance.processing_activity SET completed_at=%s WHERE processing_activity_id=%s",
                (_utc_now(), activity_id),
            )
        conn.commit()

    candidate_count = sum(
        count for status, count in counts.items() if status.startswith("exact_") and status not in {"exact_street_ambiguous", "exact_civic_ambiguous"}
    )
    return {
        "provider": PROVIDER_NAME,
        "provider_version": provider_version,
        "provider_endpoint": endpoint,
        "selected_address_ids": len(selected),
        "unique_source_addresses": len(by_source),
        "candidate": candidate_count,
        "not_found": counts.get("no_exact_street_match", 0),
        "unresolved_or_out_of_scope": len(selected) - candidate_count - counts.get("no_exact_street_match", 0),
        "resolution_status_counts": dict(sorted(counts.items())),
        "precision_counts": dict(sorted(precision_counts.items())),
        "configuration_hash": config_hash,
        "candidate_by_default": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Enrich canonical addresses from official ANNCSU exact street/civic matches."
    )
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--istat-csv", type=Path, required=True)
    parser.add_argument("--istat-manifest", type=Path, required=True)
    parser.add_argument("--anncsu-csv", type=Path, required=True)
    parser.add_argument("--anncsu-manifest", type=Path, required=True)
    parser.add_argument("--dataset-region", required=True)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--max-addresses", type=int)
    args = parser.parse_args()
    result = enrich_addresses_from_anncsu(
        dsn=args.dsn,
        istat_csv=args.istat_csv,
        istat_manifest=args.istat_manifest,
        anncsu_csv=args.anncsu_csv,
        anncsu_manifest=args.anncsu_manifest,
        dataset_region_name=args.dataset_region,
        refresh=args.refresh,
        max_addresses=args.max_addresses,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
