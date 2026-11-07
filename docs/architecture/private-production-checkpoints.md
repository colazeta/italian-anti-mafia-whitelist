# Private production checkpoints

The existing reviewed-capture transformer now retains a database checkpoint from
shard zero on every execution, including failed transformation attempts. It uses
a fresh TLS connection and one repeatable-read, read-only transaction. Reports
are create-only private operational records in the existing evidence store, with
exact provider readback; no rows, credentials or private coordinates enter Actions
artifacts. Public logs expose only checkpoint success and metric availability.

Every count identifies its table, unit and transaction timestamp. Ratios include
their actual denominator. Unreadable layers are `not_verified` with a null value,
never reported as zero and never made readable by granting privileges. Snapshot
occurrences span interpretation revisions and are not distinct businesses. Stored
durable status is a database measure, not a fresh original-byte verification;
array-length consistency is not a SHA-256 rehash. Zero canonical rows do not prove
that all source facts were processed. Backup independence and publication approval
remain unknown in this checkpoint and require their separate acceptance evidence.

This is a persistent database measurement added to the existing workflow, not a
new schedule. Robot coverage, formal parser binding coverage, historical gaps,
quarantine ageing, original-byte readbacks and public-release acceptance retain
their own denominators and evidence. Concurrent transformer shards can commit
after this snapshot, so this timestamp is not described as a final global run total.

CI also executes the collector against real PostgreSQL, verifying the actual
permission/catalogue SQL and repeatable-read/read-only transaction settings.
