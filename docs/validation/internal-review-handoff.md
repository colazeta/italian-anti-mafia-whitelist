# Internal address-review handoff

## Purpose

The Cosenza and Pistoia address-validation workflows deliberately build richer evidence packages than the project publishes. Those packages may contain source rows, entity names, full addresses, row-to-source evidence and preserved source PDFs. Because this repository is public, **GitHub Actions artifacts are not the handoff channel for that internal material**.

The public workflow run proves that the deterministic build and validation gates still work. Its uploaded artifact contains only a redacted aggregate verification record and cryptographic bindings to the richer files generated on the ephemeral runner.

## How to obtain a full review bundle

A substantive reviewer should regenerate the bundle in a trusted workstation or access-controlled runner:

1. check out the exact reviewed `main` commit (or the exact PR head under review);
2. install the same project extras and database/runtime dependencies encoded in the corresponding workflow;
3. obtain the frozen source bytes from the private evidence archive where authorised, or reacquire them from the official source only when their byte SHA-256 matches the frozen capture manifest exactly;
4. acquire the frozen Istat/ANNCSU provider inputs using the version/hash gates encoded in the workflow;
5. execute the same database reconstruction, linkage and review-pack commands from the workflow;
6. review the resulting internal Explorer/sample locally; do not upload the bundle to a public Actions artifact;
7. export reviewer decisions as JSON/CSV and verify the sample fingerprint before using them;
8. version only the curated reviewer-decision layer and reviewed metadata through a normal branch/PR/CI change.

The workflows remain the executable specification. Do not replace them with undocumented local transformations.

## Cosenza

Use `.github/workflows/cosenza-address-validation.yml` as the canonical recipe. Its internal execution reconstructs the frozen Cosenza database, verifies both source captures, runs the frozen official-first ANNCSU linkage, creates the 150-row deterministic sample and produces the review-enabled Explorer.

The public Actions artifact intentionally does **not** contain:

- `address_results.csv` with the 1,298-row drill-down;
- the 150-row source-backed review sample;
- the internal Explorer HTML;
- database table exports;
- `source_evidence.json` or the packaged source PDFs.

The completed reviewed gold standard remains versioned under `data/validation/cosenza/` and is the durable benchmark for quality comparisons.

## Pistoia

Use `.github/workflows/pistoia-address-replication.yml` as the canonical recipe. Its internal execution SHA-verifies the approved Pistoia source publications, builds the source-backed Toscana population, runs the unchanged exact ANNCSU policy and generates the deterministic replication sample.

The public Actions artifact intentionally does **not** contain:

- `source-pdfs/`;
- `source-occurrences.csv`;
- the row-level Pistoia review sample;
- the complete validation/review pack.

The reviewed Pistoia gold standard and metadata are versioned separately under `data/validation/pistoia/`.

## Evidence identity and review validity

A review export is valid only for the sample fingerprint and frozen source/provider identities it was generated from. If any of those identities differ, regenerate the bundle and treat it as a new review population rather than importing old decisions.

The public verification artifact can be used to confirm that a public CI run generated and validated the expected internal material because it records aggregate counts and SHA-256 bindings. It is not a substitute for the internal files themselves.

## Storage boundary

The private R2 evidence archive retains original source evidence according to its separate storage policy. Expanding R2 to store arbitrary review bundles is **not** implied by this procedure and would require a separate architecture/retention/access decision.

See also:

- `address-review.md` for the substantive review protocol;
- `../architecture/actions-artifact-boundary.md` for the Actions publication policy;
- `../architecture/source-evidence-archive.md` for original-source preservation.
