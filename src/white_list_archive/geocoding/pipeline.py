from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from .models import GeocodeCandidate
from .nominatim import NominatimClient, query_variants

try:
    import psycopg
except ImportError as exc:  # pragma: no cover - exercised only without database extra
    psycopg = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

SOFTWARE_NAME = "white_list_archive.geocoding.pipeline"
SOFTWARE_VERSION = "1"
PUBLIC_ONE_TIME_MAX_NETWORK_REQUESTS = 2000


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
    auto_accept_unique_address_level: bool = True,
) -> dict[str, Any]:
    """Normalise canonical addresses through a configurable Nominatim-compatible endpoint.

    Existing successful/current results for the same endpoint are a persistent
    cache unless ``refresh`` is requested. Multiple address IDs sharing the same
    exact source address are deduplicated within each run. When a raw source
    string yields no result, one lightweight syntactic variant may be attempted;
    this fallback never parses or rewrites the canonical address.
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
        "query_fallback": "raw_then_light_syntactic_cleanup",
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
            by_source_query: dict[str, list[Any]] = defaultdict(list)
            for address_id, full_address in selected:
                by_source_query[full_address.strip()].append(address_id)

            potential_requests = sum(
                len(query_variants(source_query)) for source_query in by_source_query
            )
            if (
                client.is_public_osmf_service
                and potential_requests > PUBLIC_ONE_TIME_MAX_NETWORK_REQUESTS
            ):
                raise RuntimeError(
                    "Refusing a public OSMF Nominatim batch that could require more than "
                    f"{PUBLIC_ONE_TIME_MAX_NETWORK_REQUESTS} network requests. "
                    "Configure a managed or self-hosted Nominatim-compatible endpoint instead."
                )

            activity_id = _create_activity(cur, config_hash)
            counts = {
                "selected_address_ids": len(selected),
                "unique_source_queries": len(by_source_query),
                "potential_network_queries": potential_requests,
                "network_queries": 0,
                "fallback_queries_used": 0,
                "accepted": 0,
                "candidate": 0,
                "not_found": 0,
                "error": 0,
            }

            for source_query, address_ids in by_source_query.items():
                attempted_queries: list[str] = []
                candidates: list[GeocodeCandidate] = []
                used_query = source_query
                provider_error: Exception | None = None

                for variant_index, query in enumerate(query_variants(source_query)):
                    attempted_queries.append(query)
                    counts["network_queries"] += 1
                    try:
                        candidates = client.search(
                            query,
                            limit=search_limit,
                            language=language,
                            countrycodes=countrycodes,
                        )
                    except Exception as exc:  # noqa: BLE001 - provider failure must be recorded
                        provider_error = exc
                        used_query = query
                        break
                    used_query = query
                    if candidates:
                        if variant_index > 0:
                            counts["fallback_queries_used"] += 1
                        break

                if provider_error is not None:
                    error_payload = {
                        "source_address": source_query,
                        "attempted_queries": attempted_queries,
                        "error_type": type(provider_error).__name__,
                        "message": str(provider_error),
                    }
                    for address_id in address_ids:
                        _insert_terminal_result(
                            cur,
                            address_id=address_id,
                            query=used_query,
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
                            query=used_query,
                            match_status="not_found",
                            provider_name=status.provider_name,
                            endpoint=status.endpoint,
                            provider_version=status.software_version,
                            provider_data_updated=status.data_updated,
                            payload={
                                "source_address": source_query,
                                "attempted_queries": attempted_queries,
                                "features": [],
                            },
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
                        payload = dict(candidate.payload)
                        payload["_normalisation"] = {
                            "source_address": source_query,
                            "attempted_queries": attempted_queries,
                            "used_query": used_query,
                        }
                        enriched_candidate = GeocodeCandidate(
                            provider_result_id=candidate.provider_result_id,
                            candidate_rank=candidate.candidate_rank,
                            matched_address=candidate.matched_address,
                            street_name=candidate.street_name,
                            house_number=candidate.house_number,
                            postal_code=candidate.postal_code,
                            locality=candidate.locality,
                            admin_unit_l2=candidate.admin_unit_l2,
                            admin_unit_l1=candidate.admin_unit_l1,
                            country_name=candidate.country_name,
                            country_code=candidate.country_code,
                            latitude=candidate.latitude,
                            longitude=candidate.longitude,
                            precision_code=candidate.precision_code,
                            attribution=candidate.attribution,
                            licence=candidate.licence,
                            payload=payload,
                        )
                        _insert_candidate(
                            cur,
                            address_id=address_id,
                            query=used_query,
                            candidate=enriched_candidate,
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
        "--no-auto-accept-unique-address-level",
        action="store_true",
        help="Keep even a single address-level candidate as candidate rather than accepted.",
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
        auto_accept_unique_address_level=not args.no_auto_accept_unique_address_level,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
