# Canonical national data dictionary

The database uses one national semantic representation regardless of how an individual Prefecture labels or formats its data. The authoritative machine-readable registry is seeded in `mapping.canonical_field`; this document highlights the most important mappings.

| Canonical path | Meaning | Source variants may include |
|---|---|---|
| `entity_name.name` | Canonical entity name | Ragione sociale; Denominazione; Denominazione e ragione sociale |
| `entity_name.language` | Language tag of the entity name | usually implicit in Italian sources |
| `entity_identifier.value` | External identifier value | Codice fiscale; P. IVA; Codice fiscale/Partita IVA |
| `white_list_register.id` | Concrete administrative White List register | implicit in publishing Prefecture/page |
| `relationship_state.nominal_valid_from` | Nominal start/enrolment date asserted by the source | Data iscrizione; Data di iscrizione |
| `relationship_state.nominal_valid_until` | Nominal expiry asserted by the source | Data scadenza; Data scadenza iscrizione |
| `relationship_state.legal_effect_status` | Canonical legal-effect state | may require interpretation of notes/renewal context |
| `relationship_sector.sector_concept` | Canonical activity concept represented in the register | Sezione; Attività; I/III/VI/X |
| `relationship_sector.scheme_membership` | Versioned legal notation used by the source | Sezione X; X; sez. 10 |
| `procedure.application_date` | Application submission date | Data presentazione istanza; Data domanda |
| `procedure.status` | Canonical administrative procedure status | Esito; In istruttoria; Aggiornamento in corso |
| `source.origin_type` | Provenance class of a capture | current official page; historical official portal; archive capture |
| `provenance.processing_activity` | Versioned transformation generating a canonical assertion | parser/normaliser/resolver activity |

## Rule

**One canonical field represents one semantic concept.**

Different labels with the same meaning map to one field. Similar-looking labels with different legal or temporal meaning remain separate.

Raw labels and values are retained unchanged in the source layer. Missing canonical values use SQL `NULL`; reasons such as “not published”, “unreadable” or “ambiguous” belong in source/provenance metadata rather than being encoded as pseudo-values.
