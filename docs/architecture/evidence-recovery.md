# Independent evidence backup and restore gate

## Status

The repository contains an executable, provider-neutral backup and clean-restore gate for the durable source-evidence archive. **The gate is tooling-ready, not live-verified.** No independent recovery provider, account, bucket or credential is provisioned by this repository, and no such resource is created by the workflow.

Issue #16 therefore remains open until a genuinely independent recovery target is designated, the recovery environment is configured and the manual workflow passes against the frozen Cosenza evidence. Production database promotion is a separate remaining #16 control.

## Purpose

The primary evidence store protects exact source bytes through content-addressing, conditional creation, full-object retrieval and SHA-256 verification. That protects integrity inside the primary namespace, but it is not an independent recovery copy.

The recovery gate tests a separate property:

```text
verified primary durable object
        ↓ full GET + frozen SHA-256 check
short-lived runner file
        ↓ local manifest verification
independent recovery object store
        ↓ full GET + frozen SHA-256 check
clean local restore path
        ↓ independent size + SHA-256 check
redacted verification receipt
```

Raw source bytes remain private throughout this path. They are not committed to Git and are not uploaded as GitHub Actions artifacts.

This repository is public, so workflow artifacts must not be described or treated as private. GitHub Actions artifacts in a public repository are readable by users with repository read access and public artifact metadata is available through the Actions API. The workflow therefore uploads only a deliberately redacted verification receipt. Provider endpoints, bucket names, namespace fingerprints, policy locators and the reviewed independence statement itself are never written to the uploaded artifact.

## Fail-closed independence contract

`white_list_archive.storage.recovery` computes a non-secret fingerprint of the exact object-store namespace from the normalized endpoint and bucket name. The recovery helper refuses a target whose fingerprint equals the primary namespace.

That mechanical check is deliberately narrow. A different bucket name, endpoint or account identifier does **not** by itself prove independent recovery. The workflow also requires `RECOVERY_INDEPENDENCE_EVIDENCE`, a reviewed operator locator documenting why the recovery target is an independent administrative/failure domain appropriate for recovery. The project must not infer independence merely because two S3-compatible configurations differ.

A defensible live configuration should document, at minimum:

- who administers the primary and recovery copies;
- whether the recovery copy survives loss, lockout, deletion or provider failure affecting the primary namespace;
- retention/immutability and deletion privileges for the recovery copy;
- recovery responsibility and the procedure for restoring exact bytes;
- the successful restore-test evidence and date.

The current Cloudflare R2 Bucket Lock on the primary `sha256/` namespace remains unchanged. A recovery test must never require weakening or removing it.

## Recovery workflow

`.github/workflows/evidence-recovery.yml` is manual and main-only. It uses a dedicated GitHub environment named `evidence-recovery`.

Configure these environment variables only after an independent recovery target has been approved:

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
| Secret | `PRIMARY_EVIDENCE_READ_ACCESS_KEY_ID` | Primary **read-only** recovery credential |
| Secret | `PRIMARY_EVIDENCE_READ_SECRET_ACCESS_KEY` | Primary **read-only** recovery credential |
| Secret, optional | `PRIMARY_EVIDENCE_READ_SESSION_TOKEN` | Temporary primary read token |
| Secret | `RECOVERY_ACCESS_KEY_ID` | Recovery write/read credential |
| Secret | `RECOVERY_SECRET_ACCESS_KEY` | Recovery write/read credential |
| Secret, optional | `RECOVERY_SESSION_TOKEN` | Temporary recovery token |

The primary credential used here should be read-only. It is intentionally separate from the normal ingestion credential in `evidence-archive`, so a recovery operation does not need primary write privileges.

## What a successful live run proves

For each frozen Cosenza capture manifest, the workflow must:

1. read the primary durable object and independently verify byte size and SHA-256;
2. stage those already-verified bytes only on the ephemeral runner;
3. archive them to the recovery target through the same conditional, content-addressed `EvidenceStore` contract;
4. fully retrieve and hash the recovery object;
5. restore it to a new clean local path that did not exist before the test;
6. hash the restored file again and compare the restored bytes to the independently verified primary bytes;
7. emit a redacted JSON verification receipt containing only content identity, whether the content-addressed backup was newly created, an assertion that the recovery target differed from the primary namespace, a SHA-256 digest binding the run to the reviewed independence record, and the clean-restore verification time.

The complete runtime receipt is kept in memory only for the duration of the job. It contains provider coordinates and policy evidence needed by the control logic but is not written to a GitHub artifact. The digest of `RECOVERY_INDEPENDENCE_EVIDENCE` lets an operator later match the public verification receipt to the separately retained reviewed independence record without disclosing that record in the public repository.

Repeated runs are idempotent: an existing content-addressed recovery object is accepted only after full retrieval and hash verification. An existing local restore path fails before any recovery write, preventing a dirty restore directory from masquerading as a recovery test.

## Public artifact contract

`public_recovery_receipt()` is the publication boundary for recovery evidence. Tests require the uploaded JSON to exclude:

- primary and recovery endpoint or bucket coordinates;
- primary and recovery namespace fingerprints;
- storage URIs;
- primary or recovery policy locators;
- the reviewed independence evidence text or locator;
- raw evidence bytes.

The redacted artifact is verification evidence, not the independent recovery record itself. The authoritative independence assessment remains an operator-controlled record outside the public artifact.

## What the workflow does not prove

Static/unit tests use an in-memory protocol double and prove only application behaviour. They do not establish that any real recovery target is independent, durable or correctly administered.

Likewise, a different namespace fingerprint proves only that the exact endpoint+bucket tuple differs. The `RECOVERY_INDEPENDENCE_EVIDENCE` review and an actual successful live restore are required before the independent backup/restore acceptance criterion in #16 can be marked complete.

The workflow does not create cloud resources, configure billing, rotate credentials, alter Bucket Lock, publish source PDFs or promote database rows.

## Remaining #16 boundary

After this tooling is merged and verified in CI, the remaining external decisions are explicit:

1. designate/configure an independent recovery target and execute this workflow successfully;
2. designate/configure an existing hosted archive PostgreSQL database as `EVIDENCE_DATABASE_URL` and verify production `ContentObject` promotion.

Until those live controls are executed, durable source storage is primary-provider verified but issue #16 is not complete.
