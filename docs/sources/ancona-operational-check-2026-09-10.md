# Ancona operational source check — 10 September 2026

## Official current publication

- Authority: Prefettura di Ancona.
- Official page: https://prefettura.interno.gov.it/it/prefetture/ancona/evidenza/white-list
- The page was independently re-verified on 10 September 2026 and exposes one attachment explicitly labelled as the list of both registered companies and companies requesting registration.
- The official page reports “Ultimo aggiornamento” on 7 September 2026; every page of the attachment carries the marker `Agg. al 07/09/2026`.
- Approved resource: https://prefettura.interno.gov.it/sites/default/files/0/2026-09/elenco_imprese_wl07-10-2026.pdf
- Approved byte SHA-256: `09d5ba7264ee6f0c6170273713881273c5d5a045cc9a4a49de3dd36c3860f88d`.

The resource filename is retained verbatim and is not interpreted as a date; the reference date is established from the official page and the repeated in-document marker.

## Parser boundary and denominators

The fail-closed parser requires 23 pages, an exact nine-column company table on every page, the repeated reference-date marker on every page, and the reviewed per-page row denominators. It yields exactly **577 source-backed observations**:

- 331 `listed`;
- 100 `renewal_update_in_progress`, only where the source says `Richiesto rinnovo`;
- 145 `pending`, only where the row has an application date and no listing-date pair within the official combined listed/applicant population;
- 1 `other_or_unknown`, because no positive status signal is present.

All 577 rows retain a non-empty raw identifier field. Four malformed source date tokens are retained verbatim in provenance and deliberately not repaired. The parser also contains narrowly anchored repairs for reviewed PDF table-boundary extraction errors; each repair checks the exact byte-pinned neighbouring cells and fails closed if layout or content drifts. No status, date digit, legal identifier or missing source value is invented.

## Publication decision

The combined current edition is sufficient for the published observation layer because the official attachment expressly covers both registered and applicant populations. The public export may therefore include these 577 observations after the repository-wide publication gates pass. Canonical hosted-database integration and independent durable-evidence verification remain separately governed under issue #16 and are not claimed complete here.
