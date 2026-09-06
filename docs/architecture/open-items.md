# Open implementation items

The logical model and the audit corrections are incorporated in the current pre-alpha schema. The following work remains before the schema can be tagged as a database release:

1. **Live PostgreSQL 18 validation** of every DDL statement and all negative/positive integration tests.
2. **Historical taxonomy backfill** for the pre-7 June 2020 White List sector scheme(s), including transitional mappings.
3. **National source census** covering every Prefecture/competent authority and historical source series.
4. **Licence/reuse review** before bulk public release.
5. **Parser specification** and structural fingerprints for each observed source schema.
6. **Entity-resolution policy** defining thresholds for automatic acceptance versus manual review.
7. **Public dissemination profiles**, including treatment of fields linked to self-employed natural persons.
8. **Object-storage design** and retention policy for immutable raw content.
9. **Migration tooling** before the schema begins evolving against persistent production databases.
10. **External code-list bindings** for countries, languages, administrative units, legal forms and identifier schemes.

The previous audit blockers concerning true unbounded system periods, tri-temporal overlap, parser versioning, field/schema consistency, sector/scheme consistency, raw-value immutability, processing lineage and derived-event inputs have been addressed in the DDL and test suite. They still require execution against a live PostgreSQL 18 server before release status is granted.
