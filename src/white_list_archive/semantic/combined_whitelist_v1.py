from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any

PROJECTOR_CODE = "prefecture-combined-whitelist-v1"
PROJECTOR_VERSION = "2"
RECORD_CONTRACT_CODE = "prefecture-combined-whitelist-v1"
PROJECTOR_CONFIGURATION = (
    "Project a parsed combined Prefecture White List record into typed semantic "
    "entity, identifier, establishment, relationship, procedure and requested-sector "
    "observations. Source values remain authoritative evidence; canonicalisation is a "
    "separate guarded activity. A source listing date is associated with a procedure "
    "decision only when it is not earlier than that procedure's application date."
)
PROJECTOR_CONFIGURATION_HASH = hashlib.sha256(PROJECTOR_CONFIGURATION.encode()).hexdigest()

REQUIRED_FIELDS = {
    "ragione_sociale",
    "sede_legale",
    "sede_secondaria",
    "codice_fiscale_partita_iva",
    "attivita_richiesta_iscrizione",
    "data_presentazione_istanza",
    "esito",
}

ACTIVITY_ALIASES: dict[str, tuple[str, ...]] = {
    "WL-ACT-INERT-MATERIALS": ("estrazione, fornitura e trasporto di terra e materiali inerti",),
    "WL-ACT-CONCRETE-BITUMEN": ("confezionamento, fornitura e trasporto di calcestruzzo e di bitume",),
    "WL-ACT-COLD-MACHINERY-RENTAL": ("noli a freddo macchinari", "noli a freddo di macchinari"),
    "WL-ACT-WORKED-IRON": ("fornitura di ferro lavorato",),
    "WL-ACT-HOT-RENTAL": ("noli a caldo",),
    "WL-ACT-THIRD-PARTY-HAULAGE": ("autotrasporto per conto terzi", "autotrasporti per conto di terzi"),
    "WL-ACT-CONSTRUCTION-SITE-GUARDING": ("guardiania ai cantieri", "guardiania dei cantieri"),
    "WL-ACT-FUNERAL-CEMETERY": ("servizi funerari e cimiteriali",),
    "WL-ACT-CATERING": ("ristorazione, gestione delle mense e catering",),
    "WL-ACT-ENVIRONMENTAL-SERVICES": ("servizi ambientali",),
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def normalise_identifier(value: str) -> str:
    return re.sub(r"\s+", "", value).upper()


def normalise_activity(value: str) -> str:
    value = value.lower().replace("…", "")
    value = re.sub(r"\s+", " ", value).strip(" .;,:\t\n")
    return value


def map_activity(value: str) -> str | None:
    normalised = normalise_activity(value)
    for concept_code, aliases in ACTIVITY_ALIASES.items():
        if any(normalised == alias or normalised.startswith(alias) for alias in aliases):
            return concept_code
    return None


def parse_source_date(value: str | None) -> date | None:
    if not value:
        return None
    value = value.strip().strip("()")
    try:
        return datetime.strptime(value, "%d/%m/%Y").date()
    except ValueError:
        return None


def _procedure_semantics(outcome: dict[str, Any]) -> tuple[str, str, str, str | None]:
    status = str(outcome.get("status") or "other_or_unknown")
    renewal = bool(outcome.get("renewal_requested") or outcome.get("update_in_progress"))
    procedure_type = "renewal" if renewal else "initial_registration"
    mention_type = "renewal" if renewal else "registration"
    if status == "listed":
        return mention_type, procedure_type, "completed", "approved"
    if status == "pending":
        return mention_type, procedure_type, "under_investigation", "unknown"
    if status in {"renewal_requested", "renewal_update_in_progress"}:
        return mention_type, procedure_type, "under_investigation", "unknown"
    if status == "rejected_or_denied":
        return mention_type, procedure_type, "completed", "rejected"
    if status == "cancellation_related":
        return mention_type, procedure_type, "completed", "cancelled"
    return mention_type, procedure_type, "unknown", "unknown"


def _ensure_projection_run(cur, parse_run_id, parse_run_code: str) -> tuple[Any, bool]:
    material = "\x1f".join(
        [parse_run_code, PROJECTOR_CODE, PROJECTOR_VERSION, PROJECTOR_CONFIGURATION_HASH]
    )
    run_code = hashlib.sha256(material.encode()).hexdigest()
    cur.execute(
        "SELECT projection_run_id FROM semantic.projection_run WHERE projection_run_code=%s",
        (run_code,),
    )
    row = cur.fetchone()
    if row:
        return row[0], False
    now = utc_now()
    cur.execute(
        """
        INSERT INTO provenance.processing_activity(
            activity_type_code, software_name, software_version,
            configuration_hash, started_at, completed_at
        ) VALUES ('semantic_project',%s,%s,%s,%s,%s)
        RETURNING processing_activity_id
        """,
        (PROJECTOR_CODE, PROJECTOR_VERSION, PROJECTOR_CONFIGURATION_HASH, now, now),
    )
    activity_id = cur.fetchone()[0]
    cur.execute(
        """
        INSERT INTO semantic.projection_run(
            parse_run_id, processing_activity_id, projection_run_code,
            projector_code, projector_version, record_contract_code, status_code
        ) VALUES (%s,%s,%s,%s,%s,%s,'succeeded')
        RETURNING projection_run_id
        """,
        (
            parse_run_id,
            activity_id,
            run_code,
            PROJECTOR_CODE,
            PROJECTOR_VERSION,
            RECORD_CONTRACT_CODE,
        ),
    )
    return cur.fetchone()[0], True


def _parse_run_contexts(cur, series_code: str) -> list[dict[str, Any]]:
    cur.execute(
        """
        SELECT DISTINCT
            run.parse_run_id, run.parse_run_code,
            e.edition_id, e.edition_code, lower(e.reference_period)::date,
            s.register_id
        FROM source.parse_run run
        JOIN provenance.processing_activity pa
          ON pa.processing_activity_id=run.processing_activity_id
        JOIN source.parsed_record pr ON pr.parse_run_id=run.parse_run_id
        JOIN source.source_schema_version sv ON sv.schema_version_id=pr.schema_version_id
        JOIN source.source_schema ss ON ss.source_schema_id=sv.source_schema_id
        JOIN source.source_series s ON s.series_id=ss.series_id
        JOIN source.source_capture cap ON cap.content_object_id=run.content_object_id
        JOIN source.capture_edition ce ON ce.capture_id=cap.capture_id
        JOIN source.source_edition e ON e.edition_id=ce.edition_id AND e.series_id=s.series_id
        WHERE s.series_code=%s
          AND run.status_code='succeeded'
          AND pa.software_name='white_list_archive.parsers.cosenza_combined_v2'
        ORDER BY lower(e.reference_period)::date
        """,
        (series_code,),
    )
    return [
        {
            "parse_run_id": row[0],
            "parse_run_code": row[1],
            "edition_id": row[2],
            "edition_code": row[3],
            "observation_date": row[4],
            "register_id": row[5],
        }
        for row in cur.fetchall()
    ]


def _record_fields(cur, parse_run_id) -> dict[Any, dict[str, Any]]:
    cur.execute(
        """
        SELECT pr.parsed_record_id, pr.record_locator, em.entity_mention_id,
               fd.normalised_source_label, sfv.source_field_value_id,
               sfv.raw_value, sfv.parsed_value_json
        FROM source.parsed_record pr
        JOIN source.entity_mention em ON em.parsed_record_id=pr.parsed_record_id
        JOIN source.source_field_value sfv ON sfv.parsed_record_id=pr.parsed_record_id
        JOIN source.source_field_definition fd ON fd.field_definition_id=sfv.field_definition_id
        WHERE pr.parse_run_id=%s
        ORDER BY pr.record_locator, fd.ordinal_position
        """,
        (parse_run_id,),
    )
    records: dict[Any, dict[str, Any]] = {}
    for parsed_record_id, locator, mention_id, label, sfv_id, raw, parsed in cur.fetchall():
        rec = records.setdefault(
            parsed_record_id,
            {"record_locator": locator, "entity_mentions": set(), "fields": {}},
        )
        rec["entity_mentions"].add(mention_id)
        rec["fields"][label] = {
            "source_field_value_id": sfv_id,
            "raw": raw or "",
            "parsed": parsed,
        }
    for rec in records.values():
        if len(rec["entity_mentions"]) != 1:
            raise ValueError(
                f"Expected one primary entity mention for parsed record {rec['record_locator']}; "
                f"found {len(rec['entity_mentions'])}"
            )
        rec["entity_mention_id"] = next(iter(rec["entity_mentions"]))
        missing = REQUIRED_FIELDS - set(rec["fields"])
        if missing:
            raise ValueError(
                f"Record {rec['record_locator']} violates {RECORD_CONTRACT_CODE}: missing {sorted(missing)}"
            )
    return records


def _sector_map(cur, register_id, observation_date: date) -> dict[str, tuple[Any, Any]]:
    cur.execute(
        """
        SELECT c.concept_code, c.sector_concept_id, sm.scheme_membership_id
        FROM whitelist.white_list_register reg
        JOIN whitelist.sector_scheme_version sv
          ON sv.regime_id=reg.regime_id AND sv.effective_period @> %s::date
        JOIN whitelist.sector_scheme_membership sm
          ON sm.scheme_version_id=sv.scheme_version_id AND sm.effective_period @> %s::date
        JOIN whitelist.sector_concept c ON c.sector_concept_id=sm.sector_concept_id
        WHERE reg.register_id=%s
        """,
        (observation_date, observation_date, register_id),
    )
    return {row[0]: (row[1], row[2]) for row in cur.fetchall()}


def _ensure_procedure_mention(
    cur, parsed_record_id, entity_mention_id, mention_type: str, material: str
):
    code = hashlib.sha256(material.encode()).hexdigest()
    cur.execute(
        "SELECT procedure_mention_id FROM source.procedure_mention WHERE procedure_mention_code=%s",
        (code,),
    )
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute(
        """
        INSERT INTO source.procedure_mention(
            parsed_record_id, entity_mention_id, mention_type_code, procedure_mention_code
        ) VALUES (%s,%s,%s,%s)
        RETURNING procedure_mention_id
        """,
        (parsed_record_id, entity_mention_id, mention_type, code),
    )
    return cur.fetchone()[0]


def _issue(cur, projection_run_id, parsed_record_id, code, severity, field, value, details=None):
    cur.execute(
        """
        INSERT INTO semantic.projection_issue(
            projection_run_id, parsed_record_id, issue_code, severity_code,
            field_name, source_value, details_json
        ) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb)
        """,
        (
            projection_run_id,
            parsed_record_id,
            code,
            severity,
            field,
            value,
            json.dumps(details, ensure_ascii=False) if details is not None else None,
        ),
    )


def project_series(conn, series_code: str) -> dict[str, int]:
    totals = defaultdict(int)
    with conn.cursor() as cur:
        contexts = _parse_run_contexts(cur, series_code)
        if not contexts:
            raise LookupError(f"No successful parser-v2 runs found for source series {series_code!r}")

        for context in contexts:
            projection_run_id, created = _ensure_projection_run(
                cur, context["parse_run_id"], context["parse_run_code"]
            )
            if not created:
                continue
            records = _record_fields(cur, context["parse_run_id"])
            sector_map = _sector_map(cur, context["register_id"], context["observation_date"])

            for parsed_record_id, record in records.items():
                fields = record["fields"]
                name = fields["ragione_sociale"]
                identifiers = fields["codice_fiscale_partita_iva"]["parsed"] or []
                strong_ids = [
                    item
                    for item in identifiers
                    if item.get("shape") in {"11_digit_numeric", "16_char_alphanumeric"}
                ]
                readiness = "ready" if strong_ids else "requires_resolution"
                cur.execute(
                    """
                    INSERT INTO semantic.entity_observation(
                        projection_run_id, entity_mention_id, parsed_record_id,
                        edition_id, observation_date, source_name_raw,
                        source_name_normalised, name_source_field_value_id,
                        resolution_readiness_code
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    RETURNING entity_observation_id
                    """,
                    (
                        projection_run_id,
                        record["entity_mention_id"],
                        parsed_record_id,
                        context["edition_id"],
                        context["observation_date"],
                        name["raw"],
                        (name["parsed"] or {}).get("normalised") or name["raw"].upper(),
                        name["source_field_value_id"],
                        readiness,
                    ),
                )
                entity_observation_id = cur.fetchone()[0]
                totals["entity_observations"] += 1

                identifier_field = fields["codice_fiscale_partita_iva"]
                for item in identifiers:
                    raw_identifier = str(item.get("raw_value") or "").strip()
                    if not raw_identifier:
                        continue
                    cur.execute(
                        """
                        INSERT INTO semantic.identifier_observation(
                            entity_observation_id, source_field_value_id, raw_value,
                            normalised_value, shape_code, scheme_assertion_code,
                            candidate_schemes_json, source_hint
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s)
                        """,
                        (
                            entity_observation_id,
                            identifier_field["source_field_value_id"],
                            raw_identifier,
                            normalise_identifier(raw_identifier),
                            item.get("shape") or "unknown",
                            item.get("scheme_assertion") or "UNKNOWN",
                            json.dumps(item.get("candidate_schemes") or []),
                            item.get("source_hint"),
                        ),
                    )
                    totals["identifier_observations"] += 1
                    if item.get("shape") not in {"11_digit_numeric", "16_char_alphanumeric"}:
                        _issue(
                            cur,
                            projection_run_id,
                            parsed_record_id,
                            "IDENTIFIER_UNEXPECTED_SHAPE",
                            "warning",
                            "codice_fiscale_partita_iva",
                            raw_identifier,
                            item,
                        )
                        totals["issues"] += 1

                for label, establishment_type in (
                    ("sede_legale", "registered_office"),
                    ("sede_secondaria", "secondary_establishment"),
                ):
                    field = fields[label]
                    if field["raw"].strip():
                        cur.execute(
                            """
                            INSERT INTO semantic.establishment_observation(
                                entity_observation_id, source_field_value_id,
                                establishment_type_code, full_address_raw
                            ) VALUES (%s,%s,%s,%s)
                            """,
                            (
                                entity_observation_id,
                                field["source_field_value_id"],
                                establishment_type,
                                field["raw"].strip(),
                            ),
                        )
                        totals["establishment_observations"] += 1

                outcome_field = fields["esito"]
                outcome = outcome_field["parsed"] or {}
                source_status = str(outcome.get("status") or "other_or_unknown")
                listing_date = parse_source_date(outcome.get("observed_listing_date"))
                expiry_date = parse_source_date(outcome.get("observed_expiry_date"))
                cur.execute(
                    """
                    INSERT INTO semantic.relationship_observation(
                        projection_run_id, entity_observation_id, register_id,
                        outcome_source_field_value_id, source_status_code, outcome_raw,
                        observed_listing_date, observed_expiry_date,
                        renewal_requested, update_in_progress
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    RETURNING relationship_observation_id
                    """,
                    (
                        projection_run_id,
                        entity_observation_id,
                        context["register_id"],
                        outcome_field["source_field_value_id"],
                        source_status,
                        outcome_field["raw"],
                        listing_date,
                        expiry_date,
                        bool(outcome.get("renewal_requested")),
                        bool(outcome.get("update_in_progress")),
                    ),
                )
                relationship_observation_id = cur.fetchone()[0]
                totals["relationship_observations"] += 1

                mention_type, procedure_type, procedure_status, procedure_outcome = _procedure_semantics(outcome)
                application_field = fields["data_presentazione_istanza"]
                activities_field = fields["attivita_richiesta_iscrizione"]
                application_dates = application_field["parsed"] or []
                activities = activities_field["parsed"] or []

                for date_item in application_dates:
                    application_date = parse_source_date(date_item.get("date") or date_item.get("raw_value"))
                    if application_date is None:
                        _issue(
                            cur,
                            projection_run_id,
                            parsed_record_id,
                            "APPLICATION_DATE_UNPARSEABLE",
                            "warning",
                            "data_presentazione_istanza",
                            str(date_item.get("raw_value")),
                            date_item,
                        )
                        totals["issues"] += 1
                        continue
                    parenthesized = bool(date_item.get("parenthesized"))
                    observed_decision_date = None
                    if procedure_outcome == "approved" and listing_date is not None:
                        if listing_date >= application_date:
                            observed_decision_date = listing_date
                        else:
                            _issue(
                                cur,
                                projection_run_id,
                                parsed_record_id,
                                "LISTING_DATE_PRECEDES_APPLICATION_DATE",
                                "warning",
                                "esito",
                                outcome_field["raw"],
                                {
                                    "application_date": application_date.isoformat(),
                                    "observed_listing_date": listing_date.isoformat(),
                                    "interpretation": (
                                        "The listing date may refer to a prior registration/relationship state "
                                        "rather than a decision on this later application."
                                    ),
                                },
                            )
                            totals["issues"] += 1
                    material = "\x1f".join(
                        [
                            str(parsed_record_id),
                            application_date.isoformat(),
                            str(parenthesized),
                            procedure_type,
                        ]
                    )
                    procedure_mention_id = _ensure_procedure_mention(
                        cur,
                        parsed_record_id,
                        record["entity_mention_id"],
                        mention_type,
                        material,
                    )
                    cur.execute(
                        """
                        INSERT INTO semantic.procedure_observation(
                            relationship_observation_id, procedure_mention_id,
                            application_source_field_value_id, outcome_source_field_value_id,
                            application_date, parenthesized_in_source,
                            projected_procedure_type_code, projected_status_code,
                            projected_outcome_code, observed_decision_date,
                            canonicalisation_eligible
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        RETURNING procedure_observation_id
                        """,
                        (
                            relationship_observation_id,
                            procedure_mention_id,
                            application_field["source_field_value_id"],
                            outcome_field["source_field_value_id"],
                            application_date,
                            parenthesized,
                            procedure_type,
                            procedure_status,
                            procedure_outcome,
                            observed_decision_date,
                            not parenthesized,
                        ),
                    )
                    procedure_observation_id = cur.fetchone()[0]
                    totals["procedure_observations"] += 1
                    if parenthesized:
                        _issue(
                            cur,
                            projection_run_id,
                            parsed_record_id,
                            "PARENTHESIZED_APPLICATION_DATE",
                            "info",
                            "data_presentazione_istanza",
                            str(date_item.get("raw_value")),
                            {"canonicalisation_eligible": False},
                        )
                        totals["issues"] += 1

                    for activity in activities:
                        raw_activity = str(activity).strip()
                        normalised = normalise_activity(raw_activity)
                        concept_code = map_activity(raw_activity)
                        mapped = sector_map.get(concept_code) if concept_code else None
                        if mapped:
                            concept_id, membership_id = mapped
                            mapping_status, confidence = "mapped", 1.0
                        else:
                            concept_id = membership_id = None
                            mapping_status, confidence = "unmapped", 0.0
                            _issue(
                                cur,
                                projection_run_id,
                                parsed_record_id,
                                "UNMAPPED_REQUESTED_ACTIVITY",
                                "warning",
                                "attivita_richiesta_iscrizione",
                                raw_activity,
                                {"normalised": normalised},
                            )
                            totals["issues"] += 1
                        cur.execute(
                            """
                            INSERT INTO semantic.procedure_sector_observation(
                                procedure_observation_id, source_field_value_id,
                                source_activity_raw, source_activity_normalised,
                                sector_concept_id, scheme_membership_id,
                                mapping_status_code, mapping_confidence
                            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                            """,
                            (
                                procedure_observation_id,
                                activities_field["source_field_value_id"],
                                raw_activity,
                                normalised,
                                concept_id,
                                membership_id,
                                mapping_status,
                                confidence,
                            ),
                        )
                        totals["procedure_sector_observations"] += 1

            totals["projection_runs"] += 1
    return dict(totals)
