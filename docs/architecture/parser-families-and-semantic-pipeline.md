# Parser families and automatic semantic pipeline

## Why this architecture exists

The first Cosenza checkpoint exposed an important architectural gap. The project had a strong source-observation layer (`Capture -> ParseRun -> ParsedRecord -> SourceFieldValue -> EntityMention`) but parsing stopped there by design. That was useful for proving immutability and provenance, but it left ontology/canonical tables empty even when the source contained enough information to populate them safely.

The corrected pipeline is:

```text
SourceSeries / SourceEdition
        |
        v
Capture / ContentObject
        |
        v
ParserFamily              physical source extraction
        |
        v
RecordContract            stable interface independent of source layout
        |
        v
SemanticProjector         typed ontology-level observations
        |
        v
Resolution / Canonicaliser
        |
        +--> requires_resolution / requires_review
        |
        v
Canonical model           LegalEntity, WhiteListRelationship, procedures, history
        |
        v
Derived events / marts / Explorer
```

The key correction is that **conservatism applies to inference, not to ontology population**. Every safely typed source fact should reach the semantic layer automatically. Only identity merges or administrative interpretations that require stronger evidence remain unresolved.

## Parser families, not parsers per URL

A parser is a physical extraction implementation. It understands a specific source family: PDF table geometry, HTML table structure, XLSX workbook layout, CSV dialect, or another recurring publication form.

The project does not create one parser for every URL. URLs and publication pages are resources/editions and can change without changing the source schema.

It also avoids a single universal parser. A universal parser tends to hide source-specific assumptions and makes regression testing difficult.

Instead the project maintains **parser families**:

```text
parsers/
  cosenza_combined_v2.py
  <future-family-a>.py
  <future-family-b>.py
  registry.py
```

A family may be assigned to many source series when validation shows that the layout/schema is compatible.

## Source-series binding and schema fingerprints

Parser selection is data-driven through:

- `data/source_registry/parser_families.csv`
- `data/source_registry/parser_bindings.csv`

Each parser family declares:

- implementation module;
- parser version;
- output record contract;
- semantic profile;
- field-locator namespace;
- validated structural schema fingerprints;
- validation status.

Selection order:

1. an explicit validated `SourceSeries -> ParserFamily` binding wins;
2. otherwise one exact validated schema-fingerprint match may reuse the family;
3. multiple matches require an explicit binding;
4. no match produces a controlled failure / new-family review. The system never guesses a parser.

This makes a parser reusable across a block of compatible sources while keeping every assignment explicit and auditable.

## Record contracts decouple parsing from ontology

A physical parser does not write canonical database tables. It emits a stable **record contract**.

The first implemented contract is:

`prefecture-combined-whitelist-v1`

For Cosenza it provides the source fields:

- business name;
- registered office;
- secondary office;
- source identifiers;
- requested White List activities;
- application dates;
- full source outcome (`Esito`).

A future HTML parser and a future XLSX parser can emit the same contract and therefore reuse the same semantic projector.

Conversely, if a source publishes materially different semantics, it can use a different record contract even if its physical file format is identical.

## Semantic profiles and field mappings

`data/source_registry/semantic_profiles.csv` maps a record contract to a versioned semantic projector.

The projector populates typed semantic observations such as:

- `semantic.entity_observation`;
- `semantic.identifier_observation`;
- `semantic.establishment_observation`;
- `semantic.relationship_observation`;
- `semantic.procedure_observation`;
- `semantic.procedure_sector_observation`.

At the same time, the project materialises versioned `mapping.field_mapping` records from parser-family field definitions to `mapping.canonical_field` concepts.

This is the place where a source can reveal an ontology gap. If a source concept is not representable, the projector must create an explicit unmapped/review issue. It must **not silently add or redefine the canonical ontology**.

## Guarded canonicalisation

Semantic projection is automatic. Canonicalisation is also automatic where deterministic rules are strong enough, but is deliberately selective.

For entity identity, the current resolver requires at least one strong source identifier that is not ambiguous across distinct source names. The resolver may create:

- `core.legal_entity`;
- source-supported `entity_name` and `entity_identifier` versions;
- addresses and establishments;
- `whitelist.white_list_relationship`;
- relationship-state versions;
- resolved White List procedures and procedure versions;
- requested procedure-sector links.

Ambiguous cases remain `requires_resolution` instead of blocking the rest of the dataset.

An important edge case is explicitly supported: a row may contain one ambiguous identifier and another independent, non-ambiguous identifier. The entity may be resolved using the safe identifier, while the ambiguous identifier remains only in `semantic.identifier_observation` and is **not promoted** to `core.entity_identifier`.

## Temporal guardrails

Source chronology is not mechanically equated to procedure chronology.

For example, a source row can contain:

- an older listing date referring to an existing White List relationship; and
- a newer application date referring to a renewal/update procedure.

If `observed_listing_date < application_date`, the listing date is retained as a relationship/source observation but cannot be promoted as the decision date of that later procedure. A `LISTING_DATE_PRECEDES_APPLICATION_DATE` issue is recorded instead.

Similarly:

- nominal expiry is not automatic loss of legal effect;
- disappearance from an edition is not removal;
- requested sectors belong to procedures, not automatically to the listed relationship.

## Data-driven population status

The Dataset Explorer no longer relies on hard-coded statements such as “table populated” or “not populated”. After ingestion, `white-list-model-population` queries the reconstructed PostgreSQL database and exports counts/statuses for the model.

Statuses include:

- `POPULATED`;
- `POPULATED_WITH_UNRESOLVED_EDGE_CASES`;
- `POPULATED_WITH_REVIEW_ITEMS`;
- `REQUIRES_RESOLUTION`;
- `REQUIRES_REVIEW`;
- `NOT_APPLICABLE_FROM_CURRENT_SOURCE`;
- `NOT_YET_PROCESSED`;
- `NOT_YET_POPULATED`.

Therefore an empty table is never presented without an explanation of whether it is empty because the source does not support it, a downstream stage has not run, or review/resolution is still pending.

## Rule for future Prefectures

For each newly discovered source series:

1. fingerprint and inventory the source schema;
2. try to match an already validated parser family;
3. if compatible, bind the source series to that family and run its regression suite;
4. if not compatible, implement a new parser family;
5. prefer reusing an existing record contract when the semantics are equivalent;
6. create a new semantic profile only when the source semantics require it;
7. project all observable source information automatically;
8. canonicalise only the subset supported by explicit deterministic rules;
9. retain unmapped, ambiguous and conflicting values as first-class reviewable data;
10. regenerate model-population and Dataset Explorer outputs from the database itself.

This architecture lets the parser library grow with source heterogeneity without coupling the canonical ontology to individual Prefecture websites.
