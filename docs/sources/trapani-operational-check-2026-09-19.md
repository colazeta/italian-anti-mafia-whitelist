# Trapani White List operational check — 19 September 2026

## Official publication surface

The current official Prefettura di Trapani White List landing page is `https://prefettura.interno.gov.it/it/prefetture/trapani/evidenza/white-list`. It positively exposes two dedicated populations: the registered-company list and the list of companies requesting registration. Applicant coverage is therefore based on positive official-source evidence and is not inferred from search results or absence.

The source edition boundary used by the integration is 11 September 2026 because that date is explicitly carried in both official attachment filenames. It is a source reference boundary only and is not promoted to a company decision date, registration date, expiry date, or legal-effect date.

## Byte-pinned sources

- Listed PDF: `https://prefettura.interno.gov.it/sites/default/files/97/2026-09/elenco-ditte-iscritte-negli-elenchi-delle-white-list-aggiornato-all-11.09.2026.pdf` — SHA-256 `060c5ddb20b24f733066b59f27aa1ea98a8fdc04d22b0196b90c9e383253b476`.
- Applicant PDF: `https://prefettura.interno.gov.it/sites/default/files/97/2026-09/elenco-ditte-richiedenti-iscrizione-negli-elenchi-delle-white-list-aggiornato-all-11.09.2026.pdf` — SHA-256 `d42720c3ebf9c24055371fc42b1de89060604fc98d60861ec72a54e650412ae9`.

The validation worker performed two independent cache-bypassed GETs for each official attachment and required byte identity and exact SHA-256 before parsing.

## Listed population

The listed PDF has 41 pages. Its 658 statutory-sector rows resolve conservatively to 333 company observations after exact handling of repeated sector membership and ten explicitly bound continuation rows. The validated status boundary is 177 `listed` and 156 `renewal_update_in_progress`; structured identifier coverage is 333/333.

One source cell is intentionally not parsed as an expiry date. For `CALCESTRUZZI DI ROMANO ALESSANDRO` (identifier `05913370820`, Marsala), the source prints `In amministrazio ne giudiziaria e fermo restando fino al permanere della stessa` in the expiry column. The parser binds that exact identity/page/name/office/listing-date evidence, preserves the literal value in the raw expiry variants, and leaves `observed_expiry_date` blank. No date is inferred.

The page-boundary `SILVESTRO` fragment is likewise treated only through exact evidence: it completes `IMPRESA EDILE DI MANGANO SILVESTRO` and carries the source marker `per rinnovo`, yielding `In aggiornamento per rinnovo`. Generic continuation heuristics are not used to silently absorb unexpected semantic content.

## Applicant population

The applicant PDF has 44 pages and yields 222 pending observations with 222/222 structured identifiers. Twenty-three page-boundary continuation rows are joined only where exact prior-row identity and continuation content are bound in the parser. No applicant status, legal outcome, or completeness claim is inferred from failed retrieval or search.

## Validation boundary

The exact-head validation on 19 September 2026 required 333 listed-side observations, 222 applicant observations, 555 unique structured identifiers across the two source populations, exact status denominators, exact continuation counts, the unique raw non-date expiry case, and byte-identical repeated official-source captures. Repository CI, the source probe, shape diagnostics and focused parser validation were green before national integration was attempted.
