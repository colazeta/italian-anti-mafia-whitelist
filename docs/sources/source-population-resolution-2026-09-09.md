# Source-population resolution wave — 2026-09-09

## Purpose

This pass revisits the five register scopes that remained unresolved after the 7 September source-population wave. The same positive-evidence rule applies: a logical `listed` or `applicant` target is covered only when a current official authority surface directly exposes that population, explicitly links its recurring publication surface, or explicitly identifies an external application as the publication surface.

Search failure, a submission portal, a generic White List information page or historical evidence is not treated as proof that a population is unpublished.

## Result

After the completed 9 September resolution work:

- verified authorities: **34**;
- register/regime scopes: **35**;
- scopes with both `listed` and `applicant` populations accounted for: **33**;
- unresolved scopes: **2**;
- inventoried recurring source series: **65**.

Three previously unresolved authorities are now positively resolved: **Bari**, **Udine** and **Crotone**.

## Bari — resolved

Current official surface:

https://prefettura.interno.gov.it/it/prefetture/bari/evidenza/white-list

The current Prefettura page explicitly exposes two separate attachments:

- `Elenco società iscritte al 31/08/2026`;
- `Elenco richieste di iscrizione al 31/08/2026`.

The page therefore positively accounts for both mandatory logical populations. The registry contains `bari-listed` and `bari-applicants`, both bound to the current official landing page as recurring periodic attachments.

This supersedes the access failure recorded in `bari-operational-check-2026-09-08.md`; that earlier record remains historically correct for the failed 8 September observation and is not rewritten.

## Udine — resolved

Current official surface:

https://prefettura.interno.gov.it/it/prefetture/udine/evidenza/white-list

The current Prefettura page explicitly exposes two separate attachments, both updated 18 August 2026:

- `Elenco ditte iscritte nelle White List`;
- `Elenco dei fornitori che hanno chiesto di essere iscritti nelle White List`.

The registry contains `udine-listed` and `udine-applicants`, both bound to the current official landing page as recurring periodic attachments. No historical-site inference is required.

## Crotone — resolved

Current official surface:

https://prefettura.interno.gov.it/it/prefetture/crotone/evidenza/white-list

The current Prefettura page, last updated **14 August 2026**, directly exposes two separate White List attachments:

- `Ditte con richiesta iscrizione white list`;
- `Ditte iscritte white list`.

This is positive current evidence for both mandatory logical populations. The registry therefore contains `crotone-listed` and `crotone-applicants`, both bound to the official White List landing page as recurring periodic attachments.

An earlier research note on 9 September had positively resolved only the listed-company surface through the general documents index and therefore retained the applicant target as unresolved. The current White List page itself now provides the stronger direct evidence needed to resolve both targets. The earlier uncertainty is superseded rather than reinterpreted as evidence of prior non-publication.

## Still unresolved

### Milano

Current official surface:

https://prefettura.interno.gov.it/it/prefetture/milano/evidenza/white-list

Current registered-company application:

https://whitelist.prefmi.it/elenco/elenco_iscritte.php

The Ministry page explicitly links `White list - Elenco imprese iscritte` and separately `White list - Richiesta iscrizione (dal 21 luglio 2025)`. The latter is the national submission portal, not a public applicant-list publication. The current linked `elenco_iscritte.php` application is live and exposes registered firms, including already-registered firms whose renewal is `IN AGGIORNAMENTO`.

A deeper same-day audit recovered **historical evidence** that the older Milano application surface `whitelist.prefmi.it/elenco/elenco.php` previously mixed ordinary registered rows with rows explicitly labelled `RICHIESTA ISCRIZIONE (date)`. Historical third-party/public records also refer to that application as a way to check whether a Milano firm had applied. This establishes that the Milano application has historically represented applicant status, but it does not establish that the applicant population remains publicly exposed by the **current** publication surface after the 21 July 2025 submission transition and the current `elenco_iscritte.php` split.

The current Prefettura instructions for contracting authorities are compatible with the need to ascertain whether an undertaking has already applied, but instructions are not a substitute for identifying the actual current applicant publication surface. No current official applicant endpoint or attachment was positively identified in this audit. `milano-applicant` therefore remains `UNRESOLVED_REQUIRES_REVIEW` rather than being inferred from the legacy application.

### Sassari

Current official surface:

https://prefettura.interno.gov.it/it/prefetture/sassari/evidenza/white-list

The current page, last updated **29 July 2026**, exposes exactly one attachment labelled `WHITE LIST elenco provinciale delle imprese` (74.29 KB). It also contains procedural text concerning contracting on the basis of an application that is still awaiting the Prefettura's final decision.

A second same-day audit searched for a separately indexed current applicant publication and for a searchable copy of the 74.29 KB attachment that would reveal its physical schema. Neither was positively recovered. The comparison with other current Prefetture is important but not dispositive: Cagliari and Oristano, for example, explicitly label their applicant publications as `richiedenti`; Sassari's generic attachment label does not establish equivalent content.

Accordingly, the single Sassari attachment is not promoted to `listed_and_applicant` without inspecting its schema or obtaining a current official statement that it contains both populations. `sassari-applicant` remains `UNRESOLVED_REQUIRES_REVIEW`.

## Second-audit conclusion

The extra audit materially narrows the evidentiary question but does **not** justify moving either remaining scope to covered:

- **Milano:** prove that a current public surface still exposes first-time/pending applicants, rather than only registered and renewal-in-progress firms. The historical mixed application is useful provenance, not current publication evidence.
- **Sassari:** inspect the current 74.29 KB attachment schema or locate a distinct current applicant publication. Procedural text alone is insufficient.

The next evidence-producing action, if open-source retrieval remains inconclusive, is direct clarification from the relevant Prefettura/White List office. Until such evidence exists, the correct canonical state is unresolved rather than `NOT_PUBLISHED`.

## Regression rule

The deterministic coverage test now asserts the exact unresolved set:

```text
milano
sassari
```

Bari, Udine and Crotone must regress to unresolved if their qualifying series are removed. The target state remains 35/35 complete only if the remaining two populations are positively evidenced under the same admission rule.
