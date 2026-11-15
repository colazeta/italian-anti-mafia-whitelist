# Private interpretation reuse across operational changes

The changed-source worker used the entire deployment commit as its reuse key.
Direct production SQL on 15 November 2026 found 25 Aosta interpretations with
identical complete input/configuration and one output digest. These remain
immutable historical processing records, not 25 administrative editions.

The existing worker now reuses a prior interpretation only after:

1. Every labelled original and immutable capture provenance has passed readback.
2. Parser name, full source configuration and the complete labelled SHA-256 input
   set match. Missing or additional bundle members cannot match.
3. The recorded processing commit equals the deployment commit, or Git proves
   identical objects for **all** parser families, the entire publishing package
   (including dispatch/adapters/contracts), national-index dependency and
   `pyproject.toml`. No historical code is executed. Missing/incomplete Git
   history means no cross-revision reuse. The protected checkout retains history.
4. Every equivalent stored interpretation passes a full content rehash, including
   diagnostics. Conflicting outputs fail closed before any new capture linkage.

Repeated historical copies with identical output can select the oldest verified
interpretation deterministically. Its processing revision is retained. New capture
checks link to that existing ParseRun using the existing idempotent relation;
no rows, dates or digests are rewritten. A parser/dependency/adapter change still
requires a new interpretation. This is conservative package equivalence, not yet
per-family dependency analysis or proof that external runtime versions are fixed.

The change does not approve SourceEdition, QA flags or publication. Provenance,
TLS, listed/applicant and public release gates remain separate. Acquisition and
snapshot writes retain their existing locks/transactions. No additional scheduler,
writer, database or infrastructure is introduced.

Production acceptance must separately show current worker reuse counts, committed
input/capture links, unchanged snapshot IDs/counts on repeat, and absence of new
equivalent output copies. Unit tests and CI alone do not establish these facts.
