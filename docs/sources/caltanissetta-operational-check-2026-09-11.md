# Caltanissetta White List operational check — 11 September 2026

## Current official surface

Official landing page: `https://prefettura.interno.gov.it/it/prefetture/caltanissetta/evidenza/white-list`.

The current official landing page was directly resolved on 11 September 2026. It positively and separately exposes the registered-company and applicant populations. The page itself was updated on 10 September 2026 and both current attachments are explicitly dated 9 September 2026. No population status is inferred from search failure.

## Approved current resources

### Registered-company population

- resource: `https://prefettura.interno.gov.it/sites/default/files/19/2026-09/elenco-delle-imprese-iscritte-nella-white-list_09.09.2026.pdf`
- reference date: 9 September 2026
- SHA-256: `539285d8096c25c3f1d38ba7bb0d4cc33eb10e6de5ca24b268b1c7d2f31abb74`
- bytes: 874,167
- pages: 55
- reviewed source observations: 518
- status distribution: 281 ordinary listed observations; 232 explicit `In corso di aggiornamento`; 5 source-explicit special-condition observations retained conservatively as `other_or_unknown`
- strict identifier coverage: 515/518

The five special-condition observations are four rows carrying `Misura di prevenzione collaborativa ex art. 94 bis del D. Lgs. 159/2011` and one row carrying `SOSPESA (in corso di accertamenti)`. They are not reclassified as ordinary listed observations. The source has no duplicate observation under the audited identity/address/date/activity/status key.

Three malformed-length numeric identifier values are retained verbatim but are never promoted to canonical identifiers: `020826508502` (A2G CONSTRUCTION SRL), `0143890854` (EDILTECNICA COSTRUZIONI SRL) and `0206772085` (FARRUGGIA SALVATORE). Source date relationships are not repaired or regularised; for example, any apparent registration/expiry inconsistency remains source provenance.

### Applicant population

- resource: `https://prefettura.interno.gov.it/sites/default/files/19/2026-09/elenco-delle-imprese-richiedenti-iscrizione-nella-white-list_09.09.2026.pdf`
- reference date: 9 September 2026
- SHA-256: `7c8b43dee53dc478d4a59d7e3d60763155814551cfc88811a398d82433d84954`
- bytes: 940,406
- pages: 67
- reviewed source observations: 288
- status: 288 `pending`, supported by the explicit applicant-list publication identity
- strict identifier coverage: 285/288

The applicant table contains one reviewed date annotation (`12/12/2016 (variazione compagine societaria)`). The date is parsed as 12 December 2016 while the parenthetical annotation is retained separately in source provenance. The malformed-length values `0583920965` (EDIL S.A.F. SRL) and `0208546051` (NUOVA TRASPORTI SRL), and the blank identifier for EDILSOMMY 2011 SRL UNIPERSONALE, remain raw and are never reconstructed.

## Parser boundary

The registered-company PDF is a stable eight-column table with company name, registered office, secondary office, identifier, registration date, expiry date, activity and source-status note. The parser requires the approved 55-page document and exactly 518 reviewed dated rows. It validates the frozen status and identifier-coverage denominators.

The applicant PDF is a stable six-column table after its legal notice: company name, registered office, secondary office, identifier, requested activities and application date. The parser requires the approved 67-page document and exactly 288 reviewed dated rows. Applicant status comes from the positively identified applicant publication, not from an inferred row outcome.

Both current resources are raw-byte pinned. Publication remains fail-closed on SHA-256 drift before parsing.

## Evidence boundary

This operational check validates the public-source observation layer only. Canonical hosted-database integration and independent durable-evidence verification remain separately governed under issue #16. No claim is made that a failed future fetch means a population is not published or that the current list is unchanged.
