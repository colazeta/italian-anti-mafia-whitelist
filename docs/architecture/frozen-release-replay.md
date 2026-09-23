# Frozen release replay gate

A frozen release is an immutable selection of already archived source captures plus the exact parser, projector, configuration and code revisions that interpret them. It is not a request to reacquire the currently served Prefecture URLs.

## Selecting a frozen release

`white-list-select-frozen-release` creates a candidate release manifest from an explicit reviewed selection of already archived capture manifests and immutable capture-catalogue receipts. Selection is deliberately separate from acquisition and from public promotion.

Before it can emit a manifest, the selector requires the private selection to cover every and only source configured for the national publication scope. It binds the configured parser name and configuration digests, preserves the selected parser/projector revisions, and then performs two independent provider checks for every selected resource: immutable capture-provenance readback through `CaptureCatalogue.verify_receipt` and full ContentObject byte readback through `EvidenceStore.read_verified`. A missing, corrupt, mismatched or unverified selected capture fails closed. There is no live-source fallback.

The private selection cannot supply release processing time or executing code identity. The selector derives `code_revision` from the exact checked-out Git `HEAD` and creates `created_at` at selection time. These release-processing fields remain distinct from every source's declared reference/publication time and capture time, all of which stay attached to the selected capture provenance. This prevents an operator-authored selection from labelling a manifest as if it had been produced by another code revision or at a source-administrative time.

The selector does not discover missing historical versions, infer a source edition from a URL, or treat a recovery-package path as a verified capture. It also does not publish or deploy anything. Its JSON output is create-only and must be reviewed before it is committed under `data/releases/`. A successful selector run therefore proves only that the captures chosen for that candidate were provider-readable with matching immutable provenance at selection time; national archival completeness still depends on the separately reconciled recovery denominator.

## Locator identity during replay

A source URL remains a physical locator and is never used as the archival identity of a capture or ContentObject. The legacy parser plumbing still requests bytes by URL, so frozen replay exposes a temporary URL-keyed routing adapter only after archival verification has completed.

That adapter must not collapse provenance. If two configured source scopes reuse the same URL and the same bytes, replay independently verifies both selected capture/check catalogue records and independently reads the selected ContentObject for each capture before allowing parser execution. Only the identical verified byte payload is then shared through the URL adapter. If the same locator is bound to different bytes within one frozen release, replay fails closed because the legacy parser interface cannot unambiguously route those two selected inputs. Distinct capture identities are therefore preserved even when locator and ContentObject identity happen to coincide.

## Operational replay

`.github/workflows/replay-frozen-release.yml` is the protected, manual replay path for a reviewed release manifest committed under `data/releases/`.

The workflow deliberately separates release selection from execution:

1. it starts only from `main` and accepts only a tracked JSON manifest resolving under `data/releases/`;
2. it copies that reviewed manifest outside the checkout and reads its exact 40-character `code_revision`;
3. it checks out that pinned revision rather than interpreting the release with whichever code happens to be current later;
4. it uses the existing `evidence-archive` environment and approved private object store;
5. it invokes `white-list-public-national-build` with `--release-manifest`, which replaces legacy source downloads with verified reads of the selected immutable ContentObjects and capture-provenance records;
6. it writes replay products only to runner-temporary storage and validates the resulting registry without uploading or deploying it.

The release path is fail-closed. A selected ContentObject or capture-provenance record that is absent, corrupt or inconsistent with the manifest stops replay. An official URL that has disappeared or now serves different bytes is irrelevant to a valid frozen replay and is never substituted for the selected capture.

The workflow does **not** promote a release. Public deployment remains a distinct serial integration decision after the selected release has satisfied its full integrity and public-contract gates.

## Code revision pinning

A release manifest can be created after the code revision it selects. Consequently, replay first reads the reviewed manifest from current `main`, freezes that manifest in runner-temporary storage, and then checks out the manifest's pinned code revision. This avoids the incorrect alternative of requiring an old release to be replayed by current code merely because the manifest itself was catalogued later.

The manifest is validated again by the frozen-release runtime. Parser revision, projector revision, configuration digest and code revision are executable pins rather than descriptive metadata.

## What this gate proves — and what it does not

A successful protected run proves that one reviewed release can be rebuilt from its selected private archived captures with the live official endpoints out of the execution path. It is evidence of replayability for that release.

The existence of the workflow, its unit tests or a synthetic-store run does not establish national archival completeness. In particular it does not prove:

- that every historically acquired source version is present in the governed store;
- that the national recovery denominator has been reconciled against real catalogue objects and recovery packages;
- production persistence of all historical observations or interpretation revisions;
- independent backup/restore capability;
- that a complete national release manifest has been selected and successfully replayed on the real provider.

Those acceptance dimensions remain separate in issue #163. The historical R2 provider gate also remains distinct from national capture coverage and independent restore evidence.

## Relationship to the legacy public workflow

`public-pages.yml` still uses the legacy live-source build while the archive migration is incomplete. It must not be switched to frozen-release publication merely to avoid mutable-source failures before a complete, reviewed national frozen release exists. The last validated public release is preserved during that migration.
