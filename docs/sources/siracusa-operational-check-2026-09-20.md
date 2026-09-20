# Siracusa White List operational check — 20 September 2026

## Current official surface

Official landing page: `https://prefettura.interno.gov.it/it/prefetture/siracusa/evidenza/white-list`.

The current official landing was directly resolved on 20 September 2026. It positively and separately exposes `Elenco società iscritte` and `Elenco società richiedenti`. The landing reports an update on 3 September 2026. That landing-update date is used as the observation/reference boundary for this current-source snapshot; it is not treated as an individual legal-effect date and no registration date is inferred from PDF creation metadata or URL paths.

Two independent no-cache GETs of the landing were byte-identical (113,004 bytes; SHA-256 `2c0b5f2752f93151ef28c2f9c0c2a2ffc177b8131233b46547a5d65ac96be0b9`). Each resolved attachment was then independently fetched twice and required to be byte-identical before parser work proceeded. Failed future fetches must not be interpreted as evidence that either population is unpublished.

## Approved current resources

### Registered-company population

- resource: `https://prefettura.interno.gov.it/sites/default/files/94/2026-08/Elenco%20societ%C3%A0%20iscritte%20White%20List_0.pdf`
- observation/reference date: 3 September 2026 (official landing update)
- SHA-256: `fbfc6107894afd0b2ef8c2aba9eb00a60f4949c947c25b0d28eaa4286e6769ba`
- bytes: 759,667
- pages: 81
- reviewed raw table segments after headers: 317
- reviewed company observations after merging two note-only continuation segments into their immediately preceding source rows: 315
- status distribution: 246 ordinary listed observations; 67 source-explicit renewal/update observations; 2 observations retained conservatively as `other_or_unknown`
- strict identifier coverage: 312/315
- expiry-date coverage after normalising only reviewed source typography: 315/315

The two continuation segments contain only source notes and are not independent companies. Their exact reviewed texts are `29.11.2022 Variazione assetto societario 16.01.2023 Istanza di rinnovo 13.09.2023 Istanza di rinnovo 09.09.2024 Istanza di rinnovo 09.10.2025` and `Istanza di rinnovo 04.10.2023`; both are retained in the preceding company's provenance.

Three identifier cells do not satisfy the repository's strict 11-digit/16-character identifier shapes and therefore remain raw without canonical reconstruction: `0598740823` (ECO AMBIENTE ITALIA S.R.L.), `RANN` (ITALSCAVI di CALAFIORE MARIACONCETTA) and `013413108912` (METROSERVICE S.R.L.). Two expiry cells use reviewed single-digit-month typography, `13.8.2026` and `18.6.2024`; only their explicit digits are normalised to ISO dates while the original cells remain in provenance.

The two `other_or_unknown` observations are intentionally not converted into a legal outcome. CAMO S.R.L. carries only the source note `06.08.2026`; ECO AMBIENTE ITALIA S.R.L. states that an application for cancellation due to transfer of registered office to another province was filed on 6 May 2026. Filing that application does not, by itself, evidence a completed cancellation.

### Applicant population

- resource: `https://prefettura.interno.gov.it/sites/default/files/94/2026-09/ELENCO%20RICHIEDENTI%20ISCRIZIONE-W.L_1.pdf`
- observation/reference date: 3 September 2026 (official landing update)
- SHA-256: `74f4cf251ebd7903d47ebfa6fd134f9228990d76f50aabb4b39fbec1e6a903a9`
- bytes: 311,715
- pages: 27
- reviewed observations: 104
- status: 104 `pending`, supported by the explicit applicant-publication identity
- strict identifier coverage: 102/104
- normalised application-date coverage: 103/104

Two applicant identifier cells remain raw because they do not satisfy strict canonical shapes: `0213450897` (C & SA S.R.L.) and `10988791215 *` (J&J MAINTENANCE, INC.). The malformed application-date cell `17.01/2024` for DI TOMMASI FRANCESCO S.R.L. is retained verbatim but deliberately produces no normalised date; the separator is not silently repaired.

Eight additional application-date cells contain a clean leading `dd.mm.yyyy` date followed by source text or a second date. Only the leading source-explicit date is typed as the application date, while each complete cell is retained in provenance. No later `Perfezionata`, `Integrata` or second-date value is substituted for the original application date.

## Parser boundary

The registered-company PDF is a stable seven-column table repeated on 81 pages: company name, registered office, secondary office, identifier, activity sections, expiry date and notes. The parser requires exactly one reviewed table per page, the reviewed headers, 317 nonblank data segments, exactly the two approved note-only continuations, 315 resulting observations, the frozen status distribution and the frozen identifier/expiry coverage. Unreviewed date typography, table shape, continuation text or population counts fail closed.

The applicant PDF is a stable six-column table repeated on 27 pages: company name, registered office, secondary office, identifier, requested sections and application-date cell. The parser requires exactly 104 observations and freezes the reviewed annotated/malformed date variants, identifier coverage and application-date coverage. Applicant status comes from the positively identified applicant publication rather than from row-level inference.

Both resources are raw-byte pinned before parsing.

## Evidence boundary

This operational check validates the current public-source observation layer. It does not infer NOT_PUBLISHED, deletion, revocation, cancellation, denial or any other legal effect from source absence, malformed cells or future retrieval failure. Canonical/public integration remains contingent on parser validation, national build gates and the normal post-merge live verification sequence.
