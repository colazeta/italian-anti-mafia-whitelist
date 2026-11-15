# Physical interpretation reuse and downstream publication tooling

The protected transformer verifies the genuine capture and all labelled byte
inputs before looking for an existing successful interpretation. Reuse requires
the same parser name, per-source configuration hash, complete labelled input
hashes and equivalent interpretation code. Every matching stored snapshot is
read and rehashed; conflicting or corrupt copies prevent reuse. Current QA flags
are recomputed from the verified stored output. A reused snapshot is not a new
administrative SourceEdition or a publication approval.

## Observed cause of repeated work

A direct production SELECT on 15 November 2026, following checkpoints at
15:16:20 and 16:57:51 UTC, found two post-checkpoint parse runs but only one
distinct complete snapshot/record payload for each of:

| SourceSeries | Records per identical payload |
| --- | ---: |
| `aosta-listed` | 236 |
| `aosta-applicants` | 148 |
| `taranto-listed` | 383 |
| `taranto-applicants` | 226 |
| `potenza-combined` | 1,057 |

That is five repeated revisions / 2,050 repeated record occurrences, not new
source facts, distinct firms or editions. Como's two versioned payloads differ
and are not classified as duplicates. All historical snapshots and their
processing provenance remain immutable and retained.

The previous equivalence key hashed the entire publishing directory as one Git
tree. Editing the downstream `como_review.py` or `publication_handoff.py`
therefore invalidated unrelated physical interpretations even though parser,
inputs and their per-source configuration had not changed. These changes can be
triggered indirectly by a later ordinary acquisition cycle, not only by the
commit that changed the release tooling.

## Conservative boundary

`acquisition.interpretation_code` now verifies all required footprint roots and
compares their complete recursive tracked Git objects, excluding exactly:

- `publishing/publication_handoff.py`: downstream finite intent/selector handling;
- `publishing/como_review.py`: downstream review of already parsed source output.

Physical parsing, normalisation and the retained interpretation modules do not
import either excluded module. An AST import-boundary regression guards that
separation, including literal dynamic module imports. If a retained module
starts depending on either tool, that exclusion must be reconsidered; it cannot
silently become an unhashed interpretation dependency.

Every physical parser, dispatcher, public record contract, national-index
dependency, runtime declaration and **other existing or new publishing object**
continues to invalidate reuse when changed. Unknown new helpers are included
automatically rather than assumed safe. Missing Git objects, incomplete roots,
an otherwise empty publishing tree or Git errors cannot prove equivalence.
The existing complete input/configuration, snapshot-integrity, provenance and
quality gates are unchanged. A real parser/configuration change still yields a
new versioned interpretation when appropriate.

Tests use real Git repositories and cover addition/edit/deletion of downstream
tools; parser/runtime/dispatcher/contract/unknown-helper changes; incomplete
trees; missing revisions; corrupt stored snapshots; and the import boundary.
Production acceptance must additionally show unchanged source inputs reused by
the ordinary protected workflow without new duplicate snapshots. Issue #225
records that observed result separately from unit-test or merge success.
