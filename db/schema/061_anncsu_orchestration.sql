CREATE TABLE geo.anncsu_orchestration_run (
    anncsu_orchestration_run_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    processing_activity_id      uuid NOT NULL REFERENCES provenance.processing_activity(processing_activity_id),
    map_version                 text NOT NULL,
    plan_sha256                 text NOT NULL,
    istat_reference_version     text NOT NULL,
    istat_sha256                text NOT NULL,
    refresh_provider_inputs     boolean NOT NULL DEFAULT false,
    total_canonical_addresses   integer NOT NULL,
    italian_route_addresses     integer NOT NULL,
    assignable_addresses        integer NOT NULL,
    unassigned_addresses        integer NOT NULL,
    status_code                 text NOT NULL,
    started_at                  timestamptz NOT NULL,
    completed_at                timestamptz NULL,
    error_text                  text NULL,
    CONSTRAINT anncsu_run_map_not_blank CHECK (btrim(map_version) <> ''),
    CONSTRAINT anncsu_run_plan_hash CHECK (plan_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT anncsu_run_istat_hash CHECK (istat_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT anncsu_run_counts_nonnegative CHECK (
        total_canonical_addresses >= 0 AND italian_route_addresses >= 0
        AND assignable_addresses >= 0 AND unassigned_addresses >= 0
    ),
    CONSTRAINT anncsu_run_counts_reconcile CHECK (
        assignable_addresses + unassigned_addresses = italian_route_addresses
        AND italian_route_addresses <= total_canonical_addresses
    ),
    CONSTRAINT anncsu_run_status_allowed CHECK (status_code IN ('running','succeeded','failed')),
    CONSTRAINT anncsu_run_completion_consistent CHECK (
        (status_code='running' AND completed_at IS NULL)
        OR (status_code IN ('succeeded','failed') AND completed_at IS NOT NULL)
    )
);

CREATE INDEX anncsu_orchestration_started_idx
    ON geo.anncsu_orchestration_run (started_at DESC);

CREATE TABLE geo.anncsu_region_run (
    anncsu_region_run_id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    anncsu_orchestration_run_id   uuid NOT NULL REFERENCES geo.anncsu_orchestration_run(anncsu_orchestration_run_id) ON DELETE CASCADE,
    region_name                   text NOT NULL,
    province_plate                text NULL,
    dataset_code                  text NOT NULL,
    provider_version              text NOT NULL,
    provider_endpoint             text NOT NULL,
    zip_sha256                    text NOT NULL,
    csv_sha256                    text NOT NULL,
    cache_status                  text NOT NULL,
    planned_address_count         integer NOT NULL,
    processed_address_count       integer NOT NULL,
    candidate_count               integer NOT NULL,
    not_found_count               integer NOT NULL,
    skipped_existing_count        integer NOT NULL,
    status_code                   text NOT NULL,
    error_text                    text NULL,
    created_at                    timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT anncsu_region_name_not_blank CHECK (btrim(region_name) <> ''),
    CONSTRAINT anncsu_region_dataset_code CHECK (dataset_code ~ '^INDIR_[A-Z0-9]+$'),
    CONSTRAINT anncsu_region_provider_version_not_blank CHECK (btrim(provider_version) <> ''),
    CONSTRAINT anncsu_region_endpoint_not_blank CHECK (btrim(provider_endpoint) <> ''),
    CONSTRAINT anncsu_region_zip_hash CHECK (zip_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT anncsu_region_csv_hash CHECK (csv_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT anncsu_region_cache_status CHECK (cache_status IN ('acquired','reused','refreshed')),
    CONSTRAINT anncsu_region_counts_nonnegative CHECK (
        planned_address_count >= 0 AND processed_address_count >= 0
        AND candidate_count >= 0 AND not_found_count >= 0
        AND skipped_existing_count >= 0
    ),
    CONSTRAINT anncsu_region_counts_reconcile CHECK (
        candidate_count + not_found_count = processed_address_count
        AND processed_address_count + skipped_existing_count = planned_address_count
    ),
    CONSTRAINT anncsu_region_status_allowed CHECK (status_code IN ('succeeded','failed')),
    CONSTRAINT anncsu_region_identity UNIQUE (anncsu_orchestration_run_id,dataset_code)
);

CREATE INDEX anncsu_region_dataset_version_idx
    ON geo.anncsu_region_run (dataset_code,provider_version);

COMMENT ON TABLE geo.anncsu_orchestration_run IS
    'National ANNCSU orchestration run: deterministic required-region plan, versioned Istat input, and complete assignable/unassigned accounting.';
COMMENT ON TABLE geo.anncsu_region_run IS
    'Per-region ANNCSU input identity and incremental enrichment accounting. Provider versions and physical ZIP/CSV hashes are retained even when cached inputs are reused.';
