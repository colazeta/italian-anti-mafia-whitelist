# Dataset Explorer UI style

## Design rule

The Dataset Explorer uses a deliberately restrained **administrative-management-system** visual language, closer to a 1990s/early-2000s institutional database application than to a modern analytics dashboard.

The goal is to make structure, fields, rows and provenance immediately inspectable. Decorative visualisation must never compete with the data model.

## Required characteristics

- Dense tables are the primary information surface.
- Neutral grey/white chrome, thin borders and compact spacing.
- System sans-serif fonts for interface text; monospace for identifiers, hashes, locators and technical names.
- Tabs and simple toolbars instead of large navigation cards.
- Summary values appear primarily in status rows or compact tables, not KPI cards.
- No gradients, glass effects, oversized typography, decorative illustrations or dashboard-style chart decoration.
- Hover/selection states may be visually stronger, but should resemble a management application rather than a consumer website.
- Source observations, canonical facts and release status must remain explicitly labelled in text; colour alone is never sufficient.

## Information architecture

The two primary product surfaces are:

1. **Struttura dataset** — a readable map of the full logical data model, objects, tables/areas, status of population and meaning.
2. **Esplora i dati** — dense browse/filter/drill-down tables over the actual source observations and later canonical data.

Supporting tabs include snapshot comparison, national coverage, provenance and methodology.

## Dataset-structure rule

Do not expose only the currently populated pilot subset as if it were the whole data model. The structure view must show the complete logical architecture even when a layer is not yet populated, and must state its population status explicitly.

## Accessibility

The deliberately old-style visual language must not reproduce old accessibility problems. Maintain usable contrast, keyboard-compatible controls, clear text labels and responsive overflow for wide tables.
