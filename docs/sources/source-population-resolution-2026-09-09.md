# Source-population resolution wave — 2026-09-09

## Purpose

This pass revisits the five register scopes that remained unresolved after the 7 September source-population wave. The same positive-evidence rule applies: a logical `listed` or `applicant` target is covered only when a current official authority surface directly exposes that population, explicitly links its recurring publication surface, or explicitly identifies an external application as the publication surface.

Search failure, a submission portal, a generic White List information page or historical evidence is not treated as proof that a population is unpublished.

## Result

After this pass:

- verified authorities: **34**;
- register/regime scopes: **35**;
- scopes with both `listed` and `applicant` populations accounted for: **32**;
- unresolved scopes: **3**;
- inventoried recurring source series: **63**.

Two previously unresolved authorities are now positively resolved: **Bari** and **Udine**.

## Bari — resolved

Current official surface:

https://prefettura.interno.gov.it/it/prefetture/bari/evidenza/white-list

The current Prefettura page explicitly exposes two separate attachments:

- `Elenco società iscritte al 31/08/2026`;
- `Elenco richieste di iscrizione al 31/08/2026`.

The page therefore positively accounts for both mandatory logical populations. The registry now contains `bari-listed` and `bari-applicants`, both bound to the current official landing page as recurring periodic attachments.

This supersedes the access failure recorded in `bari-operational-check-2026-09-08.md`; that earlier record remains historically correct for the failed 8 September observation and is not rewritten.

## Udine — resolved

Current official surface:

https://prefettura.interno.gov.it/it/prefetture/udine/evidenza/white-list

The current Prefettura page explicitly exposes two separate attachments, both updated 18 August 2026:

- `Elenco ditte iscritte nelle White List`;
- `Elenco dei fornitori che hanno chiesto di essere iscritti nelle White List`.

The registry now contains `udine-listed` and `udine-applicants`, both bound to the current official landing page as recurring periodic attachments. No historical-site inference is required.

## Still unresolved

### Crotone

Current official surfaces reviewed:

- https://prefettura.interno.gov.it/it/prefetture/crotone/evidenza/white-list
- https://prefettura.interno.gov.it/it/prefetture/crotone/decreti-direttive-e-altri-documenti

The current White List page establishes the active service and application process. The current documents index exposes a `WHITE LIST - ELENCO IMPRESE ISCRITTE` entry, but the present research route did not positively resolve a clean recurring applicant publication identity. The scope therefore remains `UNRESOLVED_REQUIRES_REVIEW`; no applicant non-publication is inferred.

### Milano

Current official surface:

https://prefettura.interno.gov.it/it/prefetture/milano/evidenza/white-list

The registered-company publication remains positively evidenced through the dedicated Prefettura application (`whitelist.prefmi.it`). The current Ministry page also exposes the new `portalewl.interno.gov.it` route for submitting applications from 21 July 2025. A submission route is not a public applicant-list publication. No separate current public applicant series was positively resolved in this pass, so `milano-applicant` remains `UNRESOLVED_REQUIRES_REVIEW`.

### Sassari

Current official surface:

https://prefettura.interno.gov.it/it/prefetture/sassari/evidenza/white-list

The page currently exposes a single attachment labelled `WHITE LIST elenco provinciale delle imprese`. The page also contains procedural text concerning firms that have applied but are not yet registered. Neither the generic attachment label nor procedural text alone proves that the attachment physically contains both populations. Until the attachment schema or a distinct applicant publication is positively verified, the Sassari scope remains `UNRESOLVED_REQUIRES_REVIEW`.

## Regression rule

The deterministic coverage test now asserts the exact unresolved set:

```text
crotone
milano
sassari
```

Bari and Udine must regress to unresolved if their qualifying series are removed. The target state remains 35/35 complete only if the remaining three populations are positively evidenced under the same admission rule.
