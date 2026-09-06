CREATE TABLE provenance.processing_activity (
    processing_activity_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    activity_type_code     text NOT NULL REFERENCES registry.activity_type(code),
    software_name          text NULL,
    software_version       text NULL,
    configuration_hash     text NULL,
    started_at             timestamptz NOT NULL,
    completed_at           timestamptz NULL,
    CONSTRAINT processing_activity_time_order CHECK (completed_at IS NULL OR started_at <= completed_at)
);
