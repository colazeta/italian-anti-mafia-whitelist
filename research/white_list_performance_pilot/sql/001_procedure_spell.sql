-- EXPERIMENTAL RESEARCH ONLY.
-- This file is not referenced by db/apply.sql and must not be promoted implicitly.
--
-- Purpose: one analytical row per canonical White List procedure, preserving
-- proxy dates and censoring instead of inventing exact administrative dates.

CREATE SCHEMA IF NOT EXISTS research_perf;

CREATE OR REPLACE VIEW research_perf.whitelist_procedure_spell_v1 AS
WITH versions AS (
    SELECT
        p.procedure_id,
        p.relationship_id,
        rel.legal_entity_id,
        reg.register_id,
        reg.register_code,
        auth.public_authority_id,
        auth.preferred_name AS authority_name,
        pv.procedure_version_id,
        pv.procedure_type_code,
        pv.application_date,
        pv.decision_date,
        pv.procedure_status_code,
        pv.procedure_outcome_code,
        lower(pv.observation_period)::date AS observation_date,
        lower(pv.system_period) AS system_from
    FROM whitelist.white_list_procedure p
    JOIN whitelist.white_list_relationship rel
      ON rel.relationship_id = p.relationship_id
    JOIN whitelist.white_list_register reg
      ON reg.register_id = rel.register_id
    JOIN core.public_authority auth
      ON auth.public_authority_id = reg.public_authority_id
    JOIN whitelist.procedure_version pv
      ON pv.procedure_id = p.procedure_id
    WHERE upper_inf(pv.system_period)
),
summarised AS (
    SELECT
        procedure_id,
        relationship_id,
        legal_entity_id,
        register_id,
        register_code,
        public_authority_id,
        authority_name,
        min(application_date) AS application_date,
        count(DISTINCT application_date) FILTER (WHERE application_date IS NOT NULL)
            AS distinct_application_dates,
        (array_agg(procedure_type_code ORDER BY observation_date DESC, system_from DESC))[1]
            AS procedure_type_code,
        min(decision_date) FILTER (WHERE decision_date IS NOT NULL) AS min_decision_date,
        max(decision_date) FILTER (WHERE decision_date IS NOT NULL) AS max_decision_date,
        count(DISTINCT decision_date) FILTER (WHERE decision_date IS NOT NULL)
            AS distinct_decision_dates,
        min(observation_date) FILTER (
            WHERE procedure_status_code = 'completed'
        ) AS first_completed_observation_date,
        max(observation_date) FILTER (
            WHERE procedure_status_code IN ('submitted','pending','under_investigation')
        ) AS last_open_observation_date,
        max(observation_date) AS last_observation_date,
        (array_agg(procedure_status_code ORDER BY observation_date DESC, system_from DESC))[1]
            AS last_observed_status,
        (array_agg(procedure_outcome_code ORDER BY observation_date DESC, system_from DESC))[1]
            AS last_observed_outcome,
        count(*) AS procedure_version_count
    FROM versions
    GROUP BY
        procedure_id,
        relationship_id,
        legal_entity_id,
        register_id,
        register_code,
        public_authority_id,
        authority_name
),
classified AS (
    SELECT
        *,
        CASE
            WHEN distinct_application_dates > 1 THEN 'conflicting_application_dates'
            WHEN distinct_decision_dates > 1 THEN 'conflicting_decision_dates'
            WHEN min_decision_date IS NOT NULL
                 AND application_date IS NOT NULL
                 AND min_decision_date >= application_date
                THEN 'source_listing_date_proxy'
            WHEN first_completed_observation_date IS NOT NULL
                 AND last_open_observation_date IS NOT NULL
                 AND last_open_observation_date < first_completed_observation_date
                THEN 'interval_censored'
            WHEN last_observed_status IN ('submitted','pending','under_investigation')
                THEN 'right_censored'
            ELSE 'unknown'
        END AS decision_time_class
    FROM summarised
)
SELECT
    procedure_id,
    relationship_id,
    legal_entity_id,
    register_id,
    register_code,
    public_authority_id,
    authority_name,
    procedure_type_code,
    application_date,
    last_observed_status,
    last_observed_outcome,
    decision_time_class,
    CASE
        WHEN decision_time_class = 'source_listing_date_proxy'
            THEN min_decision_date
        ELSE NULL
    END AS decision_date_proxy,
    CASE
        WHEN decision_time_class = 'interval_censored'
            THEN last_open_observation_date
        ELSE NULL
    END AS decision_lower_bound,
    CASE
        WHEN decision_time_class = 'interval_censored'
            THEN first_completed_observation_date
        ELSE NULL
    END AS decision_upper_bound,
    CASE
        WHEN decision_time_class = 'right_censored'
            THEN last_observation_date
        ELSE NULL
    END AS censor_date,
    CASE
        WHEN decision_time_class = 'source_listing_date_proxy'
             AND application_date IS NOT NULL
            THEN min_decision_date - application_date
        ELSE NULL
    END AS processing_days_proxy,
    CASE
        WHEN decision_time_class = 'interval_censored'
             AND application_date IS NOT NULL
            THEN last_open_observation_date - application_date
        ELSE NULL
    END AS processing_days_lower_bound,
    CASE
        WHEN decision_time_class = 'interval_censored'
             AND application_date IS NOT NULL
            THEN first_completed_observation_date - application_date
        ELSE NULL
    END AS processing_days_upper_bound,
    CASE
        WHEN decision_time_class = 'right_censored'
             AND application_date IS NOT NULL
            THEN last_observation_date - application_date
        ELSE NULL
    END AS age_at_censor_days,
    distinct_application_dates,
    distinct_decision_dates,
    procedure_version_count,
    last_observation_date
FROM classified;

COMMENT ON VIEW research_perf.whitelist_procedure_spell_v1 IS
'Experimental research view. Canonical decision_date is conservatively labelled source_listing_date_proxy under the current Cosenza projector; observation transitions remain interval/right censored rather than being converted into exact administrative decisions.';
