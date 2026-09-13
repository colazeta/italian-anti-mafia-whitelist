# Gorizia White List operational check — 2026-09-13

## Scope

This checkpoint records positive current-source evidence for the Prefettura di Gorizia and freezes the current official source bytes. It does **not** yet approve a production parser, final observation counts, population completeness, national integration or public export.

## Official publication surface

- Official landing page: `https://prefettura.interno.gov.it/it/prefetture/gorizia/evidenza/white-list`
- Live verification on 13 September 2026 returned the official page successfully. The page reports its own last update as **17 August 2026, 12:37**.
- The landing page positively exposes two distinct current publication resources:
  - applicants, labelled `Ditte per cui è in corso la richiesta di iscrizione alla WhiteList`: `https://prefettura.interno.gov.it/sites/default/files/0/2026-08/2026.08-white-list-ditte-richiedenti-iscrizione.pdf`
  - listed companies, labelled `Elenco delle Ditte della provincia di Gorizia iscritte alla White List`: `https://prefettura.interno.gov.it/sites/default/files/0/2026-08/gorizia-elenco-ditte-iscritte-wl.docx`
- The applicant publication is a PDF and the listed publication is a DOCX. The official page therefore provides positive evidence for both logical populations; neither population is inferred from filename construction or search-engine absence.
- The exact reference date carried by each document has **not yet been established**. The August 2026 URL paths and the landing-page update timestamp are provenance signals, not substitutes for a document-level source date.

## Frozen capture

The two exact official resources were each fetched twice independently by the source-audit workflow. Both repeat captures were byte-identical and passed native-container validation.

- listed DOCX:
  - bytes: **108,574**
  - SHA-256: `680f0822f56ce7499a5d3f6c9e524d3d33b631feca51886e57e70fdf9e5fbd6d`
  - valid OOXML/ZIP container with required `[Content_Types].xml` and `word/document.xml`; **21** container entries
- applicant PDF:
  - bytes: **143,930**
  - SHA-256: `befe7ed054e0cfe9dda48c8dec59f843b569019e40b925d6d5d1fcec19021c7c`
  - valid PDF; **2 pages**

Any later source failure must be recorded as a retrieval failure. It must **not** be converted into `NOT_PUBLISHED`, a missing applicant population, a legal-status claim, or an assertion of completeness. Any later byte change must be treated as source drift and re-audited before parsing.

## Document structure audit

### Listed DOCX

The frozen listed source contains **10 sector tables**. Their non-header row counts are:

`26, 13, 25, 14, 32, 38, 0, 1, 10, 27`

for a total of **186 sector rows**. Every source row has seven physical OOXML cells matching the publication schema:

1. Ragione Sociale
2. Sede legale
3. Sede secondaria con rappresentanza stabile in Italia
4. Codice fiscale/Partita IVA
5. Data d’iscrizione
6. Data scadenza iscrizione
7. Aggiornamento in corso

The publication repeats the same registration across multiple sector tables, so **186 is not a company-observation count**. A semantic probe found 119 exact registration groups before deciding the final production grouping contract. It also found 104 identity groups when registration dates/status are ignored. These figures are diagnostic only: they are deliberately not promoted as public record counts because the source contains genuine multiple-registration histories and editorial variants that must not be collapsed by aggressive normalisation.

The `Aggiornamento in corso` column is not binary. Across sector rows the raw lexemes are:

- blank: 138
- `IN AGGIORNAMENTO`: 41
- `21 gennaio 2026`: 1
- `25 settembre 2026`: 3
- `30 luglio 2027`: 1
- `“`: 2

The dates and punctuation are retained as source evidence. Production status logic must be based on the column semantics and explicit fail-closed invariants, not on silently rewriting these values.

Identifier and date anomalies are also preserved raw. Examples observed in the frozen source include `00001092420312`, `001370303018`, `0237978303`, listing-date lexemes such as `10.12.202` and `14 agosto 204`, and company-name/identifier variants such as `EQUIPE SRL` / `EQUPE SRL`. No spelling, identifier or date correction is authorised by this audit.

### Applicant PDF

The frozen applicant source is a two-page table publication. It positively exposes **10 distinct 11-digit identifier anchors** in source order:

`01270500315`, `01262160318`, `01190800316`, `01270740317`, `00407990316`, `01268270319`, `00557360310`, `01040110312`, `01170510315`, `01195820319`.

The corresponding visible company names are ITALTRCH SRL, METAL X SRL, L’ANTICA RICETTA SRLS, EL.NET SOLUTION SRL, C.M.T. SRL, FMGDUE SRL, SI.ECO:SICUREZZA ED ECOLOGIA SRL, SULTAN SRL, SVILUPPO SOLARE SRL and T-RECYCLE SRL.

The extraction is structurally fragmented at the page break: the SULTAN record crosses pages, and page-one/page-two table extraction does not expose an identical logical width. Therefore **10 is currently an anchor count, not yet an approved parser record count**. A coordinate-aware reconstruction must prove that every identifier and field fragment is attached to exactly one record without inventing missing values. Blank application dates must remain blank.

## Gate state

At this checkpoint:

- `source_verified`: **true**, from positive official landing-page evidence;
- current listed publication resource: **identified and byte-frozen**;
- current applicant publication resource: **identified and byte-frozen**;
- repeat-fetch byte identity: **verified** for both resources;
- exact document reference dates: **not yet asserted**;
- `population_scopes_complete`: **not yet asserted** pending parser-level document review;
- parser family: **not yet bound for production**;
- final observation counts: **not yet asserted**;
- public export: **not approved**.

The next gate is a coordinate-aware applicant reconstruction plus a conservative listed-registration grouping contract. Only after both populations can be reproduced from the frozen bytes with explicit invariants should parser implementation, company-observation loading and national integration begin.
