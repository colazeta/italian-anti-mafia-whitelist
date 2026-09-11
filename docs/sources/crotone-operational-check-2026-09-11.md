# Crotone operational source check — 11 September 2026

The current official Prefettura di Crotone White List landing page was reverified on 11 September 2026 and positively exposes two distinct populations: **Ditte iscritte white list** and **Ditte con richiesta iscrizione white list**. Failed or blocked independent HTTP requests are not treated as negative evidence.

## Byte-pinned current sources

- Listed population: `ditte-iscritte-white-list-2.pdf`, SHA-256 `c9a2774c5842b895cd0bb18be3fe30a0c8858b2d67e985a993983e1834f0d511`, 130 pages.
- Applicant population: `ditte-con-richiesta-iscrizione-white-list-2.pdf`, SHA-256 `af66ff6bf6a173c4156fef3e7741ca26956769e399285764123ef8405097e6d1`, 46 pages.

Neither PDF states a reliable edition date in its visible content. PDF metadata records creation/modification on 9 September 2026, so the public configuration uses the **verification date 11 September 2026** as its reference date rather than inventing an edition date.

## Listed population

The table audit identified 743 reviewed section rows after one deterministic structural continuation: on page 63 a row with blank identity/address cells contains only a second date/status observation immediately below `SAMMARCO GIUSEPPE COSTRUZIONI GENERALI SRL`; only the preceding identity/address cells are carried, while the date/status observation remains separate.

Companies recur across White List sections. A conservative grouping uses normalised company name, the raw source identifier, formatting-only normalised registered address, semantic listing date (or raw sentinel), semantic expiry date (or raw sentinel), and source status. It yields **325 public observations: 72 `listed` and 253 `renewal_update_in_progress`**. A broader identity/date/status grouping would produce 323 groups but merges five cases with substantively different addresses; it is therefore rejected. No identifier, address or missing date is repaired or inferred.

## Applicant population

The applicant PDF contains 205 non-header physical table rows. Twenty-five are deterministic cross-page continuation fragments. The fail-closed stitching rules yield **180 distinct `pending` observations**, with zero duplicate logical rows. One reviewed example is `INERTI CALCESTRUZZI NETO S.A.S DI SALVATORE LIDONNICI & C`, whose identity/date and long textual cells are split across pages 9–10.

Malformed source identifiers remain in `identifier_field_raw` and never become canonical IDs. This includes embedded-space/mixed values such as `VRTGPP43P20 E339O` and `RLLGGR87M29 B774G/ 03332600794`.

## Publication boundary

The production parsers freeze page counts, row denominators, grouping denominator, statuses and applicant continuation count. They fail closed on new table widths, unreviewed date typography, ambiguous page continuations, duplicate same-section grouping, or source-count drift. Durable evidence and hosted-database integration remain governed separately under issue #16.
