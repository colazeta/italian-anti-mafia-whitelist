# GitHub Actions artifact publication boundary

## Decision

This repository is public. Every GitHub Actions artifact produced by it is therefore treated as a **publication surface**, not as a private workspace.

The deliberate public website remains the narrower contract under `public-site/` and GitHub Pages. Actions artifacts may publish only material that has been classified explicitly as one of:

- `deliberately_public_publication` — the public site or public rendering/link checks;
- `deliberately_public_discovery` — public-source discovery output whose fields are intended for redistribution;
- `public_operational_verification` — aggregate/redacted verification evidence that proves a gate ran without publishing the internal bundle used by that gate.

The machine-readable allow-list is [`actions-artifact-policy.json`](actions-artifact-policy.json). CI fails if a workflow adds or changes an `actions/upload-artifact` surface without reconciling that policy.

## Current upload inventory

| Workflow | Artifact family | Classification | Public contents |
|---|---|---|---|
| `anncsu-national-validation.yml` | `national-anncsu-verification-*` | operational verification | aggregate multi-region gate result and a cryptographic binding to the internal summary |
| `cosenza-address-validation.yml` | `cosenza-address-validation-verification-*` | operational verification | aggregate address coverage/quality figures, frozen review aggregates and hashes of internal row files |
| `cosenza-content-capture.yml` | `cosenza-content-verification-*` | operational verification | frozen content identities, parser/semantic aggregates, population-coverage aggregates and hashes of internal outputs |
| `evidence-store.yml` | `evidence-store-verification-*` | operational verification | redacted R2 write/retrieval verification only |
| `evidence-recovery.yml` | `evidence-recovery-verification-*` | operational verification | redacted recovery/restore verification only |
| `fallback-geocoding-validation.yml` | `fallback-geocoding-verification-*` | operational verification | aggregate deterministic synthetic fallback-gate result |
| `pistoia-address-replication.yml` | `pistoia-address-replication-verification-*` | operational verification | aggregate Pistoia replication result, source hashes/provider-version hashes and a binding to the internal review sample |
| `discover-national-index.yml` | `national-white-list-index` | public discovery | Ministry/public authority discovery URLs |
| `cosenza-snapshot-discovery.yml` | `cosenza-snapshot-discovery` | public discovery | public dated-source discovery output |
| `public-pages.yml` | rendered evidence, link audit, review build | public publication | browser screenshots/test evidence, public link audit and the public-site build |
| `public-pages.yml` | Pages deployment artifact | public publication | `public-site/` only |

The public verification publishers intentionally retain counts, content hashes and file digests while excluding row values, entity names, full address records, source PDFs, internal Explorer HTML, provider/storage coordinates that are not needed for the public claim, and review notes.

## Internal material that must stay off public Actions artifacts

The following may be created on a trusted ephemeral runner because they are needed to validate the project, but they are **not authorised for Actions artifact upload**:

- original captured Prefecture PDFs unless a separate redistribution decision explicitly approves that publication surface;
- the internal Dataset Explorer and its full database-table exports;
- `source_evidence.json` plus packaged row-to-PDF evidence;
- full geocoding/address-result tables;
- substantive-review samples containing source rows, entity names or evidence locators;
- Pistoia `source-pdfs/`, `source-occurrences.csv` and the complete review pack;
- provider request logs or other diagnostic traces that are not necessary for a public verification claim.

A workflow may still build these materials to prove an invariant. They are discarded with the runner after the redacted verification record has been generated.

## Historical artifact families

This change is prospective. Existing historical Actions artifacts are **not deleted autonomously** because deletion is irreversible and some are part of the project audit trail. They remain accessible until their recorded GitHub expiry unless the user later authorises another retention action.

Historical families known to have had a broader boundary are:

| Historical family | Contents/classification | Retention note |
|---|---|---|
| `cosenza-content-capture-v2` | source capture PDFs/text and parsed row outputs; source-evidence/internal material | normal per-run GitHub retention; exact expiry is run metadata |
| `data-explorer-preview-v2` | internal Explorer, DB table exports, original PDFs and row locators | 90-day workflow retention where configured |
| `cosenza-address-validation-explorer` | internal Explorer, full 1,298-row address results, review sample and source-PDF evidence | 90-day workflow retention |
| `pistoia-address-review-pack-attempt-*` | source PDFs, source-occurrence rows, review sample and validation bundle | 90-day workflow retention |
| `national-anncsu-validation-attempt-*` | broader operational validation directory; no intended source-PDF redistribution | 30-day workflow retention |
| `fallback-geocoding-validation-attempt-*` | deterministic synthetic request logs and operational validation directory | 90-day workflow retention |
| legacy evidence-store receipt artifact | verification receipts with provider/storage coordinates, but no credentials or source PDFs | retained to normal expiry; superseded by PR #64 redaction |
| any pre-redaction recovery receipt artifact | recovery verification metadata from the earlier contract, if a run exists | retained to normal expiry; superseded by PR #63 redaction |

The fact that original documents are publicly obtainable from a Prefettura does not itself authorise republishing the project’s exact preserved copy through GitHub Actions. Evidence retention and redistribution remain separate decisions.

## Substantive review without public artifact confidentiality

The address-review method is preserved. When a reviewer needs the full Cosenza/Pistoia evidence bundle, it must be regenerated in a trusted local/private execution environment from a pinned commit and the same frozen source/provider identities. See [`../validation/internal-review-handoff.md`](../validation/internal-review-handoff.md).

The workflow itself remains a reproducible recipe and continues to execute the internal validation package on GitHub-hosted ephemeral runners; only its **uploaded output** is redacted. Completed reviewer decisions and their reviewed metadata may still be versioned in `data/validation/` through the normal PR/CI process because those are deliberate curated gold-standard artifacts, not raw workflow bundles.

## Governance

`tests/test_actions_artifact_policy.py` enforces that:

1. every current `actions/upload-artifact@v4` call matches the reviewed allow-list exactly;
2. operational verification paths cannot point at known internal/source-evidence directories;
3. no current artifact name claims to be `private`;
4. the Pages artifact can contain only `public-site/`;
5. redaction functions bind internal files by SHA-256 without emitting their row values or hidden URLs.

Any future need to publish a richer Actions artifact is therefore an explicit publication decision, not an incidental consequence of adding a workflow step.
