# Pescara White List operational check — 21 September 2026

## Official publication evidence

The current official Prefettura di Pescara surfaces positively expose both populations. The listed landing is `https://prefettura.interno.gov.it/it/prefetture/pescara/evidenza/white-list` and direct verification exposed **White list 16/09/2026**. The applicant page is `https://prefettura.interno.gov.it/it/prefetture/pescara/elenco-imprese-richiedenti-liscrizione-nelle-white-list` and exposed **Elenco richiedenti White List - 04.09.2026**. A separate client returning HTTP 403 is not negative publication evidence; source identity was established by successful official-site retrieval in the validation runner.

Two independent downloads of each current resource were byte-identical. Both are legacy Microsoft Word/OLE documents and are parsed with `antiword` in fail-closed mode.

| population | resource | bytes | SHA-256 |
|---|---|---:|---|
| listed | `white-list-2026.doc` | 1,967,616 | `6a8aa832db7d0f55c17d9ed1f8179d9ed46a7c927b5b88d85319f79a1da92239` |
| applicants | `elenco_richiedenti_white-list_04.09.2026.doc` | 350,720 | `2a0f74ab6548ad2418f539aba7fc2eaf0d23998b709b0bc247e512d7b46a578c` |

## Listed population

The source contains ten statutory White List sections represented through 13 seven-column table groups and 1,060 physical company×section rows. Exact full-row grouping produces **607 logical observations** and 1,058 unique section memberships; two exact repeated memberships inside the same section are treated as source duplicates rather than additional activities.

The frozen status boundary is **456 listed, 150 renewal/update in progress, and 1 other/unknown**. Only a blank update field maps to `listed`; exact `IN RINNOVO` maps to `renewal_update_in_progress`; the single source token `I` is deliberately retained as `other_or_unknown`. Any new status token fails validation.

Structured identifier coverage is **579/607**. Twenty-eight observations contain source identifiers that do not satisfy accepted 11-digit/16-character shapes and remain raw-only. Seven malformed source date tokens are likewise retained as raw evidence and are not repaired: `21/052024`, `13/07/20222`, `23701/2026`, `09/06/20206`, `22/12/202`, `30707/2024`, `29/10/204`.

## Applicant population

The applicant source contains two six-column table groups, one exact header and **36 physical data rows**. Physical row 6 is a continuation of the preceding `CALISTA IMPIANTI SRL` row: the first fragment contains company/office/identifier while the second carries the requested activity and application date `01.10.2025`. The parser permits that merge only for this exact reviewed owner and shape and therefore emits **35 applicant observations**, all `pending` on positive applicant-source evidence.

Structured identifier coverage is **34/35**; source value `0285069069` remains raw-only. Applicant dates contain no reviewed malformed values. Blank names elsewhere, row-width/header drift, a changed continuation shape, or an unreviewed malformed applicant date fail closed.

## Publication boundary

Pescara contributes **642 observations** to one ordinary register: 607 listed-side observations plus 35 applicant observations. Structured identifier coverage is **613/642**. Parser validation is byte-pinned to the two hashes above. Source anomalies remain provenance and are never silently normalised.
