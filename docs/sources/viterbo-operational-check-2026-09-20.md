# Viterbo White List operational check — 2026-09-20

## Positive official-source evidence
- Official landing: `https://prefettura.interno.gov.it/it/prefetture/viterbo/elenco-imprese-richiedenti-iscrizione-elenco-imprese-iscritte`
- Landing content type: `text/html`; first SHA-256 `cb8c7767e48390a0dc8e7185fcd7e233ef1bcafed9a26ae6d23edddfe1edd8f3`; cache-bypassed second SHA-256 `c0e4ab2a26e6d1908f4d54a0441d0b5bcceaa2a29f9bb448784968b7d2e365c2`.
- The official page positively labels both `imprese richiedenti iscrizione` and `imprese iscritte`; no population is inferred from failed discovery.
- Public page metadata reports last update 2 September 2026.

## Independently re-fetched attachments
- **imprese iscritte in white list**
  - URL: `https://prefettura.interno.gov.it/sites/default/files/87/2026-09/iscritte_4.pdf`
  - content type: `application/pdf`; bytes: `684901`; magic: `255044462d312e37`
  - SHA-256: `ee6bdb1f9020689ae4e24d91397cdf07e7bf17999a85f4f2620eb127541f2e78`
  - independent second SHA-256: `ee6bdb1f9020689ae4e24d91397cdf07e7bf17999a85f4f2620eb127541f2e78`; byte-identical: `true`
- **imprese richiedenti iscrizione**
  - URL: `https://prefettura.interno.gov.it/sites/default/files/87/2026-09/richiedenti_4.pdf`
  - content type: `application/pdf`; bytes: `101066`; magic: `255044462d312e37`
  - SHA-256: `a0a2280f4c4352e29997ab3b5b532500f1a7d5eb57b5e44f82a62515ac66a545`
  - independent second SHA-256: `a0a2280f4c4352e29997ab3b5b532500f1a7d5eb57b5e44f82a62515ac66a545`; byte-identical: `true`

## Methodological boundary
This checkpoint establishes current first-party listed/applicant source availability and byte identity only. It does not yet assert parser denominators, legal status beyond source text, canonical completeness, or public integration. Malformed values must remain uninterpreted until parser validation.

## Parser boundary

Production validation freezes 237 listed observations plus 23 applicant observations (260 total). Listed statuses are 190 `listed` and 47 `renewal_update_in_progress`; all 23 applicants are `pending`. Structured identifier coverage is 235/237 listed and 23/23 applicants. The two nonconforming listed source identifiers `BNMGLC74C265C773P` and `0226497056` are preserved raw and are not padded, truncated or otherwise repaired. Source page 96 repeats `Sez 05 - Noli a caldo` exactly; the parser collapses only that exact same-section/same-text duplicate within the single company form, and fails closed if a repeated section carries different text or if the frozen duplicate boundary changes.

The national candidate builder subsequently validates exactly 260 Viterbo public observations with 258 structured identifiers, unique record locators, two source series and one ordinary register.
