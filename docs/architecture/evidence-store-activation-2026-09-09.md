# R2 evidence-store activation record — 2026-09-09

## Status

**LIVE PROVIDER VERIFICATION REQUIRES RETEST.**

This record documents the operator-confirmed configuration of the designated private Cloudflare R2 backend for the White List source-evidence archive. It is an operational attestation and configuration locator; it does **not** by itself prove provider durability, backup adequacy or restore capability.

The production-readiness gate remains open until the live verification workflow succeeds and the independent backup/restore requirement is documented and tested.

## Designated backend

- Provider: Cloudflare R2 Object Storage
- Bucket: `italian-anti-mafia-whitelist-evidence`
- Jurisdiction: European Union
- Default storage class: Standard
- S3 signing region used by the application: `auto`
- S3 endpoint pattern: `https://<ACCOUNT_ID>.eu.r2.cloudflarestorage.com`
- Evidence namespace: `sha256/`

No credentials, account identifiers or secret values are recorded in Git.

## Access and immutability controls

Operator-confirmed on 2026-09-09:

- public development URL is not enabled;
- no custom domain is attached to the bucket;
- a Bucket Lock rule applies to prefix `sha256/` with indefinite retention;
- the ingestion credential is an account API token restricted to this bucket with Object Read & Write permissions;
- GitHub environment `evidence-archive` holds the runtime configuration and credentials separately from the repository.

The application writes evidence only under content-addressed keys of the form:

```text
sha256/<first-two-hex>/<full-sha256>
```

The indefinite Bucket Lock is the effective provider-side control preventing deletion or overwrite of evidence objects in that namespace. Application-side conditional creation (`If-None-Match: *`) and post-write full-object SHA-256 verification remain mandatory independent controls.

## First live verification attempt

The first `Private evidence store verification` run on 2026-09-09 passed environment/configuration and credential preflight, reached the designated R2 bucket and then failed during the repeated-upload idempotence probe. R2 returned `ObjectLockedByBucketPolicy` for the already protected content-addressed key instead of the `412 PreconditionFailed` response assumed by the generic S3 adapter.

This is a provider-response compatibility issue, not a reason to weaken immutability. The adapter is amended to treat `ObjectLockedByBucketPolicy` only as a **possible existing-object signal**. It must then retrieve the full object and independently verify byte size and SHA-256 before returning an idempotent success. A missing or mismatching object still fails; no unconditional overwrite, delete, lock bypass or metadata-only trust is introduced.

The live gate therefore remains open until the corrected adapter is merged and the manual workflow is rerun successfully.

## GitHub environment contract

The `evidence-archive` environment is expected to contain:

| Kind | Name | Expected value/purpose |
| --- | --- | --- |
| Variable | `EVIDENCE_BUCKET` | `italian-anti-mafia-whitelist-evidence` |
| Variable | `EVIDENCE_ENDPOINT` | EU-jurisdiction R2 S3 HTTPS origin |
| Variable | `EVIDENCE_REGION` | `auto` |
| Variable | `EVIDENCE_POLICY_EVIDENCE` | this document's repository-relative path |
| Secret | `EVIDENCE_ACCESS_KEY_ID` | restricted R2 ingestion credential |
| Secret | `EVIDENCE_SECRET_ACCESS_KEY` | restricted R2 ingestion credential |
| Secret, optional | `EVIDENCE_SESSION_TOKEN` | temporary token if applicable |
| Secret, optional | `EVIDENCE_DATABASE_URL` | existing archive database for verified promotion |

The intended value of `EVIDENCE_POLICY_EVIDENCE` is:

```text
docs/architecture/evidence-store-activation-2026-09-09.md
```

## Controls not yet evidenced by this record

The following remain explicit open gates and must not be represented as verified merely because R2 accepts writes:

1. successful live upload, repeated conditional upload, full-object retrieval and SHA-256 verification against the frozen Cosenza manifests;
2. independent backup/recovery responsibility and a documented restore test;
3. any provider-level retention/version-recovery settings outside the verified `sha256/` Bucket Lock;
4. optional database promotion through `EVIDENCE_DATABASE_URL`;
5. periodic re-verification of access and retention controls.

Until those gates are closed, issue #16 remains open and national readiness must not be advanced to a fully provisioned/durable state.

## Change-control rule

Any later change to bucket name, jurisdiction, endpoint, public-access state, lock prefix/retention, credential scope, backup policy or recovery design requires an updated activation record and corresponding documentation change. Secret values must never be committed to Git, public artifacts, issue comments or receipts.
