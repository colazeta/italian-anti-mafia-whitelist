from __future__ import annotations

import argparse
import json
from pathlib import Path

import psycopg

from white_list_archive.geocoding.fallback import fallback_geocode


def _activity(cur) -> str:
    cur.execute(
        """
        INSERT INTO provenance.processing_activity(
            activity_type_code,software_name,software_version,
            configuration_hash,started_at,completed_at
        ) VALUES ('normalise','fallback-live-fixture','1',repeat('f',64),CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)
        RETURNING processing_activity_id
        """
    )
    return cur.fetchone()[0]


def _insert_address(
    cur,
    *,
    activity_id,
    full_address: str,
    route: str,
    source_country: str | None = None,
    derived_country: str | None = None,
    with_anncsu_not_found: bool = False,
):
    cur.execute(
        "INSERT INTO core.address(full_address,processing_activity_id) VALUES (%s,%s) RETURNING address_id",
        (full_address, activity_id),
    )
    address_id = cur.fetchone()[0]
    classification = "source_explicit" if source_country else (
        "derived_italian" if derived_country else "unresolved"
    )
    cur.execute(
        """
        INSERT INTO geo.address_country_assessment(
            address_id,source_country_code,derived_country_code,
            classification_status_code,route_code,derivation_reason,
            reference_scheme,reference_version,processing_activity_id
        ) VALUES (%s,%s,%s,%s,%s,'fallback-live-fixture','TEST','1',%s)
        """,
        (
            address_id, source_country, derived_country, classification, route, activity_id
        ),
    )
    upstream_id = None
    if with_anncsu_not_found:
        cur.execute(
            """
            INSERT INTO geo.address_geocode_result(
                address_id,provider_name,provider_endpoint,provider_version,
                provider_data_updated,candidate_rank,match_status_code,query_text,
                processing_activity_id
            ) VALUES (%s,'anncsu','https://anncsu.example.test','ann-v1',
                      '2026-09-09T00:00:00Z',1,'not_found',%s,%s)
            RETURNING address_geocode_result_id
            """,
            (address_id, full_address, activity_id),
        )
        upstream_id = cur.fetchone()[0]
    return address_id, upstream_id


def _seed(dsn: str) -> dict[str, str]:
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        activity_id = _activity(cur)
        values = {}
        values["calabria"], _ = _insert_address(
            cur,
            activity_id=activity_id,
            full_address="COSENZA Via Roma 1",
            route="italian_anncsu",
            derived_country="IT",
            with_anncsu_not_found=True,
        )
        values["toscana"], _ = _insert_address(
            cur,
            activity_id=activity_id,
            full_address="PISTOIA Via Cavour 2",
            route="italian_anncsu",
            derived_country="IT",
            with_anncsu_not_found=True,
        )
        values["foreign"], _ = _insert_address(
            cur,
            activity_id=activity_id,
            full_address="PARIGI (FR) Rue de Test 3",
            route="foreign_fallback",
            source_country="FR",
        )
        values["unresolved"], _ = _insert_address(
            cur,
            activity_id=activity_id,
            full_address="MYSTERY Road 4",
            route="unresolved_fallback",
        )
        conn.commit()
    return {key: str(value) for key, value in values.items()}


def _insert_new_toscana(dsn: str) -> str:
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        activity_id = _activity(cur)
        address_id, _ = _insert_address(
            cur,
            activity_id=activity_id,
            full_address="FIRENZE Via Nuova 5",
            route="italian_anncsu",
            derived_country="IT",
            with_anncsu_not_found=True,
        )
        conn.commit()
    return str(address_id)


def _make_unresolved_ineligible(dsn: str, address_id: str) -> None:
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        activity_id = _activity(cur)
        cur.execute(
            """
            UPDATE geo.address_country_assessment
            SET system_period=tstzrange(lower(system_period),CURRENT_TIMESTAMP,'[)')
            WHERE address_id=%s AND upper_inf(system_period)
            """,
            (address_id,),
        )
        cur.execute(
            """
            INSERT INTO geo.address_country_assessment(
                address_id,derived_country_code,classification_status_code,route_code,
                derivation_reason,reference_scheme,reference_version,processing_activity_id
            ) VALUES (%s,'IT','derived_italian','italian_anncsu',
                      'fallback-live-route-change','TEST','2',%s)
            """,
            (address_id, activity_id),
        )
        conn.commit()


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def _assert_run(
    run: dict,
    *,
    eligible: int,
    selected: int,
    reused: int,
    network: int,
    candidate_addresses: int,
    not_found: int,
    expired: int = 0,
) -> None:
    expected = {
        "eligible_address_count": eligible,
        "selected_address_count": selected,
        "reused_current_count": reused,
        "network_query_count": network,
        "candidate_address_count": candidate_addresses,
        "not_found_count": not_found,
        "expired_ineligible_count": expired,
    }
    for key, value in expected.items():
        if int(run[key]) != value:
            raise RuntimeError(f"{key}: expected {value}, got {run[key]} in {run}")
    if run["error_count"] != 0 or not run["all_selected_addresses_accounted_for"]:
        raise RuntimeError(f"Fallback run failed accounting/error gate: {run}")
    if run["public_osmf_service"] or run["automatic_acceptance"]:
        raise RuntimeError("Recurring fallback gate violated provider/acceptance policy")


def _validate_database(dsn: str, unresolved_id: str) -> dict:
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM geo.address_geocode_result WHERE routing_stage_code='fallback' AND match_status_code='accepted'"
        )
        accepted = int(cur.fetchone()[0])
        cur.execute(
            """
            SELECT routing_reason_code,count(DISTINCT address_id)
            FROM geo.address_geocode_result
            WHERE routing_stage_code='fallback' AND upper_inf(system_period)
            GROUP BY routing_reason_code ORDER BY routing_reason_code
            """
        )
        current_reasons = {row[0]: int(row[1]) for row in cur.fetchall()}
        cur.execute(
            """
            SELECT count(*)
            FROM geo.address_geocode_result
            WHERE address_id=%s AND routing_stage_code='fallback' AND upper_inf(system_period)
            """,
            (unresolved_id,),
        )
        stale_current = int(cur.fetchone()[0])
        cur.execute(
            """
            SELECT count(*)
            FROM geo.address_geocode_result g
            WHERE g.routing_reason_code='anncsu_not_found'
              AND upper_inf(g.system_period)
              AND g.upstream_geocode_result_id IS NOT NULL
              AND EXISTS (
                  SELECT 1 FROM geo.address_geocode_result ann
                  WHERE ann.address_geocode_result_id=g.upstream_geocode_result_id
                    AND ann.provider_name='anncsu'
                    AND ann.match_status_code='not_found'
              )
            """
        )
        upstream_linked = int(cur.fetchone()[0])
        cur.execute(
            "SELECT count(*) FROM geo.fallback_geocode_run WHERE status_code='succeeded'"
        )
        successful_runs = int(cur.fetchone()[0])
        cur.execute(
            "SELECT count(*) FROM geo.fallback_geocode_run_item"
        )
        run_items = int(cur.fetchone()[0])
    if accepted:
        raise RuntimeError("Fallback validation produced accepted geography")
    if stale_current:
        raise RuntimeError("Ineligible fallback result remained current after route change")
    if current_reasons != {"anncsu_not_found": 3, "source_foreign": 1}:
        raise RuntimeError(f"Unexpected current fallback reasons: {current_reasons}")
    if upstream_linked != 3:
        raise RuntimeError(f"ANNCSU fallback provenance did not retain 3 upstream not_found links: {upstream_linked}")
    if successful_runs != 5 or run_items != 22:
        raise RuntimeError(f"Unexpected persisted run provenance: runs={successful_runs} items={run_items}")
    return {
        "accepted": accepted,
        "current_reason_counts": current_reasons,
        "anncsu_upstream_links": upstream_linked,
        "successful_runs": successful_runs,
        "run_items": run_items,
    }


def _validate_log(path: Path) -> dict:
    events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(events) != 10:
        raise RuntimeError(f"Expected 10 actual fallback search requests, got {len(events)}")
    by_version = {}
    for event in events:
        by_version[event["provider_version"]] = by_version.get(event["provider_version"], 0) + 1
        query = event["query"].upper()
        country = event["countrycodes"]
        if query.startswith(("COSENZA", "PISTOIA", "FIRENZE")) and country != "it":
            raise RuntimeError(f"Italian ANNCSU remainder lacked IT fallback filter: {event}")
        if query.startswith("PARIGI") and country != "fr":
            raise RuntimeError(f"Foreign source address lacked FR fallback filter: {event}")
        if query.startswith("MYSTERY") and country is not None:
            raise RuntimeError(f"Country-unresolved fallback was incorrectly constrained: {event}")
    if by_version != {"mock-v1": 5, "mock-v2": 5}:
        raise RuntimeError(f"Provider-version request accounting mismatch: {by_version}")
    return {"search_requests": len(events), "searches_by_provider_version": by_version}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--version-file", type=Path, required=True)
    parser.add_argument("--request-log", type=Path, required=True)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    args = parser.parse_args()
    args.artifact_dir.mkdir(parents=True, exist_ok=True)

    ids = _seed(args.dsn)
    run1 = fallback_geocode(dsn=args.dsn, endpoint=args.endpoint)
    _assert_run(run1, eligible=4, selected=4, reused=0, network=4, candidate_addresses=3, not_found=1)
    _write(args.artifact_dir / "run-1.json", run1)

    run2 = fallback_geocode(dsn=args.dsn, endpoint=args.endpoint)
    _assert_run(run2, eligible=4, selected=4, reused=4, network=0, candidate_addresses=3, not_found=1)
    _write(args.artifact_dir / "run-2-same-version-cache.json", run2)

    ids["new_toscana"] = _insert_new_toscana(args.dsn)
    run3 = fallback_geocode(dsn=args.dsn, endpoint=args.endpoint)
    _assert_run(run3, eligible=5, selected=5, reused=4, network=1, candidate_addresses=4, not_found=1)
    _write(args.artifact_dir / "run-3-new-address-only.json", run3)

    args.version_file.write_text("mock-v2\n", encoding="utf-8")
    run4 = fallback_geocode(dsn=args.dsn, endpoint=args.endpoint)
    _assert_run(run4, eligible=5, selected=5, reused=0, network=5, candidate_addresses=4, not_found=1)
    _write(args.artifact_dir / "run-4-provider-version-refresh.json", run4)

    _make_unresolved_ineligible(args.dsn, ids["unresolved"])
    run5 = fallback_geocode(dsn=args.dsn, endpoint=args.endpoint)
    _assert_run(run5, eligible=4, selected=4, reused=4, network=0, candidate_addresses=4, not_found=0, expired=1)
    _write(args.artifact_dir / "run-5-stale-expiration.json", run5)

    db = _validate_database(args.dsn, ids["unresolved"])
    network = _validate_log(args.request_log)
    summary = {
        "status": "VERIFIED",
        "fixture": {
            "initial_addresses": 4,
            "regions_with_anncsu_remainder": ["Calabria", "Toscana"],
            "foreign_country": "FR",
            "country_unresolved": 1,
            "new_address_region": "Toscana",
        },
        "routing_reasons_tested": ["anncsu_not_found", "source_foreign", "country_unresolved"],
        "same_version_cache_reuse_verified": True,
        "new_address_incremental_refresh_verified": True,
        "provider_version_refresh_verified": True,
        "stale_fallback_expiration_verified": True,
        "public_osmf_used": False,
        "automatic_acceptance": False,
        "database": db,
        "network": network,
    }
    _write(args.artifact_dir / "verification-summary.json", summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
