# Frosinone White List operational check — 2026-09-13

## Scope

This checkpoint records positive current-source evidence for the Prefettura di Frosinone. It does **not** yet approve parser binding, population completeness, company-observation loading, or public export.

## Official publication surface

- Official landing page: `https://prefettura.interno.gov.it/it/prefetture/frosinone/evidenza/white-list`
- The landing page currently exposes two separate current publication populations, both labelled as updated **2 September 2026**:
  - listed companies: `https://prefettura.interno.gov.it/sites/default/files/9/2026-09/elenco-societa-iscritte-white-list-al-2-settembre-2026-aggiornato.pdf`
  - applicants: `https://prefettura.interno.gov.it/sites/default/files/9/2026-09/elenco-ric-iscr-white-list-aggiornato-al-2-settembre-2026-ordine-alfabetico-ok.pdf`
- The official landing page reports its own last update as **3 September 2026, 13:28** and also exposes earlier paired listed/applicant editions. The current population identity therefore rests on positive official publication evidence, not on filename prediction or absence-based inference.

## Preliminary document-structure review

A live document parse confirms that both current resources are PDFs and contain structured tabular populations.

### Listed population

The current listed PDF reports 91 pages. Its table surface includes the fields `DENOMINAZIONE DITTA`, `SEDE LEGALE`, `CODICE FISCALE / PARTITA IVA`, `DATA DI ISCRIZIONE`, `DATA SCADENZA ISCRIZIONE`, `SEZIONI`, and `NOTE`.

The preliminary review positively observes both ordinary listed rows and rows whose notes state `Aggiornamento in corso per richiesta a permanere ...`. It also exposes source irregularities that must be preserved rather than silently repaired, including split identifiers, wrapped rows, duplicated-looking company rows and malformed or internally unusual date strings.

### Applicant population

The current applicant PDF reports 37 pages. Its table surface includes the fields `RAGIONE SOCIALE`, `SEDE LEGALE`, `SEDE SECONDARIA CON RAPPRESENTANZA STABILE IN ITALIA`, `CODICE FISCALE / PARTITA IVA`, `SEZIONI`, `DATA DI PRESENTAZIONE DELL’ISTANZA`, and `ESITO`.

The preliminary review predominantly observes `ISTRUTTORIA IN CORSO`, while also revealing literal source anomalies and blanks (for example misspelled status text and at least one observed row with blank outcome/date fields). Any parser must therefore bind only reviewed source semantics and fail closed on unreviewed variants; no missing legal status may be inferred.

## Gate state

Before this Prefecture can advance beyond reconnaissance, the current source bytes must be captured repeatably and content-addressed. A valid capture requires two independent downloads of each current official PDF in the same run, PDF validation, matching SHA-256 values and byte identity. Only after that gate may the full documents be audited for row boundaries, status taxonomy and parser invariants.

At this checkpoint:

- `source_verified`: positive landing-page evidence only;
- `current_edition_identified`: positive for both listed and applicant publications dated 2 September 2026;
- content SHA-256: **not yet frozen**;
- `population_scopes_complete`: **not yet asserted**;
- parser family: **not yet bound**;
- record counts: **not yet asserted**;
- public export: **not approved**.

A failed fetch in a later capture attempt must be recorded as an external retrieval failure and must not be converted into `NOT_PUBLISHED`, a missing applicant population, or any other negative publication claim.
