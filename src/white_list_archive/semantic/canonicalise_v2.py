from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import datetime, timezone

from white_list_archive.semantic import canonicalise as base

RESOLVER_CODE = "stable-source-identifier-v2"
RESOLVER_VERSION = "2"
RESOLVER_CONFIGURATION = (
    "Resolve an entity observation when at least one strong source identifier is "
    "non-ambiguous across the source series and the observations share the same "
    "normalised source name. An ambiguous identifier never becomes a canonical "
    "EntityIdentifier merely because another independent identifier safely resolves "
    "the entity. Malformed and ambiguity-only observations remain unresolved."
)
RESOLVER_CONFIGURATION_HASH = hashlib.sha256(RESOLVER_CONFIGURATION.encode()).hexdigest()


def _ensure_canonicalisation_run(cur, series_id, projection_codes: list[str]):
    material = "\x1f".join(
        [str(series_id), RESOLVER_CODE, RESOLVER_VERSION, RESOLVER_CONFIGURATION_HASH]
        + sorted(projection_codes)
    )
    run_code = hashlib.sha256(material.encode()).hexdigest()
    cur.execute(
        "SELECT canonicalisation_run_id, processing_activity_id "
        "FROM semantic.canonicalisation_run WHERE canonicalisation_run_code=%s",
        (run_code,),
    )
    row = cur.fetchone()
    if row:
        return row[0], row[1], False
    now = datetime.now(timezone.utc).replace(microsecond=0)
    cur.execute(
        """
        INSERT INTO provenance.processing_activity(
            activity_type_code, software_name, software_version,
            configuration_hash, started_at, completed_at
        ) VALUES ('canonicalise',%s,%s,%s,%s,%s)
        RETURNING processing_activity_id
        """,
        (RESOLVER_CODE, RESOLVER_VERSION, RESOLVER_CONFIGURATION_HASH, now, now),
    )
    activity_id = cur.fetchone()[0]
    cur.execute(
        """
        INSERT INTO semantic.canonicalisation_run(
            series_id, processing_activity_id, canonicalisation_run_code,
            resolver_code, resolver_version, status_code
        ) VALUES (%s,%s,%s,%s,%s,'succeeded')
        RETURNING canonicalisation_run_id
        """,
        (series_id, activity_id, run_code, RESOLVER_CODE, RESOLVER_VERSION),
    )
    return cur.fetchone()[0], activity_id, True


def _safe_identifier_items(items, ambiguous_values: set[str]):
    """Return identifiers eligible for canonical materialisation.

    Ambiguous values remain intact in semantic.identifier_observation. They are
    excluded only from the canonical EntityIdentifier layer. This allows a row
    containing both an ambiguous identifier and an independent safe identifier to
    resolve the entity without laundering the ambiguous value into the canonic layer.
    """
    return [
        item
        for item in items
        if item["normalised_value"] not in ambiguous_values
    ]


def canonicalise_series(conn, series_code: str) -> dict[str, int]:
    totals = defaultdict(int)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT series_id FROM source.source_series WHERE series_code=%s",
            (series_code,),
        )
        row = cur.fetchone()
        if not row:
            raise LookupError(f"Unknown source series {series_code!r}")
        series_id = row[0]
        observations, identifiers, projection_codes = base._load_observations(cur, series_code)
        if not observations:
            raise LookupError(f"No semantic observations for source series {series_code!r}")

        canonicalisation_run_id, activity_id, created = _ensure_canonicalisation_run(
            cur, series_id, projection_codes
        )
        if not created:
            cur.execute(
                """
                SELECT decision_status_code,count(*)
                FROM semantic.entity_projection_resolution
                WHERE canonicalisation_run_id=%s
                GROUP BY decision_status_code
                """,
                (canonicalisation_run_id,),
            )
            return {
                f"entity_decisions_{status}": count
                for status, count in cur.fetchall()
            }

        field_ids = base._canonical_field_ids(cur)
        schemes = base._scheme_ids(cur)
        groups, unresolved, ambiguous, strong_by_obs = base._clusters(
            observations, identifiers
        )

        relationship_for_obs = {}
        for group in groups:
            legal_entity_id, _ = base._ensure_legal_entity(
                cur, series_code, group, observations, identifiers, strong_by_obs
            )
            totals["legal_entities"] += 1
            for obs_id in group:
                obs = observations[obs_id]
                cur.execute(
                    """
                    INSERT INTO semantic.entity_projection_resolution(
                        entity_observation_id,canonicalisation_run_id,legal_entity_id,
                        decision_status_code,confidence_score,decision_reason
                    ) VALUES (%s,%s,%s,'accepted',0.9900,%s)
                    """,
                    (
                        obs_id,
                        canonicalisation_run_id,
                        legal_entity_id,
                        "At least one stable non-ambiguous source identifier plus same normalised source name",
                    ),
                )
                base._ensure_entity_resolution(
                    cur,
                    obs["entity_mention_id"],
                    legal_entity_id,
                    activity_id,
                    len(strong_by_obs[obs_id]),
                )
                base._ensure_entity_name(
                    cur, legal_entity_id, obs, activity_id, field_ids
                )
                safe_identifiers = _safe_identifier_items(
                    identifiers.get(obs_id, []), ambiguous
                )
                base._ensure_identifiers(
                    cur,
                    legal_entity_id,
                    obs,
                    safe_identifiers,
                    activity_id,
                    field_ids,
                    schemes,
                )
                base._ensure_establishments(
                    cur,
                    legal_entity_id,
                    obs_id,
                    obs["observation_date"],
                    activity_id,
                    field_ids,
                )
                relationship_id = base._ensure_relationship(
                    cur, legal_entity_id, obs["register_id"]
                )
                relationship_for_obs[obs_id] = relationship_id
                base._ensure_relationship_state(
                    cur, relationship_id, obs, activity_id, field_ids
                )
                totals["accepted_entity_observations"] += 1

        for obs_id in unresolved:
            obs = observations[obs_id]
            has_ambiguous_strong = any(
                item["shape_code"] in base.STRONG_SHAPES
                and item["normalised_value"] in ambiguous
                for item in identifiers.get(obs_id, [])
            )
            reason = (
                "Only ambiguous strong identifiers are available for automatic resolution"
                if has_ambiguous_strong
                else "No non-ambiguous strong identifier is available for automatic resolution"
            )
            cur.execute(
                """
                INSERT INTO semantic.entity_projection_resolution(
                    entity_observation_id,canonicalisation_run_id,legal_entity_id,
                    decision_status_code,confidence_score,decision_reason
                ) VALUES (%s,%s,NULL,'requires_resolution',NULL,%s)
                """,
                (obs_id, canonicalisation_run_id, reason),
            )
            totals["unresolved_entity_observations"] += 1

        procedures = base._load_eligible_procedures(cur, series_code)
        seen_procedures = set()
        seen_versions = set()
        seen_sectors = set()
        for proc_obs in procedures:
            relationship_id = relationship_for_obs.get(
                proc_obs["entity_observation_id"]
            )
            if relationship_id is None:
                continue
            procedure_id, version_id = base._ensure_procedure(
                cur, relationship_id, proc_obs, activity_id, field_ids
            )
            seen_procedures.add(procedure_id)
            seen_versions.add(version_id)
            cur.execute(
                """
                SELECT sector_concept_id
                FROM semantic.procedure_sector_observation
                WHERE procedure_observation_id=%s AND mapping_status_code='mapped'
                """,
                (proc_obs["procedure_observation_id"],),
            )
            for (sector_concept_id,) in cur.fetchall():
                cur.execute(
                    """
                    INSERT INTO whitelist.procedure_sector(
                        procedure_id,sector_concept_id
                    ) VALUES (%s,%s) ON CONFLICT DO NOTHING
                    """,
                    (procedure_id, sector_concept_id),
                )
                seen_sectors.add((procedure_id, sector_concept_id))

        totals["relationships"] = len(set(relationship_for_obs.values()))
        totals["relationship_state_versions"] = len(relationship_for_obs)
        totals["procedures"] = len(seen_procedures)
        totals["procedure_versions"] = len(seen_versions)
        totals["procedure_sectors"] = len(seen_sectors)
        totals["ambiguous_identifier_values"] = len(ambiguous)
        totals["ambiguous_identifier_values_excluded_from_canonical"] = len(ambiguous)
        totals["canonicalisation_runs"] = 1
    return dict(totals)
