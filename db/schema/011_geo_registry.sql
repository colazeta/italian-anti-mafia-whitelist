CREATE TABLE IF NOT EXISTS registry.geographic_unit_level (
    code        text PRIMARY KEY,
    label       text NOT NULL,
    description text NULL
);
COMMENT ON TABLE registry.geographic_unit_level IS 'Administrative/statistical geographic unit level.';

CREATE TABLE IF NOT EXISTS registry.geocode_match_status (
    code        text PRIMARY KEY,
    label       text NOT NULL,
    description text NULL
);
COMMENT ON TABLE registry.geocode_match_status IS 'Review/acceptance status of a geocoding result.';

CREATE TABLE IF NOT EXISTS registry.geocode_precision (
    code        text PRIMARY KEY,
    label       text NOT NULL,
    description text NULL
);
COMMENT ON TABLE registry.geocode_precision IS 'Spatial precision/granularity of a geocoding result.';

CREATE TABLE IF NOT EXISTS registry.geographic_assignment_method (
    code        text PRIMARY KEY,
    label       text NOT NULL,
    description text NULL
);
COMMENT ON TABLE registry.geographic_assignment_method IS 'Method used to assign an address to an administrative/statistical unit.';
