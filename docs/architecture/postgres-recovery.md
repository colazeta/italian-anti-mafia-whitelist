# Private PostgreSQL logical recovery checkpoint

`postgres-recovery.yml` is manual, main-only and uses the existing protected
`evidence-archive` environment. It creates no cloud infrastructure or credentials.
The only restore target is a new ephemeral PostgreSQL 18 service on its runner.

The source connection must use TLS. A repeatable-read, read-only transaction
exports a consistent snapshot. The matching PostgreSQL 18 client uses that
snapshot for a custom-format `pg_dump`, including schema, table data, functions,
constraints, views, extensions and triggers. Connection strings travel through
environment variables, never process arguments. Tool stderr and provider exception
messages are suppressed because they can include secrets or row values.

The full dump is conditionally written to a fresh private R2 operational attempt
path, identified by SHA-256, and fully read back before use. The readback bytes
are restored with `pg_restore --exit-on-error --no-owner --no-acl` into a clean
database; a populated target is refused. Every table, including empty tables, is
compared using its exact row count and length-framed SHA-256 of the sorted full
JSON row multiset. Structural catalogues are independently compared. A private
inventory and receipt are also persisted and read back. Only aggregate counts,
digests, verification time and explicit limitations are printed.

The current project uses UUID identities. The tool fails closed if sequences,
large objects or foreign tables exist; they require additional snapshot/recovery
handling before this check can claim coverage. Only PostgreSQL major 18 is
accepted, avoiding representation differences in row and catalogue hashing.
Privileges must permit reading all project relations; a preflight reports only
the aggregate unreadable-table count and fails before the dump if access is
incomplete. The tool never grants privileges or obtains an owner credential.
No production writes, role changes or migrations occur.

This verifies the database's logical schema and contents, not role ownership,
passwords or ACL restoration. Those are deployment configuration and remain an
explicit separate recovery responsibility. Same-provider R2 persistence is not
an independent backup. A separate provider readback and clean restore, original
document recovery, reviewed recovery responsibility and the frozen national
release gate remain necessary for closing issue #16. No unit test or successful
dump command alone closes that issue.
