# Catania 13 November: exact capture provenance readback

This is a **source-only** diagnostic for the two already-frozen 13 November
2026 XLSX original digests in `catania_november13_archive_qa.PINS`.
The primary R2 SHA/size verification and the private ten-row tail dossier
do **not** prove that either original was entered in the immutable capture
catalogue or registered in PostgreSQL. Prior independent PostgreSQL readback
found 0/2 matching ContentObjects/captures for those exact digests.

The existing protected `Transform reviewed captures` shard 0 now calls
`storage.catania_capture_provenance_audit`. It reuses the bounded
`audit_historical_catalogue` contract: each SourceSeries prefix is checked
for up to 64 pre-existing UUID-keyed catalogue entries; a positive match
requires the embedded complete capture manifest, verified catalogue receipt
and independently verified exact original bytes. Provenance metadata required
for a *possible later* source-only database writer is counted separately.
Truncated or inaccessible listings and missing/legacy manifests stay
`unknown` rather than becoming evidence of absence. The audit performs
**zero writes**. No current-source fetch, new capture, approval, parser
change, administrative event, semantic projection or public promotion occurs.

Only closed aggregate scope/status/count/availability fields leave the
trusted workflow. Do not emit original hashes, names, personal data, capture
IDs, locator, provider exception or archive keys into a GitHub comment/log.

If exact immutable provenance is positively verified, next review the
source-only append-only writer contract (capture UUID and original identity,
capture timestamp, original resource locator/type, authority rank and scope)
and independently read back PostgreSQL before treating the relational
binding as complete. An available original with no verifiable capture
manifest is not enough to authorise constructing a new capture UUID/date.
The ten Catania listed tail rows still require private document-level
classification and a versioned parser with QA before any new public release.
The selected Alessandria release and all its Catania 6 Nov/Perugia 5 Nov
observations remain untouched. Independent recovery is a separate control.

## Private tail packet repeat acceptance (14 November 2026)

The protected step must demonstrate **both** first readback and same-code,
same-original, same-packet reuse on the immutable `IfNoneMatch` key. The second
staging invocation must report `created=false`, the same complete packet digest
and source-shape counts, with a full second readback. Existing private packet
content must never be replaced: a conflicting object or failed second readback
fails closed with a redacted error. Only a boolean repeat-reuse verdict and
aggregate counts may leave the protected workflow. This is not a second
acquisition, an authenticated documentary classification of the ten tail rows,
a CaptureCatalogue receipt, a PostgreSQL write, an approved SourceEdition or a
public release. The two original Catania SHA pins remain unchanged.
