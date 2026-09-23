# National recovery evidence reconciliation

## Purpose

The national temporal archive has three related but distinct evidence questions:

1. which source acquisitions have a stable archive-first capture identity and immutable capture/check provenance;
2. which historical byte versions are positively known from repository evidence even when no durable capture identity survives; and
3. which aggregate source scopes were part of an approved public release.

These layers must not be collapsed. A known hash does not retroactively create a `SourceCapture` or `SourceEdition`, and an aggregate public-history digest does not by itself prove possession of one raw `ContentObject`.

## Recovery denominator identity classes

The recovery denominator uses two raw-source identity classes:

- `capture`: an archive-first acquisition with a stable capture identifier, exact byte identity and immutable capture/check provenance;
- `known_version`: a historically observed byte identity supported by reviewed evidence but without a recoverable capture identity.

A `known_version` reconciliation key is an internal evidence key only. It is not an administrative edition identifier. Matching bytes in durable storage do not make a `known_version` `verified`, because the missing temporal capture provenance is still missing.

Recovery outcomes remain conservative:

- `verified`: exact durable bytes and immutable capture/check provenance both read back and verify;
- `recoverable_pending`: exact bytes are available in an explicitly supplied recovery package but have not yet been promoted as a verified governed capture;
- `missing`: byte size is known, durable absence is positively confirmed and the declared recovery search is complete;
- `not_verified`: every other unresolved condition, including incomplete searches, provider errors, unknown byte size, corruption or missing temporal provenance.

Repeated acquisitions/checks are evidence in their own right. Two monitoring checks with the same timestamp and the same bytes therefore retain separate evidence identities. Unchanged bytes may still point to one content-addressed object.

## Public history is a separate aggregate layer

`data/history/public_history.json` is an aggregate publication ledger. It records approved edition scopes, parser signatures, source/reference labels, successful verification checks and a `document_sha256`.

That digest must not be interpreted automatically as a raw `ContentObject` identity. The public-history builder accepts both scalar source capture identities and `bundle:<sha256>` identities, then stores only the resulting digest. The aggregate ledger therefore does not preserve enough information to prove whether a digest represents one raw source object or a bundle-derived publication identity.

Recovery reconciliation consequently imports public-history editions only as `published_release_scopes`. Each scope preserves:

- the stable public-history edition ID;
- authority and source keys;
- the aggregate document digest with explicit `public_history_document_digest` semantics;
- parser signature;
- declared reference date/raw label;
- successful history checks and their timestamps;
- repository evidence references.

`published_release_scopes` are counted separately from captures, known raw versions, distinct ContentObjects and durable originals. They never become `known_version` rows merely because a digest happens to match another evidence item.

This separation preserves the existing public-history IDs and avoids silently changing their meaning during the archive migration.

## Repository evidence reconciliation

The repository reconciler currently admits:

- timestamped monitoring checks that positively record a source SHA-256;
- legacy source-capture manifests with authority, SHA-256, byte size, capture time and resource URL;
- lower-specificity authority-level known hashes not already represented by stronger repository evidence;
- aggregate public-history editions as separate publication scopes.

Analytical diff/profile JSON files do not enter the raw-source denominator. Evidence paths are stored repository-relative, never as runner-local filesystem paths.

The repository reconciler does not inspect the governed object store and cannot assign final recovery outcomes by itself. Provider/catalogue verification, recovery-package inspection and any declaration that a search is complete remain separate operational steps.

## Private operational materialisation

`white-list-recovery-reconcile` bridges the repository-supported denominator to those operational checks without making object-store discovery the denominator. It takes a private, operator-reviewed recovery plan and then performs exact readback verification through the existing `EvidenceStore` and `CaptureCatalogue` contracts.

The private plan may supply only facts that repository evidence cannot establish safely:

- archive-first captures with their stable capture UUID, frozen capture manifest and immutable catalogue receipt;
- explicit recovery-package paths for an already-known historical version;
- a reviewed byte size when repository evidence did not retain it;
- positive durable-absence decisions for individual denominator items; and
- a global declaration that the recovery search is complete.

The plan cannot mint a historical `known_version`. Every historical recovery overlay must match an existing repository-supported authority + evidence-version key + SHA-256 identity. A reviewed byte size cannot replace a conflicting size already retained by repository evidence. Any operational size, recovery path or durable-absence assertion requires an operator evidence reference. This keeps the provenance of recovery decisions explicit without committing private package paths or provider coordinates to Git.

Archive-first captures are different because their capture UUID and immutable catalogue record are themselves positive acquisition identity. They may therefore enter the operational plan even when the public repository intentionally does not contain private capture records. A capture becomes `verified` only after both the selected ContentObject bytes and the selected catalogue record are read back from the governed provider and independently verified.

The command writes a new report with exclusive-create semantics and refuses to overwrite an earlier report. The report contains recovery identities, statuses and metrics but does not expose provider endpoint/bucket configuration or source bytes. The recovery plan and resulting operational report are private operator artefacts unless deliberately reviewed for another dissemination boundary.

A minimal operational plan has this shape:

```json
{
  "schema_version": 1,
  "generated_at": "2026-09-23T03:00:00+00:00",
  "recovery_search_complete": false,
  "captures": [],
  "known_version_recovery": []
}
```

`recovery_search_complete` defaults operationally to a reviewed decision, not to a successful command execution. It must remain `false` until the governed store/catalogue and all declared recovery locations in the selected denominator have actually been searched. Likewise, absence from a provider listing is never sufficient to set an item's `durable_absence_confirmed` flag.

## Compatibility

The recovery-denominator schema remains version 1 while `published_release_scopes` is an optional extension. Existing callers that provide only captures and known versions remain valid. New reconciler output includes the field explicitly.

Monitoring evidence keys now include the stable ledger check position in addition to observed time and content digest. This prevents equal-time repeated checks from colliding. No persisted national denominator used the earlier generated key form, so this is an implementation-key correction rather than a migration of established archive or administrative IDs.

## Non-claims

Repository reconciliation and operational materialisation tooling do not by themselves establish:

- national durable-byte coverage;
- successful real-provider readback until the command is actually run against the approved private backend;
- production historical-observation persistence;
- independent backup/restore;
- a complete frozen national release;
- or that a historical version is missing unless the explicit positive-absence and completed-search gates are satisfied.

Those claims require their own positive acceptance evidence under issue #163.
