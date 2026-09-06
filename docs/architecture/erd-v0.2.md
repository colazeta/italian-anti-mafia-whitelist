# ERD v0.2 — audited consolidated baseline

This document records the logical baseline implemented by the corrected pre-alpha PostgreSQL schema.

## Canonical core

```mermaid
erDiagram
    LEGAL_ENTITY ||--o{ ENTITY_NAME : has
    LEGAL_ENTITY ||--o{ ENTITY_IDENTIFIER : has
    LEGAL_ENTITY ||--o{ ESTABLISHMENT : has
    ESTABLISHMENT ||--o{ ESTABLISHMENT_ADDRESS : uses
    ADDRESS ||--o{ ESTABLISHMENT_ADDRESS : represents

    PUBLIC_AUTHORITY ||--o{ WHITE_LIST_REGISTER : maintains
    WHITE_LIST_REGIME ||--o{ WHITE_LIST_REGISTER : governs

    LEGAL_ENTITY ||--o{ WHITE_LIST_RELATIONSHIP : has
    WHITE_LIST_REGISTER ||--o{ WHITE_LIST_RELATIONSHIP : contains
    WHITE_LIST_RELATIONSHIP ||--o{ RELATIONSHIP_STATE_VERSION : has_history
    WHITE_LIST_RELATIONSHIP ||--o{ RELATIONSHIP_SECTOR : has_sector
    RELATIONSHIP_SECTOR ||--o{ RELATIONSHIP_SECTOR_STATE_VERSION : has_history
    SECTOR_CONCEPT ||--o{ RELATIONSHIP_SECTOR : classifies

    WHITE_LIST_RELATIONSHIP ||--o{ WHITE_LIST_PROCEDURE : has_procedure
    WHITE_LIST_PROCEDURE ||--o{ PROCEDURE_VERSION : has_history
    WHITE_LIST_PROCEDURE ||--o{ PROCEDURE_SECTOR : concerns
    SECTOR_CONCEPT ||--o{ PROCEDURE_SECTOR : requested_in

    WHITE_LIST_REGIME ||--o{ SECTOR_SCHEME_VERSION : defines
    SECTOR_SCHEME_VERSION ||--o{ SECTOR_SCHEME_MEMBERSHIP : contains
    SECTOR_CONCEPT ||--o{ SECTOR_SCHEME_MEMBERSHIP : represented_as

    PROCESSING_ACTIVITY ||--o{ ENTITY_NAME : generates
    PROCESSING_ACTIVITY ||--o{ ENTITY_IDENTIFIER : generates
    PROCESSING_ACTIVITY ||--o{ RELATIONSHIP_STATE_VERSION : generates
    PROCESSING_ACTIVITY ||--o{ RELATIONSHIP_SECTOR_STATE_VERSION : generates
    PROCESSING_ACTIVITY ||--o{ PROCEDURE_VERSION : generates
```

## Source and provenance

```mermaid
erDiagram
    SOURCE_SERIES ||--o{ SOURCE_EDITION : has
    SOURCE_RESOURCE ||--o{ SOURCE_CAPTURE : captured
    CONTENT_OBJECT ||--o{ SOURCE_CAPTURE : materialises
    SOURCE_CAPTURE ||--o{ CAPTURE_EDITION : attributed_to
    SOURCE_EDITION ||--o{ CAPTURE_EDITION : represented_by

    CONTENT_OBJECT ||--o{ PARSE_RUN : parsed_by
    PROCESSING_ACTIVITY ||--o| PARSE_RUN : describes
    PARSE_RUN ||--o{ PARSED_RECORD : yields

    SOURCE_SCHEMA ||--o{ SOURCE_SCHEMA_VERSION : versions
    SOURCE_SCHEMA_VERSION ||--o{ SOURCE_FIELD_DEFINITION : defines
    SOURCE_SCHEMA_VERSION ||--o{ PARSED_RECORD : structures
    PARSED_RECORD ||--o{ SOURCE_FIELD_VALUE : contains
    SOURCE_FIELD_DEFINITION ||--o{ SOURCE_FIELD_VALUE : defines

    PARSED_RECORD ||--o{ ENTITY_MENTION : mentions
    PARSED_RECORD ||--o{ PROCEDURE_MENTION : mentions
    ENTITY_MENTION ||--o{ ENTITY_RESOLUTION : resolved_by
    LEGAL_ENTITY ||--o{ ENTITY_RESOLUTION : resolves_to
    PROCEDURE_MENTION ||--o{ PROCEDURE_RESOLUTION : resolved_by
    WHITE_LIST_PROCEDURE ||--o{ PROCEDURE_RESOLUTION : resolves_to
```

`SourceFieldValue` carries the schema version explicitly and uses composite foreign keys so that the parsed record and field definition must belong to that same source-schema version.

## Key semantic decisions

- A White List relationship is unique for `legal_entity × register` and carries no status itself.
- Requested sectors are attached to procedures; sectors actually represented in the register are attached to the relationship.
- `I`, `II`, ..., `X` are not canonical sector identifiers. They are notations within a versioned scheme.
- Scheme versions for one regime cannot overlap; membership periods must be contained in their scheme-version period.
- A relationship-sector state may reference a scheme membership only when both its canonical sector and regime match the relationship/register context.
- Canonical historical versions carry `effective_period`, `observation_period`, and `system_period` where all three dimensions matter.
- Unknown `effective_period` remains semantically unknown, but is treated as an all-time wildcard when evaluating overlap integrity.
- Open system/observation periods use true unbounded range bounds (`NULL` bound), so `upper_inf()` correctly identifies current rows.
- A source locator is not assumed to be a web URL. Web URLs are optional metadata, supporting future FOIA/archive acquisitions.
- Immutable bytes are represented by `content_object` and keyed by SHA-256. Source field values are append-only.
- Parsing is versioned through `parse_run` + `processing_activity`; reprocessing the same content never destroys an earlier interpretation.
- Evidence is many-to-many and can point to a field value, parsed record, source edition, or source capture.
- Evidence and processing lineage are separate: evidence explains support; `ProcessingActivity` explains generation/transformation.
- Derived events retain explicit links to the canonical version rows used as inputs.
- Dissemination decisions are scoped to named publication profiles rather than attached globally to a field.
