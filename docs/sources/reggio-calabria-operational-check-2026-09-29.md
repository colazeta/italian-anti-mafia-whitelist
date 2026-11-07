# Reggio Calabria White List — reviewed source/parser checkpoint (29 September–1 October 2026)

## Scope

This checkpoint closes the source/population/parser review for the ordinary White List of the Prefettura di Reggio Calabria. The two mandatory logical populations are independently supported by the official landing page and remain separate throughout acquisition and parsing:

- **listed** — the official registered-company White List attachment;
- **applicant** — the official attachment for companies requesting registration.

Official landing page: https://prefettura.interno.gov.it/it/prefetture/reggio-calabria/evidenza/white-list

This review establishes **reviewed source/parser coverage**. It does not by itself claim that Reggio Calabria has been promoted into the currently approved public release.

## Archive-first evidence

The scheduled national Prefecture robot run on 29 September 2026 completed successfully and captured the landing page plus both current PDFs through the governed evidence archive. Reggio Calabria had no acquisition error and no pending crawl frontier.

Robot run: https://github.com/colazeta/italian-anti-mafia-whitelist/actions/runs/36557477529

| population | current resource | SHA-256 | bytes | HTTP last-modified |
| --- | --- | --- | ---: | --- |
| listed | https://prefettura.interno.gov.it/sites/default/files/0/2026-09/white-list-foglio-unico-nuove-attivita-24-set-2026.pdf | `f93a63a89c2c22f9fee27af29654c3dd5e97b58452dde92224b4b2259d3f148f` | 266878 | 24 Sep 2026 15:15:23 GMT |
| applicant | https://prefettura.interno.gov.it/sites/default/files/0/2026-09/elenco-richieste-iscrizioni-white-list-foglio-del-24-set-2026.pdf | `da60df92f7ffdfc1148ead109395e00ae34e11cb53c01ccc6928bbdff0c71d53` | 372194 | 24 Sep 2026 15:15:07 GMT |

The governed robot history contains repeated byte-identical captures for both resources. On 1 October 2026 the exact official URLs were independently fetched again inside CI before parser validation; both byte counts and both SHA-256 values still matched the archived identities.

Parser validation run: https://github.com/colazeta/italian-anti-mafia-whitelist/actions/runs/36828318024

The attachment names and official source presentation support **24 September 2026** as the source-reference date for this reviewed edition. Capture time, processing time and source-reference time remain distinct. No company legal-effect date is inferred from the attachment date.

## Population semantics

The applicant population is not inferred from the filename: the official landing page explicitly identifies that attachment as the list of companies requesting registration. The registered-company attachment is separately presented as the White List of suppliers/service providers. The reviewed configuration therefore binds two distinct SourceSeries:

- `reggio-calabria-listed` → `reggio_calabria_listed`;
- `reggio-calabria-applicants` → `reggio_calabria_applicants`.

Both mappings are SHA-pinned and fail closed on source-layout or denominator drift.

## Listed parser boundary

The byte-pinned listed PDF has **65 pages**, exactly one detected table per page and source numbers **1–533** with no gaps or duplicates. The header is present only on page 1; later pages start directly with company rows, which is an explicit parser invariant.

The source contains one numbered row, **533**, with only its sequence number and no company identity or substantive fields. It is retained as a reviewed blank numbered source row but is **not materialised as a company observation**. The parser therefore yields **532 public-source observations**.

Reviewed status boundary:

- 252 `listed`;
- 250 `renewal_update_in_progress`;
- 30 `other_or_unknown`.

The last category is deliberate: non-empty source notes that are not source-explicit renewal/update-in-progress language are preserved without translating judicial-administration or other text into a stronger legal status.

Additional invariants:

- strict source identifiers: **517/532** observations;
- source-explicit listing dates normalised: **532/532**;
- source-explicit expiry dates normalised: **518/532**;
- 13 expiry cells are source-blank;
- the malformed source token `07/04//23` remains raw and unparsed;
- one source row has a blank company-name cell, one has a blank registered-office cell, and two have blank activity cells; these source blanks remain blank and are not imputed;
- malformed or irregular identifier strings remain in `identifier_field_raw`; the parser does not repair them into structured identifiers.

## Applicant parser boundary

The byte-pinned applicant PDF has **79 pages**, exactly one detected table per page, a repeated table header on every page and source numbers **1–732** with no gaps or duplicates. The parser yields **732 observations**.

Reviewed status boundary:

- 730 `pending`, including two source-explicit typographic variants of “Istruttoria”;
- 2 `other_or_unknown`: one blank source outcome and one `L.M.` outcome.

Additional invariants:

- strict source identifiers: **697/732** observations;
- source-explicit application dates normalised: **731/732**;
- the impossible source token `07/13/2024` remains raw and unparsed rather than being reinterpreted;
- two registered-office cells are source-blank and remain blank;
- malformed or irregular identifier strings are preserved raw and are not repaired.

## Governance decision

The parser was executed end-to-end against the exact SHA-pinned resources and the repository CI passed that validation. The reviewed SourceSeries, parsers and robot profile therefore support setting `population_mapping_reviewed=true` for Reggio Calabria.

The publication boundary remains separate. The national monitoring row records parser/source coverage as validated while `company_observations_loaded`, `canonical_integration_validated` and `public_export_enabled` remain false in this checkpoint. The existing national public-candidate workflow is independently blocked by a current Lodi byte-identity change and must not be bypassed merely to publish Reggio Calabria.

Accordingly, this checkpoint establishes **reviewed Prefettura coverage +1** for Reggio Calabria, while public-release coverage is unchanged until the normal release gates succeed.
