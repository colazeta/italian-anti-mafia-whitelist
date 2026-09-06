-- Resolution decisions are run-scoped: later resolver versions must coexist with
-- earlier decisions rather than overwrite them.
ALTER TABLE semantic.entity_projection_resolution
    DROP CONSTRAINT entity_projection_resolution_pkey;
ALTER TABLE semantic.entity_projection_resolution
    ADD COLUMN entity_projection_resolution_id uuid NOT NULL DEFAULT gen_random_uuid();
ALTER TABLE semantic.entity_projection_resolution
    ADD PRIMARY KEY (entity_projection_resolution_id);
ALTER TABLE semantic.entity_projection_resolution
    ADD CONSTRAINT entity_projection_resolution_run_unique
    UNIQUE (entity_observation_id, canonicalisation_run_id);
CREATE INDEX entity_projection_resolution_observation_idx
    ON semantic.entity_projection_resolution(entity_observation_id);
