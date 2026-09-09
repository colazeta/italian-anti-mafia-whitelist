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
- extracted source sector rows: `670`
- grouped public observations: `363`
- section headers observed: `SEZIONE I` through `SEZIONE X`
- source outcomes across sector rows: `406` blank, `245` `In istruttoria per rinnovo`, `5` upper-case `IN ISTRUTTORIA PER RINNOVO`, `8` bare `In istruttoria`.

The source repeats the same company across numbered sectors. Rows are grouped only when source company name, source identifier, source outcome **and normalised date pair** coincide. Sector memberships, registered-office variants and raw date variants are retained. A bare `In istruttoria` note inside this registered-company document is kept as `other_or_unknown`; it is not silently reclassified as a renewal or an applicant record.

A second live-source audit was run after the first parser attempt exposed four dropped rows. It established that the complete listed document contains **670** company/sector rows and **359** distinct company-identifier-outcome groups. Four of those identity/outcome groups contain two different date pairs. Because the archive does not infer which source date is correct, those four groups remain split by their stated date pair, producing **363 source-backed public observations**. This preserves the association between each date pair and its sector rows rather than collapsing conflicting facts into a single synthetic record.

The following source-date handling is explicit and conservative:

- ordinal typography after day `1` (for example `1°.5.2025`) is normalised as the visibly stated date; the raw source value is retained;
- a single layout-extraction space inside a four-digit year (`1°.12.202 2`) is removed because all four source digits are present; the raw source value is retained;
- the calendar-invalid source value `65.5.2026`, observed twice for `EDIL SINA S.R.L.` (`02614330062`), is never repaired. The same company/identifier/outcome is repeated elsewhere in the same official source with exactly one complete clean date pair (`6.5.2025` / `5.5.2026`), so the malformed repetitions can be attached to that unique source-backed observation while their raw malformed value remains in provenance;
- where the same company/identifier/outcome has more than one complete date pair, each complete pair is retained as a distinct observation. No value is selected by plausibility and no conflicting pair is discarded;
- if an invalid row were ever associated with more than one possible complete pair for the same identity/outcome, the parser would leave that row unresolved and the existing `dropped_date_rows` gate would block publication.

The four conflict groups observed on 2026-09-09 are:

1. `FERRANDO MAURO IMPRESA INDIVIDUALE` (`01904830062`): listing variants `5.8.2025` and `5.8.2026`; expiry `4.8.2026`;
2. `ISOLTRASPORTI S.N.C.` (`01363250067`): listing `18.6.2026`; expiry variants `17.6.2027` and `17.7.2027`;
3. `GESTIONE AMBIENTE S.P.A.` (`01492290067`): listing `15.04.2025`; expiry variants `13.04.2026` and `14.04.2026`;
4. `T.S.L. TRASPORTI S.R.L.` (`01273050052`): listing `29.4.2025`; expiry variants `28.4.2026` and `29.4.2026`.

This treatment is intentionally observation-level rather than entity-level: the public archive reports what the official source states and does not resolve source inconsistencies that would require an external evidentiary basis.

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
- https://github.com/colazeta/italian-anti-mafia-whitelist/actions/runs/34407888680
- https://github.com/colazeta/italian-anti-mafia-whitelist/actions/runs/34408068745

The exploratory characterisation runs were intentionally fail-signalled after emitting source diagnostics and are not acceptance gates. Their findings are pinned by deterministic parser tests. The permanent parser/configuration changes must pass normal repository tests and the public portal regression before merge. At the audited counts, Alessandria contributes 363 listed observations plus 71 applicant observations; if accepted, the public national registry denominator becomes 5,486 observations across five Prefectures and six registers.
