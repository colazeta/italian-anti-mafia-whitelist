from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    import psycopg
except ImportError as exc:  # pragma: no cover
    psycopg = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

from .anncsu_linkage import resolve_anncsu_addresses
from .anncsu_pipeline import (
    PROVIDER_NAME,
    SOFTWARE_NAME,
    SOFTWARE_VERSION,
    _close_current_provider_results,
    _configuration_hash,
    _create_activity,
    _insert_candidate,
    _insert_terminal_result,
    _utc_now,
    _validate_inputs,
)
from .italian_address import MunicipalityPrefixMatcher


def _select_scoped_addresses(
    cur,
    *,
    address_ids: Iterable[Any],
    provider_version: str,
    endpoint: str,
):
    ids = list(address_ids)
    if not ids:
        return []
    cur.execute(
        """
        SELECT a.address_id,a.full_address
        FROM core.address a
        JOIN geo.address_country_assessment ca
          ON ca.address_id=a.address_id
         AND upper_inf(ca.system_period)
         AND ca.route_code='italian_anncsu'
        WHERE a.address_id=ANY(%s)
          AND btrim(a.full_address)<>''
          AND NOT EXISTS (
              SELECT 1 FROM geo.address_geocode_result g
              WHERE g.address_id=a.address_id
                AND g.provider_name=%s
                AND g.provider_endpoint=%s
                AND g.provider_version=%s
                AND upper_inf(g.system_period)
                AND g.match_status_code IN ('accepted','candidate','not_found')
          )
        ORDER BY a.full_address,a.address_id
        """,
        (ids, PROVIDER_NAME, endpoint, provider_version),
    )
    return [(row[0], str(row[1])) for row in cur.fetchall()]


def enrich_scoped_addresses_from_anncsu(
    *,
    dsn: str,
    istat_csv: Path,
    istat_manifest: Path,
    anncsu_csv: Path,
    anncsu_manifest: Path,
    dataset_region_name: str,
    address_ids: Iterable[Any],
) -> dict[str, Any]:
    """Apply one ANNCSU regional dataset only to an explicit planned address scope.

    Country assessment and region planning must already have been completed by the
    national orchestrator. Existing results for the same provider version are skipped,
    so a repeat run processes only new addresses or a newly acquired provider version.
    """
    if psycopg is None:
        raise RuntimeError("Install the project with the database extra") from _IMPORT_ERROR

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
        "scope": "national_orchestrator_explicit_address_ids",
        "matching_policy": "istat_exact_prefix+anncsu_exact_typed_street+exact_civic_when_available",
        "candidate_by_default": True,
    }
    config_hash = _configuration_hash(configuration)

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            selected = _select_scoped_addresses(
                cur,
                address_ids=address_ids,
                provider_version=provider_version,
                endpoint=endpoint,
            )
        if not selected:
            return {
                "provider": PROVIDER_NAME,
                "provider_version": provider_version,
                "provider_endpoint": endpoint,
                "selected_address_ids": 0,
                "candidate": 0,
                "not_found": 0,
                "configuration_hash": config_hash,
                "all_selected_addresses_accounted_for": True,
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
        outside = [
            item.source_address for item in resolutions if item.status == "outside_dataset_region"
        ]
        if outside:
            raise RuntimeError(
                f"National ANNCSU plan leaked {len(outside)} address(es) outside {dataset_region_name}"
            )

        counts = Counter()
        precision_counts = Counter()
        candidate_count = 0
        not_found_count = 0
        with conn.cursor() as cur:
            activity_id = _create_activity(cur, config_hash)
            for source_address, ids in by_source.items():
                resolution = resolution_by_source[source_address]
                counts[resolution.status] += len(ids)
                for address_id in ids:
                    _close_current_provider_results(cur, address_id, endpoint)
                    if resolution.candidate is not None:
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
                        candidate_count += 1
                        precision_counts[resolution.candidate.precision_code or "none"] += 1
                    else:
                        _insert_terminal_result(
                            cur,
                            address_id=address_id,
                            source_address=source_address,
                            resolution=resolution,
                            endpoint=endpoint,
                            provider_version=provider_version,
                            provider_data_updated=provider_data_updated,
                            activity_id=activity_id,
                        )
                        not_found_count += 1
            cur.execute(
                "UPDATE provenance.processing_activity SET completed_at=%s WHERE processing_activity_id=%s",
                (_utc_now(), activity_id),
            )
        conn.commit()

    if candidate_count + not_found_count != len(selected):
        raise RuntimeError("Scoped ANNCSU accounting does not reconcile")
    return {
        "provider": PROVIDER_NAME,
        "provider_version": provider_version,
        "provider_endpoint": endpoint,
        "selected_address_ids": len(selected),
        "candidate": candidate_count,
        "not_found": not_found_count,
        "resolution_status_counts": dict(sorted(counts.items())),
        "precision_counts": dict(sorted(precision_counts.items())),
        "configuration_hash": config_hash,
        "all_selected_addresses_accounted_for": True,
    }
