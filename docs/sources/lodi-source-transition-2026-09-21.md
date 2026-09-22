# Lodi applicant source transition — 21 September 2026

## Scope and official publication surface

This review is limited to the `lodi-applicants` series already positively identified from the official Prefettura di Lodi White List landing page. On 21 September 2026 the landing page returned HTTP 200 and continued to expose both the registered-company and requesting-company publication surfaces. Publication is therefore established positively; no applicant population, withdrawal, legal status or completeness is inferred from search results or failed retrievals.

The applicant source is a mutable Google Sheet and exposes no reliable edition date. **21 September 2026 is therefore an observation/capture boundary, not an inferred publication date.** The listed series remains independently pinned to its 18 September 2026 observation boundary.

## Same-day source evolution

The previously approved applicant capture was SHA-256 `55aeab7e809cb90cc1ebd1ad9c1f08db78e91648a2c2e1a2b603188c77846228` with eight physical rows and four applicant observations.

During the 21 September review, two independent cache-bypassed captures at approximately 10:06:54 and 10:06:57 UTC were byte-identical at SHA-256 `e9db317df7f604c85e58fed6bfa023117146ad6cde39264f103e9cf73418b9a9` (1,765 bytes, nine physical rows). That intermediate snapshot added `ARS CHEMICA S.r.l.` and produced five applicant observations. Before this state was promoted canonically, the mutable official Sheet advanced again.

A later fail-closed source probe at approximately 10:31:19 and 10:31:22 UTC acquired two more byte-identical HTTP 200 responses at SHA-256 `c200e90a0410ba23fddee9d3ad0a5ac1532fec8dedfe0ec983eb2e94d0601a16` (2,151 bytes, ten physical rows). A separate read-only audit then independently repeated the capture at approximately 10:32:22 and 10:32:25 UTC and obtained the **same SHA-256 `c200e90a0410ba23fddee9d3ad0a5ac1532fec8dedfe0ec983eb2e94d0601a16` both times**. Across those two later workflow attempts, four independent current-source captures therefore agree byte-for-byte. The audit also re-verified the official landing page and its positive listed/applicant publication labels.

The intermediate `e9db317df7f604c85e58fed6bfa023117146ad6cde39264f103e9cf73418b9a9` snapshot is retained as observed provenance, but it is not promoted as the current canonical source boundary because it was superseded before permanent integration.

## Current reviewed applicant population

The current `c200e90a0410ba23fddee9d3ad0a5ac1532fec8dedfe0ec983eb2e94d0601a16` CSV has ten physical rows, seven columns throughout and six source-backed applicant observations:

1. `C.F. S.r.l.` — identifier `03554730790`, application 02/03/2021, explicit denial dated 17/06/2021;
2. `PAOLO GOMME TRASPORTI S.r.l.` — identifier `02155610187`, application 26/10/2021, explicit denial dated 17/11/2022;
3. `EAL COMPOST S.r.l.` — identifier `12220770155`, application 06/11/2025, `IN ISTRUTTORIA`;
4. `M.B. IMPIANTI S.r.l.s.` — identifier `13973560967`, application 07/09/2026, `IN ISTRUTTORIA`;
5. `ARS CHEMICA S.r.l.` — identifier `04087190965`, application 18/09/2026, `IN ISTRUTTORIA`;
6. `BRONCO COPERTURE S.r.l.` — identifier `01711850220`, legal office `Via Togliatti, n. 2/I - Casalpusterlengo (LO)`, application 21/09/2026, `IN ISTRUTTORIA`.

The status boundary is therefore two `rejected_or_denied` and four `pending`. No legal interpretation is added to the source wording. Addresses remain source-faithful subject only to the project’s conservative normalisation rules.

## Canonical transition proposed by this checkpoint

- listed series: unchanged at SHA-256 `a9f6a0977ce0d1a26a6a86450643496cc70f2a1a3eba017e89812eb6f203276e`, 169 public records, observation boundary 18 September 2026;
- applicant series: `55aeab7e809cb90cc1ebd1ad9c1f08db78e91648a2c2e1a2b603188c77846228` → current `c200e90a0410ba23fddee9d3ad0a5ac1532fec8dedfe0ec983eb2e94d0601a16`;
- intermediate positively observed applicant snapshot retained in monitoring provenance: `e9db317df7f604c85e58fed6bfa023117146ad6cde39264f103e9cf73418b9a9`;
- applicant records: 4 → 6;
- Lodi public records: 173 → 175;
- Lodi status boundary: 144 `listed`, 25 `renewal_update_in_progress`, 4 `pending`, 2 `rejected_or_denied`;
- national candidate over the separately reviewed Milano correction: 73,670 records / 72 authorities / 75 registers / 72 mapped-published.

The parser keeps the listed and applicant `reference_date` values separate so that refreshing the mutable applicant series cannot falsely re-date the unchanged listed series.
