# Biella White List operational check — 10 September 2026

## Current official source

The authoritative surface used for this publication is the Prefettura di Biella White List landing page:

- https://prefettura.interno.gov.it/it/prefetture/biella/evidenza/white-list
- official visible update: **26 August 2026, 09:43**
- byte identity verified from a GitHub-hosted runner on 10 September 2026: `636389e9980b58b80e3ef5338feca39221db934b6b7ccb0f29b8d286c95dca53`

The current HTML itself contains two explicitly labelled populations: the table of companies requesting registration and the listed-company table organised across the ten statutory White List sections. A separate applicant page also exists, but the observed table there stopped in 2023 while the embedded landing-page table contains applications through 2026. The separate page is therefore retained only as discovery evidence, not selected as the current approved edition.

## Parser validation

The byte-pinned source was parsed with `biella_html_applicants` and `biella_html_listed` in Actions run 34433478263. The validated boundary is:

- applicants: **109 source rows / 109 public observations**;
- applicant statuses: **93 listed, 12 pending, 4 renewal/update in progress**;
- applicant identifiers: **107 canonical, 2 raw-only**; one application date is blank;
- listed table: **234 source sector rows / 130 public observations** after source-backed sector grouping;
- listed statuses: **120 listed, 10 renewal/update in progress**;
- listed identifiers: **90 canonical, 40 raw-only**; one expiry date is blank;
- no source-date row was dropped.

Sector repetition is grouped only when a conservatively normalised source identity, listing date, expiry date and mapped source status all agree. Conflicting date tuples remain distinct observations. Typography-equivalent dates such as `23-nov-20` and `23/11/2020` may resolve to the same date, but source digits are never repaired. Non-canonical identifiers remain available only in the raw source field.

## Evidence boundary

This validates the **public source-observation layer**. It does not claim nationally deduplicated legal entities, canonical hosted-database integration or independent durable-evidence recovery. Those infrastructure gates remain governed separately under issue #16 and do not justify withholding these directly source-backed observations from the experimental public registry.
