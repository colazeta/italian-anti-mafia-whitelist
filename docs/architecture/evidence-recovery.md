# Independent evidence backup and restore gate

## Status

The repository contains a provider-neutral backup and clean-restore gate for the durable source-evidence archive. The historical provider/storage gate and its Cosenza probes remain useful evidence, but they are **not** national archive coverage and are not a substitute for restoring a selected frozen national release.

The national restore gate is tooling-ready until it has executed successfully against the approved independent recovery environment. No provider, account, bucket, credential or paid resource is created by this repository.

## Purpose

The primary evidence store protects exact source bytes through content-addressing, conditional creation, full-object retrieval and SHA-256 verification. That protects integrity inside the primary namespace, but it is not an independent recovery copy.

For a reviewed frozen release, the recovery gate tests a separate property:

```text
reviewed frozen release manifest
        ↓ exact selected capture/check set
primary CaptureCatalogue readback + ContentObject readback
        ↓ every capture provenance verified separately
short-lived verified runner bytes
        ↓ unchanged bytes deduplicated only at ContentObject layer
independent recovery object store
        ↓ full GET + frozen SHA-256 check
clean local restore path
        ↓ independent size + SHA-256 check
redacted release/object verification receipts
```

Raw source bytes remain private throughout this path. They are not committed to Git and are not uploaded as GitHub Actions artifacts.

A SourceSeries URL remains only a locator. Independent recovery operates on exact capture identities and ContentObjects selected by the frozen release. Repeated unchanged bytes may share one recovery ContentObject, but every selected capture/check is still verified independently before byte-level deduplication.

## Frozen release selection

`.github/workflows/evidence-recovery.yml` is manual and main-only. It requires `release_manifest`, which must be a tracked JSON file directly under `data/releases/`.

The workflow freezes that file before provider access, requires an exact 40-character `code_revision`, requires that revision to be an ancestor of the executing `main`, and reads `data/publication/multi_prefecture_pilot.json` from that exact revision. `selected_release_captures()` then validates the release/configuration binding through the same frozen-release model used by archive replay.

The restore path therefore cannot silently switch to current live Prefecture URLs or to a different current source configuration. Missing, malformed or incompatible selected inputs fail closed.

Before any recovery-store write, the workflow verifies **every selected capture** through both controls:

1. `CaptureCatalogue.verify_receipt()` reads back and validates immutable capture/check provenance;
2. `EvidenceStore.read_verified()` retrieves the exact primary ContentObject and verifies byte size and SHA-256.

Only after all selected captures pass are repeated byte-identical ContentObjects deduplicated for backup. This preserves distinct checks/captures while avoiding duplicate recovery objects for unchanged bytes.

## Fail-closed independence contract

`white_list_archive.storage.recovery` computes a non-secret fingerprint of the exact object-store namespace from normalized endpoint and bucket. The recovery helper refuses the primary namespace.

That mechanical check is deliberately narrow. A different bucket name, endpoint or account identifier does **not** by itself prove independent recovery. The workflow also requires `RECOVERY_INDEPENDENCE_EVIDENCE`, a reviewed operator locator documenting why the recovery target is an independent administrative/failure domain. The project must not infer independence merely because two S3-compatible configurations differ.

A defensible live configuration should document, at minimum:

- who administers the primary and recovery copies;
- whether the recovery copy survives loss, lockout, deletion or provider failure affecting the primary namespace;
- retention/immutability and deletion privileges for the recovery copy;
- recovery responsibility and the procedure for restoring exact bytes;
- the successful restore-test evidence and date.

The primary archive retention controls remain unchanged. A recovery test must never require weakening or removing them.

## Recovery environment

The workflow uses the dedicated `evidence-recovery` environment. Configure the following only after an independent recovery target has been approved:

| Kind | Name | Purpose |
| --- | --- | --- |
| Variable | `PRIMARY_EVIDENCE_BUCKET` | Primary durable evidence bucket name |
| Variable | `PRIMARY_EVIDENCE_ENDPOINT` | Primary S3-compatible HTTPS endpoint |
| Variable | `PRIMARY_EVIDENCE_REGION` | Primary signing region |
| Variable | `PRIMARY_EVIDENCE_POLICY_EVIDENCE` | Reviewed primary policy locator |
| Variable | `RECOVERY_BUCKET` | Independent recovery bucket name |
| Variable | `RECOVERY_ENDPOINT` | Recovery S3-compatible HTTPS endpoint |
| Variable | `RECOVERY_REGION` | Recovery signing region |
| Variable | `RECOVERY_POLICY_EVIDENCE` | Reviewed recovery retention/access policy locator |
| Variable | `RECOVERY_INDEPENDENCE_EVIDENCE` | Reviewed explanation/evidence of recovery independence |
| Secret | `PRIMARY_EVIDENCE_READ_ACCESS_KEY_ID` | Primary read-only recovery credential |
| Secret | `PRIMARY_EVIDENCE_READ_SECRET_ACCESS_KEY` | Primary read-only recovery credential |
| Secret, optional | `PRIMARY_EVIDENCE_READ_SESSION_TOKEN` | Temporary primary read token |
| Secret | `RECOVERY_ACCESS_KEY_ID` | Recovery write/read credential |
| Secret | `RECOVERY_SECRET_ACCESS_KEY` | Recovery write/read credential |
| Secret, optional | `RECOVERY_SESSION_TOKEN` | Temporary recovery token |

The primary credential should be read-only and remains separate from normal archive ingestion credentials.

## What a successful national live run proves

For the exact frozen release supplied to the run, the workflow must:

1. validate the reviewed release manifest against its exact pinned source configuration;
2. read back immutable catalogue provenance for every selected capture/check;
3. read the corresponding primary durable object for every selected capture and verify byte size/SHA-256;
4. retain distinct capture identities even when multiple checks reuse unchanged bytes;
5. back up each distinct ContentObject to the independent recovery target through the conditional content-addressed `EvidenceStore` contract;
6. fully retrieve and hash every recovery object;
7. restore each distinct object into a new clean local path;
8. compare every restored object with the independently verified primary bytes;
9. emit only redacted public verification receipts plus a release-level summary with selected-capture and distinct-ContentObject counts.

Repeated runs are idempotent at the ContentObject layer: an existing recovery object is accepted only after full retrieval and hash verification. An existing local restore path fails before recovery work can masquerade as a clean restore.

## Public artifact contract

This repository is public, so Actions artifacts are treated as public evidence. The workflow uploads only deliberately redacted receipts. It never uploads originals, parser workspaces, capture catalogue records, provider coordinates, policy locators, credentials or the reviewed independence statement itself.

`public_recovery_receipt()` excludes primary/recovery endpoints and buckets, namespace fingerprints, storage URIs, policy evidence and the independence evidence text. A SHA-256 digest can bind the public receipt to the separately retained reviewed independence record without disclosing it.

The release-level summary contains only the public release id/code revision, selected-capture count, distinct-ContentObject count and boolean verification outcomes.

## What the workflow does not prove

Unit and CI tests prove application behaviour only. They do not establish that any real recovery target is independent, durable or correctly administered.

A different namespace fingerprint proves only that the exact endpoint+bucket tuple differs. The reviewed independence record and an actual successful restore are required before independent restore can satisfy the national temporal archive acceptance criteria.

The workflow does not create cloud resources, configure billing, rotate credentials, alter retention controls, publish source originals or promote database/public rows.

The historical storage/provider gate remains separate evidence. National archive completion additionally requires the selected frozen national release to exist, its complete capture set to be durably retrievable and provenance-verified, production observation persistence to be established, archive-backed replay/public gates to pass, and this independent restore to succeed for the same selected release.
