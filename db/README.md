# Database implementation

## Target

PostgreSQL 18.

## Apply

```bash
psql -v ON_ERROR_STOP=1 -f db/apply.sql
```

`apply.sql` loads schema files and seed vocabularies in dependency order inside one transaction. A failed bootstrap therefore rolls back rather than leaving a partially installed baseline.

This is a bootstrap schema, not yet a production migration system. Migration tooling will be introduced before persistent production databases are upgraded across schema versions.

## Test

```bash
psql -v ON_ERROR_STOP=1 -f db/test.sql
```

The integration suite deliberately attempts invalid operations and succeeds only when PostgreSQL rejects them with the expected constraint/trigger errors. It also checks positive cases such as historical corrections with non-overlapping system periods and current-state views over true unbounded ranges.

## Important

The execution environment used to build this baseline does not provide a local PostgreSQL server. Python/static repository tests are run locally; the PostgreSQL integration suite is designed to run under Docker Compose or GitHub Actions. The schema must not be tagged as a database release until that live PostgreSQL 18 suite passes.
