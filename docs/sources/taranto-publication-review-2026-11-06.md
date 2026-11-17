# Taranto public source review — 6 November 2026

This is a bounded **source/observation review** of the existing ordinary White List populations, not a SourceEdition in PostgreSQL, a canonical legal event or permission to introduce new public attributes. The live baseline for these sources is 7 September 2026 (388 listed-source and 212 applicant-source observations). The selected national baseline remains Como `public-data-43736522316-1`, with 74,496 documentary presences.

## Verified original provenance and physical completeness

The existing protected worker [43757038299](https://github.com/colazeta/italian-anti-mafia-whitelist/actions/runs/43757038299) retrieved genuine archived originals from the immutable CaptureCatalogue and R2 and independently classified every physical evidence-table row. A second real protected acceptance in [43774217234](https://github.com/colazeta/italian-anti-mafia-whitelist/actions/runs/43774217234), shard 1/job 132996719924, verified the complete original hashes, exact capture provenance, document-level explicit **6 November 2026** update date, parser/physical counts, and full publication-field digests. No live refetch, inferred administrative event or previous-version repinning is accepted. The date comes from the archived page itself, not `source_capture.declared_reference_date`, which remains NULL.

| Exact source | listed | applicants |
| --- | ---: | ---: |
| Physical/public observations | 383/383 | 226/226 |
| Original bytes | 150383 | 109175 |
| Original SHA-256 | `013cc91b1a62e353e77ab0e773299b6c0ed25c930d9d26d9bd62ec4613ed9396` | `c873e011a424e278f91a1bf80abec69282fc5ea53d310aa7118e49693c81c970` |
| Parser | `taranto_html_listed@1` | `taranto_html_applicants@1` |
| Full source semantic SHA-256 | `80fd32841490c1c72845fb394c8fab796d95b3e6f481a51951824f0d0c29a19b` | `1b51bb0dda7e0e001435351e07ce60b11d982afd2cf5cdb07373034da2b2e033` |
| Complete public-record SHA-256 | `c7bc0802534ccfa65e9b01d46727af52362c5bf6b64d40ee15dadf114fc6d524` | `534b016ae55363ae802d646c0c2da35cfe74e4f8b0f0695766f77bd1647c183c` |

## Finite semantic, identity and privacy assessment

- The strict listed parser recognises only blank source notes (183 `listed`) and the two observed literal notes for renewal/update (200 `renewal_update_in_progress`). The applicant parser yields exactly 226 `pending` observations; unknown listed notes trigger a hard error. These are **documentary states**, not new administrative decisions.
- All source section tokens are constrained to the existing White List section enumeration I–X, not NACE. Independent read-only Neon reconciliation on **16 November 2026, 01:41 UTC** found zero unapproved normalised sector values, zero empty activity lists and zero blank names across 609 rows. The two sources retain 10 and 9 distinct section categories, respectively; no new sector field or classification is introduced.
- Structured identifiers cover 377/383 and 225/226 observations; the remaining six and one values respectively stay raw-only. No source observation becomes a canonical entity through this release. A direct PostgreSQL JSONB readback found 383/383 and 226/226 unique physical locators and contiguous ordinals, with zero incorrect source keys, population assignments, authority/register assignments, capture SHA identities or structural field types.
- Exactly **eight** listed source rows retain malformed date evidence; no malformed applicant row dates. The existing parser conservatively preserves those raw variants in the already-approved `source_fields` contract, leaving any unparseable corresponding normalised date blank. In particular, the independent aggregate readback found zero affected rows with both associated normalised dates nonblank, zero synthetic `decision_date` values, and no unexpected applicant outcomes. These are not repaired dates, inferred expiry events, removals, cancellations or interdictions. The separate document update date is not substituted for an individual row date.
- Only fields already allowed by the versioned `public_contract.public_record` schema are proposed. The contracted addresses remain source-published text; no geocoding or geographic claims are added. Existing privacy/distribution safeguards remain mandatory. The closed, complete public value digest for **every** record is pinned above, rather than approved from an unexpected candidate output.

These observations are supported by the strict parser/census implementation, protected genuine-original receipt and independent aggregate readback; they do not assert that every raw date is historically true or that source differences prove legal effects.

## Incremental boundary and conditions

The two source entries alone move from **7 September to 6 November 2026**. Their 600 previous documentary presences become **609** (+9), with the national count provisionally 74,496 → 74,505 if and only if the complete candidate is selected and five live assets are verified. The potential 60-day Taranto documentary lag becomes zero only after successful publication; it is not yet a realised improvement. The other **140/140** scopes and their records, original source reports and verification timestamps must remain byte/record-identical. National scope stays 74/106 qualified Prefectures, 77 registers and 142 public series.

This review binds the exact two archived originals, versioned parsers, complete semantic and public-record digests to `multi_prefecture_pilot.json`. The finite `incremental_release_intent.json` is bound to the **current selected Como baseline** (canonical SHA-256 `892a2825c45f373c2702715ca23469c0e56901166dc3dcab3fcc7c97fa4166e3`) and this exact reviewed configuration (canonical SHA-256 `d36860ead30810f7b02c40653d6707c43b872fe5d6794acb9c650a73401fa282`). The previous Como intent is not authorisation for Taranto.

The candidate must pass existing CI, real original/semantic-byte controls, complete two-population checking, contract/privacy gates, five durable asset rehashes, full out-of-scope record/report comparison, and the main-only branch/selector handoff. Never construct a selector by hand. Only the existing Public retro portal may deploy, followed by five real live SHA-256/size checks. On failure, preserve the existing Como selection and rollback. There is no change to credentials, grants, infrastructure, scheduler or publisher.
