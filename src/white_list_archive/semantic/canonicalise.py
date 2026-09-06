from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import datetime, time, timedelta, timezone
from typing import Any

RESOLVER_CODE = "stable-source-identifier-v1"
RESOLVER_VERSION = "1"
RESOLVER_CONFIGURATION = (
    "Automatically resolve entity observations only when at least one strong source "
    "identifier is non-ambiguous across the source series and the observations share "
    "the same normalised source name. Keep ambiguous/malformed cases unresolved. "
    "Materialise source-supported names, identifiers, establishments, register "
    "relationships, relationship states, eligible procedures and requested sectors."
)
RESOLVER_CONFIGURATION_HASH = hashlib.sha256(RESOLVER_CONFIGURATION.encode()).hexdigest()
STRONG_SHAPES = {"11_digit_numeric", "16_char_alphanumeric"}


def _day_period(value):
    start = datetime.combine(value, time.min, tzinfo=timezone.utc)
    return start, start + timedelta(days=1)


def _canonical_field_ids(cur) -> dict[str, Any]:
    cur.execute("SELECT canonical_path, canonical_field_id FROM mapping.canonical_field")
    return {row[0]: row[1] for row in cur.fetchall()}


def _ensure_evidence_item(cur, source_field_value_id):
    cur.execute(
        "SELECT evidence_item_id FROM provenance.evidence_item WHERE source_field_value_id=%s",
        (source_field_value_id,),
    )
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute(
        """
        INSERT INTO provenance.evidence_item(evidence_type_code, source_field_value_id)
        VALUES ('field_value',%s)
        RETURNING evidence_item_id
        """,
        (source_field_value_id,),
    )
    return cur.fetchone()[0]


LINK_TABLES = {
    "entity_name": ("provenance.entity_name_evidence", "entity_name_id"),
    "entity_identifier": ("provenance.entity_identifier_evidence", "entity_identifier_id"),
    "establishment": ("provenance.establishment_evidence", "establishment_id"),
    "address": ("provenance.address_evidence", "address_id"),
    "relationship_state": ("provenance.relationship_state_evidence", "relationship_state_version_id"),
    "procedure_version": ("provenance.procedure_version_evidence", "procedure_version_id"),
}


def _ensure_evidence_link(cur, kind: str, target_id, evidence_item_id, canonical_field_id=None):
    table, column = LINK_TABLES[kind]
    cur.execute(
        f"SELECT 1 FROM {table} WHERE {column}=%s AND evidence_item_id=%s "
        "AND canonical_field_id IS NOT DISTINCT FROM %s AND evidence_role_code='supports'",
        (target_id, evidence_item_id, canonical_field_id),
    )
    if cur.fetchone():
        return
    cur.execute(
        f"INSERT INTO {table}({column},canonical_field_id,evidence_item_id,evidence_role_code) "
        "VALUES (%s,%s,%s,'supports')",
        (target_id, canonical_field_id, evidence_item_id),
    )


def _ensure_canonicalisation_run(cur, series_id, projection_codes: list[str]):
    material = "\x1f".join(
        [str(series_id), RESOLVER_CODE, RESOLVER_VERSION, RESOLVER_CONFIGURATION_HASH]
        + sorted(projection_codes)
    )
    run_code = hashlib.sha256(material.encode()).hexdigest()
    cur.execute(
        "SELECT canonicalisation_run_id, processing_activity_id FROM semantic.canonicalisation_run WHERE canonicalisation_run_code=%s",
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


def _load_observations(cur, series_code: str):
    cur.execute(
        """
        SELECT eo.entity_observation_id, eo.entity_mention_id, eo.parsed_record_id,
               eo.observation_date, eo.source_name_raw, eo.source_name_normalised,
               eo.name_source_field_value_id, ro.relationship_observation_id,
               ro.register_id, ro.source_status_code, ro.outcome_source_field_value_id,
               ro.observed_listing_date, ro.observed_expiry_date,
               ro.renewal_requested, ro.update_in_progress,
               prj.projection_run_code
        FROM semantic.entity_observation eo
        JOIN semantic.projection_run prj ON prj.projection_run_id=eo.projection_run_id
        JOIN source.source_edition ed ON ed.edition_id=eo.edition_id
        JOIN source.source_series s ON s.series_id=ed.series_id
        JOIN semantic.relationship_observation ro ON ro.entity_observation_id=eo.entity_observation_id
        WHERE s.series_code=%s AND prj.status_code='succeeded'
        ORDER BY eo.observation_date, eo.entity_observation_id
        """,
        (series_code,),
    )
    observations = {}
    projection_codes = set()
    for row in cur.fetchall():
        observations[row[0]] = {
            "entity_observation_id": row[0],
            "entity_mention_id": row[1],
            "parsed_record_id": row[2],
            "observation_date": row[3],
            "source_name_raw": row[4],
            "source_name_normalised": row[5],
            "name_sfv_id": row[6],
            "relationship_observation_id": row[7],
            "register_id": row[8],
            "source_status": row[9],
            "outcome_sfv_id": row[10],
            "listing_date": row[11],
            "expiry_date": row[12],
            "renewal_requested": row[13],
            "update_in_progress": row[14],
        }
        projection_codes.add(row[15])

    cur.execute(
        """
        SELECT io.entity_observation_id, io.identifier_observation_id,
               io.source_field_value_id, io.raw_value, io.normalised_value,
               io.shape_code, io.scheme_assertion_code
        FROM semantic.identifier_observation io
        JOIN semantic.entity_observation eo USING(entity_observation_id)
        JOIN source.source_edition ed ON ed.edition_id=eo.edition_id
        JOIN source.source_series s ON s.series_id=ed.series_id
        WHERE s.series_code=%s
        """,
        (series_code,),
    )
    identifiers = defaultdict(list)
    for row in cur.fetchall():
        identifiers[row[0]].append(
            {
                "identifier_observation_id": row[1],
                "source_field_value_id": row[2],
                "raw_value": row[3],
                "normalised_value": row[4],
                "shape_code": row[5],
                "scheme_assertion_code": row[6],
            }
        )
    return observations, identifiers, sorted(projection_codes)


def _clusters(observations, identifiers):
    by_identifier = defaultdict(set)
    for obs_id, obs in observations.items():
        for identifier in identifiers.get(obs_id, []):
            if identifier["shape_code"] in STRONG_SHAPES:
                by_identifier[identifier["normalised_value"]].add(obs["source_name_normalised"])
    ambiguous = {value for value, names in by_identifier.items() if len(names) > 1}

    obs_ids = list(observations)
    parent = {obs_id: obs_id for obs_id in obs_ids}

    def find(value):
        root = value
        while parent[root] != root:
            root = parent[root]
        while parent[value] != value:
            nxt = parent[value]
            parent[value] = root
            value = nxt
        return root

    def union(left, right):
        lroot, rroot = find(left), find(right)
        if lroot != rroot:
            parent[rroot] = lroot

    strong_by_obs = {}
    index = defaultdict(list)
    for obs_id, obs in observations.items():
        strong = {
            item["normalised_value"]
            for item in identifiers.get(obs_id, [])
            if item["shape_code"] in STRONG_SHAPES
            and item["normalised_value"] not in ambiguous
        }
        strong_by_obs[obs_id] = strong
        for value in strong:
            index[(obs["source_name_normalised"], value)].append(obs_id)
    for group in index.values():
        for obs_id in group[1:]:
            union(group[0], obs_id)

    groups = defaultdict(list)
    unresolved = []
    for obs_id in obs_ids:
        if strong_by_obs[obs_id]:
            groups[find(obs_id)].append(obs_id)
        else:
            unresolved.append(obs_id)
    return list(groups.values()), unresolved, ambiguous, strong_by_obs


def _ensure_legal_entity(cur, series_code, group, observations, identifiers, strong_by_obs):
    all_strong = sorted({value for obs_id in group for value in strong_by_obs[obs_id]})
    names = sorted({observations[obs_id]["source_name_normalised"] for obs_id in group})
    material = "\x1f".join([series_code, "|".join(names), "|".join(all_strong)])
    entity_code = "WLENT-" + hashlib.sha256(material.encode()).hexdigest()[:32]
    cur.execute("SELECT legal_entity_id FROM core.legal_entity WHERE entity_code=%s", (entity_code,))
    row = cur.fetchone()
    if row:
        return row[0], entity_code
    cur.execute(
        """
        INSERT INTO core.legal_entity(entity_code,entity_class_code,registration_country)
        VALUES (%s,'unknown','IT')
        RETURNING legal_entity_id
        """,
        (entity_code,),
    )
    return cur.fetchone()[0], entity_code


def _ensure_entity_resolution(cur, mention_id, legal_entity_id, activity_id, identifier_count):
    cur.execute(
        """
        SELECT legal_entity_id FROM provenance.entity_resolution
        WHERE entity_mention_id=%s AND decision_status_code='accepted' AND upper_inf(system_period)
        """,
        (mention_id,),
    )
    row = cur.fetchone()
    if row:
        if row[0] != legal_entity_id:
            raise ValueError("Existing accepted entity resolution conflicts with deterministic resolver")
        return
    method = "multi_identifier" if identifier_count > 1 else "exact_identifier"
    cur.execute(
        """
        INSERT INTO provenance.entity_resolution(
            entity_mention_id, legal_entity_id, resolution_method_code,
            confidence_score, decision_status_code, processing_activity_id
        ) VALUES (%s,%s,%s,0.9900,'accepted',%s)
        """,
        (mention_id, legal_entity_id, method, activity_id),
    )


def _ensure_entity_name(cur, legal_entity_id, obs, activity_id, field_ids):
    start, end = _day_period(obs["observation_date"])
    cur.execute(
        """
        SELECT entity_name_id FROM core.entity_name
        WHERE legal_entity_id=%s AND name_type_code='legal_name'
          AND name=%s AND observation_period=tstzrange(%s,%s,'[)')
          AND upper_inf(system_period)
        """,
        (legal_entity_id, obs["source_name_raw"], start, end),
    )
    row = cur.fetchone()
    if row:
        entity_name_id = row[0]
    else:
        cur.execute(
            """
            INSERT INTO core.entity_name(
                legal_entity_id,name_type_code,language_code,name,normalised_name,
                effective_period,observation_period,processing_activity_id
            ) VALUES (%s,'legal_name','it',%s,%s,NULL,tstzrange(%s,%s,'[)'),%s)
            RETURNING entity_name_id
            """,
            (
                legal_entity_id,
                obs["source_name_raw"],
                obs["source_name_normalised"],
                start,
                end,
                activity_id,
            ),
        )
        entity_name_id = cur.fetchone()[0]
    evidence = _ensure_evidence_item(cur, obs["name_sfv_id"])
    _ensure_evidence_link(cur, "entity_name", entity_name_id, evidence, field_ids.get("entity_name.name"))


def _scheme_ids(cur):
    cur.execute("SELECT scheme_code,identifier_scheme_id FROM core.identifier_scheme")
    return {row[0]: row[1] for row in cur.fetchall()}


def _ensure_identifiers(cur, legal_entity_id, obs, id_items, activity_id, field_ids, schemes):
    start, end = _day_period(obs["observation_date"])
    for item in id_items:
        assertion = item["scheme_assertion_code"]
        if assertion == "IT_CF_CANDIDATE":
            scheme_code = "IT_CF"
        elif assertion == "UNRESOLVED_CF_OR_VAT":
            scheme_code = "UNRESOLVED_CF_OR_VAT"
        else:
            continue
        scheme_id = schemes[scheme_code]
        cur.execute(
            """
            SELECT entity_identifier_id FROM core.entity_identifier
            WHERE legal_entity_id=%s AND identifier_scheme_id=%s
              AND normalised_value=%s
              AND observation_period=tstzrange(%s,%s,'[)')
              AND upper_inf(system_period)
            """,
            (legal_entity_id, scheme_id, item["normalised_value"], start, end),
        )
        row = cur.fetchone()
        if row:
            identifier_id = row[0]
        else:
            cur.execute(
                """
                INSERT INTO core.entity_identifier(
                    legal_entity_id,identifier_scheme_id,identifier_value,normalised_value,
                    issuing_jurisdiction,verification_status_code,effective_period,
                    observation_period,processing_activity_id
                ) VALUES (%s,%s,%s,%s,'IT','source_asserted',NULL,tstzrange(%s,%s,'[)'),%s)
                RETURNING entity_identifier_id
                """,
                (
                    legal_entity_id,
                    scheme_id,
                    item["raw_value"],
                    item["normalised_value"],
                    start,
                    end,
                    activity_id,
                ),
            )
            identifier_id = cur.fetchone()[0]
        evidence = _ensure_evidence_item(cur, item["source_field_value_id"])
        _ensure_evidence_link(
            cur,
            "entity_identifier",
            identifier_id,
            evidence,
            field_ids.get("entity_identifier.value"),
        )


def _ensure_establishments(cur, legal_entity_id, entity_observation_id, obs_date, activity_id, field_ids):
    cur.execute(
        """
        SELECT establishment_type_code,full_address_raw,source_field_value_id
        FROM semantic.establishment_observation
        WHERE entity_observation_id=%s
        """,
        (entity_observation_id,),
    )
    start, end = _day_period(obs_date)
    for establishment_type, address_raw, sfv_id in cur.fetchall():
        cur.execute("SELECT address_id FROM core.address WHERE full_address=%s ORDER BY created_at LIMIT 1", (address_raw,))
        row = cur.fetchone()
        if row:
            address_id = row[0]
        else:
            cur.execute(
                """
                INSERT INTO core.address(full_address,country_code,processing_activity_id)
                VALUES (%s,'IT',%s) RETURNING address_id
                """,
                (address_raw, activity_id),
            )
            address_id = cur.fetchone()[0]
        evidence = _ensure_evidence_item(cur, sfv_id)
        _ensure_evidence_link(cur, "address", address_id, evidence, field_ids.get("establishment.address"))

        cur.execute(
            """
            SELECT est.establishment_id
            FROM core.establishment est
            JOIN core.establishment_address ea ON ea.establishment_id=est.establishment_id
            WHERE est.legal_entity_id=%s AND est.establishment_type_code=%s
              AND est.observation_period=tstzrange(%s,%s,'[)')
              AND ea.address_id=%s AND upper_inf(est.system_period) AND upper_inf(ea.system_period)
            """,
            (legal_entity_id, establishment_type, start, end, address_id),
        )
        row = cur.fetchone()
        if row:
            establishment_id = row[0]
        else:
            cur.execute(
                """
                INSERT INTO core.establishment(
                    legal_entity_id,establishment_type_code,competence_relevance_code,
                    effective_period,observation_period,processing_activity_id
                ) VALUES (%s,%s,'unknown',NULL,tstzrange(%s,%s,'[)'),%s)
                RETURNING establishment_id
                """,
                (legal_entity_id, establishment_type, start, end, activity_id),
            )
            establishment_id = cur.fetchone()[0]
            cur.execute(
                """
                INSERT INTO core.establishment_address(
                    establishment_id,address_id,effective_period,observation_period,processing_activity_id
                ) VALUES (%s,%s,NULL,tstzrange(%s,%s,'[)'),%s)
                """,
                (establishment_id, address_id, start, end, activity_id),
            )
        _ensure_evidence_link(
            cur,
            "establishment",
            establishment_id,
            evidence,
            field_ids.get("establishment.address"),
        )


def _ensure_relationship(cur, legal_entity_id, register_id):
    cur.execute(
        "SELECT relationship_id FROM whitelist.white_list_relationship WHERE legal_entity_id=%s AND register_id=%s",
        (legal_entity_id, register_id),
    )
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute(
        """
        INSERT INTO whitelist.white_list_relationship(legal_entity_id,register_id)
        VALUES (%s,%s) RETURNING relationship_id
        """,
        (legal_entity_id, register_id),
    )
    return cur.fetchone()[0]


def _relationship_codes(status):
    if status == "listed":
        return "registered", "effective"
    if status in {"renewal_requested", "renewal_update_in_progress"}:
        return "registered", "unknown"
    if status == "rejected_or_denied":
        return "rejected", "not_effective"
    return "unknown", "unknown"


def _ensure_relationship_state(cur, relationship_id, obs, activity_id, field_ids):
    start, end = _day_period(obs["observation_date"])
    cur.execute(
        """
        SELECT relationship_state_version_id FROM whitelist.relationship_state_version
        WHERE relationship_id=%s AND observation_period=tstzrange(%s,%s,'[)')
          AND upper_inf(system_period)
        """,
        (relationship_id, start, end),
    )
    row = cur.fetchone()
    if row:
        state_id = row[0]
    else:
        disposition, legal_effect = _relationship_codes(obs["source_status"])
        cur.execute(
            """
            INSERT INTO whitelist.relationship_state_version(
                relationship_id,administrative_disposition_code,legal_effect_status_code,
                nominal_valid_from,nominal_valid_until,effective_period,
                observation_period,processing_activity_id
            ) VALUES (%s,%s,%s,%s,%s,NULL,tstzrange(%s,%s,'[)'),%s)
            RETURNING relationship_state_version_id
            """,
            (
                relationship_id,
                disposition,
                legal_effect,
                obs["listing_date"],
                obs["expiry_date"],
                start,
                end,
                activity_id,
            ),
        )
        state_id = cur.fetchone()[0]
    evidence = _ensure_evidence_item(cur, obs["outcome_sfv_id"])
    _ensure_evidence_link(
        cur,
        "relationship_state",
        state_id,
        evidence,
        field_ids.get("relationship_state.administrative_disposition"),
    )
    if obs["listing_date"]:
        _ensure_evidence_link(
            cur,
            "relationship_state",
            state_id,
            evidence,
            field_ids.get("relationship_state.nominal_valid_from"),
        )
    if obs["expiry_date"]:
        _ensure_evidence_link(
            cur,
            "relationship_state",
            state_id,
            evidence,
            field_ids.get("relationship_state.nominal_valid_until"),
        )
    return state_id


def _ensure_procedure(cur, relationship_id, proc_obs, activity_id, field_ids):
    material = "\x1f".join(
        [str(relationship_id), proc_obs["application_date"].isoformat(), proc_obs["procedure_type"]]
    )
    procedure_code = "WLPROC-" + hashlib.sha256(material.encode()).hexdigest()[:32]
    cur.execute("SELECT procedure_id FROM whitelist.white_list_procedure WHERE procedure_code=%s", (procedure_code,))
    row = cur.fetchone()
    if row:
        procedure_id = row[0]
    else:
        cur.execute(
            """
            INSERT INTO whitelist.white_list_procedure(relationship_id,procedure_code)
            VALUES (%s,%s) RETURNING procedure_id
            """,
            (relationship_id, procedure_code),
        )
        procedure_id = cur.fetchone()[0]

    cur.execute(
        """
        SELECT procedure_id FROM provenance.procedure_resolution
        WHERE procedure_mention_id=%s AND decision_status_code='accepted' AND upper_inf(system_period)
        """,
        (proc_obs["procedure_mention_id"],),
    )
    resolution = cur.fetchone()
    if resolution:
        if resolution[0] != procedure_id:
            raise ValueError("Existing accepted procedure resolution conflicts with deterministic resolver")
    else:
        cur.execute(
            """
            INSERT INTO provenance.procedure_resolution(
                procedure_mention_id,procedure_id,resolution_method_code,
                confidence_score,decision_status_code,processing_activity_id
            ) VALUES (%s,%s,'deterministic_source_fields',0.9900,'accepted',%s)
            """,
            (proc_obs["procedure_mention_id"], procedure_id, activity_id),
        )

    start, end = _day_period(proc_obs["observation_date"])
    cur.execute(
        """
        SELECT procedure_version_id FROM whitelist.procedure_version
        WHERE procedure_id=%s AND observation_period=tstzrange(%s,%s,'[)')
          AND upper_inf(system_period)
        """,
        (procedure_id, start, end),
    )
    row = cur.fetchone()
    if row:
        version_id = row[0]
    else:
        cur.execute(
            """
            INSERT INTO whitelist.procedure_version(
                procedure_id,procedure_type_code,application_date,decision_date,
                procedure_status_code,procedure_outcome_code,effective_period,
                observation_period,processing_activity_id
            ) VALUES (%s,%s,%s,%s,%s,%s,NULL,tstzrange(%s,%s,'[)'),%s)
            RETURNING procedure_version_id
            """,
            (
                procedure_id,
                proc_obs["procedure_type"],
                proc_obs["application_date"],
                proc_obs["decision_date"],
                proc_obs["status"],
                proc_obs["outcome"],
                start,
                end,
                activity_id,
            ),
        )
        version_id = cur.fetchone()[0]
    app_evidence = _ensure_evidence_item(cur, proc_obs["application_sfv_id"])
    _ensure_evidence_link(
        cur,
        "procedure_version",
        version_id,
        app_evidence,
        field_ids.get("procedure.application_date"),
    )
    outcome_evidence = _ensure_evidence_item(cur, proc_obs["outcome_sfv_id"])
    _ensure_evidence_link(
        cur,
        "procedure_version",
        version_id,
        outcome_evidence,
        field_ids.get("procedure.status"),
    )
    return procedure_id, version_id


def _load_eligible_procedures(cur, series_code):
    cur.execute(
        """
        SELECT po.procedure_observation_id, ro.entity_observation_id,
               po.procedure_mention_id, po.application_source_field_value_id,
               po.outcome_source_field_value_id, po.application_date,
               po.projected_procedure_type_code, po.projected_status_code,
               po.projected_outcome_code, po.observed_decision_date,
               eo.observation_date
        FROM semantic.procedure_observation po
        JOIN semantic.relationship_observation ro ON ro.relationship_observation_id=po.relationship_observation_id
        JOIN semantic.entity_observation eo ON eo.entity_observation_id=ro.entity_observation_id
        JOIN source.source_edition ed ON ed.edition_id=eo.edition_id
        JOIN source.source_series s ON s.series_id=ed.series_id
        WHERE s.series_code=%s AND po.canonicalisation_eligible
        """,
        (series_code,),
    )
    return [
        {
            "procedure_observation_id": row[0],
            "entity_observation_id": row[1],
            "procedure_mention_id": row[2],
            "application_sfv_id": row[3],
            "outcome_sfv_id": row[4],
            "application_date": row[5],
            "procedure_type": row[6],
            "status": row[7],
            "outcome": row[8],
            "decision_date": row[9],
            "observation_date": row[10],
        }
        for row in cur.fetchall()
    ]


def canonicalise_series(conn, series_code: str) -> dict[str, int]:
    totals = defaultdict(int)
    with conn.cursor() as cur:
        cur.execute("SELECT series_id FROM source.source_series WHERE series_code=%s", (series_code,))
        row = cur.fetchone()
        if not row:
            raise LookupError(f"Unknown source series {series_code!r}")
        series_id = row[0]
        observations, identifiers, projection_codes = _load_observations(cur, series_code)
        if not observations:
            raise LookupError(f"No semantic observations for source series {series_code!r}")
        canonicalisation_run_id, activity_id, created = _ensure_canonicalisation_run(
            cur, series_id, projection_codes
        )
        if not created:
            cur.execute(
                """
                SELECT decision_status_code,count(*) FROM semantic.entity_projection_resolution
                WHERE canonicalisation_run_id=%s GROUP BY decision_status_code
                """,
                (canonicalisation_run_id,),
            )
            return {f"entity_decisions_{status}": count for status, count in cur.fetchall()}

        field_ids = _canonical_field_ids(cur)
        schemes = _scheme_ids(cur)
        groups, unresolved, ambiguous, strong_by_obs = _clusters(observations, identifiers)

        entity_for_obs = {}
        relationship_for_obs = {}
        for group in groups:
            legal_entity_id, _ = _ensure_legal_entity(
                cur, series_code, group, observations, identifiers, strong_by_obs
            )
            totals["legal_entities"] += 1
            for obs_id in group:
                obs = observations[obs_id]
                entity_for_obs[obs_id] = legal_entity_id
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
                        "Stable non-ambiguous source identifier and same normalised source name",
                    ),
                )
                _ensure_entity_resolution(
                    cur,
                    obs["entity_mention_id"],
                    legal_entity_id,
                    activity_id,
                    len(strong_by_obs[obs_id]),
                )
                _ensure_entity_name(cur, legal_entity_id, obs, activity_id, field_ids)
                _ensure_identifiers(
                    cur, legal_entity_id, obs, identifiers.get(obs_id, []), activity_id, field_ids, schemes
                )
                _ensure_establishments(
                    cur, legal_entity_id, obs_id, obs["observation_date"], activity_id, field_ids
                )
                relationship_id = _ensure_relationship(cur, legal_entity_id, obs["register_id"])
                relationship_for_obs[obs_id] = relationship_id
                _ensure_relationship_state(cur, relationship_id, obs, activity_id, field_ids)
                totals["accepted_entity_observations"] += 1

        for obs_id in unresolved:
            obs = observations[obs_id]
            reason = (
                "Strong identifier is ambiguous across distinct source names"
                if any(
                    item["shape_code"] in STRONG_SHAPES and item["normalised_value"] in ambiguous
                    for item in identifiers.get(obs_id, [])
                )
                else "No non-ambiguous strong identifier available for automatic resolution"
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

        procedures = _load_eligible_procedures(cur, series_code)
        seen_procedures = set()
        seen_versions = set()
        seen_sectors = set()
        for proc_obs in procedures:
            obs_id = proc_obs["entity_observation_id"]
            relationship_id = relationship_for_obs.get(obs_id)
            if relationship_id is None:
                continue
            procedure_id, version_id = _ensure_procedure(
                cur, relationship_id, proc_obs, activity_id, field_ids
            )
            seen_procedures.add(procedure_id)
            seen_versions.add(version_id)
            cur.execute(
                """
                SELECT sector_concept_id FROM semantic.procedure_sector_observation
                WHERE procedure_observation_id=%s AND mapping_status_code='mapped'
                """,
                (proc_obs["procedure_observation_id"],),
            )
            for (sector_concept_id,) in cur.fetchall():
                cur.execute(
                    """
                    INSERT INTO whitelist.procedure_sector(procedure_id,sector_concept_id)
                    VALUES (%s,%s) ON CONFLICT DO NOTHING
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
        totals["canonicalisation_runs"] = 1
    return dict(totals)
