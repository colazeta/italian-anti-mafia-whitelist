-- EXPERIMENTAL RESEARCH ONLY.
-- These checks are intended to fail closed before aggregate performance metrics
-- are produced from research_perf.whitelist_procedure_spell_v1.

-- Q1: impossible or conflicting chronology must be zero.
SELECT *
FROM research_perf.whitelist_procedure_spell_v1
WHERE application_date IS NOT NULL
  AND (
      (decision_date_proxy IS NOT NULL AND decision_date_proxy < application_date)
      OR (decision_lower_bound IS NOT NULL AND decision_lower_bound < application_date)
      OR (decision_upper_bound IS NOT NULL AND decision_upper_bound < application_date)
      OR distinct_application_dates > 1
      OR distinct_decision_dates > 1
  );

-- Q2: interval-censored procedures require an ordered interval.
SELECT *
FROM research_perf.whitelist_procedure_spell_v1
WHERE decision_time_class = 'interval_censored'
  AND (
      decision_lower_bound IS NULL
      OR decision_upper_bound IS NULL
      OR decision_lower_bound >= decision_upper_bound
  );

-- Q3: right-censored procedures require a censor date and no decision proxy.
SELECT *
FROM research_perf.whitelist_procedure_spell_v1
WHERE decision_time_class = 'right_censored'
  AND (
      censor_date IS NULL
      OR decision_date_proxy IS NOT NULL
  );

-- Q4: no unknown decision-time class may silently contribute an exact duration.
SELECT *
FROM research_perf.whitelist_procedure_spell_v1
WHERE decision_time_class IN (
        'unknown',
        'conflicting_application_dates',
        'conflicting_decision_dates'
      )
  AND (
      processing_days_proxy IS NOT NULL
      OR processing_days_lower_bound IS NOT NULL
      OR processing_days_upper_bound IS NOT NULL
  );

-- Q5: descriptive QA distribution by authority.
SELECT
    authority_name,
    decision_time_class,
    count(*) AS procedures
FROM research_perf.whitelist_procedure_spell_v1
GROUP BY authority_name, decision_time_class
ORDER BY authority_name, decision_time_class;
