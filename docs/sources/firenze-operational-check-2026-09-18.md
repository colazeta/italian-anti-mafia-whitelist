# Firenze — operational source check (2026-09-18)

## Scope

This note records the positive evidence required before integrating the Prefettura di Firenze White List into the canonical/public pipeline. It is an evidence checkpoint, not a publication approval by itself.

## Official source surface

Official landing page:

- `https://prefettura.interno.gov.it/it/prefetture/firenze/white-list-elenco-imprese-iscritte`
- page last-updated marker observed during the 2026-09-18 check: `09/09/2026 - 11:19`
- the page exposes two distinct current population attachments, both of which must be treated for a complete current edition:
  - `White List Firenze` — enrolled/current-list population;
  - `Elenco richiedenti White List` — applicant population.

Current official attachments resolved from that page:

1. Listed-side XLSX
   - URL: `https://prefettura.interno.gov.it/sites/default/files/42/2026-09/white_list_09-09-2026.xlsx`
   - bytes: `74031`
   - SHA-256: `bc23303a5c9f398c4749def1178057f8d938644fe6f2b3745c8a8112901f17f0`

2. Applicant PDF
   - URL: `https://prefettura.interno.gov.it/sites/default/files/42/2026-09/elenco-rich-w.l-al-09.09.26.pdf`
   - bytes: `350462`
   - SHA-256: `6a6eb981f3476b67c4344067a82b14295076cb1c35a557337aecb8bc38a7d695`

The attachment bytes and hashes above were re-fetched in independent GitHub Actions executions during this operational check. Publication code must remain fail-closed on source-byte drift unless a newly reviewed edition is approved.

## Listed-side structure and reviewed extraction boundary

The XLSX contains ten statutory sheets (`Sezione I` through `Sezione X`) and the same tabular field family already handled by the repository's audited Arezzo OpenXML parser: company name, registered office, secondary office, tax/VAT identifier, inscription date, expiry date and update marker.

Applying the existing structural parser to the byte-pinned Firenze workbook produced the following audited diagnostics:

- physical sector rows: `989`;
- dated sector rows: `989`;
- dropped dated rows: `0`;
- malformed dated rows preserved: `0`;
- date-conflict identity groups: `0`;
- grouped company observations: `539`;
- status distribution:
  - `listed`: `429`;
  - `renewal_update_in_progress`: `110`;
- structured identifier coverage: `537 / 539`;
- non-empty raw identifier values not safely structured: `2`;
- duplicate identity-variant groups after grouping: `0`.

The `989 → 539` reduction is not row loss: the workbook repeats the same company across statutory sector sheets. The parser groups only rows sharing the exact source identity/date/update boundary and preserves all requested sector memberships.

## Applicant-side structure and reviewed extraction boundary

The official applicant PDF contains `9` pages and reports `Totale Società: 125`. Layout-preserving extraction identifies exactly `125` applicant rows. Each row contains company name, registered office when reported, raw tax/fiscal identifier, application date and an `Esito` column.

Reviewed diagnostics:

- applicant rows: `125`;
- rows with a strict structured identifier: `123`;
- rows retaining a non-empty raw identifier that must not be repaired/inferred: `2`;
- blank registered-office values: `2`;
- `Esito` values: blank for all `125` rows in this edition.

The two reviewed raw-only identifier observations are:

- `CALENZANO SPURGHI DI DANI MICHELE` — registered office `CALENZANO` — raw identifier `DNAMHL69H19B832` — application date `31/08/2026`;
- `VALDARNO SPURGHI DI BENEDETTI MASSIMILIANO` — registered office `FIGLINE E INCISA VALDARNO` — raw identifier `BNDMSM73B08D583` — application date `30/07/2026`.

The two reviewed blank-office observations are:

- `SAN TOMMASO D'AQUINO Soc. Coop. Sociale` — identifier `05056380487` — application date `25/05/2026`;
- `TECNOCONFERENCE Srl` — identifier `03755090481` — application date `24/07/2026`.

These source defects/omissions must be preserved as source facts. Do not infer missing identifier characters or a registered office from external data merely to increase field coverage.

## Status semantics

The applicant attachment is explicitly published by the Prefettura as `Elenco richiedenti White List`. In this edition every applicant row has an empty `Esito` cell. Subject to the parser reproducing the byte-pinned denominator and blank-outcome invariant, the appropriate source status for these observations is `pending`. If a later edition contains a non-empty outcome marker, the parser must fail closed until that marker is reviewed rather than silently retaining `pending`.

The XLSX status mapping remains the established evidence-first rule: a grouped row with a non-empty source update marker is `renewal_update_in_progress`; otherwise a positively dated listed row is `listed`.

## Parser-family decision

- Listed population: bind Firenze to the audited OpenXML grouped-sector family used for Arezzo, with Firenze-specific byte/hash and denominator assertions.
- Applicant population: implement a dedicated Firenze paginated-PDF parser. It must derive the repeated column boundary from the official layout, require the reviewed `125`-row denominator, preserve the two raw-only identifiers and two blank offices, and fail on non-empty/unknown `Esito` semantics.

No applicant population may be omitted merely because it is a separate attachment.

## Publication gate

Firenze must remain outside the public national registry until all of the following are true on a permanent branch/PR without temporary probe machinery:

1. both current source attachments are represented in the source/current-edition configuration;
2. both parsers reproduce the reviewed denominators and source defects above;
3. generated observations pass schema validation without weakening existing rules;
4. national build assertions are updated to the actual generated boundary;
5. CI, public artifact validation, browser acceptance and official-source-link checks are green;
6. after merge, the corresponding `main` build and GitHub Pages deployment are verified.

Operational source verification alone is therefore `verified source / not yet public`.
