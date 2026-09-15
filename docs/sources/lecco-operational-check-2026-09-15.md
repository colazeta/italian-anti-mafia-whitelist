# Lecco White List operational check — 15 September 2026

## Official publication surface

The current official Prefettura di Lecco page was verified directly at:

- `https://prefettura.interno.gov.it/it/prefetture/lecco/white-list-elenco-imprese-iscritte`

Two independent GETs returned the same 82,173-byte HTML response with SHA-256 `f1f50685df3aeb0036e5879c85f9f607b5fb6595272c1067b7bbd34a116636fe`.

The page positively exposes two distinct current publication series, both labelled `aggiornato al 14.09.2026`:

1. **Allegato A / listed population** — `All.A aggiornato al 14.09.2026`
   - resource: `https://prefettura.interno.gov.it/sites/default/files/56/2026-09/all_a-attivita-elenco-ditte-non-soggette-a-tentativo-infiltr_mafiosa_2.pdf`
   - SHA-256: `80c439521cf2bd4062b54fff3646666487367f0f8b47c1a91a6c8f62bcf8e5bc`
   - bytes: 448,763
   - pages: 19
2. **Allegato B / applicant population** — `All.B aggiornato al 14.09.2026`
   - resource: `https://prefettura.interno.gov.it/sites/default/files/56/2026-09/all_b-attivita-elenco-ditte-richiedenti-iscrizione_2.pdf`
   - SHA-256: `7c24e015342cc2cb61cf4b5bf726621c8b3b90b195cd91c40942fc3ef6b6ba5b`
   - bytes: 235,376
   - pages: 4

Each attachment was acquired twice independently during this check. The paired captures were byte-identical. The 14 September date is treated as the current source-edition/reference date only; it is not inferred to be an individual company decision or legal-effect date.

## Source structure and denominator

Both PDFs are Word-exported tables. Their logical table cells are represented by filled white PDF rectangles; text-line subdivisions are nested inside those cells. The Lecco parser therefore binds to the byte-pinned logical-cell geometry rather than joining text lines heuristically across company rows.

### Allegato A

The current listed attachment yields **230 source-backed observations**. The source status distribution is:

- 201 `listed`;
- 29 `renewal_update_in_progress` (`Aggiornamento in corso`).

Two of the 201 listed observations carry the source-explicit text `Iscritta con Misura Collaborativa Ex Art. 94 Bis D.Lgs. 159/2011 per mesi 12`; this text is preserved in `outcome_raw` and is not converted into a different legal status.

Strict identifier coverage is **228/230**. The two malformed source identifiers are retained verbatim and deliberately not repaired:

- `BIGS di Ivan Chavarriaga` — `0416200136`;
- `Termoidraulica` — `035180050137`.

Source activity labels are preserved as printed, including unusual source typography such as `Sez. XIII`; no section correction is inferred.

### Allegato B

The current applicant attachment contains **26 application-event observations**. The source status distribution is:

- 22 `pending` (`In istruttoria` / case variation);
- 4 `rejected_or_denied` with source-explicit `Diniego di iscrizione` outcomes.

All 26 application events have strict valid identifiers. The denominator is event-level rather than company-level because the source contains repeated applications by the same company. In particular, `Edilnord S.r.l.` (`01882770132`) has three separately published applications and three separate denial outcomes:

- application 12.12.2013 → provvedimento n. 5864 del 31.03.2014;
- application 29.01.2016 → provvedimento n. 14507 del 29.08.2016;
- application 18.04.2017 → provvedimento n. 20237 del 01.12.2017.

These observations must not be collapsed. Where a denial outcome explicitly ends with a decision date, that printed date may be structured while the complete outcome remains preserved as raw provenance.

## Candidate publication boundary

The current defensible Lecco source boundary is therefore **256 observations**:

- 230 listed-series observations;
- 26 applicant-series application events;
- combined statuses: 201 `listed`, 29 `renewal_update_in_progress`, 22 `pending`, 4 `rejected_or_denied`.

No applicant population, status, date, identifier repair or completeness conclusion is inferred from search absence or failed retrieval. Publication remains fail-closed on the pinned byte identities and reviewed structural denominators.

## Integration state

At this checkpoint source verification and parser work are in progress on `expansion/lecco-2026-09-15`. National canonical/public integration is not yet validated. `canonical_integration_validated` and `durable_evidence_verified` therefore remain false; durable evidence infrastructure continues to be governed separately under issue #16.
