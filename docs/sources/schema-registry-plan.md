# National source/schema registry plan

Before production normalisation, every competent White List source will be registered with:

- authority;
- White List register/regime, where identifiable;
- source series;
- source locator and optional web URL;
- population scope and its completeness;
- sector scope and its completeness;
- file/resource type;
- source origin and evidential rank at capture time;
- source editions and captures;
- source schema versions;
- every observed source field;
- field-to-canonical mappings;
- divergence classes and resolution rules.

The first national census should cover all entries linked from the Ministry of the Interior's national White List index and then backfill the historical Prefecture portal.

A schema version changes when the structural fingerprint changes, not merely because a new monthly edition is published. A `SourceFieldValue` is constrained to use a field definition from the same schema version as its parsed record, preventing cross-schema contamination.
