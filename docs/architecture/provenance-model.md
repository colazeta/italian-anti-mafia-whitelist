# Provenance and reproducibility

The archive follows the W3C PROV distinction between entities, activities, and responsible agents at a conceptual level.

## Immutable source chain

```text
SourceResource
  → SourceCapture
      → ContentObject (SHA-256)
          → ParseRun
              → ParsedRecord
                  → SourceFieldValue
```

The byte identity of a `ContentObject` is immutable. A repeated capture may point to the same content object; storage metadata may change without changing the content identity.

`SourceFieldValue` rows are append-only. Correcting a parsing error requires a new `ParseRun`, not an update to a previous raw value.

## Versioned processing

`ProcessingActivity` stores software, version, configuration hash and execution times. `ParseRun` is a typed parsing attempt linked to one immutable content object.

The same PDF can therefore produce:

```text
PDF hash H
  → parser 1.0 → interpretation A
  → parser 2.0 → interpretation B
```

without losing A.

Canonical version rows (`EntityName`, `EntityIdentifier`, `Establishment`, White List state versions and procedure versions) also reference the `ProcessingActivity` that generated them. Evidence therefore answers **what supports the fact**, while the processing link answers **how this canonical representation was produced**.

## Resolution

`EntityMention` and `ProcedureMention` are source-level occurrences. They are connected to canonical objects only through explicit resolution decisions, with method, confidence, processing activity and system-time history.

Accepted resolutions are non-overlapping in system time. The database therefore cannot hold two simultaneously accepted canonical identities for the same mention.

## Evidence

Canonical states never rely on a single hard-coded `source_record_id`. Evidence items can be:

- a field value;
- a parsed record;
- a source edition;
- a source capture.

This is necessary because facts such as “listed entity” may be established by a document heading or list context rather than a dedicated cell.

## Derived events

Derived events retain the derivation rule/version and explicit links to the concrete canonical state versions used as inputs. This allows an event to be regenerated after a rule or parser change.
