# Product documentation

This section documents user-facing surfaces built on top of the archive without changing the underlying evidence/canonical model.

Current product checkpoint:

- [`data-explorer-checkpoint.md`](data-explorer-checkpoint.md) — the internal Cosenza-first Data Explorer used to review parsing, source observations, snapshot differences and provenance before national parser scale-out.

Product surfaces must preserve the same semantic boundaries as the database. In particular, a UI must never make a parsed source observation look like a canonical company, administrative registration/removal or legal-effect determination unless the relevant canonical layer has actually been populated and evidenced.
