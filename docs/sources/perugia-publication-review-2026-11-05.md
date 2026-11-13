# Perugia White List — 5 November 2026 source review

The official Perugia White List page labels both attachments as 5 November 2026 and reports an update on that date at 13:13. That attachment label is the edition basis; robot execution time is not the edition date. Both November PDFs were captured by the 13 November robot into the existing immutable archive, independently reacquired by source-only job 132152058099 in run 43502624795, and downloaded for original-document review. Full local parsing repeats the same original SHA-256 pins. Original documents are not committed or added to public release assets.

| Population | Original SHA-256 | Pages | Physical table rows | Logical source rows | Public observations |
|---|---|---:|---:|---:|---:|
| Listed | `d8dd83ac23e8fd1fa3b3913423d0b08ff5b1bc12a964738d4ff1a8499fa274f8` | 225 | 1,921 | 1,867 section rows | 1,020 |
| Applicants | `c049e8ec3d94f3a87ec7e6749cdd5f88b769c318156d38a51bba07b777762e77` | 187 | 1,316 | 1,243 | 1,243 |

## Physical contracts and source interpretation

The separately named November v2 adapter shares stateless helpers with the September parser, without changing or patching its pins, constants or semantics. November has different section boundaries and continuation coordinates. Its fixed source SHA, page/table/column counts, header coordinates, blank-row counts, exact continuation set and digest of every stitched row must match before projecting any record.

Listed decomposition: 10 headers + 38 blank rows + 6 previous-row continuation fragments + 1,867 section rows = 1,921 physical rows. Page 194 contains no table. Section boundaries: 1, 30, 42, 89, 107, 157, 195, 197, 199, 206. Section-row counts: I 256; II 108; III 404; IV 145; V 442; VI 252; VII 12; VIII 8; IX 68; X 172. Strict source identifiers occur on 1,829 section rows; three identifier cells are empty. Repeated section memberships are grouped using the established source-observation rule (strict identifier, otherwise source-name fallback, together with the exact source registration/expiry fields and update marker). This is not canonical national entity resolution. The grouped status distribution is **642 listed + 378 renewal/update in progress**; no status is inferred from expiry.

Applicant decomposition: 1 header + 17 blank rows + 54 previous-row continuation fragments + 1 forward fragment + 1,243 logical rows = 1,316 physical rows. Page 187 contains no table. The p6 r6 activity/outcome fragment belongs to p7 r1, not the preceding company; original-page visual inspection confirms this. Some other page-leading fragments split names and fiscal identifiers as well as activity descriptions. Only the exact reviewed coordinates are stitched. All 1,243 logical rows have names; 1,215 have strict identifiers. The applicant source retains historical positive outcomes: **1,038 listed + 204 pending + 1 other/unknown**, with 1,035 safely labelled decision dates. This source is not a list of pending applications alone.

## Finite anomalies retained

- Listed: five non-standard populated date cells remain unnormalised (p17 r4 expiry, p37 r2 registration, p66 r7 registration, p105 r7 registration, p163 r5 expiry); p200 r8 has both dates blank. Five exact chronology inversions are retained at p38 r1, p104 r7, p188 r3, p205 r3 and p220 r7. No dates are corrected or inferred.
- Applicants: six application dates are empty and five have unparseable source typography. Three explicitly positive outcomes lack a safely parseable labelled date. Their positive wording and raw values are retained; normalised dates remain empty.
- Applicant p185 r2 contains only `27/11/2026` in its outcome cell. Original-page visual inspection confirms that it has no decision label. It remains `other_or_unknown`, with no inferred decision date or positive status. The date is after the edition date and is not silently changed.
- Internal row/page/fragment evidence is projected through the existing closed public contract; no new private diagnostic fields or original PDFs enter the five-file public release.

## Incremental release acceptance

Compared with the selected Catania November baseline `public-data-43496640709-1`, the proposed Perugia counts replace 1,016 listed-series and 1,213 applicant-series observations with 1,020 and 1,243 respectively. The proposed national total is **74,462 source-document presences** (+34), with **74 Prefectures and 77 registers** retained. These are occurrences, not unique enterprises or legal-status changes.

Catania's already approved November source editions are explicitly preserved from the current immutable public derivative. The incremental audit must show **zero changes to all non-Perugia public observations**, including Catania. It is scoped to the exact Catania baseline, not a universal constraint on future approved editions. The source-manifest gate, public schema/privacy gate, browser checks and link checks remain mandatory.

The owner's 13 November instruction is to complete the work through publication. Parser/manifest integration and selector promotion remain separate reviewable commits, with CI on each exact revision and the sole Public retro portal publisher. Geography enrichment is not a release prerequisite. A successful candidate alone is not publication: require a new immutable derivative release, selector update, successful Pages deployment and live readback. Source capture/interpretation is separate from canonical database attribution.
