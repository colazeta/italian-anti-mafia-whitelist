# Enna White List operational check — 22 September 2026

## Official source and current edition

The current official Prefettura di Enna White List landing page is:

- https://prefettura.interno.gov.it/it/prefetture/enna/evidenza/white-list

On 22 September 2026 the landing positively exposed the attachment labelled **“White list - Elenco aggiornato al 18/09/2026”** at:

- https://prefettura.interno.gov.it/sites/default/files/0/2026-09/wl-enna_3.pdf

The landing identified the current update as Friday 18 September 2026. Two independent cache-bypassed GETs of the attachment were byte-identical at **1,350,854 bytes** and SHA-256:

`1a5dc0bc8cd6eef69724c1afe767108abdecc325f7f01e8ef80620cca0d622c6`

The date 18 September 2026 is therefore used as the reviewed source reference boundary. No separate legal effect or completeness claim is inferred from that date.

## Population evidence

The exact pinned PDF is a combined listed-and-applicant publication. Page 1 explicitly carries the heading **“ELENCO DELLE IMPRESE RICHIEDENTI L'ISCRIZIONE …”** and a six-column applicant table. Pages 2–16 carry the listed-company table, organised into the ten White List activity sections.

The physical source boundary is:

- **41 applicant rows** on page 1;
- **1,028 listed company-by-section rows** across pages 2–16;
- **1,069 physical company rows** in total.

All 41 applicant rows expose a structured identifier, an application date and the explicit source outcome `IN ISTRUTTORIA`. The parser therefore maps these observations to `pending` solely from this source-explicit applicant/outcome evidence.

The listed rows expose company, registered office, identifier, listing date, expiry date and note. The only reviewed note values are blank and `[ 2 ]`. The source explicitly defines `[ 2 ]` as **`AGGIORNAMENTO IN CORSO`** in the relevant section layouts. The parser maps blank-note observations to `listed` and `[ 2 ]` observations to `renewal_update_in_progress`; unreviewed note or applicant-outcome vocabulary fails closed.

## Logical observation treatment

Listed enterprises are physically repeated across activity sections. The parser does not discard those memberships. It groups only exact normalised observations sharing company name, office, identifier, listing date, expiry date and note, while accumulating every section membership and page-row locator. Distinct date pairs or source-explicit notes remain distinct logical observations even when the identifier is the same.

This conservative grouping transforms the 1,028 physical listed rows into **474 logical listed observations** while preserving **1,028 listed section memberships**. Their source-status distribution is:

- **417 `listed`**;
- **57 `renewal_update_in_progress`**.

Together with the 41 applicant observations, the reviewed Enna public boundary is therefore **515 observations**, with status distribution:

- **417 listed**;
- **57 renewal/update in progress**;
- **41 pending**.

All **515/515** observations carry a structured identifier. No cross-population collapse is performed between the listed and applicant populations.

## Fail-closed parser boundary

`src/white_list_archive/parsers/enna_combined.py` pins and validates the reviewed boundary before producing records. In addition to the exact resource hash and byte length it asserts:

- 16 pages and exactly one extractable six-column table per page;
- exact applicant and listed header signatures;
- reviewed per-page row denominators;
- the reviewed page-to-section map for sections 1–10;
- strict identifier and date typography;
- applicant activity codes restricted to source-explicit section numbers 1–10;
- applicant outcome vocabulary restricted to `IN ISTRUTTORIA`;
- listed note vocabulary restricted to blank and `[ 2 ]`;
- source-explicit `AGGIORNAMENTO IN CORSO` legend wherever `[ 2 ]` is used;
- 474 logical listed observations, 41 applicant observations and 515 public observations;
- exact 417/57/41 public status distribution;
- 1,028 retained listed section memberships and 515/515 identifier coverage.

Any reviewed-boundary drift fails closed. Validation on 22 September 2026 re-fetched the official attachment twice and successfully parsed the exact current boundary before running the repository test suite.

## Interpretation limits

This integration records what the official Enna publication explicitly presents. It does not infer `NOT_PUBLISHED`, legal finality, publication completeness, adverse legal effects, or any status not expressed by the source. A missing separate applicant link is not interpreted as non-publication because the current combined PDF itself positively exposes the applicant population on page 1.
