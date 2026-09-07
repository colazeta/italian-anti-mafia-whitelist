# Source-population resolution wave — 2026-09-07

## Purpose

This research pass resolves the mandatory `listed` and `applicant` source-population targets for register/regime scopes whose primary White List pages were already independently verified.

The pass does **not** treat failure to locate a publication as evidence that the population is not published. A scope remains unresolved until the publication identity is positively evidenced.

## Admission rule

A source series was added only when the population identity and publication surface were supported by one of the following:

1. a current official Prefettura / Commissariato / Valle d'Aosta page that directly exposes the publication;
2. a current official page that explicitly links the recurring publication surface;
3. an external application only where the official authority page explicitly identifies and links that application as its White List publication surface.

Predictable URL construction, search-result absence and semantic inference from application instructions were not accepted as evidence.

## Result

After this wave:

- verified authorities: **34**;
- register/regime scopes: **35**;
- scopes with both `listed` and `applicant` populations accounted for: **30**;
- unresolved scopes: **5**;
- inventoried source series: **59**.

## Scopes resolved in this wave

| Authority | Register/regime | Publication structure | Evidence surface |
| --- | --- | --- | --- |
| Ancona | ordinary L. 190/2012 | one combined attachment | https://prefettura.interno.gov.it/it/prefetture/ancona/evidenza/white-list |
| Aosta | ordinary L. 190/2012 | separate listed + applicant pages | https://www.regione.vda.it/prefettura/Antimafia/white_list/elenco_imprese_white_list_i.aspx ; https://www.regione.vda.it/prefettura/Antimafia/white_list/elenco_imprese_richiedenti_i.aspx |
| Arezzo | ordinary L. 190/2012 | separate attachments on one official page | https://prefettura.interno.gov.it/it/prefetture/arezzo/iscrizione-white-list |
| Asti | ordinary L. 190/2012 | separate attachments on one official page | https://prefettura.interno.gov.it/it/prefetture/asti/white-list-provinciali |
| Avellino | ordinary L. 190/2012 | separate official pages | https://prefettura.interno.gov.it/it/prefetture/avellino/white-list-elenco-imprese-iscritte ; https://prefettura.interno.gov.it/it/prefetture/avellino/white-list-elenco-imprese-richiedenti |
| Bergamo | ordinary L. 190/2012 | separate attachments on landing page | https://prefettura.interno.gov.it/it/prefetture/bergamo/evidenza/white-list |
| Bolzano/Bozen | ordinary L. 190/2012 | distinct consultation paths | https://prefettura.interno.gov.it/it/prefetture/bolzano/evidenza/white-list |
| Brescia | ordinary L. 190/2012 | separate attachments on landing page | https://prefettura.interno.gov.it/it/prefetture/brescia/evidenza/white-list |
| Bologna | ordinary L. 190/2012 | applicant attachment alongside ordinary registered-company files | https://prefettura.interno.gov.it/it/prefetture/bologna/white-list-provinciali-elenco-imprese-iscritte |
| Bologna | post-earthquake special regime | applicant attachment alongside post-earthquake registered-company file | https://prefettura.interno.gov.it/it/prefetture/bologna/white-list-post-sisma-elenco-imprese-iscritte |
| Genova | ordinary L. 190/2012 | separate attachments on one official page | https://prefettura.interno.gov.it/it/prefetture/genova/elenco-imprese-iscritte-white-list |
| Lodi | ordinary L. 190/2012 | two distinct resources linked by official landing page | https://prefettura.interno.gov.it/it/prefetture/lodi/evidenza/white-list |
| Napoli | ordinary L. 190/2012 | separate official pages | https://prefettura.interno.gov.it/it/prefetture/napoli/white-list-elenco-imprese-iscritte ; https://prefettura.interno.gov.it/it/prefetture/napoli/white-list-elenco-imprese-richiedenti |
| Padova | ordinary L. 190/2012 | separate official pages | https://prefettura.interno.gov.it/it/prefetture/padova/white-list-elenco-imprese-iscritte ; https://prefettura.interno.gov.it/it/prefetture/padova/white-list-elenco-imprese-richiedenti |
| Potenza | ordinary L. 190/2012 | combined custom application explicitly linked by official landing page | https://www.utgpotenza.it/_whitelist.php |
| Roma | ordinary L. 190/2012 | separate official pages | https://prefettura.interno.gov.it/it/prefetture/roma/white-list-elenco-imprese-iscritte ; https://prefettura.interno.gov.it/it/prefetture/roma/white-list-elenco-imprese-richiedenti-iscrizione |
| Torino | ordinary L. 190/2012 | applicant attachment alongside already-inventoried registered-company publication | https://prefettura.interno.gov.it/it/prefetture/torino/evidenza/white-list |
| Trento | ordinary L. 190/2012 | registered-company resource plus dedicated applicant page | https://prefettura.interno.gov.it/it/prefetture/trento/evidenza/white-list ; https://prefettura.interno.gov.it/it/prefetture/trento/white-list-elenco-imprese-richiedenti |

## Explicitly unresolved after the wave

| Authority | Current state | Research interpretation |
| --- | --- | --- |
| Bari | primary White List page verified; no evidence-backed source series entered yet | `UNRESOLVED_REQUIRES_REVIEW` for both populations |
| Crotone | primary White List page verified; source-series identity still requires a clean current resolution pass | do not infer applicant non-publication |
| Milano | registered-company series is evidenced through the dedicated White List application; no public applicant series has yet been positively resolved | `listed = COVERED`; `applicant = UNRESOLVED_REQUIRES_REVIEW` |
| Sassari | primary White List page verified; source-series identity still requires a clean current resolution pass | do not infer applicant non-publication |
| Udine | primary White List page verified; source-series identity still requires a clean current resolution pass | do not rely on historical-site hits as proof of the current publication model |

## Important negative rule

`UNRESOLVED_REQUIRES_REVIEW` means that the research registry has not yet positively accounted for that logical population. It must never be transformed into `not published` merely because a search engine, crawler or current landing-page extraction failed to expose the relevant object.

The remaining five scopes are therefore a defined research queue, not negative findings about publication practice.
