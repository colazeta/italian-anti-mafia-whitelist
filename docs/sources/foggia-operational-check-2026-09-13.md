# Foggia operational source check — 13 September 2026

## Current official publication

The official Prefettura di Foggia White List landing page is `https://prefettura.interno.gov.it/it/prefetture/foggia/evidenza/white-list`. The current registered-company and applicant populations are published as separate official PDF attachments and were re-downloaded by the parser validation gate on 13 September 2026. Publication is bound to the exact byte hashes below; hash drift fails closed.

- Listed population: 8 September 2026, 44 pages, `313828d0d7fc0797920697841411503230a1a569e1eb8d41f93aec15908e5d5a`, `https://prefettura.interno.gov.it/sites/default/files/43/2026-09/white-list-elenco-imprese-iscritte-aggiornato_al-08-09-2026-copia.pdf`.
- Applicant population: 10 September 2026, 46 pages, `d76eab040fcb984dbabbff740296f9cd30b41ef028ba756d210d4b7d7df2f6d5`, `https://prefettura.interno.gov.it/sites/default/files/43/2026-09/elenco_delle_imprese_richiedenti_iscrizione_elenco_fornitori_agg_10-09-2026.pdf`.

## Parser boundary and semantics

The listed PDF contains 942 statutory-section rows. Exact grouping by strict source identity, date pair and reviewed status semantics yields 330 public observations: 85 `listed` and 245 `renewal_update_in_progress`. Three source name-layout inconsistencies are reconciled only through explicit evidence-backed guards; raw variants remain parser evidence. Unknown status lexemes, section structures, row widths and groupings fail closed.

The applicant PDF yields 628 observations, all explicitly marked `ISTRUTTORIA` and published as `pending`. Identifier coverage is frozen at 621 strict identifiers, six non-empty raw-only identifiers and one empty source identifier. No identifier is padded, truncated or otherwise repaired. Application dates and requested activities are required by the parser.

The parser validation also freezes reviewed identity cases including LUISI COSTRUZIONI DI LUISI CARMINE (`03570730717`) and the two source observations for IMPRESA PASQUA S.R.L. (`03926080718`), and verifies six applicant identifiers that occur in two distinct source rows each.

## Publication treatment

Foggia is represented as one ordinary register with two source series, `foggia-listed` and `foggia-applicants`. Parser-only layout diagnostics are retained for validation but projected through an exact fail-closed adapter before the recursively closed public contract. Canonical hosted-database integration and independent durable-evidence verification remain governed separately under issue #16; they are not inferred from public-source availability.
