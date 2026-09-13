# Frosinone White List operational check — 2026-09-13

## Scope

This checkpoint records positive current-source evidence for the Prefettura di Frosinone and freezes the byte identity of the current listed and applicant publications. It does **not** yet approve parser binding, population completeness, company-observation loading, or public export.

## Official publication surface

- Official landing page: `https://prefettura.interno.gov.it/it/prefetture/frosinone/evidenza/white-list`
- The landing page currently exposes two separate current publication populations, both labelled as updated **2 September 2026**:
  - listed companies: `https://prefettura.interno.gov.it/sites/default/files/9/2026-09/elenco-societa-iscritte-white-list-al-2-settembre-2026-aggiornato.pdf`
  - applicants: `https://prefettura.interno.gov.it/sites/default/files/9/2026-09/elenco-ric-iscr-white-list-aggiornato-al-2-settembre-2026-ordine-alfabetico-ok.pdf`
- The official landing page reports its own last update as **3 September 2026, 13:28** and also exposes earlier paired listed/applicant editions. The current population identity therefore rests on positive official publication evidence, not on filename prediction or absence-based inference.

## Content-addressed capture

A GitHub-hosted audit downloaded each current PDF twice from its official URL, validated HTTP 200 and PDF magic, and obtained byte-identical repeat fetches.

| population | bytes | pages | SHA-256 |
| --- | ---: | ---: | --- |
| listed | 1,230,003 | 91 | `aad166b49393055a197b9b1fef4eba82d0a70453a90d84209f967180d2855d71` |
| applicants | 775,657 | 37 | `9906d55864f4c1dc8e027efa2b44fa2c6463c512fb34241a32aa9b21a5ba6db8` |

The temporary audit report is `tmp/frosinone_source_audit.json`. These hashes bind all subsequent parser/layout work to the reviewed 2 September 2026 source bytes.

## Preliminary document-structure review

### Listed population

The current listed PDF reports 91 pages. Its table surface includes the fields `DENOMINAZIONE DITTA`, `SEDE LEGALE`, `CODICE FISCALE / PARTITA IVA`, `DATA DI ISCRIZIONE`, `DATA SCADENZA ISCRIZIONE`, `SEZIONI`, and `NOTE`.

The preliminary review positively observes both ordinary listed rows and rows whose notes state `Aggiornamento in corso per richiesta a permanere ...`. It also exposes source irregularities that must be preserved rather than silently repaired, including split identifiers, wrapped rows, duplicated-looking company rows and malformed or internally unusual date strings.

### Applicant population

The current applicant PDF reports 37 pages. Its table surface includes the fields `RAGIONE SOCIALE`, `SEDE LEGALE`, `SEDE SECONDARIA CON RAPPRESENTANZA STABILE IN ITALIA`, `CODICE FISCALE / PARTITA IVA`, `SEZIONI`, `DATA DI PRESENTAZIONE DELL’ISTANZA`, and `ESITO`.

The preliminary review predominantly observes `ISTRUTTORIA IN CORSO`, while also revealing literal source anomalies and blanks (for example misspelled status text and at least one observed row with blank outcome/date fields). Any parser must therefore bind only reviewed source semantics and fail closed on unreviewed variants; no missing legal status may be inferred.

## Gate state

At this checkpoint:

- `source_verified`: **true**, on positive official landing-page evidence;
- `current_edition_identified`: **true** for both listed and applicant publications dated 2 September 2026;
- content SHA-256: **frozen** for both current publications as above;
- repeat-fetch byte identity: **verified** for both current publications;
- `population_scopes_complete`: **not yet asserted** pending full layout/status review;
- parser family: **not yet bound**;
- record counts: **not yet asserted**;
- public export: **not approved**.

The next gate is a full-document layout/status audit over these exact hashes. Source irregularities, malformed values and duplicate-looking rows must remain evidence, not prompts for inferential repair.

A failed fetch in a later capture attempt must be recorded as an external retrieval failure and must not be converted into `NOT_PUBLISHED`, a missing applicant population, or any other negative publication claim.
