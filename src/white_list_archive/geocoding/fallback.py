from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

try:
    import psycopg
except ImportError as exc:  # pragma: no cover
    psycopg = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

from .nominatim import NominatimClient
from .pipeline import _close_current_results, _insert_candidate, _insert_terminal_result

SOFTWARE_NAME = "white_list_archive.geocoding.fallback"
SOFTWARE_VERSION = "1"


@dataclass(frozen=True)
class FallbackTarget:
    address_id: Any
    query: str
    eligibility_reason_code: str
    source_route_code: str
    source_country_code: str | None
    upstream_geocode_result_id: Any | None
    upstream_provider_version: str | None
    current_result_status: str | None
    current_candidate_count: int
    current_provider_version: str | None
    current_provider_data_updated: datetime | None

    @property
    def country_filter_code(self) -> str | None:
        if self.eligibility_reason_code == "anncsu_not_found":
            return "IT"
        if self.eligibility_reason_code == "source_foreign":
            return self.source_country_code
        return None


def _require_psycopg() -> None:
    if psycopg is None:
        raise RuntimeError("Install the project with the 'database' extra") from _IMPORT_ERROR


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _configuration_hash(value: dict[str, Any]) -> str:
    material = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _select_targets(cur, *, provider_name: str, endpoint: str) -> list[FallbackTarget]:
    cur.execute(
        """
        SELECT
            a.address_id,
            a.full_address,
            CASE
                WHEN ca.route_code = 'foreign_fallback' THEN 'source_foreign'
                WHEN ca.route_code = 'unresolved_fallback' THEN 'country_unresolved'
                ELSE 'anncsu_not_found'
            END AS eligibility_reason_code,
            ca.route_code,
            ca.source_country_code,
            ann.address_geocode_result_id,
            ann.provider_version,
            fb.result_status_code,
            COALESCE(fb.candidate_count, 0),
            fb.provider_version,
            fb.provider_data_updated
        FROM core.address a
        JOIN geo.address_country_assessment ca
          ON ca.address_id = a.address_id
         AND upper_inf(ca.system_period)
        LEFT JOIN LATERAL (
            SELECT
                g.address_geocode_result_id,
                g.provider_version
            FROM geo.address_geocode_result g
            WHERE g.address_id = a.address_id
              AND g.provider_name = 'anncsu'
              AND g.match_status_code = 'not_found'
              AND upper_inf(g.system_period)
            ORDER BY lower(g.system_period) DESC, g.address_geocode_result_id DESC
            LIMIT 1
        ) ann ON TRUE
        LEFT JOIN LATERAL (
            SELECT
                CASE
                    WHEN count(*) FILTER (WHERE g.match_status_code = 'candidate') > 0 THEN 'candidate'
                    WHEN count(*) FILTER (WHERE g.match_status_code = 'not_found') > 0 THEN 'not_found'
                    WHEN count(*) FILTER (WHERE g.match_status_code = 'error') > 0 THEN 'error'
                    ELSE NULL
                END AS result_status_code,
                count(*) FILTER (WHERE g.match_status_code = 'candidate')::integer AS candidate_count,
                g.provider_version,
                g.provider_data_updated
            FROM geo.address_geocode_result g
            WHERE g.address_id = a.address_id
              AND g.provider_name = %s
              AND g.provider_endpoint = %s
              AND g.routing_stage_code = 'fallback'
              AND upper_inf(g.system_period)
            GROUP BY g.provider_version, g.provider_data_updated
            ORDER BY max(lower(g.system_period)) DESC
            LIMIT 1
        ) fb ON TRUE
        WHERE btrim(a.full_address) <> ''
          AND (
              ca.route_code IN ('foreign_fallback','unresolved_fallback')
              OR (
                  ca.route_code = 'italian_anncsu'
                  AND ann.address_geocode_result_id IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1
                      FROM geo.address_geocode_result good
                      WHERE good.address_id = a.address_id
                        AND good.provider_name = 'anncsu'
                        AND good.match_status_code IN ('accepted','candidate')
                        AND upper_inf(good.system_period)
                  )
              )
          )
        ORDER BY a.full_address, a.address_id
        """,
        (provider_name, endpoint),
    )
    return [
        FallbackTarget(
            address_id=row[0],
            query=str(row[1]).strip(),
            eligibility_reason_code=str(row[2]),
            source_route_code=str(row[3]),
            source_country_code=str(row[4]).upper() if row[4] else None,
            upstream_geocode_result_id=row[5],
            upstream_provider_version=str(row[6]) if row[6] else None,
            current_result_status=str(row[7]) if row[7] else None,
            current_candidate_count=int(row[8] or 0),
            current_provider_version=str(row[9]) if row[9] else None,
            current_provider_data_updated=row[10],
        )
        for row in cur.fetchall()
    ]


def _same_identity(target: FallbackTarget, *, provider_version: str | None, provider_data_updated: datetime | None) -> bool:
    return (
        target.current_provider_version == provider_version
        and target.current_provider_data_updated == provider_data_updated
    )


def _create_run(
    cur,
    *,
    configuration_hash: str,
    provider_name: str,
    endpoint: str,
    provider_version: str | None,
    provider_data_updated: datetime | None,
    eligible_address_count: int,
    selected_address_count: int,
) -> tuple[Any, Any]:
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
    activity_id = cur.fetchone()[0]
    cur.execute(
        """
        INSERT INTO geo.fallback_geocode_run(
            processing_activity_id, provider_name, provider_endpoint,
            provider_version, provider_data_updated, configuration_hash,
            eligible_address_count, selected_address_count, status_code, started_at
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'running',%s)
        RETURNING fallback_geocode_run_id
        """,
        (
            activity_id,
            provider_name,
            endpoint,
            provider_version,
            provider_data_updated,
            configuration_hash,
            eligible_address_count,
            selected_address_count,
            now,
        ),
    )
    return cur.fetchone()[0], activity_id


def _record_item(
    cur,
    *,
    run_id: Any,
    target: FallbackTarget,
    cache_disposition_code: str,
    result_status_code: str | None,
    candidate_count: int,
) -> None:
    cur.execute(
        """
        INSERT INTO geo.fallback_geocode_run_item(
            fallback_geocode_run_id, address_id, eligibility_reason_code,
            source_route_code, source_country_code, country_filter_code,
            upstream_geocode_result_id, upstream_provider_version,
            cache_disposition_code, result_status_code, candidate_count, query_text
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            run_id,
            target.address_id,
            target.eligibility_reason_code,
            target.source_route_code,
            target.source_country_code,
            target.country_filter_code,
            target.upstream_geocode_result_id,
            target.upstream_provider_version,
            cache_disposition_code,
            result_status_code,
            candidate_count,
            target.query,
        ),
    )


def _finish_run(
    cur,
    *,
    run_id: Any,
    activity_id: Any,
    counts: dict[str, int],
    status_code: str,
    error_text: str | None = None,
) -> None:
    now = _utc_now()
    cur.execute(
        """
        UPDATE geo.fallback_geocode_run
        SET reused_current_count=%s,
            network_query_count=%s,
            candidate_address_count=%s,
            candidate_row_count=%s,
            not_found_count=%s,
            error_count=%s,
            status_code=%s,
            completed_at=%s,
            error_text=%s
        WHERE fallback_geocode_run_id=%s
        """,
        (
            counts["reused_current_count"],
            counts["network_query_count"],
            counts["candidate_address_count"],
            counts["candidate_row_count"],
            counts["not_found_count"],
            counts["error_count"],
            status_code,
            now,
            error_text,
            run_id,
        ),
    )
    cur.execute(
        "UPDATE provenance.processing_activity SET completed_at=%s WHERE processing_activity_id=%s",
        (now, activity_id),
    )


def fallback_geocode(
    *,
    dsn: str,
    endpoint: str,
    min_interval_seconds: float = 0.0,
    search_limit: int = 3,
    language: str = "it",
    max_addresses: int | None = None,
    refresh: bool = False,
) -> dict[str, Any]:
    """Geocode only addresses explicitly eligible for the fallback stage.

    Eligibility is limited to three auditable cases: source-explicit foreign addresses,
    country-unresolved addresses, and defensibly Italian addresses whose current ANNCSU
    result is `not_found`. The public OSMF Nominatim endpoint is rejected unconditionally.

    Successful results are always stored as `candidate`; this stage has no auto-accept
    path. Current results are reused only when provider endpoint and provider version/data
    timestamp are unchanged. A provider-version change therefore refreshes only currently
    eligible addresses, while same-version reruns generate no network traffic for cached
    candidate/not_found outcomes.
    """
    _require_psycopg()
    endpoint = endpoint.strip().rstrip("/")
    client = NominatimClient(endpoint, allow_public_service=False, min_interval_seconds=min_interval_seconds)
    if client.is_public_osmf_service:  # defensive: constructor already refuses it
        raise RuntimeError("Public OSMF Nominatim is not permitted for recurring fallback geocoding")
    status = client.status()
    if status.software_version is None and status.data_updated is None:
        raise RuntimeError(
            "Fallback provider status must expose software_version/database_version or data_updated for versioned caching"
        )
    if max_addresses is not None and max_addresses < 1:
        raise ValueError("max_addresses must be >= 1")

    configuration = {
        "software": SOFTWARE_NAME,
        "software_version": SOFTWARE_VERSION,
        "provider": status.provider_name,
        "endpoint": status.endpoint,
        "provider_version": status.software_version,
        "provider_data_updated": status.data_updated.isoformat() if status.data_updated else None,
        "search_limit": search_limit,
        "language": language,
        "selection": ["source_foreign", "country_unresolved", "anncsu_not_found"],
        "query_preprocessing": "none",
        "automatic_acceptance": False,
    }
    config_hash = _configuration_hash(configuration)

    with psycopg.connect(dsn, autocommit=True) as conn, conn.cursor() as cur:
        eligible = _select_targets(cur, provider_name=status.provider_name, endpoint=status.endpoint)
        selected = eligible[:max_addresses] if max_addresses is not None else eligible
        run_id, activity_id = _create_run(
            cur,
            configuration_hash=config_hash,
            provider_name=status.provider_name,
            endpoint=status.endpoint,
            provider_version=status.software_version,
            provider_data_updated=status.data_updated,
            eligible_address_count=len(eligible),
            selected_address_count=len(selected),
        )
        counts = {
            "reused_current_count": 0,
            "network_query_count": 0,
            "candidate_address_count": 0,
            "candidate_row_count": 0,
            "not_found_count": 0,
            "error_count": 0,
        }

        to_query: list[FallbackTarget] = []
        try:
            for target in selected:
                reusable = bool(
                    not refresh
                    and target.current_result_status in {"candidate", "not_found"}
                    and _same_identity(
                        target,
                        provider_version=status.software_version,
                        provider_data_updated=status.data_updated,
                    )
                )
                if reusable:
                    counts["reused_current_count"] += 1
                    if target.current_result_status == "candidate":
                        counts["candidate_address_count"] += 1
                        counts["candidate_row_count"] += max(1, target.current_candidate_count)
                    else:
                        counts["not_found_count"] += 1
                    _record_item(
                        cur,
                        run_id=run_id,
                        target=target,
                        cache_disposition_code="reused_current",
                        result_status_code=target.current_result_status,
                        candidate_count=target.current_candidate_count,
                    )
                else:
                    to_query.append(target)

            groups: dict[tuple[str, str | None], list[FallbackTarget]] = defaultdict(list)
            for target in to_query:
                country_filter = target.country_filter_code.lower() if target.country_filter_code else None
                groups[(target.query, country_filter)].append(target)

            for (query, country_filter), targets in groups.items():
                counts["network_query_count"] += 1
                try:
                    candidates = client.search(
                        query,
                        limit=search_limit,
                        language=language,
                        countrycodes=country_filter,
                    )
                except Exception as exc:  # provider failure remains explicit and retryable next run
                    payload = {"error_type": type(exc).__name__, "message": str(exc)}
                    for target in targets:
                        _insert_terminal_result(
                            cur,
                            address_id=target.address_id,
                            query=query,
                            match_status="error",
                            provider_name=status.provider_name,
                            endpoint=status.endpoint,
                            provider_version=status.software_version,
                            provider_data_updated=status.data_updated,
                            payload=payload,
                            activity_id=activity_id,
                            routing_stage_code="fallback",
                            routing_reason_code=target.eligibility_reason_code,
                            upstream_geocode_result_id=target.upstream_geocode_result_id,
                            fallback_geocode_run_id=run_id,
                        )
                        counts["error_count"] += 1
                        _record_item(
                            cur,
                            run_id=run_id,
                            target=target,
                            cache_disposition_code="queried",
                            result_status_code="error",
                            candidate_count=0,
                        )
                    continue

                for target in targets:
                    _close_current_results(cur, target.address_id, status.provider_name, status.endpoint)
                    if not candidates:
                        _insert_terminal_result(
                            cur,
                            address_id=target.address_id,
                            query=query,
                            match_status="not_found",
                            provider_name=status.provider_name,
                            endpoint=status.endpoint,
                            provider_version=status.software_version,
                            provider_data_updated=status.data_updated,
                            payload={"features": []},
                            activity_id=activity_id,
                            routing_stage_code="fallback",
                            routing_reason_code=target.eligibility_reason_code,
                            upstream_geocode_result_id=target.upstream_geocode_result_id,
                            fallback_geocode_run_id=run_id,
                        )
                        counts["not_found_count"] += 1
                        _record_item(
                            cur,
                            run_id=run_id,
                            target=target,
                            cache_disposition_code="queried",
                            result_status_code="not_found",
                            candidate_count=0,
                        )
                        continue

                    for candidate in candidates:
                        _insert_candidate(
                            cur,
                            address_id=target.address_id,
                            query=query,
                            candidate=candidate,
                            match_status="candidate",
                            provider_name=status.provider_name,
                            endpoint=status.endpoint,
                            provider_version=status.software_version,
                            provider_data_updated=status.data_updated,
                            activity_id=activity_id,
                            routing_stage_code="fallback",
                            routing_reason_code=target.eligibility_reason_code,
                            upstream_geocode_result_id=target.upstream_geocode_result_id,
                            fallback_geocode_run_id=run_id,
                        )
                    counts["candidate_address_count"] += 1
                    counts["candidate_row_count"] += len(candidates)
                    _record_item(
                        cur,
                        run_id=run_id,
                        target=target,
                        cache_disposition_code="queried",
                        result_status_code="candidate",
                        candidate_count=len(candidates),
                    )

            reconciled = (
                counts["candidate_address_count"]
                + counts["not_found_count"]
                + counts["error_count"]
                == len(selected)
            )
            if not reconciled:
                raise RuntimeError(f"Fallback address accounting does not reconcile: {counts} selected={len(selected)}")
            _finish_run(
                cur,
                run_id=run_id,
                activity_id=activity_id,
                counts=counts,
                status_code="succeeded",
            )
        except Exception as exc:
            _finish_run(
                cur,
                run_id=run_id,
                activity_id=activity_id,
                counts=counts,
                status_code="failed",
                error_text=str(exc),
            )
            raise

    return {
        "software": SOFTWARE_NAME,
        "software_version": SOFTWARE_VERSION,
        "fallback_geocode_run_id": str(run_id),
        "provider": status.provider_name,
        "endpoint": status.endpoint,
        "provider_version": status.software_version,
        "provider_data_updated": status.data_updated.isoformat() if status.data_updated else None,
        "configuration_hash": config_hash,
        "eligible_address_count": len(eligible),
        "selected_address_count": len(selected),
        "queried_address_count": len(selected) - counts["reused_current_count"],
        "public_osmf_service": False,
        "automatic_acceptance": False,
        "cache_policy": "reuse same-version current fallback candidate/not_found; refresh new/changed/error cases",
        "all_selected_addresses_accounted_for": True,
        **counts,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run managed/self-hosted Nominatim-compatible fallback geocoding only for "
            "source-foreign, country-unresolved and ANNCSU-not-found canonical addresses."
        )
    )
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--min-interval-seconds", type=float, default=0.0)
    parser.add_argument("--search-limit", type=int, default=3)
    parser.add_argument("--language", default="it")
    parser.add_argument("--max-addresses", type=int)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    result = fallback_geocode(
        dsn=args.dsn,
        endpoint=args.endpoint,
        min_interval_seconds=args.min_interval_seconds,
        search_limit=args.search_limit,
        language=args.language,
        max_addresses=args.max_addresses,
        refresh=args.refresh,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
