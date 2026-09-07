from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from .models import GeocodeCandidate
from .nominatim import NominatimClient

try:
    import psycopg
except ImportError as exc:  # pragma: no cover - exercised only without database extra
    psycopg = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

SOFTWARE_NAME = "white_list_archive.geocoding.pipeline"
SOFTWARE_VERSION = "1"
PUBLIC_ONE_TIME_MAX_UNIQUE_QUERIES = 2000


def _require_psycopg() -> None:
    if psycopg is None:
        raise RuntimeError("Install the project with the 'database' extra") from _IMPORT_ERROR


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _configuration_hash(configuration: dict[str, Any]) -> str:
    payload = json.dumps(configuration, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _select_addresses(
    cur,
    *,
    provider_name: str,
    provider_endpoint: str,
    refresh: bool,
    max_addresses: int | None,
) -> list[tuple[Any, str]]:
    sql = """
        SELECT a.address_id, a.full_address
        FROM core.address a
        WHERE btrim(a.full_address) <> ''
    """
    params: list[Any] = []
    if not refresh:
        sql += """
          AND NOT EXISTS (
              SELECT 1
              FROM geo.address_geocode_result g
              WHERE g.address_id = a.address_id
                AND g.provider_name = %s
                AND g.provider_endpoint = %s
                AND upper_inf(g.system_period)
                AND g.match_status_code IN ('accepted','candidate','not_found')
          )
        """
        params.extend([provider_name, provider_endpoint])
    sql += " ORDER BY a.full_address, a.address_id"
    if max_addresses is not None:
        if max_addresses < 1:
            raise ValueError("max_addresses must be >= 1")
        sql += " LIMIT %s"
        params.append(max_addresses)
    cur.execute(sql, params)
    return [(row[0], str(row[1])) for row in cur.fetchall()]


def _create_activity(cur, configuration_hash: str) -> Any:
    now = _utc_now()
    cur.execute(
        """
        INSERT INTO provenance.processing_activity(
            activity_type_code, software_name, software_version,
            configuration_hash, started_at
        ) VALUES ('geocode', %s, %s, %s, %s)
        RETURNING processing_activity_id
        """,
        (SOFTWARE_NAME, SOFTWARE_VERSION, configuration_hash, now),
    )
    row = cur.fetchone()
    if row is None:
        raise RuntimeError("Failed to create geocoding processing activity")
    return row[0]


def _complete_activity(cur, activity_id: Any) -> None:
    cur.execute(
        """
        UPDATE provenance.processing_activity
        SET completed_at = %s
        WHERE processing_activity_id = %s
        """,
        (_utc_now(), activity_id),
    )


def _close_current_results(cur, address_id: Any, provider_name: str, endpoint: str) -> None:
    cur.execute(
        """
        UPDATE geo.address_geocode_result
        SET system_period = tstzrange(lower(system_period), CURRENT_TIMESTAMP, '[)')
        WHERE address_id = %s
          AND provider_name = %s
          AND provider_endpoint = %s
          AND upper_inf(system_period)
        """,
        (address_id, provider_name, endpoint),
    )


def _insert_candidate(
    cur,
    *,
    address_id: Any,
    query: str,
    candidate: GeocodeCandidate,
    match_status: str,
    provider_name: str,
    endpoint: str,
    provider_version: str | None,
    provider_data_updated: datetime | None,
    activity_id: Any,
) -> None:
    cur.execute(
        """
        INSERT INTO geo.address_geocode_result(
            address_id,
            provider_name,
            provider_endpoint,
            provider_version,
            provider_data_updated,
            provider_result_id,
            candidate_rank,
            match_status_code,
            precision_code,
            latitude,
            longitude,
            confidence,
            query_text,
            matched_address,
            normalised_street_name,
            normalised_house_number,
            normalised_postal_code,
            normalised_locality,
            normalised_admin_unit_l2,
            normalised_admin_unit_l1,
            normalised_country_name,
            normalised_country_code,
            provider_attribution,
            provider_licence,
            provider_payload,
            processing_activity_id
        ) VALUES (
            %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL,
            %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s
        )
        """,
        (
            address_id,
            provider_name,
            endpoint,
            provider_version,
            provider_data_updated,
            candidate.provider_result_id,
            candidate.candidate_rank,
            match_status,
            candidate.precision_code,
            candidate.latitude,
            candidate.longitude,
            query,
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


def _insert_terminal_result(
    cur,
    *,
    address_id: Any,
    query: str,
    match_status: str,
    provider_name: str,
    endpoint: str,
    provider_version: str | None,
    provider_data_updated: datetime | None,
    payload: dict[str, Any] | None,
    activity_id: Any,
) -> None:
    cur.execute(
        """
        INSERT INTO geo.address_geocode_result(
            address_id,
            provider_name,
            provider_endpoint,
            provider_version,
            provider_data_updated,
            candidate_rank,
            match_status_code,
            query_text,
            provider_payload,
            processing_activity_id
        ) VALUES (%s,%s,%s,%s,%s,1,%s,%s,%s::jsonb,%s)
        """,
        (
            address_id,
            provider_name,
            endpoint,
            provider_version,
            provider_data_updated,
            match_status,
            query,
            json.dumps(payload or {}, ensure_ascii=False),
            activity_id,
        ),
    )


def normalise_addresses(
    *,
    dsn: str,
    endpoint: str,
    allow_public_nominatim: bool = False,
    min_interval_seconds: float = 0.0,
    search_limit: int = 3,
    language: str = "it",
    countrycodes: str | None = None,
    max_addresses: int | None = None,
    refresh: bool = False,
    auto_accept_unique_address_level: bool = False,
) -> dict[str, Any]:
    """Normalise canonical addresses through a configurable Nominatim-compatible endpoint.

    Existing successful/current results for the same endpoint are a persistent
    cache unless ``refresh`` is requested. Multiple address IDs sharing the same
    exact query are deduplicated within each run. Source text is sent unchanged
    to the provider; preprocessing is intentionally not part of this baseline.

    Provider results remain candidates by default. Optional auto-acceptance is
    deliberately an explicit policy choice rather than normalisation behaviour.
    """
    _require_psycopg()
    endpoint = endpoint.strip().rstrip("/")
    client = NominatimClient(
        endpoint,
        allow_public_service=allow_public_nominatim,
        min_interval_seconds=min_interval_seconds,
    )
    status = client.status()
    configuration = {
        "provider": status.provider_name,
        "endpoint": status.endpoint,
        "search_limit": search_limit,
        "language": language,
        "countrycodes": countrycodes,
        "auto_accept_unique_address_level": auto_accept_unique_address_level,
        "query_preprocessing": "none",
    }
    config_hash = _configuration_hash(configuration)

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            selected = _select_addresses(
                cur,
                provider_name=status.provider_name,
                provider_endpoint=status.endpoint,
                refresh=refresh,
                max_addresses=max_addresses,
            )
            by_query: dict[str, list[Any]] = defaultdict(list)
            for address_id, full_address in selected:
                by_query[full_address.strip()].append(address_id)

            if client.is_public_osmf_service and len(by_query) > PUBLIC_ONE_TIME_MAX_UNIQUE_QUERIES:
                raise RuntimeError(
                    "Refusing a public OSMF Nominatim batch larger than "
                    f"{PUBLIC_ONE_TIME_MAX_UNIQUE_QUERIES} unique queries. "
                    "Configure a managed or self-hosted Nominatim-compatible endpoint instead."
                )

            activity_id = _create_activity(cur, config_hash)
            counts = {
                "selected_address_ids": len(selected),
                "unique_queries": len(by_query),
                "network_queries": 0,
                "accepted": 0,
                "candidate": 0,
                "not_found": 0,
                "error": 0,
            }

            for query, address_ids in by_query.items():
                counts["network_queries"] += 1
                try:
                    candidates = client.search(
                        query,
                        limit=search_limit,
                        language=language,
                        countrycodes=countrycodes,
                    )
                except Exception as exc:  # noqa: BLE001 - provider failure must be recorded, not hidden
                    error_payload = {
                        "error_type": type(exc).__name__,
                        "message": str(exc),
                    }
                    for address_id in address_ids:
                        _insert_terminal_result(
                            cur,
                            address_id=address_id,
                            query=query,
                            match_status="error",
                            provider_name=status.provider_name,
                            endpoint=status.endpoint,
                            provider_version=status.software_version,
                            provider_data_updated=status.data_updated,
                            payload=error_payload,
                            activity_id=activity_id,
                        )
                        counts["error"] += 1
                    continue

                auto_accept = bool(
                    auto_accept_unique_address_level
                    and len(candidates) == 1
                    and candidates[0].is_address_level
                    and candidates[0].latitude is not None
                    and candidates[0].longitude is not None
                )

                for address_id in address_ids:
                    _close_current_results(
                        cur,
                        address_id,
                        status.provider_name,
                        status.endpoint,
                    )
                    if not candidates:
                        _insert_terminal_result(
                            cur,
                            address_id=address_id,
                            query=query,
                            match_status="not_found",
                            provider_name=status.provider_name,
                            endpoint=status.endpoint,
                            provider_version=status.software_version,
                            provider_data_updated=status.data_updated,
                            payload={"features": []},
                            activity_id=activity_id,
                        )
                        counts["not_found"] += 1
                        continue

                    for candidate in candidates:
                        match_status = (
                            "accepted"
                            if auto_accept and candidate.candidate_rank == 1
                            else "candidate"
                        )
                        _insert_candidate(
                            cur,
                            address_id=address_id,
                            query=query,
                            candidate=candidate,
                            match_status=match_status,
                            provider_name=status.provider_name,
                            endpoint=status.endpoint,
                            provider_version=status.software_version,
                            provider_data_updated=status.data_updated,
                            activity_id=activity_id,
                        )
                        counts[match_status] += 1

            _complete_activity(cur, activity_id)

    return {
        "provider": status.provider_name,
        "endpoint": status.endpoint,
        "provider_version": status.software_version,
        "provider_data_updated": status.data_updated.isoformat() if status.data_updated else None,
        "configuration_hash": config_hash,
        "public_osmf_service": client.is_public_osmf_service,
        "auto_accept_unique_address_level": auto_accept_unique_address_level,
        "cache_policy": "skip current accepted/candidate/not_found results unless --refresh",
        **counts,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Normalise canonical addresses using a configurable Nominatim-compatible geocoder."
    )
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument(
        "--allow-public-nominatim",
        action="store_true",
        help=(
            "Explicitly permit nominatim.openstreetmap.org for a deliberate, policy-compliant "
            "small one-time batch. Do not use this flag in recurring production workflows."
        ),
    )
    parser.add_argument("--min-interval-seconds", type=float, default=0.0)
    parser.add_argument("--search-limit", type=int, default=3)
    parser.add_argument("--language", default="it")
    parser.add_argument("--countrycodes")
    parser.add_argument("--max-addresses", type=int)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument(
        "--auto-accept-unique-address-level",
        action="store_true",
        help=(
            "Opt in to accepting a single address-level candidate with house number and coordinates. "
            "Without this flag, all provider matches remain candidates."
        ),
    )
    args = parser.parse_args()
    result = normalise_addresses(
        dsn=args.dsn,
        endpoint=args.endpoint,
        allow_public_nominatim=args.allow_public_nominatim,
        min_interval_seconds=args.min_interval_seconds,
        search_limit=args.search_limit,
        language=args.language,
        countrycodes=args.countrycodes,
        max_addresses=args.max_addresses,
        refresh=args.refresh,
        auto_accept_unique_address_level=args.auto_accept_unique_address_level,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
