# Brescia operational source check — 12 September 2026

## Current official evidence

The current official Prefettura di Brescia White List landing page was directly verified on 12 September 2026. It returned HTTP 200 and positively exposed separate registered-company and applicant-company XLSX attachments for the **10 September 2026** edition. Both attachments were independently fetched twice and produced identical SHA-256 values on both requests.

- Landing page: https://prefettura.interno.gov.it/it/prefetture/brescia/evidenza/white-list
- Landing-page SHA-256 at verification: `432bdbf9f1ac00e30ebc1c82685799192fac3dd99839ef7a2bd4a3d19a1d7225`.
- Listed XLSX: 285,910 bytes; SHA-256 `509e6724de2d4d63f403e254236ec2c5b77077d676ee8c17382464d5c9da07a7`; HTTP Last-Modified 10 September 2026 12:14:29 GMT.
- Applicant XLSX: 125,330 bytes; SHA-256 `0ab15af0f0f2838aa162177cbc07b91f3d7d80b561ca490611b8ec368c595f34`; HTTP Last-Modified 10 September 2026 12:15:40 GMT.

No publication identity, completeness or legal status is inferred from search failure. The public candidate uses only these positively identified official resources.

## Listed population

The listed workbook contains ten stacked statutory White List sections. The reviewed physical denominator is **3,380 section rows**: I 426; II 222; III 576; IV 448; V 598; VI 467; VII 70; VIII 35; IX 81; X 457. Conservative semantic grouping yields **2,071 public observations**: **1,859 `listed`** and **212 `renewal_update_in_progress`**.

The real workbook contains an audited layout class in which the company name is placed in column A while the labelled company-name column is blank. The full audit found exactly **72** such company-like source rows, frozen by SHA-256 fingerprint `f6d55887c3f4e45e46217447100e5e896e509c5daa50f603a9ab48a53c5a41c2`. They touch 58 semantic groups, including 39 groups that would otherwise be absent. The parser accepts only that exact reviewed fingerprint and fails closed if the class changes. One separate non-company noise row is frozen by fingerprint `494b0d0d6944b0c006f0a103889004950b190070ee36f2cdfa8d7d9e8c63e610` and excluded from company observations.

One `ADMG SRL` row has a separately reviewed structural field shift. Two malformed source date tokens are normalised only because an exact same-company/same-identifier peer in another statutory section supplies a unique clean date. Other malformed date values remain raw. No fuzzy company matching, address reconstruction or identifier reconstruction is used.

## Applicant population

The applicant workbook contains **1,264 reviewed source rows** and yields **1,263 public observations**, all represented as `pending`, after one exact duplicate group. The parser records 841 missing application dates and one malformed application date without inventing replacements. Identifiers are normalised only when they satisfy the strict accepted format; otherwise the source value remains available as raw evidence.

## Publication decision

The two current source populations are distinct and positively identified by the official authority. The parser has passed semantic tests, two-fetch byte verification against both pinned resources, real-source validation and the full repository test suite. Brescia is therefore eligible for the public national candidate subject to the normal national-build, browser, official-link, CI and deployment gates. Durable independent evidence-store verification and canonical hosted-database integration remain governed separately under issue #16 and are not inferred here.
