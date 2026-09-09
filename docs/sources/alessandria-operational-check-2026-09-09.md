# Alessandria White List — operational source check (2026-09-09)

## Official surface

Official landing page:

- https://prefettura.interno.gov.it/it/prefetture/alessandria/evidenza/white-list

A live retrieval from the repository CI environment on 2026-09-09 resolved two current official resources from that page. This was necessary because indexed search results were lagging behind the live official surface and still exposed an earlier 27 August edition.

## Current edition verified

### Registered companies

- source series: `alessandria-listed`
- population: `listed`
- reference date stated in the document: **4 September 2026**
- resource: https://prefettura.interno.gov.it/sites/default/files/14/2026-09/white-list-4-settembre-2026.pdf
- bytes: `1227364`
- SHA-256: `78606eafbfd6237b0c513ffd9faea1826f39cbda228538d197a42bcf20317b95`
- pages: `57`
- extracted source sector rows: `664`
- grouped public observations: `365`
- section headers observed: `SEZIONE I` through `SEZIONE X`
- source outcomes across sector rows: `406` blank, `245` `In istruttoria per rinnovo`, `5` upper-case `IN ISTRUTTORIA PER RINNOVO`, `8` bare `In istruttoria`.

The parser groups repeated sector rows on source identity/date/outcome while retaining all observed section memberships and all registered-office variants. A bare `In istruttoria` note inside this registered-company document is kept as `other_or_unknown`; it is not silently reclassified as a renewal or an applicant record.

### Applicant companies

- source series: `alessandria-applicants`
- population: `applicant`
- reference date stated in the document: **4 September 2026**
- resource: https://prefettura.interno.gov.it/sites/default/files/14/2026-09/elenco-imprese-richiedenti-iscrizione-in-white-list-4-settembre-2026.pdf
- bytes: `195918`
- SHA-256: `34f151daa69ad3d84e0ad892cbc5048ff516ad9ae371805321bbe5156c82deb0`
- pages: `11`
- extracted source rows / public observations: `71`
- source outcome: `In istruttoria` for all `71` rows.

Applicant activities are published as numbered White List sections. The parser retains those as neutral source-derived labels such as `Sezione 1`, rather than inventing a semantic activity description not present in the row.

## Identifier handling

The PDFs contain a small number of numeric identifiers whose printed source length is not 11 digits:

- listed sector rows: `26` ten-digit occurrences;
- applicants: one ten-digit and two twelve-digit occurrences.

The archive does **not** infer missing leading zeroes, truncate values, or otherwise repair these identifiers. The source value remains in `identifier_field_raw`; only identifiers satisfying the existing conservative normalisation rule enter the normalised `identifiers` array.

## Population-scope assessment

For this source check:

- official White List surface found: **yes**;
- current registered-company population found: **yes**;
- current applicant population found: **yes**;
- all population scopes represented: **yes**;
- all current resources needed for the ordinary Alessandria register found: **yes**.

The current edition therefore supports a complete ordinary listed/applicant treatment for Alessandria under the archive's positive-evidence rules. This statement concerns the two populations exposed by the official surface; it does not infer anything about unpublished material.

## Reproducibility evidence

Exploratory live-source CI runs used to resolve and characterise the two current resources:

- https://github.com/colazeta/italian-anti-mafia-whitelist/actions/runs/34405433472
- https://github.com/colazeta/italian-anti-mafia-whitelist/actions/runs/34405623120

Both exploratory runs were intentionally fail-signalled after emitting source diagnostics and are not acceptance gates. The permanent parser/configuration changes are required to pass normal repository tests and the public portal regression before merge.
