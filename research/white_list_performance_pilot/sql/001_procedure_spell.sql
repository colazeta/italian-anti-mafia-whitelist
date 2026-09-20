-- EXPERIMENTAL RESEARCH ONLY. NOT INCLUDED BY db/apply.sql.
--
-- The original v0.1 view is preserved in Git history at ca02d710210831e8e1a3fde112de7927cdffff60.
-- It has not been deployed by the research runner and must not be executed as an
-- administrative-performance view. Methodological review found three gaps:
--   1. a published pending -> listed transition is not necessarily an
--      administrative decision interval (the pending publication may be stale);
--   2. ordered application/listing dates need same-procedure evidence;
--   3. completed -> pending or withdrawal histories require episode review.
--
-- Fail closed rather than silently leaving a statistically unsafe executable
-- recipe available. No DROP or canonical mutation is performed here.
--
-- Use scripts/run_followup.py for the executable source-observation diagnostic,
-- which keeps true processing time, clearance and total backlog rates NULL.
-- See METHODOLOGICAL_REVIEW.md for the evidence gates required for a future
-- procedure-spell SQL implementation. Source/canonical data remain unchanged.

DO $$
BEGIN
    RAISE EXCEPTION 'Research v0.1 procedure-spell view retired: administrative date/episode evidence is not validated. Use research source diagnostics; see METHODOLOGICAL_REVIEW.md.';
END;
$$;
