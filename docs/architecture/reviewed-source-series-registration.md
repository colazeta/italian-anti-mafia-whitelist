# Reviewed SourceSeries registration at archive persistence

Archive-first acquisition must not depend on a manually pre-seeded relational `source.source_series` row. A newly reviewed logical source series can therefore be present in the repository registries before its first durable capture while still being absent from the private relational evidence database.

The archive boundary remains unchanged: official bytes are acquired, frozen, written to the approved private ContentObject store, read back and size/SHA-256 verified; immutable capture/check provenance is then written to the private CaptureCatalogue and read back. Only after those two durable provider checks may relational work begin. A database registration or capture-persistence failure must never delete or overwrite the already recoverable provider objects.

The protected archive-first CLI now resolves the requested `source_key` against the reviewed repository `territorial_authorities.csv` and `source_series_inventory.csv` **before network acquisition, staging or provider setup**. A syntactically valid typo or otherwise unreviewed SourceSeries can therefore no longer create durable bytes or capture provenance under an identity that the relational and recovery layers would later reject. This preflight validates logical SourceSeries review and its authority binding; it deliberately does **not** require the exact acquired `resource_url` to equal `series_url`. Both are locators, and a recurring SourceSeries may move from a landing page to a different attachment URL or expose a new physical resource URL over time without changing logical series identity. The exact requested and resolved URLs remain capture provenance.

When `EVIDENCE_DATABASE_URL` is available, `archive_first` subsequently resolves the same reviewed `source_key` again before relational persistence. It idempotently ensures the corresponding public authority, White List register and logical SourceSeries exist before binding the archived capture. Existing structural authority/register/series bindings are checked and conflicting metadata fail closed in the same database transaction.

This registration is deliberately narrower than source acquisition or edition attribution. In particular:

- a SourceSeries key must already be present in the reviewed repository inventory; an arbitrary workflow input cannot create one;
- `series_url` remains discovery/locator metadata and is not inserted as document identity;
- acquisition preflight does not treat URL equality as SourceSeries or document identity;
- no SourceResource is created from the series locator merely by registration;
- no SourceEdition is created, and no reference/publication/effective/legal date is inferred;
- the exact acquired `resource_url` becomes a SourceResource only when the already-archived capture is persisted;
- repeated registration is idempotent and does not change established series IDs;
- if the relational writer is unavailable, bytes and capture provenance may still be archived, but the redacted checkpoint remains `writer_unavailable` and no archive-complete downstream claim is permitted;
- if reviewed-series registration or relational capture persistence fails after a valid reviewed acquisition, the transaction rolls back while durable bytes and immutable private catalogue provenance remain recoverable.

This is shared Lane A infrastructure. Lane B remains responsible for researching and reviewing new Prefecture source-series metadata on its own branch. Serial integration means that a new reviewed series row must reach canonical `main` before the protected `archive-source` workflow can acquire or register its first capture; Lane A does not infer or add Prefecture-specific rows on Lane B's behalf.

CI exercises the registration and subsequent capture persistence against real PostgreSQL constraints with synthetic object transport and rolls the transaction back. The acquisition preflight regression also proves that a syntax-valid but unreviewed SourceSeries fails before work-directory creation and before provider/network initialisation. These tests establish application behaviour only. They are not a real-provider readback, production database promotion, national recovery reconciliation, frozen national replay or independent restore test.
