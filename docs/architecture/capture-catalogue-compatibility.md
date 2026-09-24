# Capture catalogue provenance compatibility

The private CaptureCatalogue is the durable capture/check layer beside the content-addressed original. A `ContentObject` establishes which bytes were acquired; a catalogue record must preserve enough frozen acquisition provenance to identify and interpret that particular check even when later relational persistence is unavailable.

## Complete frozen manifest for new records

New catalogue records embed the complete validated `capture_manifest` in addition to the existing denormalised identity fields and `capture_manifest_sha256`. This retains optional acquisition provenance such as `origin_type`, `authority_rank_code` and `resource_type_code`, and avoids losing future validated manifest fields merely because they were not part of an older fixed projection.

The embedded manifest does not create a second document identity. Content remains addressed by SHA-256 and byte size, while each capture/check keeps its own stable `capture_id` and capture time. The manifest digest continues to bind the exact frozen metadata that accompanied the durable ContentObject readback.

## Existing v1 records

Catalogue objects written before complete-manifest preservation are not rewritten or silently relabelled. They remain readable through an explicit compatibility path when their existing denormalised fields and `capture_manifest_sha256` match the exact historical manifest supplied for verification. The absence of an embedded manifest in such a record remains an archival limitation: omitted metadata must not be reconstructed from current configuration, neighbouring captures or aggregate history.

A retry of an already-recorded capture/check also preserves the original catalogue bytes. `content_verified_at` records the readback/processing event that first established that catalogue object; a later successful readback has a new processing time but does not create a new administrative publication or change capture identity. An exact retry therefore validates the existing immutable object and returns its actual digest rather than overwriting it.

## Recovery consequence

The national recovery inventory may distinguish complete-manifest catalogue records from legacy catalogue records when assessing provenance quality. Both still require durable ContentObject verification and immutable catalogue readback before a capture can count as verified. A legacy record does not authorise inference of fields it never stored directly, and this compatibility path does not manufacture historical SourceEdition or SourceCapture facts.
