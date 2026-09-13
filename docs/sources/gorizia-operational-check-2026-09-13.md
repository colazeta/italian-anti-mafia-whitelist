# Gorizia White List operational check — 2026-09-13

## Scope

This checkpoint records positive current-source evidence for the Prefettura di Gorizia. It identifies the two publication populations exposed by the official White List page, but does **not** yet approve byte identity, source reference dates, parser binding, population completeness, company-observation loading, or public export.

## Official publication surface

- Official landing page: `https://prefettura.interno.gov.it/it/prefetture/gorizia/evidenza/white-list`
- Live verification on 13 September 2026 returned the official page successfully. The page reports its own last update as **17 August 2026, 12:37**.
- The landing page positively exposes two distinct current publication resources:
  - applicants, labelled `Ditte per cui è in corso la richiesta di iscrizione alla WhiteList`: `https://prefettura.interno.gov.it/sites/default/files/0/2026-08/2026.08-white-list-ditte-richiedenti-iscrizione.pdf`
  - listed companies, labelled `Elenco delle Ditte della provincia di Gorizia iscritte alla White List`: `https://prefettura.interno.gov.it/sites/default/files/0/2026-08/gorizia-elenco-ditte-iscritte-wl.docx`
- The applicant publication is a PDF and the listed publication is a DOCX. The official page therefore provides positive evidence for both logical populations; neither population is inferred from filename construction or search-engine absence.
- The exact reference date carried by each document has **not yet been established**. The August 2026 URL paths and the landing-page update timestamp are provenance signals, not substitutes for a document-level source date.

## Capture gate

The next step is a repeatable byte-level capture from the two exact official URLs. Each source must be fetched independently at least twice and validated against its native container format before a SHA-256 may be frozen:

- applicant PDF: HTTP 200, PDF magic, parseable PDF container, stable byte length and SHA-256 across repeat fetches;
- listed DOCX: HTTP 200, ZIP/DOCX magic, required Office Open XML members (`[Content_Types].xml` and `word/document.xml`), stable byte length and SHA-256 across repeat fetches.

A later source failure must be recorded as a retrieval failure. It must **not** be converted into `NOT_PUBLISHED`, a missing applicant population, a legal-status claim, or an assertion of completeness.

## Gate state

At this checkpoint:

- `source_verified`: **true**, from positive official landing-page evidence;
- current listed publication resource: **identified**;
- current applicant publication resource: **identified**;
- exact document reference dates: **not yet asserted**;
- content SHA-256: **not yet asserted**;
- repeat-fetch byte identity: **not yet verified**;
- `population_scopes_complete`: **not yet asserted** pending document-level review;
- parser family: **not yet bound**;
- record counts: **not yet asserted**;
- public export: **not approved**.

No parser, dataset, national registry or public-site change is justified until the capture gate and a full document-structure/status review have succeeded against the frozen source bytes.
