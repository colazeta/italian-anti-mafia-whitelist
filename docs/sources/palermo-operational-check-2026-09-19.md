# Palermo operational source check — 2026-09-19

## Official source surface

Authority: Prefettura di Palermo — Ufficio Territoriale del Governo.

Official landing page:

- `https://prefettura.interno.gov.it/it/prefetture/palermo/evidenza/white-list`

The landing page positively exposes two distinct populations and therefore supports a complete listed/applicant treatment; no population is inferred from search failure or absence.

## Listed population

Landing label: `Whitelistelencounicoimpreseiscritte`

Official resource:

- `https://prefettura.interno.gov.it/sites/default/files/61/2026-09/whitelistelencounicoimpreseiscritte_10.pdf`

Two independent cache-bypassed GETs on 2026-09-19 returned identical bytes:

- bytes: `1,558,757`
- SHA-256: `2349d3ae3dcd37e5da7fc5fdec1326a9408e00fcc0b3b78b0a0809ad75c0837f`
- HTTP `Last-Modified`: `Fri, 18 Sep 2026 11:11:27 GMT`
- ETag: `"17c8e5-65bbff62b230f"`
- PDF pages: `55`
- document marker: `Ultima modifica: 18/09/2026`

The source has 929 observable company rows. Source numbering runs to 931 but omits `N° 252` and `N° 316`; those two numbering gaps are preserved as source anomalies rather than repaired. The parser boundary is 486 `listed` and 443 `renewal_update_in_progress` observations. Nine identifier fields are malformed as printed; structured identifiers remain available for 924/929 observations. Two printed expiry values (`N° 247: 28/072027`; `N° 577: 20/072027`) are preserved raw but not normalised to dates. The special note on `N° 926` concerning a collaborative prevention measure is preserved as source evidence and is not reinterpreted as a different legal status.

## Applicant population

Landing label: `elencoimpreserichiedentiliscrizione-1.pdf`

Official resource:

- `https://prefettura.interno.gov.it/sites/default/files/61/2026-09/elencoimpreserichiedentiliscrizione-1_0.pdf`

Two independent cache-bypassed GETs on 2026-09-19 returned identical bytes:

- bytes: `1,017,501`
- SHA-256: `82dd288c21c85ea563c75cbfc8346c528b603e54c3a78283a0ae67983e97f2f5`
- HTTP `Last-Modified`: `Thu, 17 Sep 2026 11:15:44 GMT`
- ETag: `"f869d-65babe7a94b66"`
- PDF pages: `58`
- document marker: `Ultima modifica: 17/09/2026`

The source contains 609 sequential applicant observations. All carry a positive in-proceedings outcome, with nine observed spelling/capitalisation variants frozen into the parser vocabulary rather than silently corrected. Five identifier fields are malformed as printed and one observation (`N° 470`) has no VAT/fiscal identifier in the source; structured identifiers remain available for 606/609 observations. `N° 98` prints `Via Ravenna n.7` in the source's secondary-office column while its address column is blank; the parser preserves that column placement rather than moving the value inferentially.

## Parser and integrity policy

The dedicated `palermo_positioned` parser uses PDF word geometry and explicit x-bands. It fails closed on page count/geometry, document-date markers, page denominators, source row numbering, outcome vocabulary, source section cells, identifier-anomaly boundaries, expiry anomalies and structured-identifier coverage. Registered office locality and the printed address column are joined only as a presentation-preserving office string; the source's secondary-office column remains separate. Activities are emitted as explicit source section numbers (`Sezione 1` … `Sezione 10`) without inventing semantic labels beyond what the source marks.

The temporary source-probe workflow and its short-retention artifact are implementation evidence only and must be removed before a reviewable expansion PR. Permanent publication must pin the two resource URLs and SHA-256 values above and continue to fail closed if future bytes drift.
