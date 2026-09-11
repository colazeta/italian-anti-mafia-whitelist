# Brindisi operational source check — 11 September 2026

## Official current publication surface

- Authority: Prefettura di Brindisi.
- Official landing page: https://prefettura.interno.gov.it/it/prefetture/brindisi/evidenza/white-list
- The live official page was reverified on 11 September 2026 and positively exposes two distinct current populations: `White List - Elenco imprese iscritte` and `White List - Elenco imprese richiedenti iscrizione`.
- The page reports `Ultimo aggiornamento Martedì 8 Settembre 2026, ore 13:16`; the public-source reference date is therefore frozen as **2026-09-08**.
- Listed resource: https://prefettura.interno.gov.it/sites/default/files/23/2026-09/white-list-elenco-imprese-iscritte_1.pdf
- Applicant resource: https://prefettura.interno.gov.it/sites/default/files/23/2026-09/white_list_della_provincia_di_brindisi-elenco_delle_imprese_richiedenti_l-iscrizione_0.pdf

This treatment does not infer a missing population, status or completeness from search behaviour. Both populations are supported by positive labels on the official surface.

## Capture identity and repeatability

Two independent live captures of each current official attachment were parsed in the same validation run. Both raw bytes and parsed semantics were stable across the two captures.

| Population | Pages | Raw SHA-256 | Semantic SHA-256 | Public observations |
| --- | ---: | --- | --- | ---: |
| Listed | 39 | `11d33d62f5e40139d4869e5f39752b1a69686bb064e46446161929fd84eeb06a` | `589cce1b755a50c3629d3bc5034bbe5b566c3d24dd08c3bfe4fb9e1cff83b20e` | 385 |
| Applicant | 3 | `1153781d3bf17b6cfc6513c90f8e083edf3a432fe6be382c4a1ffde9845f9e1b` | `9b1f6767a921c140a8ef3c2b4339a876d91829201ef0b51464ae137886df22b5` | 26 |

Raw SHA-256 is used as the publication approval boundary because both repeated captures were byte-identical. Semantic digests remain independent audit evidence.

## Listed-population parser boundary

The current listed PDF contains ten White List sections. The fail-closed parser freezes the section transitions and the following source-sector denominators: I 109, II 55, III 137, IV 52, V 150, VI 155, VII 4, VIII 14, IX 32 and X 122, for **830 source-sector rows**.

The source repeats companies across sections. Rows are grouped only when the same strict source identity (or, if no strict identifier exists, the same cleaned name), listing date, expiry date, status and source note agree. This yields **385 public source-backed observations**: **341 `listed`** and **44 `renewal_update_in_progress`**. The underlying 830 sector rows contain 718 listed and 112 update-in-progress rows.

Three reviewed malformed expiry strings — `0S-03-2027`, `25-03-20270` and `07-04-2027ti` — are preserved in raw provenance while the normalised date remains blank. They are not repaired. Strict identifiers are extracted only when the source contains an 11-digit numeric identifier or a 16-character alphanumeric identifier; malformed lengths are not padded, truncated or inferred. The public listed observations have strict identifier coverage for 383/385 records.

## Applicant-population parser boundary

The current applicant PDF is independently identified by the official page as the applicant population. The parser uses fixed ruled-table geometry and validated header anchors. It freezes page denominators of **10 + 15 + 1 = 26 observations**, all mapped to **`pending`** solely because they belong to the positively identified applicant publication.

One reviewed applicant observation has a blank application date and remains blank. Strict identifier coverage is 25/26, and one source observation legitimately contains two strict identifiers. No identifier or date is reconstructed.

## Publication scope and remaining infrastructure boundary

The validated Brindisi public contribution is therefore **411 source-backed observations** (385 listed-population observations plus 26 applicant observations). This is an observation count, not a count of unique legal entities.

Canonical hosted-database integration and independent durable-evidence verification are not asserted by this expansion and remain governed separately under issue #16. The parser and public build fail closed on source byte drift, page/section denominator drift, unreviewed date typography and applicant geometry drift.
