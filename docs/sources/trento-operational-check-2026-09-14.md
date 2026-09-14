# Trento White List operational check — 2026-09-14

## Scope

This note records the current official Commissariato del Governo per la Provincia di Trento White List publication boundary and the source evidence captured before parser implementation. Row-level denominators and parser semantics remain fail-closed until the complete structure audit is finished.

## Official publication surface

The official Trento White List publication positively separates the registered-company and requesting-company populations. The two current official pages were revalidated on 14 September 2026:

- registered companies: `https://prefettura.interno.gov.it/it/prefetture/trento/white-list-elenco-imprese-iscritte`;
- requesting companies: `https://prefettura.interno.gov.it/it/prefetture/trento/white-list-elenco-imprese-richiedenti`.

The registered-company page currently exposes **“ELENCO IMPRESE ISCRITTE ALL'11 SETTEMBRE 2026”** and reports page update time 11 September 2026 at 11:04. The requesting-company page exposes **“ELENCO IMPRESE RICHIEDENTI AL 10 SETTEMBRE 2026”** and reports page update time 10 September 2026 at 13:47. These are separate positive population anchors; the applicant population is not inferred from absence or search failure.

A temporary GitHub Actions capture gate performed two independent GETs of each official attachment on 14 September 2026. Each pair was byte-identical, both resources had a valid PDF magic header, and `pdfinfo` confirmed the page counts below. The successful source-capture run is `34890395921`. The temporary workflow is diagnostic only and must be removed before any production PR.

## Current registered-company source

- Positive-evidence anchor: `ELENCO IMPRESE ISCRITTE ALL'11 SETTEMBRE 2026`
- Resource URL: `https://prefettura.interno.gov.it/sites/default/files/86/2026-09/imprese-iscritte-11-settembre-2026.pdf`
- Media type: `application/pdf`
- Size: **7,663,549 bytes**
- SHA-256: `b831570c01220b8709ebf9c4dbdfe856aba37a21c46353cf7bc9eedb5965c8af`
- PDF pages: **289**
- `pdftotext -layout` lines: **10,411**
- The second independent GET returned the same bytes and SHA-256.

Preliminary inspection shows a sectioned table with the recurring source columns `Ragione Sociale`, `Sede legale`, `Sede secondaria con rappresentanza stabile in Italia`, `Codice fiscale/Partita IVA`, `Data di iscrizione`, `Data scadenza iscrizione`, and `Aggiornamento in corso`. `AGGIORNAMENTO IN CORSO` is an explicit source marker and must not be reconstructed from expiry dates. The listed source spans statutory White List sections and repeats companies where they belong to multiple sections, so public-observation grouping must be established from the complete source audit rather than from unique identifiers alone.

The final PDF page is a source-formatted trailing page with no visible company row. This observation is not yet a denominator rule; the complete `pdfplumber` audit must freeze the table/page boundary before parser implementation.

## Current requesting-company source

- Positive-evidence anchor: `ELENCO IMPRESE RICHIEDENTI AL 10 SETTEMBRE 2026`
- Resource URL: `https://prefettura.interno.gov.it/sites/default/files/86/2026-09/imprese-richiedenti-10-settembre-2026.pdf`
- Media type: `application/pdf`
- Size: **384,118 bytes**
- SHA-256: `9f36797e3e11834c979f9b5f5d58d693e19fa2456c69ce5859628d4e56a056c0`
- PDF pages: **22**
- `pdftotext -layout` lines: **752**
- The second independent GET returned the same bytes and SHA-256.

Preliminary inspection shows the recurring columns `Ragione sociale`, `Sede legale`, `Sede secondaria con rappresentanza stabile in Italia`, `Codice Fiscale/P.IVA`, `Attività per cui è richiesta l’iscrizione`, `Data di presentazione dell’istanza`, and `Esito`. Visible rows include multi-line activity descriptions and page-spanning continuations. The `Esito` field is visibly blank in the sampled current rows; the parser must nevertheless audit the entire finite source before assigning a source status and must not mechanically assume that all historic applicant rows are pending.

At least one application-date cell contains additional source text — `29.06.2026 (integrata il 02.07.2026)` — so any normalised primary date must remain separate from the complete raw source value and no generic date repair is permitted.

## Parser-design boundary

The next gate is the exhaustive table-structure audit over the exact byte-pinned PDFs above. Before a production parser is accepted it must establish and freeze, at minimum:

- exact table counts, physical rows and logical company/section rows across all 289 listed pages and all 22 applicant pages;
- exact statutory-section boundaries and source-row denominators for the listed population;
- the conservative grouping key, if repeated section membership is collapsed into one public observation, with conflict checks demonstrating that no differing source semantics are merged;
- exact continuation fragments and any page-leading/page-trailing fragments in the applicant source;
- complete status/outcome typography and finite date/identifier anomaly populations;
- strict identifier extraction with malformed or ambiguous raw values preserved rather than repaired;
- exact source SHA-256 and page-count checks before parsing.

No public row count, completeness claim, `NOT_PUBLISHED` state, legal status or applicant outcome is asserted by this note before those finite boundaries are validated. Canonical hosted-database integration and independent durable-evidence verification remain separate controls.